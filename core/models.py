from django.db import models

# ==============================================================================
# CORE - CONSTANTES E MODELOS BASE
# ==============================================================================

# CONSTANTES GLOBAIS (Reutilizadas por todos os apps)
STATUS_CHOICES = [("ATIVO", "Ativo"), ("INATIVO", "Inativo"), ("INSS", "Afastado INSS")]
TURNOS_CHOICES = [
    ("ADM", "Administrativo"),
    ("TURNO_1", "Turno 1"),
    ("TURNO_2", "Turno 2"),
    ("TURNO_3", "Turno 3"),
    ("12X36", "12x36"),
]


# ==============================================================================
# MODELO: UnidadeMedida
# ==============================================================================
class UnidadeMedida(models.Model):
    nome = models.CharField(
        max_length=50, unique=True, verbose_name="Unidade de Medida"
    )
    descricao = models.CharField(
        max_length=200, null=True, blank=True, verbose_name="Descrição"
    )

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Unidade de Medida"
        verbose_name_plural = "Unidades de Medida"
        ordering = ["nome"]
