from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


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
    padrao = models.BooleanField('Modelo padrão', default=False, help_text='Vem selecionado na tela de colagem.')
    criado_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Modelo de colagem'
        verbose_name_plural = 'Modelos de colagem'

    def __str__(self):
        return self.nome


class LoteColagem(models.Model):
    """Registro de uma gravação por colagem, com o antes/depois de cada medição alterada (permite desfazer)."""
    modelo = models.ForeignKey(ModeloColagem, null=True, blank=True, on_delete=models.SET_NULL, related_name='lotes')
    modelo_nome = models.CharField('Modelo', max_length=100)
    granularidade = models.CharField('Período', max_length=8, choices=Medicao.GRANULARIDADES)
    periodo = models.DateField('Data de referência')
    texto = models.TextField('Números colados', blank=True)
    alteracoes = models.JSONField('Medições alteradas', default=list, blank=True)
    criado_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    criado_em = models.DateTimeField(default=timezone.now)
    desfeito_em = models.DateTimeField(null=True, blank=True)
    desfeito_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['-criado_em', '-pk']
        verbose_name = 'Lote de colagem'
        verbose_name_plural = 'Lotes de colagem'

    def __str__(self):
        return f'{self.modelo_nome} - {self.periodo:%d/%m/%Y} ({self.criado_em:%d/%m/%Y %H:%M})'


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

    # Um card é um relato (comentário) ou uma ocorrência: esta tem plano de ação (ações com responsável e
    # prazo, em shared.AcaoOcorrencia) e é acompanhada até a resolução na Central de Ocorrências.
    TIPO_COMENTARIO, TIPO_OCORRENCIA = 'comentario', 'ocorrencia'
    TIPOS = [(TIPO_COMENTARIO, 'Relato'), (TIPO_OCORRENCIA, 'Ocorrência')]
    STATUS_ABERTA, STATUS_RESOLVIDA = 'ABERTA', 'RESOLVIDA'
    STATUS = [(STATUS_ABERTA, 'Em aberto'), (STATUS_RESOLVIDA, 'Resolvida')]
    tipo = models.CharField('Tipo', max_length=10, choices=TIPOS, default=TIPO_COMENTARIO, db_index=True)
    status = models.CharField('Situação', max_length=10, choices=STATUS, default=STATUS_ABERTA, db_index=True)
    resolucao = models.TextField('Resolução', blank=True)
    resolvido_em = models.DateTimeField(null=True, blank=True)
    resolvido_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    criado_em = models.DateTimeField(default=timezone.now)

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


class KpiHierarquico(models.Model):
    """KPI em árvore (ex.: Insumos): Setor > Categoria (ex.: máquina) > Subcategoria (item avaliado), com consumo mensal."""
    nome = models.CharField('KPI', max_length=100, unique=True)
    descricao = models.CharField('Descrição', max_length=255, blank=True)
    ordem = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField('Ativo', default=True)

    class Meta:
        ordering = ['ordem', 'nome']
        verbose_name = 'KPI por setor'
        verbose_name_plural = 'KPIs por setor'

    def __str__(self):
        return self.nome


class HierSetor(models.Model):
    kpi = models.ForeignKey(KpiHierarquico, on_delete=models.CASCADE, related_name='setores')
    nome = models.CharField('Setor', max_length=100)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordem', 'nome']
        unique_together = [('kpi', 'nome')]
        verbose_name = 'Setor (KPI por setor)'
        verbose_name_plural = 'Setores (KPI por setor)'

    def __str__(self):
        return f'{self.kpi} / {self.nome}'


class HierCategoria(models.Model):
    setor = models.ForeignKey(HierSetor, on_delete=models.CASCADE, related_name='categorias')
    nome = models.CharField('Categoria', max_length=100, help_text='Ex.: a máquina (Corte Orbit 2.0, Polimento DLP).')
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordem', 'nome']
        unique_together = [('setor', 'nome')]
        verbose_name = 'Categoria (KPI por setor)'
        verbose_name_plural = 'Categorias (KPI por setor)'

    def __str__(self):
        return f'{self.setor} / {self.nome}'


class HierSubcategoria(models.Model):
    """Agrupador abaixo da categoria (ex.: o modelo da máquina: DLP, Toro Flex, Orbit 2.0)."""
    categoria = models.ForeignKey(HierCategoria, on_delete=models.CASCADE, related_name='subcategorias')
    nome = models.CharField('Subcategoria', max_length=100)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordem', 'nome']
        unique_together = [('categoria', 'nome')]
        verbose_name = 'Subcategoria (KPI por setor)'
        verbose_name_plural = 'Subcategorias (KPI por setor)'

    def __str__(self):
        return f'{self.categoria} / {self.nome}'


class HierItem(models.Model):
    """Item avaliado (ex.: Pads, Diamante, Líquido polidor). Tem meta própria de consumo (quanto menor, melhor) e
    recebe o consumo dos códigos de almoxarifado vinculados a ele (HierCodigo)."""
    subcategoria = models.ForeignKey(HierSubcategoria, on_delete=models.CASCADE, related_name='itens')
    nome = models.CharField('Item avaliado', max_length=100)
    unidade = models.CharField('Unidade', max_length=20, blank=True, help_text='Ex.: L, un, kg.')
    meta = models.DecimalField('Meta de consumo mensal (máximo)', max_digits=14, decimal_places=2, null=True, blank=True)
    ordem = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField('Ativo', default=True)

    class Meta:
        ordering = ['ordem', 'nome']
        unique_together = [('subcategoria', 'nome')]
        verbose_name = 'Item (KPI por setor)'
        verbose_name_plural = 'Itens (KPI por setor)'

    def __str__(self):
        return f'{self.subcategoria} / {self.nome}'

    def atingiu(self, valor):
        if valor is None or self.meta is None:
            return None
        return valor <= self.meta


class HierConsumo(models.Model):
    """Consumo de um item em um mês (período = último dia do mês). Vem do cálculo sobre as movimentações
    importadas (origem 'importado') ou de lançamento manual, que prevalece sobre o importado."""
    ORIGEM_MANUAL, ORIGEM_IMPORTADO = 'manual', 'importado'
    ORIGENS = [(ORIGEM_MANUAL, 'Manual'), (ORIGEM_IMPORTADO, 'Importado')]

    item = models.ForeignKey(HierItem, on_delete=models.CASCADE, related_name='consumos')
    periodo = models.DateField('Mês (último dia)')
    valor = models.DecimalField('Consumo', max_digits=14, decimal_places=2)
    origem = models.CharField('Origem', max_length=10, choices=ORIGENS, default=ORIGEM_MANUAL)
    observacao = models.CharField('Observação', max_length=255, blank=True)
    registrado_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    registrado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-periodo']
        unique_together = [('item', 'periodo')]
        verbose_name = 'Consumo (KPI por setor)'
        verbose_name_plural = 'Consumos (KPI por setor)'

    def __str__(self):
        return f'{self.item} - {self.periodo:%m/%Y}: {self.valor}'


class HierCodigo(models.Model):
    """Código do insumo no almoxarifado (chave única do tipo de insumo), vinculado a um item avaliado."""
    codigo = models.PositiveIntegerField('Código', unique=True)
    descricao = models.CharField('Material / referência', max_length=300, blank=True)
    unidade = models.CharField('Unidade do almoxarifado', max_length=20, blank=True)
    familia = models.CharField('Família (almoxarifado)', max_length=100, blank=True)
    item = models.ForeignKey(HierItem, null=True, blank=True, on_delete=models.SET_NULL, related_name='codigos')
    fator = models.DecimalField('Fator de conversão', max_digits=14, decimal_places=6, default=1,
                                help_text='Multiplica a quantidade do código para chegar na unidade do item (ex.: galão → litros).')
    ignorado = models.BooleanField('Ignorado (fora do KPI)', default=False, db_index=True)

    class Meta:
        ordering = ['codigo']
        verbose_name = 'Código de insumo'
        verbose_name_plural = 'Códigos de insumo'

    def __str__(self):
        return f'{self.codigo} - {self.descricao}'


class HierMovimento(models.Model):
    """Uma saída do almoxarifado importada do relatório de movimentação. Guardada integralmente: vincular ou
    desvincular um código recalcula o consumo sem precisar reimportar."""
    codigo = models.ForeignKey(HierCodigo, on_delete=models.CASCADE, related_name='movimentos')
    data = models.DateField(db_index=True)
    quantidade = models.DecimalField(max_digits=14, decimal_places=3)
    tipo = models.CharField('Tipo de movimento', max_length=20, help_text='UTILIZACOES, PERDAS, DEVOLUCAO...')
    origem = models.CharField(max_length=30, blank=True)
    identif = models.BigIntegerField('Identificador do movimento', null=True, blank=True)

    class Meta:
        ordering = ['-data', 'codigo']
        indexes = [models.Index(fields=['codigo', 'data'], name='kpi_hiermov_codigo_data_idx')]
        verbose_name = 'Movimento de insumo'
        verbose_name_plural = 'Movimentos de insumo'

    def __str__(self):
        return f'{self.codigo_id} {self.data:%d/%m/%Y} {self.quantidade}'


class IndicadorInsumo(models.Model):
    """Indicador de eficiência de um insumo: cruza o consumo do item (códigos do almoxarifado) com a produção lançada
    nos KPIs principais. Ex.: Pad = lentes produzidas × 70% ÷ pads consumidos (lentes por pad); Aloy = gramas
    consumidos ÷ lentes produzidas. Calculado dia a dia, semana a semana e mês a mês (ver kpi.indicadores_insumo)."""
    MODO_RENDIMENTO, MODO_CONSUMO, MODO_USO = 'rendimento', 'consumo', 'uso'
    MODOS = [
        (MODO_RENDIMENTO, 'Rendimento: produção ÷ consumo (ex.: lentes por unidade)'),
        (MODO_CONSUMO, 'Consumo específico: consumo ÷ produção (ex.: gramas por lente)'),
        (MODO_USO, 'Uso: só o consumo no período (ex.: filtros usados na semana)'),
    ]

    nome = models.CharField('Indicador', max_length=150)
    item = models.ForeignKey(HierItem, on_delete=models.CASCADE, related_name='indicadores', verbose_name='Item (insumo)')
    modo = models.CharField('Cálculo', max_length=10, choices=MODOS, default=MODO_RENDIMENTO)
    producao_indicador = models.ForeignKey(
        Indicador, null=True, blank=True, on_delete=models.SET_NULL, related_name='+', verbose_name='Produção: indicador de origem')
    producao_variavel = models.CharField(
        'Produção: variável', max_length=100, blank=True,
        help_text='Variável do indicador de origem (ex.: Lentes produzidas). Vazia = o valor do próprio indicador.')
    producao_setor = models.ForeignKey(
        SetorIndicador, null=True, blank=True, on_delete=models.SET_NULL, related_name='+', verbose_name='Produção: setor do indicador')
    participacao = models.DecimalField(
        'Participação na produção (%)', max_digits=6, decimal_places=2, default=100,
        help_text='Parte da produção atribuída a este insumo. Ex.: Pad 70% e Membrana 30% da produção da surfaçagem.')
    multiplicador = models.DecimalField('Multiplicador do resultado', max_digits=14, decimal_places=4, default=1,
                                        help_text='Ex.: 1000 para exibir por mil lentes.')
    unidade = models.CharField('Métrica', max_length=40, blank=True, help_text='Ex.: lentes/und, g/lente, lentes/galão.')
    casas = models.PositiveSmallIntegerField('Casas decimais', default=2)
    sentido = models.CharField('Sentido da meta', max_length=5, choices=Indicador.SENTIDOS, default=Indicador.SENTIDO_MAIOR)
    meta = models.DecimalField('Meta', max_digits=14, decimal_places=4, null=True, blank=True)
    meta_semanal = models.DecimalField(
        'Meta semanal', max_digits=14, decimal_places=4, null=True, blank=True,
        help_text='Opcional. No cálculo "uso" vale a meta proporcional aos dias se vazia; nos demais vale a meta geral.')
    meta_diaria = models.DecimalField('Meta diária', max_digits=14, decimal_places=4, null=True, blank=True,
                                      help_text='Opcional. Mesma regra da meta semanal.')
    ordem = models.PositiveIntegerField('Ordem', default=0)
    ativo = models.BooleanField('Ativo', default=True)
    criado_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['ordem', 'nome']
        verbose_name = 'Indicador de insumo'
        verbose_name_plural = 'Indicadores de insumo'

    def __str__(self):
        return self.nome

    def atingiu(self, valor, meta):
        if valor is None or meta is None:
            return None
        return valor >= meta if self.sentido == Indicador.SENTIDO_MAIOR else valor <= meta


class DecideImportacao(models.Model):
    """Um envio da planilha semanal do DECIDE (medidor de lentes)."""
    arquivo = models.CharField('Arquivo', max_length=200)
    linhas = models.PositiveIntegerField('Medições', default=0)
    lentes = models.PositiveIntegerField('Lentes', default=0)
    inicio = models.DateField('Primeira medição', null=True, blank=True)
    fim = models.DateField('Última medição', null=True, blank=True)
    criado_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-criado_em', '-pk']
        verbose_name = 'Importação DECIDE'
        verbose_name_plural = 'Importações DECIDE'

    def __str__(self):
        return self.arquivo


class DecideLente(models.Model):
    """Uma medição de uma lente (linha da planilha). `ultima` marca a medição final da lente."""
    importacao = models.ForeignKey(DecideImportacao, on_delete=models.CASCADE, related_name='medicoes')
    track_id = models.CharField('Final TrackID', max_length=60, db_index=True)
    medido_em = models.DateTimeField('Data da medição', db_index=True)
    passagens = models.PositiveSmallIntegerField('Passagens', default=1)
    ultima = models.BooleanField('Medição final', default=False)
    reprovada = models.BooleanField('Reprovada', default=False)
    reprovada_1a = models.BooleanField('Reprovada na 1ª medição', default=False)
    falhas = models.CharField('Parâmetros reprovados', max_length=60, blank=True)
    ilot = models.CharField(max_length=20, blank=True)
    decisao = models.CharField('Decisão do operador', max_length=20, blank=True)
    codigo_op = models.CharField('Código da operação', max_length=20, blank=True)
    marca = models.CharField(max_length=30, blank=True)
    indice = models.CharField('Índice', max_length=20, blank=True)
    diametro = models.CharField('Diâmetro', max_length=20, blank=True)
    olho = models.CharField(max_length=5, blank=True)
    medidor = models.CharField('Operador (INI)', max_length=30, blank=True)

    class Meta:
        ordering = ['-medido_em']
        unique_together = [('track_id', 'medido_em')]
        verbose_name = 'Medição DECIDE'
        verbose_name_plural = 'Medições DECIDE'

    def __str__(self):
        return f'{self.track_id} {self.medido_em:%d/%m/%Y %H:%M}'


class DecideIndicador(models.Model):
    """Indicador de acompanhamento montado no construtor do DECIDE (configuração salva)."""
    nome = models.CharField('Nome', max_length=150)
    descricao = models.CharField('Descrição', max_length=255, blank=True)
    config = models.JSONField('Configuração', default=dict)
    meta = models.DecimalField('Meta', max_digits=14, decimal_places=2, null=True, blank=True)
    criado_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Indicador DECIDE'
        verbose_name_plural = 'Indicadores DECIDE'

    def __str__(self):
        return self.nome
