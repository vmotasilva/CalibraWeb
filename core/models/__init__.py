# Core - Base Models e Constantes
from django.db import models


# ==============================================================================
# CONSTANTES E OPÇÕES GLOBAIS
# ==============================================================================
STATUS_CHOICES = [("ATIVO", "Ativo"), ("INATIVO", "Inativo"), ("INSS", "Afastado INSS")]
TURNOS_CHOICES = [
    ("ADM", "Administrativo"),
    ("TURNO_1", "Turno 1"),
    ("TURNO_2", "Turno 2"),
    ("TURNO_3", "Turno 3"),
    ("12X36", "12x36"),
]


class UnidadeMedida(models.Model):
    """Unidades de medida para instrumentos (mm, V, A, °C, etc)"""
    nome = models.CharField(max_length=50)
    sigla = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.nome} ({self.sigla})"

    class Meta:
        verbose_name_plural = "Unidades de Medida"
