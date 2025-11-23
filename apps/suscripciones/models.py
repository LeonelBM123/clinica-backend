from django.db import models
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from apps.cuentas.models import Grupo 

class Plan(models.Model):
    nombre = models.CharField(max_length=50)  
    descripcion = models.TextField(blank=True)
    precio_mensual = models.DecimalField(max_digits=10, decimal_places=2)
    
    limite_usuarios = models.IntegerField(default=5)
    limite_almacenamiento_gb = models.IntegerField(default=1)
    soporte_prioritario = models.BooleanField(default=False)
    reportes= models.BooleanField(default=False)
    pagination_class=None
    
    def __str__(self):
        return f"{self.nombre} - ${self.precio_mensual}"

class Suscripcion(models.Model):
    ESTADOS = [
        ('ACTIVA', 'Activa'),
        ('VENCIDA', 'Vencida'),
        ('CANCELADA', 'Cancelada'),
        ('PENDIENTE', 'Pendiente de Pago'),
    ]
    
    grupo = models.OneToOneField(Grupo, on_delete=models.CASCADE, related_name='suscripcion_info')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDIENTE')
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField()
    renovacion_automatica = models.BooleanField(default=True)
    
    id_suscripcion_externa = models.CharField(max_length=100, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.pk and not self.fecha_fin:
            self.fecha_fin = timezone.now() + relativedelta(months=1)
        super().save(*args, **kwargs)

    @property
    def esta_activa(self):
        return self.estado == 'ACTIVA' and self.fecha_fin > timezone.now()
        
    @property
    def dias_restantes(self):
        delta = self.fecha_fin - timezone.now()
        return max(delta.days, 0)

    def __str__(self):
        return f"{self.grupo.nombre} - {self.plan.nombre}"

class PagoSuscripcion(models.Model):
    """Historial de facturación del SaaS"""
    suscripcion = models.ForeignKey(Suscripcion, on_delete=models.CASCADE, related_name='historial_pagos')
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_pago = models.DateTimeField(auto_now_add=True)
    metodo_pago = models.CharField(max_length=50) 
    referencia_pago = models.CharField(max_length=100) 
    exitoso = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Pago {self.fecha_pago.date()} - {self.suscripcion.grupo.nombre}"