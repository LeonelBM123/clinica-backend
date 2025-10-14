from datetime import datetime, timedelta
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from apps.cuentas.utils import get_actor_usuario_from_request, log_action
from apps.cuentas.models import Usuario, Grupo
from apps.doctores.models import Medico
from rest_framework.response import Response
from rest_framework import generics
from rest_framework import permissions
from .models import *
from .serializers import *
from django.db.models import Q

class MultiTenantMixin:
    """Mixin para filtrar datos por grupo del usuario actual"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get_user_grupo(self):
        """Obtiene el grupo del usuario actual"""
        if hasattr(self.request, 'user') and self.request.user.is_authenticated:
            try:
                usuario = Usuario.objects.get(correo=self.request.user.email)
                return usuario.grupo
            except Usuario.DoesNotExist:
                pass
        return None
    
    def get_user_medico(self):
        """Obtiene el médico asociado al usuario actual"""
        if hasattr(self.request, 'user') and self.request.user.is_authenticated:
            try:
                # Buscar médico por email
                medico = Medico.objects.get(correo=self.request.user.email)
                return medico
            except Medico.DoesNotExist:
                pass
        return None
    
    def is_super_admin(self):
        """Verifica si el usuario actual es super admin"""
        grupo = self.get_user_grupo()
        # Aquí tu lógica para super admin...
        return False
    
    def filter_by_grupo(self, queryset):
        """Filtra el queryset por el grupo del usuario actual"""
        grupo = self.get_user_grupo()
        if grupo:
            model = queryset.model
            has_grupo_field = any(
                hasattr(field, 'name') and field.name == 'grupo' 
                for field in model._meta.get_fields()
            )
            
            if has_grupo_field:
               
                return queryset.filter(grupo=grupo)
        
      
        return queryset

class CitaMedicaViewSet(MultiTenantMixin, viewsets.ModelViewSet):
    """
    Gestiona el CRUD completo y las acciones personalizadas para las Citas Médicas.
    """
    # Usamos select_related para optimizar las consultas a la base de datos
    queryset = Cita_Medica.objects.all().select_related('paciente', 'bloque_horario__medico', 'grupo')
    serializer_class = CitaMedicaSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Filtra las citas de forma inteligente según el rol del usuario:
        - Si es Médico, solo ve sus propias citas.
        - Si es otro rol (Admin/Recepcionista), ve todas las citas de su grupo.
        """
        # Obtenemos el queryset base ya optimizado
        queryset = super().get_queryset()
        
        # Filtramos por el grupo del usuario (lógica del MultiTenantMixin)
        queryset = self.filter_by_grupo(queryset)
        
        # Si el usuario es un médico, aplicamos un filtro adicional
        medico = self.get_user_medico()
        if medico:
            queryset = queryset.filter(bloque_horario__medico=medico)
        
        return queryset.order_by('-fecha', '-hora_inicio')

    def perform_create(self, serializer):
        """
        Asigna datos automáticos (hora_fin, grupo) al crear una cita y registra el log.
        """
        bloque = serializer.validated_data.get('bloque_horario')
        hora_inicio = serializer.validated_data.get('hora_inicio')

        # Cálculo automático de la hora de fin
        hora_inicio_dt = datetime.combine(datetime.today(), hora_inicio)
        duracion = timedelta(minutes=bloque.duracion_cita_minutos)
        hora_fin = (hora_inicio_dt + duracion).time()
        
        # Guardamos la cita asignando los datos calculados y el grupo del bloque
        cita = serializer.save(grupo=bloque.grupo, hora_fin=hora_fin)
        
        # --- Log de Acción ---
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Creó cita para {cita.paciente.nombre} el {cita.fecha} a las {cita.hora_inicio.strftime('%H:%M')}",
            objeto=f"Cita ID: {cita.id}",
            usuario=actor
        )

    def perform_update(self, serializer):
        """
        Registra el log al actualizar una cita.
        """
        cita_actualizada = serializer.save()
        
        # --- Log de Acción ---
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Actualizó la cita ID: {cita_actualizada.id} para el paciente {cita_actualizada.paciente.nombre}",
            objeto=f"Cita ID: {cita_actualizada.id}",
            usuario=actor
        )

    def perform_destroy(self, instance):
        """
        Realiza un "soft delete" (desactivación) de la cita y registra el log.
        """
        cita_info = f"ID: {instance.id} - Paciente: {instance.paciente.nombre}"
        
        instance.estado = False
        # Es buena práctica cambiar el estado a 'CANCELADA' al eliminar lógicamente
        if instance.estado_cita not in ['COMPLETADA', 'CANCELADA']:
            instance.estado_cita = 'CANCELADA'
            instance.motivo_cancelacion = "Cancelada por personal administrativo."
        instance.save()
        
        # --- Log de Acción ---
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Canceló (soft delete) la cita: {cita_info}",
            objeto=f"Cita ID: {instance.id}",
            usuario=actor
        )

    # --- ACCIONES PERSONALIZADAS ---

    @action(detail=True, methods=['post'], url_path='cambiar-estado')
    def cambiar_estado(self, request, pk=None):
        """
        Permite cambiar el estado de una cita específica (ej: PENDIENTE -> CONFIRMADA).
        """
        cita = self.get_object()
        nuevo_estado = request.data.get('estado_cita')
        
        if not nuevo_estado or nuevo_estado not in dict(Cita_Medica.ESTADOS_CITA):
            return Response({"error": "Debe proporcionar un estado válido."}, status=status.HTTP_400_BAD_REQUEST)
        
        estado_anterior = cita.estado_cita
        cita.estado_cita = nuevo_estado
        
        if nuevo_estado == 'CANCELADA':
            cita.motivo_cancelacion = request.data.get('motivo_cancelacion', 'Sin motivo especificado.')
            
        cita.save()

        # --- Log de Acción ---
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Cambió estado de cita ID {cita.id} de '{estado_anterior}' a '{nuevo_estado}'",
            objeto=f"Cita ID: {cita.id}",
            usuario=actor
        )
        
        serializer = self.get_serializer(cita)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def eliminadas(self, request):
        """
        Devuelve una lista de las citas que han sido desactivadas (soft delete).
        """
        # El queryset ya está filtrado por grupo/médico gracias a get_queryset
        queryset = self.get_queryset().filter(estado=False)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        """
        Restaura una cita que fue desactivada.
        """
        cita = self.get_object()
        cita.estado = True
        cita.estado_cita = 'CONFIRMADA' # Se restaura a un estado activo
        cita.save()

        # --- Log de Acción ---
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Restauró la cita ID: {cita.id}",
            objeto=f"Cita ID: {cita.id}",
            usuario=actor
        )
        
        serializer = self.get_serializer(cita)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='estados-disponibles')
    def estados_disponibles(self, request):
        """
        Devuelve un diccionario con los posibles estados de una cita y sus nombres.
        """
        return Response(dict(Cita_Medica.ESTADOS_CITA))