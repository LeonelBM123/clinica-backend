import stripe
from datetime import datetime, timedelta
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import ValidationError
from apps.cuentas.utils import get_actor_usuario_from_request, log_action
from apps.cuentas.models import Usuario, Grupo
from apps.doctores.models import Medico
from rest_framework.response import Response
from rest_framework.exceptions import APIException
from rest_framework import generics
from rest_framework import permissions
from config import settings
from .models import *
from .serializers import *
from django.db.models import Q
from apps.historiasDiagnosticos.models import Paciente

# Importamos la función de nuestro servicio de IA
from .ia_services import generar_informe_con_ia

stripe.api_key = settings.STRIPE_SECRET_KEY
@api_view(['POST'])
def create_payment_intent(request):
    try:
        data = request.data
        amount = data.get('amount')  # en centavos
        currency = data.get('currency', 'usd')

        if not amount:
            return Response({"error": "Amount is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Crear el PaymentIntent en Stripe
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            automatic_payment_methods={"enabled": True},
        )

        return Response({
            "clientSecret": intent.client_secret
        })
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
class MultiTenantMixin:
    """Mixin para filtrar datos por grupo del usuario actual"""
    permission_classes = [permissions.IsAuthenticated]

    def get_user_grupo(self):
        if hasattr(self.request, 'user') and self.request.user.is_authenticated:
            try:
                usuario = Usuario.objects.get(correo=self.request.user.email)
                return usuario.grupo
            except Usuario.DoesNotExist:
                pass
        return None

    def get_user_medico(self):
        if hasattr(self.request, 'user') and self.request.user.is_authenticated:
            try:
                medico = Medico.objects.get(correo=self.request.user.email)
                return medico
            except Medico.DoesNotExist:
                pass
        return None

    def is_super_admin(self):
        # Implementa tu lógica real aquí si es necesario
        return False

    def get_user_paciente(self):
        if hasattr(self.request, 'user') and self.request.user.is_authenticated:
            try:
                from apps.historiasDiagnosticos.models import Paciente # Importación local
                from apps.cuentas.models import Usuario # Importación local

                usuario = Usuario.objects.get(correo=self.request.user.email)
                paciente = Paciente.objects.get(usuario=usuario)
                return paciente
            except (Usuario.DoesNotExist, Paciente.DoesNotExist):
                pass
        return None

    def filter_by_grupo(self, queryset):
        grupo = self.get_user_grupo()
        if grupo:
            model = queryset.model
            # Forma más robusta de verificar si el modelo tiene el campo 'grupo'
            if hasattr(model, 'grupo'):
                 return queryset.filter(grupo=grupo)
            # Considera añadir un log o manejo si el modelo no tiene 'grupo' pero se espera
        return queryset

class CitaMedicaViewSet(MultiTenantMixin, viewsets.ModelViewSet):
    """
    Gestiona el CRUD completo y las acciones personalizadas para las Citas Médicas.
    """
    queryset = Cita_Medica.objects.all().select_related('paciente__usuario', 'bloque_horario__medico', 'grupo')
    serializer_class = CitaMedicaSerializer
    permission_classes = [permissions.IsAuthenticated] # Redundante si ya está en el Mixin, pero no hace daño

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.filter_by_grupo(queryset)
        medico = self.get_user_medico()
        if medico:
            queryset = queryset.filter(bloque_horario__medico=medico)
        else:
            print("🔍 [Backend] No se está filtrando por médico")
            
        return queryset.order_by('-fecha', '-hora_inicio')

    def perform_create(self, serializer):
        bloque = serializer.validated_data.get('bloque_horario')
        paciente = serializer.validated_data.get('paciente')

        # La validación de grupo ahora está en el serializer.validate
        # if paciente.usuario.grupo != bloque.medico.grupo:
        #     raise ValidationError('El paciente y el médico no pertenecen a la misma clínica/grupo.')

        # El serializer.create ya asigna el grupo
        cita = serializer.save() # No es necesario pasar 'grupo' aquí si el serializer lo hace

        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Creó cita para {cita.paciente.usuario.nombre} el {cita.fecha} a las {cita.hora_inicio.strftime('%H:%M')}",
            objeto=f"Cita ID: {cita.id}",
            usuario=actor
        )

    @action(detail=False, methods=['get'], url_path='paciente/(?P<paciente_id>[^/.]+)')
    def citas_por_paciente(self, request, paciente_id=None):
        try:
            # Usar get_queryset asegura que se apliquen los filtros de grupo/médico
            citas = self.get_queryset().filter(paciente_id=paciente_id)
            serializer = self.get_serializer(citas, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            # Considera loguear el error 'e' para debugging
            return Response(
                {'error': f'Error al obtener las citas del paciente.'}, # Mensaje más genérico al usuario
                status=status.HTTP_400_BAD_REQUEST
            )

    def perform_update(self, serializer):
        cita_actualizada = serializer.save()
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Actualizó la cita ID: {cita_actualizada.id} para {cita_actualizada.paciente.usuario.nombre}",
            objeto=f"Cita ID: {cita_actualizada.id}",
            usuario=actor
        )

    def perform_destroy(self, instance):
        cita_info = f"ID: {instance.id} - Paciente: {instance.paciente.usuario.nombre}"
        instance.estado = False
        if instance.estado_cita not in ['COMPLETADA', 'CANCELADA']:
            instance.estado_cita = 'CANCELADA'
            instance.motivo_cancelacion = "Cancelada por el sistema/personal."
        instance.save()

        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Canceló (soft delete) la cita: {cita_info}",
            objeto=f"Cita ID: {instance.id}",
            usuario=actor
        )

    @action(detail=True, methods=['post'], url_path='cambiar-estado')
    def cambiar_estado(self, request, pk=None):
        cita = self.get_object()
        nuevo_estado = request.data.get('estado_cita')

        if not nuevo_estado or nuevo_estado not in dict(Cita_Medica.ESTADOS_CITA):
            return Response({"error": "Debe proporcionar un estado válido."}, status=status.HTTP_400_BAD_REQUEST)

        estado_anterior = cita.estado_cita
        cita.estado_cita = nuevo_estado

        if nuevo_estado == 'CANCELADA':
            cita.motivo_cancelacion = request.data.get('motivo_cancelacion', 'Sin motivo especificado.')

        cita.save()

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
        queryset = self.get_queryset().filter(estado=False)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        cita = self.get_object()
        # Asegurarse que solo se restauren citas con estado=False
        if not cita.estado:
             cita.estado = True
             # Decidir a qué estado restaurar, ¿CONFIRMADA siempre?
             cita.estado_cita = 'CONFIRMADA'
             cita.save()

             actor = get_actor_usuario_from_request(self.request)
             log_action(
                 request=self.request,
                 accion=f"Restauró la cita ID: {cita.id}",
                 objeto=f"Cita ID: {cita.id}",
                 usuario=actor
             )

             serializer = self.get_serializer(cita)
             return Response(serializer.data, status=status.HTTP_200_OK)
        else:
             # Si la cita ya está activa, no hacer nada o devolver error
             return Response({"detail": "La cita ya está activa."}, status=status.HTTP_400_BAD_REQUEST)


        serializer = CitaMedicaDetalleSerializer(cita)
        return Response(serializer.data)
    @action(detail=False, methods=['get'], url_path='estados-disponibles')
    def estados_disponibles(self, request):
        return Response(dict(Cita_Medica.ESTADOS_CITA))

    @action(detail=False, methods=['get'], url_path='mi-paciente-id')
    def mi_paciente_id(self, request):
        paciente = self.get_user_paciente()
        if paciente:
            return Response({'paciente_id': paciente.id})
        else:
            return Response({'error': 'No se encontró un paciente asociado a este usuario'},
                           status=status.HTTP_404_NOT_FOUND)

    # --- ¡ACCIÓN CORREGIDA!  ---
    @action(detail=True, methods=['post'], url_path='generar-reporte-ia')
    def generar_reporte_ia(self, request, pk=None):
        """
        Recibe notas vagas del médico y DEVUELVE un reporte estructurado
        generado por la IA (sin guardar).
        """
        cita = self.get_object() # Necesario para el log y contexto si hiciera falta
        notas_vagas = request.data.get('notas_vagas', '')
        if not notas_vagas:
            return Response(
                {"error": "No se proporcionaron 'notas_vagas' en el body."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Llamamos al servicio de IA (que ahora usa PROMPT_V5)
            reporte_generado = generar_informe_con_ia(notas_vagas)

            # Ya NO guardamos aquí:
            # cita.reporte = reporte_generado
            # cita.save(update_fields=['reporte'])

            # Log de Acción (informando que solo se generó)
            actor = get_actor_usuario_from_request(self.request)
            log_action(
                request=self.request,
                accion=f"Generó borrador de IA (sin guardar) para cita ID: {cita.id}",
                objeto=f"Cita ID: {cita.id}",
                usuario=actor
            )

            # Devolvemos el reporte al frontend
            return Response(
                {"reporte_generado": reporte_generado},
                status=status.HTTP_200_OK
            )

        except APIException as e:
            # Si nuestro servicio lanzó un error, lo pasamos limpiamente a DRF
            return Response(
                {"error": e.detail},
                status=e.status_code
            )
