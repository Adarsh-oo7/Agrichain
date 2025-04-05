from django.contrib import admin
from django.urls import path, include
from users.views import home
from django.conf.urls.i18n import i18n_patterns

# URL patterns without language prefix
urlpatterns = [
    path('admin/', admin.site.urls),
    path("maps/",include('maps.urls')),
    path('crop-ai/', include('crop_ai.urls')),


    path('i18n/', include('django.conf.urls.i18n')),  # Built-in language switching
]

# URL patterns with language prefix
urlpatterns += i18n_patterns(
    path('', home, name="home"),  # Home page with language prefix
    path('users/', include('users.urls')),  # Include users URLs with language prefix
    prefix_default_language=False,  # No prefix for the default language
)