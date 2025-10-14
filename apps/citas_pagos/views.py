def get_dia_semana_es(fecha):
    dias_map = {
        'MONDAY': 'LUNES',
        'TUESDAY': 'MARTES',
        'WEDNESDAY': 'MIERCOLES',
        'THURSDAY': 'JUEVES',
        'FRIDAY': 'VIERNES',
        'SATURDAY': 'SABADO',
        'SUNDAY': 'DOMINGO',
    }
    import datetime
    dia_en = datetime.datetime.strptime(fecha, '%Y-%m-%d').strftime('%A').upper()
    return dias_map.get(dia_en)
from datetime import datetime
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework import generics
from rest_framework import permissions
from .models import *
from .serializers import *
class CitaMedicaViewSet(viewsets.ModelViewSet):

    def get_dia_semana_es(fecha):
        dias_map = {
        'MONDAY': 'LUNES',
        'TUESDAY': 'MARTES',
        'WEDNESDAY': 'MIERCOLES',
        'THURSDAY': 'JUEVES',
        'FRIDAY': 'VIERNES',
        'SATURDAY': 'SABADO',
        'SUNDAY': 'DOMINGO',
        }
        dia_en = datetime.strptime(fecha, '%Y-%m-%d').strftime('%A').upper()
        return dias_map.get(dia_en)

    queryset = Cita_Medica.objects.all()
    serializer_class = CitaMedicaSerializer

    def create(self, request, *args, **kwargs):
        data = request.data
        bloque_id = data.get('bloque_horario')
        fecha = data.get('fecha')
        hora_inicio = data.get('hora_inicio')
        hora_fin = data.get('hora_fin')

        # Validar bloque horario
        try:
            bloque = Bloque_Horario.objects.get(id=bloque_id)
        except Bloque_Horario.DoesNotExist:
            return Response({'error': 'Bloque horario no existe.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validar día de la semana (simplificado)
        dia_es = get_dia_semana_es(fecha)
        if bloque.dia_semana != dia_es:
            return Response({'error': f'La fecha corresponde a {dia_es}, pero el bloque es para {bloque.dia_semana}.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validar rango de hora
        if not (str(bloque.hora_inicio) <= hora_inicio < str(bloque.hora_fin) and str(bloque.hora_inicio) < hora_fin <= str(bloque.hora_fin)):
            return Response({'error': 'La hora de la cita está fuera del rango del bloque horario.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validar disponibilidad (no solapamiento)
        citas_existentes = Cita_Medica.objects.filter(
            bloque_horario=bloque,
            fecha=fecha,
            hora_inicio__lt=hora_fin,
            hora_fin__gt=hora_inicio
        )
        if citas_existentes.exists():
            return Response({'error': 'El médico ya tiene una cita en ese horario.'}, status=status.HTTP_400_BAD_REQUEST)

        return super().create(request, *args, **kwargs)
        
    def get_queryset(self):
        # Por defecto, solo pacientes cuyo usuario está activo
        if self.action == 'list':
            return Cita_Medica.objects.filter(estado=True)
        return Cita_Medica.objects.all()

    def perform_destroy(self, instance):
        # Soft delete: cambia estado del usuario a False
        instance.cita.estado = False
        instance.cita.save()

    @action(detail=False, methods=['get'])
    def eliminadas(self, request):
        # Pacientes cuyo usuario está inactivo
        eliminadas = Cita_Medica.objects.filter(estado=False)
        serializer = self.get_serializer(eliminadas, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def restaurar(self, request, pk=None):
        cita = self.get_object()
        cita.estado = True
        cita.save()
        serializer = self.get_serializer(cita)
        return Response(serializer.data, status=status.HTTP_200_OK)