from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import CitaMedicaViewSet


router = DefaultRouter()
router.register('citas', CitaMedicaViewSet, basename='cita-medica')

urlpatterns = [
    path('', include(router.urls)),
]