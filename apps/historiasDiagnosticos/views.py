from django.shortcuts import render
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import *
from .serializers import *
from apps.cuentas.models import Usuario
from apps.cuentas.utils import get_actor_usuario_from_request, log_action

class MultiTenantMixin:
    """Mixin para filtrar datos por grupo del usuario actual"""
    
    permission_classes = [permissions.IsAuthenticated]  # Requiere autenticación
    
    def get_user_grupo(self):
        """Obtiene el grupo del usuario actual"""
        if hasattr(self.request, 'user') and self.request.user.is_authenticated:
            try:
                usuario = Usuario.objects.get(correo=self.request.user.email)
                return usuario.grupo
            except Usuario.DoesNotExist:
                pass
        return None
    
    def is_super_admin(self):
        """Verifica si el usuario actual es super admin"""
        if hasattr(self.request, 'user') and self.request.user.is_authenticated:
            try:
                usuario = Usuario.objects.get(correo=self.request.user.email)
                return usuario.rol and usuario.rol.nombre == 'superAdmin'
            except Usuario.DoesNotExist:
                pass
        return False
    
    def filter_by_grupo(self, queryset):
        """Filtra el queryset por el grupo del usuario actual"""
        if self.is_super_admin():
            return queryset  # Super admin ve todo
        
        grupo = self.get_user_grupo()
        if grupo and hasattr(queryset.model, 'grupo'):
            return queryset.filter(grupo=grupo)
        
        return queryset


class PatologiasOViewSet(MultiTenantMixin, viewsets.ModelViewSet):
    queryset = PatologiasO.objects.all() 
    serializer_class = PatologiasOSerializer

    def get_queryset(self):
        queryset = PatologiasO.objects.all()
        # Filtrar por grupo del usuario
        queryset = self.filter_by_grupo(queryset)
        
        # Por defecto, solo activos
        if self.action == 'list':
            return queryset.filter(estado=True)
        return queryset

    def perform_create(self, serializer):
        # Asignar automáticamente el grupo del usuario que crea
        usuario = Usuario.objects.get(correo=self.request.user.email)
        patologia = serializer.save(grupo=usuario.grupo)
        
        # Log de la acción
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Creó la patología {patologia.nombre} (id:{patologia.id})",
            objeto=f"Patología: {patologia.nombre} (id:{patologia.id})",
            usuario=actor
        )

    def perform_update(self, serializer):
        patologia = serializer.save()
        
        # Log de la acción
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Actualizó la patología {patologia.nombre} (id:{patologia.id})",
            objeto=f"Patología: {patologia.nombre} (id:{patologia.id})",
            usuario=actor
        )

    def perform_destroy(self, instance):
        # Soft delete: solo cambia estado a False y actualiza fecha_modificacion
        nombre = instance.nombre
        pk = instance.pk
        instance.estado = False
        instance.save()
        
        # Log de la acción
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Eliminó (soft delete) la patología {nombre} (id:{pk})",
            objeto=f"Patología: {nombre} (id:{pk})",
            usuario=actor
        )
    
    @action(detail=False, methods=['get'])
    def eliminadas(self, request):
        queryset = PatologiasO.objects.all()
        queryset = self.filter_by_grupo(queryset)  # Filtrar por grupo
        eliminadas = queryset.filter(estado=False)
        serializer = self.get_serializer(eliminadas, many=True)
        return Response(serializer.data)    
    
    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        patologia = self.get_object()
        patologia.estado = True
        patologia.save()
        
        # Log de la acción
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Restauró la patología {patologia.nombre} (id:{patologia.id})",
            objeto=f"Patología: {patologia.nombre} (id:{patologia.id})",
            usuario=actor
        )
        
        serializer = self.get_serializer(patologia)
        return Response(serializer.data, status=status.HTTP_200_OK)

class TratamientoMedicacionViewSet(MultiTenantMixin, viewsets.ModelViewSet):
    queryset = TratamientoMedicacion.objects.all() 
    serializer_class = TratamientoMedicacionSerializer

    def get_queryset(self):
        queryset = TratamientoMedicacion.objects.all()
        # Filtrar por grupo del usuario
        queryset = self.filter_by_grupo(queryset)
        return queryset

    def perform_create(self, serializer):
        # Asignar automáticamente el grupo del usuario que crea
        usuario = Usuario.objects.get(correo=self.request.user.email)
        tratamiento = serializer.save(grupo=usuario.grupo)
        
        # Log de la acción
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Creó el tratamiento {tratamiento.nombre} (id:{tratamiento.id})",
            objeto=f"Tratamiento: {tratamiento.nombre} (id:{tratamiento.id})",
            usuario=actor
        )

    def perform_update(self, serializer):
        tratamiento = serializer.save()
        
        # Log de la acción
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Actualizó el tratamiento {tratamiento.nombre} (id:{tratamiento.id})",
            objeto=f"Tratamiento: {tratamiento.nombre} (id:{tratamiento.id})",
            usuario=actor
        )

    def perform_destroy(self, instance):
        # Soft delete: solo cambia estado a False y actualiza fecha_modificacion
        nombre = instance.nombre
        pk = instance.pk
        instance.delete()
        
        # Log de la acción
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Eliminó (soft delete) el tratamiento {nombre} (id:{pk})",
            objeto=f"Tratamiento: {nombre} (id:{pk})",
            usuario=actor
        )


class PacienteViewSet(MultiTenantMixin, viewsets.ModelViewSet):
    queryset = Paciente.objects.all() 
    serializer_class = PacienteSerializer

    def get_queryset(self):
        queryset = Paciente.objects.all()
        # Filtrar por grupo a través del usuario
        if not self.is_super_admin():
            grupo = self.get_user_grupo()
            if grupo:
                queryset = queryset.filter(usuario__grupo=grupo)
        return queryset

    def perform_destroy(self, instance):
        # Soft delete: cambia estado del usuario a False
        nombre = instance.usuario.nombre
        pk = instance.pk
        instance.usuario.estado = False
        instance.usuario.save()
        
        # Log de la acción
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Eliminó (soft delete) el paciente {nombre} (id:{pk})",
            objeto=f"Paciente: {nombre} (id:{pk})",
            usuario=actor
        )
    
    @action(detail=False, methods=['get'])
    def eliminadas(self, request):
        queryset = Paciente.objects.all()
        # Filtrar por grupo a través del usuario
        if not self.is_super_admin():
            grupo = self.get_user_grupo()
            if grupo:
                queryset = queryset.filter(usuario__grupo=grupo)
        
        eliminadas = queryset.filter(usuario__estado=False)
        serializer = self.get_serializer(eliminadas, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        paciente = self.get_object()
        paciente.usuario.estado = True
        paciente.usuario.save()
        
        # Log de la acción
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Restauró el paciente {paciente.usuario.nombre} (id:{paciente.id})",
            objeto=f"Paciente: {paciente.usuario.nombre} (id:{paciente.id})",
            usuario=actor
        )
        
        serializer = self.get_serializer(paciente)
        return Response(serializer.data, status=status.HTTP_200_OK)

