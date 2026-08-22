from django.db import models
from core.models import STATUS_CHOICES, TURNOS_CHOICES

# ==============================================================================
# ORGANIZATION - ESTRUTURA ORGANIZACIONAL
# ==============================================================================

class Unidade(models.Model):
    nome = models.CharField(max_length=150, unique=True, verbose_name="Nome da Unidade / Empresa")
    codigo = models.CharField(max_length=50, blank=True, default="", verbose_name="Código / Sigla")
    cnpj = models.CharField(max_length=20, blank=True, default="", verbose_name="CNPJ")
    cidade = models.CharField(max_length=100, blank=True, default="", verbose_name="Cidade")
    estado = models.CharField(max_length=2, blank=True, default="", verbose_name="UF")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Unidade / Empresa"
        verbose_name_plural = "Unidades / Empresas"
        ordering = ["nome"]


class Setor(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome do Setor")
    responsavel = models.CharField(
        max_length=100, null=True, blank=True, verbose_name="Responsável Genérico"
    )

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Setor"
        verbose_name_plural = "Cadastro de Setores"
        ordering = ["nome"]


class CentroCusto(models.Model):
    setor = models.ForeignKey(
        Setor,
        on_delete=models.CASCADE,
        related_name="centros_custo",
        verbose_name="Setor Pertencente",
    )
    codigo = models.CharField(max_length=20, verbose_name="Código")
    descricao = models.CharField(
        max_length=100, null=True, blank=True, verbose_name="Descrição"
    )

    def __str__(self):
        return f"{self.codigo} - {self.descricao or self.setor.nome}"

    class Meta:
        verbose_name = "Centro de Custo"
        verbose_name_plural = "Centros de Custo"
        unique_together = ("setor", "codigo")


class HierarquiaSetor(models.Model):
    setor = models.ForeignKey(Setor, on_delete=models.CASCADE, verbose_name="Setor")
    turno = models.CharField(
        max_length=20, choices=TURNOS_CHOICES, verbose_name="Turno"
    )
    lider = models.ForeignKey(
        'rh.Colaborador',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="liderados_setor",
        verbose_name="Líder",
    )
    supervisor = models.ForeignKey(
        'rh.Colaborador',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supervisionados_setor",
        verbose_name="Supervisor",
    )
    gerente = models.ForeignKey(
        'rh.Colaborador',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gerenciados_setor",
        verbose_name="Gerente",
    )
    diretor = models.ForeignKey(
        'rh.Colaborador',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diretoria_setor",
        verbose_name="Diretor",
    )

    def __str__(self):
        return f"Hierarquia: {self.setor.nome} - {self.get_turno_display()}"

    class Meta:
        verbose_name = "Hierarquia"
        verbose_name_plural = "Hierarquia (Setor x Turno)"
        unique_together = ("setor", "turno")
