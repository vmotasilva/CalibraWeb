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
    Identificado por Numeração sequencial e Título, com associação opcional a Procedimentos.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero = models.PositiveIntegerField(
        unique=True,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Número do Diagrama",
        help_text="Numeração sequencial do diagrama (#001, #002...)"
    )
    titulo = models.CharField(max_length=255, verbose_name="Título do Processo")
    departamento = models.CharField(max_length=120, default="Metrologia", verbose_name="Departamento/Área")

    # Código opcional para compatibilidade
    codigo = models.CharField(
        max_length=60,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Código Documental / Referência",
        help_text="Código opcional para identificação adicional"
    )

    # Vínculo opcional com Procedimento Operacional existente no CalibraWeb (ex: POP, IT, DEX...)
    procedimento = models.ForeignKey(
        'procedures.Procedimento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='diagramas_fluxo',
        verbose_name="Procedimento Vinculado (Opcional)"
    )
    matriz_procedimento = models.ForeignKey(
        'procedures.MatrizProcedimento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='diagramas_associados',
        verbose_name="Matriz de Procedimento (Opcional)"
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
        ordering = ["numero", "titulo"]

    def save(self, *args, **kwargs):
        if not self.numero:
            max_num = Diagrama.objects.aggregate(models.Max('numero'))['numero__max'] or 0
            self.numero = max_num + 1
        super().save(*args, **kwargs)

    @property
    def identificador(self):
        """Retorna o identificador formatado (ex: #001, #002)."""
        return f"#{self.numero:03d}" if self.numero else "#001"

    @property
    def codigo_exibicao(self):
        """Retorna a referência textual completa (ex: POP-001 (#001) ou apenas #001)."""
        if self.procedimento and self.procedimento.codigo:
            return f"{self.procedimento.codigo} ({self.identificador})"
        if self.codigo:
            return f"{self.codigo} ({self.identificador})"
        return self.identificador

    def __str__(self):
        return f"{self.codigo_exibicao} - {self.titulo}"

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
    submetido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='diagramas_revisoes_submetidas',
        verbose_name="Submetido por"
    )
    data_submissao = models.DateTimeField(null=True, blank=True, verbose_name="Data da Submissão")
    motivo_devolucao = models.TextField(
        blank=True,
        null=True,
        verbose_name="Motivo da Última Devolução",
        help_text="Justificativa do aprovador quando a revisão é devolvida ao elaborador."
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
        return f"{self.diagrama.codigo_exibicao} - Rev. {self.revisao:02d} ({self.get_status_display()})"

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


class RaiaCatalogo(models.Model):
    """
    Catálogo global de Raias (swimlanes) reutilizáveis nos diagramas.
    Os diagramas guardam apenas o NOME da raia (raias de uso livre continuam permitidas);
    o catálogo fornece padronização, cor, ordem padrão e o vínculo com o Setor do RH.
    """
    nome = models.CharField(max_length=100, verbose_name="Nome da Raia")
    setor = models.ForeignKey(
        'organization.Setor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='raias_diagramas',
        verbose_name="Setor vinculado (RH)",
        help_text="Colaboradores desse setor caem automaticamente nesta raia."
    )
    cor = models.CharField(max_length=7, default="#334155", verbose_name="Cor da faixa")
    ordem = models.PositiveIntegerField(default=0, db_index=True, verbose_name="Ordem padrão")
    descricao = models.CharField(max_length=255, blank=True, verbose_name="Descrição")
    ativo = models.BooleanField(default=True, verbose_name="Ativa")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Raia de Diagrama"
        verbose_name_plural = "Raias de Diagramas"
        ordering = ["ordem", "nome"]
        constraints = [
            models.UniqueConstraint(models.functions.Lower('nome'), name='uniq_raia_catalogo_nome_ci'),
        ]

    def __str__(self):
        return self.nome


class TemaDiagrama(models.Model):
    """Tema de cores/estilos salvo no catálogo e reutilizável em qualquer diagrama."""
    nome = models.CharField(max_length=100, verbose_name="Nome do tema")
    definicao = models.JSONField(default=dict, verbose_name="Definição do tema")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='temas_diagramas',
        verbose_name="Criado por"
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tema de Diagrama"
        verbose_name_plural = "Temas de Diagramas"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(models.functions.Lower('nome'), name='uniq_tema_diagrama_nome_ci'),
        ]

    def __str__(self):
        return self.nome
