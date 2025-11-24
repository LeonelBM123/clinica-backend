from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated,AllowAny
from .models import Plan, Suscripcion
from .serializers import PlanSerializer, SuscripcionSerializer
from apps.cuentas.models import Usuario
from django.utils import timezone
from datetime import timedelta

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
    
    def create(self, request, *args, **kwargs):
        try:
            usuario = Usuario.objects.get(correo=request.user.email)
            grupo = usuario.grupo
            if not grupo:
                return Response({"detail": "El usuario no pertenece a ninguna clínica."}, status=400)
        except Usuario.DoesNotExist:
            return Response({"detail": "Usuario no encontrado."}, status=400)

        suscripcion_existente = Suscripcion.objects.filter(grupo=grupo).first()

        if suscripcion_existente:
            serializer = self.get_serializer(suscripcion_existente, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            
            self.perform_update(serializer)
            
            suscripcion_existente.fecha_inicio = timezone.now()
            suscripcion_existente.fecha_fin = timezone.now() + timedelta(days=30)
            suscripcion_existente.estado = 'ACTIVA'
            suscripcion_existente.save()

            return Response(serializer.data)
        
        else:
            return super().create(request, *args, **kwargs)


    def perform_create(self, serializer):
        
        usuario = Usuario.objects.get(correo=self.request.user.email)
        if usuario.grupo:
            serializer.save(
                grupo=usuario.grupo,
                estado='ACTIVA',  
                fecha_inicio=timezone.now(),
                fecha_fin=timezone.now() + timedelta(days=30)
            )
    @action(detail=False, methods=['get'])
    def mi_suscripcion(self, request):
        qs = self.get_queryset().first()
        if qs:
            serializer = self.get_serializer(qs)
            return Response(serializer.data)
        return Response({"mensaje": "No tienes una suscripción activa"}, status=404)