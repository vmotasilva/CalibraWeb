from django.db import models

from organization.models import Setor


class CategoriaMaquina(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True, null=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ("nome",)
        verbose_name = "categoria de maquina"
        verbose_name_plural = "categorias de maquinas"

    def __str__(self):
        return self.nome


class Maquina(models.Model):
    nome = models.CharField(max_length=100, blank=True, null=True)
    codigo = models.CharField(max_length=50, unique=True)
    numero_serie = models.CharField(max_length=100, blank=True, null=True)
    fabricante = models.CharField(max_length=120, blank=True, null=True)
    descricao = models.TextField(blank=True, null=True)
    categoria = models.ForeignKey(CategoriaMaquina, on_delete=models.SET_NULL, null=True, blank=True, related_name="maquinas")
    setor = models.ForeignKey(Setor, on_delete=models.SET_NULL, null=True, blank=True, related_name="maquinas")
    status = models.BooleanField(default=True)

    class Meta:
        ordering = ("codigo", "numero_serie", "fabricante")
        verbose_name = "maquina"
        verbose_name_plural = "maquinas"

    @property
    def display_name(self):
        parts = [self.codigo]
        secondary_label = self.fabricante or self.nome
        if secondary_label:
            parts.append(secondary_label)
        if self.numero_serie:
            parts.append(f"Serie {self.numero_serie}")
        return " - ".join(parts)

    def __str__(self):
        return self.display_name