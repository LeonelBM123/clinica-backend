from django.db import transaction
from django.apps import apps
from datetime import date, datetime
import locale
import sys
import time

# Imports locales
from .models import DimTiempo, DimMedico, DimEspecialidad, DimPaciente, DimEstadoCita, FactCitas

def run_etl():
    start_time = time.time()
    print("--- INICIO ETL (MODO TURBO FINAL) ---")
    
    # 1. OBTENER MODELOS
    try:
        CitaMedica = apps.get_model('citas_pagos', 'Cita_Medica') 
        Medico = apps.get_model('doctores', 'Medico')
        Especialidad = apps.get_model('doctores', 'Especialidad')
        Paciente = apps.get_model('historiasDiagnosticos', 'Paciente')
    except LookupError as e:
        print(f"ERROR CRÍTICO DE NOMBRES: {e}")
        raise e

    # Configuración Idioma
    try:
        locale.setlocale(locale.LC_TIME, 'es_ES' if sys.platform == 'win32' else 'es_ES.UTF-8') 
    except: pass

    # Usamos atomic para velocidad
    with transaction.atomic():
        
        # --- PASO 1: TIEMPO ---
        print("1. Procesando Tiempo...")
        fechas_origen = set(CitaMedica.objects.values_list('fecha', flat=True))
        fechas_destino = set(DimTiempo.objects.values_list('fecha', flat=True))
        fechas_nuevas = fechas_origen - fechas_destino
        
        if fechas_nuevas:
            objs_tiempo = []
            for fecha in fechas_nuevas:
                fecha_key = int(fecha.strftime('%Y%m%d'))
                es_finde = fecha.weekday() >= 5
                semestre = 1 if fecha.month <= 6 else 2
                trimestre = (fecha.month - 1) // 3 + 1
                objs_tiempo.append(DimTiempo(
                    fecha_key=fecha_key, fecha=fecha, anio=fecha.year, semestre=semestre,
                    trimestre=trimestre, mes=fecha.month, dia=fecha.day,
                    nombre_mes=fecha.strftime('%B').capitalize(),
                    dia_semana=fecha.weekday() + 1,
                    nombre_dia=fecha.strftime('%A').capitalize(),
                    es_fin_de_semana=es_finde
                ))
            DimTiempo.objects.bulk_create(objs_tiempo)
        
        mapa_tiempo = {d.fecha_key: d for d in DimTiempo.objects.all()}


        # --- PASO 2: MÉDICOS ---
        print("2. Procesando Médicos...")
        medicos_origen = Medico.objects.select_related('usuario_ptr').all()
        for m in medicos_origen:
            DimMedico.objects.update_or_create(
                id_medico_sistema=m.usuario_ptr_id,
                defaults={
                    'nombre_completo': m.usuario_ptr.nombre,
                    'numero_colegiado': getattr(m, 'numero_colegiado', 'S/N'),
                    'genero': getattr(m.usuario_ptr, 'sexo', 'X'),
                    'fecha_registro': m.usuario_ptr.fecha_registro
                }
            )
        mapa_medicos = {d.id_medico_sistema: d for d in DimMedico.objects.all()}


        # --- PASO 3: ESPECIALIDADES ---
        print("3. Procesando Especialidades...")
        for e in Especialidad.objects.all():
            DimEspecialidad.objects.update_or_create(
                id_especialidad_sistema=e.id, defaults={'nombre_especialidad': e.nombre}
            )
        mapa_especialidad = {d.id_especialidad_sistema: d for d in DimEspecialidad.objects.all()}
        esp_general, _ = DimEspecialidad.objects.get_or_create(id_especialidad_sistema=9999, defaults={'nombre_especialidad':'General'})


        # --- PASO 4: PACIENTES ---
        print("4. Procesando Pacientes...")
        for p in Paciente.objects.select_related('usuario').all():
            edad = (date.today() - p.usuario.fecha_nacimiento).days // 365 if p.usuario.fecha_nacimiento else 0
            grupo = 'Adulto'
            if edad <= 12: grupo = 'Niño'
            elif edad <= 18: grupo = 'Adolescente'
            elif edad > 60: grupo = 'Senior'

            DimPaciente.objects.update_or_create(
                id_paciente_sistema=p.id,
                defaults={
                    'numero_historia_clinica': p.numero_historia_clinica,
                    'nombre_completo': p.usuario.nombre,
                    'genero': getattr(p.usuario, 'sexo', 'X'),
                    'fecha_nacimiento': p.usuario.fecha_nacimiento or date(2000,1,1),
                    'grupo_etario': grupo
                }
            )
        mapa_pacientes = {d.id_paciente_sistema: d for d in DimPaciente.objects.all()}


        # --- PASO 5: ESTADOS ---
        print("5. Procesando Estados...")
        estados = [
            ('REALIZADA', 'Cita Realizada', False, True),  # <--- CAMBIADO DE 'COMPLETADA' A 'REALIZADA'
            ('CONFIRMADA', 'Confirmada', False, False),
            ('EN_PROCESO', 'En Atención', False, True),
            ('PENDIENTE', 'Pendiente', False, False),
            ('CANCELADA', 'Cancelada', True, False),
            ('NO_ASISTIO', 'No Asistió', True, False),
        ]
        for cod, desc, es_cancel, es_asist in estados:
            DimEstadoCita.objects.update_or_create(
                codigo_estado=cod, defaults={'descripcion_estado': desc, 'es_cancelacion': es_cancel, 'es_asistencia': es_asist}
            )
        mapa_estados = {d.codigo_estado: d for d in DimEstadoCita.objects.all()}
        estado_default = mapa_estados.get('PENDIENTE')


        # --- PASO 6: FACT CITAS ---
        print("6. Procesando Tabla de Hechos (FACT)...")
        
        ids_existentes = set(FactCitas.objects.values_list('id_cita_sistema', flat=True))
        
        citas_queryset = CitaMedica.objects.exclude(id__in=ids_existentes).select_related(
            'bloque_horario__medico', 'paciente', 'bloque_horario'
        ).prefetch_related('bloque_horario__medico__especialidades')

        nuevos_hechos = []
        BATCH_SIZE = 2000 
        total_citas = citas_queryset.count()
        print(f"-> {total_citas} citas nuevas detectadas.")

        # AQUÍ ESTABA EL ERROR: Agregamos chunk_size=2000
        for i, c in enumerate(citas_queryset.iterator(chunk_size=2000), 1):
            try:
                fecha_key = int(c.fecha.strftime('%Y%m%d'))
                obj_tiempo = mapa_tiempo.get(fecha_key)
                
                medico_id = c.bloque_horario.medico.usuario_ptr_id
                obj_medico = mapa_medicos.get(medico_id)
                
                obj_paciente = mapa_pacientes.get(c.paciente.id)
                
                estado_code = c.estado_cita if c.estado_cita else 'PENDIENTE'
                obj_estado = mapa_estados.get(estado_code, estado_default)

                obj_especialidad = esp_general
                esps = c.bloque_horario.medico.especialidades.all()
                if esps:
                    first_esp_id = esps[0].id
                    obj_especialidad = mapa_especialidad.get(first_esp_id, esp_general)

                duracion = 30
                if c.hora_inicio and c.hora_fin:
                    dummy = date.today()
                    duracion = (datetime.combine(dummy, c.hora_fin) - datetime.combine(dummy, c.hora_inicio)).seconds // 60
                
                anticipacion = (c.fecha - c.fecha_creacion.date()).days if c.fecha_creacion else 0

                if obj_tiempo and obj_medico and obj_paciente:
                    nuevos_hechos.append(FactCitas(
                        fecha_cita=obj_tiempo,
                        medico=obj_medico,
                        paciente=obj_paciente,
                        especialidad=obj_especialidad,
                        estado=obj_estado,
                        id_cita_sistema=c.id,
                        grupo_id=c.grupo_id,
                        hora_inicio=c.hora_inicio,
                        cantidad_citas=1,
                        duracion_minutos=duracion,
                        tiempo_anticipacion_dias=anticipacion
                    ))

                if len(nuevos_hechos) >= BATCH_SIZE:
                    FactCitas.objects.bulk_create(nuevos_hechos)
                    print(f"   Guardado lote de {BATCH_SIZE} registros... (Progreso: {i}/{total_citas})", end='\r')
                    nuevos_hechos = [] 

            except Exception as e:
                continue

        if nuevos_hechos:
            FactCitas.objects.bulk_create(nuevos_hechos)
    
    total_time = time.time() - start_time
    print(f"\n--- FIN ETL EXITOSO EN {total_time:.2f} SEGUNDOS ---")