from django.urls import path
from . import views

urlpatterns = [
    path('blog/', views.farming_news, name='farming_news'),
]