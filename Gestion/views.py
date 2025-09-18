# views.py
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, generics, permissions
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from .models import Usuario, Rol, Medico, Especialidad, Bitacora
from .serializers import UsuarioSerializer, RolSerializer, MedicoSerializer, EspecialidadSerializer, BitacoraSerializer
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from rest_framework.permissions import IsAuthenticated,AllowAny
from rest_framework.decorators import permission_classes
from django.utils.dateparse import parse_date
from .utils import log_action, get_actor_usuario_from_request
# viewsets.ModelViewSet automáticamente crea los CRUD endpoints:

class RolViewSet(viewsets.ModelViewSet):
    queryset = Rol.objects.all()
    serializer_class = RolSerializer
    
    # GET /api/roles/ - Lista todos los roles
    # POST /api/roles/ - Crea nuevo rol
    # GET /api/roles/{id}/ - Obtiene un rol
    # PUT /api/roles/{id}/ - Actualiza rol completo
    # PATCH /api/roles/{id}/ - Actualiza parcialmente
    # DELETE /api/roles/{id}/ - Elimina rol

class EspecialidadViewSet(viewsets.ModelViewSet):
    queryset = Especialidad.objects.all()
    serializer_class = EspecialidadSerializer
    
    # GET /api/especialidades/ - Lista todas las especialidades
    # POST /api/especialidades/ - Crea nueva especialidad
    # GET /api/especialidades/{id}/ - Obtiene una especialidad
    # PUT /api/especialidades/{id}/ - Actualiza especialidad completa
    # PATCH /api/especialidades/{id}/ - Actualiza parcialmente
    # DELETE /api/especialidades/{id}/ - Elimina especialidad

class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    
    # GET /api/usuarios/
    # POST /api/usuarios/
    # GET /api/usuarios/{id}/
    # PUT /api/usuarios/{id}/
    # PATCH /api/usuarios/{id}/
    # DELETE /api/usuarios/{id}/
    
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

        # Log de acción
        actor = get_actor_usuario_from_request(request)
        log_action(
            request=request,
            accion=f"Cambio de contraseña del usuario {usuario.nombre} (id:{usuario.id})",
            objeto=f"Usuario: {usuario.nombre} (id:{usuario.id})",
            usuario=actor
        )

        return Response({'message': 'Contraseña actualizada correctamente'}, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        """
        Crea un User cada vez que se crea un Usuario, sin asociarlo.
        """
        data = serializer.validated_data

        # Crear el User de Django (para login/tokens)
        User.objects.create_user(
            username=data["correo"],  
            email=data["correo"],
            password=data["password"]  
        )
        # Guardar el Usuario normalmente
        usuario_obj = serializer.save()

        # Log de acción
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Creó usuario {usuario_obj.nombre} (id:{usuario_obj.id})",
            objeto=f"Usuario: {usuario_obj.nombre} (id:{usuario_obj.id})",
            usuario=actor
        )

    def perform_update(self, serializer):
        usuario_obj = serializer.save()
        actor = get_actor_usuario_from_request(self.request)
        log_action(
            request=self.request,
            accion=f"Actualizó usuario {usuario_obj.nombre} (id:{usuario_obj.id})",
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
    def login(self, request):
        correo = request.data.get('correo')
        password = request.data.get('password')
        if not correo or not password:
            return Response(
                {"error": "Correo y password son requeridos"},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Buscar usuario en el modelo User usando el email
        user = get_object_or_404(User, email=correo)
        # Validar contraseña
        if not user.check_password(password):
            return Response(
                {"error": "Contraseña incorrecta"},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Obtener o crear token
        token, created = Token.objects.get_or_create(user=user)

        # Perfil extendido
        usuario_perfil = get_object_or_404(Usuario, correo=correo)

        # 🔥 Log de inicio de sesión
        actor = get_actor_usuario_from_request(request)
        log_action(
            request=request,
            accion=f"Inicio de sesión del usuario {usuario_perfil.nombre} (id:{usuario_perfil.id})",
            objeto=f"Usuario: {usuario_perfil.nombre} (id:{usuario_perfil.id})",
            usuario=actor
        )

        return Response(
            {
                "message": "Login exitoso",
                "usuario_id": usuario_perfil.id if usuario_perfil else None,
                "token": token.key,
                "rol": usuario_perfil.rol.get_nombre_display() if usuario_perfil and usuario_perfil.rol else None
            },
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def logout(self, request):
        try:
            actor = Usuario.objects.get(correo=request.user.email)
        except Usuario.DoesNotExist:
            actor = None

        log_action(
            request=request,
            accion=f"Cierre de sesión del usuario {actor.nombre} (id:{actor.id})" if actor else "Cierre de sesión de usuario anónimo",
            objeto=f"Usuario: {actor.nombre} (id:{actor.id})" if actor else "Usuario anónimo",
            usuario=actor
        )

        # Borrar token después de loggear
        if hasattr(request.user, 'auth_token'):
            request.user.auth_token.delete()

        return Response({"message": "Cierre de sesión exitoso"}, status=status.HTTP_200_OK)

class MedicoViewSet(viewsets.ModelViewSet):
    queryset = Medico.objects.all()
    serializer_class = MedicoSerializer
    
    # GET /api/medicos/
    # POST /api/medicos/
    # GET /api/medicos/{id}/
    # PUT /api/medicos/{id}/
    # PATCH /api/medicos/{id}/
    # DELETE /api/medicos/{id}/

    def perform_create(self, serializer):
        medico_obj = serializer.save()
        actor = get_actor_usuario_from_request(self.request)
        nombre = medico_obj.medico.nombre if medico_obj.medico else str(medico_obj)
        log_action(
            request=self.request,
            accion=f"Creó médico {nombre} (id:{medico_obj.id})",
            objeto=f"Medico: {nombre} (id:{medico_obj.id})",
            usuario=actor
        )

    def perform_update(self, serializer):
        medico_obj = serializer.save()
        actor = get_actor_usuario_from_request(self.request)
        nombre = medico_obj.medico.nombre if medico_obj.medico else str(medico_obj)
        log_action(
            request=self.request,
            accion=f"Actualizó médico {nombre} (id:{medico_obj.id})",
            objeto=f"Medico: {nombre} (id:{medico_obj.id})",
            usuario=actor
        )

    def perform_destroy(self, instance):
        nombre = instance.medico.nombre if instance.medico else str(instance)
        pk = instance.pk
        actor = get_actor_usuario_from_request(self.request)
        instance.delete()
        log_action(
            request=self.request,
            accion=f"Eliminó médico {nombre} (id:{pk})",
            objeto=f"Medico: {nombre} (id:{pk})",
            usuario=actor
        )


class BitacoraListAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]  # solo admins por seguridad
    serializer_class = BitacoraSerializer
    pagination_class = None  # puedes habilitar paginación si quieres

    def get_queryset(self):
        qs = Bitacora.objects.all()
        start = self.request.query_params.get('start')  # YYYY-MM-DD
        end = self.request.query_params.get('end')      # YYYY-MM-DD
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
            # filtra por id o por nombre parcial
            if usuario.isdigit():
                qs = qs.filter(usuario__id=int(usuario))
            else:
                qs = qs.filter(usuario__nombre__icontains=usuario)
        return qs