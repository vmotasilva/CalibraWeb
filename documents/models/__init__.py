# Documents - Modelos de Documentos
from django.db import models


class DocumentoGerado(models.Model):
    """Documento gerado pelo sistema (certificado, relatório, etc)"""
    tipo = models.CharField(max_length=50, verbose_name="Tipo de Documento")
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(null=True, blank=True)
    arquivo = models.FileField(upload_to="documentos_gerados/")
    data_geracao = models.DateTimeField(auto_now_add=True)
    criado_por = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.titulo} ({self.data_geracao.strftime('%d/%m/%Y')})"

    class Meta:
        verbose_name = "Documento Gerado"
        verbose_name_plural = "Documentos Gerados"
        ordering = ["-data_geracao"]


class ConfiguracaoCarimbo(models.Model):
    """Configuração do carimbo para certificados"""
    nome = models.CharField(max_length=100, unique=True)
    posicao_x = models.FloatField(help_text="Posição X em mm")
    posicao_y = models.FloatField(help_text="Posição Y em mm")
    tamanho_fonte = models.IntegerField(default=12)
    formato_data = models.CharField(
        max_length=50,
        default="%d/%m/%Y",
        help_text="Formato strftime"
    )
    texto_customizado = models.TextField(null=True, blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Configuração de Carimbo"
        verbose_name_plural = "Configurações de Carimbo"
