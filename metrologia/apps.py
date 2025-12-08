from django.apps import AppConfig


class MetrologiaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'metrologia'
    verbose_name = 'Metrologia - Calibração de Instrumentos'
    
    def ready(self):
        import metrologia.signals
