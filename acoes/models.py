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
        ('atrasada', 'Atrasada'),
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
        max_length=100,
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
    link_registro = models.CharField(
        max_length=500,
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
    """Modelo para Plano de Ação com alinhamento ao template Excel"""
    
    STATUS_CHOICES = [
        ('planejada', 'Planejada'),
        ('em_curso', 'Em Curso/Andamento'),
        ('completa', 'Completa/Concluído'),
        ('retardo', 'Retardo/Atrasada'),
        ('cancelada', 'Cancelada'),
    ]
    
    CLASSIFICACAO_CHOICES = [
        ('corretiva', 'Corretiva'),
        ('preventiva', 'Preventiva'),
        ('melhoria', 'Melhoria'),
    ]
    
    solucao = models.OneToOneField(
        Solucao,
        on_delete=models.CASCADE,
        related_name="plano_acao",
        verbose_name="Solução"
    )
    
    # Informações do Plano
    laboratorio_area_projeto = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        verbose_name="Laboratório, Área ou Projeto"
    )
    numero_registro = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Nº Registro"
    )
    
    # Campos da tabela de ações (conforme Excel)
    numero_acao = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Nº Ação"
    )
    input_origem = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Input/Origem"
    )
    problema = models.TextField(
        null=True,
        blank=True,
        verbose_name="Problema"
    )
    laboratorio = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Lab"
    )
    kpi = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="KPI"
    )
    descricao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Descrição / Descripción"
    )
    classificacao = models.CharField(
        max_length=20,
        choices=CLASSIFICACAO_CHOICES,
        null=True,
        blank=True,
        verbose_name="Classificação"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='planejada',
        verbose_name="Status"
    )
    prioridade = models.BooleanField(
        default=False,
        verbose_name="Prioridade (Y/N)"
    )
    responsavel_acao = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planos_acao",
        verbose_name="Responsável (Legado)"
    )
    responsaveis_multiplos = models.ManyToManyField(
        Colaborador,
        blank=True,
        related_name="planos_acao_multiplos",
        verbose_name="Responsáveis (Múltiplos)"
    )
    data_primeira_deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name="1º Deadline"
    )
    data_deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name="Deadline Final"
    )
    comentarios = models.TextField(
        null=True,
        blank=True,
        verbose_name="Comentários"
    )
    acao_eficaz = models.CharField(
        max_length=20,
        choices=[
            ('eficaz', 'Eficaz'),
            ('nao_eficaz', 'Não Eficaz'),
            ('parcialmente_eficaz', 'Parcialmente Eficaz'),
        ],
        null=True,
        blank=True,
        verbose_name="Ação Eficaz?"
    )
    
    # Resultado e conclusão
    resultado = models.TextField(
        null=True,
        blank=True,
        verbose_name="Resultado Obtido"
    )
    data_conclusao = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data de Conclusão"
    )
    
    # Campos de rastreamento
    criado_em = models.DateTimeField(
        auto_now_add=True,
        null=True,
        blank=True,
        verbose_name="Criado em"
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        null=True,
        blank=True,
        verbose_name="Atualizado em"
    )
    
    class Meta:
        verbose_name = "Plano de Ação"
        verbose_name_plural = "Planos de Ação"
        ordering = ['numero_acao']
        indexes = [
            models.Index(fields=['numero_acao']),
            models.Index(fields=['status']),
            models.Index(fields=['prioridade']),
        ]
    
    def __str__(self):
        return f"Ação {self.numero_acao} - {self.descricao[:50]}"
    
    def percentual_conclusao(self):
        """Calcula percentual de conclusão baseado no status"""
        status_weight = {
            'planejada': 0,
            'em_curso': 50,
            'completa': 100,
            'retardo': 25,
            'cancelada': 0,
        }
        return status_weight.get(self.status, 0)


class LinhaAcao(models.Model):
    """Modelo para cada linha de ação dentro de um Plano de Ação"""
    
    STATUS_CHOICES = [
        ('planejada', 'Planejada'),
        ('em_curso', 'Em Curso/Andamento'),
        ('completa', 'Completa/Concluído'),
        ('retardo', 'Retardo/Atrasada'),
        ('cancelada', 'Cancelada'),
    ]
    
    CLASSIFICACAO_CHOICES = [
        ('corretiva', 'Corretiva'),
        ('preventiva', 'Preventiva'),
        ('melhoria', 'Melhoria'),
    ]
    
    plano_acao = models.ForeignKey(
        PlanoAcao,
        on_delete=models.CASCADE,
        related_name="linhas_acao",
        verbose_name="Plano de Ação"
    )
    
    numero_acao = models.IntegerField(
        verbose_name="Nº Ação"
    )
    input_origem = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Input/Origem"
    )
    problema = models.TextField(
        null=True,
        blank=True,
        verbose_name="Problema"
    )
    kpi = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="KPI"
    )
    descricao = models.TextField(
        verbose_name="Descrição"
    )
    classificacao = models.CharField(
        max_length=20,
        choices=CLASSIFICACAO_CHOICES,
        null=True,
        blank=True,
        verbose_name="Classificação"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='planejada',
        verbose_name="Status"
    )
    prioridade = models.BooleanField(
        default=False,
        verbose_name="Prioridade (Y/N)"
    )
    responsavel_acao = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linhas_acao_responsavel",
        verbose_name="Responsável Principal"
    )
    responsaveis_multiplos = models.ManyToManyField(
        Colaborador,
        blank=True,
        related_name="linhas_acao_multiplos",
        verbose_name="Responsáveis (Múltiplos)"
    )
    responsaveis_externos = models.TextField(
        null=True,
        blank=True,
        verbose_name="Responsáveis Externos"
    )
    data_primeira_deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name="1º Deadline"
    )
    data_deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name="Deadline Final"
    )
    comentarios = models.TextField(
        null=True,
        blank=True,
        verbose_name="Comentários"
    )
    acao_eficaz = models.CharField(
        max_length=20,
        choices=[
            ('eficaz', 'Eficaz'),
            ('nao_eficaz', 'Não Eficaz'),
            ('parcialmente_eficaz', 'Parcialmente Eficaz'),
        ],
        null=True,
        blank=True,
        verbose_name="Ação Eficaz?"
    )
    data_conclusao = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data de Conclusão"
    )
    
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )
    
    class Meta:
        verbose_name = "Linha de Ação"
        verbose_name_plural = "Linhas de Ação"
        ordering = ['plano_acao', 'numero_acao']
        unique_together = ['plano_acao', 'numero_acao']
        indexes = [
            models.Index(fields=['plano_acao', 'numero_acao']),
            models.Index(fields=['status']),
            models.Index(fields=['prioridade']),
        ]
    
    def __str__(self):
        return f"Ação #{self.numero_acao} - {self.descricao[:50]}"
    
    def percentual_conclusao(self):
        """Calcula percentual de conclusão baseado no status"""
        status_weight = {
            'planejada': 0,
            'em_curso': 50,
            'completa': 100,
            'retardo': 25,
            'cancelada': 0,
        }
        return status_weight.get(self.status, 0)


class SolucaoA3(models.Model):
    """Modelo para Solução tipo A3 - Relatório em 1 página com alinhamento ao template Excel"""
    
    STATUS_CHOICES = [
        ('planejada', 'Planejada'),
        ('em_curso', 'Em Curso/Andamento'),
        ('completa', 'Completa/Concluído'),
        ('retardo', 'Retardo/Atrasada'),
    ]
    
    PRIORIDADE_CHOICES = [
        ('y', 'Sim'),
        ('n', 'Não'),
    ]
    
    CLASSIFICACAO_CHOICES = [
        ('corretiva', 'Corretiva'),
        ('preventiva', 'Preventiva'),
        ('melhoria', 'Melhoria'),
    ]
    
    solucao = models.OneToOneField(
        Solucao,
        on_delete=models.CASCADE,
        related_name="a3",
        verbose_name="Solução"
    )
    
    # IDENTIFICAÇÃO (Conforme Excel A3.xlsx)
    a3_numero = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name="A3 Nº"
    )
    # Novos campos para alinhamento com "Ações Registradas"
    numero_acao = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Nº Ação"
    )
    input_origem = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Input/Origem"
    )
    kpi = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="KPI"
    )
    classificacao = models.CharField(
        max_length=20,
        choices=CLASSIFICACAO_CHOICES,
        null=True,
        blank=True,
        verbose_name="Classificação"
    )
    prioridade = models.BooleanField(
        default=False,
        verbose_name="Prioridade (Y/N)"
    )
    responsaveis_multiplos = models.ManyToManyField(
        Colaborador,
        blank=True,
        related_name="a3s_responsaveis",
        verbose_name="Responsáveis (Múltiplos)"
    )
    data_primeira_deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name="1º Deadline"
    )
    comentarios = models.TextField(
        null=True,
        blank=True,
        verbose_name="Comentários"
    )
    acao_eficaz = models.CharField(
        max_length=20,
        choices=[
            ('eficaz', 'Eficaz'),
            ('nao_eficaz', 'Não Eficaz'),
            ('parcialmente_eficaz', 'Parcialmente Eficaz'),
        ],
        null=True,
        blank=True,
        verbose_name="Ação Eficaz?"
    )
    data_criacao = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data"
    )
    laboratorio = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Laboratório"
    )
    lider_projeto = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="a3_lider",
        verbose_name="Líder do Projeto"
    )
    participantes = models.TextField(
        null=True,
        blank=True,
        verbose_name="Participantes"
    )
    
    # PROBLEMA
    problema = models.TextField(
        null=True,
        blank=True,
        verbose_name="Problema"
    )
    historico_importancia = models.TextField(
        null=True,
        blank=True,
        verbose_name="HISTÓRICO / IMPORTÂNCIA"
    )
    observacoes_importantes = models.TextField(
        null=True,
        blank=True,
        verbose_name="Observações Importantes"
    )
    
    # FERRAMENTAS DE QUALIDADE UTILIZADAS
    ferramenta_fluxograma = models.BooleanField(
        default=False,
        verbose_name="Fluxograma"
    )
    ferramenta_brainstorming = models.BooleanField(
        default=False,
        verbose_name="Brainstorming"
    )
    ferramenta_ishikawa = models.BooleanField(
        default=False,
        verbose_name="Diagrama de Ishikawa"
    )
    ferramenta_5_porques = models.BooleanField(
        default=False,
        verbose_name="5 Porquês"
    )
    ferramenta_grafico_pareto = models.BooleanField(
        default=False,
        verbose_name="Gráfico de Pareto"
    )
    ferramenta_checklist = models.BooleanField(
        default=False,
        verbose_name="Check List"
    )
    ferramenta_grafico_geral = models.BooleanField(
        default=False,
        verbose_name="Gráfico Geral"
    )
    ferramenta_carta_tendencia = models.BooleanField(
        default=False,
        verbose_name="Carta de Tendência"
    )
    ferramenta_antes_depois = models.BooleanField(
        default=False,
        verbose_name="Antes x Depois"
    )
    
    # ANÁLISE (A.ANALISAR)
    analise_causas = models.TextField(
        null=True,
        blank=True,
        verbose_name="Análise de Causas"
    )
    causa_raiz = models.TextField(
        null=True,
        blank=True,
        verbose_name="Causa Raiz Identificada"
    )
    
    # DEFINIÇÃO (D.DEFINIR)
    objetivo = models.TextField(
        null=True,
        blank=True,
        verbose_name="Objetivo (D.DEFINIR)"
    )
    
    # IMPLEMENTAÇÃO (I.IMPLEMENTAR / Plano de Ação)
    plano_acao_relacionado = models.ForeignKey(
        PlanoAcao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="a3s_relacionados",
        verbose_name="Plano de Ação (Implementação)"
    )
    
    # MÉTRICAS (Computed - Read-only)
    total_acoes_planejadas = models.IntegerField(
        default=0,
        null=True,
        blank=True,
        verbose_name="Total de Ações Planejadas"
    )
    total_acoes_completas = models.IntegerField(
        default=0,
        null=True,
        blank=True,
        verbose_name="Total de Ações Completas"
    )
    total_acoes_andamento = models.IntegerField(
        default=0,
        null=True,
        blank=True,
        verbose_name="Total de Ações em Andamento"
    )
    total_acoes_prioridade_andamento = models.IntegerField(
        default=0,
        null=True,
        blank=True,
        verbose_name="Total de Ações Prioridade em Andamento"
    )
    
    # MEDIÇÃO (M.MEDIR)
    estado_atual = models.TextField(
        null=True,
        blank=True,
        verbose_name="M. MEDIR (Estado Atual / Anterior)"
    )
    
    # CONTROLE (C.CONTROLE)
    resultados = models.TextField(
        null=True,
        blank=True,
        verbose_name="C. CONTROLE (Resultados)"
    )
    
    # Rastreamento
    criado_em = models.DateTimeField(
        auto_now_add=True,
        null=True,
        blank=True,
        verbose_name="Criado em"
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        null=True,
        blank=True,
        verbose_name="Atualizado em"
    )
    
    class Meta:
        verbose_name = "Solução A3"
        verbose_name_plural = "Soluções A3"
        ordering = ['-data_criacao']
        indexes = [
            models.Index(fields=['a3_numero']),
            models.Index(fields=['lider_projeto']),
        ]
    
    def __str__(self):
        return f"A3 {self.a3_numero} - {self.problema[:50]}"


class Solucao8D(models.Model):
    """Modelo para Solução tipo 8D - 8 Disciplinas com alinhamento ao template Excel"""
    
    DISCIPLINA_CHOICES = [
        ('d1', 'D1 - Formação da Equipe'),
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
    
    # D1 - FORMAÇÃO DA EQUIPE
    numero_formulario = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Número do Formulário"
    )
    data_abertura = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Abertura"
    )
    lider_8d = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="d8_lider",
        verbose_name="Líder 8D"
    )
    patrocinador = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Patrocinador"
    )
    equipe = models.TextField(
        null=True,
        blank=True,
        verbose_name="Equipe"
    )
    departamento = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Departamento"
    )
    problema_identificado = models.TextField(
        null=True,
        blank=True,
        verbose_name="Problema Identificado"
    )
    prazo_projeto = models.DateField(
        null=True,
        blank=True,
        verbose_name="Prazo Projeto 8D"
    )
    
    # D2 - DESCREVER O PROBLEMA
    d2_descricao = models.TextField(
        null=True,
        blank=True,
        verbose_name="D2 - Descrição do Problema"
    )
    d2_especificacoes = models.TextField(
        null=True,
        blank=True,
        verbose_name="D2 - Especificações Afetadas"
    )
    
    # D3 - CONTER O PROBLEMA
    d3_contencao = models.TextField(
        null=True,
        blank=True,
        verbose_name="D3 - Plano de Contenção"
    )
    d3_responsavel = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="d8_d3_responsavel",
        verbose_name="D3 - Responsável"
    )
    d3_deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name="D3 - Deadline"
    )
    
    # D4 - ANÁLISE DE CAUSA RAIZ
    d4_analise_causas = models.TextField(
        null=True,
        blank=True,
        verbose_name="D4 - Análise de Causas"
    )
    d4_ferramentas_qualidade = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="D4 - Ferramentas de Qualidade Utilizadas"
    )
    d4_causa_raiz = models.TextField(
        null=True,
        blank=True,
        verbose_name="D4 - Causa Raiz"
    )
    
    # D5 - DESENVOLVIMENTO DE CONTRAMEDIDAS
    d5_contramedidas = models.TextField(
        null=True,
        blank=True,
        verbose_name="D5 - Contramedidas Propostas"
    )
    d5_criterios_selecao = models.TextField(
        null=True,
        blank=True,
        verbose_name="D5 - Critérios de Seleção"
    )
    
    # D6 - IMPLEMENTAÇÃO DE CONTRAMEDIDAS
    d6_implementacao = models.TextField(
        null=True,
        blank=True,
        verbose_name="D6 - Plano de Implementação"
    )
    d6_responsavel = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="d8_d6_responsavel",
        verbose_name="D6 - Responsável"
    )
    d6_deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name="D6 - Deadline de Implementação"
    )
    d6_status = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="D6 - Status de Implementação"
    )
    
    # D7 - VERIFICAÇÃO DE EFETIVIDADE
    d7_verificacao = models.TextField(
        null=True,
        blank=True,
        verbose_name="D7 - Plano de Verificação"
    )
    d7_resultado = models.TextField(
        null=True,
        blank=True,
        verbose_name="D7 - Resultado da Verificação"
    )
    d7_efetivo = models.BooleanField(
        null=True,
        blank=True,
        verbose_name="D7 - Resultado Efetivo?"
    )
    
    # D8 - PADRONIZAÇÃO E FECHAMENTO
    d8_padronizacao = models.TextField(
        null=True,
        blank=True,
        verbose_name="D8 - Padronização"
    )
    d8_documentos_atualizados = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="D8 - Documentos Atualizados"
    )
    d8_treinamento = models.TextField(
        null=True,
        blank=True,
        verbose_name="D8 - Plano de Treinamento"
    )
    d8_encerramento = models.TextField(
        null=True,
        blank=True,
        verbose_name="D8 - Encerramento"
    )
    
    # Análise e causas (mantido para compatibilidade)
    analise_causas = models.TextField(
        null=True,
        blank=True,
        verbose_name="Análise de Causas"
    )
    causa_raiz = models.TextField(
        null=True,
        blank=True,
        verbose_name="Causa Raiz"
    )
    
    # Novos campos para alinhamento com "Ações Registradas"
    numero_acao = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Nº Ação"
    )
    input_origem = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Input/Origem"
    )
    laboratorio = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Laboratório"
    )
    kpi = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="KPI"
    )
    classificacao = models.CharField(
        max_length=20,
        choices=[('corretiva', 'Corretiva'), ('preventiva', 'Preventiva'), ('melhoria', 'Melhoria')],
        null=True,
        blank=True,
        verbose_name="Classificação"
    )
    status = models.CharField(
        max_length=20,
        choices=[('planejada', 'Planejada'), ('em_curso', 'Em Curso/Andamento'), ('completa', 'Completa/Concluído'), ('retardo', 'Retardo/Atrasada'), ('cancelada', 'Cancelada')],
        default='planejada',
        verbose_name="Status"
    )
    prioridade = models.BooleanField(
        default=False,
        verbose_name="Prioridade (Y/N)"
    )
    responsaveis_multiplos = models.ManyToManyField(
        Colaborador,
        blank=True,
        related_name="solucoes_8d_responsaveis",
        verbose_name="Responsáveis (Múltiplos)"
    )
    data_primeira_deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name="1º Deadline"
    )
    comentarios = models.TextField(
        null=True,
        blank=True,
        verbose_name="Comentários"
    )
    acao_eficaz = models.CharField(
        max_length=20,
        choices=[
            ('eficaz', 'Eficaz'),
            ('nao_eficaz', 'Não Eficaz'),
            ('parcialmente_eficaz', 'Parcialmente Eficaz'),
        ],
        null=True,
        blank=True,
        verbose_name="Ação Eficaz?"
    )
    
    # Rastreamento
    criado_em = models.DateTimeField(
        auto_now_add=True,
        null=True,
        blank=True,
        verbose_name="Criado em"
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        null=True,
        blank=True,
        verbose_name="Atualizado em"
    )
    
    class Meta:
        verbose_name = "Solução 8D"
        verbose_name_plural = "Soluções 8D"
        ordering = ['-data_abertura']
        indexes = [
            models.Index(fields=['numero_formulario']),
            models.Index(fields=['lider_8d']),
        ]
    
    def __str__(self):
        return f"8D {self.numero_formulario} - {self.problema_identificado[:50]}"


class SolucaoRNC(models.Model):
    """Modelo para RNC - Registro de Não Conformidade com alinhamento ao template Excel"""
    
    ORIGEM_CHOICES = [
        ('insumo', 'Insumo'),
        ('produto', 'Produto'),
        ('indicador', 'Indicador'),
        ('auditoria', 'Auditoria'),
        ('equipamento_medicao', 'Equipamento de Medição'),
        ('processo', 'Processo'),
        ('fornecedor', 'Fornecedor'),
        ('testes_qualidade', 'Testes de Qualidade'),
        ('outros', 'Outros'),
    ]
    
    CLASSIFICACAO_CHOICES = [
        ('critica', 'Crítica'),
        ('maior', 'Maior'),
        ('menor', 'Menor'),
        ('oportunidade_melhoria', 'Oportunidade de Melhoria'),
    ]
    
    FREQUENCIA_CHOICES = [
        ('rara', 'Rara'),
        ('ocasional', 'Ocasional'),
        ('frequente', 'Frequente'),
    ]
    
    RISCO_CHOICES = [
        ('baixo', 'Baixo'),
        ('medio', 'Médio'),
        ('alto', 'Alto'),
    ]
    
    ACAO_NC_CHOICES = [
        ('aprovar_concessao', 'Aprovar sob Concessão'),
        ('rejeitar', 'Rejeitar'),
        ('corrigir', 'Corrigir'),
    ]
    
    EFICACIA_CHOICES = [
        ('eficaz', 'Eficaz'),
        ('nao_eficaz', 'Não Eficaz'),
    ]
    
    solucao = models.OneToOneField(
        Solucao,
        on_delete=models.CASCADE,
        related_name="rnc",
        verbose_name="Solução"
    )
    
    # Identificação
    unidade = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Unidade"
    )
    numero_rnc = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Nº da RNC"
    )
    data_abertura = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data da Abertura"
    )
    
    # Origem e Classificação
    origem = models.CharField(
        max_length=30,
        choices=ORIGEM_CHOICES,
        null=True,
        blank=True,
        verbose_name="Origem"
    )
    classificacao = models.CharField(
        max_length=30,
        choices=CLASSIFICACAO_CHOICES,
        default='maior',
        verbose_name="Classificação"
    )
    
    # Requerimento/Requisito
    requerimento_requisito = models.TextField(
        null=True,
        blank=True,
        verbose_name="Requerimento/Requisito"
    )
    
    # Descrição da Não Conformidade
    descricao_nc = models.TextField(
        null=True,
        blank=True,
        verbose_name="Descrição da Não Conformidade"
    )
    
    # Evidência
    evidencia_nc = models.TextField(
        null=True,
        blank=True,
        verbose_name="Evidência da Não Conformidade"
    )
    
    # Gerenciamento de Risco
    frequencia = models.CharField(
        max_length=20,
        choices=FREQUENCIA_CHOICES,
        null=True,
        blank=True,
        verbose_name="Frequência"
    )
    risco = models.CharField(
        max_length=20,
        choices=RISCO_CHOICES,
        null=True,
        blank=True,
        verbose_name="Nível de Risco"
    )
    
    # Tratativas
    causa_raiz = models.TextField(
        null=True,
        blank=True,
        verbose_name="Causa Raiz"
    )
    acao_contencao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Ação de Contenção"
    )
    acao_nc = models.CharField(
        max_length=30,
        choices=ACAO_NC_CHOICES,
        null=True,
        blank=True,
        verbose_name="Ação sobre Não Conformidade"
    )
    
    # Ligação com Plano de Ação
    gerar_plano_acao = models.BooleanField(
        default=False,
        verbose_name="Gerar Plano de Ação"
    )
    plano_acao_relacionado = models.ForeignKey(
        PlanoAcao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rncs_relacionadas",
        verbose_name="Plano de Ação Relacionado"
    )
    
    # Conclusão
    eficacia = models.CharField(
        max_length=20,
        choices=EFICACIA_CHOICES,
        null=True,
        blank=True,
        verbose_name="Análise Crítica da Eficácia"
    )
    evidencia_implementacao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Evidência da Implementação"
    )
    responsavel = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rncs_responsavel",
        verbose_name="Responsável"
    )
    data_fechamento = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data do Fechamento"
    )
    
    # Análise e Ações Corretivas
    analise_causas = models.TextField(
        null=True,
        blank=True,
        verbose_name="Análise de Causas"
    )
    acao_imediata = models.TextField(
        null=True,
        blank=True,
        verbose_name="Ação Imediata"
    )
    acao_corretiva = models.TextField(
        null=True,
        blank=True,
        verbose_name="Ação Corretiva"
    )
    acao_preventiva = models.TextField(
        null=True,
        blank=True,
        verbose_name="Ação Preventiva"
    )
    
    # Verificação
    plano_verificacao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Plano de Verificação"
    )
    resultado = models.TextField(
        null=True,
        blank=True,
        verbose_name="Resultado"
    )
    
    # Novos campos para alinhamento com "Ações Registradas"
    numero_acao = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Nº Ação"
    )
    input_origem = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Input/Origem"
    )
    laboratorio = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Laboratório"
    )
    kpi = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="KPI"
    )
    descricao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Descrição"
    )
    status = models.CharField(
        max_length=20,
        choices=[('planejada', 'Planejada'), ('em_curso', 'Em Curso/Andamento'), ('completa', 'Completa/Concluído'), ('retardo', 'Retardo/Atrasada'), ('cancelada', 'Cancelada')],
        default='planejada',
        verbose_name="Status"
    )
    prioridade = models.BooleanField(
        default=False,
        verbose_name="Prioridade (Y/N)"
    )
    responsaveis_multiplos = models.ManyToManyField(
        Colaborador,
        blank=True,
        related_name="rncs_responsaveis_multiplos",
        verbose_name="Responsáveis (Múltiplos)"
    )
    data_primeira_deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name="1º Deadline"
    )
    comentarios = models.TextField(
        null=True,
        blank=True,
        verbose_name="Comentários"
    )
    acao_eficaz = models.CharField(
        max_length=20,
        choices=[
            ('eficaz', 'Eficaz'),
            ('nao_eficaz', 'Não Eficaz'),
            ('parcialmente_eficaz', 'Parcialmente Eficaz'),
        ],
        null=True,
        blank=True,
        verbose_name="Ação Eficaz?"
    )
    
    # Rastreamento
    criado_em = models.DateTimeField(
        auto_now_add=True,
        null=True,
        blank=True,
        verbose_name="Criado em"
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        null=True,
        blank=True,
        verbose_name="Atualizado em"
    )
    
    class Meta:
        verbose_name = "Registro de Não Conformidade"
        verbose_name_plural = "Registros de Não Conformidade"
        ordering = ['-data_abertura']
        indexes = [
            models.Index(fields=['numero_rnc']),
            models.Index(fields=['classificacao']),
            models.Index(fields=['risco']),
        ]
    
    def __str__(self):
        return f"RNC {self.numero_rnc} - {self.descricao_nc[:50]}"


class SolucaoGestaoDeMudanca(models.Model):
    """Modelo para Gestão de Mudança com alinhamento ao template FOR.137.R5"""
    
    TIPO_MUDANCA_CHOICES = [
        ('regulatorio', 'Regulatório'),
        ('qms_sgi', 'QMS/SGI'),
        ('projetos', 'Projetos'),
    ]
    
    PRIORIDADE_MUDANCA_CHOICES = [
        ('urgente', 'Urgente'),
        ('alto', 'Alto'),
        ('medio', 'Médio'),
    ]
    
    STATUS_CHOICES = [
        ('proposta', 'Proposta'),
        ('analise', 'Análise'),
        ('aprovada', 'Aprovada'),
        ('implementada', 'Implementada'),
        ('rejeitada', 'Rejeitada'),
    ]
    
    IMPACTO_EHS_CHOICES = [
        ('nao_aplica', 'Não Aplica'),
        ('baixo', 'Baixo'),
        ('medio', 'Médio'),
        ('alto', 'Alto'),
        ('critico', 'Crítico'),
    ]
    
    solucao = models.OneToOneField(
        Solucao,
        on_delete=models.CASCADE,
        related_name="gestao_mudanca",
        verbose_name="Solução"
    )
    
    # INFORMAÇÕES GERAIS
    unidade = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Unidade"
    )
    data_abertura = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data da Abertura"
    )
    solicitante = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Solicitante"
    )
    numero_registro = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Nº do Registro"
    )
    tipo_mudanca = models.CharField(
        max_length=20,
        choices=TIPO_MUDANCA_CHOICES,
        null=True,
        blank=True,
        verbose_name="Tipo de Mudança"
    )
    prioridade_mudanca = models.CharField(
        max_length=20,
        choices=PRIORIDADE_MUDANCA_CHOICES,
        null=True,
        blank=True,
        verbose_name="Prioridade da Mudança"
    )
    area_impactada = models.TextField(
        null=True,
        blank=True,
        verbose_name="Área(s) Impactada(s)"
    )
    area_avaliadora = models.TextField(
        null=True,
        blank=True,
        verbose_name="Área Avaliadora (setores/departamentos)"
    )
    
    # DADOS DA MUDANÇA
    situacao_antes = models.TextField(
        null=True,
        blank=True,
        verbose_name="Situação (Antes da Mudança)"
    )
    situacao_depois = models.TextField(
        null=True,
        blank=True,
        verbose_name="Situação Projetada (Após Mudança)"
    )
    justificativa = models.TextField(
        null=True,
        blank=True,
        verbose_name="Justificativa"
    )
    beneficios = models.TextField(
        null=True,
        blank=True,
        verbose_name="Benefícios"
    )
    data_mudanca = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data da Mudança/Projeto"
    )
    evidencia = models.TextField(
        null=True,
        blank=True,
        verbose_name="Evidência (imagens e/ou informações antes da mudança)"
    )
    
    # IMPACTOS DE EHS
    impacto_pessoas = models.TextField(
        null=True,
        blank=True,
        verbose_name="Impacto - Pessoas (Saúde, Segurança Química/Elétrica, Ergonomia)"
    )
    referencia_pessoas = models.CharField(
        max_length=20,
        choices=IMPACTO_EHS_CHOICES,
        null=True,
        blank=True,
        verbose_name="Referência Necessária - Pessoas"
    )
    
    impacto_ambiente = models.TextField(
        null=True,
        blank=True,
        verbose_name="Impacto - Meio Ambiente (Emissões, Resíduos, Energia)"
    )
    referencia_ambiente = models.CharField(
        max_length=20,
        choices=IMPACTO_EHS_CHOICES,
        null=True,
        blank=True,
        verbose_name="Referência Necessária - Ambiente"
    )
    
    impacto_ativos = models.TextField(
        null=True,
        blank=True,
        verbose_name="Impacto - Propriedades e Ativos (Instalações, Equipamentos)"
    )
    referencia_ativos = models.CharField(
        max_length=20,
        choices=IMPACTO_EHS_CHOICES,
        null=True,
        blank=True,
        verbose_name="Referência Necessária - Ativos"
    )
    
    impacto_compliance = models.TextField(
        null=True,
        blank=True,
        verbose_name="Impacto - Compliance (Regulamentos)"
    )
    referencia_compliance = models.CharField(
        max_length=20,
        choices=IMPACTO_EHS_CHOICES,
        null=True,
        blank=True,
        verbose_name="Referência Necessária - Compliance"
    )
    
    # RISCOS ENVOLVIDOS
    processos_afetados = models.TextField(
        null=True,
        blank=True,
        verbose_name="Quais processos serão afetados pela mudança"
    )
    modulos_sistema_afetados = models.TextField(
        null=True,
        blank=True,
        verbose_name="Quais módulos do sistema serão afetados"
    )
    como_afeta_processo = models.TextField(
        null=True,
        blank=True,
        verbose_name="Como a mudança afeta o processo atual"
    )
    consequencia_nao_mudanca = models.TextField(
        null=True,
        blank=True,
        verbose_name="Consequência de não realizar a mudança"
    )
    riscos_identificados = models.TextField(
        null=True,
        blank=True,
        verbose_name="Riscos Identificados"
    )
    tratamento_riscos = models.TextField(
        null=True,
        blank=True,
        verbose_name="Tratamento dos Riscos"
    )
    plano_contingencia = models.TextField(
        null=True,
        blank=True,
        verbose_name="Plano de Contingência em caso de riscos"
    )
    areas_implantacao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Áreas envolvidas na implantação"
    )
    observacoes = models.TextField(
        null=True,
        blank=True,
        verbose_name="Observações"
    )
    
    # Ligação com Plano de Ação
    gerar_plano_acao = models.BooleanField(
        default=False,
        verbose_name="Gerar Plano de Ação"
    )
    plano_acao_relacionado = models.ForeignKey(
        PlanoAcao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gestoes_mudanca_relacionadas",
        verbose_name="Plano de Ação Relacionado"
    )
    percentual_conclusao_plano = models.FloatField(
        default=0,
        verbose_name="Percentual de Conclusão do Plano"
    )
    
    # ANÁLISE CRÍTICA PELAS ÁREAS AVALIADORAS
    sera_implantada = models.BooleanField(
        null=True,
        blank=True,
        verbose_name="Mudança será implantada"
    )
    
    # Área Avaliadora 1
    justificativa_area1 = models.TextField(
        null=True,
        blank=True,
        verbose_name="Justificativa/Parecer (Área 1)"
    )
    responsavel_decisao_area1 = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Responsável pela Decisão (Área 1)"
    )
    data_area1 = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data (Área 1)"
    )
    
    # Área Avaliadora 2
    justificativa_area2 = models.TextField(
        null=True,
        blank=True,
        verbose_name="Justificativa/Parecer (Área 2)"
    )
    responsavel_decisao_area2 = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Responsável pela Decisão (Área 2)"
    )
    data_area2 = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data (Área 2)"
    )
    
    # Comunicação
    solicitante_informado = models.BooleanField(
        null=True,
        blank=True,
        verbose_name="Solicitante Informado"
    )
    data_informada = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data Informada"
    )
    
    # Status geral
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='proposta',
        verbose_name="Status"
    )
    
    # Verificação
    plano_validacao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Plano de Validação"
    )
    resultado_validacao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Resultado da Validação"
    )
    
    # Novos campos para alinhamento com "Ações Registradas"
    numero_acao = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Nº Ação"
    )
    input_origem = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Input/Origem"
    )
    laboratorio_acao = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Laboratório"
    )
    kpi = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="KPI"
    )
    descricao_acao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Descrição"
    )
    classificacao = models.CharField(
        max_length=20,
        choices=[('corretiva', 'Corretiva'), ('preventiva', 'Preventiva'), ('melhoria', 'Melhoria')],
        null=True,
        blank=True,
        verbose_name="Classificação"
    )
    prioridade = models.BooleanField(
        default=False,
        verbose_name="Prioridade (Y/N)"
    )
    responsaveis_multiplos = models.ManyToManyField(
        Colaborador,
        blank=True,
        related_name="gestoes_mudanca_responsaveis",
        verbose_name="Responsáveis (Múltiplos)"
    )
    data_primeira_deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name="1º Deadline"
    )
    comentarios = models.TextField(
        null=True,
        blank=True,
        verbose_name="Comentários"
    )
    acao_eficaz = models.CharField(
        max_length=20,
        choices=[
            ('eficaz', 'Eficaz'),
            ('nao_eficaz', 'Não Eficaz'),
            ('parcialmente_eficaz', 'Parcialmente Eficaz'),
        ],
        null=True,
        blank=True,
        verbose_name="Ação Eficaz?"
    )
    
    # Rastreamento
    criado_em = models.DateTimeField(
        auto_now_add=True,
        null=True,
        blank=True,
        verbose_name="Criado em"
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        null=True,
        blank=True,
        verbose_name="Atualizado em"
    )
    
    class Meta:
        verbose_name = "Gestão de Mudança"
        verbose_name_plural = "Gestões de Mudança"
        ordering = ['-data_abertura']
        indexes = [
            models.Index(fields=['numero_registro']),
            models.Index(fields=['status']),
            models.Index(fields=['prioridade_mudanca']),
        ]
    
    def __str__(self):
        return f"Gestão de Mudança {self.numero_registro} - {self.tipo_mudanca}"


class RevisaoGerencial(models.Model):
    """Modelo para Revisão Gerencial - Análise Crítica com alinhamento ao template Excel"""
    
    STATUS_CHOICES = [
        ('planejada', 'Planejada'),
        ('em_andamento', 'Em Andamento'),
        ('finalizada', 'Finalizada'),
        ('cancelada', 'Cancelada'),
    ]
    
    solucao = models.OneToOneField(
        Solucao,
        on_delete=models.CASCADE,
        related_name="revisao_gerencial",
        verbose_name="Solução"
    )
    
    # IDENTIFICAÇÃO (Conforme Excel Revisão Gerencial.xlsx)
    numero_rg = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Nº Registro"
    )
    data_realizacao = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data da realização desta reunião"
    )
    laboratorio = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        verbose_name="Laboratório"
    )
    periodo_inicio = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Período desta Revisão Gerencial (Início)"
    )
    periodo_fim = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Período desta Revisão Gerencial (Fim)"
    )
    
    # PARTICIPANTES
    representante_direcao = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Representante da Direção"
    )
    responsavel_unidade = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Responsável pela Unidade"
    )
    participantes = models.TextField(
        null=True,
        blank=True,
        verbose_name="Participantes"
    )
    
    # ENTRADAS
    entradas_acompanhamento = models.TextField(
        null=True,
        blank=True,
        verbose_name="1. Ações de acompanhamento de análises críticas anteriores"
    )
    entradas_auditorias = models.TextField(
        null=True,
        blank=True,
        verbose_name="2. Resultados de auditorias"
    )
    entradas_satisfacao = models.TextField(
        null=True,
        blank=True,
        verbose_name="3. Satisfação de clientes"
    )
    entradas_desempenho = models.TextField(
        null=True,
        blank=True,
        verbose_name="Desempenho de processos e conformidade"
    )
    entradas_pessoal = models.TextField(
        null=True,
        blank=True,
        verbose_name="Adequação de recursos (pessoal)"
    )
    entradas_fornecedores = models.TextField(
        null=True,
        blank=True,
        verbose_name="Desempenho de fornecedores"
    )
    entradas_mudancas = models.TextField(
        null=True,
        blank=True,
        verbose_name="Alterações e mudanças"
    )
    entradas_risco = models.TextField(
        null=True,
        blank=True,
        verbose_name="Avaliação de risco"
    )
    entradas_oportunidades = models.TextField(
        null=True,
        blank=True,
        verbose_name="Oportunidades de melhoria"
    )
    
    # SAÍDAS
    saidas_eficacia_sgq = models.TextField(
        null=True,
        blank=True,
        verbose_name="1. Melhoria da eficácia do SGQ e de seus processos"
    )
    saidas_melhoria_produto = models.TextField(
        null=True,
        blank=True,
        verbose_name="2. Melhoria do produto em relação aos requisitos"
    )
    saidas_necessidades_cliente = models.TextField(
        null=True,
        blank=True,
        verbose_name="3. Atendimento de necessidades de partes interessadas"
    )
    saidas_necessidade_recurso = models.TextField(
        null=True,
        blank=True,
        verbose_name="4. Necessidade de recursos"
    )
    
    # ANÁLISES CRÍTICAS (Seção principal)
    analises_criticas = models.TextField(
        null=True,
        blank=True,
        verbose_name="Análises Críticas Realizadas"
    )
    
    # PLANO DE AÇÃO RELACIONADO
    plano_acao_relacionado = models.ForeignKey(
        PlanoAcao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revisoes_gerenciais",
        verbose_name="Plano de Ação Relacionado"
    )
    
    # MÉTRICAS (Do Plano de Ação associado)
    total_acoes_planejadas = models.IntegerField(
        default=0,
        null=True,
        blank=True,
        verbose_name="Total de Ações Planejadas"
    )
    total_acoes_completas = models.IntegerField(
        default=0,
        null=True,
        blank=True,
        verbose_name="Total de Ações Completas"
    )
    total_acoes_andamento = models.IntegerField(
        default=0,
        null=True,
        blank=True,
        verbose_name="Total de Ações em Andamento"
    )
    total_acoes_prioridade_andamento = models.IntegerField(
        default=0,
        null=True,
        blank=True,
        verbose_name="Total de Ações Prioridade em Andamento"
    )
    percentual_conclusao = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        null=True,
        blank=True,
        verbose_name="Percentual de Conclusão"
    )
    
    # Novos campos para alinhamento com "Ações Registradas"
    numero_acao = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Nº Ação"
    )
    input_origem = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Input/Origem"
    )
    kpi = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="KPI"
    )
    descricao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Descrição"
    )
    classificacao = models.CharField(
        max_length=20,
        choices=[('corretiva', 'Corretiva'), ('preventiva', 'Preventiva'), ('melhoria', 'Melhoria')],
        null=True,
        blank=True,
        verbose_name="Classificação"
    )
    prioridade = models.BooleanField(
        default=False,
        verbose_name="Prioridade (Y/N)"
    )
    responsaveis_multiplos = models.ManyToManyField(
        Colaborador,
        blank=True,
        related_name="revisoes_gerenciais_responsaveis",
        verbose_name="Responsáveis (Múltiplos)"
    )
    data_primeira_deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name="1º Deadline"
    )
    comentarios = models.TextField(
        null=True,
        blank=True,
        verbose_name="Comentários"
    )
    acao_eficaz = models.CharField(
        max_length=20,
        choices=[
            ('eficaz', 'Eficaz'),
            ('nao_eficaz', 'Não Eficaz'),
            ('parcialmente_eficaz', 'Parcialmente Eficaz'),
        ],
        null=True,
        blank=True,
        verbose_name="Ação Eficaz?"
    )
    
    # STATUS E RASTREAMENTO
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='planejada',
        verbose_name="Status"
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        null=True,
        blank=True,
        verbose_name="Criado em"
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        null=True,
        blank=True,
        verbose_name="Atualizado em"
    )
    
    class Meta:
        verbose_name = "Revisão Gerencial"
        verbose_name_plural = "Revisões Gerenciais"
        ordering = ['-data_realizacao']
        indexes = [
            models.Index(fields=['numero_rg']),
            models.Index(fields=['data_realizacao']),
        ]
    
    def __str__(self):
        return f"RG {self.numero_rg} - {self.laboratorio}"


# ============================================================================
# ORIGENS DE PROBLEMA
# ============================================================================

class OrigemProblema(models.Model):
    """Modelo para armazenar as possíveis origens de problemas."""
    
    nome = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nome da Origem"
    )
    descricao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Descrição"
    )
    codigo = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Código"
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )
    
    class Meta:
        verbose_name = "Origem de Problema"
        verbose_name_plural = "Origens de Problema"
        ordering = ['nome']
        indexes = [
            models.Index(fields=['nome']),
            models.Index(fields=['ativo']),
        ]
    
    def __str__(self):
        return self.nome


class KPIOpcao(models.Model):
    """Modelo para armazenar opções de KPI configuráveis."""
    
    nome = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nome do KPI"
    )
    descricao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Descrição"
    )
    codigo = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Código"
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )
    
    class Meta:
        verbose_name = "Opção de KPI"
        verbose_name_plural = "Opções de KPI"
        ordering = ['nome']
        indexes = [
            models.Index(fields=['nome']),
            models.Index(fields=['ativo']),
        ]
    
    def __str__(self):
        return self.nome


class TipoSolucao(models.Model):
    """Modelo para armazenar tipos de solucao configuraveis."""

    nome = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nome do Tipo"
    )
    descricao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Descricao"
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )

    class Meta:
        verbose_name = "Tipo de Solucao"
        verbose_name_plural = "Tipos de Solucao"
        ordering = ['nome']
        indexes = [
            models.Index(fields=['nome']),
            models.Index(fields=['ativo']),
        ]

    def __str__(self):
        return self.nome
