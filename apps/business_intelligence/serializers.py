from rest_framework import serializers
from .models import FactCitas

class KPISerializer(serializers.Serializer):
    total_citas = serializers.IntegerField()
    citas_realizadas = serializers.IntegerField()
    tasa_cancelacion = serializers.FloatField()
    duracion_promedio = serializers.FloatField()
    
class RankingMedicoSerializer(serializers.Serializer):
    medico = serializers.CharField()
    citas = serializers.IntegerField()

class TendenciaMensualSerializer(serializers.Serializer):
    mes = serializers.CharField()
    total = serializers.IntegerField()