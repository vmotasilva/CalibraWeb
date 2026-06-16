from django.db import models
from django.contrib.auth.models import User
from rh.models import Colaborador

class Board(models.Model):
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

    def __str__(self):
        return self.nome

    @property
    def total_tasks(self):
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

    class Meta:
        ordering = ['ordem', 'criado_em']
        verbose_name = "Coluna do Quadro"
        verbose_name_plural = "Colunas do Quadro"

    def __str__(self):
        return f"{self.quadro.nome} - {self.nome}"


class Card(models.Model):
    PRIORIDADE_CHOICES = [
        ('BAIXA', 'Baixa'),
        ('MEDIA', 'Média'),
        ('ALTA', 'Alta'),
    ]
    coluna = models.ForeignKey(BoardColumn, on_delete=models.CASCADE, related_name="cartoes")
    titulo = models.CharField(max_length=200, verbose_name="Título da Tarefa")
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição")
    responsavel = models.ForeignKey(
        Colaborador, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="cartoes_atribuidos", 
        verbose_name="Responsável"
    )
    data_entrega = models.DateField(blank=True, null=True, verbose_name="Data de Entrega")
    prioridade = models.CharField(
        max_length=10, 
        choices=PRIORIDADE_CHOICES, 
        default='BAIXA', 
        verbose_name="Prioridade"
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
    autor = models.ForeignKey(Colaborador, on_delete=models.CASCADE)
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
