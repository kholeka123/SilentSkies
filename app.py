# Silent Skies: Updated Streamlit Dashboard with Enhancements

import streamlit as st
import pandas as pd
import requests
import os
from datetime import datetime
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import seaborn as sns
import pydeck as pdk

# === Static fallback coordinates for airports ===
AIRPORT_COORDS = {
    "EDDB": {"lat": 52.3667, "lon": 13.5033},  # Berlin Brandenburg
    "LFPG": {"lat": 49.0097, "lon": 2.5479},   # Paris CDG
    "EGLL": {"lat": 51.4700, "lon": -0.4543}   # London Heathrow
}

load_dotenv()

st.set_page_config(page_title="Silent Skies", layout="wide")
st.title("\U0001F303️ Silent Skies: Noise, Flight Arrivals & Weather Dashboard")
st.sidebar.header("🔧 Settings")

api_key = st.sidebar.text_input("🔑 AeroDataBox API Key", type="password")
weather_key = st.sidebar.text_input("🔑 OpenWeatherMap API Key", type="password")
icao_list = st.sidebar.multiselect("🛬 Select Airports", options=list(AIRPORT_COORDS.keys()), default=["EDDB"])
noise_file = st.sidebar.file_uploader("📄 Upload Noise Data CSV", type="csv")
st.sidebar.download_button(
    label="Download Sample Noise CSV",
    data="timestamp,noise_db,max_slow\n2025-07-01T12:00:00+02:00,65,72\n2025-07-01T12:15:00+02:00,68,74\n",
    file_name="sample_noise.csv",
    mime="text/csv"
)

# Set environment variables if keys entered
if api_key:
    os.environ["AERODATABOX_API_KEY"] = api_key
if weather_key:
    os.environ["OPENWEATHER_API_KEY"] = weather_key

# === Load and process noise data ===
if noise_file:
    try:
        df_noise = pd.read_csv(noise_file)
        if 'timestamp' not in df_noise.columns:
            st.error("Missing 'timestamp' column in noise data.")
            st.stop()
        df_noise['timestamp'] = pd.to_datetime(df_noise['timestamp'], errors='coerce')
        df_noise.dropna(subset=['timestamp'], inplace=True)
        def localize_or_pass(x):
            if x.tzinfo is None:
                try:
                    return x.tz_localize('Europe/Berlin', ambiguous='NaT', nonexistent='shift_forward')
                except Exception:
                    return pd.NaT
            else:
                return x
        df_noise['timestamp'] = df_noise['timestamp'].apply(localize_or_pass)
        df_noise.dropna(subset=['timestamp'], inplace=True)
        df_noise['timestamp'] = df_noise['timestamp'].dt.tz_convert('UTC')
        st.subheader("🔊 Noise Data Preview")
        st.dataframe(df_noise.head())
    except Exception as e:
        st.error(f"Error loading noise data: {e}")
        st.stop()
else:
    st.warning("Please upload a noise CSV to proceed.")
    st.stop()

# === Fetch arrivals for a given ICAO ===
def get_arrivals(icao, api_key):
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "aerodatabox.p.rapidapi.com"
    }
    base_url = "https://aerodatabox.p.rapidapi.com/flights/airports/icao"
    target_day = datetime.utcnow().date()
    ranges = [(f"{target_day}T00:00", f"{target_day}T12:00"), (f"{target_day}T12:00", f"{target_day}T23:59")]
    flights = []

    for start, end in ranges:
        url = f"{base_url}/{icao}/{start}/{end}"
        params = {
            "withLeg": "true", "direction": "Arrival",
            "withCancelled": "false", "withCodeshared": "false",
            "withCargo": "false", "withPrivate": "false",
            "withLocation": "true"
        }
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json().get("arrivals", [])
            for flight in data:
                flights.append({
                    "flight_number": flight.get("number"),
                    "arrival_scheduled_utc": flight.get("arrival", {}).get("scheduledTime", {}).get("utc"),
                    "arrival_latitude": flight.get("arrival", {}).get("airport", {}).get("location", {}).get("latitude"),
                    "arrival_longitude": flight.get("arrival", {}).get("airport", {}).get("location", {}).get("longitude"),
                    "model": flight.get("aircraft", {}).get("model"),
                    "icao": icao
                })
        except Exception as e:
            st.warning(f"Error fetching arrivals for {icao}: {e}")
    return pd.DataFrame(flights)

# === Merge noise and flight data by nearest time (15 min tolerance) ===
def merge_by_time(df_noise, df_flights):
    df_flights['arrival_scheduled_utc'] = pd.to_datetime(df_flights['arrival_scheduled_utc'], errors='coerce', utc=True)
    df_flights.dropna(subset=['arrival_scheduled_utc'], inplace=True)
    df_noise_sorted = df_noise.sort_values('timestamp')
    df_flights_sorted = df_flights.sort_values('arrival_scheduled_utc')
    return pd.merge_asof(df_noise_sorted, df_flights_sorted, left_on='timestamp', right_on='arrival_scheduled_utc', direction='nearest', tolerance=pd.Timedelta('15m'))

# === Map visualization with pydeck ===
def plot_map(df):
    if df[['arrival_latitude', 'arrival_longitude']].notnull().all(axis=1).any():
        df_map = df.dropna(subset=['arrival_latitude', 'arrival_longitude']).copy()
        df_map['color'] = df_map['icao'].map({"EDDB": [255, 0, 0, 160], "LFPG": [0, 255, 0, 160], "EGLL": [0, 0, 255, 160]}).fillna([0, 100, 255, 160])
        heat_layer = pdk.Layer("HeatmapLayer", data=df_map, get_position='[arrival_longitude, arrival_latitude]', get_weight=1, radiusPixels=60)
        view_state = pdk.ViewState(latitude=df_map['arrival_latitude'].mean(), longitude=df_map['arrival_longitude'].mean(), zoom=6)
        st.pydeck_chart(pdk.Deck(layers=[heat_layer], initial_view_state=view_state))
    else:
        fallback_df = pd.DataFrame([{ "icao": code, "arrival_latitude": AIRPORT_COORDS[code]['lat'], "arrival_longitude": AIRPORT_COORDS[code]['lon']} for code in icao_list if code in AIRPORT_COORDS])
        st.warning("No coordinates found in flight data. Showing airport fallback locations.")
        r = pdk.Deck(layers=[pdk.Layer("ScatterplotLayer", data=fallback_df, get_position='[arrival_longitude, arrival_latitude]', get_color='[255, 165, 0]', get_radius=1000)], initial_view_state=pdk.ViewState(latitude=fallback_df['arrival_latitude'].mean(), longitude=fallback_df['arrival_longitude'].mean(), zoom=6))
        st.pydeck_chart(r)

# === Noise level over time plot ===
def plot_noise_vs_time(df):
    st.write("### 📈 Noise Levels Over Time")
    if 'timestamp' in df.columns and 'noise_db' in df.columns:
        df_sorted = df.sort_values('timestamp')
        plt.figure(figsize=(12, 4))
        sns.lineplot(data=df_sorted, x='timestamp', y='noise_db', linewidth=1.5)
        plt.xticks(rotation=30, ha='right')
        plt.tight_layout()
        st.pyplot(plt.gcf())
        plt.clf()

# === Noise by aircraft model boxplot ===
def plot_noise_by_model(df):
    if 'model' in df.columns and 'max_slow' in df.columns:
        st.write("### ✈️ Noise by Aircraft Model")
        plt.figure(figsize=(12, 5))
        sns.boxplot(data=df.dropna(subset=['model', 'max_slow']), x='model', y='max_slow')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        st.pyplot(plt.gcf())
        plt.clf()

# === Dual plot: noise vs arrivals per hour ===
def plot_dual_noise_vs_arrivals(df_noise, df_arrivals):
    st.write("### 🔁 Noise Levels vs. Flight Arrivals per Hour")
    noise_hourly = df_noise.copy()
    noise_hourly['hour'] = noise_hourly['timestamp'].dt.floor('H')
    noise_hourly = noise_hourly.groupby('hour')['noise_db'].mean().reset_index()
    arrivals_hourly = df_arrivals.copy()
    arrivals_hourly['arrival_hour'] = arrivals_hourly['arrival_scheduled_utc'].dt.floor('H')
    arrivals_count = arrivals_hourly.groupby('arrival_hour').size().reset_index(name='arrivals')
    merged = pd.merge(noise_hourly, arrivals_count, left_on='hour', right_on='arrival_hour', how='outer').fillna(0)
    merged['hour'] = merged['hour'].fillna(merged['arrival_hour'])
    merged['hour_str'] = merged['hour'].dt.strftime('%H:%M')
    merged = merged.sort_values('hour')
    fig, ax1 = plt.subplots(figsize=(14, 5))
    sns.lineplot(data=merged, x='hour_str', y='noise_db', marker='o', ax=ax1, color='tab:blue', label='Avg Noise (dB)')
    ax1.set_ylabel('Noise (dB)', color='tab:blue')
    ax1.tick_params(axis='y', labelcolor='tab:blue')
    ax2 = ax1.twinx()
    sns.barplot(data=merged, x='hour_str', y='arrivals', alpha=0.4, ax=ax2, color='tab:orange')
    ax2.set_ylabel('Flight Arrivals', color='tab:orange')
    ax2.tick_params(axis='y', labelcolor='tab:orange')
    ax1.set_xlabel('Hour')
    plt.title('Hourly Noise Levels vs Flight Arrivals')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    st.pyplot(fig)
    plt.clf()

# === Main workflow ===
st.header("🚀 Data Fetch & Visualization")
if api_key:
    all_arrivals = pd.DataFrame()
    for airport_icao in icao_list:
        st.write(f"Fetching arrivals for airport: {airport_icao} ...")
        df_arrivals = get_arrivals(airport_icao, api_key)
        if not df_arrivals.empty:
            all_arrivals = pd.concat([all_arrivals, df_arrivals], ignore_index=True)
    if not all_arrivals.empty:
        st.subheader("✈️ Flight Arrivals Preview")
        st.dataframe(all_arrivals.head())
        merged_df = merge_by_time(df_noise, all_arrivals)
        st.subheader("🔗 Merged Noise & Flight Data")
        st.dataframe(merged_df.head())
        plot_map(merged_df)
        plot_noise_vs_time(df_noise)
        plot_noise_by_model(merged_df)
        plot_dual_noise_vs_arrivals(df_noise, all_arrivals)
    else:
        st.warning("No flight arrivals data fetched. Please check your API key and airport selections.")
else:
    st.info("Enter your AeroDataBox API key to fetch flight arrivals data.")

st.markdown("---")
st.caption("Developed by Kholeka Westerkamp | Data Analytics Portfolio Project")




































