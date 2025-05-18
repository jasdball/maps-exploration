import streamlit as st
from googlemaps import Client
from googlemaps.directions import directions
import pandas as pd
from datetime import datetime
import uuid
from bs4 import BeautifulSoup
import hashlib

API_KEY = st.secrets.google.maps.api_key
ADDRESSES = st.secrets.addresses
COMMUTES = {
    "Home to Work": {
        "origin": ADDRESSES["Home"],
        "destination": ADDRESSES["Work"],
    },
    "Work to Home": {
        "origin": ADDRESSES["Work"],
        "destination": ADDRESSES["Home"],
    },
}
TRAFFIC_MODELS = ["best_guess", "pessimistic", "optimistic"]

def strip_html(html):
    return BeautifulSoup(html, "html.parser").get_text()

def hash_route_steps(steps):
    instructions = [strip_html(step["html_instructions"]) for step in steps]
    route_fingerprint = hashlib.md5(" > ".join(instructions).encode()).hexdigest()
    return route_fingerprint

gmaps = Client(API_KEY)

# Generate datetime values for Monday through Friday, 2 PM to 7 PM, with a 30-minute step
start_time = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0) + pd.Timedelta(days=1)  # Start from tomorrow
if start_time.weekday() >= 5:  # If today is Saturday or Sunday, move to next Monday
    start_time += pd.Timedelta(days=(7 - start_time.weekday()))
end_time = datetime.now().replace(hour=19, minute=0, second=0, microsecond=0)
departure_times = {}

for day_offset in range(7):
    current_day = start_time + pd.Timedelta(days=day_offset)
    current_time = current_day
    while current_time <= current_day.replace(hour=19, minute=0):
        key = f"{current_time.strftime('%A')}_{current_time.strftime('%H:%M')}"
        departure_times[key] = current_time
        current_time += pd.Timedelta(minutes=15)

routes, legs, steps = [], [], []
for departure_time in departure_times.values():
    for traffic_model in TRAFFIC_MODELS:
        work_to_home_directions = directions(
            client = gmaps,
            origin = ADDRESSES["Work"],
            destination = ADDRESSES["Home"],
            mode = "driving",
            departure_time = departure_time,
            alternatives=True,
            traffic_model=traffic_model,
            units="imperial",
        )
        for route in work_to_home_directions:
            route_id = str(uuid.uuid4())
            api_call_timestamp = datetime.now().isoformat()
            all_steps = [step for leg in route["legs"] for step in leg["steps"]]
            route_fingerprint = hash_route_steps(all_steps)
            arrival_timestamp = departure_time + pd.Timedelta(seconds=route["legs"][0]["duration"]["value"])
            arrival_timestamp_traffic = departure_time + pd.Timedelta(seconds=route["legs"][0]["duration_in_traffic"]["value"])
            routes.append({
                "route_id": route_id,
                "route_hash": route_fingerprint,
                "summary": route["summary"],
                "legs_count": len(route["legs"]),
                "departure_timestamp": departure_time.isoformat(),
                "departure_date": departure_time.date().isoformat(),
                "departure_time": departure_time.time().isoformat(timespec="seconds"),
                "arrival_timestamp": arrival_timestamp.isoformat(),
                "arrival_date": arrival_timestamp.date().isoformat(),
                "arrival_time": arrival_timestamp.time().isoformat(timespec="seconds"),
                "arrival_timestamp_traffic": arrival_timestamp_traffic.isoformat(),
                "arrival_date_traffic": arrival_timestamp_traffic.date().isoformat(),
                "arrival_time_traffic": arrival_timestamp_traffic.time().isoformat(timespec="seconds"),
                "timestamp": api_call_timestamp,
                "traffic_model": traffic_model
            })

            for leg in route["legs"]:
                leg_id = str(uuid.uuid4())
                legs.append({
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
                })
                for step_number,step in enumerate(leg["steps"],start=1):
                    step_id = str(uuid.uuid4())
                    steps.append({
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
                    })
df_routes = pd.DataFrame(routes)
df_legs = pd.DataFrame(legs)
df_steps = pd.DataFrame(steps)

st.title("Google Maps Directions API Exploration")
st.write("This app explores the Google Maps Directions API and displays the routes, legs, and steps data.")
with st.expander("Routes DataFrame",expanded=False):
    st.dataframe(df_routes)
with st.expander("Legs DataFrame",expanded=False):
    st.dataframe(df_legs)
with st.expander("Steps DataFrame",expanded=False):
    st.dataframe(df_steps)

try:
    df_routes.to_csv("routes.csv", index=False)
    df_legs.to_csv("legs.csv", index=False)
    df_steps.to_csv("steps.csv", index=False)
    st.write("Routes, legs, and steps data have been saved to CSV files.")
except Exception as e:
    st.error(f"Error saving CSV files: {e}")