# urls.py in users app
from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    # Change this to match the name used in templates
    path('switch-language/<str:language>/', views.switch_language, name='set_language'),
]