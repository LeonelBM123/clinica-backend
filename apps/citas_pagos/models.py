from django.db import models
from apps.historiasDiagnosticos.models import Paciente
from apps.doctores.models import Bloque_Horario
from apps.cuentas.models import Grupo
class Cita_Medica(models.Model):
    ESTADOS_CITA = [
        ('PENDIENTE', 'Pendiente'),
        ('CONFIRMADA', 'Confirmada'),
        ('EN_PROCESO', 'En Proceso'),
        ('COMPLETADA', 'Completada'),
        ('CANCELADA', 'Cancelada'),
        ('NO_ASISTIO', 'No Asistió'),
    ]
    
    fecha = models.DateField(help_text="Fecha de la cita médica")
    hora_inicio = models.TimeField(help_text="Hora de inicio de la cita médica")
    hora_fin = models.TimeField(help_text="Hora de fin de la cita médica")
    estado_cita = models.CharField(
        max_length=20, 
        choices=ESTADOS_CITA, 
        default='PENDIENTE',
        help_text="Estado actual de la cita"
    )
    estado = models.BooleanField(default=True, help_text="Activo = True, Eliminado = False")
    notas = models.TextField(blank=True, help_text="Notas adicionales sobre la cita médica")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    motivo_cancelacion = models.TextField(blank=True, help_text="Motivo de la cancelación, si aplica")
    calificacion = models.IntegerField(null=True, blank=True, help_text="Calificación de la cita médica (1-5)")
    comentario_calificacion = models.TextField(blank=True, help_text="Comentario sobre la calificación, si aplica")
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='citas')
    bloque_horario = models.ForeignKey(Bloque_Horario, on_delete=models.CASCADE, related_name='citas')
    grupo = models.ForeignKey(
        Grupo,
        on_delete=models.CASCADE,
        related_name='citas_medicas',
        verbose_name="Grupo al que pertenece",
    )
    reporte = models.TextField(blank=True, null=True)
    class Meta:
        verbose_name = "Cita Médica"
        verbose_name_plural = "Citas Médicas"
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['fecha_creacion']),
            models.Index(fields=['estado']),
            models.Index(fields=['estado_cita']),
        ]
    
    def __str__(self):
        return f"Cita {self.id} - {self.paciente} - {self.fecha} {self.hora_inicio}"