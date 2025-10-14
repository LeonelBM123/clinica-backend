from rest_framework import serializers
from .models import *
from apps.doctores.models import Bloque_Horario
from apps.historiasDiagnosticos.models import Paciente
from apps.cuentas.models import Grupo
from apps.doctores.models import Medico
from django.db.models import Q

class HorarioDisponibleSerializer(serializers.Serializer):
    bloque_horario_id = serializers.IntegerField()
    hora_inicio = serializers.TimeField(format='%H:%M')

class CitaMedicaSerializer(serializers.ModelSerializer):
    paciente_nombre = serializers.CharField(source='paciente.nombre', read_only=True)
    medico_nombre = serializers.CharField(source='bloque_horario.medico.nombre', read_only=True)
    
    paciente = serializers.PrimaryKeyRelatedField(
        queryset=Paciente.objects.filter(usuario__estado=True)
    )
    bloque_horario = serializers.PrimaryKeyRelatedField(
        queryset=Bloque_Horario.objects.filter(estado=True)
    )

    class Meta:
        model = Cita_Medica
        fields = [
            'id', 'fecha', 'hora_inicio', 'hora_fin', 'estado_cita', 'notas',
            'paciente', 'paciente_nombre', 'bloque_horario', 'medico_nombre',
            'grupo', 'motivo_cancelacion', 'calificacion', 'comentario_calificacion'
        ]
        read_only_fields = ['hora_fin', 'grupo', 'paciente_nombre', 'medico_nombre']

    def validate(self, data):
        bloque = data.get('bloque_horario')
        fecha = data.get('fecha')
        hora_inicio = data.get('hora_inicio')
        paciente = data.get('paciente')
        
        # 1. Validación de Grupo
        if paciente.grupo != bloque.grupo:
            raise serializers.ValidationError("El paciente y el médico no pertenecen a la misma clínica/grupo.")

        # 2. Validación de Día de la Semana
        DIAS_SEMANA_MAP = {0: 'LUNES', 1: 'MARTES', 2: 'MIÉRCOLES', 3: 'JUEVES', 4: 'VIERNES', 5: 'SÁBADO', 6: 'DOMINGO'}
        dia_semana_cita = DIAS_SEMANA_MAP.get(fecha.weekday())
        
        # CORRECCIÓN: Tu modelo usa 'MIERCOLES' sin tilde. Lo ajustamos para que coincida.
        if dia_semana_cita == 'MIÉRCOLES':
            dia_semana_cita = 'MIERCOLES'
            
        if dia_semana_cita != bloque.dia_semana:
             # Usamos getattr para mostrar el nombre amigable del día de forma segura
            nombre_dia_bloque = getattr(bloque, 'get_dia_semana_display', lambda: bloque.dia_semana)()
            raise serializers.ValidationError(
                f"La fecha seleccionada corresponde a un {dia_semana_cita}, pero el bloque horario es para los {nombre_dia_bloque}."
            )

        # Si estamos actualizando, no contamos la cita actual para el cupo máximo
        cita_actual = self.instance
        citas_query = Cita_Medica.objects.filter(
            bloque_horario=bloque,
            fecha=fecha
        ).exclude(estado_cita='CANCELADA')
        if cita_actual:
            citas_query = citas_query.exclude(pk=cita_actual.pk)

        # 3. Validación de Cupo Máximo
        if citas_query.count() >= bloque.max_citas_por_bloque:
            raise serializers.ValidationError("El cupo máximo de citas para este bloque y fecha ya ha sido alcanzado.")

        # 4. Validación de Horario Ocupado
        if citas_query.filter(hora_inicio=hora_inicio).exists():
             raise serializers.ValidationError("Este horario específico ya se encuentra ocupado.")

        # 5. Validación Matemática del Slot
        minutos_desde_inicio = (
            (hora_inicio.hour - bloque.hora_inicio.hour) * 60 +
            (hora_inicio.minute - bloque.hora_inicio.minute)
        )
        if minutos_desde_inicio < 0 or minutos_desde_inicio % bloque.duracion_cita_minutos != 0:
            raise serializers.ValidationError(
                f"La hora de inicio {hora_inicio.strftime('%H:%M')} no es un intervalo válido para este bloque."
            )

        return data