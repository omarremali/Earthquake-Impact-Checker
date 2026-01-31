from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import requests
from geopy.distance import geodesic

app = FastAPI(
    title="Earthquake Impact Checker",
    description="Will this earthquake affect me?",
    version="1.4"
)

# -----------------------------
# Allow CORS for all origins (so browser can call from file or another host)
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # <- allow any origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

USGS_LATEST = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"

# -----------------------------
# Scoring logic (updated for realistic results)
# -----------------------------
def impact_score(magnitude, distance_km, building_type):
    building_factor = {
        "house": 0,
        "apartment": 1,
        "old_building": 2
    }.get(building_type, 0)

    # distance effect
    if distance_km < 10:
        distance_factor = 10
    elif distance_km < 50:
        distance_factor = 7
    elif distance_km < 100:
        distance_factor = 5
    elif distance_km < 200:
        distance_factor = 3
    else:
        distance_factor = 0

    # realistic magnitude effect
    score = magnitude * 4 + building_factor + distance_factor
    return round(score, 1)


def impact_level(score):
    if score < 20:
        return "Low"
    elif score < 45:
        return "Medium"
    else:
        return "High"


def felt_intensity(score):
    if score < 20:
        return "Barely felt"
    elif score < 45:
        return "Strong shaking possible"
    else:
        return "Potential damage"


def confidence_statement(score):
    if score < 10:
        return "You are very unlikely to notice any earthquake activity."
    elif score < 30:
        return "Some people may feel light shaking."
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
        response = requests.get(USGS_LATEST, timeout=10)
        data = response.json()
    except:
        return {"error": "Cannot fetch earthquake data."}

    if not data.get("features"):
        return {"error": "No earthquake data available"}

    nearby_quakes = []

    for q in data["features"]:
        mag = q["properties"]["mag"]
        if mag is None or mag < 3:
            continue

        q_lon, q_lat, depth = q["geometry"]["coordinates"]
        dist = geodesic((lat, lon), (q_lat, q_lon)).km

        if dist < 1000:
            nearby_quakes.append((q, dist))

    # -----------------------------
    # CASE 1: No relevant quakes nearby
    # -----------------------------
    if not nearby_quakes:
        return {
            "status": "No relevant earthquakes near your location",
            "impact_level": "Low",
            "impact_score": 0,
            "felt_intensity": "None",
            "confidence": "No earthquake activity near you is expected to be felt.",
            "why": "No earthquakes of magnitude 3.0+ occurred within 1000 km in the last hour.",
            "what_to_do": [
                "No action needed",
                "Stay informed for future alerts",
                "Ensure general emergency preparedness"
            ]
        }

    # -----------------------------
    # CASE 2: Closest relevant quake
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
