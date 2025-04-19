import json
import requests
import pandas as pd
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator
from .models import Farm
import joblib
import logging
from datetime import datetime
import numpy as np
import os
from math import radians, sin, cos, sqrt, atan2

logger = logging.getLogger(__name__)

try:
    crop_model = joblib.load("maps/crop_recommendation_model.pkl")
    logger.info("ML model loaded successfully")
except Exception as e:
    logger.error(f"Error loading model: {e}")
    crop_model = None

def check_water_location(lat, lon):
    """Check if the given coordinates are over water using Nominatim API with fallback."""
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=10"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        location_type = data.get('type', '')
        display_name = data.get('display_name', '')
        water_keywords = ['sea', 'ocean', 'waterbody', 'lake', 'river', 'bay', 'gulf']
        is_water = any(keyword in location_type.lower() or keyword in display_name.lower() for keyword in water_keywords)
        
        # Fallback: Check elevation (sea typically has elevation <= 0)
        if not is_water:
            elevation = get_elevation(lat, lon)
            if elevation <= 0:
                logger.warning(f"Location ({lat}, {lon}) has elevation {elevation}, likely water")
                is_water = True
        
        if is_water:
            logger.info(f"Water location detected at ({lat}, {lon}): {display_name}")
        return is_water
    except requests.RequestException as e:
        logger.error(f"Error checking location at ({lat}, {lon}): {e}")
        # Fallback: Assume water if API fails and elevation is low
        elevation = get_elevation(lat, lon)
        if elevation <= 0:
            logger.warning(f"API failed, elevation {elevation} at ({lat}, {lon}), assuming water")
            return True
        return False

def get_weather_data(lat, lon):
    """Fetch weather data from Open-Meteo API."""
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
        response = requests.get(url, timeout=14)
        response.raise_for_status()
        data = response.json()["properties"]["layers"]
        soil_properties = {}
        for layer in data:
            for depth in layer["depths"]:
                if depth["range"]["top_depth"] == 0 and depth["range"]["bottom_depth"] == 5:
                    soil_properties[layer["name"]] = depth["values"]["mean"]

        required = ["nitrogen", "phh2o", "clay", "sand", "silt"]
        if not all(k in soil_properties for k in required):
            raise KeyError("Incomplete SoilGrids data")

        N = soil_properties["nitrogen"] / 100
        ph = soil_properties["phh2o"] / 10
        clay = soil_properties["clay"] / 10
        sand = soil_properties["sand"] / 10
        silt = soil_properties["silt"] / 10
        soil_type = "sandy" if sand > 85 else "clay" if clay > 40 and silt < 40 else "silt" if silt > 40 and clay < 20 else "loamy"
        K = (soil_properties.get("cec", 100) / 10)
        P = 35 + (N * 7) if soil_type == "loamy" else 50 + (N * 10) if soil_type == "clay" else 20 + (N * 5) if soil_type == "sandy" else 40 + (N * 8)
        P = min(max(P, 10), 100)
        K = min(max(K, 20), 150)
        return {"N": N, "P": P, "K": K, "ph": ph, "soil_type": soil_type, "elevation": get_elevation(lat, lon)}
    except (requests.RequestException, KeyError) as e:
        logger.error(f"Error fetching soil data at ({lat}, {lon}): {e}")
        return {"N": 0.8, "P": 40, "K": 50, "ph": 6.5, "soil_type": "loamy", "elevation": 28}

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

def get_sunlight_hours(lat, lon):
    """Fetch sunlight hours from Sunrise-Sunset API."""
    url = f"https://api.sunrise-sunset.org/json?lat={lat}&lng={lon}&formatted=0"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()["results"]
        sunrise = datetime.fromisoformat(data["sunrise"])
        sunset = datetime.fromisoformat(data["sunset"])
        return round((sunset - sunrise).total_seconds() / 3600, 1)
    except Exception as e:
        logger.error(f"Error fetching sunlight hours at ({lat}, {lon}): {e}")
        return 6.5

def get_soil_moisture(lat, lon):
    """Fetch soil moisture from Open-Meteo API."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=soil_moisture_0_1cm&forecast_days=1"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()["hourly"]["soil_moisture_0_1cm"][0] * 100
    except requests.RequestException as e:
        logger.error(f"Error fetching soil moisture at ({lat}, {lon}): {e}")
        return 30.0

def estimate_pest_risk(weather, crop=None):
    """Estimate pest risk based on weather."""
    temperature = weather["temperature"]
    humidity = weather["humidity"]
    return "High" if humidity > 80 and temperature > 25 else "Moderate" if humidity > 60 or temperature > 20 else "Low"

def estimate_water_availability(climate, soil_type):
    """Estimate water availability."""
    rainfall = climate["avg_rainfall"]
    retention = {"loamy": 0.7, "clay": 0.9, "sandy": 0.4, "silt": 0.6}
    water = rainfall * 10_000 * retention.get(soil_type, 0.7)
    return round(water / 1000, 0)

def get_elevation(lat, lon):
    """Fetch elevation from Open-Elevation API."""
    url = f"https://api.open-elevation.com/api/v1/lookup?locations={lat},{lon}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()["results"][0]["elevation"]
    except Exception as e:
        logger.error(f"Error fetching elevation at ({lat}, {lon}): {e}")
        return 10

def get_price_data(crop, lat, lon, date='2024-12-31'):
    """Fetch predicted price from CSV."""
    try:
        markets = {
            'Kochi': (9.9312, 76.2673),
            'Chennai': (13.0827, 80.2707),
            'Delhi': (28.7041, 77.1025),
            'Ludhiana': (30.9009, 75.8573)
        }
        def haversine(lat1, lon1, lat2, lon2):
            R = 6371
            dlat = radians(lat2 - lat1)
            dlon = radians(lon2 - lon1)
            a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            return R * c
        market = min(markets, key=lambda m: haversine(lat, lon, markets[m][0], markets[m][1]))
        df = pd.read_csv('data/price_predictions.csv')
        key = f"{crop}_{market}"
        row = df[(df['crop'] == key) & (df['date'] == date)]
        return row['predicted_price'].iloc[0] if not row.empty else 1000
    except Exception as e:
        logger.error(f"Error fetching price for {crop}: {e}")
        return 1000

def calculate_market_status(crop, market, harvest_date, combined_csv):
    """Calculate oversupply and low demand status based on market data."""
    try:
        if not os.path.exists(combined_csv):
            logger.warning(f"Combined CSV missing at {combined_csv}")
            return {"oversupply_status": False, "low_demand_status": False}

        df = pd.read_csv(combined_csv)
        df["date"] = pd.to_datetime(df["date"], errors='coerce')
        crop_key = f"{crop}_{market}"

        # Check if supply and demand columns exist
        supply_col = f"{crop_key}_supply"
        demand_col = f"{crop_key}_demand"
        if supply_col in df.columns and demand_col in df.columns:
            # Get recent data (last 12 months)
            target_date = pd.to_datetime(harvest_date, errors='coerce')
            one_year_ago = target_date - pd.Timedelta(days=365)
            recent_data = df[(df["date"] >= one_year_ago) & (df["date"] <= target_date)]

            if recent_data.empty:
                logger.warning(f"No recent supply/demand data for {crop_key}")
                return {"oversupply_status": False, "low_demand_status": False}

            # Calculate average supply and demand
            avg_supply = recent_data[supply_col].replace(0, pd.NA).mean()
            avg_demand = recent_data[demand_col].replace(0, pd.NA).mean()

            if pd.isna(avg_supply) or pd.isna(avg_demand):
                logger.warning(f"Invalid supply/demand data for {crop_key}")
                return {"oversupply_status": False, "low_demand_status": False}

            # Oversupply: Supply exceeds demand by 20%
            oversupply_status = avg_supply > avg_demand * 1.2

            # Low demand: Demand is below 80% of historical average
            historical_demand = df[demand_col].replace(0, pd.NA).mean()
            low_demand_status = avg_demand < historical_demand * 0.8 if not pd.isna(historical_demand) else False

            logger.info(f"Market status for {crop_key}: oversupply={oversupply_status}, low_demand={low_demand_status}")
            return {
                "oversupply_status": oversupply_status,
                "low_demand_status": low_demand_status
            }
        else:
            # Fallback: Use price trends as proxy
            if crop_key in df.columns:
                recent_data = df[(df["date"] >= one_year_ago) & (df["date"] <= target_date)]
                if recent_data.empty:
                    logger.warning(f"No recent price data for {crop_key}")
                    return {"oversupply_status": False, "low_demand_status": False}

                avg_price = recent_data[crop_key].replace(0, pd.NA).mean()
                historical_avg = df[crop_key].replace(0, pd.NA).mean()

                if pd.isna(avg_price) or pd.isna(historical_avg):
                    logger.warning(f"Invalid price data for {crop_key}")
                    return {"oversupply_status": False, "low_demand_status": False}

                # Oversupply: Recent price is significantly below historical average
                oversupply_status = avg_price < historical_avg * 0.8

                # Low demand: Price stability (low variance) suggests low trading volume
                price_variance = recent_data[crop_key].replace(0, pd.NA).var()
                low_demand_status = price_variance < df[crop_key].replace(0, pd.NA).var() * 0.5 if not pd.isna(price_variance) else False

                logger.info(f"Price-based market status for {crop_key}: oversupply={oversupply_status}, low_demand={low_demand_status}")
                return {
                    "oversupply_status": oversupply_status,
                    "low_demand_status": low_demand_status
                }
            else:
                logger.warning(f"No data for {crop_key} in combined_data.csv")
                return {"oversupply_status": False, "low_demand_status": False}
    except Exception as e:
        logger.error(f"Error calculating market status for {crop}_{market}: {e}")
        return {"oversupply_status": False, "low_demand_status": False}

@login_required
def farm_map(request):
    """Render the farm map template."""
    return render(request, "maps/map.html", {
        "crop_choices": Farm.CROP_CHOICES
    })

@csrf_exempt
@login_required
def save_location(request):
    """Save a farm location."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            latitude = float(data.get("latitude"))
            longitude = float(data.get("longitude"))
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                return JsonResponse({"error": "Invalid coordinates"}, status=400)

            # Check if location is water
            if check_water_location(latitude, longitude):
                return JsonResponse({"error": "Cannot process request for water location"}, status=400)

            soil = get_soil_data(latitude, longitude)
            climate = get_climate_data(latitude, longitude)
            weather = get_weather_data(latitude, longitude)
            recommended_crops = get_crop_recommendations(soil, weather, climate, latitude, longitude)

            farm = Farm.objects.create(
                farmer=request.user,
                latitude=latitude,
                longitude=longitude,
                soil_type=soil["soil_type"],
                climate="tropical" if climate["avg_temp"] > 25 else "subtropical",
                recommended_crop=recommended_crops[0]["crop"],
                oversupply_risk=False
            )
            return JsonResponse({"message": "Farm saved", "farm_id": farm.id}, status=201)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid data in save_location: {e}")
            return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"error": "Invalid method"}, status=405)

@csrf_exempt
@login_required
def get_location_details(request):
    """Fetch location details."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            lat = float(data["latitude"])
            lon = float(data["longitude"])
            more_details = data.get("more_details", False)
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                logger.error(f"Invalid coordinates: ({lat}, {lon})")
                return JsonResponse({"error": "Invalid coordinates"}, status=400)

            # Check if location is water
            if check_water_location(lat, lon):
                logger.info(f"Blocked water location details request for ({lat}, {lon})")
                return JsonResponse({"error": "Cannot process request for water location"}, status=400)

            weather = get_weather_data(lat, lon)
            soil = get_soil_data(lat, lon)
            climate = get_climate_data(lat, lon)
            recommended_crops = get_crop_recommendations(soil, weather, climate, lat, lon)

            response = {
                "weather": weather,
                "soil": soil,
                "climate": climate,
                "recommended_crops": recommended_crops
            }
            if more_details:
                response.update({
                    "soil": {**soil, "moisture": get_soil_moisture(lat, lon)},
                    "climate": {**climate, "sunlight_hours": get_sunlight_hours(lat, lon)},
                    "pest_risk": estimate_pest_risk(weather),
                    "water_availability": estimate_water_availability(climate, soil["soil_type"]),
                    "elevation": soil["elevation"],
                })
            logger.info(f"Successfully fetched location details for ({lat}, {lon})")
            return JsonResponse(response)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid data in get_location_details: {e}")
            return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"error": "Invalid method"}, status=405)

@csrf_exempt
@login_required
def get_farm_by_coords(request):
    """Retrieve farm by coordinates."""
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
            return JsonResponse({"message": "No farm found"}, status=200)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid data in get_farm_by_coords: {e}")
            return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"error": "Invalid method"}, status=405)

@csrf_exempt
@login_required
def add_farm(request):
    """Add a new farm."""
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
                return JsonResponse({"error": "Invalid coordinates"}, status=400)
            if farm_size <= 0 or yield_per_acre <= 0:
                return JsonResponse({"error": "Invalid farm size or yield"}, status=400)
            if user_crop and user_crop not in dict(Farm.CROP_CHOICES):
                return JsonResponse({"error": f"Invalid crop: {user_crop}"}, status=400)

            # Check if location is water
            if check_water_location(lat, lon):
                return JsonResponse({"error": "Cannot process request for water location"}, status=400)

            weather = get_weather_data(lat, lon)
            soil = get_soil_data(lat, lon)
            climate = get_climate_data(lat, lon)
            recommended_crops = get_crop_recommendations(soil, weather, climate, lat, lon)

            farm = Farm.objects.create(
                farmer=request.user,
                latitude=lat,
                longitude=lon,
                area=farm_size,
                status=farm_status,
                soil_type=soil["soil_type"],
                climate="tropical" if climate["avg_temp"] > 25 else "subtropical",
                recommended_crop=recommended_crops[0]["crop"],
                user_crop_preferences=user_crop,
                planting_date=datetime.strptime(planting_date, '%Y-%m-%d').date() if planting_date else None,
                yield_per_acre=yield_per_acre,
                oversupply_risk=False
            )
            return JsonResponse({
                "message": "Farm added",
                "farm_id": farm.id,
                "recommended_crop": farm.recommended_crop
            }, status=201)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid data in add_farm: {e}")
            return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"error": "Invalid method"}, status=405)

@login_required
def get_farm_data(request):
    """Retrieve all farms as GeoJSON."""
    farms = Farm.objects.all()
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(farm.longitude), float(farm.latitude)]},
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
        } for farm in farms
    ]
    return JsonResponse({"type": "FeatureCollection", "features": features})

@login_required
def my_farms(request):
    """Render user's farms with pagination."""
    try:
        farms = Farm.objects.filter(farmer=request.user)
        paginator = Paginator(farms, 10)
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)
        farm_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [float(farm.longitude), float(farm.latitude)]},
                    "properties": {
                        "id": farm.id,
                        "farmer_name": farm.farmer.username,
                        "status": farm.status or "green",
                        "area": float(farm.area) if farm.area else None,
                        "soil_type": farm.soil_type or "unknown",
                        "climate": farm.climate or "unknown",
                        "user_crop_preferences": farm.user_crop_preferences or "",
                        "recommended_crop": farm.recommended_crop or "",
                        "oversupply_risk": bool(farm.oversupply_risk),
                        "planting_date": farm.planting_date.strftime('%Y-%m-%d') if farm.planting_date else None,
                        "yield_per_acre": float(farm.yield_per_acre) if farm.yield_per_acre else None
                    }
                } for farm in page_obj
            ]
        }
        logger.info(f"Loaded {len(farm_data['features'])} farms for user {request.user.username}")
    except Exception as e:
        logger.error(f"Error fetching farms: {e}")
        farm_data = {"type": "FeatureCollection", "features": []}
        page_obj = None
    return render(request, "maps/my_farms.html", {
        "farm_data_json": json.dumps(farm_data, allow_nan=False),
        "has_farms": len(farm_data["features"]) > 0,
        "page_obj": page_obj,
        "total_farms": farms.count() if farms else 0
    })

@csrf_exempt
@login_required
def delete_farm(request, farm_id):
    """Delete a farm."""
    if request.method == "DELETE":
        try:
            farm = Farm.objects.get(id=farm_id, farmer=request.user)
            lat, lon = farm.latitude, farm.longitude
            farm.delete()
            return JsonResponse({"message": "Farm deleted", "latitude": float(lat), "longitude": float(lon)}, status=200)
        except Farm.DoesNotExist:
            return JsonResponse({"error": "Farm not found"}, status=404)
    return JsonResponse({"error": "Invalid method"}, status=405)

def get_crop_recommendations(soil, weather, climate, lat, lon):
    """Generate accurate crop recommendations."""
    feature_names = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
    features = pd.DataFrame([[
        soil["N"],
        soil["P"],
        soil["K"],
        weather["temperature"],
        weather["humidity"],
        soil["ph"],
        climate["avg_rainfall"]
    ]], columns=feature_names)
    
    recommendations = []
    valid_crops = {
        "coconut", "rice", "banana", "cardamom", "cotton", "gram", "groundnut",
        "maize", "mustard", "pepper", "rubber", "soybean", "tapioca", "turmeric", "wheat"
    }

    # ML model prediction
    if crop_model and hasattr(crop_model, 'predict_proba'):
        try:
            probs = crop_model.predict_proba(features)[0]
            model_crops = crop_model.classes_
            for crop, prob in zip(model_crops, probs):
                if crop in valid_crops:
                    score = float(prob * 100)
                    if score >= 35:
                        recommendations.append({"crop": crop, "suitability": score})
        except Exception as e:
            logger.error(f"Error predicting crops: {e}")

    # Rule-based scoring
    crop_rules = {
        'coconut': [
            ('ph', 5.5, 8.0, soil['ph'], 0.15),
            ('N', 0.5, 1.5, soil['N'], 0.1),
            ('P', 0.3, 1.0, soil['P'], 0.1),
            ('K', 0.5, 1.5, soil['K'], 0.1),
            ('avg_temp', 25, 35, climate['avg_temp'], 0.25),
            ('humidity', 60, 90, weather['humidity'], 0.1),
            ('avg_rainfall', 1500, 3000, climate['avg_rainfall'], 0.25),
            ('soil_type', 'sandy', None, soil['soil_type'], 0.15),
            ('elevation', 0, 600, soil['elevation'], 0.05)
        ],
        'rice': [
            ('ph', 5.0, 7.0, soil['ph'], 0.15),
            ('N', 0.5, 1.5, soil['N'], 0.15),
            ('P', 30, 70, soil['P'], 0.1),
            ('K', 30, 50, soil['K'], 0.1),
            ('avg_temp', 20, 35, climate['avg_temp'], 0.2),
            ('humidity', 70, 100, weather['humidity'], 0.15),
            ('avg_rainfall', 1000, 2000, climate['avg_rainfall'], 0.3),
            ('soil_type', 'clay', None, soil['soil_type'], 0.1),
            ('elevation', 0, 1500, soil['elevation'], 0.05)
        ],
        'banana': [
            ('ph', 5.5, 7.5, soil['ph'], 0.15),
            ('N', 0.7, 1.8, soil['N'], 0.15),
            ('P', 40, 80, soil['P'], 0.1),
            ('K', 50, 90, soil['K'], 0.15),
            ('avg_temp', 20, 35, climate['avg_temp'], 0.2),
            ('humidity', 70, 95, weather['humidity'], 0.15),
            ('avg_rainfall', 1000, 2500, climate['avg_rainfall'], 0.2),
            ('soil_type', 'loamy', None, soil['soil_type'], 0.1),
            ('elevation', 0, 1200, soil['elevation'], 0.05)
        ],
        'cardamom': [
            ('ph', 4.5, 6.5, soil['ph'], 0.15),
            ('N', 0.5, 1.2, soil['N'], 0.1),
            ('P', 20, 50, soil['P'], 0.1),
            ('K', 30, 60, soil['K'], 0.1),
            ('avg_temp', 15, 30, climate['avg_temp'], 0.2),
            ('humidity', 70, 95, weather['humidity'], 0.2),
            ('avg_rainfall', 1500, 4000, climate['avg_rainfall'], 0.25),
            ('soil_type', 'loamy', None, soil['soil_type'], 0.1),
            ('elevation', 600, 1500, soil['elevation'], 0.1)
        ],
        'cotton': [
            ('ph', 5.5, 7.5, soil['ph'], 0.15),
            ('N', 0.8, 1.8, soil['N'], 0.15),
            ('P', 30, 60, soil['P'], 0.1),
            ('K', 20, 50, soil['K'], 0.1),
            ('avg_temp', 20, 35, climate['avg_temp'], 0.25),
            ('humidity', 50, 80, weather['humidity'], 0.1),
            ('avg_rainfall', 600, 1200, climate['avg_rainfall'], 0.2),
            ('soil_type', 'loamy', None, soil['soil_type'], 0.1),
            ('elevation', 0, 1000, soil['elevation'], 0.05)
        ],
        'gram': [
            ('ph', 6.0, 7.5, soil['ph'], 0.15),
            ('N', 0.2, 0.8, soil['N'], 0.1),
            ('P', 20, 50, soil['P'], 0.15),
            ('K', 15, 40, soil['K'], 0.1),
            ('avg_temp', 15, 30, climate['avg_temp'], 0.2),
            ('humidity', 40, 70, weather['humidity'], 0.1),
            ('avg_rainfall', 400, 800, climate['avg_rainfall'], 0.2),
            ('soil_type', 'loamy', None, soil['soil_type'], 0.1),
            ('elevation', 0, 1000, soil['elevation'], 0.05)
        ],
        'groundnut': [
            ('ph', 6.0, 7.5, soil['ph'], 0.15),
            ('N', 0.3, 1.0, soil['N'], 0.1),
            ('P', 20, 50, soil['P'], 0.15),
            ('K', 20, 50, soil['K'], 0.1),
            ('avg_temp', 20, 35, climate['avg_temp'], 0.2),
            ('humidity', 50, 80, weather['humidity'], 0.1),
            ('avg_rainfall', 500, 1000, climate['avg_rainfall'], 0.2),
            ('soil_type', 'sandy', None, soil['soil_type'], 0.1),
            ('elevation', 0, 1000, soil['elevation'], 0.05)
        ],
        'maize': [
            ('ph', 5.5, 7.5, soil['ph'], 0.15),
            ('N', 0.8, 1.8, soil['N'], 0.15),
            ('P', 40, 80, soil['P'], 0.1),
            ('K', 30, 60, soil['K'], 0.1),
            ('avg_temp', 18, 35, climate['avg_temp'], 0.2),
            ('humidity', 50, 80, weather['humidity'], 0.1),
            ('avg_rainfall', 500, 1500, climate['avg_rainfall'], 0.2),
            ('soil_type', 'loamy', None, soil['soil_type'], 0.1),
            ('elevation', 0, 2500, soil['elevation'], 0.05)
        ],
        'mustard': [
            ('ph', 6.0, 7.5, soil['ph'], 0.15),
            ('N', 0.5, 1.5, soil['N'], 0.1),
            ('P', 20, 50, soil['P'], 0.1),
            ('K', 20, 50, soil['K'], 0.1),
            ('avg_temp', 10, 25, climate['avg_temp'], 0.25),
            ('humidity', 40, 70, weather['humidity'], 0.1),
            ('avg_rainfall', 300, 700, climate['avg_rainfall'], 0.2),
            ('soil_type', 'loamy', None, soil['soil_type'], 0.1),
            ('elevation', 0, 1500, soil['elevation'], 0.05)
        ],
        'pepper': [
            ('ph', 4.5, 6.5, soil['ph'], 0.15),
            ('N', 0.5, 1.5, soil['N'], 0.1),
            ('P', 20, 50, soil['P'], 0.1),
            ('K', 30, 60, soil['K'], 0.1),
            ('avg_temp', 20, 35, climate['avg_temp'], 0.2),
            ('humidity', 70, 95, weather['humidity'], 0.2),
            ('avg_rainfall', 1500, 3000, climate['avg_rainfall'], 0.25),
            ('soil_type', 'loamy', None, soil['soil_type'], 0.1),
            ('elevation', 0, 1500, soil['elevation'], 0.05)
        ],
        'rubber': [
            ('ph', 4.5, 6.0, soil['ph'], 0.15),
            ('N', 0.5, 1.5, soil['N'], 0.1),
            ('P', 20, 50, soil['P'], 0.1),
            ('K', 20, 50, soil['K'], 0.1),
            ('avg_temp', 25, 35, climate['avg_temp'], 0.25),
            ('humidity', 70, 95, weather['humidity'], 0.15),
            ('avg_rainfall', 2000, 4000, climate['avg_rainfall'], 0.25),
            ('soil_type', 'loamy', None, soil['soil_type'], 0.1),
            ('elevation', 0, 700, soil['elevation'], 0.05)
        ],
        'soybean': [
            ('ph', 6.0, 7.5, soil['ph'], 0.15),
            ('N', 0.5, 1.5, soil['N'], 0.1),
            ('P', 30, 60, soil['P'], 0.15),
            ('K', 20, 50, soil['K'], 0.1),
            ('avg_temp', 20, 30, climate['avg_temp'], 0.2),
            ('humidity', 50, 80, weather['humidity'], 0.1),
            ('avg_rainfall', 600, 1200, climate['avg_rainfall'], 0.2),
            ('soil_type', 'loamy', None, soil['soil_type'], 0.1),
            ('elevation', 0, 1500, soil['elevation'], 0.05)
        ],
        'tapioca': [
            ('ph', 5.0, 7.0, soil['ph'], 0.15),
            ('N', 0.5, 1.5, soil['N'], 0.1),
            ('P', 20, 50, soil['P'], 0.1),
            ('K', 30, 70, soil['K'], 0.15),
            ('avg_temp', 20, 35, climate['avg_temp'], 0.2),
            ('humidity', 60, 90, weather['humidity'], 0.1),
            ('avg_rainfall', 1000, 2000, climate['avg_rainfall'], 0.2),
            ('soil_type', 'loamy', None, soil['soil_type'], 0.1),
            ('elevation', 0, 1000, soil['elevation'], 0.05)
        ],
        'turmeric': [
            ('ph', 5.5, 7.5, soil['ph'], 0.15),
            ('N', 0.8, 1.8, soil['N'], 0.15),
            ('P', 20, 50, soil['P'], 0.1),
            ('K', 30, 60, soil['K'], 0.1),
            ('avg_temp', 20, 35, climate['avg_temp'], 0.2),
            ('humidity', 60, 90, weather['humidity'], 0.1),
            ('avg_rainfall', 1000, 2000, climate['avg_rainfall'], 0.2),
            ('soil_type', 'loamy', None, soil['soil_type'], 0.1),
            ('elevation', 0, 1500, soil['elevation'], 0.05)
        ],
        'wheat': [
            ('ph', 6.0, 7.5, soil['ph'], 0.15),
            ('N', 0.8, 1.8, soil['N'], 0.15),
            ('P', 30, 60, soil['P'], 0.1),
            ('K', 20, 50, soil['K'], 0.1),
            ('avg_temp', 10, 25, climate['avg_temp'], 0.25),
            ('humidity', 50, 80, weather['humidity'], 0.1),
            ('avg_rainfall', 500, 1000, climate['avg_rainfall'], 0.2),
            ('soil_type', 'loamy', None, soil['soil_type'], 0.1),
            ('elevation', 0, 2000, soil['elevation'], 0.05)
        ]
    }

    def calculate_suitability(conditions, price, max_price):
        if not conditions:
            return 60.0
        score = 0
        total_weight = sum(weight for _, _, _, _, weight in conditions)
        for param, min_val, max_val, actual, weight in conditions:
            if param == "soil_type" and isinstance(min_val, str):
                score += (1 if actual == min_val else 0.6) * weight
            else:
                if actual is None:
                    score += 0.6 * weight
                elif actual < min_val:
                    normalized = max(0, 1 - (min_val - actual) / (max_val - min_val))
                elif actual > max_val:
                    normalized = max(0, 1 - (actual - max_val) / (max_val - min_val))
                else:
                    normalized = 1 - abs(actual - (min_val + max_val) / 2) / ((max_val - min_val) / 2)
                score += normalized * weight
        env_score = (score / total_weight) if total_weight > 0 else 0.6
        price_score = price / max_price if max_price > 0 else 1
        return round((0.7 * env_score + 0.3 * price_score) * 100, 1)

    # Combine ML and rule-based scores
    rule_scores = {}
    prices = {crop: get_price_data(crop, lat, lon) for crop in valid_crops}
    max_price = max(prices.values(), default=1000)
    
    for crop in valid_crops:
        suitability = calculate_suitability(crop_rules.get(crop, []), prices[crop], max_price)
        rule_scores[crop] = suitability

    for crop in valid_crops:
        ml_score = next((r["suitability"] for r in recommendations if r["crop"] == crop), 60.0)
        rule_score = rule_scores.get(crop, 60.0)
        # Blend scores: 60% ML, 40% rule-based if ML available, else 100% rule-based
        final_score = (0.6 * ml_score + 0.4 * rule_score) if crop in [r["crop"] for r in recommendations] else rule_score
        if final_score >= 35:
            recommendations.append({"crop": crop, "suitability": final_score})

    recommendations = [r for r in recommendations if r["suitability"] >= 35]
    recommendations.sort(key=lambda x: x["suitability"], reverse=True)
    return recommendations[:5] or [{"crop": "rice", "suitability": 60.0}]

def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance between two lat/lon points."""
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def get_nearest_market(lat, lon):
    """Map lat/lon to nearest market."""
    markets = {
        'Kochi': (9.9312, 76.2673),
        'Chennai': (13.0827, 80.2707),
        'Delhi': (28.7041, 77.1025),
        'Ludhiana': (30.9009, 75.8573)
    }
    return min(markets, key=lambda m: haversine(lat, lon, markets[m][0], markets[m][1]))

@csrf_exempt
@login_required
def get_price_prediction(request):
    """Predict crop price with improved accuracy."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            crop = data.get("crop")
            harvest_date = data.get("harvest_date")
            farm_id = data.get("farm_id")
            lat = float(data.get("latitude", 9.9312))  # Default to Kochi
            lon = float(data.get("longitude", 76.2673))
            if not crop or not harvest_date:
                return JsonResponse({"error": "Crop and harvest date required"}, status=400)

            # Validate crop
            valid_crops = {
                "coconut", "rice", "banana", "cardamom", "cotton", "gram", "groundnut",
                "maize", "mustard", "pepper", "rubber", "soybean", "tapioca", "turmeric", "wheat"
            }
            if crop not in valid_crops:
                logger.error(f"Invalid crop: {crop}")
                return JsonResponse({"error": f"Invalid crop: {crop}"}, status=400)

            # Get market
            market = get_nearest_market(lat, lon)
            crop_key = f"{crop}_{market}"
            logger.info(f"Predicting price for {crop_key} on {harvest_date}")

            # Load CSVs
            price_csv = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "price_predictions.csv")
            combined_csv = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "combined_data.csv")
            response = {"crop": crop, "date": harvest_date}

            # Initialize variables
            predicted_price = None
            historical_avg = None
            seasonal_factor = 1.0

            # 1. Try price_predictions.csv
            try:
                if not os.path.exists(price_csv):
                    logger.warning(f"Price CSV missing at {price_csv}")
                else:
                    df = pd.read_csv(price_csv)
                    df["date"] = pd.to_datetime(df["date"], errors='coerce')
                    target_date = pd.to_datetime(harvest_date, errors='coerce')
                    if target_date is pd.NaT:
                        raise ValueError("Invalid harvest date")

                    # Find closest prediction
                    prediction = df[(df["crop"] == crop_key) & (df["date"] <= target_date)].sort_values("date", ascending=False)
                    if not prediction.empty:
                        predicted_price = float(prediction.iloc[0]["predicted_price"])
                        logger.info(f"Found prediction: {predicted_price} for {crop_key}")
                    else:
                        logger.warning(f"No prediction for {crop_key} on or before {harvest_date}")
            except Exception as e:
                logger.error(f"Error reading price_predictions.csv: {e}")

            # 2. Use combined_data.csv for historical context
            try:
                if os.path.exists(combined_csv):
                    df = pd.read_csv(combined_csv)
                    df["date"] = pd.to_datetime(df["date"], errors='coerce')
                    if crop_key in df.columns:
                        # Historical average
                        historical_avg = df[crop_key].replace(0, pd.NA).mean()
                        if pd.isna(historical_avg):
                            logger.warning(f"No valid historical prices for {crop_key}")
                        else:
                            logger.info(f"Historical avg for {crop_key}: {historical_avg}")

                        # Seasonality: Adjust based on month
                        target_month = pd.to_datetime(harvest_date).month
                        monthly_avg = df[df["date"].dt.month == target_month][crop_key].replace(0, pd.NA).mean()
                        yearly_avg = df[crop_key].replace(0, pd.NA).mean()
                        if not pd.isna(monthly_avg) and not pd.isna(yearly_avg) and yearly_avg != 0:
                            seasonal_factor = monthly_avg / yearly_avg
                            seasonal_factor = min(max(seasonal_factor, 0.8), 1.2)  # Cap at ±20%
                            logger.info(f"Seasonal factor for {crop_key}, month {target_month}: {seasonal_factor}")
                    else:
                        logger.warning(f"Crop {crop_key} not in combined_data.csv")
            except Exception as e:
                logger.error(f"Error reading combined_data.csv: {e}")

            # 3. Compute final price
            # Crop volatility (high for spices, low for staples)
            volatility = {
                "cardamom": 0.3, "pepper": 0.25, "turmeric": 0.2, "rubber": 0.2,
                "coconut": 0.15, "banana": 0.15, "rice": 0.1, "wheat": 0.1,
                "maize": 0.1, "soybean": 0.1, "cotton": 0.1, "gram": 0.1,
                "groundnut": 0.1, "mustard": 0.1, "tapioca": 0.1
            }

            if predicted_price is not None:
                # Blend prediction with historical data if available
                if historical_avg is not None:
                    weight_pred = 0.7 if target_date.year <= 2025 else 0.5  # Trust predictions less for future
                    final_price = (weight_pred * predicted_price + (1 - weight_pred) * historical_avg) * seasonal_factor
                else:
                    final_price = predicted_price * seasonal_factor
            elif historical_avg is not None:
                # Use historical with volatility adjustment
                final_price = historical_avg * seasonal_factor * (1 + volatility.get(crop, 0.1))
            else:
                # Fallback: Dynamic based on crop type
                fallback_prices = {
                    "coconut": 3000.0, "rice": 2000.0, "banana": 2200.0, "cardamom": 80000.0,
                    "cotton": 5500.0, "gram": 4000.0, "groundnut": 3500.0, "maize": 2100.0,
                    "mustard": 3700.0, "pepper": 45000.0, "rubber": 14000.0, "soybean": 3300.0,
                    "tapioca": 1700.0, "turmeric": 6500.0, "wheat": 2200.0
                }
                final_price = fallback_prices.get(crop, 1000.0) * seasonal_factor
                response["warning"] = "Using fallback price due to missing data"

            # Adjust for market-specific trends (e.g., Kochi vs. Delhi)
            market_adjust = {
                "Kochi": 1.1, "Chennai": 1.05, "Delhi": 0.95, "Ludhiana": 0.9
            }
            final_price *= market_adjust.get(market, 1.0)

            response["predicted_price"] = round(final_price, 2)
            response["market"] = market

            # 4. Add farm-specific calculations
            if farm_id:
                try:
                    farm = Farm.objects.get(id=farm_id, farmer=request.user)
                    response.update({
                        "total_yield": float(farm.area * farm.yield_per_acre),
                        "estimated_revenue": float(farm.area * farm.yield_per_acre * final_price)
                    })
                except Farm.DoesNotExist:
                    response["warning"] = response.get("warning", "") + " Farm not found"

            # 5. Add market status (oversupply and low demand)
            market_status = calculate_market_status(crop, market, harvest_date, combined_csv)
            response.update({
                "oversupply_status": market_status["oversupply_status"],
                "low_demand_status": market_status["low_demand_status"]
            })
            if market_status["oversupply_status"]:
                response["warning"] = response.get("warning", "") + f" High oversupply risk for {crop} in {market}"

            logger.info(f"Final price for {crop_key}: {response['predicted_price']}")
            return JsonResponse(response, status=200)

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid data in get_price_prediction: {e}")
            return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"error": "Invalid method"}, status=405)