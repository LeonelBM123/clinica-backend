from django.urls import path
from . import views

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
    path('citas-excel/', 
         views.generar_reporte_citas_excel, 
         name='excel_reporte_citas'),
    

]