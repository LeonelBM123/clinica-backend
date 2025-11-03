from django.db import models
from apps.cuentas.models import Usuario, Grupo  # Importar Grupo
from apps.doctores.models import Medico

class PatologiasO(models.Model):
    
    gravedad_opciones = [
        ('LEVE', 'Leve'),
        ('MODERADA', 'Moderada'),
        ('GRAVE', 'Grave'),
        ('CRITICA', 'Critica'),    
    ]
    
    nombre = models.CharField(
        max_length=120,
        unique=True,
        help_text="Nombre oficial de la patología") 
    
    alias = models.CharField(
        max_length=120,
        blank=True,
        help_text="Alias o nombres comunes de la patología",)
    
    descripcion = models.TextField(
        blank=True,
        help_text="Descripción de la patología")
    
    gravedad = models.CharField(
        max_length=50,
        choices=gravedad_opciones)
    
    estado = models.BooleanField(
        default=True,
        help_text= "Activo = True, Eliminado = False")
    
    # NUEVO CAMPO - Multi-tenancy por grupo
    grupo = models.ForeignKey(
        Grupo, 
        on_delete=models.CASCADE, 
        related_name='patologias',
        verbose_name="Grupo al que pertenece",
        help_text="Patología pertenece a este grupo/clínica"
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Patologia"
        verbose_name_plural = "Patologias"
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['nombre']),
            models.Index(fields=['gravedad']),
            models.Index(fields=['grupo']),  
        ]
    
    def __str__(self):
        return f"{self.nombre} ({self.grupo.nombre})"

class TratamientoMedicacion(models.Model):
    nombre = models.CharField(
        max_length=120,
        help_text="Nombre oficial del tratamiento") 
    
    descripcion = models.TextField(
        blank=True,
        null=True,
        help_text="Descripción del tratamiento")
    
    duracion_dias = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Duración del tratamiento en días")

    patologias = models.ManyToManyField(
        'PatologiasO',
        related_name='tratamientos',
        blank=True
    )

    grupo = models.ForeignKey(
        Grupo, 
        on_delete=models.CASCADE, 
        related_name='tratamientos',
        verbose_name="Grupo al que pertenece",
        help_text="Tratamiento pertenece a este grupo/clínica"
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tratamiento"
        verbose_name_plural = "Tratamientos"
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['nombre']),
            models.Index(fields=['grupo']),  
        ]
    
    def __str__(self):
        return f"{self.nombre} ({self.grupo.nombre})"



class Paciente(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE)
    numero_historia_clinica = models.CharField(max_length=64, unique=True,help_text="Ejemplo: HC-2023-0001")
    patologias = models.ManyToManyField('PatologiasO', related_name='pacientes', blank=True)
    agudeza_visual_derecho = models.CharField(max_length=20, blank=True,help_text="Ejemplo: 20/20")
    agudeza_visual_izquierdo = models.CharField(max_length=20, blank=True,help_text="Ejemplo: 20/20")
    presion_ocular_derecho = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,help_text="Ejemplo: 15.50")
    presion_ocular_izquierdo = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,help_text="Ejemplo: 15.50")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['usuario']

    def __str__(self):
        return f" {self.usuario.nombre} - {self.numero_historia_clinica}"


# Modelo para resultados de exámenes
class ResultadoExamenes(models.Model):
    ESTADOS_OPCIONES = [
        ('PENDIENTE', 'Pendiente'),
        ('REVISADO', 'Revisado'),
        ('ARCHIVADO', 'Archivado'),   
    ]
    TIPO_EXAMEN_CHOICES = [
        ('Topografía Corneal', 'Topografía Corneal'),
        ('OCT de Retina', 'OCT de Retina'),
        ('OCT de Nervio Óptico', 'OCT de Nervio Óptico'),
        ('Fotografía Segmento Anterior', 'Fotografía Segmento Anterior'),
        ('Fotografía de Anexos', 'Fotografía de Anexos'),
        ('Microscopía Especular', 'Microscopía Especular'),
        ('Otro', 'Otro'),
    ]    
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='resultados_examenes')
    medico = models.ForeignKey(Medico, on_delete=models.CASCADE, related_name='resultados_examenes')
    tipo_examen = models.CharField(max_length=120, choices=TIPO_EXAMEN_CHOICES, help_text="Tipo de examen (ej: OCT, fondo de ojo, etc.)")
    archivo_url = models.CharField(max_length=255, help_text="URL o ruta del archivo", null=True, blank=True)
    observaciones = models.TextField(blank=True, help_text="Observaciones del médico")
    estado = models.CharField(max_length=30, choices=ESTADOS_OPCIONES, default='PENDIENTE', help_text="Estado del resultado")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    grupo = models.ForeignKey(
         Grupo, 
            on_delete=models.CASCADE, 
            related_name='resultados_examenes',
            verbose_name="Grupo al que pertenece",
            help_text="Resultado de examen pertenece a este grupo/clínica",
            null=True, 
        blank=True
        )
    class Meta:
        verbose_name = "Resultado de Examen"
        verbose_name_plural = "Resultados de Exámenes"
        ordering = ['-fecha_creacion', '-fecha_actualizacion']

    def __str__(self):
        return f"{self.tipo_examen} - {self.paciente} ({self.fecha_examen})"


