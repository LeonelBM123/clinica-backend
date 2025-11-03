from django.urls import path
from . import views
from .views import download_backup_json_zip
urlpatterns = [
    #esta api es /api/reportes/pacientes_oloquesea/pdf/
    path('pacientes/pdf/', 
         views.generar_reporte_pacientes_pdf, 
         name='reporte_pacientes_pdf'),

    path('medicos/pdf/',
         views.generar_reporte_medicos_pdf,
         name='reporte_medico_pdf'),

    path('citas/pdf/',
         views.generar_reporte_citas_pdf,
         name='reporte_citas_pdf'),

    path('citas_dia/',
         views.reporte_citas_por_dia,
         name='reporte_citas_dia'),

    path('citas_excel/', 
         views.generar_reporte_citas_excel, 
         name='excel_reporte_citas'),

    path('pacientes_fechas/',
         views.reporte_pacientes_por_mes_json,
         name='reporte_pacientes_fechas'),

    path('pacientes_excel/',
         views.generar_reporte_pacientes_excel,
         name='pacientes_fechas_excel'),

     path('comando_voz/',
         views.procesar_comando_voz_json,
         name='procesar_comando_voz'),
         
     path("backup/json-zip", download_backup_json_zip, name="backup-json-zip"),
    

]