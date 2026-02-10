from django.db import models

from django.db import models
from rh.models import Colaborador
from django.utils import timezone
from django.db.models import Q


class TemplateSolucao(models.Model):
    """Armazena templates em PDF para cada tipo de solução"""
    
    TIPO_CHOICES = [
        ('plano_acao', 'Plano de Ação'),
        ('a3', 'A3'),
        ('8d', '8D'),
        ('rnc', 'RNC'),
        ('gestao_mudanca', 'Gestão de Mudança'),
        ('revisao_gerencial', 'Revisão Gerencial'),
    ]
    
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        unique=True,
        verbose_name="Tipo de Solução"
    )
    descricao = models.CharField(
        max_length=255,
        verbose_name="Descrição"
    )
    arquivo_pdf = models.FileField(
        upload_to='templates_solucoes/',
        verbose_name="Arquivo PDF"
    )
    data_upload = models.DateTimeField(
        auto_now=True,
        verbose_name="Data de Upload"
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )
    
    class Meta:
        verbose_name = "Template de Solução"
        verbose_name_plural = "Templates de Soluções"
    
    def __str__(self):
        return f"Template {self.get_tipo_display()}"


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
    
    TIPO_SOLUCAO_CHOICES = [
        ('corretiva', 'Corretiva'),
        ('preventiva', 'Preventiva'),
        ('melhoria', 'Melhoria'),
    ]
    
    # Identificação do Registro
    numero_registro = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Nº do Registro"
    )
    ano = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Ano"
    )
    unidade = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Unidade"
    )
    
    # Informações básicas
    titulo = models.CharField(max_length=200, verbose_name="Título da Ação")
    descricao = models.TextField(verbose_name="Descrição da NC e/ou Melhoria")
    tipo = models.CharField(
        max_length=20, 
        choices=TIPO_CHOICES, 
        default='corretiva',
        verbose_name="Tipo de Ação"
    )
    tipo_solucao = models.CharField(
        max_length=20,
        choices=TIPO_SOLUCAO_CHOICES,
        null=True,
        blank=True,
        verbose_name="Tipo de Solução"
    )
    prioridade = models.CharField(
        max_length=20,
        choices=PRIORIDADE_CHOICES,
        default='media',
        verbose_name="Prioridade"
    )
    
    # Origem e Causa
    origem = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Origem do Problema"
    )
    causa_raiz = models.TextField(
        null=True,
        blank=True,
        verbose_name="Causa Raiz"
    )
    
    # Status e prazos
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='aberta',
        verbose_name="Status"
    )
    data_abertura = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data de Abertura"
    )
    data_vencimento = models.DateField(
        verbose_name="Data de Fechamento Programada"
    )
    data_conclusao = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data de Fechamento"
    )
    
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
    meta = models.TextField(null=True, blank=True, verbose_name="Meta/Objetivo")
    resultado = models.TextField(null=True, blank=True, verbose_name="Resultado Obtido")
    observacoes = models.TextField(null=True, blank=True, verbose_name="Observação")
    link_registro = models.URLField(
        null=True,
        blank=True,
        verbose_name="Link do Registro"
    )
    
    # Ativo/Inativo
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    
    class Meta:
        verbose_name = "Ação Corretiva/Preventiva"
        verbose_name_plural = "Ações Corretivas/Preventivas"
        ordering = ['-data_abertura']
        indexes = [
            models.Index(fields=['-data_abertura']),
            models.Index(fields=['status']),
            models.Index(fields=['responsavel']),
            models.Index(fields=['prioridade']),
            models.Index(fields=['numero_registro']),
        ]
    
    def __str__(self):
        return f"{self.numero_registro} - {self.titulo}"
    
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


class Solucao(models.Model):
    """Modelo para gerenciar diferentes tipos de soluções (A3, 8D, RNC, etc.)"""
    
    TIPO_SOLUCAO_CHOICES = [
        ('plano_acao', 'Plano de Ação'),
        ('a3', 'A3'),
        ('8d', '8D'),
        ('rnc', 'RNC'),
        ('gestao_mudanca', 'Gestão de Mudança'),
        ('revisao_gerencial', 'Revisão Gerencial'),
    ]
    
    STATUS_CHOICES = [
        ('planejamento', 'Planejamento'),
        ('analise', 'Análise'),
        ('implementacao', 'Implementação'),
        ('validacao', 'Validação'),
        ('encerrada', 'Encerrada'),
    ]
    
    # Relacionamento
    acao_corretiva = models.ForeignKey(
        AcaoCorretiva,
        on_delete=models.CASCADE,
        related_name="solucoes",
        verbose_name="Ação Corretiva"
    )
    
    # Informações básicas
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_SOLUCAO_CHOICES,
        verbose_name="Tipo de Solução"
    )
    titulo = models.CharField(max_length=200, verbose_name="Título da Solução")
    descricao = models.TextField(verbose_name="Descrição")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='planejamento',
        verbose_name="Status"
    )
    
    # Datas
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_inicio = models.DateField(null=True, blank=True, verbose_name="Data de Início")
    data_conclusao = models.DateField(null=True, blank=True, verbose_name="Data de Conclusão")
    
    # Responsáveis
    responsavel = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        related_name="solucoes_responsavel",
        verbose_name="Responsável"
    )
    
    # Rastreamento
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    
    class Meta:
        verbose_name = "Solução"
        verbose_name_plural = "Soluções"
        ordering = ['-data_criacao']
    
    def __str__(self):
        return f"{self.get_tipo_display()} - {self.titulo}"


class PlanoAcao(models.Model):
    """Modelo para Plano de Ação simples"""
    
    STATUS_CHOICES = [
        ('planejado', 'Planejado'),
        ('em_execucao', 'Em Execução'),
        ('concluido', 'Concluído'),
        ('cancelado', 'Cancelado'),
    ]
    
    solucao = models.OneToOneField(
        Solucao,
        on_delete=models.CASCADE,
        related_name="plano_acao",
        verbose_name="Solução"
    )
    
    acao_proposta = models.TextField(verbose_name="Ação Proposta")
    responsavel_acao = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planos_acao",
        verbose_name="Responsável pela Ação"
    )
    data_inicio = models.DateField(verbose_name="Data de Início")
    data_conclusao = models.DateField(verbose_name="Data de Conclusão")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='planejado',
        verbose_name="Status"
    )
    resultado = models.TextField(null=True, blank=True, verbose_name="Resultado")
    
    class Meta:
        verbose_name = "Plano de Ação"
        verbose_name_plural = "Planos de Ação"
    
    def __str__(self):
        return f"Plano de Ação - {self.solucao.titulo}"


class SolucaoA3(models.Model):
    """Modelo para Solução tipo A3 - Relatório em 1 página"""
    
    solucao = models.OneToOneField(
        Solucao,
        on_delete=models.CASCADE,
        related_name="a3",
        verbose_name="Solução"
    )
    
    # Problema
    problema_descricao = models.TextField(verbose_name="Descrição do Problema")
    problema_impacto = models.TextField(verbose_name="Impacto do Problema")
    
    # Situação atual
    situacao_atual = models.TextField(verbose_name="Situação Atual")
    
    # Análise
    analise_causas = models.TextField(verbose_name="Análise de Causas")
    causa_raiz = models.TextField(verbose_name="Causa Raiz Identificada")
    
    # Contramedidas
    contramedidas = models.TextField(verbose_name="Contramedidas Propostas")
    
    # Resultados esperados
    resultados_esperados = models.TextField(verbose_name="Resultados Esperados")
    
    # Acompanhamento
    plano_verificacao = models.TextField(null=True, blank=True, verbose_name="Plano de Verificação")
    resultado_verificacao = models.TextField(null=True, blank=True, verbose_name="Resultado da Verificação")
    
    class Meta:
        verbose_name = "Solução A3"
        verbose_name_plural = "Soluções A3"
    
    def __str__(self):
        return f"A3 - {self.solucao.titulo}"


class Solucao8D(models.Model):
    """Modelo para Solução tipo 8D - 8 Disciplinas"""
    
    DISCIPLINA_CHOICES = [
        ('d1', 'D1 - Nomear o Time'),
        ('d2', 'D2 - Descrever o Problema'),
        ('d3', 'D3 - Conter o Problema'),
        ('d4', 'D4 - Análise de Causa Raiz'),
        ('d5', 'D5 - Desenvolvimento de Contramedidas'),
        ('d6', 'D6 - Implementação de Contramedidas'),
        ('d7', 'D7 - Verificação de Efetividade'),
        ('d8', 'D8 - Padronização/Fechamento'),
    ]
    
    solucao = models.OneToOneField(
        Solucao,
        on_delete=models.CASCADE,
        related_name="oito_d",
        verbose_name="Solução"
    )
    
    # D1
    d1_time = models.TextField(verbose_name="D1 - Time Responsável")
    
    # D2
    d2_descricao = models.TextField(verbose_name="D2 - Descrição do Problema")
    d2_especificacoes = models.TextField(verbose_name="D2 - Especificações Afetadas")
    
    # D3
    d3_contencao = models.TextField(null=True, blank=True, verbose_name="D3 - Plano de Contenção")
    
    # D4
    d4_causas = models.TextField(null=True, blank=True, verbose_name="D4 - Análise de Causas")
    d4_causa_raiz = models.TextField(null=True, blank=True, verbose_name="D4 - Causa Raiz")
    
    # D5
    d5_contramedidas = models.TextField(null=True, blank=True, verbose_name="D5 - Contramedidas Propostas")
    
    # D6
    d6_implementacao = models.TextField(null=True, blank=True, verbose_name="D6 - Plano de Implementação")
    
    # D7
    d7_verificacao = models.TextField(null=True, blank=True, verbose_name="D7 - Verificação de Efetividade")
    d7_resultado = models.TextField(null=True, blank=True, verbose_name="D7 - Resultado")
    
    # D8
    d8_padronizacao = models.TextField(null=True, blank=True, verbose_name="D8 - Padronização")
    d8_encerramento = models.TextField(null=True, blank=True, verbose_name="D8 - Encerramento")
    
    class Meta:
        verbose_name = "Solução 8D"
        verbose_name_plural = "Soluções 8D"
    
    def __str__(self):
        return f"8D - {self.solucao.titulo}"


class SolucaoRNC(models.Model):
    """Modelo para Solução tipo RNC - Relatório de Não Conformidade"""
    
    solucao = models.OneToOneField(
        Solucao,
        on_delete=models.CASCADE,
        related_name="rnc",
        verbose_name="Solução"
    )
    
    # Não conformidade
    nc_descricao = models.TextField(verbose_name="Descrição da Não Conformidade")
    nc_tipo = models.CharField(
        max_length=50,
        choices=[('maior', 'Maior'), ('menor', 'Menor')],
        verbose_name="Tipo de NC"
    )
    
    # Análise
    analise_causas = models.TextField(verbose_name="Análise de Causas")
    causa_raiz = models.TextField(verbose_name="Causa Raiz")
    
    # Ações
    acao_imediata = models.TextField(verbose_name="Ação Imediata")
    acao_corretiva = models.TextField(verbose_name="Ação Corretiva")
    acao_preventiva = models.TextField(null=True, blank=True, verbose_name="Ação Preventiva")
    
    # Verificação
    plano_verificacao = models.TextField(verbose_name="Plano de Verificação")
    resultado = models.TextField(null=True, blank=True, verbose_name="Resultado")
    
    class Meta:
        verbose_name = "Solução RNC"
        verbose_name_plural = "Soluções RNC"
    
    def __str__(self):
        return f"RNC - {self.solucao.titulo}"


class SolucaoGestaoDeMudanca(models.Model):
    """Modelo para Solução tipo Gestão de Mudança"""
    
    STATUS_CHOICES = [
        ('proposta', 'Proposta'),
        ('analise', 'Análise'),
        ('aprovada', 'Aprovada'),
        ('implementada', 'Implementada'),
        ('rejeitada', 'Rejeitada'),
    ]
    
    solucao = models.OneToOneField(
        Solucao,
        on_delete=models.CASCADE,
        related_name="gestao_mudanca",
        verbose_name="Solução"
    )
    
    # Mudança
    mudanca_descricao = models.TextField(verbose_name="Descrição da Mudança")
    motivacao = models.TextField(verbose_name="Motivação/Justificativa")
    
    # Impacto
    impacto_processos = models.TextField(verbose_name="Impacto em Processos")
    impacto_sistemas = models.TextField(null=True, blank=True, verbose_name="Impacto em Sistemas")
    impacto_pessoas = models.TextField(null=True, blank=True, verbose_name="Impacto em Pessoas")
    
    # Plano
    plano_implementacao = models.TextField(verbose_name="Plano de Implementação")
    data_implementacao = models.DateField(verbose_name="Data de Implementação")
    
    # Aprovação
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='proposta',
        verbose_name="Status"
    )
    
    # Verificação
    plano_validacao = models.TextField(null=True, blank=True, verbose_name="Plano de Validação")
    resultado_validacao = models.TextField(null=True, blank=True, verbose_name="Resultado da Validação")
    
    class Meta:
        verbose_name = "Gestão de Mudança"
        verbose_name_plural = "Gestões de Mudança"
    
    def __str__(self):
        return f"Gestão de Mudança - {self.solucao.titulo}"


class RevisaoGerencial(models.Model):
    """Modelo para Solução tipo Revisão Gerencial"""
    
    solucao = models.OneToOneField(
        Solucao,
        on_delete=models.CASCADE,
        related_name="revisao_gerencial",
        verbose_name="Solução"
    )
    
    # Revisão
    revisao_descricao = models.TextField(verbose_name="Descrição da Revisão")
    escopo = models.TextField(verbose_name="Escopo da Revisão")
    
    # Achados
    achados_principais = models.TextField(verbose_name="Achados Principais")
    oportunidades_melhoria = models.TextField(verbose_name="Oportunidades de Melhoria")
    
    # Recomendações
    recomendacoes = models.TextField(verbose_name="Recomendações")
    prioridade_implementacao = models.CharField(
        max_length=20,
        choices=[('alta', 'Alta'), ('media', 'Média'), ('baixa', 'Baixa')],
        verbose_name="Prioridade de Implementação"
    )
    
    # Acompanhamento
    plano_acao = models.TextField(verbose_name="Plano de Ação")
    responsavel_implementacao = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revisoes_gerenciais",
        verbose_name="Responsável pela Implementação"
    )
    data_alvo_implementacao = models.DateField(verbose_name="Data Alvo de Implementação")
    
    # Validação
    resultado = models.TextField(null=True, blank=True, verbose_name="Resultado")
    data_conclusao = models.DateField(null=True, blank=True, verbose_name="Data de Conclusão")
    
    class Meta:
        verbose_name = "Revisão Gerencial"
        verbose_name_plural = "Revisões Gerenciais"
    
    def __str__(self):
        return f"Revisão Gerencial - {self.solucao.titulo}"
