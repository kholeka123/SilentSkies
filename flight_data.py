import requests
import pandas as pd
from datetime import datetime, timedelta
import os

def get_arrivals_two_calls_per_airport(icao: str, api_key: str) -> list[dict]:
    """
    Fetches arrivals for a given airport (ICAO code) in two 12-hour time windows for tomorrow.
    Returns a list of dictionaries with flight details.
    """
    base_url = "https://aerodatabox.p.rapidapi.com/flights/airports/icao"
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "aerodatabox.p.rapidapi.com"
    }

    target_day = datetime.utcnow().date() + timedelta(days=1)
    # ISO 8601 format with seconds and 'Z' to indicate UTC time
    time_ranges = [
        (f"{target_day}T00:00:00Z", f"{target_day}T12:00:00Z"),
        (f"{target_day}T12:00:00Z", f"{target_day}T23:59:59Z")
    ]

    querystring = {
        "withLeg": "true",
        "direction": "Arrival",
        "withCancelled": "false",
        "withCodeshared": "false",
        "withCargo": "false",
        "withPrivate": "false",
        "withLocation": "true"
    }

    flight_list = []

    for start_time, end_time in time_ranges:
        url = f"{base_url}/{icao}/{start_time}/{end_time}"
        try:
            response = requests.get(url, headers=headers, params=querystring, timeout=10)
            response.raise_for_status()
            arrivals = response.json().get("arrivals", [])

            for flight in arrivals:
                flight_list.append({
                    "flight_number": flight.get("number"),
                    "flight_status": flight.get("status"),
                    "origin_icao": flight.get("departure", {}).get("airport", {}).get("icao"),
                    "origin_iata": flight.get("departure", {}).get("airport", {}).get("iata"),
                    "origin_airport_name": flight.get("departure", {}).get("airport", {}).get("name"),
                    "arrival_scheduled_utc": flight.get("arrival", {}).get("scheduledTime", {}).get("utc"),
                    "arrival_scheduled_local": flight.get("arrival", {}).get("scheduledTime", {}).get("local"),
                    "arrival_terminal": flight.get("arrival", {}).get("terminal"),
                    "arrival_gate": flight.get("arrival", {}).get("gate"),
                    "arrival_baggage_belt": flight.get("arrival", {}).get("baggageBelt"),
                    "aircraft_model": flight.get("aircraft", {}).get("model"),
                    "aircraft_registration": flight.get("aircraft", {}).get("reg"),
                    "aircraft_modeS": flight.get("aircraft", {}).get("modeS"),
                    "airline_name": flight.get("airline", {}).get("name"),
                    "airline_iata": flight.get("airline", {}).get("iata"),
                    "airline_icao": flight.get("airline", {}).get("icao"),
                    "call_sign": flight.get("callSign"),
                    "arrival_revised_utc": flight.get("arrival", {}).get("revisedTime", {}).get("utc"),
                    "arrival_revised_local": flight.get("arrival", {}).get("revisedTime", {}).get("local"),
                })

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed fetching {icao} arrivals from {start_time} to {end_time}:\n{e}")

    return flight_list

# === Optional: Test when running directly ===
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()  # Load from .env if available

    api_key = os.getenv("AERODATABOX_API_KEY")  # Environment variable name (fix!)
    if not api_key:
        raise ValueError("❌ Please set your API key in an environment variable: AERODATABOX_API_KEY")

    icaos = ['EDDB', 'LFPG', 'EGLL']  # Sample airports: Berlin, Paris CDG, Heathrow
    all_flights = []
    for icao in icaos:
        flights = get_arrivals_two_calls_per_airport(icao, api_key)
        all_flights.extend(flights)

    df_flights = pd.DataFrame(all_flights)
    df_flights_clean = df_flights.dropna(subset=["arrival_scheduled_utc", "arrival_scheduled_local"]).reset_index(drop=True)

    print("✅ Sample cleaned flight data:")
    print(df_flights_clean.head())

