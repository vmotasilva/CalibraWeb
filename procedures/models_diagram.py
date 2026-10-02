# -*- coding: utf-8 -*-
"""
Modelos para o Módulo de Criação de Diagramas e Fluxogramas (DOC.071)
CalibraWeb - QMS / ISO 13485
"""

import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class StatusDiagrama(models.TextChoices):
    RASCUNHO = 'RASCUNHO', 'Rascunho'
    EM_APROVACAO = 'EM_APROVACAO', 'Em Aprovação'
    APROVADO = 'APROVADO', 'Aprovado'
    OBSOLETO = 'OBSOLETO', 'Obsoleto'


class Diagrama(models.Model):
    """
    Entidade Principal / Cabeçalho do Fluxograma de Processo.
    Ex: DOC.071 - Fluxo de Calibração e Controle Metrológico.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(
        max_length=60,
        unique=True,
        db_index=True,
        verbose_name="Código Documental",
        help_text="Identificador único no QMS. Ex: DOC.071-FLX-001"
    )
    titulo = models.CharField(max_length=255, verbose_name="Título do Processo")
    departamento = models.CharField(max_length=120, verbose_name="Departamento/Área")

    # Vínculo opcional com a Matriz ou Procedimento Operacional existente no CalibraWeb
    matriz_procedimento = models.ForeignKey(
        'procedures.MatrizProcedimento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='diagramas_associados',
        verbose_name="Matriz de Procedimento"
    )
    procedimento = models.ForeignKey(
        'procedures.Procedimento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='diagramas_fluxo',
        verbose_name="Procedimento Operacional Vinculado"
    )

    descricao = models.TextField(blank=True, verbose_name="Descrição / Objetivo do Fluxo")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='diagramas_criados',
        verbose_name="Elaborador"
    )
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Diagrama de Processo"
        verbose_name_plural = "Diagramas de Processos"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} - {self.titulo}"

    @property
    def versao_vigente(self):
        """Retorna a versão aprovada vigente mais recente."""
        return self.versoes.filter(status=StatusDiagrama.APROVADO).order_by('-revisao').first()


class DiagramaVersao(models.Model):
    """
    Revisões de Qualidade (R00, R01, etc.) e Armazenamento da Topologia xyflow (JSONField).
    Assegura rastreabilidade total (ISO 13485) e imutabilidade pós-aprovação.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    diagrama = models.ForeignKey(
        Diagrama,
        on_delete=models.CASCADE,
        related_name='versoes',
        verbose_name="Diagrama Principal"
    )
    revisao = models.PositiveIntegerField(
        default=0,
        verbose_name="Número da Revisão",
        help_text="0 para R00, 1 para R01, etc."
    )
    status = models.CharField(
        max_length=20,
        choices=StatusDiagrama.choices,
        default=StatusDiagrama.RASCUNHO,
        db_index=True,
        verbose_name="Status da Revisão"
    )

    # Persistência da topologia (nodes, edges, grid_data)
    dados_topologia = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Topologia do Grafo (xyflow JSON)",
        help_text="Armazena { 'nodes': [...], 'edges': [...], 'grid_data': [...] }"
    )

    # Metadados de QMS / Auditoria
    motivo_revisao = models.TextField(
        blank=True,
        null=True,
        verbose_name="Motivo da Revisão / Alteração"
    )
    aprovado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='diagramas_revisoes_aprovadas',
        verbose_name="Aprovado por"
    )
    data_aprovacao = models.DateTimeField(null=True, blank=True, verbose_name="Data da Aprovação")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Versão de Diagrama"
        verbose_name_plural = "Versões de Diagramas"
        unique_together = [('diagrama', 'revisao')]
        ordering = ['-revisao']
        indexes = [
            models.Index(fields=['diagrama', 'status']),
        ]

    def __str__(self):
        return f"{self.diagrama.codigo} - Rev. {self.revisao:02d} ({self.get_status_display()})"

    def clean(self):
        """Validação QMS: Bloqueia alterações em versões já Aprovadas."""
        if self.pk:
            versao_antiga = DiagramaVersao.objects.filter(pk=self.pk).values('status').first()
            if versao_antiga and versao_antiga['status'] == StatusDiagrama.APROVADO:
                if self.status == StatusDiagrama.APROVADO:
                    raise ValidationError("Versões Aprovadas são imutáveis (Requisito ISO 13485). Crie uma nova revisão para realizar alterações.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
