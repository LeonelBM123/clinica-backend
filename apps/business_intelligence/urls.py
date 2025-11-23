from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AnalyticsViewSet

# Creamos el router
router = DefaultRouter()

# Registramos el ViewSet
# 'analytics' será el prefijo base de la URL
router.register('analytics', AnalyticsViewSet, basename='analytics')

urlpatterns = [
    # Esto genera automáticamente las URLs:
    # /analytics/run-etl/ (POST)
    # /analytics/dashboard/ (GET)
    path('', include(router.urls)),
]