#pendiente
from django.db import models
from django.forms import ValidationError
from apps.cuentas.models import Usuario, Grupo

# Modelo Especialidad
class Especialidad(models.Model):
    nombre = models.CharField(
        max_length=128,
        unique=True,
        verbose_name="Nombre de la especialidad"
    )

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Especialidad"
        verbose_name_plural = "Especialidades"
        ordering = ['nombre']

# Modelo de Medico
class Medico(Usuario):
    numero_colegiado = models.CharField(
        max_length=64, 
        unique=True,
        verbose_name="Número de colegiado"
    )

    especialidades = models.ManyToManyField(
        Especialidad,
        related_name='medicos',
        verbose_name="Especialidades médicas",
        blank=True,
    )

    class Meta:
        verbose_name = "Médico"
        verbose_name_plural = "Médicos"
        ordering = ['nombre']

    def __str__(self):
        return f"Dr. {self.nombre} - {self.numero_colegiado}"


class Bloque_Horario(models.Model):
    dia_semana = models.CharField(
        max_length=10,
        choices=[
            ('LUNES', 'Lunes'),
            ('MARTES', 'Martes'),
            ('MIERCOLES', 'Miércoles'),
            ('JUEVES', 'Jueves'),
            ('VIERNES', 'Viernes'),
            ('SABADO', 'Sábado'),
            ('DOMINGO', 'Domingo'),
        ]
    )
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    estado = models.BooleanField(default=True)
    duracion_cita_minutos = models.PositiveIntegerField(default=30, help_text="Duración de cada cita en minutos")
    max_citas_por_bloque = models.PositiveIntegerField(default=10, help_text="Número máximo de citas permitidas en este bloque horario")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    medico = models.ForeignKey(Medico, on_delete=models.CASCADE, related_name='bloques_horarios')
    tipo_atencion = models.ForeignKey('Tipo_Atencion', on_delete=models.SET_NULL, null=True, blank=True, related_name='bloques_horarios')
    grupo = models.ForeignKey(
        Grupo,
        on_delete=models.CASCADE,
        related_name='bloques_horarios',
        verbose_name="Grupo al que pertenece",
    )

    def clean(self):
        super().clean()
        
        # Calcular duración total del bloque en minutos
        from datetime import datetime
        inicio = datetime.combine(datetime.today(), self.hora_inicio)
        fin = datetime.combine(datetime.today(), self.hora_fin)
        duracion_total_minutos = (fin - inicio).total_seconds() / 60
        
        # Calcular máximo teórico de citas
        max_posible = duracion_total_minutos // self.duracion_cita_minutos
        
        if self.max_citas_por_bloque > max_posible:
            raise ValidationError({
                'max_citas_por_bloque': 
                    f'No puede haber más de {max_posible} citas en este bloque '
                    f'de {duracion_total_minutos} minutos con citas de {self.duracion_cita_minutos} minutos'
            })

    class Meta:
        verbose_name = "Bloque Horario"
        verbose_name_plural = "Bloques Horarios"
        ordering = ['medico', 'dia_semana', 'hora_inicio']
        unique_together = ('medico', 'dia_semana', 'hora_inicio', 'hora_fin')

    def __str__(self):
        return f"{self.medico} - {self.dia_semana} {self.hora_inicio} a {self.hora_fin}"
    
class Tipo_Atencion(models.Model):
    nombre = models.CharField(max_length=128, unique=True)
    descripcion = models.TextField(blank=True)
    estado = models.BooleanField(default=True)
    grupo = models.ForeignKey(
        Grupo,
        on_delete=models.CASCADE,
        related_name='tipos_atencion',
        verbose_name="Grupo al que pertenece",
    )
    class Meta:
        verbose_name = "Tipo de Atención"
        verbose_name_plural = "Tipos de Atención"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre    
    