from rest_framework import serializers
from .models import *
from datetime import datetime, timedelta
from apps.doctores.models import Bloque_Horario
from apps.historiasDiagnosticos.models import Paciente
from apps.cuentas.models import Grupo
from apps.doctores.models import Medico
from django.db.models import Q

class HorarioDisponibleSerializer(serializers.Serializer):
    bloque_horario_id = serializers.IntegerField()
    hora_inicio = serializers.TimeField(format='%H:%M')

class CitaMedicaSerializer(serializers.ModelSerializer):
    """
    Gestiona la validación y serialización completa de las Citas Médicas.
    """
    
    # --- Campos de solo lectura para enriquecer las respuestas GET ---
    paciente_nombre = serializers.CharField(source='paciente.usuario.nombre', read_only=True)
    medico_nombre = serializers.CharField(source='bloque_horario.medico.nombre', read_only=True)
    
    # --- Campos de escritura (los que se reciben desde el frontend) ---
    paciente = serializers.PrimaryKeyRelatedField(
        queryset=Paciente.objects.filter(usuario__estado=True),
        required=True # Hacemos el campo obligatorio
    )
    bloque_horario = serializers.PrimaryKeyRelatedField(
        queryset=Bloque_Horario.objects.filter(estado=True)
    )
    medico = serializers.PrimaryKeyRelatedField(
        source='bloque_horario.medico',
        read_only=True # El médico se obtiene del bloque, no se envía
    )

    class Meta:
        model = Cita_Medica
        fields = [
            'id', 'fecha', 'hora_inicio', 'hora_fin', 'estado_cita', 'notas',
            'paciente', 'paciente_nombre', 'bloque_horario', 'medico', 'medico_nombre',
            'grupo', 'motivo_cancelacion', 'calificacion', 'comentario_calificacion'
        ]
        # `hora_fin` y `grupo` son calculados o asignados por el servidor.
        read_only_fields = ['grupo', 'hora_fin', 'paciente_nombre', 'medico_nombre']

    def validate(self, data):
        """
        Realiza validaciones cruzadas para asegurar la integridad de la cita.
        """
        bloque = data.get('bloque_horario')
        fecha = data.get('fecha')
        hora_inicio = data.get('hora_inicio')
        paciente = data.get('paciente')
        
        # --- 1. Validación de Grupo (CORREGIDA) ---
        if paciente.usuario.grupo != bloque.medico.grupo:
            raise serializers.ValidationError({"detail": "El paciente y el médico no pertenecen a la misma clínica/grupo."})

        # --- 2. Validación de Día de la Semana ---
        DIAS_SEMANA_MAP = {0: 'LUNES', 1: 'MARTES', 2: 'MIERCOLES', 3: 'JUEVES', 4: 'VIERNES', 5: 'SABADO', 6: 'DOMINGO'}
        dia_semana_cita = DIAS_SEMANA_MAP.get(fecha.weekday())
        
        if dia_semana_cita != bloque.dia_semana:
            nombre_dia_bloque = getattr(bloque, 'get_dia_semana_display', lambda: bloque.dia_semana)()
            raise serializers.ValidationError({
                "fecha": f"La fecha seleccionada corresponde a un {dia_semana_cita}, pero el bloque horario es para los {nombre_dia_bloque}."
            })

        # --- El resto de tus validaciones están perfectas y no necesitan cambios ---
        citas_en_conflicto = Cita_Medica.objects.filter(
            bloque_horario__medico=bloque.medico,
            fecha=fecha
        ).exclude(estado_cita__in=['CANCELADA', 'NO_ASISTIO'])

        if self.instance:
            citas_en_conflicto = citas_en_conflicto.exclude(pk=self.instance.pk)

        if bloque.max_citas_por_bloque and citas_en_conflicto.filter(bloque_horario=bloque).count() >= bloque.max_citas_por_bloque:
            raise serializers.ValidationError({"detail": "El cupo máximo de citas para este bloque y fecha ya ha sido alcanzado."})

        if citas_en_conflicto.filter(hora_inicio=hora_inicio).exists():
            raise serializers.ValidationError({"hora_inicio": "Este horario específico ya se encuentra ocupado."})

        if not (bloque.hora_inicio <= hora_inicio < bloque.hora_fin):
            raise serializers.ValidationError({
                "hora_inicio": f"La hora {hora_inicio.strftime('%H:%M')} está fuera del rango del bloque horario ({bloque.hora_inicio.strftime('%H:%M')} - {bloque.hora_fin.strftime('%H:%M')})."
            })

        minutos_desde_inicio_bloque = (
            (hora_inicio.hour - bloque.hora_inicio.hour) * 60 +
            (hora_inicio.minute - bloque.hora_inicio.minute)
        )
        
        if minutos_desde_inicio_bloque % bloque.duracion_cita_minutos != 0:
            raise serializers.ValidationError({
                "hora_inicio": f"La hora de inicio {hora_inicio.strftime('%H:%M')} no es un intervalo válido. Los intervalos deben ser cada {bloque.duracion_cita_minutos} minutos."
            })

        return data

    def create(self, validated_data):
        """
        Calcula `hora_fin` y asigna `grupo` automáticamente antes de crear la cita.
        """
        bloque_horario = validated_data.get('bloque_horario')
        hora_inicio = validated_data.get('hora_inicio')
        fecha_cita = validated_data.get('fecha')
        
        # Calcular la hora de fin
        duracion_minutos = bloque_horario.duracion_cita_minutos
        hora_inicio_dt = datetime.combine(fecha_cita, hora_inicio)
        hora_fin_dt = hora_inicio_dt + timedelta(minutes=duracion_minutos)
        
        # Asignar los campos automáticos
        validated_data['hora_fin'] = hora_fin_dt.time()
        validated_data['grupo'] = bloque_horario.medico.grupo
        
        # Crear la cita con todos los datos
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """
        Calcula `hora_fin` si la hora de inicio o el bloque cambian.
        """
        bloque_horario = validated_data.get('bloque_horario', instance.bloque_horario)
        hora_inicio = validated_data.get('hora_inicio', instance.hora_inicio)
        fecha_cita = validated_data.get('fecha', instance.fecha)

        # Recalcular hora_fin solo si los datos relevantes han cambiado
        if 'hora_inicio' in validated_data or 'bloque_horario' in validated_data or 'fecha' in validated_data:
            duracion_minutos = bloque_horario.duracion_cita_minutos
            hora_inicio_dt = datetime.combine(fecha_cita, hora_inicio)
            hora_fin_dt = hora_inicio_dt + timedelta(minutes=duracion_minutos)
            validated_data['hora_fin'] = hora_fin_dt.time()
            
        return super().update(instance, validated_data)