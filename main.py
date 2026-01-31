from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import requests
from geopy.distance import geodesic
import math

app = FastAPI(
    title="Earthquake Impact Checker",
    description="Realistic earthquake impact using real USGS data only",
    version="4.0"
)

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Use 24-hour feed for stronger events
# -----------------------------
USGS_FEED = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"

# -----------------------------
# Impact scoring
# -----------------------------
def impact_score(magnitude, distance_km, building_type):
    building_factor = {
        "house": 0,
        "apartment": 1,
        "old_building": 2
    }.get(building_type, 0)

    # Realistic distance decay
    distance_factor = max(0, 10 - math.log10(distance_km + 1) * 3)

    # Magnitude weight
    score = magnitude * 10 + distance_factor + building_factor
    return round(score, 1)


def impact_level(score):
    if score < 30:
        return "Low"
    elif score < 60:
        return "Medium"
    else:
        return "High"


def felt_intensity(score):
    if score < 30:
        return "Barely felt"
    elif score < 60:
        return "Noticeable shaking"
    else:
        return "Potential damage"


def confidence_statement(score):
    if score < 10:
        return "You are very unlikely to notice any earthquake activity."
    elif score < 50:
        return "Some people may feel shaking."
    else:
        return "There is a realistic chance of noticeable shaking."


# -----------------------------
# API endpoint
# -----------------------------
@app.get("/impact")
def check_impact(
    lat: float = Query(..., description="Your latitude"),
    lon: float = Query(..., description="Your longitude"),
    building: str = Query("house", description="house | apartment | old_building")
):
    try:
        response = requests.get(USGS_FEED, timeout=10)
        data = response.json()
    except:
        return {"error": "Cannot fetch earthquake data."}

    nearby_quakes = []

    for q in data.get("features", []):
        mag = q["properties"].get("mag")
        if mag is None or mag < 3:
            continue

        q_lon, q_lat, depth = q["geometry"]["coordinates"]
        dist = geodesic((lat, lon), (q_lat, q_lon)).km

        if dist < 1000:  # consider earthquakes within 1000 km
            nearby_quakes.append((q, dist))

    # -----------------------------
    # CASE 1: No nearby quakes
    # -----------------------------
    if not nearby_quakes:
        return {
            "status": "No relevant earthquakes near your location",
            "impact_level": "Low",
            "impact_score": 0,
            "felt_intensity": "None",
            "confidence": "No earthquake activity near you is expected to be felt.",
            "why": "No earthquakes of magnitude 3.0+ occurred within 1000 km in the last 24 hours.",
            "what_to_do": [
                "No action needed",
                "Stay informed for future alerts",
                "Ensure general emergency preparedness"
            ]
        }

    # -----------------------------
    # CASE 2: Closest real quake
    # -----------------------------
    quake, distance_km = min(nearby_quakes, key=lambda x: x[1])

    q_lon, q_lat, depth = quake["geometry"]["coordinates"]
    magnitude = quake["properties"]["mag"]
    place = quake["properties"]["place"]

    score = impact_score(magnitude, distance_km, building)

    return {
        "earthquake": {
            "magnitude": magnitude,
            "place": place,
            "depth_km": abs(round(depth, 1))
        },
        "your_location": {
            "latitude": lat,
            "longitude": lon
        },
        "distance_km": round(distance_km, 1),
        "impact_score": score,
        "impact_level": impact_level(score),
        "felt_intensity": felt_intensity(score),
        "confidence": confidence_statement(score),
        "why": "This is the closest significant earthquake to your location.",
        "what_to_do": [
            "Stay calm and informed",
            "Secure loose objects nearby",
            "Check emergency supplies"
        ]
    }
