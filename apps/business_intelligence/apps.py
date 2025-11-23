from django.apps import AppConfig

class BusinessIntelligenceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.business_intelligence'  # <--- IMPORTANTE: Debe incluir 'apps.'
    verbose_name = 'Business Intelligence'