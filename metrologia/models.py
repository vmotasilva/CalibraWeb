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


class Instrumento(models.Model):
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

    # Dados de Calibração
    erro_max = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    erro_min = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    incerteza = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    resultado = models.CharField(
        max_length=20,
        choices=[('OK', 'OK'), ('FORA', 'Fora da Faixa')],
        default='OK',
    )

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
