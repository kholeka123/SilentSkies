# app.py

import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv

# External visual and logic modules
from data_fetch import load_noise_data, get_arrivals, get_weather, merge_by_time
from visualizations import (
    plot_noise_vs_time,
    plot_noise_by_model,
    plot_dual_noise_vs_arrivals,
    plot_map
)

# === Static airport metadata ===
AIRPORTS = {
    "EDDB": {"lat": 52.3667, "lon": 13.5033, "city": "Berlin", "pop_m": 3.7},
    "LFPG": {"lat": 49.0097, "lon": 2.5479, "city": "Paris", "pop_m": 11.0},
    "EGLL": {"lat": 51.4700, "lon": -0.4543, "city": "London", "pop_m": 9.0},
}

# === Streamlit setup ===
load_dotenv()
st.set_page_config(page_title="Silent Skies", layout="wide")
st.title("🌃 Silent Skies: Noise, Flight Arrivals & Weather Dashboard")
st.sidebar.header("🔧 Settings")

# === Sidebar Inputs ===
api_key = st.sidebar.text_input("🔑 AeroDataBox API Key", type="password")
weather_key = st.sidebar.text_input("🔑 OpenWeatherMap API Key", type="password")
icao_list = st.sidebar.multiselect("🛬 Select Airports", options=list(AIRPORTS.keys()), default=["EDDB"])
noise_file = st.sidebar.file_uploader("📄 Upload Noise Data CSV", type="csv")

st.sidebar.download_button(
    label="Download Sample Noise CSV",
    data="timestamp,noise_db,max_slow\n2025-07-01T12:00:00+02:00,65,72\n2025-07-01T12:15:00+02:00,68,74\n",
    file_name="sample_noise.csv",
    mime="text/csv"
)

# === Load Noise Data ===
if noise_file:
    df_noise = load_noise_data(noise_file)
    if df_noise is None or df_noise.empty:
        st.error("Failed to load or parse noise data.")
        st.stop()
    st.subheader("🔊 Noise Data Preview")
    st.dataframe(df_noise.head())
else:
    st.warning("Please upload a noise CSV to proceed.")
    st.stop()

# === Load Flight Arrivals ===
df_arrivals_all = pd.DataFrame()
if api_key and icao_list:
    st.subheader("🛬 Flight Arrivals")
    for icao in icao_list:
        try:
            df = get_arrivals(icao, api_key)
            df["icao"] = icao
            df_arrivals_all = pd.concat([df_arrivals_all, df], ignore_index=True)
            st.write(f"✅ {icao} Arrivals Preview", df.head())
        except Exception as e:
            st.error(f"❌ {icao} failed: {e}")
else:
    st.info("Enter AeroDataBox API key and select airports to fetch arrivals.")

# === Load Weather Data ===
weather_info = []
if weather_key and icao_list:
    st.subheader("🌤 Current Weather")
    for icao in icao_list:
        meta = AIRPORTS.get(icao, {})
        try:
            weather = get_weather(meta["lat"], meta["lon"], weather_key)
            row = {"Airport": icao, **weather}
            weather_info.append(row)
        except Exception as e:
            st.warning(f"Could not get weather for {icao}: {e}")
    if weather_info:
        st.table(pd.DataFrame(weather_info))
    else:
        st.info("No weather data available.")

# === Merge Noise with Arrivals ===
if not df_arrivals_all.empty:
    merged_df = merge_by_time(df_noise, df_arrivals_all, time_col_flight="arrival_time")
else:
    merged_df = df_noise.copy()

# === Visualizations ===
plot_noise_vs_time(df_noise)

if "model" in merged_df.columns:
    plot_noise_by_model(merged_df)

if not df_arrivals_all.empty:
    plot_dual_noise_vs_arrivals(df_noise, df_arrivals_all)

# === Map View ===
st.subheader("🗺 Flight Arrival Heatmap")
plot_map(df_arrivals_all, icao_list, AIRPORTS)





































