from django.shortcuts import render
from .ml_model import recommend_crop_ml

def recommend_crop_view(request):
    context = {}
    if request.method == 'POST':
        area = float(request.POST.get('area'))
        climate = request.POST.get('climate')
        soil_type = request.POST.get('soil_type')
        nearby_crop = request.POST.get('nearby_crop')
        preferred_crop = request.POST.get('preferred_crop')
        print()

        recommended = recommend_crop_ml(area, climate, soil_type, nearby_crop, preferred_crop)
        context['recommended'] = recommended
        context['submitted'] = True

    return render(request, 'crop_ai/recommend_form.html', context)
