from django.shortcuts import render
from .ml_model import recommend_crop_ml
from maps.models import Farm
from django.contrib.auth.decorators import login_required
import math

# Haversine function to calculate distance between two GPS points
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# Crop Recommendation View
@login_required
def recommend_crop_view(request):
    context = {}

    if request.method == 'POST':
        preferred_crop = request.POST.get('preferred_crop')

        # Step 1: Get current user's farm
        farm = Farm.objects.filter(farmer=request.user).last()
        if not farm:
            context['error'] = "Your farm data is missing. Please mark your farm on the map first."
            return render(request, 'crop_ai/recommend_form.html', context)

        # Step 2: Get all nearby farms within 10 km
        nearby_farms = []
        for other_farm in Farm.objects.exclude(farmer=request.user):
            distance = haversine(farm.latitude, farm.longitude, other_farm.latitude, other_farm.longitude)
            if distance <= 10:
                nearby_farms.append(other_farm)

        # Step 3: Analyze area and nearby crop
        if nearby_farms:
            avg_area = sum(f.area for f in nearby_farms) / len(nearby_farms)
            crop_list = [f.recommended_crop for f in nearby_farms if f.recommended_crop]
            nearby_crop = max(set(crop_list), key=crop_list.count) if crop_list else "wheat"
        else:
            avg_area = farm.area  # fallback to user’s own area
            nearby_crop = "wheat"  # default crop

        # Step 4: Run recommendation model
        recommended = recommend_crop_ml(
            area=avg_area,
            climate=farm.climate,
            soil_type=farm.soil_type,
            nearby_crop=nearby_crop,
            preferred_crop=preferred_crop
        )

        # Step 5: Update farm and context
        farm.recommended_crop = recommended
        farm.save()

        context.update({
            'recommended': recommended,
            'submitted': True,
            'avg_area_used': avg_area,
            'nearby_crop_used': nearby_crop
        })

    return render(request, 'crop_ai/recommend_form.html', context)
