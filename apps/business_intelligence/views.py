from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from django.db.models import Count, Avg, Sum, F, Case, When, IntegerField
from django.db.models.functions import ExtractHour, ExtractWeekDay
import traceback 
from django.apps import apps 
from datetime import datetime

# Imports locales
from .models import FactCitas
from .etl import run_etl 

class AnalyticsViewSet(viewsets.ViewSet):
    """
    Motor de Inteligencia de Negocios 'Clinical Intelligence'.
    Soporta filtrado dinámico y agregaciones complejas.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_usuario_sistema(self, request):
        try:
            Usuario = apps.get_model('cuentas', 'Usuario') 
            return Usuario.objects.get(correo=request.user.email)
        except Exception:
            return None

    def _aplicar_filtros(self, request, queryset):
        """
        Aplica filtros dinámicos basados en los QueryParams de la URL.
        """
        # 1. Rango de Fechas
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(fecha_cita__fecha__range=[start_date, end_date])

        # 2. Especialidad
        especialidad = request.query_params.get('especialidad')
        if especialidad:
            queryset = queryset.filter(especialidad__nombre_especialidad__icontains=especialidad)

        # 3. Médico (Nombre)
        medico = request.query_params.get('medico')
        if medico:
            queryset = queryset.filter(medico__nombre_completo__icontains=medico)

        # 4. Género del Médico
        sexo_medico = request.query_params.get('sexo_medico')
        if sexo_medico:
            queryset = queryset.filter(medico__genero=sexo_medico)

        return queryset

    @action(detail=False, methods=['post'], url_path='run-etl')
    def ejecutar_etl(self, request):
        usuario = self._get_usuario_sistema(request)
        tiene_permiso = False
        
        if request.user.is_superuser:
            tiene_permiso = True
        
        if usuario and usuario.rol:
            if usuario.rol.nombre in ['superAdmin', 'administrador']:
                tiene_permiso = True
            
        if not tiene_permiso:
             return Response({"error": "No tienes permisos para ejecutar el ETL."}, status=status.HTTP_403_FORBIDDEN)

        try:
            run_etl()
            return Response({"mensaje": "DataMart actualizado exitosamente."}, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"Error ETL: {e}")
            traceback.print_exc()
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard_kpi(self, request):
        try:
            # --- 1. SEGURIDAD & MULTI-TENANCY ---
            usuario = self._get_usuario_sistema(request)
            base_queryset = FactCitas.objects.none() 

            if request.user.is_superuser:
                base_queryset = FactCitas.objects.all()
            elif usuario:
                if usuario.rol and usuario.rol.nombre == 'superAdmin':
                    base_queryset = FactCitas.objects.all()
                elif usuario.grupo:
                    base_queryset = FactCitas.objects.filter(grupo_id=usuario.grupo.id)
                else:
                    return Response({"detail": "Usuario sin clínica asignada."}, status=status.HTTP_403_FORBIDDEN)
            else:
                return Response({"detail": "Perfil no encontrado."}, status=status.HTTP_403_FORBIDDEN)

            # --- 2. APLICAR FILTROS GLOBALES ---
            queryset = self._aplicar_filtros(request, base_queryset)
            total_citas = queryset.count()

            # Estructura de respuesta vacía si no hay datos
            if total_citas == 0:
                 return Response({"kpis": {"total_citas": 0}, "mensaje": "No hay datos con estos filtros"}, status=status.HTTP_200_OK)

            # ==========================================================
            # SECCIÓN 1: RESUMEN EJECUTIVO (KPIs Principales)
            # ==========================================================
            citas_realizadas = queryset.filter(estado__codigo_estado='REALIZADA').count()
            citas_canceladas = queryset.filter(estado__es_cancelacion=True).count()
            tasa_cancelacion = round((citas_canceladas / total_citas) * 100, 1) if total_citas > 0 else 0
            
            duracion_avg = queryset.filter(estado__codigo_estado='REALIZADA').aggregate(p=Avg('duracion_minutos'))['p']
            duracion_prom = round(duracion_avg, 1) if duracion_avg else 0

            tendencia = (
                queryset
                .values('fecha_cita__nombre_mes', 'fecha_cita__mes')
                .annotate(total=Count('cita_key'))
                .order_by('fecha_cita__mes')
            )

            top_medicos = (
                queryset.filter(estado__codigo_estado='REALIZADA')
                .values('medico__nombre_completo')
                .annotate(citas=Count('cita_key'))
                .order_by('-citas')[:5]
            )

            # ==========================================================
            # SECCIÓN 2: DEMOGRAFÍA (Radiografía del Paciente)
            # ==========================================================
            # Distribución por Grupo Etario
            dist_edad = (
                queryset
                .values('paciente__grupo_etario')
                .annotate(total=Count('cita_key'))
                .order_by('-total')
            )

            # Pirámide Poblacional (Sexo vs Edad)
            # Esto cuenta cuántos Hombres y Mujeres hay
            dist_sexo = (
                queryset
                .values('paciente__genero')
                .annotate(total=Count('cita_key'))
            )

            # ==========================================================
            # SECCIÓN 3: EFICIENCIA OPERATIVA (Heatmaps)
            # ==========================================================
            # Mapa de Calor: Día de la semana + Hora
            # Nota: ExtractHour saca la hora del TimeField
            heatmap_data = (
                queryset
                .annotate(hora=ExtractHour('hora_inicio'))
                .values('fecha_cita__nombre_dia', 'fecha_cita__dia_semana', 'hora')
                .annotate(cantidad=Count('cita_key'))
                .order_by('fecha_cita__dia_semana', 'hora')
            )

            # Duración por Especialidad (Para ver cuál tarda más)
            duracion_especialidad = (
                queryset.filter(estado__codigo_estado='REALIZADA')
                .values('especialidad__nombre_especialidad')
                .annotate(promedio_min=Avg('duracion_minutos'))
                .order_by('-promedio_min')
            )

            # ==========================================================
            # SECCIÓN 4: ANÁLISIS DE FUGAS (Cancelaciones)
            # ==========================================================
            cancelaciones_queryset = queryset.filter(estado__es_cancelacion=True)
            
            cancelaciones_por_motivo = (
                cancelaciones_queryset
                .values('estado__descripcion_estado') # Ej: Cancelada, No Asistió
                .annotate(total=Count('cita_key'))
                .order_by('-total')
            )

            cancelaciones_por_especialidad = (
                cancelaciones_queryset
                .values('especialidad__nombre_especialidad')
                .annotate(total=Count('cita_key'))
                .order_by('-total')[:5]
            )

            # --- ARMADO DE LA RESPUESTA ---
            response_data = {
                "filtros_aplicados": request.query_params,
                "resumen": {
                    "kpis": {
                        "total_citas": total_citas,
                        "realizadas": citas_realizadas,
                        "canceladas": citas_canceladas,
                        "tasa_cancelacion": tasa_cancelacion,
                        "duracion_promedio": duracion_prom
                    },
                    "tendencia": list(tendencia),
                    "top_medicos": list(top_medicos)
                },
                "demografia": {
                    "distribucion_edad": list(dist_edad),
                    "distribucion_sexo": list(dist_sexo)
                },
                "operaciones": {
                    "heatmap": list(heatmap_data),
                    "duracion_por_especialidad": list(duracion_especialidad)
                },
                "fugas": {
                    "por_motivo": list(cancelaciones_por_motivo),
                    "por_especialidad": list(cancelaciones_por_especialidad)
                }
            }
            
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            print("Error en Dashboard:", str(e))
            traceback.print_exc()
            return Response({"detail": "Error interno", "error_tecnico": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)