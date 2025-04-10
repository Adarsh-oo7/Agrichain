import json
import requests
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Farm
import joblib
import logging
import numpy as np

logger = logging.getLogger(__name__)

try:
    crop_model = joblib.load("maps/crop_recommendation_model.pkl")
    logger.info("ML model loaded successfully")
except Exception as e:
    logger.error(f"Error loading model: {e}")
    crop_model = None

def get_weather_data(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,precipitation&forecast_days=1"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()["hourly"]
        return {
            "temperature": data["temperature_2m"][0],
            "humidity": data["relative_humidity_2m"][0],
            "rainfall": data["precipitation"][0],
        }
    except requests.RequestException as e:
        logger.error(f"Error fetching weather: {e}")
        return {"temperature": 25, "humidity": 70, "rainfall": 0}



def get_soil_data(lat, lon):
    url = f"https://rest.isric.org/soilgrids/v2.0/properties/query?lat={lat}&lon={lon}&property=nitrogen&property=phh2o&property=clay&property=sand&property=silt&property=cec&depth=0-5cm&value=mean"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()["properties"]["layers"]

        nitrogen = None
        ph = None
        clay = None
        sand = None
        silt = None
        cec = None

        for layer in data:
            if layer["name"] == "nitrogen":
                for depth in layer["depths"]:
                    if depth["range"]["top_depth"] == 0 and depth["range"]["bottom_depth"] == 5:
                        nitrogen = depth["values"]["mean"]
            elif layer["name"] == "phh2o":
                for depth in layer["depths"]:
                    if depth["range"]["top_depth"] == 0 and depth["range"]["bottom_depth"] == 5:
                        ph = depth["values"]["mean"]
            elif layer["name"] == "clay":
                for depth in layer["depths"]:
                    if depth["range"]["top_depth"] == 0 and depth["range"]["bottom_depth"] == 5:
                        clay = depth["values"]["mean"]
            elif layer["name"] == "sand":
                for depth in layer["depths"]:
                    if depth["range"]["top_depth"] == 0 and depth["range"]["bottom_depth"] == 5:
                        sand = depth["values"]["mean"]
            elif layer["name"] == "silt":
                for depth in layer["depths"]:
                    if depth["range"]["top_depth"] == 0 and depth["range"]["bottom_depth"] == 5:
                        silt = depth["values"]["mean"]
            elif layer["name"] == "cec":
                for depth in layer["depths"]:
                    if depth["range"]["top_depth"] == 0 and depth["range"]["bottom_depth"] == 5:
                        cec = depth["values"]["mean"]

        if nitrogen is None or ph is None or clay is None or sand is None or silt is None:
            logger.warning(f"Missing SoilGrids data at ({lat}, {lon}): N={nitrogen}, pH={ph}, clay={clay}, sand={sand}, silt={silt}")
            raise KeyError("Incomplete SoilGrids data")

        # Convert units
        N = nitrogen / 100  # cg/kg to g/kg
        ph_value = ph / 10  # pH*10 to standard pH
        clay_pct = clay / 10
        sand_pct = sand / 10
        silt_pct = silt / 10

        # Classify soil type
        if sand_pct > 85:
            soil_type = "sandy"
        elif clay_pct > 40 and silt_pct < 40:
            soil_type = "clay"
        elif silt_pct > 40 and clay_pct < 20:
            soil_type = "silt"
        else:
            soil_type = "loamy"

        # Estimate P and K
        cec_value = cec or 100
        K = cec_value / 10  # mmol(c)/kg to mg/kg
        P = 35 + (N * 7) if soil_type == "loamy" else 50 + (N * 10) if soil_type == "clay" else 20 + (N * 5) if soil_type == "sandy" else 40 + (N * 8)

        P = min(max(P, 10), 100)
        K = min(max(K, 20), 150)

        return {
            "N": N,
            "P": P,
            "K": K,
            "ph": ph_value,
            "soil_type": soil_type
        }
    except requests.RequestException as e:
        logger.error(f"Error fetching SoilGrids data at ({lat}, {lon}): {e}")
        return {"N": 0.8, "P": 40, "K": 50, "ph": 6.5, "soil_type": "loamy"}
    except (KeyError, TypeError) as e:
        logger.error(f"Error parsing SoilGrids data at ({lat}, {lon}): {e}")
        return {"N": 0.8, "P": 40, "K": 50, "ph": 6.5, "soil_type": "loamy"}

def get_climate_data(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_mean,precipitation_sum&past_days=30"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()["daily"]
        temp_avg = sum(data["temperature_2m_mean"]) / len(data["temperature_2m_mean"])
        rainfall_avg = sum(data["precipitation_sum"]) / 30 * 365
        return {"avg_temp": temp_avg, "avg_rainfall": rainfall_avg}
    except requests.RequestException as e:
        logger.error(f"Error fetching climate: {e}")
        return {"avg_temp": 24, "avg_rainfall": 1200}



def get_crop_recommendations(soil, weather, climate):
    features = [soil["N"], soil["P"], soil["K"], weather["temperature"], weather["humidity"], soil["ph"], climate["avg_rainfall"]]
    valid_crops = [choice[0] for choice in Farm.CROP_CHOICES]
    
    recommendations = []
    
    if crop_model and hasattr(crop_model, 'predict_proba'):
        try:
            probs = crop_model.predict_proba([features])[0]
            model_crops = crop_model.classes_
            crop_probs = {crop: prob for crop, prob in zip(model_crops, probs) if crop in valid_crops}
            for crop in valid_crops:
                if crop in crop_probs:
                    recommendations.append({"crop": crop, "suitability": float(crop_probs[crop] * 100)})
        except Exception as e:
            logger.error(f"Error predicting crop probabilities: {e}")

    def calculate_suitability(crop_conditions):
        score = 0
        total = len(crop_conditions)
        for condition, (min_val, max_val), value in crop_conditions:
            score += 1 if min_val <= value <= max_val else 0
        return (score / total) * 100 if total > 0 else 50

    crop_rules = {
        # Grains and Cereals
        "wheat": [("ph", (6.0, 7.5), soil["ph"]), ("N", (0.5, 1.5), soil["N"]), ("avg_temp", (10, 25), climate["avg_temp"]), ("avg_rainfall", (500, 1000), climate["avg_rainfall"])],
        "rice": [("ph", (5.0, 7.0), soil["ph"]), ("avg_rainfall", (1000, 2000), climate["avg_rainfall"]), ("temperature", (20, 35), weather["temperature"]), ("humidity", (70, 100), weather["humidity"])],
        "corn": [("ph", (5.5, 7.0), soil["ph"]), ("N", (0.8, 2.0), soil["N"]), ("K", (40, 100), soil["K"]), ("avg_temp", (20, 30), climate["avg_temp"])],
        "barley": [("ph", (6.0, 7.5), soil["ph"]), ("avg_temp", (10, 20), climate["avg_temp"]), ("avg_rainfall", (400, 800), climate["avg_rainfall"])],
        "oats": [("ph", (5.5, 7.0), soil["ph"]), ("avg_temp", (10, 20), climate["avg_temp"]), ("avg_rainfall", (400, 800), climate["avg_rainfall"])],
        "sorghum": [("ph", (6.0, 7.5), soil["ph"]), ("avg_temp", (25, 35), climate["avg_temp"]), ("avg_rainfall", (400, 800), climate["avg_rainfall"])],
        "millet": [("ph", (5.5, 7.0), soil["ph"]), ("avg_temp", (25, 35), climate["avg_temp"]), ("avg_rainfall", (300, 600), climate["avg_rainfall"])],
        # Pulses and Legumes
        "soybean": [("ph", (6.0, 7.0), soil["ph"]), ("N", (0.2, 0.8), soil["N"]), ("avg_temp", (20, 30), climate["avg_temp"]), ("avg_rainfall", (600, 1200), climate["avg_rainfall"])],
        "peanut": [("ph", (5.5, 7.0), soil["ph"]), ("avg_temp", (20, 30), climate["avg_temp"]), ("avg_rainfall", (500, 1000), climate["avg_rainfall"])],
        "bean": [("ph", (6.0, 7.0), soil["ph"]), ("avg_temp", (15, 25), climate["avg_temp"]), ("avg_rainfall", (500, 1000), climate["avg_rainfall"])],
        "pea": [("ph", (6.0, 7.0), soil["ph"]), ("avg_temp", (10, 20), climate["avg_temp"]), ("avg_rainfall", (400, 800), climate["avg_rainfall"])],
        "lentil": [("ph", (6.0, 7.5), soil["ph"]), ("avg_temp", (15, 25), climate["avg_temp"]), ("avg_rainfall", (300, 700), climate["avg_rainfall"])],
        "chickpea": [("ph", (6.0, 8.0), soil["ph"]), ("avg_temp", (15, 25), climate["avg_temp"]), ("avg_rainfall", (300, 600), climate["avg_rainfall"])],
        "mungbean": [("ph", (6.0, 7.5), soil["ph"]), ("avg_temp", (25, 35), climate["avg_temp"]), ("avg_rainfall", (500, 1000), climate["avg_rainfall"])],
        # Cash Crops
        "cotton": [("ph", (5.5, 7.0), soil["ph"]), ("avg_temp", (20, 35), climate["avg_temp"]), ("avg_rainfall", (600, 1200), climate["avg_rainfall"])],
        "sugarcane": [("ph", (5.0, 7.0), soil["ph"]), ("avg_temp", (25, 35), climate["avg_temp"]), ("avg_rainfall", (1000, 2000), climate["avg_rainfall"]), ("humidity", (60, 90), weather["humidity"])],
        "sunflower": [("ph", (6.0, 7.5), soil["ph"]), ("avg_temp", (20, 30), climate["avg_temp"]), ("avg_rainfall", (500, 1000), climate["avg_rainfall"])],
        "mustard": [("ph", (6.0, 7.5), soil["ph"]), ("avg_temp", (10, 25), climate["avg_temp"]), ("avg_rainfall", (300, 700), climate["avg_rainfall"])],
        "sesame": [("ph", (6.0, 7.0), soil["ph"]), ("avg_temp", (25, 35), climate["avg_temp"]), ("avg_rainfall", (400, 800), climate["avg_rainfall"])],
        # Vegetables
        "potato": [("ph", (5.0, 6.5), soil["ph"]), ("avg_temp", (15, 25), climate["avg_temp"]), ("avg_rainfall", (500, 1000), climate["avg_rainfall"])],
        "tomato": [("ph", (6.0, 7.0), soil["ph"]), ("avg_temp", (20, 30), climate["avg_temp"]), ("avg_rainfall", (600, 1200), climate["avg_rainfall"])],
        "onion": [("ph", (6.0, 7.0), soil["ph"]), ("avg_temp", (15, 25), climate["avg_temp"]), ("avg_rainfall", (500, 1000), climate["avg_rainfall"])],
        "carrot": [("ph", (6.0, 7.0), soil["ph"]), ("avg_temp", (15, 25), climate["avg_temp"]), ("avg_rainfall", (400, 800), climate["avg_rainfall"])],
        "cabbage": [("ph", (6.0, 7.5), soil["ph"]), ("avg_temp", (15, 25), climate["avg_temp"]), ("avg_rainfall", (500, 1000), climate["avg_rainfall"])],
        "cauliflower": [("ph", (6.0, 7.0), soil["ph"]), ("avg_temp", (15, 25), climate["avg_temp"]), ("avg_rainfall", (500, 1000), climate["avg_rainfall"])],
        "brinjal": [("ph", (5.5, 6.5), soil["ph"]), ("avg_temp", (20, 35), climate["avg_temp"]), ("avg_rainfall", (600, 1200), climate["avg_rainfall"])],
        "okra": [("ph", (6.0, 7.5), soil["ph"]), ("avg_temp", (25, 35), climate["avg_temp"]), ("avg_rainfall", (600, 1200), climate["avg_rainfall"])],
        "spinach": [("ph", (6.0, 7.5), soil["ph"]), ("avg_temp", (15, 25), climate["avg_temp"]), ("avg_rainfall", (400, 800), climate["avg_rainfall"])],
        "chilli": [("ph", (5.5, 7.0), soil["ph"]), ("avg_temp", (20, 35), climate["avg_temp"]), ("avg_rainfall", (600, 1200), climate["avg_rainfall"])],
        "bittergourd": [("ph", (6.0, 7.0), soil["ph"]), ("avg_temp", (25, 35), climate["avg_temp"]), ("avg_rainfall", (600, 1200), climate["avg_rainfall"])],
        "ridgegourd": [("ph", (6.0, 7.0), soil["ph"]), ("avg_temp", (25, 35), climate["avg_temp"]), ("avg_rainfall", (600, 1200), climate["avg_rainfall"])],
        # Fruits
        "banana": [("ph", (5.5, 7.0), soil["ph"]), ("avg_temp", (25, 35), climate["avg_temp"]), ("avg_rainfall", (1200, 2500), climate["avg_rainfall"]), ("humidity", (60, 90), weather["humidity"])],
        "banana_robusta": [("ph", (5.5, 7.0), soil["ph"]), ("avg_temp", (25, 35), climate["avg_temp"]), ("avg_rainfall", (1200, 2500), climate["avg_rainfall"]), ("humidity", (60, 90), weather["humidity"])],
        "banana_rasthali": [("ph", (5.5, 6.5), soil["ph"]), ("avg_temp", (25, 35), climate["avg_temp"]), ("avg_rainfall", (1000, 2000), climate["avg_rainfall"]), ("humidity", (70, 90), weather["humidity"])],
        "banana_poovan": [("ph", (5.5, 7.0), soil["ph"]), ("avg_temp", (25, 35), climate["avg_temp"]), ("avg_rainfall", (1200, 2500), climate["avg_rainfall"]), ("humidity", (60, 90), weather["humidity"])],
        "banana_nendran": [("ph", (5.0, 6.5), soil["ph"]), ("avg_temp", (25, 35), climate["avg_temp"]), ("avg_rainfall", (1500, 3000), climate["avg_rainfall"]), ("humidity", (70, 100), weather["humidity"])],
        "mango": [("ph", (5.5, 7.5), soil["ph"]), ("avg_temp", (20, 35), climate["avg_temp"]), ("avg_rainfall", (800, 1500), climate["avg_rainfall"])],
        "guava": [("ph", (5.0, 7.5), soil["ph"]), ("avg_temp", (20, 35), climate["avg_temp"]), ("avg_rainfall", (800, 1500), climate["avg_rainfall"])],
        "papaya": [("ph", (6.0, 7.0), soil["ph"]), ("avg_temp", (25, 35), climate["avg_temp"]), ("avg_rainfall", (1000, 2000), climate["avg_rainfall"]), ("humidity", (60, 90), weather["humidity"])],
        "pomegranate": [("ph", (6.0, 7.5), soil["ph"]), ("avg_temp", (20, 35), climate["avg_temp"]), ("avg_rainfall", (500, 1000), climate["avg_rainfall"])],
        "jackfruit": [("ph", (5.5, 7.0), soil["ph"]), ("avg_temp", (25, 35), climate["avg_temp"]), ("avg_rainfall", (1200, 2500), climate["avg_rainfall"]), ("humidity", (60, 90), weather["humidity"])],
        "coconut": [("ph", (5.5, 8.0), soil["ph"]), ("avg_temp", (25, 35), climate["avg_temp"]), ("avg_rainfall", (1500, 3000), climate["avg_rainfall"]), ("humidity", (70, 100), weather["humidity"])],
    }

    for crop in valid_crops:
        if not recommendations or crop not in [r["crop"] for r in recommendations]:
            suitability = calculate_suitability(crop_rules.get(crop, []))
            if suitability > 30:
                recommendations.append({"crop": crop, "suitability": suitability})

    recommendations.sort(key=lambda x: x["suitability"], reverse=True)
    return recommendations[:5] if recommendations else [{"crop": "wheat", "suitability": 50.0}]




def farm_map(request):
    return render(request, "maps/map.html")

@csrf_exempt
@login_required
def save_location(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            latitude = float(data.get("latitude", 0))
            longitude = float(data.get("longitude", 0))
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                return JsonResponse({"error": "Invalid latitude or longitude"}, status=400)
            farm = Farm.objects.create(
                farmer=request.user,
                latitude=latitude,
                longitude=longitude,
                soil_type="loamy",
                climate="hot",
                oversupply_risk=False
            )
            return JsonResponse({"message": "Farm location saved successfully", "farm_id": farm.id}, status=201)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid data in save_location: {e}")
            return JsonResponse({"error": f"Invalid data: {str(e)}"}, status=400)
    return JsonResponse({"error": "Invalid request method"}, status=405)

@csrf_exempt
@login_required
def get_location_details(request):
    logger.debug("Entering get_location_details")
    if request.method == "POST":
        try:
            logger.debug("Processing POST request")
            data = json.loads(request.body)
            lat = float(data["latitude"])
            lon = float(data["longitude"])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                return JsonResponse({"error": "Invalid latitude or longitude"}, status=400)

            weather = get_weather_data(lat, lon)
            soil = get_soil_data(lat, lon)
            climate = get_climate_data(lat, lon)
            logger.debug(f"Weather: {weather}")
            logger.debug(f"Soil: {soil}")
            logger.debug(f"Climate: {climate}")

            recommended_crops = get_crop_recommendations(soil, weather, climate)

            response = {
                "weather": weather,
                "soil": soil,
                "climate": climate,
                "recommended_crops": recommended_crops,
                "latitude": lat,
                "longitude": lon
            }
            logger.debug(f"Response: {response}")
            return JsonResponse(response)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid data: {e}")
            return JsonResponse({"error": f"Invalid data: {str(e)}"}, status=400)
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)
    return JsonResponse({"error": "Invalid request method"}, status=405)

@csrf_exempt
@login_required
def add_farm(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)
    try:
        data = json.loads(request.body)
        lat = float(data["latitude"])
        lon = float(data["longitude"])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return JsonResponse({"error": "Invalid latitude or longitude"}, status=400)
        farm_size = float(data.get("farmSize", 1.0))
        if farm_size <= 0:
            return JsonResponse({"error": "Farm size must be positive"}, status=400)

        weather = get_weather_data(lat, lon)
        soil = get_soil_data(lat, lon)
        climate = get_climate_data(lat, lon)
        recommended_crops = get_crop_recommendations(soil, weather, climate)
        top_crop = recommended_crops[0]["crop"]

        farm = Farm(
            farmer=request.user,
            area=farm_size,
            latitude=lat,
            longitude=lon,
            status=data.get("farmStatus", "green"),
            soil_type=soil["soil_type"],
            climate=data.get("climate", "hot"),
            recommended_crop=top_crop,
            user_crop_preferences=data.get("user_crop_preferences", None),
            oversupply_risk=False
        )
        farm.save()

        return JsonResponse({
            "message": "Farm added successfully",
            "farm_id": farm.id,
            "weather": weather,
            "soil": soil,
            "climate": climate,
            "recommended_crops": recommended_crops,
            "user_crop_preferences": farm.user_crop_preferences or "None"
        }, status=201)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Invalid data: {e}")
        return JsonResponse({"error": f"Invalid data: {str(e)}"}, status=400)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)

@login_required
def get_farm_data(request):
    farms = Farm.objects.all()
    farm_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(farm.longitude), float(farm.latitude)]},
                "properties": {
                    "id": farm.id,
                    "farmer_name": farm.farmer.username,
                    "status": farm.status,
                    "area": float(farm.area) if farm.area else None,
                    "soil_type": farm.soil_type,
                    "climate": farm.climate,
                    "recommended_crop": farm.recommended_crop,
                    "user_crop_preferences": farm.user_crop_preferences or "None",
                    "oversupply_risk": farm.oversupply_risk,
                },
            }
            for farm in farms
        ],
    }
    return JsonResponse(farm_data)

@csrf_exempt
@login_required
def get_farm_by_coords(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            latitude = float(data.get("latitude"))
            longitude = float(data.get("longitude"))
            farms = Farm.objects.filter(
                Q(latitude__range=(latitude - 0.0001, latitude + 0.0001)) &
                Q(longitude__range=(longitude - 0.0001, longitude + 0.0001))
            )
            if farms.exists():
                farm = farms.first()
                return JsonResponse({
                    "id": farm.id,
                    "farmer_name": farm.farmer.username,
                    "status": farm.status,
                    "area": float(farm.area) if farm.area else None,
                    "soil_type": farm.soil_type,
                    "climate": farm.climate,
                    "recommended_crop": farm.recommended_crop,
                    "user_crop_preferences": farm.user_crop_preferences or "None",
                    "oversupply_risk": farm.oversupply_risk,
                    "latitude": float(farm.latitude),
                    "longitude": float(farm.longitude),
                })
            return JsonResponse({}, status=404)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid data: {e}")
            return JsonResponse({"error": f"Invalid data: {str(e)}"}, status=400)
    return JsonResponse({"error": "Invalid request method"}, status=405)