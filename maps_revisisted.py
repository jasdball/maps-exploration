import streamlit as st
from googlemaps import Client
from googlemaps.directions import directions
import pandas as pd
from datetime import datetime,timedelta

API_KEY = st.secrets.google.maps.api_key

TRAFFIC_MODELS = ["best_guess", "pessimistic", "optimistic"]

def generate_departure_times(start_hour: int, end_hour: int, interval_minutes: int, days_num: int):
    start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + pd.Timedelta(days=1)
    departure_times = []
    for day in range(days_num):
        for hour in range(start_hour, end_hour):
            for minute in range(0, 60, interval_minutes):
                departure_time = start_date + timedelta(days=day, hours=hour, minutes=minute)
                departure_times.append(departure_time)
    return departure_times

departure_times = generate_departure_times(14, 17, 30, 1)

client = Client(API_KEY)

all_results = []
for departure_time in departure_times:
    for traffic_model in TRAFFIC_MODELS:
        result = directions(
            client=client,
            origin="7312 Parkway Drive S, Hanover, MD 21076",
            destination="305 Miller Court, Havre de Grace, MD 21078",
            mode="driving",
            departure_time=departure_time,
            alternatives=True,
            traffic_model=traffic_model,
            units="imperial"
        )
        all_results.append(result)

st.write(all_results[0])