from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import Farm
from .crop_ai import recommend_crop
import json

def farm_map(request):
    """Render the farm map."""
    return render(request, "maps/map.html")


@csrf_exempt
@login_required
def save_location(request):
    """Receives farm location from frontend and saves it in the database."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            latitude = float(data.get("latitude", 0))
            longitude = float(data.get("longitude", 0))

            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                return JsonResponse({"error": "Invalid latitude or longitude"}, status=400)

            Farm.objects.create(
                farmer=request.user,
                latitude=latitude,
                longitude=longitude,
                soil_type="loamy",  # Default, can be updated later
                climate="hot",  # Default, can be updated later
                oversupply_risk=False  # Default, can be updated later
            )

            return JsonResponse({"message": "Farm location saved successfully"}, status=201)

        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "Invalid JSON data"}, status=400)

    return JsonResponse({"error": "Invalid request method"}, status=405)

@login_required
def edit_location(request, farm_id):
    """Edit farm location manually through a form."""
    farm = get_object_or_404(Farm, id=farm_id, farmer=request.user)

    if request.method == "POST":
        try:
            latitude = float(request.POST.get("latitude"))
            longitude = float(request.POST.get("longitude"))

            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                return JsonResponse({"error": "Invalid latitude or longitude"}, status=400)

            farm.latitude = latitude
            farm.longitude = longitude
            farm.save()
            return redirect("farm-map")

        except ValueError:
            return JsonResponse({"error": "Invalid input data"}, status=400)

    return render(request, "maps/edit_location.html", {"farm": farm})


@login_required
def get_farm_data(request):
    """Returns farm locations and recommended crops as JSON."""
    farms = Farm.objects.all()
    farm_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [farm.longitude, farm.latitude]},
                "properties": {
                    "name": f"Farm {farm.id}",
                    "status": "green",  # You can modify this logic
                    "recommended_crop": farm.recommended_crop,
                },
            }
            for farm in farms
        ],
    }
    return JsonResponse(farm_data)
