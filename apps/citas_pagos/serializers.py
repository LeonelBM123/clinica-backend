from rest_framework import serializers
from .models import *
from django.db.models import Q

class CitaMedicaSerializer(serializers.ModelSerializer):
    paciente_nombre = serializers.CharField(source='paciente.nombre', read_only=True)
    medico_nombre = serializers.CharField(source='bloque_horario.medico.nombre', read_only=True)
    medico_id = serializers.IntegerField(source='bloque_horario.medico.id', read_only=True)
    tipo_atencion_nombre = serializers.CharField(source='bloque_horario.tipo_atencion.nombre', read_only=True)
    dia_semana = serializers.CharField(source='bloque_horario.dia_semana', read_only=True)
    
    class Meta:
        model = Cita_Medica
        fields = [
            'id', 'paciente', 'paciente_nombre', 'bloque_horario', 'fecha', 
            'hora_inicio', 'hora_fin', 'estado_cita', 'motivo_cancelacion', 
            'notas', 'fecha_creacion', 'fecha_modificacion', 'medico_nombre',
            'medico_id', 'tipo_atencion_nombre', 'dia_semana'
        ]
        read_only_fields = ['fecha_creacion', 'fecha_modificacion', 'estado_cita']

    def validate(self, data):
        """Validaciones personalizadas para crear/actualizar citas"""
        instance = self.instance
        
        # Validaciones para creación
        if not instance:
            bloque_horario = data.get('bloque_horario')
            fecha = data.get('fecha')
            hora_inicio = data.get('hora_inicio')
            hora_fin = data.get('hora_fin')
            
            if all([bloque_horario, fecha, hora_inicio, hora_fin]):
                self._validar_disponibilidad(bloque_horario, fecha, hora_inicio, hora_fin)
        
        return data

    def _validar_disponibilidad(self, bloque_horario, fecha, hora_inicio, hora_fin):
        """Valida que el horario esté disponible"""
        # Validar día de la semana
        dia_es = get_dia_semana_es(fecha.strftime('%Y-%m-%d'))
        if bloque_horario.dia_semana != dia_es:
            raise serializers.ValidationError(
                f'La fecha corresponde a {dia_es}, pero el bloque es para {bloque_horario.dia_semana}.'
            )
        
        # Validar rango de hora dentro del bloque
        if not (bloque_horario.hora_inicio <= hora_inicio < bloque_horario.hora_fin and 
                bloque_horario.hora_inicio < hora_fin <= bloque_horario.hora_fin):
            raise serializers.ValidationError(
                'La hora de la cita está fuera del rango del bloque horario.'
            )
        
        # Validar que no haya citas solapadas
        citas_existentes = Cita_Medica.objects.filter(
            bloque_horario=bloque_horario,
            fecha=fecha,
            estado=True
        ).filter(
            models.Q(hora_inicio__lt=hora_fin, hora_fin__gt=hora_inicio)
        )
        
        if citas_existentes.exists():
            raise serializers.ValidationError(
                'Ya existe una cita en ese horario para este médico.'
            )