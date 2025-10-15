from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import CitaMedicaViewSet, PacientesPorGrupoView, CitasPorPacienteView, CitaDetalleView


router = DefaultRouter()
router.register('citas', CitaMedicaViewSet, basename='cita-medica')

urlpatterns = [
    path('', include(router.urls)),
    path('pacientes/', PacientesPorGrupoView.as_view(), name='pacientes-por-grupo'),
    path('pacientes/<int:paciente_id>/citas/', CitasPorPacienteView.as_view(), name='citas-por-paciente'),
    path('citas/<int:cita_id>/detalle/', CitaDetalleView.as_view(), name='detalle-cita'),
]