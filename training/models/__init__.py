# Training - Modelos de Treinamento e Procedimentos
from datetime import date
from django.db import models
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from rh.models import Colaborador


class Area(models.Model):
    """Área macro para procedimentos"""
    nome = models.CharField(max_length=100, unique=True, verbose_name='Nome da Área')
    descricao = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = 'Área'
        verbose_name_plural = 'Áreas (Macro)'
        ordering = ['nome']


class Procedimento(models.Model):
    """Procedimento/Documento de operação"""
    codigo = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Código",
        null=True,
        blank=True
    )
    nome = models.CharField(
        max_length=200,
        verbose_name="Nome/Título do Documento",
        null=True,
        blank=True
    )
    descricao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Descrição/Objetivo/Função"
    )
    pasta = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        verbose_name="Pasta (Local no Qualiex)"
    )
    classificacao = models.CharField(
        max_length=100,
        verbose_name="Classificação (Tipo de Procedimento)",
        null=True,
        blank=True
    )
    autor = models.CharField(
        max_length=100,
        verbose_name="Autor (Texto Livre)",
        null=True,
        blank=True
    )
    numero_revisao = models.CharField(
        max_length=10,
        verbose_name="Número da Revisão",
        null=True,
        blank=True
    )
    ultima_revisao = models.DateField(
        null=True,
        blank=True,
        verbose_name="Última Revisão"
    )
    data_aprovacao = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data de Aprovação"
    )
    proxima_revisao = models.DateField(
        null=True,
        blank=True,
        verbose_name="Próxima Revisão"
    )
    data_validade = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data de Validade"
    )
    documentos_controlados = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Documentos Controlados"
    )
    matriz = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Matriz"
    )
    sub_area = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Sub-Área"
    )

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

    class Meta:
        verbose_name = "Procedimento"
        verbose_name_plural = "Procedimentos (GED)"
        ordering = ["codigo"]


class ProcedimentoRevisao(models.Model):
    """Histórico de revisões de um procedimento"""
    procedimento = models.ForeignKey(
        Procedimento,
        on_delete=models.CASCADE,
        related_name='historico_revisoes'
    )
    revisao = models.CharField(max_length=10)
    data_revisao = models.DateField(null=True, blank=True)
    data_aprovacao = models.DateField(null=True, blank=True)
    elaborador = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revisoes_elaboradas'
    )
    revisor = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revisoes_revisadas'
    )
    aprovador = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revisoes_aprovadas'
    )
    arquivo_prev = models.FileField(
        upload_to='procedimentos/rev/',
        null=True,
        blank=True,
        verbose_name='Arquivo Revisão Anterior'
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Histórico de Revisão de Procedimento'
        verbose_name_plural = 'Histórico de Revisões'
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.procedimento.codigo} Rev {self.revisao}"


class PacoteTreinamento(models.Model):
    """Pacote de procedimentos para treinamento"""
    nome = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nome do Pacote"
    )
    descricao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Descrição"
    )
    procedimentos = models.ManyToManyField(
        Procedimento,
        verbose_name="Procedimentos Incluídos",
        related_name="pacotes"
    )

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Pacote de Treinamento"
        verbose_name_plural = "Pacotes de Treinamento"


class RegistroTreinamento(models.Model):
    """Registro de treinamento de um colaborador em um procedimento"""
    colaborador = models.ForeignKey(
        Colaborador,
        on_delete=models.CASCADE,
        related_name="treinamentos"
    )
    procedimento = models.ForeignKey(
        Procedimento,
        on_delete=models.CASCADE,
        related_name="registros_treinamento"
    )
    revisao_treinada = models.CharField(max_length=10)
    data_treinamento = models.DateField()
    validade_treinamento = models.DateField(null=True, blank=True)
    observacoes = models.TextField(null=True, blank=True)

    @property
    def status_treinamento(self):
        """Indica se treinamento está vigente"""
        if str(self.revisao_treinada).strip() == str(self.procedimento.numero_revisao).strip():
            return "VIGENTE"
        return "PENDENTE"

    def __str__(self):
        return f"{self.colaborador.nome_completo} - {self.procedimento.codigo}"

    class Meta:
        verbose_name_plural = "Matriz de Treinamentos"
        unique_together = ("colaborador", "procedimento")


@receiver(m2m_changed, sender=PacoteTreinamento.procedimentos.through)
def aplicar_pacotes_treinamento(sender, instance, action, pk_set, **kwargs):
    """Quando um pacote é atribuído a um colaborador, cria registros de treinamento"""
    if action == "post_add":
        pacotes = PacoteTreinamento.objects.filter(pk__in=pk_set)
        for pacote in pacotes:
            for proc in pacote.procedimentos.all():
                RegistroTreinamento.objects.get_or_create(
                    colaborador=instance,
                    procedimento=proc,
                    defaults={
                        "revisao_treinada": "PENDENTE",
                        "data_treinamento": date.today(),
                    },
                )
