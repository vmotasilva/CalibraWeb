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
        ('INTERNA', 'Interna'),
        ('EXTERNA', 'Externa'),
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
        ('INTERNA', 'Interna'),
        ('EXTERNA', 'Externa'),
    ]
    tratativa_calibracao = models.CharField(
        max_length=10,
        choices=TRATATIVA_CHOICES,
        default='INTERNA',
        verbose_name='Tratativa de Calibração',
        help_text='Indica se a calibração é feita internamente ou com fornecedor externo'
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
        6. INSTRUMENTOS_SELECIONADOS (itens sem cotações)
        7. ABERTA (sem itens)
        """
        novo_status = self.status
        
        # Verificar primeiro se há atendimentos
        atendimentos_total = self.atendimentos.count()
        
        if atendimentos_total > 0:
            # Contar atendimentos completos conforme o tipo de local
            atendimentos_completos = 0
            for atendimento in self.atendimentos.all():
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
                atendimentos_planejados = self.atendimentos.filter(data_prevista_atendimento__isnull=False).count()
                
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
            elif self.cotacoes_fornecedores.count() == 0:
                novo_status = 'INSTRUMENTOS_SELECIONADOS'
            elif self.cotacoes_fornecedores.filter(status='RESPONDIDA').exists():
                novo_status = 'COTACAO_SOLICITADA'
            elif self.cotacoes_fornecedores.filter(status='ACEITA').exists():
                novo_status = 'AGUARDANDO_PLANEJAMENTO'
            else:
                # Manter status atual como fallback
                novo_status = self.status
        
        # Atualizar se houver mudança (não alterar CONCLUIDA ou CANCELADA)
        if novo_status != self.status and self.status not in ['CONCLUIDA', 'CANCELADA']:
            type(self).objects.filter(pk=self.pk).update(status=novo_status)
            self.status = novo_status

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
    
    def get_valor_total(self):
        """Calcula o valor total da cotação"""
        return sum(item.valor_total for item in self.itens.all())
    
    class Meta:
        verbose_name = "Cotação do Fornecedor"
        verbose_name_plural = "Cotações de Fornecedores"
        ordering = ["-data_criacao"]
        unique_together = ('solicitacao', 'fornecedor')


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
    
    # Rastreamento
    data_criacao = models.DateTimeField(auto_now_add=True)
    
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