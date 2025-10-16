from rest_framework import serializers
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.db import transaction
from .models import *
from django.db.models import Q
from apps.cuentas.models import Usuario, Rol
from apps.citas_pagos.models import Cita_Medica
#from apps.citas_pagos.serializers import HorarioDisponibleSerializer
#from apps.doctores.serializers import MedicoSerializer as BaseMedicoSerializer


class EspecialidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Especialidad
        fields = '__all__'

class MedicoSerializer(serializers.ModelSerializer):
    rol_nombre = serializers.CharField(source='rol.nombre', read_only=True)
    grupo_nombre = serializers.CharField(source='grupo.nombre', read_only=True)
    puede_acceder = serializers.SerializerMethodField()
    especialidades_nombres = serializers.SerializerMethodField()
    especialidades = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Especialidad.objects.all(),
        required=False
    )
    
    class Meta:
        model = Medico
        fields = '__all__'
        extra_kwargs = {
            'password': {'write_only': True},
            # REMUEVE 'grupo': {'required': True} - Ahora se asigna automáticamente
        }
    
    def get_puede_acceder(self, obj):
        return obj.puede_acceder_sistema()
    
    def get_especialidades_nombres(self, obj):
        return [esp.nombre for esp in obj.especialidades.all()]
    
    def update(self, instance, validated_data):
        # Extraer especialidades antes de actualizar
        especialidades_data = validated_data.pop('especialidades', None)
        
        # Hashear la contraseña si se proporciona
        password = validated_data.pop('password', None)
        if password:
            from django.contrib.auth.hashers import make_password
            validated_data['password'] = make_password(password)
        
        # Actualizar campos normales
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Actualizar especialidades si se proporcionaron
        if especialidades_data is not None:
            instance.especialidades.set(especialidades_data)
        
        return instance
    
    

class TipoAtencionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tipo_Atencion
        fields = '__all__'

class BloqueHorarioSerializer(serializers.ModelSerializer):
    """
    Gestiona la validación y serialización de los Bloques Horarios.
    """
    # --- Campos de solo lectura para respuestas GET amigables ---
    medico_nombre = serializers.CharField(source='medico.nombre', read_only=True)
    tipo_atencion_nombre = serializers.CharField(source='tipo_atencion.nombre', read_only=True)

    # --- Campo de escritura para recibir el ID del médico desde el frontend ---
    # `required=False` porque si el que crea es un médico, lo tomaremos de la sesión.
    medico = serializers.PrimaryKeyRelatedField(queryset=Medico.objects.all(), required=False)

    class Meta:
        model = Bloque_Horario
        fields = [
            'id', 'dia_semana', 'hora_inicio', 'hora_fin', 'duracion_cita_minutos',
            'max_citas_por_bloque', 'estado', 'tipo_atencion', 'tipo_atencion_nombre',
            'medico', 'medico_nombre', 'grupo'
        ]
        read_only_fields = ['grupo'] # Solo el grupo es siempre de solo lectura

    def validate(self, data):
        """
        Realiza todas las validaciones complejas en un solo lugar.
        """
        # --- 1. Determinar el médico para la validación ---
        medico_para_validar = data.get('medico')

        # Si el médico no viene en el formulario (porque el usuario logueado es médico),
        # lo obtenemos del contexto de la petición.
        if not medico_para_validar:
            try:
                medico_para_validar = Medico.objects.get(correo=self.context['request'].user.email)
            except Medico.DoesNotExist:
                # Esto sucede si un admin intenta crear un bloque SIN seleccionar un médico
                raise serializers.ValidationError({"medico": "Debe seleccionar un médico."})
        
        # --- 2. Validar que el tipo_atencion pertenezca al grupo del médico ---
        tipo_atencion = data.get('tipo_atencion')
        if tipo_atencion and tipo_atencion.grupo != medico_para_validar.grupo:
            raise serializers.ValidationError({
                "tipo_atencion": "El tipo de atención seleccionado no pertenece a la clínica del médico."
            })

        # --- 3. Validar que hora de inicio sea menor que hora de fin ---
        if data.get('hora_inicio') >= data.get('hora_fin'):
            raise serializers.ValidationError({"hora_fin": "La hora de fin debe ser posterior a la hora de inicio."})

        # --- 4. Validar que no haya solapamiento de horarios ---
        bloques_solapados = Bloque_Horario.objects.filter(
            medico=medico_para_validar,
            dia_semana=data.get('dia_semana'),
            hora_inicio__lt=data.get('hora_fin'),
            hora_fin__gt=data.get('hora_inicio')
        )
        # Si estamos editando (self.instance existe), excluimos el propio bloque de la comprobación
        if self.instance:
            bloques_solapados = bloques_solapados.exclude(pk=self.instance.pk)

        if bloques_solapados.exists():
            raise serializers.ValidationError("Conflicto de horario: El rango de tiempo se solapa con otro bloque existente para este médico.")

        return data

#para historial clinico
class MedicoResumenSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.CharField(source='usuario.nombre', read_only=True)
    especialidades = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='nombre'  # esto mostrará el nombre de cada especialidad
    )
    
    class Meta:
        model = MedicoSerializer.Meta.model  # Reusa el modelo Medico
        fields = [
            'id',
            'nombre_completo',
            'numero_colegiado',
            'especialidades'
        ]