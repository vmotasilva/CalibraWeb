# -*- coding: utf-8 -*-
"""
Models para o módulo Procedures (Procedimentos, Treinamentos, Fornecedores e Cotações)

Unificação dos módulos:
- training: Procedimentos e Treinamentos
- procurements: Fornecedores e Cotações
"""

from django.db import models
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver
from decimal import Decimal


# ==============================================================================
# PROCEDIMENTOS E TREINAMENTOS
# ==============================================================================

class Procedimento(models.Model):
    """Documento de procedimento operacional (GED)."""
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código", null=True, blank=True)
    nome = models.CharField(max_length=200, verbose_name="Nome/Título do Documento", null=True, blank=True)
    descricao = models.TextField(null=True, blank=True, verbose_name="Descrição/Objetivo/Função")
    pasta = models.CharField(max_length=200, null=True, blank=True, verbose_name="Pasta (Local no Qualiex)")
    classificacao = models.CharField(max_length=100, verbose_name="Classificação (Tipo de Procedimento)", null=True, blank=True)
    autor = models.CharField(max_length=100, verbose_name="Autor (Texto Livre)", null=True, blank=True)
    numero_revisao = models.CharField(max_length=10, verbose_name="Número da Revisão", null=True, blank=True)
    ultima_revisao = models.DateField(null=True, blank=True, verbose_name="Última Revisão")
    data_aprovacao = models.DateField(null=True, blank=True, verbose_name="Data de Aprovação")
    proxima_revisao = models.DateField(null=True, blank=True, verbose_name="Próxima Revisão")
    data_validade = models.DateField(null=True, blank=True, verbose_name="Data de Validade")
    documentos_controlados = models.CharField(max_length=50, null=True, blank=True, verbose_name="Documentos Controlados")
    matriz = models.CharField(max_length=100, null=True, blank=True, verbose_name="Matriz")
    sub_area = models.CharField(max_length=100, null=True, blank=True, verbose_name="Sub-Área")

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

    class Meta:
        verbose_name = "Procedimento"
        verbose_name_plural = "Procedimentos (GED)"
        ordering = ["codigo"]


class Area(models.Model):
    """Área macro para classificação de procedimentos."""
    nome = models.CharField(max_length=100, unique=True, verbose_name='Nome da Área')
    descricao = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = 'Área'
        verbose_name_plural = 'Áreas (Macro)'
        ordering = ['nome']


class PacoteTreinamento(models.Model):
    """Pacote que agrupa procedimentos para treinamento."""
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome do Pacote")
    descricao = models.TextField(null=True, blank=True, verbose_name="Descrição")
    procedimentos = models.ManyToManyField(
        Procedimento, verbose_name="Procedimentos Incluídos", related_name="pacotes"
    )

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Pacote de Treinamento"
        verbose_name_plural = "Pacotes de Treinamento"


class ProcedimentoRevisao(models.Model):
    """Histórico de revisões de procedimentos."""
    procedimento = models.ForeignKey(Procedimento, on_delete=models.CASCADE, related_name='historico_revisoes')
    revisao = models.CharField(max_length=10)
    data_revisao = models.DateField(null=True, blank=True)
    data_aprovacao = models.DateField(null=True, blank=True)
    elaborador = models.ForeignKey('rh.Colaborador', on_delete=models.SET_NULL, null=True, blank=True, related_name='revisoes_elaboradas')
    revisor = models.ForeignKey('rh.Colaborador', on_delete=models.SET_NULL, null=True, blank=True, related_name='revisoes_revisadas')
    aprovador = models.ForeignKey('rh.Colaborador', on_delete=models.SET_NULL, null=True, blank=True, related_name='revisoes_aprovadas')
    arquivo_prev = models.FileField(upload_to='procedimentos/rev/', null=True, blank=True, verbose_name='Arquivo Revisão Anterior')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Histórico de Revisão de Procedimento'
        verbose_name_plural = 'Histórico de Revisões'
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.procedimento.codigo} Rev {self.revisao}"


class RegistroTreinamento(models.Model):
    """Registro de treinamento de colaborador em procedimento."""
    colaborador = models.ForeignKey(
        'rh.Colaborador', on_delete=models.CASCADE, related_name="treinamentos"
    )
    procedimento = models.ForeignKey(
        Procedimento, on_delete=models.CASCADE, related_name="registros_treinamento"
    )
    revisor_qualidade = models.ForeignKey(
        'rh.Colaborador', on_delete=models.SET_NULL, null=True, blank=True, related_name="revisoes_qualidade"
    )
    revisao_treinada = models.CharField(max_length=10)
    data_treinamento = models.DateField()
    validade_treinamento = models.DateField(null=True, blank=True)
    observacoes = models.TextField(null=True, blank=True)

    @property
    def status_treinamento(self):
        """Status: VIGENTE ou PENDENTE."""
        if (
            str(self.revisao_treinada).strip()
            == str(self.procedimento.numero_revisao).strip()
        ):
            return "VIGENTE"
        return "PENDENTE"

    class Meta:
        verbose_name_plural = "Matriz de Treinamentos"
        unique_together = ("colaborador", "procedimento")


# ==============================================================================
# FORNECEDORES E COTAÇÕES
# ==============================================================================

class Fornecedor(models.Model):
    """Fornecedor homologado ou em análise."""
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
    """Avaliação de desempenho de fornecedor."""
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
        """Calcula média das notas."""
        return round(
            (self.nota_tecnica + self.nota_pontualidade + self.nota_atendimento) / 3, 1
        )


class ProcessoCotacao(models.Model):
    """Processo de cotação de instrumentos."""
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
    """Orçamento de fornecedor para processo de cotação."""
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


# ==============================================================================
# SIGNALS
# ==============================================================================

@receiver(m2m_changed, sender=PacoteTreinamento.procedimentos.through)
def aplicar_pacotes_treinamento(sender, instance, action, pk_set, **kwargs):
    """Aplica pacotes de treinamento quando procedimentos são adicionados."""
    if action == "post_add":
        pacotes = PacoteTreinamento.objects.filter(pk__in=pk_set)
        for pacote in pacotes:
            for proc in pacote.procedimentos.all():
                if not getattr(proc, "aplica_treinamento", False):
                    continue
                RegistroTreinamento.objects.get_or_create(
                    colaborador=instance,
                    procedimento=proc,
                )


@receiver(post_save, sender=AvaliacaoFornecedor)
def update_fornecedor_score(sender, instance, **kwargs):
    """Atualiza nota média do fornecedor após avaliação."""
    f = instance.fornecedor
    avgs = f.avaliacoes.all()
    if avgs:
        f.nota_media = round(sum([a.media() for a in avgs]) / len(avgs), 1)
    f.save()
