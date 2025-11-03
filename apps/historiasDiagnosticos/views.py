from django.shortcuts import render
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from .models import *
from .serializers import *
from apps.cuentas.models import Usuario,Rol
from apps.cuentas.utils import get_actor_usuario_from_request, log_action
from django.contrib.auth.models import User
from apps.citas_pagos.serializers import CitaMedicaDetalleSerializer
from apps.citas_pagos.models import Cita_Medica
from .serializers import PacienteDetalleSerializer  # El serializer de solo lectura

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Prefetch

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
        # Empezamos con el queryset optimizado de la clase
        queryset = super().get_queryset()
        
        busqueda_global = self.request.query_params.get('busqueda_global', 'false').lower() == 'true'

        # Si NO es una búsqueda global Y el usuario no es superadmin, aplicamos el filtro por grupo
        if not busqueda_global and not self.is_super_admin():
            grupo = self.get_user_grupo()
            if grupo:
                # Tu modelo Paciente se relaciona con Usuario, que a su vez tiene el grupo.
                # La consulta correcta es a través de esa relación.
                queryset = queryset.filter(usuario__grupo=grupo)

        # Filtramos por usuarios activos para la acción 'list', a menos que sea búsqueda global
        if self.action == 'list' and not busqueda_global:
            queryset = queryset.filter(usuario__estado=True)
        
        # (Opcional pero recomendado) Añadir capacidad de búsqueda por nombre
        search_query = self.request.query_params.get('search', None)
        if search_query:
            queryset = queryset.filter(usuario__nombre__icontains=search_query)

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
    
    def perform_create(self, serializer):
        # Solo crear el paciente con el usuario seleccionado
        paciente = serializer.save()
        
        # Log de la acción
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Creó el paciente {paciente.usuario.nombre} (id:{paciente.id})",
            objeto=f"Paciente: {paciente.usuario.nombre} (id:{paciente.id})",
            usuario=actor
        )
        
    #para historial clinico
    @action(detail=True, methods=['get'])
    def historial(self, request, pk=None):
        """Muestra el historial de citas médicas del paciente"""
        paciente = self.get_object()
        
        # Trae todas las citas del paciente
        citas = Cita_Medica.objects.filter(paciente=paciente).select_related(
            'bloque_horario__medico__usuario_ptr'
        )
        
        # Serializamos las citas incluyendo datos del médico
        serializer = CitaMedicaDetalleSerializer(citas, many=True)
        return Response(serializer.data)

class ResultadoExamenesViewSet(MultiTenantMixin, viewsets.ModelViewSet):
    queryset = ResultadoExamenes.objects.all()
    serializer_class = ResultadoExamenesSerializer
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        queryset = ResultadoExamenes.objects.all()
        # Filtrar por grupo del usuario
        queryset = self.filter_by_grupo(queryset)
        return queryset

    def perform_create(self, serializer):
            import cloudinary.uploader
            archivo = self.request.FILES.get('archivo')
            print('DEBUG perform_create: archivo recibido:', archivo)
            archivo_url = None
            if archivo:
                result = cloudinary.uploader.upload(archivo)
                archivo_url = result.get('secure_url')
                print('DEBUG perform_create: archivo_url generado:', archivo_url)
            else:
                print('DEBUG perform_create: No se recibió archivo')
            usuario = Usuario.objects.get(correo=self.request.user.email)
            resultado = serializer.save(grupo=usuario.grupo, archivo_url=archivo_url)
            print('DEBUG perform_create: resultado.archivo_url guardado:', resultado.archivo_url)

            # Log de la acción
            actor = get_actor_usuario_from_request(self.request)
            log_action(
                request=self.request,
                accion=f"Creó el resultado de examen {resultado.id}",
                objeto=f"Resultado de examen: {resultado.id}",
                usuario=actor
            )

    def perform_update(self, serializer):
            import cloudinary.uploader
            archivo = self.request.FILES.get('archivo')
            print('DEBUG perform_update: archivo recibido:', archivo)
            archivo_url = None
            if archivo:
                result = cloudinary.uploader.upload(archivo)
                archivo_url = result.get('secure_url')
                print('DEBUG perform_update: archivo_url generado:', archivo_url)
                resultado = serializer.save(archivo_url=archivo_url)
            else:
                print('DEBUG perform_update: No se recibió archivo')
                resultado = serializer.save()
            print('DEBUG perform_update: resultado.archivo_url guardado:', resultado.archivo_url)

            # Log de la acción
            actor = get_actor_usuario_from_request(self.request)
            log_action(
                request=self.request,
                accion=f"Actualizó el resultado de examen {resultado.id}",
                objeto=f"Resultado de examen: {resultado.id}",
                usuario=actor
            )

    def perform_destroy(self, instance):
        import cloudinary.uploader
        # Eliminar imagen de Cloudinary si existe
        archivo_url = instance.archivo_url
        if archivo_url:
            public_id = None
            # Extraer public_id de la URL de Cloudinary
            parts = archivo_url.split('/')
            if len(parts) > 1:
                public_id = '/'.join(parts[-2:]).split('.')[0]
            if public_id:
                try:
                    cloudinary.uploader.destroy(public_id)
                except Exception:
                    pass
        pk = instance.pk
        instance.delete()

        # Log de la acción
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Eliminó (soft delete) el resultado de examen (id:{pk})",
            objeto=f"Resultado de examen: (id:{pk})",
            usuario=actor
        )


#View
class PatientHistoryView(APIView):
    """
    GET /api/pacientes/{paciente_id}/historia
    Devuelve la historia clínica completa del paciente.
    """
    permission_classes = [IsAuthenticated]   # si tu proyecto demo no quiere auth, cámbialo a AllowAny

    def get(self, request, paciente_id):
        # Multi-tenancy opcional: si usas grupos en JWT/request, aquí podrías filtrar por grupo
        try:
            qs = (
                Paciente.objects
                .select_related("usuario")
                .prefetch_related(
                    # patologías + sus tratamientos
                    Prefetch(
                        "patologias",
                        queryset=PatologiasO.objects.prefetch_related("tratamientos").order_by("nombre"),
                    ),
                    # resultados con médico
                    Prefetch(
                        "resultados_examenes",
                        queryset=ResultadoExamenes.objects.select_related("medico", "paciente").order_by("-fecha_creacion"),
                    ),
                )
            )
            paciente = qs.get(pk=paciente_id)
        except Paciente.DoesNotExist:
            return Response({"detail": "Paciente no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        patologias = list(paciente.patologias.all())
        resultados = list(paciente.resultados_examenes.all())

        # métricas
        ultimo_examen = resultados[0].fecha_creacion if resultados else None
        data = {
            "paciente": paciente,
            "patologias": patologias,
            "resultados_examenes": resultados,
            "total_patologias": len(patologias),
            "total_resultados": len(resultados),
            "ultimo_examen_en": ultimo_examen,
        }

        # serializar usando el serializer agregado
        serializer = PatientHistorySerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)