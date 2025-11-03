from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'patologias', views.PatologiasOViewSet)
router.register(r'tratamientos', views.TratamientoMedicacionViewSet)
router.register(r'pacientes', views.PacienteViewSet)
router.register(r'resultados-examenes', views.ResultadoExamenesViewSet)
urlpatterns = [
    path("pacientes/<int:paciente_id>/historia", views.PatientHistoryView.as_view(), name="paciente-historia"),
]
urlpatterns = router.urls