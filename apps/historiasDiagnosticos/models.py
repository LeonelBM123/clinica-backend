from django.db import models
from apps.cuentas.models import Usuario, Grupo  # Importar Grupo

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
