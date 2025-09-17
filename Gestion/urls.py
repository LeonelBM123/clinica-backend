from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'usuarios', views.UsuarioViewSet)
router.register(r'roles', views.RolViewSet)
router.register(r'medicos', views.MedicoViewSet)
router.register(r'especialidades', views.EspecialidadViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
]