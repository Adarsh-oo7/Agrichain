from django.db import models

# Create your models here.
# crop_ai/ml_model.py
import random

# Dummy data: train ML model based on real data later
CROP_DB = {
    "loamy": {
        "hot": ["cotton", "sugarcane", "millet"],
        "moderate": ["wheat", "barley"],
        "cold": ["potato", "peas"]
    },
    "clayey": {
        "hot": ["rice"],
        "moderate": ["wheat", "pulses"],
        "cold": ["oats"]
    },
    "sandy": {
        "hot": ["millet", "peanuts"],
        "moderate": ["beans"],
        "cold": ["carrot"]
    }
}

def recommend_crop_ml(soil, climate, nearby_crops=None, user_pref=None):
    # Fetch suitable crops based on soil and climate
    base_crops = CROP_DB.get(soil.lower(), {}).get(climate.lower(), [])
    scores = {}

    for crop in base_crops:
        score = 1.0
        if nearby_crops and crop in nearby_crops:
            score *= 0.6  # lower score if already nearby to avoid oversupply
        if user_pref and crop in user_pref:
            score *= 1.5  # increase if user likes it
        scores[crop] = score

    sorted_crops = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_crops[0][0] if sorted_crops else "wheat"  # fallback
