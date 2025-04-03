from django.urls import path
from .views import farm_map, save_location, edit_location, get_farm_data  # Removed mark_location

urlpatterns = [
    path('farm-map/', farm_map, name='farm-map'),
    path('save-location/', save_location, name='save-location'),
    path('edit-location/<int:farm_id>/', edit_location, name='edit-location'),
    path('farm-data/', get_farm_data, name='farm-data'),
]
