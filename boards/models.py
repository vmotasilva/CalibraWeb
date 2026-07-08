from django.db import models
from django.contrib.auth.models import User
from rh.models import Colaborador

class Board(models.Model):
    TIPO_CHOICES = [
        ('PADRAO', 'Padrão'),
        ('PLANOS_ACAO', 'Planos de Ação'),
    ]
    nome = models.CharField(max_length=100, verbose_name="Nome do Quadro")
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição")
    criado_por = models.ForeignKey(
        Colaborador, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name="quadros_criados"
    )
    membros = models.ManyToManyField(
        Colaborador, 
        related_name="quadros_participa", 
        verbose_name="Membros do Quadro"
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    arquivado = models.BooleanField(default=False, verbose_name="Arquivado")
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='PADRAO',
        verbose_name="Tipo de Quadro"
    )

    def __str__(self):
        return self.nome

    @property
    def total_tasks(self):
        if self.tipo == 'PLANOS_ACAO':
            from acoes.models import LinhaAcao
            return LinhaAcao.objects.filter(classificacao__in=['corretiva', 'preventiva']).count()
        return Card.objects.filter(coluna__quadro=self).count()

    class Meta:
        verbose_name = "Quadro de Atividades"
        verbose_name_plural = "Quadros de Atividades"
        ordering = ["-criado_em"]


class BoardColumn(models.Model):
    quadro = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="colunas")
    nome = models.CharField(max_length=100, verbose_name="Nome da Coluna")
    ordem = models.IntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)
    status_linha_acao = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Status da Linha de Ação"
    )

    class Meta:
        ordering = ['ordem', 'criado_em']
        verbose_name = "Coluna do Quadro"
        verbose_name_plural = "Colunas do Quadro"

    def __str__(self):
        return f"{self.quadro.nome} - {self.nome}"


class BoardSubSection(models.Model):
    coluna = models.ForeignKey(BoardColumn, on_delete=models.CASCADE, related_name="subsecoes")
    nome = models.CharField(max_length=100, verbose_name="Nome da Sub-sessão")
    ordem = models.IntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ordem', 'criado_em']
        verbose_name = "Sub-sessão da Coluna"
        verbose_name_plural = "Sub-sessões da Coluna"

    def __str__(self):
        return f"{self.coluna.nome} - {self.nome}"

class BoardLabel(models.Model):
    quadro = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="etiquetas")
    nome = models.CharField(max_length=50, verbose_name="Nome da Etiqueta")
    cor = models.CharField(max_length=7, default="#0d6efd", verbose_name="Cor (Hex)")

    class Meta:
        unique_together = ('quadro', 'nome')
        verbose_name = "Etiqueta do Quadro"
        verbose_name_plural = "Etiquetas do Quadro"

    def __str__(self):
        return f"{self.quadro.nome} - {self.nome} ({self.cor})"


class Card(models.Model):
    PRIORIDADE_CHOICES = [
        ('BAIXA', 'Baixa'),
        ('ALTA', 'Alta'),
    ]
    PERIODICIDADE_CHOICES = [
        ('AVULSA', 'Nenhuma (Avulsa)'),
        ('DIARIA', 'Diária'),
        ('SEMANAL', 'Semanal'),
        ('QUINZENAL', 'Quinzenal'),
        ('MENSAL', 'Mensal'),
        ('BIMESTRAL', 'Bimestral'),
        ('TRIMESTRAL', 'Trimestral'),
        ('SEMESTRAL', 'Semestral'),
        ('ANUAL', 'Anual'),
    ]
    coluna = models.ForeignKey(BoardColumn, on_delete=models.CASCADE, related_name="cartoes")
    subsecao = models.ForeignKey(
        BoardSubSection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cartoes",
        verbose_name="Sub-sessão"
    )
    etiquetas = models.ManyToManyField(BoardLabel, blank=True, related_name="cartoes", verbose_name="Etiquetas")
    antecessora = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sucessoras",
        verbose_name="Tarefa Antecessora"
    )

    titulo = models.CharField(max_length=200, verbose_name="Título da Tarefa")
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição")
    link_anexo = models.CharField(max_length=500, blank=True, null=True, verbose_name="Link de Acesso")
    responsaveis = models.ManyToManyField(
        Colaborador, 
        blank=True, 
        related_name="cartoes_atribuidos", 
        verbose_name="Responsáveis"
    )
    data_entrega = models.DateField(blank=True, null=True, verbose_name="Data de Entrega")
    data_inicio = models.DateField(blank=True, null=True, verbose_name="Data de Início")
    data_conclusao = models.DateField(blank=True, null=True, verbose_name="Data de Conclusão")
    hora_inicio = models.TimeField(blank=True, null=True, verbose_name="Hora de Início")
    hora_fim = models.TimeField(blank=True, null=True, verbose_name="Hora de Fim")
    datetime_inicio = models.DateTimeField(blank=True, null=True, verbose_name="Data/Hora de Início")
    datetime_fim = models.DateTimeField(blank=True, null=True, verbose_name="Data/Hora de Fim")
    prioridade = models.CharField(
        max_length=10, 
        choices=PRIORIDADE_CHOICES, 
        default='BAIXA', 
        verbose_name="Prioridade"
    )
    periodicidade = models.CharField(
        max_length=15, 
        choices=PERIODICIDADE_CHOICES, 
        default='AVULSA', 
        verbose_name="Periodicidade"
    )
    ordem = models.IntegerField(default=0)
    criado_por = models.ForeignKey(
        Colaborador, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name="cartoes_criados"
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)


    class Meta:
        ordering = ['ordem', 'criado_em']
        verbose_name = "Cartão de Atividade"
        verbose_name_plural = "Cartões de Atividades"

    def __str__(self):
        return self.titulo


class ChecklistItem(models.Model):
    cartao = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="checklist_itens")
    descricao = models.CharField(max_length=255, verbose_name="Item")
    concluido = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['criado_em']
        verbose_name = "Item de Checklist"
        verbose_name_plural = "Itens de Checklist"

    def __str__(self):
        return self.descricao


class CardComment(models.Model):
    cartao = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="comentarios")
    autor = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True, blank=True)
    texto = models.TextField(verbose_name="Comentário")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = "Comentário do Cartão"
        verbose_name_plural = "Comentários do Cartão"

    def __str__(self):
        return f"Comentário por {self.autor.nome_completo} em {self.cartao.titulo}"


class BoardActivity(models.Model):
    quadro = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="atividades")
    colaborador = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True)
    descricao = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = "Log de Atividade do Quadro"
        verbose_name_plural = "Logs de Atividades do Quadro"

    def __str__(self):
        return f"{self.quadro.nome} - {self.descricao}"


class CardPlanningDate(models.Model):
    cartao = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="planejamentos")
    datetime_inicio = models.DateTimeField(verbose_name="Data/Hora de Início", null=True, blank=True)
    datetime_fim = models.DateTimeField(blank=True, null=True, verbose_name="Data/Hora de Fim")

    class Meta:
        ordering = ['datetime_inicio']
        verbose_name = "Planejamento de Data/Hora"
        verbose_name_plural = "Planejamentos de Data/Hora"

    def __str__(self):
        return f"{self.cartao.titulo} - {self.datetime_inicio.strftime('%d/%m/%Y %H:%M') if self.datetime_inicio else ''}"


class BoardMention(models.Model):
    comentario = models.ForeignKey(CardComment, on_delete=models.CASCADE, related_name="mencoes")
    mencionado = models.ForeignKey(Colaborador, on_delete=models.CASCADE, related_name="mencoes_recebidas")
    criado_por = models.ForeignKey(Colaborador, on_delete=models.CASCADE, related_name="mencoes_feitas", null=True, blank=True)
    visualizada = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = "Menção no Quadro"
        verbose_name_plural = "Menções no Quadro"

    def __str__(self):
        return f"Menção a {self.mencionado.nome_completo} em {self.comentario.cartao.titulo}"

