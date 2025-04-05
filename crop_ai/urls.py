from django.urls import path
from .views import recommend_crop_view

urlpatterns = [
    path('recommend/', recommend_crop_view, name='recommend-crop'),
]
