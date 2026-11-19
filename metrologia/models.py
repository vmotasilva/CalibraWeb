from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date
from decimal import Decimal

# ==============================================================================
# METROLOGIA - CALIBRAÇÃO E INSTRUMENTOS
# ==============================================================================

class CategoriaInstrumento(models.Model):
    TRATATIVA_CHOICES = [
        ('INTERNA', 'Equipe interna'),
        ('EXTERNA', 'Fornecedor externo'),
    ]
    
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    sigla = models.CharField(
        max_length=3, 
        blank=True, 
        null=True,
        help_text="Prefixo padrão para códigos de instrumentos (Ex: TH para termohigrômetros)"
    )
    tratativa_calibracao = models.CharField(
        max_length=20,
        choices=TRATATIVA_CHOICES,
        default='INTERNA',
        help_text="Tipo de calibração padrão para instrumentos desta categoria"
    )
    LOCAL_CALIBRACAO_CHOICES = [
        ('', 'Não definido'),
        ('NA_EMPRESA', 'Somente na empresa (não sai)'),
        ('PODE_SAIR', 'Pode ser enviado ao fornecedor'),
        ('COMPRAR_NOVO', 'Não calibra: renovado por compra'),
    ]
    local_calibracao = models.CharField(
        max_length=12,
        choices=LOCAL_CALIBRACAO_CHOICES,
        blank=True,
        default='',
        verbose_name='Local da calibração',
        help_text='Padrão para os instrumentos da categoria: onde a calibração deve ocorrer'
    )
    frequencia_calibracao_meses = models.IntegerField(
        default=12,
        null=True,
        blank=True,
        verbose_name="Frequência de Calibração (Meses)",
        help_text="Intervalo em meses entre as calibrações para instrumentos desta categoria"
    )
    
    ACAO_CHOICES = [
        ('CALIBRACAO', 'Calibração'),
        ('VERIFICACAO', 'Verificação'),
    ]
    acao = models.CharField(
        max_length=20,
        choices=ACAO_CHOICES,
        default='CALIBRACAO',
        verbose_name="Ação Padrão",
        help_text="Define se os instrumentos desta categoria sofrem Calibração ou Verificação por padrão."
    )


    def __str__(self):
        return self.nome

    class Meta:
        verbose_name_plural = "Categorias de Instrumentos"


class FaixaMedicaoPadraoCategoria(models.Model):
    """
    Faixas padrão de medição para uma categoria de instrumentos.
    Permite que ao criar um novo instrumento, as faixas da categoria sejam sugeridas como base,
    mas possam ser ajustadas sem obrigatoriedade de manter os valores originais.
    """
    categoria = models.ForeignKey(
        CategoriaInstrumento, on_delete=models.CASCADE,
        related_name="faixas_padrao_medicao",
        verbose_name="Categoria",
        help_text="Categoria de instrumento para esta faixa padrão"
    )
    
    unidade = models.ForeignKey('core.UnidadeMedida', on_delete=models.PROTECT)
    
    valor_minimo = models.DecimalField(max_digits=10, decimal_places=4)
    valor_maximo = models.DecimalField(max_digits=10, decimal_places=4)
    resolucao = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True
    )
    nominal = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        help_text="Valor central/nominal do processo"
    )
    tolerancia_mais_menos = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        help_text="Variação aceitável (+/-)"
    )
    
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    ativa = models.BooleanField(default=True, verbose_name="Faixa Ativa")

    def __str__(self):
        return f"{self.categoria.nome} - {self.valor_minimo} a {self.valor_maximo} {self.unidade.nome}"

    class Meta:
        verbose_name = "Faixa de Medição Padrão de Categoria"
        verbose_name_plural = "Faixas de Medição Padrão de Categorias"
        unique_together = [
            ('categoria', 'unidade', 'valor_minimo', 'valor_maximo'),
        ]
        ordering = ['categoria', 'valor_minimo']


class InstrumentoReferencia(models.Model):
    """
    Modelo para rastrear substituição de instrumentos
    Permite manter histórico quando um instrumento é substituído mas o código é reutilizado
    """
    codigo_referencia = models.CharField(
        max_length=50, unique=True, verbose_name="Código de Referência",
        help_text="Código único que permanece mesmo com substituições"
    )
    descricao = models.TextField(verbose_name="Descrição Geral", blank=True, null=True)
    categoria = models.ForeignKey(
        CategoriaInstrumento, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Categoria Padrão"
    )
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Ref: {self.codigo_referencia}"

    class Meta:
        verbose_name = "Instrumento Referência"
        verbose_name_plural = "Instrumentos Referências"


class Instrumento(models.Model):
    # Relação com referência de instrumento
    referencia = models.ForeignKey(
        'InstrumentoReferencia', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="instrumentos_substituidos",
        verbose_name="Referência de Instrumento",
        help_text="Instrumento anterior (em caso de substituição)"
    )
    
    tolerancia_processo = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Tolerância do processo (+/-), associada ao instrumento"
    )
    tag = models.CharField(
        max_length=50, unique=True, verbose_name="TAG / Identificação"
    )
    codigo = models.CharField(
        max_length=50, blank=True, null=True, verbose_name="Código Interno"
    )
    descricao = models.CharField(max_length=200, verbose_name="Descrição")
    fabricante = models.CharField(max_length=100, blank=True, null=True)
    modelo = models.CharField(max_length=100, blank=True, null=True)
    serie = models.CharField(max_length=100, blank=True, null=True)

    categoria = models.ForeignKey(
        CategoriaInstrumento, on_delete=models.SET_NULL, null=True, blank=True
    )

    ativo = models.BooleanField(default=True)
    data_ultima_calibracao = models.DateField(blank=True, null=True)
    data_proxima_calibracao = models.DateField(blank=True, null=True)
    frequencia_meses = models.IntegerField(default=12)

    responsavel = models.ForeignKey(
        'rh.Colaborador', on_delete=models.SET_NULL, null=True, blank=True
    )
    setor = models.ForeignKey(
        'organization.Setor', on_delete=models.SET_NULL, null=True, blank=True
    )
    localizacao = models.CharField(max_length=100, blank=True, null=True)
    
    # Tratativa de Calibração
    TRATATIVA_CHOICES = [
        ('INTERNA', 'Equipe interna'),
        ('EXTERNA', 'Fornecedor externo'),
    ]
    tratativa_calibracao = models.CharField(
        max_length=10,
        choices=TRATATIVA_CHOICES,
        default='INTERNA',
        verbose_name='Responsável pela calibração',
        help_text='Indica se a calibração é feita internamente ou com fornecedor externo'
    )
    LOCAL_CALIBRACAO_CHOICES = [
        ('', 'Não definido'),
        ('NA_EMPRESA', 'Somente na empresa (não sai)'),
        ('PODE_SAIR', 'Pode ser enviado ao fornecedor'),
        ('COMPRAR_NOVO', 'Não calibra: renovado por compra'),
    ]
    local_calibracao = models.CharField(
        max_length=12,
        choices=LOCAL_CALIBRACAO_CHOICES,
        blank=True,
        default='',
        verbose_name='Local da calibração',
        help_text='Onde a calibração deve ocorrer: somente na empresa ou pode ser enviado a fornecedor externo. Vazio = herda da categoria'
    )

    @property
    def local_calibracao_efetivo(self):
        """Local da calibração do instrumento, herdando da categoria; '' = não definido."""
        return self.local_calibracao or (self.categoria.local_calibracao if self.categoria_id else '') or ''
    
    ACAO_CHOICES = [
        ('CALIBRACAO', 'Calibração'),
        ('VERIFICACAO', 'Verificação'),
    ]
    acao = models.CharField(
        max_length=20,
        choices=ACAO_CHOICES,
        default='CALIBRACAO',
        verbose_name="Ação"
    )

    class Meta:
        verbose_name = "Instrumento"
        verbose_name_plural = "Instrumentos"

    def __str__(self):
        return f"{self.tag} - {self.descricao}"


class FaixaMedicao(models.Model):
    instrumento = models.ForeignKey(
        Instrumento,
        on_delete=models.CASCADE,
        related_name="faixas",
        null=True,
        blank=True,
    )
    # Referência para faixa padrão (reutilização)
    faixa_padrao = models.ForeignKey(
        'FaixaMedicaoPadrao', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="faixas_instancia",
        verbose_name="Faixa Padrão",
        help_text="Referência à faixa padrão para reutilização"
    )
    
    unidade = models.ForeignKey('core.UnidadeMedida', on_delete=models.PROTECT)

    valor_minimo = models.DecimalField(max_digits=10, decimal_places=4)
    valor_maximo = models.DecimalField(max_digits=10, decimal_places=4)
    resolucao = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True
    )

    nominal = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Valor central/nominal do processo",
    )
    tolerancia_mais_menos = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Variação aceitável (+/-)",
    )

    def __str__(self):
        return f"{self.valor_minimo} a {self.valor_maximo} {self.unidade.nome}"

    class Meta:
        verbose_name_plural = "Faixas de Medição"
        unique_together = [
            ('instrumento', 'unidade', 'valor_minimo', 'valor_maximo'),
        ]


class FaixaMedicaoPadrao(models.Model):
    """
    Modelo para armazenar faixas padrão de referência
    Permite reutilização de faixas em múltiplos instrumentos e importação em massa
    """
    referencia_instrumento = models.ForeignKey(
        'InstrumentoReferencia', on_delete=models.CASCADE,
        related_name="faixas_padrao",
        verbose_name="Referência de Instrumento",
        help_text="Instrumento de referência para esta faixa padrão"
    )
    
    unidade = models.ForeignKey('core.UnidadeMedida', on_delete=models.PROTECT)
    
    valor_minimo = models.DecimalField(max_digits=10, decimal_places=4)
    valor_maximo = models.DecimalField(max_digits=10, decimal_places=4)
    resolucao = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True
    )
    nominal = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        help_text="Valor central/nominal do processo"
    )
    tolerancia_mais_menos = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        help_text="Variação aceitável (+/-)"
    )
    
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    ativa = models.BooleanField(default=True, verbose_name="Faixa Ativa")

    def __str__(self):
        return f"{self.referencia_instrumento.codigo_referencia} - {self.valor_minimo} a {self.valor_maximo} {self.unidade.nome}"

    class Meta:
        verbose_name = "Faixa de Medição Padrão"
        verbose_name_plural = "Faixas de Medição Padrão"
        unique_together = [
            ('referencia_instrumento', 'unidade', 'valor_minimo', 'valor_maximo'),
        ]
        ordering = ['referencia_instrumento', 'valor_minimo']


class ArquivoPadrao(models.Model):
    """Arquivo de padrão de calibração associado a um histórico específico."""
    historico = models.ForeignKey(
        'HistoricoCalibracao',
        on_delete=models.CASCADE,
        related_name='padroes_arquivo',
        verbose_name='Histórico de Calibração',
        null=True,
        blank=True
    )
    nome = models.CharField(max_length=255)
    descricao = models.TextField(blank=True, null=True)
    arquivo = models.FileField(upload_to='padroes/')
    data_upload = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.historico:
            return f"{self.nome} - {self.historico.instrumento.tag}"
        return self.nome

    class Meta:
        verbose_name = "Arquivo Padrão"
        verbose_name_plural = "Arquivos Padrões"
        ordering = ['-data_upload']


class ResultadoFaixaCalibracao(models.Model):
    RESULTADO_CHOICES = [
        ('APROVADO_SEM_CORRECAO', 'Aprovado sem Correção'),
        ('APROVADO_COM_CORRECAO', 'Aprovado com Correção'),
        ('REPROVADO', 'Reprovado / Restrição'),
    ]
    
    historico = models.ForeignKey(
        'HistoricoCalibracao',
        on_delete=models.CASCADE,
        related_name='resultados_faixa',
    )
    faixa = models.ForeignKey(
        FaixaMedicao, on_delete=models.CASCADE, null=True, blank=True
    )

    valor_maximo = models.DecimalField(max_digits=10, decimal_places=4)
    valor_minimo = models.DecimalField(max_digits=10, decimal_places=4)
    nominal = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    tolerancia = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    # Dados de Calibração
    erro = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    incerteza = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    
    # Campos calculados automaticamente
    ema = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        verbose_name="EMA (Erro Máximo Admissível)",
        help_text="Calculado como 2*Tolerância/4"
    )
    eme = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        verbose_name="EME (Erro Máximo do Equipamento)",
        help_text="Calculado como Erro + Incerteza"
    )
    
    resultado = models.CharField(
        max_length=50,
        choices=RESULTADO_CHOICES,
        default='APROVADO_SEM_CORRECAO',
    )
    
    # Tabela de correção para resultados "APROVADO_COM_CORRECAO"
    tabela_correcao = models.JSONField(
        default=list,
        blank=True,
        null=True,
        verbose_name="Tabela de Correção",
        help_text="Tabela com valores de correção a aplicar nas medições quando resultado é APROVADO_COM_CORRECAO"
    )

    def save(self, *args, **kwargs):
        """Auto-calculate EMA, EME and resultado."""
        # Herdar tolerância da faixa se não definida
        if self.tolerancia is None and self.faixa_id:
            try:
                self.tolerancia = self.faixa.tolerancia_mais_menos
            except Exception:
                pass

        # Calcular EMA = Tolerância * 2 / 4
        if self.tolerancia is not None:
            self.ema = self.tolerancia * 2 / 4
        
        # Calcular EME = |Erro + Incerteza|
        if self.erro is not None and self.incerteza is not None:
            self.eme = abs(self.erro + self.incerteza)
        
        # Calcular resultado baseado em EME vs EMA
        if self.eme is not None and self.ema is not None:
            eme_val = abs(self.eme)
            ema_val = abs(self.ema)
            
            if eme_val > ema_val * 3:
                # EME > EMA*3 → REPROVADO / RESTRIÇÃO
                self.resultado = 'REPROVADO'
            elif eme_val <= ema_val:
                # EME <= EMA → APROVADO SEM CORREÇÃO
                self.resultado = 'APROVADO_SEM_CORRECAO'
            else:
                # EMA < EME <= EMA*3 → APROVADO COM CORREÇÃO
                self.resultado = 'APROVADO_COM_CORRECAO'
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Faixa {self.valor_minimo} a {self.valor_maximo} - {self.resultado}"

    class Meta:
        verbose_name = "Resultado de Faixa"
        verbose_name_plural = "Resultados por Faixa"


class OrdemCalibracao(models.Model):
    LOCAL_CHOICES = [
        ("EXTERNO", "Laboratório Externo"),
        ("IN_LOCO", "Calibração In Loco (Na Empresa)"),
    ]
    STATUS_CALIBRACAO = [
        ("AGENDADO", "Agendado"),
        ("ENVIADO", "Enviado ao Fornecedor"),
        ("EM_CALIBRACAO", "Em Calibração"),
        ("RETORNOU", "Retornou do Fornecedor"),
        ("FINALIZADO", "Finalizado e Aprovado"),
    ]

    instrumento = models.ForeignKey(
        Instrumento,
        on_delete=models.CASCADE,
        related_name="calibracoes",
        null=True,
        blank=True,
    )
    fornecedor = models.CharField(
        max_length=100, help_text="Nome do Laboratório/Empresa"
    )
    tipo_local = models.CharField(
        max_length=20, choices=LOCAL_CHOICES, default="EXTERNO"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CALIBRACAO, default="AGENDADO"
    )

    data_prevista = models.DateField()
    data_envio = models.DateField(
        null=True, blank=True, help_text="Data de saída da empresa"
    )
    data_retorno = models.DateField(
        null=True, blank=True, help_text="Data de chegada na empresa"
    )

    observacoes = models.TextField(blank=True, null=True)
    certificado_arquivo = models.FileField(
        upload_to="certificados/", null=True, blank=True
    )

    def __str__(self):
        return f"Calibração {self.instrumento.codigo if self.instrumento else ''} - {self.status}"

    @property
    def esta_fora(self):
        return self.tipo_local == "EXTERNO" and self.status == "ENVIADO"


class HistoricoCalibracao(models.Model):
    instrumento = models.ForeignKey(
        Instrumento,
        on_delete=models.CASCADE,
        related_name="historicos",
        verbose_name="Instrumento",
        null=True,
        blank=True,
    )
    # NEW: Linkagem com cotação (quando calibração é feita via fornecedor da solicitação)
    atendimento = models.ForeignKey(
        'AtendimentoSolicitacao',
        on_delete=models.SET_NULL,
        related_name='historicos_calibracao',
        verbose_name='Atendimento da Solicitação',
        null=True,
        blank=True,
        help_text='Atendimento da cotação que originou esta calibração'
    )
    
    # Origem: item da cotação de fornecedor cujo serviço foi concluído
    item_cotacao = models.ForeignKey(
        'ItemCotacao',
        on_delete=models.SET_NULL,
        related_name='historicos_gerados',
        verbose_name='Item da Cotação de origem',
        null=True,
        blank=True,
    )
    # Calibração gerada na conclusão do serviço, ainda sem os dados do certificado.
    # Limpo automaticamente quando número e arquivo/link do certificado são informados.
    aguardando_certificado = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Aguardando dados do certificado',
    )

    data_calibracao = models.DateField()
    data_aprovacao = models.DateField(default=date.today)
    numero_certificado = models.CharField(max_length=100, default="S/N")
    tem_selo_rbc = models.BooleanField(default=False, verbose_name="Possui Selo RBC?")
    
    TIPO_CALIBRACAO_CHOICES = [
        ("EXTERNA", "Externa (Fornecedor)"),
        ("INTERNA", "Interna (Equipe Própria)"),
    ]
    tipo_calibracao = models.CharField(
        max_length=20,
        choices=TIPO_CALIBRACAO_CHOICES,
        default="EXTERNA",
        verbose_name="Tipo",
    )
    responsavel = models.CharField(
        max_length=150, null=True, blank=True, verbose_name="Responsável Técnica"
    )
    fornecedor = models.CharField(
        max_length=150, null=True, blank=True, verbose_name="Laboratório/Fornecedor"
    )
    erro_encontrado = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True, verbose_name="Erro (E)"
    )
    incerteza = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Incerteza (U)",
    )
    tolerancia_usada = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Tol. Processo (+/-)",
    )
    proxima_calibracao = models.DateField(null=True, blank=True)
    certificado = models.FileField(upload_to="certificados/", null=True, blank=True)
    link_certificado = models.URLField(max_length=500, null=True, blank=True, verbose_name="Link Externo do Certificado")
    certificado_validado = models.BooleanField(default=False)
    certificado_carimbado = models.FileField(upload_to="certificados/carimbados/", null=True, blank=True)
    
    RESULTADO_CHOICES = [
        ("APROVADO_SEM_CORRECAO", "Aprovado sem correção"),
        ("APROVADO_COM_CORRECAO", "Aprovado com Correção"),
        ("REPROVADO", "Reprovado"),
    ]
    resultado = models.CharField(
        max_length=50, choices=RESULTADO_CHOICES, default="APROVADO_SEM_CORRECAO"
    )
    observacoes = models.TextField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    @property
    def certificado_preenchido(self):
        """Certificado recebido = número real informado (arquivo/link são opcionais)."""
        numero = (self.numero_certificado or '').strip().upper()
        return bool(numero) and numero != 'S/N'

    def save(self, *args, **kwargs):
        if self.aguardando_certificado and self.certificado_preenchido:
            self.aguardando_certificado = False

        # Auto-calculate resultado based on error vs tolerance
        if self.erro_encontrado is not None and self.tolerancia_usada is not None:
            if abs(self.erro_encontrado) <= self.tolerancia_usada:
                self.resultado = "APROVADO_SEM_CORRECAO"
            else:
                self.resultado = "REPROVADO"
        
        # Auto-calculate próxima_calibracao if not provided or based on frequency
        if not self.proxima_calibracao and self.data_calibracao:
            from dateutil.relativedelta import relativedelta
            from django.utils.dateparse import parse_date
            data_cal = self.data_calibracao
            if isinstance(data_cal, str):
                data_cal = parse_date(data_cal)
            
            frequencia = 12
            if self.instrumento and self.instrumento.frequencia_meses:
                frequencia = self.instrumento.frequencia_meses
            elif self.instrumento and self.instrumento.categoria and self.instrumento.categoria.frequencia_calibracao_meses:
                frequencia = self.instrumento.categoria.frequencia_calibracao_meses
                
            if data_cal:
                self.proxima_calibracao = data_cal + relativedelta(months=frequencia)
        
        super().save(*args, **kwargs)

        # Atualizar automaticamente data_ultima_calibracao e data_proxima_calibracao no Instrumento
        if self.instrumento_id:
            try:
                Instrumento.objects.filter(id=self.instrumento_id).update(
                    data_ultima_calibracao=self.data_calibracao,
                    data_proxima_calibracao=self.proxima_calibracao
                )
            except Exception:
                pass

    def __str__(self):
        return f"{self.instrumento} - {self.data_calibracao}"

    class Meta:
        verbose_name = "Histórico Calibração"
        verbose_name_plural = "Históricos de Calibração"
        ordering = ["-data_calibracao"]


# ==============================================================================
# COTAÇÃO DE CALIBRAÇÃO
# ==============================================================================

class Cotacao(models.Model):
    """
    Solicitação de orçamento para calibração de instrumentos
    """
    STATUS_CHOICES = [
        ('CRIADA', 'Criada'),
        ('ENVIADA', 'Enviada para Fornecedor'),
        ('PROPOSTA_RECEBIDA', 'Proposta Recebida'),
        ('APROVADA', 'Aprovada'),
        ('REPROVADA', 'Reprovada'),
        ('CANCELADA', 'Cancelada'),
    ]

    fornecedor = models.ForeignKey(
        'fornecedores.Fornecedor',
        on_delete=models.PROTECT,
        related_name='cotacoes',
        verbose_name='Fornecedor'
    )
    instrumentos = models.ManyToManyField(
        'Instrumento',
        related_name='cotacoes',
        verbose_name='Instrumentos',
        help_text='Selecione um ou mais instrumentos para calibração'
    )
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')
    data_envio = models.DateTimeField(null=True, blank=True, verbose_name='Data de Envio')
    data_proposta = models.DateTimeField(null=True, blank=True, verbose_name='Data Recebimento Proposta')
    data_decisao = models.DateTimeField(null=True, blank=True, verbose_name='Data Aprovação/Reprovação')
    
    valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Valor Orçado (R$)'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='CRIADA',
        verbose_name='Status'
    )
    observacoes = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observações'
    )
    
    # Rastreamento
    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cotacoes_criadas',
        verbose_name='Criado por'
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cotação #{self.id} - {self.fornecedor.empresa} - {self.get_status_display()}"

    class Meta:
        verbose_name = "Cotação"
        verbose_name_plural = "Cotações"
        ordering = ["-data_criacao"]


class OcorrenciaCotacao(models.Model):
    """
    Rastreamento de ocorrências/eventos na cotação
    Mapeia situações externas ao fluxo estabelecido
    """
    TIPO_CHOICES = [
        ('ATRASO', 'Atraso no Envio'),
        ('FALTA_RESPOSTA', 'Falta de Resposta'),
        ('VALOR_ALTO', 'Valor Orçado Alto'),
        ('VALOR_BAIXO', 'Valor Orçado Baixo'),
        ('PRAZO', 'Prazo de Entrega'),
        ('QUALIDADE', 'Dúvida sobre Qualidade'),
        ('COMUNICACAO', 'Problemas de Comunicação'),
        ('DOCUMENTACAO', 'Falta de Documentação'),
        ('RECURSO', 'Recurso/Reclamação'),
        ('OUTRO', 'Outro'),
    ]

    cotacao = models.ForeignKey(
        Cotacao,
        on_delete=models.CASCADE,
        related_name='ocorrencias',
        verbose_name='Cotação'
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        verbose_name='Tipo de Ocorrência'
    )
    data = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data da Ocorrência'
    )
    descricao = models.TextField(
        verbose_name='Descrição',
        help_text='Detalhe sobre a ocorrência'
    )
    acao_tomada = models.TextField(
        blank=True,
        null=True,
        verbose_name='Ação Tomada',
        help_text='Qual ação foi tomada em resposta'
    )
    responsavel = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Responsável pelo Registro'
    )
    resolvida = models.BooleanField(
        default=False,
        verbose_name='Ocorrência Resolvida'
    )
    data_resolucao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Data de Resolução'
    )

    def __str__(self):
        return f"{self.get_tipo_display()} - Cotação #{self.cotacao.id}"

    class Meta:
        verbose_name = "Ocorrência de Cotação"
        verbose_name_plural = "Ocorrências de Cotação"
        ordering = ["-data"]

# ==============================================================================
# NOVO FLUXO DE COTAÇÕES - ETAPAS 1-4
# ==============================================================================

class SolicitacaoCotacao(models.Model):
    def reabrir(self):
        if self.status == 'CONCLUIDA':
            # Volta ao status automático conforme progresso
            self.status = 'ABERTA'  # fallback
            self.atualizar_status_automatico()
            self.save(update_fields=['status'])

    def reativar(self):
        if self.status == 'CANCELADA':
            self.status = 'ABERTA'
            self.save(update_fields=['status'])
    """
    ETAPA 1: Solicitação de Cotação - Define necessidades e período de vencimento
    Agrupa múltiplos instrumentos que precisam de serviço em um mesmo período
    """
    STATUS_CHOICES = [
        ('ABERTA', 'Aberta'),
        ('INSTRUMENTOS_SELECIONADOS', 'Instrumentos Selecionados'),
        ('COM_COMPRAS', 'Com o Setor de Compras'),
        ('COTACAO_SOLICITADA', 'Cotação Solicitada'),
        ('AGUARDANDO_PLANEJAMENTO', 'Aguardando Planejamento'),
        ('PARCIALMENTE_PLANEJADA', 'Parcialmente Planejada'),
        ('PLANEJADA', 'Planejada'),
        ('PARCIALMENTE_REALIZADO', 'Parcialmente Realizado'),
        ('REALIZADO', 'Realizado'),
        ('CONCLUIDA', 'Concluída'),
        ('CANCELADA', 'Cancelada'),
    ]

    def atualizar_status_automatico(self):
        """
        Atualiza o status da solicitação conforme o progresso dos itens, cotações e atendimentos.
        Ordem de verificação (do final para o início do workflow):
        1. REALIZADO / PARCIALMENTE_REALIZADO (execução completa)
        2. PLANEJADA (planejamento completo)
        3. PARCIALMENTE_PLANEJADA (planejamento parcial)
        4. AGUARDANDO_PLANEJAMENTO (cotações aprovadas, sem planejamento)
        5. COTACAO_SOLICITADA (cotações respondidas)
        5b. COM_COMPRAS (demanda solicitada ao setor de compras, etapa ainda ativa)
        6. INSTRUMENTOS_SELECIONADOS (itens sem cotações)
        7. ABERTA (sem itens)
        """
        novo_status = self.status

        # A etapa de compras se encerra em conjunto com as cotações: ao chegar a primeira
        # proposta (respondida/aceita) ela é encerrada automaticamente.
        if self.compras_ativa and self.cotacoes_fornecedores.filter(
                ativa=True, status__in=['RESPONDIDA', 'ACEITA']).exists():
            hoje = timezone.localdate()
            type(self).objects.filter(pk=self.pk).update(compras_concluida_em=hoje)
            self.compras_concluida_em = hoje

        # Atendimentos desconsiderados (com justificativa) não entram no cálculo
        atendimentos_ativos = self.atendimentos.filter(desconsiderado=False)
        atendimentos_total = atendimentos_ativos.count()

        if atendimentos_total == 0 and self.atendimentos.exists():
            # Todos os instrumentos foram desconsiderados: mantém o status atual
            return novo_status

        if atendimentos_total > 0:
            # Contar atendimentos completos conforme o tipo de local
            atendimentos_completos = 0
            for atendimento in atendimentos_ativos:
                local = atendimento.item_cotacao.local_atendimento
                
                if local == 'NO_LOCAL' and atendimento.data_realizada:
                    atendimentos_completos += 1
                elif local == 'NO_LABORATORIO' and atendimento.data_retorno:
                    atendimentos_completos += 1
                elif local == 'COMPRAR_NOVO' and atendimento.data_chegada:
                    atendimentos_completos += 1
            
            # Determinar status baseado na execução
            if atendimentos_completos == atendimentos_total:
                novo_status = 'REALIZADO'
            elif atendimentos_completos > 0:
                novo_status = 'PARCIALMENTE_REALIZADO'
            # Se nenhum está completo, continua verificando planejamento
            elif atendimentos_total > 0:
                # Verificar planejamento
                atendimentos_planejados = atendimentos_ativos.filter(data_prevista_atendimento__isnull=False).count()
                
                if atendimentos_planejados == atendimentos_total:
                    novo_status = 'PLANEJADA'
                elif atendimentos_planejados > 0:
                    novo_status = 'PARCIALMENTE_PLANEJADA'
                else:
                    # Sem planejamento, mas com atendimentos selecionados
                    novo_status = 'AGUARDANDO_PLANEJAMENTO'
        else:
            # Sem atendimentos, verificar cotações
            if self.itens.count() == 0:
                novo_status = 'ABERTA'
            elif self.compras_ativa:
                novo_status = 'COM_COMPRAS'
            elif self.cotacoes_fornecedores.filter(ativa=True).count() == 0:
                novo_status = 'INSTRUMENTOS_SELECIONADOS'
            elif self.cotacoes_fornecedores.filter(ativa=True, status='RESPONDIDA').exists():
                novo_status = 'COTACAO_SOLICITADA'
            elif self.cotacoes_fornecedores.filter(ativa=True, status='ACEITA').exists():
                novo_status = 'AGUARDANDO_PLANEJAMENTO'
            else:
                # Manter status atual como fallback (saindo de COM_COMPRAS quando a etapa encerra)
                novo_status = 'INSTRUMENTOS_SELECIONADOS' if self.status == 'COM_COMPRAS' else self.status
        
        # Atualizar se houver mudança (não alterar CONCLUIDA ou CANCELADA)
        if novo_status != self.status and self.status not in ['CONCLUIDA', 'CANCELADA']:
            type(self).objects.filter(pk=self.pk).update(status=novo_status)
            self.status = novo_status

    def pendencias_conclusao(self):
        """Motivos que impedem concluir a cotação (lista vazia = pode concluir).

        Só se considera concluída quando todas as etapas foram realizadas e os
        certificados dos instrumentos foram recebidos:
          - calibração aprovada sem registro de calibração realizada;
          - atendimento (qualquer tipo) ainda sem a data de realização/retorno/chegada;
          - registro de calibração ainda aguardando os dados do certificado.
        Instrumentos desconsiderados (com justificativa) ou não atendidos ficam de fora.
        """
        pendencias = []
        desconsiderados = set(
            self.atendimentos.filter(desconsiderado=True).values_list('item_cotacao_id', flat=True))

        itens = ItemCotacao.objects.filter(
            cotacao_fornecedor__solicitacao=self, cotacao_fornecedor__aprovada=True, pode_atender=True,
            cotacao_fornecedor__ativa=True,
        ).exclude(cotacao_fornecedor__status__in=('CANCELADA', 'REJEITADA')).exclude(
            status_execucao='NAO_ATENDIDO').select_related('instrumento', 'cotacao_fornecedor')
        for item in itens:
            if item.id in desconsiderados:
                continue
            tag = item.instrumento.tag
            if item.tipo_servico == 'CALIBRACAO' and not (
                    item.historicos_gerados.exists()
                    or HistoricoCalibracao.objects.filter(atendimento__item_cotacao=item).exists()):
                pendencias.append(f'{tag}: calibração ainda não realizada')

        for a in self.atendimentos.filter(desconsiderado=False).select_related('item_cotacao__instrumento'):
            local = a.item_cotacao.local_atendimento
            feito = (a.data_realizada if local == 'NO_LOCAL' else
                     a.data_retorno if local == 'NO_LABORATORIO' else
                     a.data_chegada if local == 'COMPRAR_NOVO' else True)
            msg = f'{a.item_cotacao.instrumento.tag}: atendimento sem data de realização'
            if not feito and msg not in pendencias and \
                    f'{a.item_cotacao.instrumento.tag}: calibração ainda não realizada' not in pendencias:
                pendencias.append(msg)

        for h in HistoricoCalibracao.objects.filter(
                aguardando_certificado=True, item_cotacao__cotacao_fornecedor__solicitacao=self
        ).select_related('instrumento'):
            pendencias.append(f'{h.instrumento.tag}: certificado de calibração não recebido')
        return pendencias

    def marcar_concluida(self):
        self.status = 'CONCLUIDA'
        self.save(update_fields=['status'])

    def marcar_cancelada(self):
        self.status = 'CANCELADA'
        self.save(update_fields=['status'])
    
    PRIORIDADE_CHOICES = [
        ('BAIXA', 'Baixa'),
        ('MEDIA', 'Média'),
        ('ALTA', 'Alta'),
        ('CRITICA', 'Crítica'),
    ]
    
    # Identificação
    numero = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='Número da Solicitação',
        help_text='Auto-gerado: SOL-YYYY-####'
    )
    
    # Dados principais
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Criação'
    )
    data_solicitacao_orcamento = models.DateField(
        verbose_name='Data de Solicitação de Orçamento',
        help_text='Data em que o orçamento foi solicitado',
        null=True,
        blank=True
    )
    responsavel = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitacoes_cotacao_criadas',
        verbose_name='Responsável'
    )
    departamento = models.ForeignKey(
        'organization.Setor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Departamento / Setor'
    )
    
    # Período de vencimento
    dias_vencimento = models.PositiveIntegerField(
        default=30,
        verbose_name='Dias no Futuro',
        help_text='Quantos dias no futuro buscar instrumentos vencidos ou vencendo'
    )
    
    # Status e Controle
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default='ABERTA',
        verbose_name='Status'
    )

    # Etapa "Solicitação das cotações ao setor de compras": começa antes das cotações
    # e se encerra em conjunto com elas (ao chegar a primeira proposta) ou manualmente.
    compras_solicitada_em = models.DateField(
        null=True, blank=True, verbose_name='Solicitada ao setor de compras em')
    compras_solicitada_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='solicitacoes_enviadas_compras', verbose_name='Solicitada por')
    compras_responsavel = models.CharField(
        max_length=150, blank=True, default='', verbose_name='Responsável em Compras')
    compras_observacoes = models.TextField(
        blank=True, default='', verbose_name='Observações para Compras')
    compras_concluida_em = models.DateField(
        null=True, blank=True, verbose_name='Etapa de compras encerrada em')

    @property
    def compras_ativa(self):
        """A demanda está com o setor de compras (solicitada e ainda não encerrada)."""
        return bool(self.compras_solicitada_em) and not self.compras_concluida_em

    @property
    def compras_dias(self):
        """Dias da etapa de compras (até o encerramento, ou até hoje se ainda ativa)."""
        if not self.compras_solicitada_em:
            return None
        fim = self.compras_concluida_em or timezone.localdate()
        return max((fim - self.compras_solicitada_em).days, 0)
    
    # Rastreamento
    atualizado_em = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        # Gera numero automaticamente se não existir
        if not self.numero:
            from datetime import datetime
            year = datetime.now().year
            count = SolicitacaoCotacao.objects.filter(
                numero__startswith=f"SOL-{year}-"
            ).count() + 1
            self.numero = f"SOL-{year}-{count:04d}"
        super().save(*args, **kwargs)
        # Atualiza status automaticamente, exceto se for concluída ou cancelada
        if self.status not in ['CONCLUIDA', 'CANCELADA']:
            self.atualizar_status_automatico()
    
    def __str__(self):
        return f"{self.numero} - {self.get_status_display()}"
    
    class Meta:
        verbose_name = "Solicitação de Cotação"
        verbose_name_plural = "Solicitações de Cotação"
        ordering = ["-data_criacao"]


class LinkSolicitacaoCompras(models.Model):
    """Links das tratativas com o setor de compras (feitas muitas vezes em outras plataformas)."""
    solicitacao = models.ForeignKey(
        SolicitacaoCotacao, on_delete=models.CASCADE, related_name='links_compras',
        verbose_name='Solicitação')
    url = models.URLField(max_length=500, verbose_name='Link')
    descricao = models.CharField(max_length=150, blank=True, default='', verbose_name='Descrição')
    criado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='links_compras_criados', verbose_name='Adicionado por')
    criado_em = models.DateTimeField(auto_now_add=True)

    @property
    def rotulo(self):
        """Descrição informada ou, na falta dela, o domínio do link."""
        if self.descricao:
            return self.descricao
        from urllib.parse import urlparse
        return urlparse(self.url).netloc or self.url

    def __str__(self):
        return f"{self.solicitacao.numero} - {self.rotulo}"

    class Meta:
        verbose_name = "Link da Etapa de Compras"
        verbose_name_plural = "Links da Etapa de Compras"
        ordering = ['criado_em', 'id']


class ItemSolicitacaoCotacao(models.Model):
    """
    ETAPA 1: Itens da Solicitação - Cada instrumento que será cotado
    """
    solicitacao = models.ForeignKey(
        SolicitacaoCotacao,
        on_delete=models.CASCADE,
        related_name='itens',
        verbose_name='Solicitação'
    )
    instrumento = models.ForeignKey(
        Instrumento,
        on_delete=models.PROTECT,
        related_name='solicitacoes_itens',
        verbose_name='Instrumento'
    )
    
    # Pontos de Calibração
    TIPO_PONTOS_CHOICES = [
        ('3', '3 Pontos'),
        ('6', '6 Pontos'),
        ('9', '9 Pontos'),
    ]
    
    tipo_pontos = models.CharField(
        max_length=1,
        choices=TIPO_PONTOS_CHOICES,
        default='3',
        verbose_name='Tipo de Pontos de Calibração'
    )
    
    # Faixas de medição para cada tipo de ponto
    # Para 3 pontos
    faixa_min = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name='Faixa Mínima'
    )
    faixa_centro = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name='Faixa Centro'
    )
    faixa_max = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name='Faixa Máxima'
    )
    
    # Unidade de medida dos pontos
    unidade_pontos = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='Unidade dos Pontos'
    )
    
    # Notas
    notas = models.TextField(
        blank=True,
        null=True,
        verbose_name='Notas Adicionais'
    )
    
    # Rastreamento
    data_criacao = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.solicitacao.numero} - {self.instrumento.tag}"
    
    class Meta:
        verbose_name = "Item da Solicitação de Cotação"
        verbose_name_plural = "Itens da Solicitação de Cotação"
        unique_together = ('solicitacao', 'instrumento')
        ordering = ['instrumento__tag']


class ItemSolicitacaoFaixa(models.Model):
    """
    Faixas selecionadas para calibração de um item da solicitação
    Permite múltiplas faixas com diferentes unidades de medida para um mesmo instrumento
    """
    item_solicitacao = models.ForeignKey(
        ItemSolicitacaoCotacao,
        on_delete=models.CASCADE,
        related_name='faixas_selecionadas',
        verbose_name='Item da Solicitação'
    )
    faixa_medicao = models.ForeignKey(
        FaixaMedicao,
        on_delete=models.CASCADE,
        related_name='items_solicitacao',
        verbose_name='Faixa de Medição'
    )
    
    # Permite sobrescrita manual se necessário
    valor_minimo = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name='Valor Mínimo (Override)'
    )
    valor_maximo = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name='Valor Máximo (Override)'
    )
    
    # Número de pontos de calibração para esta faixa
    numero_pontos = models.IntegerField(
        default=3,
        choices=[(3, '3 Pontos'), (5, '5 Pontos'), (7, '7 Pontos')],
        verbose_name='Número de Pontos de Calibração'
    )
    
    # Pontos de calibração (até 7)
    ponto_1 = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name='Ponto 1'
    )
    ponto_2 = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name='Ponto 2'
    )
    ponto_3 = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name='Ponto 3'
    )
    ponto_4 = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name='Ponto 4'
    )
    ponto_5 = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name='Ponto 5'
    )
    ponto_6 = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name='Ponto 6'
    )
    ponto_7 = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name='Ponto 7'
    )
    
    data_criacao = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.item_solicitacao} - {self.faixa_medicao}"
    
    def get_pontos(self):
        """Retorna uma lista com os pontos preenchidos"""
        pontos = []
        for i in range(1, self.numero_pontos + 1):
            valor = getattr(self, f'ponto_{i}', None)
            if valor:
                pontos.append(valor)
        return pontos
    
    class Meta:
        verbose_name = "Faixa de Item de Solicitação"
        verbose_name_plural = "Faixas de Itens de Solicitação"
        unique_together = ('item_solicitacao', 'faixa_medicao')
        ordering = ['faixa_medicao__valor_minimo']


class CotacaoFornecedor(models.Model):
    """
    ETAPA 2: Cotação do Fornecedor - Proposta de um fornecedor para atender solicitação
    """
    STATUS_CHOICES = [
        ('RASCUNHO', 'Rascunho'),
        ('ENVIADA', 'Enviada para Fornecedor'),
        ('RESPONDIDA', 'Proposta Respondida'),
        ('ACEITA', 'Aceita'),
        ('REJEITADA', 'Rejeitada'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    # Ligação com a necessidade
    solicitacao = models.ForeignKey(
        SolicitacaoCotacao,
        on_delete=models.CASCADE,
        related_name='cotacoes_fornecedores',
        verbose_name='Solicitação'
    )
    fornecedor = models.ForeignKey(
        'fornecedores.Fornecedor',
        on_delete=models.PROTECT,
        related_name='cotacoes_novo_fluxo',
        verbose_name='Fornecedor'
    )
    
    # Identificação
    numero = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='Número da Cotação',
        help_text='Auto-gerado: COT-YYYY-####-FOR###'
    )
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Criação'
    )
    data_solicitacao = models.DateField(
        null=True,
        blank=True,
        verbose_name='Data de Solicitação'
    )
    data_retorno_fornecedor = models.DateField(
        null=True,
        blank=True,
        verbose_name='Data de Retorno do Fornecedor'
    )
    data_envio_para_fornecedor = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Data de Envio para Fornecedor'
    )
    data_proposta_recebida = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Data de Recebimento da Proposta'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='RASCUNHO',
        verbose_name='Status'
    )
    
    # Aprovação interna para planejamento
    aprovada = models.BooleanField(
        default=False,
        verbose_name='Cotação Aprovada'
    )
    data_aprovacao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Data de Aprovação'
    )
    aprovado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cotacoes_fornecedor_aprovadas',
        verbose_name='Aprovado por'
    )
    
    # Observações gerais
    observacoes = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observações Gerais da Cotação'
    )
    
    # Observações de execução/entrega
    observacoes_execucao = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observações de Execução/Entrega'
    )

    # ------------------------------------------------------------------
    # Ciclo de execução do serviço (após cotação aceita)
    # AGENDAMENTO (planejamento) -> EXECUCAO -> CONCLUIDO
    # ------------------------------------------------------------------
    ETAPA_SERVICO_CHOICES = [
        ('AGENDAMENTO', 'Planejamento'),
        ('EXECUCAO', 'Execução'),
        ('CONCLUIDO', 'Concluído'),
    ]
    etapa_servico = models.CharField(
        max_length=15,
        choices=ETAPA_SERVICO_CHOICES,
        default='AGENDAMENTO',
        verbose_name='Etapa do Serviço'
    )
    # 1. Planejamento
    data_visita = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Data e Hora da Visita'
    )
    # 2. Execução
    data_inicio_execucao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Início da Execução'
    )
    # 3. Conclusão
    data_conclusao_servico = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Data de Conclusão do Serviço'
    )
    relatorio_conclusao = models.TextField(
        blank=True,
        default='',
        verbose_name='Relatório de Conclusão'
    )
    observacoes_conclusao = models.TextField(
        blank=True,
        default='',
        verbose_name='Observações da Conclusão'
    )
    concluido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cotacoes_fornecedor_concluidas',
        verbose_name='Concluído por'
    )
    
    # Cotação obsoleta: inativada para dar lugar a uma nova versão com valores atualizados
    ativa = models.BooleanField(default=True, db_index=True, verbose_name='Cotação ativa')
    inativada_em = models.DateTimeField(null=True, blank=True, verbose_name='Inativada em')
    inativada_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cotacoes_fornecedor_inativadas', verbose_name='Inativada por')
    motivo_inativacao = models.CharField(max_length=255, blank=True, default='', verbose_name='Motivo da inativação')
    versao_anterior = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='versoes_novas', verbose_name='Versão anterior (obsoleta)')

    # Rastreamento
    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cotacoes_fornecedor_criadas',
        verbose_name='Criado por'
    )
    atualizado_em = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.numero} - {self.fornecedor.empresa}"
    
    def _gerar_numero(self):
        """COT-AAAA-SSSS-FORFFF (20 caracteres): ano, sequência do ano e id do fornecedor."""
        ano = (self.data_criacao or timezone.now()).year
        sufixo = f"FOR{self.fornecedor_id % 1000:03d}"
        sequencia = type(self).objects.filter(numero__startswith=f"COT-{ano}-").count() + 1
        while True:
            numero = f"COT-{ano}-{sequencia:04d}-{sufixo}"
            if not type(self).objects.filter(numero=numero).exists():
                return numero
            sequencia += 1

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._gerar_numero()
        super().save(*args, **kwargs)
        # proposta respondida/aceita encerra a etapa de compras e atualiza o status da solicitação
        if self.solicitacao_id and self.solicitacao.status not in ('CONCLUIDA', 'CANCELADA'):
            self.solicitacao.atualizar_status_automatico()

    def atendimentos_vinculados(self, incluir_desconsiderados=False):
        """Atendimentos (planejamento) ligados a itens desta cotação (por padrão, sem os desconsiderados)."""
        qs = AtendimentoSolicitacao.objects.filter(item_cotacao__cotacao_fornecedor=self)
        return qs if incluir_desconsiderados else qs.filter(desconsiderado=False)

    def get_valor_servicos(self):
        """Soma dos serviços (instrumentos) cotados, sem os custos adicionais."""
        return sum((item.valor_total for item in self.itens.all()), Decimal('0.00'))

    def get_valor_custos_adicionais(self):
        """Soma dos custos adicionais (deslocamento, passagens aéreas etc.)."""
        return sum((c.valor_total for c in self.custos_adicionais.all()), Decimal('0.00'))

    def get_valor_total(self):
        """Valor total da cotação: serviços + custos adicionais."""
        return self.get_valor_servicos() + self.get_valor_custos_adicionais()

    def get_valor_a_pagar(self):
        """
        Valor efetivamente devido ao fornecedor.
        - Sem execução registrada: vale o valor cotado.
        - Com execução: soma apenas o que foi atendido, pelo valor praticado.
        Os custos adicionais (deslocamentos, passagens...) entram nos dois casos.
        """
        itens = list(self.itens.all())
        adicionais = self.get_valor_custos_adicionais()
        if not any(i.status_execucao != 'PENDENTE' for i in itens):
            return sum((i.valor_total for i in itens), Decimal('0.00')) + adicionais
        return sum((i.valor_cobrado for i in itens), Decimal('0.00')) + adicionais
    
    class Meta:
        verbose_name = "Cotação do Fornecedor"
        verbose_name_plural = "Cotações de Fornecedores"
        ordering = ["-data_criacao"]
        # um fornecedor pode ter várias versões na solicitação, mas só uma ativa
        constraints = [
            models.UniqueConstraint(
                fields=['solicitacao', 'fornecedor'], condition=models.Q(ativa=True),
                name='uniq_cotacao_ativa_por_fornecedor'),
        ]


class CustoAdicionalCotacao(models.Model):
    """Custos além do serviço cotado: deslocamento, passagens aéreas, hospedagem etc."""
    TIPO_CHOICES = [
        ('DESLOCAMENTO', 'Deslocamento'),
        ('PASSAGEM_AEREA', 'Passagem aérea'),
        ('HOSPEDAGEM', 'Hospedagem'),
        ('ALIMENTACAO', 'Alimentação'),
        ('FRETE', 'Frete / transporte do instrumento'),
        ('TAXA', 'Taxa / impostos'),
        ('OUTRO', 'Outro'),
    ]

    cotacao_fornecedor = models.ForeignKey(
        'CotacaoFornecedor', on_delete=models.CASCADE, related_name='custos_adicionais',
        verbose_name='Cotação do Fornecedor')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='OUTRO', verbose_name='Tipo')
    descricao = models.CharField(max_length=150, blank=True, default='', verbose_name='Descrição')
    quantidade = models.PositiveIntegerField(default=1, verbose_name='Quantidade')
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Valor unitário (R$)')
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Valor total (R$)')

    def save(self, *args, **kwargs):
        self.valor_total = self.valor_unitario * self.quantidade
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cotacao_fornecedor.numero} - {self.get_tipo_display()} ({self.valor_total})"

    class Meta:
        verbose_name = "Custo Adicional da Cotação"
        verbose_name_plural = "Custos Adicionais da Cotação"
        ordering = ['id']


class ItemCotacao(models.Model):
    """
    ETAPA 2: Item da Cotação - Detalhe de cada instrumento/serviço na cotação do fornecedor
    """
    TIPO_SERVICO_CHOICES = [
        ('CALIBRACAO', 'Calibração de Instrumento Existente'),
        ('AQUISICAO', 'Aquisição de Instrumento Novo'),
    ]
    
    LOCAL_ATENDIMENTO_CHOICES = [
        ('NO_LOCAL', 'No local (Cliente)'),
        ('NO_LABORATORIO', 'No Laboratório (Fornecedor)'),
        ('COMPRAR_NOVO', 'Comprar Novo'),
    ]
    
    cotacao_fornecedor = models.ForeignKey(
        CotacaoFornecedor,
        on_delete=models.CASCADE,
        related_name='itens',
        verbose_name='Cotação do Fornecedor'
    )
    item_solicitacao = models.ForeignKey(
        ItemSolicitacaoCotacao,
        on_delete=models.PROTECT,
        related_name='cotacoes_itens',
        verbose_name='Item da Solicitação'
    )
    instrumento = models.ForeignKey(
        Instrumento,
        on_delete=models.PROTECT,
        related_name='cotacoes_itens',
        verbose_name='Instrumento'
    )
    
    # O fornecedor consegue atender?
    pode_atender = models.BooleanField(
        default=False,
        verbose_name='Pode Atender esta Necessidade?'
    )
    
    # Tipo de serviço (importante para automatizações)
    tipo_servico = models.CharField(
        max_length=20,
        choices=TIPO_SERVICO_CHOICES,
        default='CALIBRACAO',
        verbose_name='Tipo de Serviço'
    )
    
    # Tipo de atendimento
    local_atendimento = models.CharField(
        max_length=20,
        choices=LOCAL_ATENDIMENTO_CHOICES,
        null=True,
        blank=True,
        verbose_name='Tipo de Atendimento'
    )
    
    # Valores
    valor_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Valor Unitário (R$)'
    )
    quantidade = models.IntegerField(
        default=1,
        verbose_name='Quantidade'
    )
    valor_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Valor Total (R$)',
        help_text='Calculado automaticamente: valor_unitário × quantidade'
    )
    
    # Prazo
    prazo_dias = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Prazo (dias)',
        help_text='Quantos dias para executar o serviço?'
    )
    
    # Descrição
    descricao_servico = models.TextField(
        blank=True,
        null=True,
        verbose_name='Descrição do Serviço',
        help_text='Detalhe do que será feito, normas aplicáveis, etc.'
    )

    # Execução do serviço (confirmação do que foi de fato atendido)
    STATUS_EXECUCAO_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('ATENDIDO', 'Atendido'),
        ('NAO_ATENDIDO', 'Não atendido'),
    ]
    status_execucao = models.CharField(
        max_length=15,
        choices=STATUS_EXECUCAO_CHOICES,
        default='PENDENTE',
        verbose_name='Situação na Execução'
    )
    valor_praticado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Valor Praticado (R$)',
        help_text='Valor efetivamente cobrado. Se vazio, vale o valor cotado.'
    )
    observacao_execucao = models.TextField(
        blank=True,
        default='',
        verbose_name='Observação da Execução'
    )
    ocorrencia = models.ForeignKey(
        'qms.OcorrenciaInstrumento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='itens_cotacao',
        verbose_name='Ocorrência Aberta na Execução'
    )
    
    # Rastreamento
    data_criacao = models.DateTimeField(auto_now_add=True)

    @property
    def valor_cobrado(self):
        """Valor a pagar por este item: 0 se não atendido, senão o praticado (ou o cotado)."""
        if self.status_execucao == 'NAO_ATENDIDO':
            return Decimal('0.00')
        if self.valor_praticado is not None:
            return self.valor_praticado
        return self.valor_total
    
    def save(self, *args, **kwargs):
        """Calcula valor_total antes de salvar"""
        self.valor_total = self.valor_unitario * self.quantidade
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.cotacao_fornecedor.numero} - {self.instrumento.tag}"
    
    class Meta:
        verbose_name = "Item da Cotação"
        verbose_name_plural = "Itens de Cotação"
        unique_together = ('cotacao_fornecedor', 'instrumento')
        ordering = ['instrumento__tag']


class AtendimentoSolicitacao(models.Model):
    """
    ETAPA 3: Atendimento - Define qual cotação atenderá qual necessidade
    Permite múltiplas cotações para mesma necessidade (ex: 2 fornecedores diferentes)
    """
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('CONFIRMADA', 'Confirmada'),
        ('EXECUTANDO', 'Executando'),
        ('CONCLUIDA', 'Concluída'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    solicitacao = models.ForeignKey(
        SolicitacaoCotacao,
        on_delete=models.CASCADE,
        related_name='atendimentos',
        verbose_name='Solicitação'
    )
    item_solicitacao = models.ForeignKey(
        ItemSolicitacaoCotacao,
        on_delete=models.PROTECT,
        related_name='atendimentos',
        verbose_name='Item da Solicitação'
    )
    item_cotacao = models.ForeignKey(
        ItemCotacao,
        on_delete=models.PROTECT,
        related_name='atendimentos',
        verbose_name='Item da Cotação (Fornecedor)'
    )
    
    # Rastreamento
    data_escolha = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data da Escolha'
    )
    responsavel = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='atendimentos_definidos',
        verbose_name='Responsável pela Escolha'
    )
    
    # Planejamento
    data_prevista_atendimento = models.DateField(
        verbose_name='Data Prevista de Atendimento',
        help_text='Quando será executado o serviço?'
    )
    
    # Execução - Para NO_LOCAL
    data_realizada = models.DateField(
        blank=True,
        null=True,
        verbose_name='Data Realizada (No Local)'
    )
    tecnico_responsavel = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Técnico Responsável'
    )
    tecnico_telefone = models.CharField(
        max_length=30,
        blank=True,
        default='',
        verbose_name='Telefone do Técnico'
    )
    
    # Execução - Para NO_LABORATORIO
    data_envio = models.DateField(
        blank=True,
        null=True,
        verbose_name='Data de Envio (Lab)'
    )
    data_retorno_previsto = models.DateField(
        blank=True,
        null=True,
        verbose_name='Data Retorno Previsto'
    )
    data_retorno = models.DateField(
        blank=True,
        null=True,
        verbose_name='Data de Retorno (Lab)'
    )
    
    # Execução - Para COMPRAR_NOVO
    data_chegada = models.DateField(
        blank=True,
        null=True,
        verbose_name='Data de Chegada (Compra Novo)'
    )
    
    observacoes = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observações'
    )

    # Desconsiderar o instrumento nesta solicitação (exige justificativa)
    desconsiderado = models.BooleanField(
        default=False,
        verbose_name='Desconsiderado'
    )
    justificativa_desconsiderar = models.TextField(
        blank=True,
        default='',
        verbose_name='Justificativa para desconsiderar'
    )
    desconsiderado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='atendimentos_desconsiderados',
        verbose_name='Desconsiderado por'
    )
    desconsiderado_em = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Desconsiderado em'
    )
    # Ocorrência aberta automaticamente com a justificativa ao desconsiderar
    ocorrencia_desconsiderar = models.ForeignKey(
        'qms.OcorrenciaInstrumento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='atendimentos_desconsiderados',
        verbose_name='Ocorrência da justificativa'
    )
    
    # Status
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='PENDENTE',
        verbose_name='Status'
    )
    
    # Rastreamento adicional
    atualizado_em = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Atendimento #{self.id} - {self.item_solicitacao.instrumento.tag}"
    
    class Meta:
        verbose_name = "Atendimento de Solicitação"
        verbose_name_plural = "Atendimentos de Solicitação"
        ordering = ['-data_escolha']
        # Permite múltiplas cotações para mesma necessidade
        # unique_together = ('item_solicitacao', 'item_cotacao')


class ProcessoAutomatizacao(models.Model):
    """
    ETAPA 4: Rastreamento de processos automáticos disparados pelo atendimento
    Quando um atendimento é confirmado, cria automaticamente:
    - RegistroCalibracao (se tipo_servico = 'CALIBRACAO')
    - Processo de Substituição (se tipo_servico = 'AQUISICAO')
    """
    TIPO_PROCESSO_CHOICES = [
        ('AQUISICAO', 'Aquisição de Instrumento'),
        ('CALIBRACAO', 'Calibração'),
    ]
    
    STATUS_CHOICES = [
        ('ATIVA', 'Ativa'),
        ('CONCLUIDA', 'Concluída'),
        ('ERRO', 'Erro'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    atendimento = models.ForeignKey(
        AtendimentoSolicitacao,
        on_delete=models.CASCADE,
        related_name='processos_automatizacao',
        verbose_name='Atendimento'
    )
    
    # Tipo de processo
    tipo_processo = models.CharField(
        max_length=20,
        choices=TIPO_PROCESSO_CHOICES,
        verbose_name='Tipo de Processo'
    )
    
    # Rastreamento
    data_inicio = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Início'
    )
    data_conclusao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Data de Conclusão'
    )
    
    # Referência ao objeto criado (dinâmico: pode ser RegistroCalibracao, Substituicao, etc.)
    id_objeto_criado = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='ID do Objeto Criado'
    )
    nome_modelo_objeto = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Modelo do Objeto',
        help_text='Ex: RegistroCalibracao, ProcessoSubstituicao'
    )
    
    # Status
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='ATIVA',
        verbose_name='Status'
    )
    
    # Observações
    observacoes = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observações',
        help_text='Registrar erros ou detalhes do processo'
    )
    
    # Rastreamento
    atualizado_em = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Processo {self.get_tipo_processo_display()} - Atendimento #{self.atendimento.id}"
    
    class Meta:
        verbose_name = "Processo de Automatização"
        verbose_name_plural = "Processos de Automatização"
        ordering = ['-data_inicio']


# ==============================================================================
# MODELO DE TEMPLATES DE ETIQUETAS DE METROLOGIA (EXCEL)
# ==============================================================================

class TemplateEtiquetaInstrumento(models.Model):
    """
    Template/Modelo de etiqueta configurável em Excel (.xlsx) para instrumentos de medição.
    Suporta variações de etiquetas (Individual, Múltiplas Abas e Grade/Tabela).
    """
    VARIACAO_CHOICES = [
        ('INDIVIDUAL', 'Individual (1 Instrumento por Arquivo)'),
        ('MULTI_ABA', 'Múltiplas Abas (1 Aba por Instrumento)'),
        ('GRADE_TABELA', 'Grade / Tabela (Múltiplos Instrumentos na mesma Folha)'),
    ]

    codigo = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Código do Modelo",
        help_text="Ex: ETQ-IND-01, ETQ-MULTI-A4, ETQ-GRADE-2X5"
    )
    nome = models.CharField(
        max_length=200,
        verbose_name="Nome do Template / Variação"
    )
    descricao = models.TextField(
        null=True, blank=True,
        verbose_name="Descrição / Instruções"
    )
    tipo_variacao = models.CharField(
        max_length=30,
        choices=VARIACAO_CHOICES,
        default='INDIVIDUAL',
        verbose_name="Tipo de Variação da Etiqueta"
    )
    arquivo = models.FileField(
        upload_to='templates_etiquetas_metrologia/',
        null=True, blank=True,
        verbose_name="Arquivo do Template (.xlsx)"
    )
    arquivo_base64 = models.TextField(
        blank=True, default="",
        verbose_name="Conteúdo em Base64",
        help_text="Persistência do binário em banco de dados para ambiente serverless/nuvem"
    )
    nome_arquivo_original = models.CharField(
        max_length=255, blank=True, default="",
        verbose_name="Nome Original do Arquivo"
    )
    tamanho_arquivo = models.IntegerField(
        null=True, blank=True,
        verbose_name="Tamanho (bytes)"
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )
    padrao = models.BooleanField(
        default=False,
        verbose_name="Template Padrão da Variação"
    )
    criado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Criado por"
    )
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Criação"
    )
    data_atualizacao = models.DateTimeField(
        auto_now=True,
        verbose_name="Última Atualização"
    )

    def __str__(self):
        return f"{self.codigo} - {self.nome} ({self.get_tipo_variacao_display()})"

    def save(self, *args, **kwargs):
        # Se for marcado como padrão desta variação, desmarcar outros da mesma variação
        if self.padrao:
            TemplateEtiquetaInstrumento.objects.filter(
                tipo_variacao=self.tipo_variacao,
                padrao=True
            ).exclude(pk=self.pk).update(padrao=False)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Template de Etiqueta de Instrumento"
        verbose_name_plural = "Templates de Etiquetas de Instrumentos"
        ordering = ['tipo_variacao', '-padrao', 'nome']