from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date
from decimal import Decimal

# ==============================================================================
# METROLOGIA - CALIBRAÇÃO E INSTRUMENTOS
# ==============================================================================

class CategoriaInstrumento(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    unidade_padrao = models.ForeignKey(
        'core.UnidadeMedida', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Unidade Padrão'
    )

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name_plural = "Categorias de Instrumentos"


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
    nome = models.CharField(max_length=255)
    descricao = models.TextField(blank=True, null=True)
    arquivo = models.FileField(upload_to='padroes/')
    data_upload = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Arquivo Padrão"
        verbose_name_plural = "Arquivos Padrões"


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

    def save(self, *args, **kwargs):
        """Auto-calculate EMA, EME and resultado."""
        # Calcular EMA = 2*Tolerância/4 = Tolerância/2
        if self.tolerancia is not None:
            self.ema = self.tolerancia / 2
        
        # Calcular EME = Erro + Incerteza
        if self.erro is not None and self.incerteza is not None:
            self.eme = self.erro + self.incerteza
        
        # Calcular resultado baseado em EME e EMA
        if self.eme is not None and self.ema is not None:
            eme_abs = abs(self.eme)
            ema_3x = self.ema * 3
            
            if eme_abs > ema_3x:
                self.resultado = 'REPROVADO'
            elif eme_abs <= self.ema:
                self.resultado = 'APROVADO_SEM_CORRECAO'
            else:
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
    arquivos_padroes = models.ManyToManyField(
        ArquivoPadrao, blank=True, related_name='historicos', verbose_name='Arquivos de Padrões (PDF)'
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

    def save(self, *args, **kwargs):
        # Auto-calculate resultado based on error vs tolerance
        if self.erro_encontrado is not None and self.tolerancia_usada is not None:
            if abs(self.erro_encontrado) <= self.tolerancia_usada:
                self.resultado = "APROVADO_SEM_CORRECAO"
            else:
                self.resultado = "REPROVADO"
        super().save(*args, **kwargs)

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
