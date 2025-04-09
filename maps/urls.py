from django.urls import path
from .views import farm_map, save_location, get_farm_data, add_farm, get_farm_by_coords, get_location_details

urlpatterns = [
    path('farm-map/', farm_map, name='farm-map'),
    path('save-location/', save_location, name='save_location'),
   # path('edit-location/<int:farm_id>/', edit_location, name='edit_location'),  # This line causes the error
    path('farm-data/', get_farm_data, name='get_farm_data'),
    path('add-farm/', add_farm, name='add_farm'),
    path('get-farm-by-coords/', get_farm_by_coords, name='get_farm_by_coords'),
    path('get-location-details/', get_location_details, name='get_location_details'),
]