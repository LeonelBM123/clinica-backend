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
from rest_framework import generics
from rest_framework import permissions
from config import settings
from .models import *
from .serializers import *
from django.db.models import Q
from apps.historiasDiagnosticos.models import Paciente

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
    
    def get_user_paciente(self):
        """Obtiene el paciente asociado al usuario actual"""
        if hasattr(self.request, 'user') and self.request.user.is_authenticated:
            try:
                from apps.historiasDiagnosticos.models import Paciente
                from apps.cuentas.models import Usuario
                
                # Obtener el usuario actual
                usuario = Usuario.objects.get(correo=self.request.user.email)
                
                # Obtener el paciente asociado a este usuario
                paciente = Paciente.objects.get(usuario=usuario)
                return paciente
            except (Usuario.DoesNotExist, Paciente.DoesNotExist):
                pass
        return None

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
        Asigna datos automáticos (grupo y paciente) al crear una cita y registra el log.
        """
        bloque = serializer.validated_data.get('bloque_horario')
        paciente = self.get_user_paciente()
        
        if not paciente:
            raise ValidationError('No se encontró un paciente asociado a este usuario')
        
        # Validar que el paciente y el médico pertenezcan al mismo grupo
        if paciente.usuario.grupo != bloque.grupo:
            raise ValidationError('El paciente y el médico no pertenecen a la misma clínica/grupo.')
        
        # Guardamos la cita asignando el grupo del bloque y el paciente del usuario
        cita = serializer.save(grupo=bloque.grupo, paciente=paciente)
        
        # --- Log de Acción ---
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Creó cita para {cita.paciente.usuario.nombre} el {cita.fecha} a las {cita.hora_inicio.strftime('%H:%M')}",
            objeto=f"Cita ID: {cita.id}",
            usuario=actor
        )

    
    @action(detail=False, methods=['get'], url_path='paciente/(?P<paciente_id>[^/.]+)')
    def citas_por_paciente(self, request, paciente_id=None):
        """
        Obtiene todas las citas médicas asociadas a un paciente específico.
        """
        try:
            # Filtramos las citas por el ID del paciente
            citas = self.get_queryset().filter(paciente_id=paciente_id)
            serializer = self.get_serializer(citas, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': f'Error al obtener las citas del paciente: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        

    @action(detail=False, methods=['get'], url_path='usuario/(?P<usuario_id>[^/.]+)')
    def citas_por_usuario(self, request, usuario_id=None): # CORRECCIÓN 2: El método también cambia de nombre.
        """
        Obtiene todas las citas médicas de un paciente, buscándolo 
        a través del ID de su usuario asociado.
        """
        try:
            # PASO 1: Buscar el perfil del paciente usando el 'usuario_id' de la URL.
            # Usamos get_object_or_404 que es la forma estándar en Django.
            # Si no encuentra un paciente para ese usuario, devolverá un error 404 Not Found.
            # NOTA: Asumimos que la relación en tu modelo 'Paciente' se llama 'usuario'.
            paciente_obj = get_object_or_404(Paciente, usuario_id=usuario_id)
            
            # PASO 2: Filtrar las citas usando el objeto 'paciente' que encontramos.
            # Es más claro y seguro que filtrar por el ID.
            citas = self.get_queryset().filter(paciente=paciente_obj)
            
            serializer = self.get_serializer(citas, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            # Este bloque genérico ahora captura errores inesperados del servidor.
            return Response(
                {'error': f'Ocurrió un error inesperado en el servidor: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
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
            accion=f"Actualizó la cita ID: {cita_actualizada.id} para el paciente {cita_actualizada.paciente.usuario.nombre}",
            objeto=f"Cita ID: {cita_actualizada.id}",
            usuario=actor
        )

    def perform_destroy(self, instance):
        """
        Realiza un "soft delete" (desactivación) de la cita y registra el log.
        """
        cita_info = f"ID: {instance.id} - Paciente: {instance.paciente.usuario.nombre}"
        
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

        serializer = CitaMedicaDetalleSerializer(cita)
        return Response(serializer.data)
    @action(detail=False, methods=['get'], url_path='estados-disponibles')
    def estados_disponibles(self, request):
        """
        Devuelve un diccionario con los posibles estados de una cita y sus nombres.
        """
        return Response(dict(Cita_Medica.ESTADOS_CITA))

    @action(detail=False, methods=['get'], url_path='mi-paciente-id')
    def mi_paciente_id(self, request):
        """
        Devuelve el ID del paciente asociado al usuario actual.
        """
        paciente = self.get_user_paciente()
        if paciente:
            return Response({'paciente_id': paciente.id})
        else:
            return Response({'error': 'No se encontró un paciente asociado a este usuario'}, 
                    status=status.HTTP_404_NOT_FOUND)

