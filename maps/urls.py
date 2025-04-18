from django.urls import path
from . import views

app_name = "maps"

urlpatterns = [
    path("farm-map/", views.farm_map, name="farm-map"),
    path("save-location/", views.save_location, name="save-location"),
    path("get-location-details/", views.get_location_details, name="get-location-details"),
    path("get-farm-by-coords/", views.get_farm_by_coords, name="get-farm-by-coords"),
    path("add-farm/", views.add_farm, name="add-farm"),
    path("get-farm-data/", views.get_farm_data, name="get-farm-data"),
    path("delete-farm/<int:farm_id>/", views.delete_farm, name="delete-farm"),
    path("my-farms/", views.my_farms, name="my-farms"),
    path("get-price-prediction/", views.get_price_prediction, name="get-price-prediction"),
    # path("test-logging/", views.test_logging, name="test-logging"),
]