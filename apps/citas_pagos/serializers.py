# en apps/citas/serializers.py
from rest_framework import serializers
from .models import *
from apps.doctores.models import Bloque_Horario
from apps.historiasDiagnosticos.models import Paciente
from apps.cuentas.models import Grupo
from apps.doctores.models import Medico
from django.db.models import Q
from apps.doctores.serializers import MedicoResumenSerializer
from datetime import datetime, timedelta



class HorarioDisponibleSerializer(serializers.Serializer):
    bloque_horario_id = serializers.IntegerField()
    hora_inicio = serializers.TimeField(format='%H:%M')

class CitaMedicaSerializer(serializers.ModelSerializer):
    paciente_nombre = serializers.CharField(source='paciente.usuario.nombre', read_only=True)
    medico_nombre = serializers.CharField(source='bloque_horario.medico.nombre', read_only=True)
    
    paciente = serializers.PrimaryKeyRelatedField(
        queryset=Paciente.objects.filter(usuario__estado=True),
        required=True
    )
    bloque_horario = serializers.PrimaryKeyRelatedField(
        queryset=Bloque_Horario.objects.filter(estado=True),
        required=True # Obligatorio para POST (crear)
    )
    medico = serializers.PrimaryKeyRelatedField(
        source='bloque_horario.medico',
        read_only=True
    )

    class Meta:
        model = Cita_Medica
        fields = [
            'id', 'fecha', 'hora_inicio', 'hora_fin', 'estado_cita', 'notas',
            'paciente', 'paciente_nombre', 'bloque_horario', 'medico', 'medico_nombre',
            'grupo', 'motivo_cancelacion', 'calificacion', 'comentario_calificacion',
            'reporte'
        ]
        read_only_fields = ['grupo', 'hora_fin', 'paciente_nombre', 'medico_nombre']

    def validate(self, data):
        """
        Realiza validaciones cruzadas para asegurar la integridad de la cita.
        AHORA ES CONSCIENTE DE PETICIONES PATCH.
        """
        # --- NUEVA LÓGICA DE DETECCIÓN DE PATCH ---
        # 1. Comprobar si estamos cambiando campos de programación (agendamiento)
        scheduling_fields_present = (
            'bloque_horario' in data or
            'paciente' in data or
            'fecha' in data or
            'hora_inicio' in data
        )

        # 2. Si NO estamos cambiando nada de la programación (ej. solo 'reporte' o 'estado_cita'),
        #    omitimos todas las validaciones de horarios y salimos.
        #    Esto previene el crash del Error 500.
        if not scheduling_fields_present:
            return data

        # --- SI LLEGAMOS AQUÍ, ES PORQUE SÍ ESTAMOS CAMBIANDO LA PROGRAMACIÓN ---

        # 3. Obtenemos la instancia (la cita actual) si existe (en un PATCH/PUT)
        instance = self.instance

        # 4. Cargamos el conjunto COMPLETO de datos de programación,
        #    usando el nuevo valor de 'data' o el valor antiguo de 'instance'.

        bloque = data.get('bloque_horario', getattr(instance, 'bloque_horario', None))
        paciente = data.get('paciente', getattr(instance, 'paciente', None))
        fecha = data.get('fecha', getattr(instance, 'fecha', None))
        hora_inicio = data.get('hora_inicio', getattr(instance, 'hora_inicio', None))

        # 5. Si después de todo esto, algún dato clave falta (ej. en un POST incompleto),
        #    las validaciones a nivel de campo (required=True) lo detectarán ANTES de llegar aquí.
        #    Aquí solo validamos si tenemos todos los datos para las validaciones cruzadas.
        if not all([bloque, paciente, fecha, hora_inicio]):
            # Esto no debería pasar en un POST válido, pero es una salvaguarda.
            # En un PATCH sin estos campos, ya habríamos retornado antes.
            return data

        # --- AHORA TUS VALIDACIONES ANTERIORES PUEDEN CORRER DE FORMA SEGURA ---

        # --- 1. Validación de Grupo ---
        # (Asegurarnos que paciente y bloque tengan usuario y médico cargados)
        if hasattr(paciente, 'usuario') and hasattr(bloque, 'medico') and paciente.usuario and bloque.medico:
            if paciente.usuario.grupo != bloque.medico.grupo:
                raise serializers.ValidationError({"detail": "El paciente y el médico no pertenecen a la misma clínica/grupo."})
        else:
             # Si no podemos validar el grupo por falta de datos, podríamos lanzar error o simplemente continuar
             # dependiendo de la lógica de negocio. Por seguridad, lancemos un error si falta info esencial.
             if not hasattr(paciente, 'usuario') or not paciente.usuario:
                 raise serializers.ValidationError({"paciente": "No se pudo determinar el grupo del paciente."})
             if not hasattr(bloque, 'medico') or not bloque.medico:
                 raise serializers.ValidationError({"bloque_horario": "No se pudo determinar el grupo del médico."})


        DIAS_SEMANA_MAP = {0: 'LUNES', 1: 'MARTES', 2: 'MIÉRCOLES', 3: 'JUEVES', 4: 'VIERNES', 5: 'SÁBADO', 6: 'DOMINGO'}
        dia_semana_cita = DIAS_SEMANA_MAP.get(fecha.weekday())

        if dia_semana_cita != bloque.dia_semana:
            nombre_dia_bloque = getattr(bloque, 'get_dia_semana_display', lambda: bloque.dia_semana)()
            raise serializers.ValidationError(
                f"La fecha seleccionada corresponde a un {dia_semana_cita}, pero el bloque horario es para los {nombre_dia_bloque}."
            )

        # --- El resto de tus validaciones (sin cambios, ahora son seguras) ---
        citas_en_conflicto = Cita_Medica.objects.filter(
            bloque_horario__medico=bloque.medico,
            fecha=fecha
        ).exclude(estado_cita='CANCELADA')
        if cita_actual:
            citas_query = citas_query.exclude(pk=cita_actual.pk)

        if citas_query.count() >= bloque.max_citas_por_bloque:
            raise serializers.ValidationError("El cupo máximo de citas para este bloque y fecha ya ha sido alcanzado.")

        if bloque.max_citas_por_bloque is not None and citas_en_conflicto.filter(bloque_horario=bloque).count() >= bloque.max_citas_por_bloque:
            raise serializers.ValidationError({"detail": "El cupo máximo de citas para este bloque y fecha ya ha sido alcanzado."})

        if citas_en_conflicto.filter(hora_inicio=hora_inicio).exists():
            raise serializers.ValidationError({"hora_inicio": "Este horario específico ya se encuentra ocupado."})

        if not (bloque.hora_inicio <= hora_inicio < bloque.hora_fin):
            raise serializers.ValidationError({
                "hora_inicio": f"La hora {hora_inicio.strftime('%H:%M')} está fuera del rango del bloque horario ({bloque.hora_inicio.strftime('%H:%M')} - {bloque.hora_fin.strftime('%H:%M')})."
            })

        # Asegurarse que duracion_cita_minutos no sea None o 0 antes de la división
        if bloque.duracion_cita_minutos and bloque.duracion_cita_minutos > 0:
            minutos_desde_inicio_bloque = (
                (hora_inicio.hour - bloque.hora_inicio.hour) * 60 +
                (hora_inicio.minute - bloque.hora_inicio.minute)
            )

            if minutos_desde_inicio_bloque % bloque.duracion_cita_minutos != 0:
                raise serializers.ValidationError({
                    "hora_inicio": f"La hora de inicio {hora_inicio.strftime('%H:%M')} no es un intervalo válido. Los intervalos deben ser cada {bloque.duracion_cita_minutos} minutos."
                })
        elif bloque.duracion_cita_minutos is None or bloque.duracion_cita_minutos <= 0:
             # Si la duración es inválida, no se puede validar el intervalo. Lanza error.
             raise serializers.ValidationError({"bloque_horario": "La duración de la cita para este bloque horario no es válida."})


        return data


    def create(self, validated_data):
        """
        Calcula `hora_fin` y asigna `grupo` automáticamente antes de crear la cita.
        """
        bloque_horario = validated_data.get('bloque_horario')
        hora_inicio = validated_data.get('hora_inicio')
        fecha_cita = validated_data.get('fecha')

        # Calcular la hora de fin (asegurarse que duracion_cita_minutos tiene un valor)
        duracion_minutos = bloque_horario.duracion_cita_minutos if bloque_horario.duracion_cita_minutos else 30 # Valor por defecto si es None
        hora_inicio_dt = datetime.combine(fecha_cita, hora_inicio)
        hora_fin_dt = hora_inicio_dt + timedelta(minutes=duracion_minutos)

        validated_data['hora_fin'] = hora_fin_dt.time()
        validated_data['grupo'] = bloque_horario.medico.grupo

        return super().create(validated_data)

#para el historial clinico 
class CitaMedicaDetalleSerializer(serializers.ModelSerializer):
    paciente_nombre = serializers.CharField(source='paciente.usuario.nombre', read_only=True)
    medico = MedicoResumenSerializer(source='bloque_horario.medico', read_only=True)

    class Meta:
        model = Cita_Medica
        fields = '__all__'

    def update(self, instance, validated_data):
        bloque_horario = validated_data.get('bloque_horario', instance.bloque_horario)
        hora_inicio = validated_data.get('hora_inicio', instance.hora_inicio)
        fecha_cita = validated_data.get('fecha', instance.fecha)

        # Recalcular hora_fin solo si los datos relevantes han cambiado
        if 'hora_inicio' in validated_data or 'bloque_horario' in validated_data or 'fecha' in validated_data:
            duracion_minutos = (
                bloque_horario.duracion_cita_minutos
                if bloque_horario.duracion_cita_minutos
                else 30
            )
            hora_inicio_dt = datetime.combine(fecha_cita, hora_inicio)
            hora_fin_dt = hora_inicio_dt + timedelta(minutes=duracion_minutos)
            validated_data['hora_fin'] = hora_fin_dt.time()

        return super().update(instance, validated_data)
