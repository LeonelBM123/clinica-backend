from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AvisoViewSet, test_notificacion, health_check

router = DefaultRouter()
router.register(r'avisos', AvisoViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/test-notification/', test_notificacion, name='test-notification'),
    path('health/', health_check, name='health-check'),
]
