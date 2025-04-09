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

# Configure logging
logger = logging.getLogger(__name__)

# Load ML model globally
try:
    crop_model = joblib.load("maps/crop_recommendation_model.pkl")
    logger.info("ML model loaded successfully")
except Exception as e:
    logger.error(f"Error loading model: {e}")
    crop_model = None  # Fallback to default crop if model fails

def get_weather_data(lat, lon):
    """Fetch weather data from Open-Meteo (free, no API key)."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,precipitation&forecast_days=1"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()["hourly"]
        return {
            "temperature": data["temperature_2m"][0],  # °C
            "humidity": data["relative_humidity_2m"][0],  # %
            "rainfall": data["precipitation"][0],  # mm
        }
    except requests.RequestException as e:
        logger.error(f"Error fetching weather: {e}")
        return {"temperature": 25, "humidity": 70, "rainfall": 0}  # Fallback

def get_soil_data(lat, lon):
    """Fetch soil data from SoilGrids (free, no API key)."""
    url = f"https://rest.isric.org/soilgrids/v2.0/properties/query?lat={lat}&lon={lon}&property=nitrogen&property=phh2o&depth=0-5cm&value=mean"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()["properties"]["layers"]
        
        # Extract values for nitrogen and pH from the correct depth
        nitrogen = 80  # Default
        ph = 65  # Default
        for layer in data:
            if layer["name"] == "nitrogen":
                for depth in layer["depths"]:
                    if depth["depth"] == "0-5cm":
                        nitrogen = depth["values"]["mean"]
            elif layer["name"] == "phh2o":
                for depth in layer["depths"]:
                    if depth["depth"] == "0-5cm":
                        ph = depth["values"]["mean"]

        return {
            "N": nitrogen / 100,  # Convert from cg/kg to kg/ha
            "P": 40,  # Placeholder (SoilGrids lacks P)
            "K": 50,  # Placeholder (SoilGrids lacks K)
            "ph": ph / 10,  # Convert from pH*10 to pH
            "soil_type": "loamy"  # Simplified
        }
    except requests.RequestException as e:
        logger.error(f"Error fetching soil: {e}")
        return {"N": 80, "P": 40, "K": 50, "ph": 6.5, "soil_type": "loamy"}  # Fallback
    except (KeyError, TypeError) as e:
        logger.error(f"Error parsing soil data: {e}")
        return {"N": 80, "P": 40, "K": 50, "ph": 6.5, "soil_type": "loamy"}  # Fallback
    

    
def get_climate_data(lat, lon):
    """Fetch climate averages from Open-Meteo (past 30 days as proxy)."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_mean,precipitation_sum&past_days=30"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()["daily"]
        temp_avg = sum(data["temperature_2m_mean"]) / len(data["temperature_2m_mean"])
        rainfall_avg = sum(data["precipitation_sum"]) / 30 * 365  # Annual estimate in mm
        return {"avg_temp": temp_avg, "avg_rainfall": rainfall_avg}
    except requests.RequestException as e:
        logger.error(f"Error fetching climate: {e}")
        return {"avg_temp": 24, "avg_rainfall": 1200}  # Fallback

def farm_map(request):
    """Render the farm map."""
    return render(request, "maps/map.html")  # Updated to match your template name

@csrf_exempt
@login_required
def save_location(request):
    """Save a farm location without detailed data."""
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
    """Fetch detailed location data for a given lat/lon."""
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

            recommended_crop = "wheat"
            if crop_model:
                try:
                    features = [soil["N"], soil["P"], soil["K"], weather["temperature"], weather["humidity"], soil["ph"], climate["avg_rainfall"]]
                    recommended_crop = crop_model.predict([features])[0]
                    valid_crops = [choice[0] for choice in Farm.CROP_CHOICES]
                    if recommended_crop not in valid_crops:
                        logger.warning(f"Predicted crop {recommended_crop} not in valid crops, defaulting to wheat")
                        recommended_crop = "wheat"
                except Exception as e:
                    logger.error(f"Error predicting crop: {e}")
                    recommended_crop = "wheat"

            response = {
                "weather": weather,
                "soil": soil,
                "climate": climate,
                "recommended_crop": recommended_crop,
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
    """Add a farm with detailed data."""
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
        recommended_crop = "wheat"
        if crop_model:
            try:
                features = [soil["N"], soil["P"], soil["K"], weather["temperature"], weather["humidity"], soil["ph"], climate["avg_rainfall"]]
                recommended_crop = crop_model.predict([features])[0]
                valid_crops = [choice[0] for choice in Farm.CROP_CHOICES]
                if recommended_crop not in valid_crops:
                    recommended_crop = "wheat"
            except Exception as e:
                logger.error(f"Error predicting crop: {e}")
                recommended_crop = "wheat"

        farm = Farm(
            farmer=request.user,
            area=farm_size,
            latitude=lat,
            longitude=lon,
            status=data.get("farmStatus", "green"),
            soil_type=soil["soil_type"],
            climate=data.get("climate", "hot"),
            recommended_crop=recommended_crop,
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
            "recommended_crop": recommended_crop,
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
    """Return all farm data as GeoJSON."""
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
    """Check if a farm exists at given coordinates."""
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
            return JsonResponse({}, status=404)  # Frontend expects 404 for no farm
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid data: {e}")
            return JsonResponse({"error": f"Invalid data: {str(e)}"}, status=400)
    return JsonResponse({"error": "Invalid request method"}, status=405)