# crop_ai/ml_model.py
import joblib

try:
    crop_model = joblib.load("maps/crop_recommendation_model.pkl")
except:
    crop_model = None

def recommend_crop_ml(area, climate, soil_type, nearby_crop=None, preferred_crop=None):
    if not crop_model:
        return "wheat"  # Fallback
    # Mock features for now (integrate real data later)
    features = [50, 40, 30, 25, 50, 7.0, 1000]  # N, P, K, temp, humidity, pH, rainfall
    recommended = crop_model.predict([features])[0]
    # Adjust based on nearby_crop or preferred_crop if provided
    if preferred_crop and preferred_crop in [c[0] for c in Farm.CROP_CHOICES]:
        return preferred_crop
    return recommended