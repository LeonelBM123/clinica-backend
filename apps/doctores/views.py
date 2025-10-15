from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework import generics
from rest_framework import permissions
from apps.cuentas.utils import get_actor_usuario_from_request, log_action
from django.db.models import Q
from apps.citas_pagos.models import Cita_Medica
from apps.citas_pagos.serializers import HorarioDisponibleSerializer
from .models import *
from .serializers import *
from .permissions import CanEditOrDeleteBloqueHorario
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from rest_framework.exceptions import ValidationError

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
        if grupo:
            # Verifica si el modelo tiene campo grupo (incluyendo herencia)
            model = queryset.model
            has_grupo_field = any(
                hasattr(field, 'name') and field.name == 'grupo' 
                for field in model._meta.get_fields()
            )
            
            if has_grupo_field:
         
                return queryset.filter(grupo=grupo)
        
   
        return queryset

class EspecialidadViewSet(viewsets.ModelViewSet):
    queryset = Especialidad.objects.all()
    serializer_class = EspecialidadSerializer

class MedicoViewSet(MultiTenantMixin, viewsets.ModelViewSet):  
    queryset = Medico.objects.all()
    serializer_class = MedicoSerializer
    
    def get_queryset(self):
        queryset = Medico.objects.all()
        # Usar el filtrado por grupo del Mixin
        queryset = self.filter_by_grupo(queryset)
        
        # Por defecto, solo médicos activos
        if self.action == 'list':
            return queryset.filter(estado=True)
        return queryset

    def create(self, request, *args, **kwargs):
        """Override create para debug"""

        
        try:
            return super().create(request, *args, **kwargs)
        except Exception as e:
      
            import traceback
            traceback.print_exc()
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    def perform_create(self, serializer):
        # Asignar automáticamente el grupo del usuario que crea
        try:
            usuario = Usuario.objects.get(correo=self.request.user.email)
       
            
            # ASIGNAR ROL MÉDICO AUTOMÁTICAMENTE
            try:
                rol_medico = Rol.objects.get(nombre='medico')
            except Rol.DoesNotExist:
                # Si no existe, buscar por ID 4 o crear uno
                try:
                    rol_medico = Rol.objects.get(id=4)
                except Rol.DoesNotExist:
                    # Crear rol médico si no existe
                    rol_medico = Rol.objects.create(
                        nombre='medico',
                        descripcion='Médico del sistema'
                    )
            
              
            # OBTENER Y HASHEAR LA CONTRASEÑA
            validated_data = serializer.validated_data
            password = validated_data.get('password')
            
            if password:
                from django.contrib.auth.hashers import make_password
                validated_data['password'] = make_password(password)
    
            
            # Crear también el User de Django
            correo = validated_data.get('correo')
            if correo and password:
                try:
                    User.objects.create_user(
                        username=correo,
                        email=correo,
                        password=password  # Django ya la hashea automáticamente
                    )
                except Exception as e:
                    print(f"⚠️ Error creando User Django: {e}")
            
            # Guardar con grupo Y rol
            medico = serializer.save(grupo=usuario.grupo, rol=rol_medico)
            
            # Log de la acción
            actor = get_actor_usuario_from_request(self.request)
            log_action(
                request=self.request,
                accion=f"Creó el médico {medico.nombre} (id:{medico.id})",
                objeto=f"Médico: {medico.nombre} (id:{medico.id})",
                usuario=actor
            )

            
        except Usuario.DoesNotExist:

            # Fallback con rol médico
            grupo = Grupo.objects.first()
            try:
                rol_medico = Rol.objects.get(nombre='medico')
            except Rol.DoesNotExist:
                rol_medico = Rol.objects.get(id=4)
            
            # Hashear contraseña en fallback también
            validated_data = serializer.validated_data
            password = validated_data.get('password')
            if password:
                from django.contrib.auth.hashers import make_password
                validated_data['password'] = make_password(password)
                
            medico = serializer.save(grupo=grupo, rol=rol_medico)
    

    def perform_update(self, serializer):
        medico = serializer.save()
        
        # Log de la acción
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Actualizó el médico {medico.nombre} (id:{medico.id})",
            objeto=f"Médico: {medico.nombre} (id:{medico.id})",
            usuario=actor
        )

    def perform_destroy(self, instance):
        # Soft delete: solo cambia estado a False
        nombre = instance.nombre
        pk = instance.pk
        instance.estado = False
        instance.save()
        
        # Log de la acción
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Eliminó (soft delete) el médico {nombre} (id:{pk})",
            objeto=f"Médico: {nombre} (id:{pk})",
            usuario=actor
        )
    
    @action(detail=False, methods=['get'])
    def eliminados(self, request):
        queryset = Medico.objects.all()
        queryset = self.filter_by_grupo(queryset)  # Filtrar por grupo
        eliminados = queryset.filter(estado=False)
        serializer = self.get_serializer(eliminados, many=True)
        return Response(serializer.data)    
    
    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        medico = self.get_object()
        medico.estado = True
        medico.save()
        
        # Log de la acción
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Restauró el médico {medico.nombre} (id:{medico.id})",
            objeto=f"Médico: {medico.nombre} (id:{medico.id})",
            usuario=actor
        )
        
        serializer = self.get_serializer(medico)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'], url_path='horarios-disponibles')
    def horarios_disponibles(self, request, pk=None):
        """
        Calcula y devuelve los slots de tiempo disponibles para un médico en una fecha específica.
        Uso: GET /api/doctores/medicos/{pk}/horarios-disponibles/?fecha=YYYY-MM-DD
        """
        medico = self.get_object()
        fecha_str = request.query_params.get('fecha')
        
        if not fecha_str:
            return Response({'error': 'El parámetro "fecha" es requerido (YYYY-MM-DD).'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Formato de fecha inválido. Use AAAA-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        DIAS_SEMANA_MAP = {0: 'LUNES', 1: 'MARTES', 2: 'MIERCOLES', 3: 'JUEVES', 4: 'VIERNES', 5: 'SABADO', 6: 'DOMINGO'}
        dia_semana = DIAS_SEMANA_MAP.get(fecha.weekday())
        
        bloques_del_dia = Bloque_Horario.objects.filter(medico=medico, dia_semana=dia_semana, estado=True)
        citas_ocupadas = Cita_Medica.objects.filter(bloque_horario__medico=medico, fecha=fecha).exclude(estado_cita='CANCELADA')

        horas_ocupadas_por_bloque = {}
        citas_por_bloque = {}
        for cita in citas_ocupadas:
            bloque_id = cita.bloque_horario_id
            if bloque_id not in horas_ocupadas_por_bloque:
                horas_ocupadas_por_bloque[bloque_id] = set()
                citas_por_bloque[bloque_id] = 0
            horas_ocupadas_por_bloque[bloque_id].add(cita.hora_inicio)
            citas_por_bloque[bloque_id] += 1
            
        horarios_disponibles = []
        for bloque in bloques_del_dia:
            if citas_por_bloque.get(bloque.id, 0) >= bloque.max_citas_por_bloque:
                continue
            
            hora_actual_dt = datetime.combine(fecha, bloque.hora_inicio)
            hora_fin_dt = datetime.combine(fecha, bloque.hora_fin)
            intervalo = timedelta(minutes=bloque.duracion_cita_minutos)
            
            horas_ocupadas_set = horas_ocupadas_por_bloque.get(bloque.id, set())

            while hora_actual_dt < hora_fin_dt:
                hora_slot = hora_actual_dt.time()
                if hora_slot not in horas_ocupadas_set:
                    horarios_disponibles.append({'bloque_horario_id': bloque.id, 'hora_inicio': hora_slot})
                hora_actual_dt += intervalo
        
        serializer = HorarioDisponibleSerializer(horarios_disponibles, many=True)
        return Response(serializer.data)


class TipoAtencionViewSet(MultiTenantMixin, viewsets.ModelViewSet):
    queryset = Tipo_Atencion.objects.all()
    serializer_class = TipoAtencionSerializer
    
    def get_queryset(self):
        queryset = Tipo_Atencion.objects.all()
        return self.filter_by_grupo(queryset)

class BloqueHorarioViewSet(MultiTenantMixin, viewsets.ModelViewSet):
    """
    Gestiona el CRUD para los Bloques Horarios.
    """
    serializer_class = BloqueHorarioSerializer
    queryset = Bloque_Horario.objects.all().select_related('medico', 'tipo_atencion')

    def get_queryset(self):
        """
        Filtra los bloques:
        - Si el usuario es Médico, solo ve sus propios bloques.
        - Si es Admin/Recepcionista, ve todos los bloques de su grupo.
        """
        queryset = super().get_queryset()
        
        # Primero, intenta obtener el perfil de médico del usuario.
        # Asumo que tienes un método 'get_user_medico' en tu MultiTenantMixin.
        # Si no, podemos añadirlo.
        try:
            medico_logueado = Medico.objects.get(correo=self.request.user.email)
            return queryset.filter(medico=medico_logueado)
        except Medico.DoesNotExist:
            # Si no es un médico, se asume que es un rol administrativo
            # y se aplica el filtro por grupo del mixin.
            return self.filter_by_grupo(queryset)

    def get_permissions(self):
        """
        Asigna permisos específicos según la acción.
        """
        if self.action in ['update', 'partial_update', 'destroy']:
            self.permission_classes = [permissions.IsAuthenticated, CanEditOrDeleteBloqueHorario]
        else:
            self.permission_classes = [permissions.IsAuthenticated]
        return super().get_permissions()

    def perform_create(self, serializer):
        """
        Asigna el médico y el grupo de forma inteligente al crear un bloque.
        """
        medico_para_bloque = serializer.validated_data.get('medico')
        
        # Si el médico no vino en el formulario (porque el usuario logueado es médico)
        if not medico_para_bloque:
            try:
                medico_para_bloque = Medico.objects.get(correo=self.request.user.email)
            except Medico.DoesNotExist:
                # Esto ocurre si un admin/recepcionista no selecciona un médico en el formulario
                raise ValidationError({'medico': 'Debe seleccionar un médico para crear el bloque horario.'})
        
        if not medico_para_bloque:
            raise ValidationError({'detail': 'No se pudo determinar el médico para este bloque horario.'})
            
        # Guardamos el bloque, asignando el médico correcto y el grupo de ese médico
        bloque = serializer.save(medico=medico_para_bloque, grupo=medico_para_bloque.grupo)

        # Log de la acción
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Creó el bloque horario ID:{bloque.id} para {medico_para_bloque.nombre}",
            objeto=f"Bloque_Horario: {bloque.id}",
            usuario=actor
        )

    def perform_update(self, serializer):
        """
        Registra la acción al actualizar un bloque.
        """
        bloque = serializer.save()
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Actualizó el bloque horario ID:{bloque.id}",
            objeto=f"Bloque_Horario: {bloque.id}",
            usuario=actor
        )

    @action(detail=False, methods=['get'], url_path='medico/(?P<medico_id>[^/.]+)')
    def bloques_por_medico(self, request, medico_id=None):
        """
        Obtiene todos los bloques horarios de un médico específico.
        Uso: GET /api/doctores/bloques-horarios/medico/{medico_id}/
        """
        try:
            medico = Medico.objects.get(id=medico_id, estado=True)
        except Medico.DoesNotExist:
            return Response({'error': 'Médico no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        
        # Verificar que el paciente pueda ver médicos de su clínica
        usuario_actual = None
        try:
            usuario_actual = Usuario.objects.get(correo=self.request.user.email)
        except Usuario.DoesNotExist:
            pass
        
        # Si el usuario es paciente, verificar que el médico sea de su misma clínica
        if usuario_actual and usuario_actual.rol and usuario_actual.rol.nombre == 'paciente':
            if medico.grupo != usuario_actual.grupo:
                return Response({'error': 'No tiene permisos para ver este médico'}, status=status.HTTP_403_FORBIDDEN)
        
        # Filtrar bloques activos del médico
        bloques = Bloque_Horario.objects.filter(
            medico=medico, 
            estado=True
        ).select_related('medico', 'tipo_atencion')
        
        serializer = BloqueHorarioSerializer(bloques, many=True)
        return Response(serializer.data)

    def perform_destroy(self, instance):
        """
        Registra la acción al eliminar un bloque.
        """
        bloque_id = instance.id
        dia_semana = instance.get_dia_semana_display()
        
        instance.delete()

        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Eliminó el bloque horario ID:{bloque_id} del día {dia_semana}",
            objeto=f"Bloque_Horario: {bloque_id}",
            usuario=actor
        )

