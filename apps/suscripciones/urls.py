from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PlanViewSet, SuscripcionViewSet

router = DefaultRouter()
router.register(r'planes', PlanViewSet, basename='planes')
router.register(r'suscripciones', SuscripcionViewSet, basename='suscripciones')

urlpatterns = [
    path('', include(router.urls)),
]