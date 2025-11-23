from django.db import models

# ==========================================
# DIMENSIONES
# ==========================================

class DimTiempo(models.Model):
    fecha_key = models.IntegerField(primary_key=True, help_text="Formato YYYYMMDD")
    fecha = models.DateField()
    anio = models.IntegerField()
    semestre = models.IntegerField()
    trimestre = models.IntegerField()
    mes = models.IntegerField()
    nombre_mes = models.CharField(max_length=20)
    dia = models.IntegerField()
    dia_semana = models.IntegerField()
    nombre_dia = models.CharField(max_length=20)
    es_fin_de_semana = models.BooleanField()

    class Meta:
        db_table = 'dim_tiempo'

class DimMedico(models.Model):
    medico_key = models.AutoField(primary_key=True)
    id_medico_sistema = models.IntegerField()  # ID original
    nombre_completo = models.CharField(max_length=200)
    numero_colegiado = models.CharField(max_length=50)
    genero = models.CharField(max_length=1, null=True)
    fecha_registro = models.DateTimeField(null=True)

    class Meta:
        db_table = 'dim_medico'

class DimEspecialidad(models.Model):
    especialidad_key = models.AutoField(primary_key=True)
    id_especialidad_sistema = models.IntegerField()
    nombre_especialidad = models.CharField(max_length=100)

    class Meta:
        db_table = 'dim_especialidad'

class DimPaciente(models.Model):
    paciente_key = models.AutoField(primary_key=True)
    id_paciente_sistema = models.IntegerField()
    numero_historia_clinica = models.CharField(max_length=50)
    nombre_completo = models.CharField(max_length=200)
    genero = models.CharField(max_length=1, null=True)
    fecha_nacimiento = models.DateField(null=True)
    grupo_etario = models.CharField(max_length=20)  # Niño, Adulto, etc.

    class Meta:
        db_table = 'dim_paciente'

class DimEstadoCita(models.Model):
    estado_key = models.AutoField(primary_key=True)
    codigo_estado = models.CharField(max_length=50) # REALIZADA, CANCELADA...
    descripcion_estado = models.CharField(max_length=100)
    es_cancelacion = models.BooleanField(default=False)
    es_asistencia = models.BooleanField(default=False)

    class Meta:
        db_table = 'dim_estado_cita'

# ==========================================
# TABLA DE HECHOS
# ==========================================

class FactCitas(models.Model):
    cita_key = models.AutoField(primary_key=True)
    
    # --- MULTI-TENANCY (CRÍTICO PARA SAAS) ---
    # Usamos IntegerField en lugar de ForeignKey para desacoplar el DataMart
    # db_index=True es vital para la velocidad de los reportes
    grupo_id = models.IntegerField(default=1, db_index=True, help_text="ID de la Clínica (Tenant)")
    
    # Relaciones (Foreign Keys a Dimensiones)
    fecha_cita = models.ForeignKey(DimTiempo, on_delete=models.CASCADE, db_column='fecha_cita_key')
    medico = models.ForeignKey(DimMedico, on_delete=models.CASCADE, db_column='medico_key')
    paciente = models.ForeignKey(DimPaciente, on_delete=models.CASCADE, db_column='paciente_key')
    especialidad = models.ForeignKey(DimEspecialidad, on_delete=models.CASCADE, db_column='especialidad_key')
    estado = models.ForeignKey(DimEstadoCita, on_delete=models.CASCADE, db_column='estado_key')
    
    # Degenerate Dimensions
    id_cita_sistema = models.BigIntegerField()
    hora_inicio = models.TimeField(null=True)
    
    # Métricas
    cantidad_citas = models.IntegerField(default=1)
    duracion_minutos = models.IntegerField(null=True)
    tiempo_anticipacion_dias = models.IntegerField(null=True)

    class Meta:
        db_table = 'fact_citas'
        # Opcional: Índice compuesto por si filtras mucho por grupo y fecha
        indexes = [
            models.Index(fields=['grupo_id', 'fecha_cita']),
        ]