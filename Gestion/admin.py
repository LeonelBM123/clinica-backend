from django.contrib import admin
from .models import Bitacora

# Register your models here.
@admin.register(Bitacora)
class BitacoraAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'usuario', 'ip', 'objeto', 'accion_truncada')
    list_filter = ('usuario', 'timestamp')
    search_fields = ('accion', 'ip', 'objeto')
    readonly_fields = ('timestamp',)

    def accion_truncada(self, obj):
        return obj.accion[:80]
    accion_truncada.short_description = 'Acción'


