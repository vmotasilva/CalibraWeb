from django.db import models

class CategoriaMaquina(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True, null=True)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome


class Maquina(models.Model):
    nome = models.CharField(max_length=100)
    codigo = models.CharField(max_length=50, unique=True)
    descricao = models.TextField(blank=True, null=True)
    categoria = models.ForeignKey(CategoriaMaquina, on_delete=models.SET_NULL, null=True, blank=True, related_name="maquinas")
    status = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nome} ({self.codigo})"