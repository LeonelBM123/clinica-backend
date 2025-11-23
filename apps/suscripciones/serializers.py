from rest_framework import serializers
from .models import Plan, Suscripcion, PagoSuscripcion
from apps.cuentas.serializers import GrupoSerializer 

class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = '__all__'

class PagoSuscripcionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PagoSuscripcion
        fields = '__all__'

class SuscripcionSerializer(serializers.ModelSerializer):
    plan_detalle = PlanSerializer(source='plan', read_only=True)
    plan_id = serializers.PrimaryKeyRelatedField(
        queryset=Plan.objects.all(), 
        source='plan', 
        write_only=True
    )
    
    es_activa = serializers.BooleanField(source='esta_activa', read_only=True)
    dias_restantes = serializers.IntegerField(source='dias_restantes', read_only=True)
    nombre_grupo = serializers.CharField(source='grupo.nombre', read_only=True)

    class Meta:
        model = Suscripcion
        fields = [
            'id', 
            'grupo',       
            'nombre_grupo',
            'plan_id',    
            'plan_detalle',
            'estado', 
            'fecha_inicio', 
            'fecha_fin', 
            'renovacion_automatica',
            'es_activa',
            'dias_restantes'
        ]
        read_only_fields = ['fecha_inicio', 'fecha_fin', 'estado', 'grupo']

    def create(self, validated_data):
        return super().create(validated_data)