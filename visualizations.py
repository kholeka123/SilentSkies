import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns
import pydeck as pdk
import pandas as pd

AIRPORTS = {
    "EDDB": {"lat": 52.3667, "lon": 13.5033, "city": "Berlin", "pop_m": 3.7},
    "LFPG": {"lat": 49.0097, "lon": 2.5479, "city": "Paris", "pop_m": 11.0},
    "EGLL": {"lat": 51.4700, "lon": -0.4543, "city": "London", "pop_m": 9.0},
}

def plot_noise_vs_time(df):
    """Plot noise level over time as a line with shaded fill."""
    st.write("### 📈 Noise Levels Over Time")
    if 'timestamp' in df.columns and 'noise_db' in df.columns:
        df_sorted = df.sort_values('timestamp')
        plt.figure(figsize=(14, 5))
        sns.lineplot(data=df_sorted, x='timestamp', y='noise_db', linewidth=2, color='royalblue')
        plt.fill_between(df_sorted['timestamp'], df_sorted['noise_db'], color='lightblue', alpha=0.3)
        plt.xlabel("Timestamp")
        plt.ylabel("Noise Level (dB)")
        plt.xticks(rotation=45, ha='right')
        plt.title("Noise Level Over Time")
        plt.tight_layout()
        st.pyplot(plt.gcf())
        plt.clf()
        plt.close()

def plot_noise_by_model(df):
    """Boxplot of noise (max_slow) distribution grouped by aircraft model."""
    if 'model' in df.columns and 'max_slow' in df.columns:
        st.write("### ✈️ Noise Level Distribution by Aircraft Model")
        plt.figure(figsize=(12, 5))
        sns.boxplot(data=df.dropna(subset=['model', 'max_slow']), x='model', y='max_slow', palette="Set3")
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        st.pyplot(plt.gcf())
        plt.clf()
        plt.close()

def plot_dual_noise_vs_arrivals(df_noise, df_arrivals):
    """Dual axis plot of hourly average noise levels and number of flight arrivals."""
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
    sns.lineplot(data=merged, x='hour_str', y='noise_db', marker="o", color='royalblue', ax=ax1)
    ax1.set_ylabel('Avg Noise dB', color='royalblue')
    ax1.tick_params(axis='y', labelcolor='royalblue')
    ax1.set_xlabel('Hour')
    plt.xticks(rotation=45, ha='right')

    ax2 = ax1.twinx()
    sns.barplot(data=merged, x='hour_str', y='arrivals', alpha=0.4, color='orange', ax=ax2)
    ax2.set_ylabel('Number of Arrivals', color='orange')
    ax2.tick_params(axis='y', labelcolor='orange')

    plt.title("Noise Levels & Flight Arrivals Over the Day")
    plt.tight_layout()
    st.pyplot(fig)
    plt.clf()
    plt.close()

def plot_map(df_arrivals, icao_list):
    """
    Plot a heatmap of flight arrival locations if lat/lon available,
    else fallback to airport scatter plot from AIRPORTS metadata.
    """
    if df_arrivals[['arrival_latitude', 'arrival_longitude']].notnull().all(axis=1).any():
        df_map = df_arrivals.dropna(subset=['arrival_latitude', 'arrival_longitude']).copy()

        def map_color(icao):
            colors = {"EDDB": [255, 0, 0, 160], "LFPG": [0, 255, 0, 160], "EGLL": [0, 0, 255, 160]}
            return colors.get(icao, [0, 100, 255, 160])

        df_map['color'] = df_map['icao'].apply(map_color)

        heat_layer = pdk.Layer(
            "HeatmapLayer",
            data=df_map,
            get_position='[arrival_longitude, arrival_latitude]',
            get_weight=1,
            radiusPixels=60,
        )
        view_state = pdk.ViewState(
            latitude=df_map['arrival_latitude'].mean(),
            longitude=df_map['arrival_longitude'].mean(),
            zoom=6
        )
        st.pydeck_chart(pdk.Deck(layers=[heat_layer], initial_view_state=view_state))

    else:
        fallback_df = pd.DataFrame([
            {
                "icao": code,
                "arrival_latitude": AIRPORTS[code]['lat'],
                "arrival_longitude": AIRPORTS[code]['lon']
            } for code in icao_list if code in AIRPORTS
        ])
        st.warning("No coordinates found in flight data. Showing airport fallback locations.")
        scatter_layer = pdk.Layer(
            "ScatterplotLayer",
            data=fallback_df,
            get_position='[arrival_longitude, arrival_latitude]',
            get_color='[255, 165, 0]',
            get_radius=1000,
        )
        view_state = pdk.ViewState(
            latitude=fallback_df['arrival_latitude'].mean(),
            longitude=fallback_df['arrival_longitude'].mean(),
            zoom=6
        )
        st.pydeck_chart(pdk.Deck(layers=[scatter_layer], initial_view_state=view_state))

