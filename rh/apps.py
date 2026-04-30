from django.apps import AppConfig


class RhConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'rh'
    verbose_name = 'RH - Recursos Humanos'

    def ready(self):
        """Registra os signals quando a app está pronta"""
        import rh.signals  # noqa
