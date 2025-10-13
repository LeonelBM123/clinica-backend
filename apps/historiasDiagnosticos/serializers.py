from rest_framework import serializers
from .models import *

class PatologiasOSerializer(serializers.ModelSerializer):
    grupo_nombre = serializers.CharField(source='grupo.nombre', read_only=True)
    
    class Meta:
        model = PatologiasO
        fields = '__all__'
        read_only_fields = ['grupo']  # El grupo se asigna automáticamente

class TratamientoMedicacionSerializer(serializers.ModelSerializer):
    grupo_nombre = serializers.CharField(source='grupo.nombre', read_only=True)
    patologias = serializers.PrimaryKeyRelatedField(
        queryset=PatologiasO.objects.all(),
        many=True,
        required=False,
    )
    patologias_nombres = serializers.SerializerMethodField()  # <-- NUEVO
    
    class Meta:
        model = TratamientoMedicacion
        fields = '__all__'
        read_only_fields = ['grupo']  # El grupo se asigna automáticamente

    def get_patologias_nombres(self, obj):
        return [p.nombre for p in obj.patologias.all()]

class PacienteSerializer(serializers.ModelSerializer):
    usuario = serializers.PrimaryKeyRelatedField(
        queryset=Usuario.objects.filter(rol__nombre='paciente')  
    )
    nombre = serializers.CharField(source='usuario.nombre', read_only=True)
    correo = serializers.CharField(source='usuario.correo', read_only=True)
    fecha_nacimiento = serializers.DateField(source='usuario.fecha_nacimiento', read_only=True)
    patologias = serializers.PrimaryKeyRelatedField(
        queryset=PatologiasO.objects.all(),
        many=True,
        required=False,
    )
    
    class Meta:
        model = Paciente
        fields = [
            'id',
            'usuario',
            'nombre',
            'correo',
            'fecha_nacimiento',
            'numero_historia_clinica',
            'patologias',
            'agudeza_visual_derecho',
            'agudeza_visual_izquierdo',
            'presion_ocular_derecho',
            'presion_ocular_izquierdo',
            'fecha_creacion',
            'fecha_modificacion',
        ]

