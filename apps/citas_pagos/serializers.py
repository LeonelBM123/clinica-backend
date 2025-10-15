from rest_framework import serializers
from .models import *

class CitaMedicaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cita_Medica
        fields = ['id',
                  'paciente',
                  'bloque_horario', 
                  'fecha', 
                  'hora_inicio',
                  'hora_fin',  
                  'motivo_cancelacion', 
                  'notas', 
                  'fecha_creacion', 
                  'fecha_modificacion']


class PacienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paciente
        fields = ['id', 'nombre', 'apellido', 'ci', 'telefono']


class CitaMedicaListSerializer(serializers.ModelSerializer):
    medico_nombre = serializers.CharField(source='bloque_horario.medico.nombre', read_only=True)
    medico_apellido = serializers.CharField(source='bloque_horario.medico.apellido', read_only=True)

    class Meta:
        model = Cita_Medica
        fields = [
            'id',
            'fecha',
            'hora_inicio',
            'hora_fin',
            'estado',
            'notas',
            'medico_nombre',
            'medico_apellido',
        ]


class CitaMedicaDetalleSerializer(serializers.ModelSerializer):
    paciente_nombre = serializers.CharField(source='paciente.nombre', read_only=True)
    paciente_apellido = serializers.CharField(source='paciente.apellido', read_only=True)
    medico_nombre = serializers.CharField(source='bloque_horario.medico.nombre', read_only=True)
    medico_apellido = serializers.CharField(source='bloque_horario.medico.apellido', read_only=True)

    class Meta:
        model = Cita_Medica
        fields = [
            'id',
            'fecha',
            'hora_inicio',
            'hora_fin',
            'estado',
            'notas',
            'motivo_cancelacion',
            'paciente_nombre',
            'paciente_apellido',
            'medico_nombre',
            'medico_apellido',
            'fecha_creacion',
            'fecha_modificacion'
        ]