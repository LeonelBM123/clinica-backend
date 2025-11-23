from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated,AllowAny
from .models import Plan, Suscripcion
from .serializers import PlanSerializer, SuscripcionSerializer
from apps.cuentas.models import Usuario

class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = [AllowAny]

class SuscripcionViewSet(viewsets.ModelViewSet):
   
    serializer_class = SuscripcionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            usuario = Usuario.objects.get(correo=self.request.user.email)
            if usuario.grupo:
                return Suscripcion.objects.filter(grupo=usuario.grupo)
        except Usuario.DoesNotExist:
            pass
        return Suscripcion.objects.none()

    def perform_create(self, serializer):
        usuario = Usuario.objects.get(correo=self.request.user.email)
        if usuario.grupo:
            serializer.save(grupo=usuario.grupo)
        else:
            pass

    @action(detail=False, methods=['get'])
    def mi_suscripcion(self, request):
        qs = self.get_queryset().first()
        if qs:
            serializer = self.get_serializer(qs)
            return Response(serializer.data)
        return Response({"mensaje": "No tienes una suscripción activa"}, status=404)