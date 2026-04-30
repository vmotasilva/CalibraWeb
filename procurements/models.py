from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal

# ==============================================================================
# PROCUREMENTS - FORNECEDORES E COTAÇÕES
# ==============================================================================

class Fornecedor(models.Model):
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
    fornecedor = models.ForeignKey(
        Fornecedor, on_delete=models.CASCADE, related_name="avaliacoes"
    )
    data_avaliacao = models.DateField(auto_now_add=True)
    avaliador = models.ForeignKey('rh.Colaborador', on_delete=models.SET_NULL, null=True)
    nota_tecnica = models.IntegerField(default=10)
    nota_pontualidade = models.IntegerField(default=10)
    nota_atendimento = models.IntegerField(default=10)
    observacao = models.TextField(null=True, blank=True)

    def media(self):
        return round(
            (self.nota_tecnica + self.nota_pontualidade + self.nota_atendimento) / 3, 1
        )


@receiver(post_save, sender=AvaliacaoFornecedor)
def update_fornecedor_score(sender, instance, **kwargs):
    f = instance.fornecedor
    avgs = f.avaliacoes.all()
    if avgs:
        f.nota_media = round(sum([a.media() for a in avgs]) / len(avgs), 1)
    f.save()


class ProcessoCotacao(models.Model):
    STATUS = [("ABERTO", "Aberto"), ("FECHADO", "Fechado"), ("CANCELADO", "Cancelado")]
    titulo = models.CharField(max_length=100)
    data_abertura = models.DateField(auto_now_add=True)
    prazo_limite = models.DateField()
    instrumentos = models.ManyToManyField('metrologia.Instrumento')
    status = models.CharField(max_length=20, choices=STATUS, default="ABERTO")
    responsavel = models.ForeignKey('rh.Colaborador', on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.titulo} ({self.status})"

    class Meta:
        verbose_name_plural = "Processos de Cotação"


class Orcamento(models.Model):
    processo = models.ForeignKey(
        ProcessoCotacao, on_delete=models.CASCADE, related_name="orcamentos"
    )
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2)
    prazo_execucao_dias = models.IntegerField()
    arquivo_proposta = models.FileField(upload_to="orcamentos/")
    vencedor = models.BooleanField(default=False)
    observacoes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"R$ {self.valor_total} - {self.fornecedor}"
