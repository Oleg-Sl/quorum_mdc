from django.contrib import admin
from django.urls import path, include
from django.conf import settings

urlpatterns = [
    path(f'{settings.URL_PATH}/admin/', admin.site.urls),
    path(f'{settings.URL_PATH}/api/v1/', include('api_v1.urls', namespace='api_v1')),
    path(f'{settings.URL_PATH}/auth/', include('djoser.urls')),
    path(f'{settings.URL_PATH}/auth/', include('djoser.urls.jwt')),
]

