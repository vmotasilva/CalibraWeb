# Organization - Modelos de Estrutura Organizacional
from django.db import models


class Setor(models.Model):
    """Setores/Departamentos da empresa"""
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
    """Centro de custo associado a um setor"""
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
