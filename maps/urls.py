from django.urls import path
from .views import farm_map, save_location, get_farm_data, add_farm, get_farm_by_coords, get_location_details
from . import views
urlpatterns = [
    path('farm-map/', farm_map, name='farm-map'),
    path('save-location/', save_location, name='save_location'),
   # path('edit-location/<int:farm_id>/', edit_location, name='edit_location'),  # This line causes the error
    path('farm-data/', get_farm_data, name='get_farm_data'),
    path('add-farm/', add_farm, name='add_farm'),
    path('get-farm-by-coords/', get_farm_by_coords, name='get_farm_by_coords'),
    path('get-location-details/', get_location_details, name='get_location_details'),
    path('my-farms/', views.my_farms, name='my_farms'),  # New My Farms page
    path('delete-farm/<int:farm_id>/', views.delete_farm, name='delete_farm'),
    path('maps/get-price-prediction/', views.get_price_prediction, name='get-price-prediction'),  # New
]