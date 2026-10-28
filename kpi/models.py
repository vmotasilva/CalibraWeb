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
    exibir_mensal = models.BooleanField('Gráfico mês a mês', default=True)
    exibir_semanal = models.BooleanField('Gráfico semana a semana', default=False)
    exibir_diario = models.BooleanField('Gráfico dia a dia', default=False)
    motivos_diario = models.BooleanField('Tabela de motivos — Diário', default=False)
    motivos_semanal = models.BooleanField('Tabela de motivos — Semanal', default=False)
    motivos_mensal = models.BooleanField('Tabela de motivos — Mensal', default=False)
    campos = models.TextField(
        'Campos do indicador', blank=True,
        help_text='Um campo por linha (ex.: Lentes produzidas, Lentes perdidas). Aparecem nos lançamentos e nos modelos de importação.')
    formula = models.CharField(
        'Fórmula do valor', max_length=200, blank=True,
        help_text='Opcional. Calcula o valor a partir dos campos. Ex.: [Lentes perdidas] / [Lentes produzidas] * 100')
    grupo = models.CharField(
        'Grupo de variáveis compartilhadas', max_length=100, blank=True,
        help_text='Opcional. Indicadores do mesmo grupo que têm uma variável com o mesmo nome compartilham o valor: lançou em um, vale para todos.')
    responsavel = models.CharField('Responsável', max_length=120, blank=True)
    responsavel_analise = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        verbose_name='Responsável pela causa e análise',
        help_text='Recebe a cobrança das causas e análises dos períodos fora da meta (geral e setores sem responsável próprio).')
    ordem = models.PositiveIntegerField('Ordem de exibição', default=0, help_text='Define a ordem das abas no painel (menor primeiro).')
    ativo = models.BooleanField('Ativo', default=True)
    criado_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ordem', 'area', 'nome']
        verbose_name = 'Indicador'
        verbose_name_plural = 'Indicadores'

    def __str__(self):
        return self.nome

    @property
    def acompanhamento_detalhado(self):
        return self.exibir_semanal or self.exibir_diario

    def permite_valor(self, gran):
        """Lançamento de valores: o mensal é sempre permitido; semanal/diário dependem do gráfico habilitado."""
        return gran == 'mensal' or bool(getattr(self, {'semanal': 'exibir_semanal', 'diaria': 'exibir_diario'}[gran]))

    def permite_motivos(self, gran):
        return bool(getattr(self, {'diaria': 'motivos_diario', 'semanal': 'motivos_semanal', 'mensal': 'motivos_mensal'}[gran]))

    def graficos(self):
        return [g for g, on in (('mensal', self.exibir_mensal), ('semanal', self.exibir_semanal), ('diaria', self.exibir_diario)) if on]

    def atingiu(self, valor, meta=None):
        """Compara com a meta geral ou, se informada, com a meta do setor."""
        if valor is None:
            return None
        meta = self.meta if meta is None else meta
        return valor >= meta if self.sentido == self.SENTIDO_MAIOR else valor <= meta


class SetorIndicador(models.Model):
    """Setor que influencia a meta de um indicador; tem meta e lançamentos próprios. Opcional."""
    indicador = models.ForeignKey(Indicador, on_delete=models.CASCADE, related_name='setores')
    nome = models.CharField('Setor', max_length=100)
    meta = models.DecimalField('Meta do setor', max_digits=14, decimal_places=2, null=True, blank=True,
                               help_text='Se vazia, vale a meta geral do indicador.')
    responsavel_analise = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        verbose_name='Responsável pela causa e análise do setor',
        help_text='Se vazio, vale o responsável geral do indicador.')
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordem', 'nome']
        unique_together = [('indicador', 'nome')]
        verbose_name = 'Setor do indicador'
        verbose_name_plural = 'Setores do indicador'

    def __str__(self):
        return f'{self.indicador} / {self.nome}'

    @property
    def meta_efetiva(self):
        return self.meta if self.meta is not None else self.indicador.meta


class Medicao(models.Model):
    indicador = models.ForeignKey(Indicador, on_delete=models.CASCADE, related_name='medicoes')
    setor = models.ForeignKey(SetorIndicador, null=True, blank=True, on_delete=models.PROTECT, related_name='medicoes')
    periodo = models.DateField('Período (data de referência)')
    valor = models.DecimalField('Valor', max_digits=14, decimal_places=2)
    GRANULARIDADES = [('mensal', 'Mensal'), ('semanal', 'Semanal'), ('diaria', 'Diária')]
    granularidade = models.CharField('Granularidade', max_length=8, choices=GRANULARIDADES, default='mensal')
    dados = models.JSONField('Campos do indicador', default=dict, blank=True)
    observacao = models.CharField('Observação', max_length=255, blank=True)
    registrado_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    registrado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-periodo']
        unique_together = [('indicador', 'setor', 'periodo', 'granularidade')]
        verbose_name = 'Medição'
        verbose_name_plural = 'Medições'

    def __str__(self):
        return f'{self.indicador} - {self.periodo:%m/%Y}: {self.valor}'


class Motivo(models.Model):
    """Motivo (causa) associado a um indicador em uma data; alimenta a tabela Top principais motivos."""
    indicador = models.ForeignKey(Indicador, on_delete=models.CASCADE, related_name='motivos')
    setor = models.ForeignKey(SetorIndicador, null=True, blank=True, on_delete=models.PROTECT, related_name='motivos')
    granularidade = models.CharField('Período', max_length=8, choices=Medicao.GRANULARIDADES, default='diaria')
    data = models.DateField('Data de referência')
    descricao = models.CharField('Motivo', max_length=200)
    quantidade = models.DecimalField('Quantidade', max_digits=14, decimal_places=2, default=1)
    consolidado = models.BooleanField('Consolidado dos lançamentos diários', default=False)
    registrado_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['-data', 'descricao']
        verbose_name = 'Motivo'
        verbose_name_plural = 'Motivos'

    def __str__(self):
        return f'{self.indicador} - {self.descricao} ({self.quantidade})'


class ModeloColagem(models.Model):
    """Modelo de colagem: lista ordenada que relaciona cada posição de uma lista de números a um indicador/variável."""
    nome = models.CharField('Nome do modelo', max_length=100, unique=True)
    linhas = models.TextField(
        'Posições', help_text='Uma linha por número colado, na ordem: Rótulo | Indicador | Variável | Setor (opcional).')
    criado_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Modelo de colagem'
        verbose_name_plural = 'Modelos de colagem'

    def __str__(self):
        return self.nome


class AnaliseCausa(models.Model):
    """Causa e análise (justificativa/plano de ação) de um período fora da meta: dia, semana ou mês."""
    indicador = models.ForeignKey(Indicador, on_delete=models.CASCADE, related_name='analises')
    setor = models.ForeignKey(SetorIndicador, null=True, blank=True, on_delete=models.CASCADE, related_name='analises')
    granularidade = models.CharField('Período', max_length=8, choices=Medicao.GRANULARIDADES)
    periodo = models.DateField('Período (data de referência)')
    causa = models.TextField('Causa', blank=True)
    analise = models.TextField('Análise e ações', blank=True)
    dispensada = models.BooleanField('Dispensada de análise', default=False)
    motivo_dispensa = models.CharField('Motivo da dispensa', max_length=200, blank=True)
    registrado_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('indicador', 'setor', 'granularidade', 'periodo')]
        ordering = ['-periodo']
        verbose_name = 'Causa e análise'
        verbose_name_plural = 'Causas e análises'

    def __str__(self):
        return f'{self.indicador} - {self.get_granularidade_display()} {self.periodo:%d/%m/%Y}'


class AnaliseItem(models.Model):
    """Um card de causa, análise e ação de um período fora da meta. Um período pode ter vários."""
    registro = models.ForeignKey(AnaliseCausa, on_delete=models.CASCADE, related_name='itens')
    ordem = models.PositiveSmallIntegerField(default=0)
    causa = models.TextField('Causa', blank=True)
    analise = models.TextField('Análise', blank=True)
    acao = models.TextField('Ação', blank=True)
    ocorrencias = models.ManyToManyField('laboratorio.OcorrenciaLaboratorio', blank=True, related_name='+',
                                         verbose_name='Ocorrências do laboratório que afetaram o indicador')

    class Meta:
        ordering = ['ordem', 'id']
        verbose_name = 'Item de causa e análise'
        verbose_name_plural = 'Itens de causa e análise'


class MotivoCadastro(models.Model):
    """Base de cadastro de motivos (de perda ou de retorno), em Gestão > Processos > Motivos de Perdas."""
    TIPO_PERDA, TIPO_RETORNO = 'perda', 'retorno'
    TIPOS = [(TIPO_PERDA, 'Motivo de perda'), (TIPO_RETORNO, 'Motivo de retorno')]

    tipo = models.CharField('Tipo', max_length=8, choices=TIPOS)
    nome = models.CharField('Motivo', max_length=150)
    descricao = models.CharField('Descrição', max_length=255, blank=True)
    ordem = models.PositiveIntegerField('Ordem', default=0)
    ativo = models.BooleanField('Ativo', default=True)

    class Meta:
        ordering = ['tipo', 'ordem', 'nome']
        unique_together = [('tipo', 'nome')]
        verbose_name = 'Motivo cadastrado'
        verbose_name_plural = 'Motivos cadastrados'

    def __str__(self):
        return f'{self.get_tipo_display()}: {self.nome}'
