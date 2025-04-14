# maps/urls.py
from django.urls import path
from . import views

app_name = 'maps'

urlpatterns = [
    path('farm-map/', views.farm_map, name='farm-map'),
    path('save-location/', views.save_location, name='save_location'),
    path('farm-data/', views.get_farm_data, name='get_farm_data'),
    path('add-farm/', views.add_farm, name='add_farm'),
    path('get-farm-by-coords/', views.get_farm_by_coords, name='get_farm_by_coords'),
    path('get-location-details/', views.get_location_details, name='get_location_details'),
    path('my-farms/', views.my_farms, name='my_farms'),
    path('delete-farm/<int:farm_id>/', views.delete_farm, name='delete_farm'),
    path('maps/get-price-prediction/', views.get_price_prediction, name='get_price_prediction'),
    path('test-logging/', views.test_logging, name='test_logging'),
]