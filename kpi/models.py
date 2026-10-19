from django.contrib.auth.models import User
from django.db import models


class Indicador(models.Model):
    SENTIDO_MAIOR = 'maior'
    SENTIDO_MENOR = 'menor'
    SENTIDOS = [
        (SENTIDO_MAIOR, 'Quanto maior, melhor (meta mínima)'),
        (SENTIDO_MENOR, 'Quanto menor, melhor (meta máxima)'),
    ]
    PERIODICIDADES = [
        ('mensal', 'Mensal'),
        ('semanal', 'Semanal'),
        ('diaria', 'Diária'),
        ('trimestral', 'Trimestral'),
        ('anual', 'Anual'),
    ]

    nome = models.CharField('Indicador', max_length=150)
    descricao = models.TextField('Descrição / fórmula', blank=True)
    area = models.CharField('Área / setor', max_length=100, blank=True)
    unidade = models.CharField('Unidade', max_length=20, blank=True, help_text='Ex.: %, un, h, R$')
    meta = models.DecimalField('Meta', max_digits=14, decimal_places=2)
    sentido = models.CharField('Sentido da meta', max_length=5, choices=SENTIDOS, default=SENTIDO_MAIOR)
    periodicidade = models.CharField('Periodicidade', max_length=12, choices=PERIODICIDADES, default='mensal')
    ACOMPANHAMENTOS = [
        ('', 'Somente fechamento do período'),
        ('diario', 'Acompanhamento diário'),
        ('quinzenal', 'Acompanhamento quinzenal'),
        ('semanal', 'Acompanhamento semanal'),
    ]
    acompanhamento = models.CharField(
        'Acompanhamento parcial', max_length=10, choices=ACOMPANHAMENTOS, blank=True, default='',
        help_text='Permite lançar valores parciais (diários, semanais ou quinzenais) dentro do período do indicador.')
    responsavel = models.CharField('Responsável', max_length=120, blank=True)
    ativo = models.BooleanField('Ativo', default=True)
    criado_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['area', 'nome']
        verbose_name = 'Indicador'
        verbose_name_plural = 'Indicadores'

    def __str__(self):
        return self.nome

    def atingiu(self, valor):
        if valor is None:
            return None
        return valor >= self.meta if self.sentido == self.SENTIDO_MAIOR else valor <= self.meta


class Medicao(models.Model):
    indicador = models.ForeignKey(Indicador, on_delete=models.CASCADE, related_name='medicoes')
    periodo = models.DateField('Período (data de referência)')
    valor = models.DecimalField('Valor', max_digits=14, decimal_places=2)
    parcial = models.BooleanField('Parcial (acompanhamento)', default=False)
    observacao = models.CharField('Observação', max_length=255, blank=True)
    registrado_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    registrado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-periodo']
        unique_together = [('indicador', 'periodo', 'parcial')]
        verbose_name = 'Medição'
        verbose_name_plural = 'Medições'

    def __str__(self):
        return f'{self.indicador} - {self.periodo:%m/%Y}: {self.valor}'
