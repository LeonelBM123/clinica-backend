from django.db import models

# Create your models here.
from django.contrib.auth.models import User

class Aviso(models.Model):
    PRIORIDAD_CHOICES = [
        ('normal', 'Normal'),
        ('alta', 'Alta'),
        ('urgente', 'Urgente'),
    ]
    
    titulo = models.CharField(max_length=200)
    mensaje = models.TextField()
    prioridad = models.CharField(max_length=10, choices=PRIORIDAD_CHOICES, default='normal')
    target_user = models.CharField(max_length=100, default='all')  # 'all' o ID específico
    creado_en = models.DateTimeField(auto_now_add=True)
    leido = models.BooleanField(default=False)
    notification_id = models.CharField(max_length=100, null=True, blank=True)  # ID de OneSignal
    
    class Meta:
        ordering = ['-creado_en']
        verbose_name = 'Aviso'
        verbose_name_plural = 'Avisos'
    
    def __str__(self):
        return f"{self.titulo} - {self.prioridad}"