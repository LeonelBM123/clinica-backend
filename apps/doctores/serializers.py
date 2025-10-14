from rest_framework import serializers
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.db import transaction
from .models import *
from django.db.models import Q
from apps.cuentas.models import Usuario, Rol

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
    medico_nombre = serializers.CharField(source='medico.nombre', read_only=True)
    tipo_atencion_nombre = serializers.SerializerMethodField()
    puede_modificar = serializers.SerializerMethodField()
    motivo_no_modificable = serializers.SerializerMethodField()

    class Meta:
        model = Bloque_Horario
        fields = '__all__'

    def get_tipo_atencion_nombre(self, obj):
        # Evita AttributeError si tipo_atencion es None
        return getattr(obj.tipo_atencion, 'nombre', None)

    def get_puede_modificar(self, obj):
        return self._puede_modificar_bloque(obj)

    def get_motivo_no_modificable(self, obj):
        if self._puede_modificar_bloque(obj):
            return None

        orden_dias = ['LUNES', 'MARTES', 'MIERCOLES', 'JUEVES', 'VIERNES', 'SABADO', 'DOMINGO']
        DIAS_ANTICIPACION = 2

        hoy = datetime.now().date()
        fecha_limite = hoy + timedelta(days=DIAS_ANTICIPACION)
        dia_limite_index = fecha_limite.weekday()

        try:
            dia_bloque_index = orden_dias.index(obj.dia_semana)
        except (ValueError, TypeError):
            return "Bloque con día inválido, no se puede modificar"

        if dia_bloque_index < dia_limite_index:
            return f"No se puede modificar bloques de {obj.dia_semana} con menos de {DIAS_ANTICIPACION} días de anticipación"

        return "No se puede modificar por reglas del sistema"

    def _puede_modificar_bloque(self, bloque):
        orden_dias = ['LUNES', 'MARTES', 'MIERCOLES', 'JUEVES', 'VIERNES', 'SABADO', 'DOMINGO']
        DIAS_ANTICIPACION = 2
        hoy = datetime.now().date()
        fecha_limite = hoy + timedelta(days=DIAS_ANTICIPACION)
        dia_limite_index = fecha_limite.weekday()

        try:
            dia_bloque_index = orden_dias.index(bloque.dia_semana)
        except (ValueError, TypeError):
            return False

        return dia_bloque_index >= dia_limite_index

    def validate(self, data):
        instance = self.instance  # None si es create

        # Validar hora_fin > hora_inicio
        if data.get('hora_inicio') and data.get('hora_fin'):
            if data['hora_inicio'] >= data['hora_fin']:
                raise serializers.ValidationError({
                    "hora_fin": "La hora de fin debe ser posterior a la hora de inicio"
                })

        # Validar máximo posible de citas
        if data.get('hora_inicio') and data.get('hora_fin') and data.get('duracion_cita_minutos'):
            inicio = datetime.combine(datetime.today(), data['hora_inicio'])
            fin = datetime.combine(datetime.today(), data['hora_fin'])
            duracion_total = (fin - inicio).total_seconds() / 60
            duracion_cita = data.get('duracion_cita_minutos', 30)
            max_posible = duracion_total // duracion_cita
            max_citas = data.get('max_citas_por_bloque', 10)

            if max_citas > max_posible:
                raise serializers.ValidationError({
                    "max_citas_por_bloque": f"Máximo posible: {int(max_posible)} citas para este bloque"
                })

        # Validar duración mínima
        if data.get('hora_inicio') and data.get('hora_fin'):
            inicio = datetime.combine(datetime.today(), data['hora_inicio'])
            fin = datetime.combine(datetime.today(), data['hora_fin'])
            duracion_minutos = (fin - inicio).total_seconds() / 60
            if duracion_minutos < 30:
                raise serializers.ValidationError({
                    "duracion": "La duración mínima del bloque debe ser de 30 minutos"
                })

        # Validar solapamiento
        if self._hay_solapamiento(data, instance):
            raise serializers.ValidationError({
                "horario": "El horario se solapa con otro bloque existente del mismo médico"
            })

        return data

    def _hay_solapamiento(self, data, instance):
        medico = data.get('medico') or (instance.medico if instance else None)
        dia_semana = data.get('dia_semana') or (instance.dia_semana if instance else None)
        hora_inicio = data.get('hora_inicio') or (instance.hora_inicio if instance else None)
        hora_fin = data.get('hora_fin') or (instance.hora_fin if instance else None)

        if not all([medico, dia_semana, hora_inicio, hora_fin]):
            return False

        solapamientos = Bloque_Horario.objects.filter(
            medico=medico,
            dia_semana=dia_semana,
            estado=True
        ).exclude(pk=instance.pk if instance else None).filter(
            Q(hora_inicio__lt=hora_fin, hora_fin__gt=hora_inicio)
        )

        return solapamientos.exists()