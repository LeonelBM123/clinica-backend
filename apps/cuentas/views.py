from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework import generics
from rest_framework import permissions
from .utils import get_actor_usuario_from_request, log_action
from .models import *
from .serializers import *
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import permission_classes
from django.utils.dateparse import parse_date
import secrets
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.suscripciones.models import PagoSuscripcion,Plan,Suscripcion


class MultiTenantMixin:
    """Mixin para filtrar datos por grupo del usuario actual"""
    
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
                return usuario.rol and usuario.rol.nombre == 'superAdmin'  # Cambiar aquí también
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

class GrupoViewSet(viewsets.ModelViewSet):
    serializer_class = GrupoSerializer

    def get_permissions(self):
        """
        Permite crear grupos sin autenticación (registro público)
        Pero requiere autenticación para otras operaciones
        """
        if self.action == 'create':
            permission_classes = [AllowAny]  # Permite crear sin autenticación
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        # Solo super admins pueden ver/gestionar grupos
        if self.is_super_admin():
            return Grupo.objects.all()
        else:
            # Usuarios normales solo ven su propio grupo
            grupo = self.get_user_grupo()
            if grupo:
                return Grupo.objects.filter(id=grupo.id)
            return Grupo.objects.none()
    
    def is_super_admin(self):
        if not self.request.user.is_authenticated:
            return False
        try:
            usuario = Usuario.objects.get(correo=self.request.user.email)
            return usuario.rol and usuario.rol.nombre == 'superAdmin'
        except Usuario.DoesNotExist:
            return False
    
    def get_user_grupo(self):
        if not self.request.user.is_authenticated:
            return None
        try:
            usuario = Usuario.objects.get(correo=self.request.user.email)
            return usuario.grupo
        except Usuario.DoesNotExist:
            return None
    
    def perform_create(self, serializer):
        grupo = serializer.save()
        
        plan_id = self.request.data.get('plan_id')
        
        if plan_id:
            try:
                plan_obj = Plan.objects.get(id=plan_id)
                
                Suscripcion.objects.create(
                    grupo=grupo,
                    plan=plan_obj,
                    estado='ACTIVA',  # La activamos inmediatamente
                    fecha_inicio=timezone.now(),
                    fecha_fin=timezone.now() + timedelta(days=30), # 1 mes de duración inicial
                    renovacion_automatica=True
                )
                print(f"Suscripción creada exitosamente para {grupo.nombre} con plan {plan_obj.nombre}")
                
            except Plan.DoesNotExist:
                print(f"El plan con id {plan_id} no existe. Se creó el grupo sin suscripción.")
            except Exception as e:
                print(f"Error creando suscripción: {e}")
        else:
            print("No se recibió plan_id en el registro.")

        log_action(
            request=self.request,
            accion=f"Se registró la nueva clínica {grupo.nombre}",
            objeto=f"Grupo: {grupo.nombre} (id:{grupo.id})",
            usuario=None 
                            )
    
    @action(detail=True, methods=['post'])
    def suspender(self, request, pk=None):
        """Suspende un grupo (solo super admin)"""
        if not self.is_super_admin():
            return Response(
                {'error': 'No tienes permisos para esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        grupo = self.get_object()
        grupo.estado = 'SUSPENDIDO'
        grupo.fecha_suspension = timezone.now()
        grupo.save()
        
        return Response({'message': 'Grupo suspendido correctamente'})
    
    @action(detail=True, methods=['post'])
    def activar(self, request, pk=None):
        """Activa un grupo (solo super admin)"""
        if not self.is_super_admin():
            return Response(
                {'error': 'No tienes permisos para esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        grupo = self.get_object()
        grupo.estado = 'ACTIVO'
        grupo.fecha_suspension = None
        grupo.save()
        
        return Response({'message': 'Grupo activado correctamente'})

class PagoViewSet(MultiTenantMixin, viewsets.ModelViewSet):
    serializer_class = PagoSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Pago.objects.all()
        return self.filter_by_grupo(queryset)
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    @action(detail=True, methods=['post'])
    def marcar_pagado(self, request, pk=None):
        """Marca un pago como pagado"""
        pago = self.get_object()
        pago.marcar_como_pagado()
        
        actor = get_actor_usuario_from_request(request)
        log_action(
            request=request,
            accion=f"Marcó como pagado el pago {pago.id} del grupo {pago.grupo.nombre}",
            objeto=f"Pago: {pago.id} - {pago.grupo.nombre}",
            usuario=actor
        )
        
        return Response({'message': 'Pago marcado como pagado correctamente'})

class RolViewSet(viewsets.ModelViewSet):
    queryset = Rol.objects.all()
    serializer_class = RolSerializer
    permission_classes = [IsAuthenticated]

class UsuarioViewSet(MultiTenantMixin, viewsets.ModelViewSet):
    serializer_class = UsuarioSerializer
    def get_permissions(self):
        """
        Permite crear usuarios y login sin autenticación
        Requiere autenticación para otras operaciones
        """
        if self.action in ['create', 'login','solicitar_reset_token', 'nueva_password']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        queryset = Usuario.objects.all()
        
        # Filtrar por rol si se proporciona en query params--cambios hehco por alejandro 
        rol_nombre = self.request.query_params.get('rol', None)
        if rol_nombre:
            queryset = queryset.filter(rol__nombre=rol_nombre)
        
        return self.filter_by_grupo(queryset)
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    @action(detail=True, methods=['post'])
    def cambiar_password(self, request, pk=None):
        usuario = self.get_object()
        nuevo_password = request.data.get('password')

        if not nuevo_password:
            return Response(
                {'error': 'La contraseña es requerida'},
                status=status.HTTP_400_BAD_REQUEST
            )

        usuario.set_password(nuevo_password)
        usuario.save()
        
        return Response({'message': 'Contraseña actualizada correctamente'}, status=status.HTTP_200_OK)



#si esto no funca solo eliminar la parte de las validaciones, lo hice para restringir los privilegios dependiendo del
#tipo de suscripcion
    def perform_create(self, serializer):

        usuario_nuevo = serializer.validated_data
        grupo = self.get_user_grupo()
        
        if grupo:
            suscripcion = getattr(grupo, 'suscripcion_info', None)
            
            if suscripcion and suscripcion.esta_activa: 
                plan = suscripcion.plan
                usuarios_actuales = Usuario.objects.filter(grupo=grupo).count()
                
                if usuarios_actuales >= plan.limite_usuarios:
                    raise ValidationError({
                        "error": f"Has alcanzado el límite de {plan.limite_usuarios} usuarios de tu plan '{plan.nombre}'. Actualiza tu suscripción para agregar más."
                    })
            else:
                raise ValidationError({"error": "Tu clínica no tiene una suscripción activa."})
        
        usuario_obj = serializer.save()
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Creó usuario {usuario_obj.nombre} (id:{usuario_obj.id})",
            objeto=f"Usuario: {usuario_obj.nombre} (id:{usuario_obj.id})",
            usuario=actor
        )




    def perform_destroy(self, instance):
        nombre = instance.nombre
        pk = instance.pk
        actor = get_actor_usuario_from_request(self.request)
        instance.delete()
        log_action(
            request=self.request,
            accion=f"Eliminó usuario {nombre} (id:{pk})",
            objeto=f"Usuario: {nombre} (id:{pk})",
            usuario=actor
        )

    @action(detail=False, methods=['post'])
    @permission_classes([AllowAny])
    def login(self, request):
        correo = request.data.get('correo')
        password = request.data.get('password')
        
        if not correo or not password:
            return Response(
                {"error": "Correo y password son requeridos"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=correo)
        except User.DoesNotExist:
            return Response(
                {"error": "Usuario no encontrado"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not user.check_password(password):
            return Response(
                {"error": "Contraseña incorrecta"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            usuario_perfil = Usuario.objects.get(correo=correo)
        except Usuario.DoesNotExist:
            return Response(
                {"error": "Perfil de usuario no encontrado"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if usuario_perfil.rol and usuario_perfil.rol.nombre == 'superAdmin':
            pass  # Super admin siempre puede acceder
        elif not usuario_perfil.puede_acceder_sistema():
            return Response(
                {"error": "Tu grupo no tiene acceso al sistema. Contacta al administrador."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        token, created = Token.objects.get_or_create(user=user)

        permiso_reportes = False
        try:
            # Verificamos si tiene grupo y suscripción vinculada
            if usuario_perfil.grupo and hasattr(usuario_perfil.grupo, 'suscripcion_info'):
                suscripcion = usuario_perfil.grupo.suscripcion_info
                if suscripcion.esta_activa:
                    permiso_reportes = suscripcion.plan.reportes
        except Exception as e:
            print(f"Error verificando permisos de reportes: {e}")
        
        
        actor = get_actor_usuario_from_request(request)
        log_action(
            request=request,
            accion=f"Inicio de sesión del usuario {usuario_perfil.nombre} (id:{usuario_perfil.id})",
            objeto=f"Usuario: {usuario_perfil.nombre} (id:{usuario_perfil.id})",
            usuario=usuario_perfil  # ✅ aquí va el usuario correcto
        )
        
        return Response(
            {
                "message": "Login exitoso",
                "usuario_id": usuario_perfil.id,
                "token": token.key,
                "rol": usuario_perfil.rol.nombre,  # Envía el valor interno, no el display
                "grupo_id": usuario_perfil.grupo.id if usuario_perfil.grupo else None,
                "grupo_nombre": usuario_perfil.grupo.nombre if usuario_perfil.grupo else None,
                "puede_acceder": usuario_perfil.puede_acceder_sistema(),
                "reportes":permiso_reportes
            },
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['post'])
    @permission_classes([IsAuthenticated])
    def logout(self, request):
        try:
            Token.objects.filter(user=request.user).delete()

            actor = get_actor_usuario_from_request(request)
            log_action(
                request=request,
                accion=f"Cierre de sesión del usuario {request.user.username}",
                objeto=f"Usuario: {request.user.username}",
                usuario=actor
            )

            return Response({"message": "Cierre de sesión exitoso"}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"Ocurrió un error al cerrar sesión: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    @action(detail=False, methods=['post'])
    @permission_classes([AllowAny])
    def solicitar_reset_token(self, request):
        correo = request.data.get('correo')
        if not correo:
            return Response(
                {"error": "El correo es requerido"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            usuario = Usuario.objects.get(correo=correo)
            token_recuperacion = secrets.token_urlsafe(16)
            usuario.token_reset_password = token_recuperacion
            usuario.save()

            send_mail(
                subject="Solicitud de restablecimiento de contraseña",
                message=(
                    f"Hola {usuario.nombre},\n\n"
                    f"Usa este token para restablecer tu contraseña:\n\n"
                    f"{token_recuperacion}\n\n"
                ),
                from_email="noreply@clinicavisionx.com",
                recipient_list=[usuario.correo],
                fail_silently=False,
            )

            return Response(
                {"message": "Token enviado al correo correctamente"},
                status=status.HTTP_200_OK
            )

        except Usuario.DoesNotExist:
            return Response(
                {"error": "No existe un usuario con ese correo"},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['post'])
    def nueva_password(self, request):
        correo = request.data.get('correo')
        token = request.data.get('reset_token')
        nueva_password = request.data.get('new_password')

        if not correo or not token or not nueva_password:
            return Response(
                {"error": "Correo, token y nueva contraseña son requeridos"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            usuario = Usuario.objects.get(
                correo=correo, token_reset_password=token
            )
            usuario.set_password(nueva_password)
            usuario.token_reset_password = ""
            usuario.save()
            user=User.objects.get(email=correo)
            user.set_password(nueva_password)
            user.save()

            return Response(
                {"message": "Contraseña actualizada correctamente"},
                status=status.HTTP_200_OK
            )

        except Usuario.DoesNotExist:
            return Response(
                {"error": "Token o correo inválido"},
                status=status.HTTP_404_NOT_FOUND
            )    


class BitacoraListAPIView(MultiTenantMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BitacoraSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Bitacora.objects.all()
        qs = self.filter_by_grupo(qs)
        
        # Filtros adicionales
        start = self.request.query_params.get('start')
        end = self.request.query_params.get('end')
        usuario = self.request.query_params.get('usuario')
        
        if start:
            sd = parse_date(start)
            if sd:
                qs = qs.filter(timestamp__date__gte=sd)
        if end:
            ed = parse_date(end)
            if ed:
                qs = qs.filter(timestamp__date__lte=ed)
        if usuario:
            if usuario.isdigit():
                qs = qs.filter(usuario__id=int(usuario))
            else:
                qs = qs.filter(usuario__nombre__icontains=usuario)
        return qs

class BitacoraViewSet(MultiTenantMixin, viewsets.ModelViewSet):
    serializer_class = BitacoraSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = Bitacora.objects.all()
        return self.filter_by_grupo(qs)
    

#nueva view necesaria para los pagos de las suscripciones gaaaa



class TieneSuscripcionActiva(permissions.BasePermission):
    
    def has_permissions(self, request, view):
        if not request.user.is_authenticated:
            return False
            
        usuario = getattr(request.user, 'usuario_perfil', None) 
        
        if not usuario or not usuario.grupo:
            return False
            
        try:
            suscripcion = usuario.grupo.suscripcion_info
            if suscripcion.esta_activa():
                return True
        except:
            pass
            
        return False 
