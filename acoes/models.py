from django.db import models

from django.db import models
from rh.models import Colaborador
from django.utils import timezone
from django.db.models import Q


class AcaoCorretiva(models.Model):
    """Modelo para gerenciar ações corretivas e preventivas."""
    
    TIPO_CHOICES = [
        ('corretiva', 'Ação Corretiva'),
        ('preventiva', 'Ação Preventiva'),
    ]
    
    STATUS_CHOICES = [
        ('aberta', 'Aberta'),
        ('em_progresso', 'Em Progresso'),
        ('concluida', 'Concluída'),
        ('cancelada', 'Cancelada'),
    ]
    
    PRIORIDADE_CHOICES = [
        ('baixa', 'Baixa'),
        ('media', 'Média'),
        ('alta', 'Alta'),
        ('critica', 'Crítica'),
    ]
    
    # Informações básicas
    titulo = models.CharField(max_length=200, verbose_name="Título da Ação")
    descricao = models.TextField(verbose_name="Descrição")
    tipo = models.CharField(
        max_length=20, 
        choices=TIPO_CHOICES, 
        default='corretiva',
        verbose_name="Tipo de Ação"
    )
    prioridade = models.CharField(
        max_length=20,
        choices=PRIORIDADE_CHOICES,
        default='media',
        verbose_name="Prioridade"
    )
    
    # Status e prazos
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='aberta',
        verbose_name="Status"
    )
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_vencimento = models.DateField(verbose_name="Data de Vencimento")
    data_conclusao = models.DateField(null=True, blank=True, verbose_name="Data de Conclusão")
    
    # Responsáveis
    criado_por = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        related_name="acoes_criadas",
        verbose_name="Criado por"
    )
    responsavel = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        related_name="acoes_responsavel",
        verbose_name="Responsável"
    )
    
    # Campos adicionais
    origem = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Origem (Ex: Auditoria, Não Conformidade, etc.)"
    )
    meta = models.TextField(null=True, blank=True, verbose_name="Meta/Objetivo")
    resultado = models.TextField(null=True, blank=True, verbose_name="Resultado Obtido")
    observacoes = models.TextField(null=True, blank=True, verbose_name="Observações")
    
    # Ativo/Inativo
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    
    class Meta:
        verbose_name = "Ação Corretiva/Preventiva"
        verbose_name_plural = "Ações Corretivas/Preventivas"
        ordering = ['-data_criacao']
        indexes = [
            models.Index(fields=['-data_criacao']),
            models.Index(fields=['status']),
            models.Index(fields=['responsavel']),
            models.Index(fields=['prioridade']),
        ]
    
    def __str__(self):
        return f"{self.get_tipo_display()} - {self.titulo}"
    
    def dias_vencimento(self):
        """Retorna dias até o vencimento (negativo se vencida)."""
        from datetime import date
        delta = self.data_vencimento - date.today()
        return delta.days
    
    def esta_vencida(self):
        """Verifica se a ação está vencida."""
        from datetime import date
        return self.data_vencimento < date.today() and self.status != 'concluida'


class AcaoComentario(models.Model):
    """Comentários em ações corretivas/preventivas."""
    
    acao = models.ForeignKey(
        AcaoCorretiva,
        on_delete=models.CASCADE,
        related_name="comentarios",
        verbose_name="Ação"
    )
    autor = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Autor"
    )
    conteudo = models.TextField(verbose_name="Comentário")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data")
    
    class Meta:
        verbose_name = "Comentário"
        verbose_name_plural = "Comentários"
        ordering = ['-data_criacao']
    
    def __str__(self):
        return f"Comentário em {self.acao.titulo}"
