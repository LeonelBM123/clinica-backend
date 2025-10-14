from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views


router = DefaultRouter()
router.register(r'medicos', views.MedicoViewSet)
router.register(r'especialidades', views.EspecialidadViewSet)
router.register(r'tipos-atencion', views.TipoAtencionViewSet)
router.register(r'bloques-horarios', views.BloqueHorarioViewSet, basename='bloque-horario')

urlpatterns = [
    path('', include(router.urls)),
]