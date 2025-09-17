from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.core.validators import MinLengthValidator

# Modelo de Rol
class Rol(models.Model):
    tipo_rol_opciones = [
        ('PACIENTE', 'Paciente'),
        ('MÉDICO', 'Médico'),
        ('ADMIN', 'Administrador'),
        ('RECEPCIONISTA', 'Recepcionista'),
    ]

    nombre = models.CharField(
        max_length=64,
        unique=True,
        verbose_name="Nombre del rol",
        choices=tipo_rol_opciones
    )

    def __str__(self):
        return self.get_nombre_display()

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Roles"
        ordering = ['nombre']

# Modelo de Usuario maestro
class Usuario(models.Model):  
    sexo_opciones = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
    ]

    nombre = models.CharField(
        max_length=128,
        verbose_name="Nombre completo"
    )
    
    password = models.CharField(max_length=128)
    
    correo = models.EmailField(
        unique=True,
        verbose_name="Correo electrónico"
    )
    
    sexo = models.CharField(
        max_length=1, 
        choices=sexo_opciones,
        verbose_name="Género"
    )
    
    fecha_nacimiento = models.DateField(
        verbose_name="Fecha de nacimiento"
    )
    
    telefono = models.CharField(
        max_length=8,
        blank=True,
        null=True,
        validators=[MinLengthValidator(8)],
        verbose_name="Teléfono"
    )
    
    direccion = models.CharField(
        max_length=256,
        blank=True,
        null=True,
        verbose_name="Dirección"
    )
    
    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de registro"
    )
    
    estado = models.BooleanField(
        default=True,
        verbose_name="¿Está activo?"
    )
    
    ultimo_login = models.DateTimeField(
        auto_now=True,
        verbose_name="Último ingreso"
    )
    
    rol = models.ForeignKey(
        Rol, 
        on_delete=models.PROTECT,
        verbose_name="Rol del usuario",
        related_name='usuarios',
        null=True,
        blank=True
    )

    def set_password(self, raw_password):
        self.password = make_password(raw_password)
        self.save()
    
    def check_password(self, raw_password):
        return check_password(raw_password, self.password)
    
    def __str__(self):
        return f"{self.nombre} ({self.get_rol_display()})"

    class Meta:
        verbose_name = "Usuario del sistema"
        verbose_name_plural = "Usuarios del sistema"
        ordering = ['-fecha_registro']
        indexes = [
            models.Index(fields=['correo']),
            models.Index(fields=['rol', 'estado']),
        ]

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
class Medico(models.Model):
    medico = models.OneToOneField(
        Usuario, 
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='medico_profile'
    )
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

    def __str__(self):
        return f"Dr. {self.medico.nombre} - {self.numero_colegiado}"

    class Meta:
        verbose_name = "Médico"
        verbose_name_plural = "Médicos"
        ordering = ['medico__nombre']