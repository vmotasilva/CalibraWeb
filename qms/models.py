# ==============================================================================
# QMS MODELS - PHASE 9 MODULARIZATION
# ==============================================================================
# This file contains ONLY cross-app coordinator models
# All other models have been moved to their respective apps
# 
# See Phase 9 Architecture for details:
# - core.models: UnidadeMedida, STATUS_CHOICES, TURNOS_CHOICES
# - organization.models: Setor, CentroCusto, HierarquiaSetor
# - rh.models: Colaborador, Ferias, Ocorrencia, DocumentoPessoal
# - metrologia.models: Instrumento, HistoricoCalibracao, FaixaMedicao, CategoriaInstrumento, ArquivoPadrao, ResultadoFaixaCalibracao, OrdemCalibracao
# - procurements.models: Fornecedor, AvaliacaoFornecedor, ProcessoCotacao, Orcamento
# - training.models: Procedimento, Area, PacoteTreinamento, ProcedimentoRevisao, RegistroTreinamento
#
# THIS FILE (qms.models) ONLY exports these 3 cross-app models:
# ==============================================================================

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth.models import User
import uuid


# --- 1. Solicitação de Instrumentos (Cross-App Coordinator) ---
class SolicitacaoInstrumento(models.Model):
    """Cross-app model: coordinates instrument requests across metrologia and other apps"""
    TIPO_CHOICES = [
        ("NOVA", "Nova Aplicação"),
        ("SUBSTITUICAO", "Substituição (Dano/Perda)"),
    ]
    STATUS_CHOICES = [
        ("PENDENTE", "Pendente"),
        ("EM_ANALISE", "Em Análise pelo Qualidade"),
        ("APROVADO", "Aprovado"),
        ("REJEITADO", "Rejeitado"),
        ("CONCLUIDO", "Entregue/Resolvido"),
    ]

    solicitante = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="solicitacoes"
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    # Instrumento é opcional pois pode ser uma solicitação de algo que ainda não existe
    instrumento_alvo = models.ForeignKey(
        "metrologia.Instrumento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Preencher caso seja substituição de um item existente",
    )
    motivo = models.TextField(
        help_text="Descreva a necessidade da aplicação ou o motivo da troca", default=""
    )
    data_solicitacao = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDENTE")
    resposta_qualidade = models.TextField(
        blank=True, null=True, help_text="Parecer do setor de qualidade"
    )

    def __str__(self):
        return (
            f"{self.get_tipo_display()} - {self.solicitante.username} - {self.status}"
        )


# --- 2. Registro de Ocorrências (Cross-App Coordinator) ---
class OcorrenciaInstrumento(models.Model):
    """Cross-app model: coordinates instrument issues across metrologia and other apps"""
    TIPO_OCORRENCIA = [
        ("CALIBRACAO", "Calibração"),
        ("VERIFICACAO", "Verificação"),
        ("INSPECAO", "Inspeção"),
        ("AJUSTE", "Ajuste"),
        ("MANUTENCAO", "Manutenção"),
        ("AVARIA", "Avaria/Dano"),
        ("EXTRAVIO", "Extravio/Perda"),
        ("OUTRO", "Outro"),
    ]

    instrumento = models.ForeignKey(
        "metrologia.Instrumento",
        on_delete=models.CASCADE,
        related_name="ocorrencias",
        null=True,
        blank=True,
    )
    tipo = models.CharField(max_length=20, choices=TIPO_OCORRENCIA)
    descricao = models.TextField()
    data_ocorrencia = models.DateField(default=timezone.now)
    usuario_responsavel = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    custo_reparo = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    def __str__(self):
        return (
            f"{self.instrumento} - {self.get_tipo_display()} ({self.data_ocorrencia})"
        )


# --- 3. Import Job (Cross-App Coordinator) ---
class ImportJob(models.Model):
    """Cross-app model: coordinates data import jobs across all apps"""
    STATUS_CHOICES = [
        ("PENDING", "Pendente"),
        ("STARTED", "Em Progresso"),
        ("SUCCESS", "Concluído"),
        ("FAILURE", "Falha"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    filename = models.CharField(max_length=255)
    filepath = models.CharField(max_length=1024, null=True, blank=True)
    job_type = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    result = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ImportJob {self.id} - {self.filename} ({self.status})"

    class Meta:
        verbose_name = "Import Job"
        verbose_name_plural = "Import Jobs"
