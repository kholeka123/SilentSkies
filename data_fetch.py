# data_fetch.py

import pandas as pd
import requests
from datetime import datetime, timedelta


def load_noise_data(uploaded_file):
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(".xlsx"):
            df = pd.read_excel(uploaded_file)
        else:
            raise ValueError("Unsupported file type")

        # Clean timestamp
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    except Exception as e:
        raise RuntimeError(f"Failed to load file: {e}")


def fetch_flight_data(icao, api_key):
    try:
        url = f"https://aerodatabox.p.rapidapi.com/flights/airports/icao/{icao}/{datetime.utcnow().isoformat()}Z/{(datetime.utcnow() + timedelta(hours=3)).isoformat()}Z"

        headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "aerodatabox.p.rapidapi.com"
        }

        params = {"withLeg": "true"}

        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        arrivals = response.json().get("arrivals", [])
        df = pd.json_normalize(arrivals)

        if not df.empty and "arrival.scheduledTimeUtc" in df.columns:
            df["arrival_time"] = pd.to_datetime(df["arrival.scheduledTimeUtc"])
        return df
    except Exception as e:
        raise RuntimeError(f"Failed to fetch flight arrivals: {e}")


def enrich_with_weather(df, lat, lon, api_key):
    try:
        weather = get_weather(lat, lon, api_key)
        for key, value in weather.items():
            df[key] = value
        return df
    except Exception as e:
        raise RuntimeError(f"Failed to enrich with weather: {e}")


def get_weather(lat, lon, api_key):
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric"
        response = requests.get(url)
        response.raise_for_status()

        data = response.json()
        weather = {
            "Temperature (°C)": data["main"]["temp"],
            "Wind Speed (m/s)": data["wind"]["speed"],
            "Conditions": data["weather"][0]["description"].capitalize()
        }
        return weather
    except Exception as e:
        raise RuntimeError(f"Failed to fetch weather: {e}")


def merge_by_time(df_noise, df_flights, time_col_noise="timestamp", time_col_flight="arrival_time", tolerance="5min"):
    try:
        df_noise_sorted = df_noise.sort_values(by=time_col_noise).copy()
        df_flights_sorted = df_flights.sort_values(by=time_col_flight).copy()

        df_merged = pd.merge_asof(
            df_noise_sorted,
            df_flights_sorted,
            left_on=time_col_noise,
            right_on=time_col_flight,
            direction="nearest",
            tolerance=pd.Timedelta(tolerance)
        )
        return df_merged
    except Exception as e:
        raise RuntimeError(f"Failed to merge data: {e}")

