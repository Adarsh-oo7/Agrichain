import json
import requests
import pandas as pd
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Farm, PricePrediction
import joblib
import logging
from datetime import datetime, timedelta
import numpy as np
import os

logger = logging.getLogger(__name__)

try:
    crop_model = joblib.load("maps/crop_recommendation_model.pkl")
    logger.info("ML model loaded successfully")
except Exception as e:
    logger.error(f"Error loading model: {e}")
    crop_model = None

def get_weather_data(lat, lon):
    """Fetch weather data from Open-Meteo API, including wind speed."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,precipitation,windspeed_10m&forecast_days=1"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()["hourly"]
        return {
            "temperature": data["temperature_2m"][0],
            "humidity": data["relative_humidity_2m"][0],
            "rainfall": data["precipitation"][0],
            "wind_speed": data["windspeed_10m"][0],
        }
    except requests.RequestException as e:
        logger.error(f"Error fetching weather at ({lat}, {lon}): {e}")
        return {"temperature": 25, "humidity": 70, "rainfall": 0, "wind_speed": 2.5}

def get_soil_data(lat, lon):
    """Fetch soil data from SoilGrids API."""
    url = f"https://rest.isric.org/soilgrids/v2.0/properties/query?lat={lat}&lon={lon}&property=nitrogen&property=phh2o&property=clay&property=sand&property=silt&property=cec&depth=0-5cm&value=mean"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()["properties"]["layers"]

        soil_properties = {}
        for layer in data:
            for depth in layer["depths"]:
                if depth["range"]["top_depth"] == 0 and depth["range"]["bottom_depth"] == 5:
                    soil_properties[layer["name"]] = depth["values"]["mean"]

        required = ["nitrogen", "phh2o", "clay", "sand", "silt"]
        if not all(k in soil_properties for k in required):
            missing = [k for k in required if k not in soil_properties]
            logger.warning(f"Missing SoilGrids data at ({lat}, {lon}): {missing}")
            raise KeyError("Incomplete SoilGrids data")

        N = soil_properties["nitrogen"] / 100  # cg/kg to g/kg
        ph = soil_properties["phh2o"] / 10  # pH*10 to standard pH
        clay = soil_properties["clay"] / 10
        sand = soil_properties["sand"] / 10
        silt = soil_properties["silt"] / 10

        if sand > 85:
            soil_type = "sandy"
        elif clay > 40 and silt < 40:
            soil_type = "clay"
        elif silt > 40 and clay < 20:
            soil_type = "silt"
        else:
            soil_type = "loamy"

        cec = soil_properties.get("cec", 100)
        K = cec / 10
        P = 35 + (N * 7) if soil_type == "loamy" else 50 + (N * 10) if soil_type == "clay" else 20 + (N * 5) if soil_type == "sandy" else 40 + (N * 8)
        P = min(max(P, 10), 100)
        K = min(max(K, 20), 150)

        return {
            "N": N,
            "P": P,
            "K": K,
            "ph": ph,
            "soil_type": soil_type,
        }
    except (requests.RequestException, KeyError, TypeError) as e:
        logger.error(f"Error fetching/parsing SoilGrids data at ({lat}, {lon}): {e}")
        return {"N": 0.8, "P": 40, "K": 50, "ph": 6.5, "soil_type": "loamy"}

def get_soil_moisture(lat, lon):
    """Fetch soil moisture from Open-Meteo API."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=soil_moisture_0_1cm&forecast_days=1"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()["hourly"]
        return data["soil_moisture_0_1cm"][0] * 100  # Convert to percentage
    except requests.RequestException as e:
        logger.error(f"Error fetching soil moisture at ({lat}, {lon}): {e}")
        return 30.0  # Fallback value

def get_sunlight_hours(lat, lon):
    """Fetch sunlight hours from Sunrise-Sunset API."""
    url = f"https://api.sunrise-sunset.org/json?lat={lat}&lng={lon}&formatted=0"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()["results"]
        sunrise = datetime.fromisoformat(data["sunrise"])
        sunset = datetime.fromisoformat(data["sunset"])
        daylight = (sunset - sunrise).total_seconds() / 3600
        return round(daylight, 1)
    except (requests.RequestException, KeyError) as e:
        logger.error(f"Error fetching sunlight hours at ({lat}, {lon}): {e}")
        return 6.5  # Fallback value

def estimate_pest_risk(weather, crop=None):
    """Estimate pest risk based on weather and optional crop."""
    temperature = weather["temperature"]
    humidity = weather["humidity"]
    if humidity > 80 and temperature > 25:
        return "High"
    elif humidity > 60 or temperature > 20:
        return "Moderate"
    return "Low"

def estimate_water_availability(climate, soil_type):
    """Estimate water availability based on rainfall and soil type."""
    rainfall = climate["avg_rainfall"]
    # Approximate water retention based on soil type (liters per hectare per year)
    retention_factor = {"loamy": 0.7, "clay": 0.9, "sandy": 0.4, "silt": 0.6}
    factor = retention_factor.get(soil_type, 0.7)
    # Convert rainfall (mm/year) to liters/hectare (1 mm = 10,000 L/ha)
    water = rainfall * 10_000 * factor
    return round(water / 1000, 0)  # Convert to thousands of liters

def get_elevation(lat, lon):
    """Fetch elevation from Open-Elevation API."""
    url = f"https://api.open-elevation.com/api/v1/lookup?locations={lat},{lon}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()["results"][0]
        return data["elevation"]
    except (requests.RequestException, KeyError) as e:
        logger.error(f"Error fetching elevation at ({lat}, {lon}): {e}")
        return 10  # Fallback for Kerala’s average low elevation

def get_climate_data(lat, lon):
    """Fetch climate data from Open-Meteo API."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_mean,precipitation_sum&past_days=30"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()["daily"]
        temp_avg = sum(data["temperature_2m_mean"]) / len(data["temperature_2m_mean"])
        rainfall_avg = sum(data["precipitation_sum"]) / 30 * 365
        return {"avg_temp": temp_avg, "avg_rainfall": rainfall_avg}
    except requests.RequestException as e:
        logger.error(f"Error fetching climate at ({lat}, {lon}): {e}")
        return {"avg_temp": 24, "avg_rainfall": 1200}

def get_crop_recommendations(soil, weather, climate):
    """Generate crop recommendations using ML model or rules."""
    features = [
        soil["N"],
        soil["P"],
        soil["K"],
        weather["temperature"],
        weather["humidity"],
        soil["ph"],
        climate["avg_rainfall"]
    ]
    valid_crops = {choice[0] for choice in Farm.CROP_CHOICES}
    
    recommendations = []
    
    if crop_model and hasattr(crop_model, 'predict_proba'):
        try:
            probs = crop_model.predict_proba([features])[0]
            model_crops = crop_model.classes_
            for crop, prob in zip(model_crops, probs):
                if crop in valid_crops:
                    recommendations.append({"crop": crop, "suitability": float(prob * 100)})
        except Exception as e:
            logger.error(f"Error predicting crop probabilities: {e}")

    def calculate_suitability(crop_conditions):
        score = 0
        total = len(crop_conditions)
        for _, (min_val, max_val), value in crop_conditions:
            score += 1 if min_val <= value <= max_val else 0
        return (score / total) * 100 if total > 0 else 50

    crop_rules = {
        "wheat": [("ph", (6.0, 7.5), soil["ph"]), ("N", (0.5, 1.5), soil["N"]), ("avg_temp", (10, 25), climate["avg_temp"]), ("avg_rainfall", (500, 1000), climate["avg_rainfall"])],
        "rice": [("ph", (5.0, 7.0), soil["ph"]), ("avg_rainfall", (1000, 2000), climate["avg_rainfall"]), ("temperature", (20, 35), weather["temperature"]), ("humidity", (70, 100), weather["humidity"])],
        # ... (other crop rules unchanged)
        "coconut": [("ph", (5.5, 8.0), soil["ph"]), ("avg_temp", (25, 35), climate["avg_temp"]), ("avg_rainfall", (1500, 3000), climate["avg_rainfall"]), ("humidity", (70, 100), weather["humidity"])]
    }

    for crop in valid_crops:
        if not recommendations or crop not in {r["crop"] for r in recommendations}:
            suitability = calculate_suitability(crop_rules.get(crop, []))
            if suitability > 30:
                recommendations.append({"crop": crop, "suitability": suitability})

    recommendations.sort(key=lambda x: x["suitability"], reverse=True)
    return recommendations[:5] or [{"crop": "rice", "suitability": 50.0}]

def farm_map(request):
    """Render the farm map template."""
    logger.debug(f"Crop choices: {Farm.CROP_CHOICES}")
    return render(request, "maps/map.html", {
        "crop_choices": Farm.CROP_CHOICES
    })

@csrf_exempt
@login_required
def save_location(request):
    """Save a farm location with basic details."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            latitude = float(data.get("latitude"))
            longitude = float(data.get("longitude"))
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                return JsonResponse({"error": "Invalid latitude or longitude"}, status=400)

            soil = get_soil_data(latitude, longitude)
            climate = get_climate_data(latitude, longitude)
            weather = get_weather_data(latitude, longitude)
            recommended_crops = get_crop_recommendations(soil, weather, climate)
            top_crop = recommended_crops[0]["crop"]

            farm = Farm.objects.create(
                farmer=request.user,
                latitude=latitude,
                longitude=longitude,
                soil_type=soil["soil_type"],
                climate="tropical" if climate["avg_temp"] > 25 else "subtropical",
                recommended_crop=top_crop,
                oversupply_risk=False
            )
            return JsonResponse({"message": "Farm location saved successfully", "farm_id": farm.id}, status=201)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid data in save_location: {e}")
            return JsonResponse({"error": f"Invalid data: {str(e)}"}, status=400)
        except Exception as e:
            logger.error(f"Unexpected error in save_location: {e}")
            return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)
    return JsonResponse({"error": "Invalid request method"}, status=405)

@csrf_exempt
@login_required
def get_location_details(request):
    """Fetch detailed location data (weather, soil, climate, crops)."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            lat = float(data["latitude"])
            lon = float(data["longitude"])
            more_details = data.get("more_details", False)
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                return JsonResponse({"error": "Invalid latitude or longitude"}, status=400)

            weather = get_weather_data(lat, lon)
            soil = get_soil_data(lat, lon)
            climate = get_climate_data(lat, lon)
            recommended_crops = get_crop_recommendations(soil, weather, climate)

            response = {
                "weather": weather,
                "soil": soil,
                "climate": climate,
                "recommended_crops": recommended_crops
            }

            if more_details:
                soil_moisture = get_soil_moisture(lat, lon)
                sunlight_hours = get_sunlight_hours(lat, lon)
                pest_risk = estimate_pest_risk(weather)
                water_availability = estimate_water_availability(climate, soil["soil_type"])
                elevation = get_elevation(lat, lon)

                response.update({
                    "soil": {**soil, "moisture": soil_moisture},
                    "climate": {**climate, "sunlight_hours": sunlight_hours},
                    "pest_risk": pest_risk,
                    "water_availability": water_availability,
                    "elevation": elevation,
                    "weather": {**weather},  # Wind speed already included
                })

            return JsonResponse(response)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid data in get_location_details: {e}")
            return JsonResponse({"error": f"Invalid data: {str(e)}"}, status=400)
        except Exception as e:
            logger.error(f"Unexpected error in get_location_details: {e}")
            return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)
    return JsonResponse({"error": "Invalid request method"}, status=405)

@csrf_exempt
@login_required
def add_farm(request):
    """Add a new farm with detailed attributes."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            lat = float(data["latitude"])
            lon = float(data["longitude"])
            farm_size = float(data.get("farmSize", 1.0))
            farm_status = data.get("farmStatus", "green")
            user_crop = data.get("user_crop_preferences")
            planting_date = data.get("planting_date")
            yield_per_acre = float(data.get("yield_per_acre", 10.0))

            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                return JsonResponse({"error": "Invalid latitude or longitude"}, status=400)
            if farm_size <= 0:
                return JsonResponse({"error": "Farm size must be positive"}, status=400)
            if yield_per_acre <= 0:
                return JsonResponse({"error": "Yield per acre must be positive"}, status=400)
            if user_crop and user_crop not in dict(Farm.CROP_CHOICES):
                return JsonResponse({"error": f"Invalid crop: {user_crop}"}, status=400)
            if farm_status not in dict(Farm.STATUS_CHOICES):
                return JsonResponse({"error": f"Invalid status: {farm_status}"}, status=400)
            if planting_date:
                try:
                    planting_date = datetime.strptime(planting_date, '%Y-%m-%d').date()
                except ValueError:
                    return JsonResponse({"error": "Invalid planting date format"}, status=400)

            weather = get_weather_data(lat, lon)
            soil = get_soil_data(lat, lon)
            climate = get_climate_data(lat, lon)
            recommended_crops = get_crop_recommendations(soil, weather, climate)
            top_crop = recommended_crops[0]["crop"]

            farm = Farm.objects.create(
                farmer=request.user,
                latitude=lat,
                longitude=lon,
                area=farm_size,
                status=farm_status,
                soil_type=soil["soil_type"],
                climate=data.get("climate", "tropical"),
                recommended_crop=top_crop,
                user_crop_preferences=user_crop,
                planting_date=planting_date,
                yield_per_acre=yield_per_acre,
                oversupply_risk=False
            )

            return JsonResponse({
                "message": "Farm added successfully",
                "farm_id": farm.id,
                "recommended_crop": farm.recommended_crop,
                "oversupply_risk": farm.oversupply_risk
            }, status=201)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid data in add_farm: {e}")
            return JsonResponse({"error": f"Invalid data: {str(e)}"}, status=400)
        except Exception as e:
            logger.error(f"Unexpected error in add_farm: {e}")
            return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)
    return JsonResponse({"error": "Invalid request method"}, status=405)

@login_required
def get_farm_data(request):
    """Retrieve all farms as GeoJSON."""
    farms = Farm.objects.all()
    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(farm.longitude), float(farm.latitude)]
            },
            "properties": {
                "id": farm.id,
                "farmer": farm.farmer.username,
                "status": farm.status,
                "area": float(farm.area) if farm.area else None,
                "soil_type": farm.soil_type,
                "climate": farm.climate,
                "recommended_crop": farm.recommended_crop,
                "user_crop_preferences": farm.user_crop_preferences,
                "planting_date": farm.planting_date.strftime('%Y-%m-%d') if farm.planting_date else None,
                "yield_per_acre": float(farm.yield_per_acre) if farm.yield_per_acre else None,
                "oversupply_risk": farm.oversupply_risk
            }
        }
        for farm in farms
    ]
    return JsonResponse({"type": "FeatureCollection", "features": features})

@csrf_exempt
@login_required
def get_farm_by_coords(request):
    """Retrieve a farm by coordinates."""
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
                    "farmer": farm.farmer.username,
                    "status": farm.status,
                    "area": float(farm.area) if farm.area else None,
                    "soil_type": farm.soil_type,
                    "climate": farm.climate,
                    "recommended_crop": farm.recommended_crop,
                    "user_crop_preferences": farm.user_crop_preferences,
                    "planting_date": farm.planting_date.strftime('%Y-%m-%d') if farm.planting_date else None,
                    "yield_per_acre": float(farm.yield_per_acre) if farm.yield_per_acre else None,
                    "oversupply_risk": farm.oversupply_risk
                })
            return JsonResponse({}, status=404)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid data in get_farm_by_coords: {e}")
            return JsonResponse({"error": f"Invalid data: {str(e)}"}, status=400)
    return JsonResponse({"error": "Invalid request method"}, status=405)


@login_required
def my_farms(request):
    """
    Render the user's farms template with their registered farms.
    Fetches all farms for the logged-in farmer and passes them as GeoJSON-like data.
    """
    try:
        farms = Farm.objects.filter(farmer=request.user)
        farm_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [float(farm.longitude), float(farm.latitude)]
                    },
                    "properties": {
                        "id": farm.id,
                        "farmer_name": farm.farmer.username,
                        "status": farm.status or "green",
                        "area": float(farm.area) if farm.area else None,
                        "soil_type": farm.soil_type or "unknown",
                        "climate": farm.climate or "unknown",
                        "user_crop_preferences": farm.user_crop_preferences or "",
                        "recommended_crop": farm.recommended_crop or "",
                        "oversupply_risk": bool(farm.oversupply_risk)  # Ensure JS-compatible boolean
                    }
                } for farm in farms
            ]
        }
    except Exception as e:
        farm_data = {"type": "FeatureCollection", "features": []}
        print(f"Error fetching farms: {e}")  # For debugging; use logging in production
    return render(request, "maps/my_farms.html", {
        "farm_data_json": json.dumps(farm_data, allow_nan=False),  # Safe JSON string
        "has_farms": len(farm_data["features"]) > 0
    })

@csrf_exempt
@login_required
def delete_farm(request, farm_id):
    """Delete a farm by ID."""
    if request.method == "DELETE":
        try:
            farm = Farm.objects.get(id=farm_id, farmer=request.user)
            lat, lon = farm.latitude, farm.longitude
            farm.delete()
            return JsonResponse({
                "message": "Farm deleted successfully",
                "latitude": float(lat),
                "longitude": float(lon)
            }, status=200)
        except Farm.DoesNotExist:
            return JsonResponse({"error": "Farm not found or unauthorized"}, status=404)
        except Exception as e:
            logger.error(f"Error deleting farm: {e}")
            return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)
    return JsonResponse({"error": "Invalid request method"}, status=405)

@csrf_exempt
def get_price_prediction(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=400)
    try:
        data = json.loads(request.body)
        crop = data.get('crop')
        harvest_date = data.get('harvest_date')
        farm_id = data.get('farm_id')

        if not crop or not harvest_date:
            logger.error(f"Missing crop: {crop}, harvest_date: {harvest_date}")
            return JsonResponse({
                'error': 'Crop and harvest date are required',
                'crop': crop,
                'date': harvest_date
            }, status=400)

        logger.debug(f"Fetching price prediction for crop: {crop}, date: {harvest_date}")

        csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'price_predictions.csv')
        df = pd.read_csv(csv_path)
        df['date'] = pd.to_datetime(df['date'])
        target_date = pd.to_datetime(harvest_date)

        df['crop_normalized'] = df['crop'].str.replace('_Kochi', '', case=False)
        prediction = df[
            (df['crop_normalized'] == crop) & (df['date'] <= target_date)
        ].sort_values('date', ascending=False)

        if prediction.empty:
            prediction = df[
                (df['crop'] == crop) & (df['date'] <= target_date)
            ].sort_values('date', ascending=False)
            if prediction.empty:
                prediction = df[
                    df['crop_normalized'] == crop
                ].sort_values('date', key=lambda x: abs(x - target_date))
                if prediction.empty:
                    prediction = df[
                        df['crop'] == crop
                    ].sort_values('date', key=lambda x: abs(x - target_date))
                if prediction.empty:
                    logger.warning(f"No prediction for {crop} on or before {harvest_date}")
                    return JsonResponse({
                        'warning': f'No prediction for {crop} on or before {harvest_date}',
                        'crop': crop,
                        'date': harvest_date,
                        'predicted_price': 1000.00
                    })

        price = prediction.iloc[0]['predicted_price']
        response = {
            'crop': crop,
            'date': harvest_date,
            'predicted_price': float(price)
        }

        if farm_id:
            try:
                farm = Farm.objects.get(id=farm_id)
                total_yield = farm.area * farm.yield_per_acre
                estimated_revenue = total_yield * price
                response.update({
                    'total_yield': float(total_yield),
                    'estimated_revenue': float(estimated_revenue)
                })
            except Farm.DoesNotExist:
                response['warning'] = 'Farm not found'

        logger.debug(f"Price prediction response: {response}")
        return JsonResponse(response)
    except Exception as e:
        logger.error(f"Error in get_price_prediction: {e}")
        return JsonResponse({'error': str(e)}, status=500)

def test_logging(request):
    logger = logging.getLogger('maps')
    logger.debug("Test logging from maps.views")
    return JsonResponse({'message': 'Logged'})