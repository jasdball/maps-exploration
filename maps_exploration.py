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

def generate_departure_times():
    start_time = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0) + pd.Timedelta(days=1)
    if start_time.weekday() >= 5:
        start_time += pd.Timedelta(days=(7 - start_time.weekday()))
    departure_times = {}
    for day_offset in range(7):
        current_day = start_time + pd.Timedelta(days=day_offset)
        current_time = current_day
        while current_time <= current_day.replace(hour=19, minute=0):
            key = f"{current_time.strftime('%A')}_{current_time.strftime('%H:%M')}"
            departure_times[key] = current_time
            current_time += pd.Timedelta(minutes=15)
    return departure_times

def generate_departure_times_new():
    """
    Generate datetime values for Monday through Friday, 2 PM to 7 PM, with a 15-minute step
    """
    start_hour = 14  # 2 PM
    end_hour = 19    # 7 PM
    interval_minutes = 15

    start_time = datetime.now().replace(hour=start_hour, minute=0, second=0, microsecond=0) + pd.Timedelta(days=1)
    if start_time.weekday() >= 5:  # If today is Saturday or Sunday, move to next Monday
        start_time += pd.Timedelta(days=(7 - start_time.weekday()))
    departure_times = []

    for day_offset in range(30):  # Generate for 30 days
        if start_time.weekday() >= 5:  # Skip weekends
            continue
        current_day = start_time + pd.Timedelta(days=day_offset)
        current_time = current_day
        while current_time <= current_day.replace(hour=end_hour, minute=0):
            departure_times.append(current_time)
            current_time += pd.Timedelta(minutes=interval_minutes)

    return departure_times

@st.cache_resource
def create_gmaps_client(api_key):
    """
    Create a Google Maps client using the provided API key.
    """
    st.session_state.gmaps_client = Client(api_key)

@st.cache_data
def fetch_all_directions(origin, destination, departure_times, traffic_models):
    """
    Fetch directions for all combinations of departure times and traffic models.
    """
    all_results = []
    for departure_time in departure_times:
        for traffic_model in traffic_models:
            result = fetch_directions(origin, destination, departure_time, traffic_model)
            all_results.append((result, departure_time, traffic_model))
    return all_results

@st.cache_data
def fetch_directions(origin, destination, departure_time, traffic_model):
    """
    Fetch directions from Google Maps API for a given origin, destination, departure time, and traffic model.
    """
    gmaps = st.session_state.gmaps_client
    return directions(
        client=gmaps,
        origin=origin,
        destination=destination,
        mode="driving",
        departure_time=departure_time,
        alternatives=True,
        traffic_model=traffic_model,
        units="imperial",
    )

def extract_route_attributes(route, departure_time, traffic_model, api_call_timestamp, route_id, route_fingerprint):
    arrival_timestamp = departure_time + pd.Timedelta(seconds=route["legs"][0]["duration"]["value"])
    arrival_timestamp_traffic = departure_time + pd.Timedelta(seconds=route["legs"][0]["duration_in_traffic"]["value"])
    return {
        "route_id": route_id,
        "route_hash": route_fingerprint,
        "summary": route["summary"],
        "legs_count": len(route["legs"]),
        "departure_timestamp": departure_time.isoformat(),
        "departure_date": departure_time.date().isoformat(),
        "departure_time": departure_time.time().isoformat(timespec="seconds"),
        "departure_weekday": departure_time.strftime("%A"),
        "arrival_timestamp": arrival_timestamp.isoformat(),
        "arrival_date": arrival_timestamp.date().isoformat(),
        "arrival_time": arrival_timestamp.time().isoformat(timespec="seconds"),
        "arrival_timestamp_traffic": arrival_timestamp_traffic.isoformat(),
        "arrival_date_traffic": arrival_timestamp_traffic.date().isoformat(),
        "arrival_time_traffic": arrival_timestamp_traffic.time().isoformat(timespec="seconds"),
        "timestamp": api_call_timestamp,
        "traffic_model": traffic_model
    }

def extract_leg_attributes(leg, route_id):
    leg_id = str(uuid.uuid4())
    return leg_id, {
        "leg_id": leg_id,
        "route_id": route_id,
        "start_location_latitude": leg["start_location"]["lat"],
        "start_location_longitude": leg["start_location"]["lng"],
        "end_location_latitude": leg["end_location"]["lat"],
        "end_location_longitude": leg["end_location"]["lng"],
        "distance_text": leg["distance"]["text"],
        "distance_meters": leg["distance"]["value"],
        "duration_text": leg["duration"]["text"],
        "duration_seconds": leg["duration"]["value"],
        "duration_in_traffic_text": leg["duration_in_traffic"]["text"],
        "duration_in_traffic_seconds": leg["duration_in_traffic"]["value"],
        "start_address": leg["start_address"],
        "end_address": leg["end_address"],
        "steps_count": len(leg["steps"]),
    }

def extract_step_attributes(step, leg_id, step_number):
    step_id = str(uuid.uuid4())
    return {
        "step_id": step_id,
        "leg_id": leg_id,
        "step_number": step_number,
        "html_instruction": step["html_instructions"],
        "plaintext_instruction": strip_html(step["html_instructions"]),
        "maneuver": step.get("maneuver", None),
        "distance_text": step["distance"]["text"],
        "distance_meters": step["distance"]["value"],
        "duration_text": step["duration"]["text"],
        "duration_seconds": step["duration"]["value"],
        "start_location_latitude": step["start_location"]["lat"],
        "start_location_longitude": step["start_location"]["lng"],
        "end_location_latitude": step["end_location"]["lat"],
        "end_location_longitude": step["end_location"]["lng"],
        "travel_mode": step["travel_mode"],
    }

def process_single_route(route, departure_time, traffic_model, api_call_timestamp):
    routes, legs, steps = [], [], []
    route_id = str(uuid.uuid4())
    all_steps = [step for leg in route["legs"] for step in leg["steps"]]
    route_fingerprint = hash_route_steps(all_steps)
    # Route attributes
    routes.append(extract_route_attributes(route, departure_time, traffic_model, api_call_timestamp, route_id, route_fingerprint))
    # Leg and step attributes
    for leg in route["legs"]:
        leg_id, leg_attrs = extract_leg_attributes(leg, route_id)
        legs.append(leg_attrs)
        for step_number, step in enumerate(leg["steps"], start=1):
            steps.append(extract_step_attributes(step, leg_id, step_number))
    return routes, legs, steps

def aggregate_all_routes_legs_steps(all_directions_results):
    all_routes, all_legs, all_steps = [], [], []
    for directions_result, departure_time, traffic_model in all_directions_results:
        api_call_timestamp = datetime.now().isoformat()
        for route in directions_result:
            routes, legs, steps = process_single_route(route, departure_time, traffic_model, api_call_timestamp)
            all_routes.extend(routes)
            all_legs.extend(legs)
            all_steps.extend(steps)
    return pd.DataFrame(all_routes), pd.DataFrame(all_legs), pd.DataFrame(all_steps)

def save_dataframes(df_routes, df_legs, df_steps):
    try:
        df_routes.to_csv("routes.csv", index=False)
        df_legs.to_csv("legs.csv", index=False)
        df_steps.to_csv("steps.csv", index=False)
        st.write("Routes, legs, and steps data have been saved to CSV files.")
    except Exception as e:
        st.error(f"Error saving CSV files: {e}")

def main():
    gmaps = create_gmaps_client(API_KEY)
    departure_times = generate_departure_times_new()
    all_directions_results = fetch_all_directions(
        ADDRESSES["work"],
        ADDRESSES["home"],
        departure_times,
        TRAFFIC_MODELS
    )
    df_routes, df_legs, df_steps = aggregate_all_routes_legs_steps(all_directions_results)
    st.title("Google Maps Directions API Exploration")
    st.write("This app explores the Google Maps Directions API and displays the routes, legs, and steps data.")
    with st.expander("Routes DataFrame", expanded=False):
        st.dataframe(df_routes)
    with st.expander("Legs DataFrame", expanded=False):
        st.dataframe(df_legs)
    with st.expander("Steps DataFrame", expanded=False):
        st.dataframe(df_steps)
    save_dataframes(df_routes, df_legs, df_steps)

if __name__ == "__main__":
    print("Running main...")
    main()
    print("...main finished.")