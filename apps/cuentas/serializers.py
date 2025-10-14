from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.db import transaction
from .models import *

class GrupoSerializer(serializers.ModelSerializer):
    admin_nombre = serializers.CharField(write_only=True, required=True)
    admin_correo = serializers.EmailField(write_only=True, required=True)
    admin_sexo = serializers.CharField(write_only=True, required=True)
    admin_fecha_nacimiento = serializers.DateField(write_only=True, required=True)
    admin_telefono = serializers.CharField(write_only=True, required=False, allow_blank=True)
    admin_direccion = serializers.CharField(write_only=True, required=False, allow_blank=True)
    admin_password = serializers.CharField(write_only=True, required=True)
    
    pagos_pendientes = serializers.SerializerMethodField()
    total_usuarios = serializers.SerializerMethodField()
    esta_moroso = serializers.SerializerMethodField()
    
    class Meta:
        model = Grupo
        fields = '__all__'
        extra_kwargs = {
            'admin_nombre': {'write_only': True},
            'admin_correo': {'write_only': True},
            'admin_sexo': {'write_only': True},
            'admin_fecha_nacimiento': {'write_only': True},
            'admin_telefono': {'write_only': True},
            'admin_direccion': {'write_only': True},
        }
    
    def get_pagos_pendientes(self, obj):
        return obj.pagos.filter(estado='PENDIENTE').count()
    
    def get_total_usuarios(self, obj):
        return obj.usuarios.filter(estado=True).count()
    
    def get_esta_moroso(self, obj):
        return obj.esta_moroso()

    @transaction.atomic
    def create(self, validated_data):
        admin_data = {
            'nombre': validated_data.pop('admin_nombre'),
            'correo': validated_data.pop('admin_correo'),
            'sexo': validated_data.pop('admin_sexo'),
            'fecha_nacimiento': validated_data.pop('admin_fecha_nacimiento'),
            'telefono': validated_data.pop('admin_telefono', ''),
            'direccion': validated_data.pop('admin_direccion', ''),
            'password': validated_data.pop('admin_password')
        }
        # Validar que el correo del admin no exista
        if Usuario.objects.filter(correo=admin_data['correo']).exists():
            raise serializers.ValidationError({'admin_correo': 'Ya existe un usuario con este correo electrónico'})
        if User.objects.filter(email=admin_data['correo']).exists():
            raise serializers.ValidationError({'admin_correo': 'Ya existe un usuario con este correo electrónico'})
        grupo = Grupo.objects.create(**validated_data)
        try:
            rol_admin = Rol.objects.get(nombre='administrador')
            django_user = User.objects.create_user(
                username=admin_data['correo'],
                email=admin_data['correo'],
                password=admin_data['password']
            )
            admin_usuario = Usuario.objects.create(
                grupo=grupo,
                nombre=admin_data['nombre'],
                password=make_password(admin_data['password']),
                correo=admin_data['correo'],
                sexo=admin_data['sexo'],
                fecha_nacimiento=admin_data['fecha_nacimiento'],
                telefono=admin_data['telefono'] or None,
                direccion=admin_data['direccion'] or None,
                rol=rol_admin,
                estado=True
            )
            return grupo
        except Rol.DoesNotExist:
            grupo.delete()
            raise serializers.ValidationError({'non_field_errors': 'No se encontró el rol de Administrador'})
        except Exception as e:
            grupo.delete()
            raise serializers.ValidationError({'non_field_errors': f'Error al crear el administrador: {str(e)}'})

class PagoSerializer(serializers.ModelSerializer):
    grupo_nombre = serializers.CharField(source='grupo.nombre', read_only=True)
    
    class Meta:
        model = Pago
        fields = '__all__'
    
    def create(self, validated_data):
        # Auto-asignar grupo del usuario actual si no se especifica
        request = self.context.get('request')
        if request and request.user:
            try:
                usuario_perfil = Usuario.objects.get(correo=request.user.email)
                if usuario_perfil.grupo and 'grupo' not in validated_data:
                    validated_data['grupo'] = usuario_perfil.grupo
            except Usuario.DoesNotExist:
                pass
        
        return super().create(validated_data)

class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rol
        fields = '__all__'

class UsuarioSerializer(serializers.ModelSerializer):
    # Mostrar el nombre del rol en lugar de solo el ID
    rol_nombre = serializers.CharField(source='rol.nombre', read_only=True)
    grupo_nombre = serializers.CharField(source='grupo.nombre', read_only=True)
    puede_acceder = serializers.SerializerMethodField()
    
    class Meta:
        model = Usuario
        fields = '__all__'
        extra_kwargs = {'password': {'write_only': True}}
    
    def get_puede_acceder(self, obj):
        return obj.puede_acceder_sistema()
    
    def validate(self, data):
        request = self.context.get('request')
        # Solo valida grupo si hay usuario autenticado
        if request and hasattr(request.user, 'email') and request.user.is_authenticated:
            try:
                usuario_creador = Usuario.objects.get(correo=request.user.email)
                # Si no es super admin, debe usar su mismo grupo
                if usuario_creador.rol.nombre != 'superAdmin':
                    if 'grupo' in data and data['grupo'] != usuario_creador.grupo:
                        raise serializers.ValidationError({
                            'grupo': 'No puedes registrar usuarios en otros grupos'
                        })
                    # Forzar el grupo del creador
                    data['grupo'] = usuario_creador.grupo
            except Usuario.DoesNotExist:
                pass
        # Si no hay usuario autenticado, no valida grupo
        return data
    
    def create(self, validated_data):
        request = self.context.get('request')
        # Solo asigna grupo si hay usuario autenticado
        if request and hasattr(request.user, 'email') and request.user.is_authenticated:
            try:
                usuario_creador = Usuario.objects.get(correo=request.user.email)
                if (usuario_creador.rol.nombre != 'superAdmin' and 
                    usuario_creador.grupo and 
                    'grupo' not in validated_data):
                    validated_data['grupo'] = usuario_creador.grupo
            except Usuario.DoesNotExist:
                pass
        
        password = validated_data.pop('password', None)
        if password:
            validated_data['password'] = make_password(password)
        
        # Crear el User de Django también
        if 'correo' in validated_data:
            User.objects.create_user(
                username=validated_data['correo'],
                email=validated_data['correo'],
                password=password or '123'
            )
        
        usuario = Usuario.objects.create(**validated_data)
        return usuario
    
    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        # Hashear la contraseña si se proporciona
        if password:
            validated_data['password'] = make_password(password)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class BitacoraSerializer(serializers.ModelSerializer):
    usuario = serializers.SerializerMethodField()
    grupo_nombre = serializers.CharField(source='grupo.nombre', default='', read_only=True)

    class Meta:
        model = Bitacora
        fields = ['id', 'usuario', 'grupo_nombre', 'accion', 'ip', 'objeto', 'extra', 'timestamp']

    def get_usuario(self, obj):
        # Si existe usuario, retorna el nombre, si no, retorna "Anónimo"
        return obj.usuario.nombre if obj.usuario else "Anónimo"
