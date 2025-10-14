from datetime import datetime
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
    queryset = Cita_Medica.objects.all()
    serializer_class = CitaMedicaSerializer
    
    def get_queryset(self):
        """Filtra citas por grupo y médico (si es médico)"""
        queryset = Cita_Medica.objects.all()
        queryset = self.filter_by_grupo(queryset)
        
        # CORRECCIÓN: Usar get_user_medico() en lugar de hasattr
        medico = self.get_user_medico()
        if medico:
            queryset = queryset.filter(bloque_horario__medico=medico)
           
        
        # Por defecto, solo citas activas
        if self.action == 'list':
            queryset = queryset.filter(estado=True)
            
        return queryset.order_by('-fecha', '-hora_inicio')

    def create(self, request, *args, **kwargs):
        """Override create para asignar grupo automáticamente"""
     
        
        # CORRECCIÓN: Crear copia de los datos y asignar grupo
        data = request.data.copy()
        
        try:
            usuario = Usuario.objects.get(correo=request.user.email)
            data['grupo'] = usuario.grupo.id
            
            # CORRECCIÓN: Usar el serializer con los datos modificados
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
            
        except Usuario.DoesNotExist:
       
            return Response(
                {"error": "Usuario no válido"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
          
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    def perform_create(self, serializer):
        """Asignar grupo y estado inicial"""
        try:
            usuario = Usuario.objects.get(correo=self.request.user.email)
            cita = serializer.save(grupo=usuario.grupo, estado_cita='PENDIENTE')
            
            # Log de la acción
            actor = get_actor_usuario_from_request(self.request)
            log_action(
                request=self.request,
                accion=f"Creó cita médica para {cita.paciente.nombre} - {cita.fecha} {cita.hora_inicio}",
                objeto=f"Cita Médica: {cita}",
                usuario=actor
            )
      
            
        except Usuario.DoesNotExist:
            grupo = Grupo.objects.first()
            cita = serializer.save(grupo=grupo, estado_cita='PENDIENTE')
          

    def perform_update(self, serializer):
        """Logging en actualizaciones"""
        # CORRECCIÓN: Obtener la cita antes de guardar para logging
        cita = serializer.instance
        cita_actualizada = serializer.save()
        
        # Log de la acción
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Actualizó cita médica {cita.id} - {cita.paciente.nombre}",
            objeto=f"Cita Médica: {cita}",
            usuario=actor
        )

    def perform_destroy(self, instance):
        """Soft delete"""
        # CORRECCIÓN: Guardar información antes de modificar
        cita_info = f"{instance.id} - {instance.paciente.nombre}"
        
        instance.estado = False
        instance.estado_cita = 'CANCELADA'
        instance.save()
        
        # Log de la acción
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Canceló cita médica {cita_info}",
            objeto=f"Cita Médica: {cita_info}",
            usuario=actor
        )

    # ENDPOINTS PERSONALIZADOS
    @action(detail=False, methods=['get'])
    def por_medico(self, request):
        """Obtener citas por médico (para el médico logueado)"""
        # CORRECCIÓN: Usar get_user_medico()
        medico = self.get_user_medico()
        if not medico:
            return Response(
                {"error": "Usuario no es un médico o no está asociado a un médico"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        citas = self.get_queryset().filter(bloque_horario__medico=medico)
        serializer = self.get_serializer(citas, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def por_fecha(self, request):
        """Obtener citas por fecha específica"""
        fecha = request.query_params.get('fecha')
        if not fecha:
            return Response(
                {"error": "Se requiere parámetro fecha (YYYY-MM-DD)"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # CORRECCIÓN: Validar formato de fecha
        try:
            datetime.strptime(fecha, '%Y-%m-%d')
        except ValueError:
            return Response(
                {"error": "Formato de fecha inválido. Use YYYY-MM-DD"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        citas = self.get_queryset().filter(fecha=fecha)
        serializer = self.get_serializer(citas, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def cambiar_estado(self, request, pk=None):
        """Cambiar estado de una cita"""
        cita = self.get_object()
        nuevo_estado = request.data.get('estado_cita')
        motivo = request.data.get('motivo_cancelacion', '')
        
        if nuevo_estado not in dict(Cita_Medica.ESTADOS_CITA):
            return Response(
                {"error": "Estado no válido"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # CORRECCIÓN: Validar transiciones de estado
        estado_actual = cita.estado_cita
        if estado_actual == 'COMPLETADA' and nuevo_estado != 'COMPLETADA':
            return Response(
                {"error": "No se puede modificar una cita completada"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        cita.estado_cita = nuevo_estado
        if nuevo_estado == 'CANCELADA':
            cita.motivo_cancelacion = motivo
        cita.save()
        
        # Log de la acción
        actor = get_actor_usuario_from_request(request)
        log_action(
            request=request,
            accion=f"Cambió estado de cita {cita.id} de {estado_actual} a {nuevo_estado}",
            objeto=f"Cita Médica: {cita}",
            usuario=actor
        )
        
        serializer = self.get_serializer(cita)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def eliminadas(self, request):
        """Citas eliminadas/desactivadas"""
        eliminadas = self.get_queryset().filter(estado=False)
        serializer = self.get_serializer(eliminadas, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        """Restaurar cita eliminada"""
        cita = self.get_object()
        cita.estado = True
        cita.estado_cita = 'PENDIENTE'  # CORRECCIÓN: Resetear estado
        cita.save()
        
        # Log de la acción
        actor = get_actor_usuario_from_request(request)
        log_action(
            request=request,
            accion=f"Restauró cita médica {cita.id}",
            objeto=f"Cita Médica: {cita}",
            usuario=actor
        )
        
        serializer = self.get_serializer(cita)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def estados_disponibles(self, request):
        """Obtener lista de estados disponibles"""
        return Response(dict(Cita_Medica.ESTADOS_CITA))

    # CORRECCIÓN: Agregar endpoint para disponibilidad
    @action(detail=False, methods=['get'])
    def verificar_disponibilidad(self, request):
        """Verificar disponibilidad de horario para cita"""
        bloque_id = request.query_params.get('bloque_id')
        fecha = request.query_params.get('fecha')
        hora_inicio = request.query_params.get('hora_inicio')
        hora_fin = request.query_params.get('hora_fin')
        
        if not all([bloque_id, fecha, hora_inicio, hora_fin]):
            return Response(
                {"error": "Se requieren todos los parámetros: bloque_id, fecha, hora_inicio, hora_fin"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            bloque = Bloque_Horario.objects.get(id=bloque_id)
            # Validar disponibilidad (sin solapamientos)
            citas_existentes = Cita_Medica.objects.filter(
                bloque_horario=bloque,
                fecha=fecha,
                estado=True
            ).filter(
                Q(hora_inicio__lt=hora_fin, hora_fin__gt=hora_inicio)
            )
            
            disponible = not citas_existentes.exists()
            
            return Response({
                "disponible": disponible,
                "citas_existentes": citas_existentes.count()
            })
            
        except Bloque_Horario.DoesNotExist:
            return Response(
                {"error": "Bloque horario no encontrado"}, 
                status=status.HTTP_404_NOT_FOUND
            )
