# Procurements - Modelos de Fornecedores e Compras
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from metrologia.models import Instrumento
from rh.models import Colaborador


class Fornecedor(models.Model):
    """Fornecedor/Laboratório de calibração"""
    STATUS = [
        ("HOMOLOGADO", "Homologado"),
        ("BLOQUEADO", "Bloqueado"),
        ("EM_ANALISE", "Em Análise"),
    ]
    nome_fantasia = models.CharField(max_length=100)
    razao_social = models.CharField(max_length=150, null=True, blank=True)
    cnpj = models.CharField(max_length=20, unique=True)
    contato = models.CharField(max_length=100)
    email = models.EmailField()
    telefone = models.CharField(max_length=20)
    escopo_servico = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS, default="EM_ANALISE")
    nota_media = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)

    def __str__(self):
        return f"{self.nome_fantasia}"

    class Meta:
        verbose_name_plural = "Fornecedores"


class AvaliacaoFornecedor(models.Model):
    """Avaliação de desempenho de fornecedor"""
    fornecedor = models.ForeignKey(
        Fornecedor,
        on_delete=models.CASCADE,
        related_name="avaliacoes"
    )
    data_avaliacao = models.DateField(auto_now_add=True)
    avaliador = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True)
    nota_tecnica = models.IntegerField(default=10)
    nota_pontualidade = models.IntegerField(default=10)
    nota_atendimento = models.IntegerField(default=10)
    observacao = models.TextField(null=True, blank=True)

    def media(self):
        """Calcula média de notas"""
        return round(
            (self.nota_tecnica + self.nota_pontualidade + self.nota_atendimento) / 3,
            1
        )

    class Meta:
        verbose_name = "Avaliação de Fornecedor"
        verbose_name_plural = "Avaliações de Fornecedor"


@receiver(post_save, sender=AvaliacaoFornecedor)
def update_fornecedor_score(sender, instance, **kwargs):
    """Atualiza nota média de fornecedor quando nova avaliação é criada"""
    f = instance.fornecedor
    avgs = f.avaliacoes.all()
    if avgs:
        f.nota_media = round(sum([a.media() for a in avgs]) / len(avgs), 1)
    f.save()


class ProcessoCotacao(models.Model):
    """Processo de cotação para instrumentos"""
    STATUS = [
        ("ABERTO", "Aberto"),
        ("FECHADO", "Fechado"),
        ("CANCELADO", "Cancelado")
    ]
    
    titulo = models.CharField(max_length=100)
    data_abertura = models.DateField(auto_now_add=True)
    prazo_limite = models.DateField()
    instrumentos = models.ManyToManyField(Instrumento)
    status = models.CharField(max_length=20, choices=STATUS, default="ABERTO")
    responsavel = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.titulo} ({self.status})"

    class Meta:
        verbose_name_plural = "Processos de Cotação"


class Orcamento(models.Model):
    """Orçamento de fornecedor para processo de cotação"""
    processo = models.ForeignKey(
        ProcessoCotacao,
        on_delete=models.CASCADE,
        related_name="orcamentos"
    )
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2)
    prazo_execucao_dias = models.IntegerField()
    arquivo_proposta = models.FileField(upload_to="orcamentos/")
    vencedor = models.BooleanField(default=False)
    observacoes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"R$ {self.valor_total} - {self.fornecedor}"

    class Meta:
        verbose_name = "Orçamento"
        verbose_name_plural = "Orçamentos"
