from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from rest_framework.authtoken.views import obtain_auth_token
urlpatterns = [
    path('', lambda request: HttpResponse(
        '<h1>API Clínica</h1>'
        '<p><a href="/admin/">Admin</a> | '
        '<a href="/api/doctores/">Doctores</a> | '
        '<a href="/api/citas/">Citas</a> | '
        '<a href="/api/cuentas/">Cuentas</a> | '
        '<a href="/api/diagnosticos/">Diagnosticos</a></p>'
    )),
    
    path('api-token-auth/', obtain_auth_token),# Endpoint para obtener el token de autenticación 
    path('admin/', admin.site.urls),
    path('api/cuentas/', include('apps.cuentas.urls')),
    path('api/doctores/', include('apps.doctores.urls')),
    path('api/citas_pagos/', include('apps.citas_pagos.urls')),
    path('api/diagnosticos/', include('apps.historiasDiagnosticos.urls')), 
    path('api/reportes/', include('apps.reportes.urls')),
    path('api/suscripciones/', include('apps.suscripciones.urls')),
    path('api/bi/', include('apps.business_intelligence.urls')),
]