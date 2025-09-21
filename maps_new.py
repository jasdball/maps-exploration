import streamlit as st
from googlemaps import Client
from googlemaps.directions import directions
import pandas as pd
from datetime import datetime
import uuid
from bs4 import BeautifulSoup
import hashlib

API_KEY = st.secrets.google.maps.api_key
ADDRESSES = st.secrets.google.maps.addresses
COMMUTES = {
    "Home to Work": {
        "origin": ADDRESSES["home"],
        "destination": ADDRESSES["work"],
    },
    "Work to Home": {
        "origin": ADDRESSES["work"],
        "destination": ADDRESSES["home"],
    },
}
TRAFFIC_MODELS = ["best_guess", "pessimistic", "optimistic"]

def strip_html(html):
    return BeautifulSoup(html, "html.parser").get_text()

def hash_route_steps(steps):
    instructions = [strip_html(step["html_instructions"]) for step in steps]
    route_fingerprint = hashlib.md5(" > ".join(instructions).encode()).hexdigest()
    return route_fingerprint

def create_gmaps_client(api_key):
    """
    Create a Google Maps client using the provided API key.
    """
    return Client(api_key)

def generate_departure_times():
    """
    Generate datetime values for Monday through Friday, 2 PM to 7 PM, with a 15-minute step
    """
    start_hour = 14  # 2 PM
    end_hour = 15    # 7 PM
    interval_minutes = 30

    start_time = datetime.now().replace(hour=start_hour, minute=0, second=0, microsecond=0) + pd.Timedelta(days=1)  # Start from tomorrow
    if start_time.weekday() >= 5:  # If today is Saturday or Sunday, move to next Monday
        start_time += pd.Timedelta(days=(7 - start_time.weekday()))
    end_time = datetime.now().replace(hour=end_hour, minute=0, second=0, microsecond=0)
    departure_times = {}

    for day_offset in range(7):
        current_day = start_time + pd.Timedelta(days=day_offset)
        current_time = current_day
        while current_time <= current_day.replace(hour=end_hour, minute=0):
            key = f"{current_time.strftime('%A')}_{current_time.strftime('%H:%M')}"
            departure_times[key] = current_time
            current_time += pd.Timedelta(minutes=interval_minutes)

    return departure_times

def generate_departure_times_list():
    """
    Generate datetime values for Monday through Friday, 2 PM to 7 PM, with a 15-minute step
    """
    start_hour = 14  # 2 PM
    end_hour = 15    # 7 PM
    interval_minutes = 30

    start_time = datetime.now().replace(hour=start_hour, minute=0, second=0, microsecond=0) + pd.Timedelta(days=1)  # Start from tomorrow
    if start_time.weekday() >= 5:  # If today is Saturday or Sunday, move to next Monday
        start_time += pd.Timedelta(days=(7 - start_time.weekday()))
    
    
    end_time = datetime.now().replace(hour=end_hour, minute=0, second=0, microsecond=0)
    departure_times = {}

    for day_offset in range(7):
        current_day = start_time + pd.Timedelta(days=day_offset)
        current_time = current_day
        while current_time <= current_day.replace(hour=end_hour, minute=0):
            key = f"{current_time.strftime('%A')}_{current_time.strftime('%H:%M')}"
            departure_times[key] = current_time
            current_time += pd.Timedelta(minutes=interval_minutes)

    return departure_times

def get_route_data(departure_times, traffic_models, client):
    """
    Fetch route data for each departure time and traffic model.
    """
    route_directions_list = []
    for departure_time in departure_times.values():
        for traffic_model in traffic_models:
            route_directions = directions(
                client=client,
                origin=ADDRESSES["work"],
                destination=ADDRESSES["home"],
                mode="driving",
                departure_time=departure_time,
                alternatives=True,
                traffic_model=traffic_model,
                units="imperial",
            )
            route_directions_list.append(route_directions)
    return route_directions_list

def main():
    """
    Main function to execute the route fetching and processing.
    """
    gmaps = create_gmaps_client(API_KEY)
    departure_times = generate_departure_times()
    route_directions_list = get_route_data(departure_times, TRAFFIC_MODELS, gmaps)

    st.write(route_directions_list)

if __name__ == "__main__":
    main()