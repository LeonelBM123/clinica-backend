from datetime import date
from rest_framework import serializers
from .models import *
from apps.citas_pagos.models import Cita_Medica
from apps.doctores.models import Medico, Especialidad
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
        queryset=Usuario.objects.filter(rol__nombre='paciente', estado=True)  
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

#para el historial clinico
class PacienteDetalleSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source='usuario.nombre', read_only=True)
    correo = serializers.CharField(source='usuario.correo', read_only=True)
    fecha_nacimiento = serializers.DateField(source='usuario.fecha_nacimiento', read_only=True)

    class Meta:
        model = Paciente
        fields = ['id', 'nombre', 'correo', 'fecha_nacimiento', 'numero_historia_clinica']
        
class ResultadoExamenesSerializer(serializers.ModelSerializer):
    paciente_nombre = serializers.CharField(source='paciente.usuario.nombre', read_only=True)
    medico_nombre = serializers.CharField(source='medico.nombre', read_only=True)
    class Meta:
        model = ResultadoExamenes
        fields = ['id', 'paciente', 'paciente_nombre', 'medico', 'medico_nombre',
        'tipo_examen', 'archivo_url', 'observaciones', 'estado']
        

#Serializer para Historial Clinico
# ---- Helpers ---------------------------------------------------------------

def _age_from_birthdate(dob):
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


# ---- Lite serializers ------------------------------------------------------

class UsuarioLiteSerializer(serializers.ModelSerializer):
    edad = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = (
            "id", "nombre", "correo", "sexo", "fecha_nacimiento",
            "telefono", "direccion", "estado", "fecha_registro", "ultimo_login",
            "edad",
        )

    def get_edad(self, obj):
        return _age_from_birthdate(obj.fecha_nacimiento)


class MedicoLiteSerializer(serializers.ModelSerializer):
    # nombres de especialidad, legibles
    especialidades = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field="nombre"
    )

    class Meta:
        model = Medico
        fields = ("id", "nombre", "numero_colegiado", "especialidades")# ajusta si tu Medico tiene otros campos públicos


# ---- Núcleo clínico --------------------------------------------------------

class TratamientoLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TratamientoMedicacion
        fields = ("id", "nombre", "descripcion", "duracion_dias")


class PatologiaWithTratamientosSerializer(serializers.ModelSerializer):
    tratamientos = TratamientoLiteSerializer(many=True, read_only=True)

    class Meta:
        model = PatologiasO
        fields = (
            "id", "nombre", "alias", "descripcion", "gravedad", "estado",
            "tratamientos",
        )


class ResultadoExamenSerializer(serializers.ModelSerializer):
    medico = MedicoLiteSerializer()

    class Meta:
        model = ResultadoExamenes
        fields = (
            "id", "tipo_examen", "archivo_url", "observaciones",
            "estado", "fecha_creacion", "fecha_actualizacion", "medico",
        )


class PacienteCoreSerializer(serializers.ModelSerializer):
    usuario = UsuarioLiteSerializer()

    class Meta:
        model = Paciente
        fields = (
            "id", "numero_historia_clinica", "usuario",
            "agudeza_visual_derecho", "agudeza_visual_izquierdo",
            "presion_ocular_derecho", "presion_ocular_izquierdo",
            "fecha_creacion", "fecha_modificacion",
        )


# ---- Historia clínica (agregada) ------------------------------------------

class PatientHistorySerializer(serializers.Serializer):
    paciente = PacienteCoreSerializer()
    patologias = PatologiaWithTratamientosSerializer(many=True)
    resultados_examenes = ResultadoExamenSerializer(many=True)

    # métricas útiles
    total_patologias = serializers.IntegerField()
    total_resultados = serializers.IntegerField()
    ultimo_examen_en = serializers.DateTimeField(allow_null=True)