def recommend_crop(soil_type, climate, oversupply_risk):
    crop_recommendations = {
        "sandy": {"hot": "corn", "cold": "wheat"},
        "clay": {"hot": "rice", "cold": "vegetables"},
        "loamy": {"hot": "fruits", "cold": "wheat"},
    }

    if oversupply_risk:
        return "Diversify Crops"  # Avoid oversupplied crops

    return crop_recommendations.get(soil_type, {}).get(climate, "general crops")
