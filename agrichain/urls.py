from django.contrib import admin
from django.urls import path, include
from users.views import home
from django.conf.urls.i18n import i18n_patterns

# Non-prefixed URLs
urlpatterns = [
    path('admin/', admin.site.urls),
    path('maps/', include('maps.urls')),
    path('crop-ai/', include('crop_ai.urls')),
    path('blog/', include('add_on.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
]

# Prefixed URLs with language support
urlpatterns += i18n_patterns(
    path('', home, name='home'),
    path('users/', include('users.urls')),
    prefix_default_language=False,
)