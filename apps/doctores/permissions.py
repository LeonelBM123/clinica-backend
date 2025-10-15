from rest_framework import permissions
from datetime import date
from .models import Medico 
from apps.citas_pagos.models import Cita_Medica 

# Mapeo de días de la semana para comparar con el weekday() de Python (Lunes=0, Domingo=6)
DIAS_SEMANA_ORDEN = ['LUNES', 'MARTES', 'MIÉRCOLES', 'JUEVES', 'VIERNES', 'SÁBADO', 'DOMINGO']

class CanEditOrDeleteBloqueHorario(permissions.BasePermission):
    """
    Permiso personalizado para controlar la edición y eliminación de Bloques Horarios.
    Reglas:
    1. Solo el médico propietario puede modificar su bloque.
    2. No se pueden modificar bloques de días pasados o del día actual.
    3. Bloques de mañana solo se pueden modificar si no tienen citas confirmadas.
    4. Bloques de días futuros (después de mañana) se pueden modificar libremente.
    """
    message = 'No tienes permiso para realizar esta acción.'

    def has_object_permission(self, request, view, obj):
        # El método GET, HEAD, OPTIONS siempre son permitidos a nivel de objeto
        if request.method in permissions.SAFE_METHODS:
            return True

        try:
            # 1. Verificar que el usuario sea el médico dueño del bloque
            medico_solicitante = Medico.objects.get(correo=request.user.email)
            if obj.medico != medico_solicitante:
                self.message = 'Solo puedes modificar tus propios bloques horarios.'
                return False
        except Medico.DoesNotExist:
            self.message = 'Usuario no encontrado o no es un médico.'
            return False

        # 2. Lógica de días
        hoy_int = date.today().weekday()  # Lunes=0, Martes=1, ...

        try:
            bloque_int = DIAS_SEMANA_ORDEN.index(obj.dia_semana.upper())
        except ValueError:
            # Esto no debería pasar si los choices del modelo son correctos
            self.message = 'Día de la semana inválido en el bloque horario.'
            return False

        # Regla 2: No modificar bloques de hoy o días pasados
        if bloque_int <= hoy_int:
            self.message = f'No puedes modificar horarios para hoy ({DIAS_SEMANA_ORDEN[hoy_int]}) o días pasados.'
            return False
        
        # Regla 3: Verificar citas para el día de mañana
        # El operador % 7 maneja el caso de Domingo (6) -> Lunes (0)
        manana_int = (hoy_int + 1) % 7
        if bloque_int == manana_int:
            # Buscamos citas que NO estén canceladas. Si existe al menos una, no se puede modificar.
            citas_existentes = Cita_Medica.objects.filter(
                bloque_horario=obj
            ).exclude(estado_cita='CANCELADA').exists()
            
            if citas_existentes:
                self.message = 'No puedes modificar este bloque porque ya tiene citas agendadas para mañana.'
                return False

        # Regla 4: Si es un día futuro (después de mañana), se permite
        return True