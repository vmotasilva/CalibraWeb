# Metrologia - Modelos de Instrumentos e Calibração
import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_delete, post_save, m2m_changed
from django.dispatch import receiver
from django.utils import timezone

from core.models import UnidadeMedida
from organization.models import Setor
from rh.models import Colaborador


class CategoriaInstrumento(models.Model):
    """Categorias/Tipos de instrumentos (paquímetro, micrômetro, etc)"""
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    unidade_padrao = models.ForeignKey(
        UnidadeMedida,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Unidade Padrão'
    )

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name_plural = "Categorias de Instrumentos"


class Instrumento(models.Model):
    """Instrumento de medição que será calibrado"""
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
        Colaborador, on_delete=models.SET_NULL, null=True, blank=True
    )
    setor = models.ForeignKey(Setor, on_delete=models.SET_NULL, null=True, blank=True)
    localizacao = models.CharField(max_length=100, blank=True, null=True)
    
    tolerancia_processo = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Tolerância do processo (+/-), associada ao instrumento"
    )

    class Meta:
        verbose_name = "Instrumento"
        verbose_name_plural = "Instrumentos"

    def __str__(self):
        return f"{self.tag} - {self.descricao}"


class FaixaMedicao(models.Model):
    """Faixa de medição de um instrumento"""
    instrumento = models.ForeignKey(
        Instrumento,
        on_delete=models.CASCADE,
        related_name="faixas",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(UnidadeMedida, on_delete=models.PROTECT)

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
        return f"{self.valor_minimo} a {self.valor_maximo} {self.unidade.sigla}"

    class Meta:
        verbose_name_plural = "Faixas de Medição"


class HistoricoCalibracao(models.Model):
    """Registro de calibração de um instrumento"""
    instrumento = models.ForeignKey(
        Instrumento,
        on_delete=models.CASCADE,
        related_name="historicos",
        verbose_name="Instrumento",
        null=True,
        blank=True,
    )
    arquivos_padroes = models.ManyToManyField(
        'ArquivoPadrao',
        blank=True,
        related_name='historicos',
        verbose_name='Arquivos de Padrões (PDF)'
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
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Erro (E)"
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
    certificado_carimbado = models.FileField(
        upload_to="certificados/carimbados/", null=True, blank=True
    )
    
    RESULTADO_CHOICES = [
        ("APROVADO_SEM_CORRECAO", "Aprovado sem correção"),
        ("APROVADO_COM_CORRECAO", "Aprovado com Correção"),
        ("REPROVADO", "Reprovado"),
    ]
    resultado = models.CharField(
        max_length=50,
        choices=RESULTADO_CHOICES,
        default="APROVADO_SEM_CORRECAO"
    )
    
    observacoes = models.TextField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Calibração {self.instrumento.tag} - {self.data_calibracao}"

    class Meta:
        verbose_name = "Histórico de Calibração"
        verbose_name_plural = "Histórico de Calibrações"
        ordering = ["-data_calibracao"]


class ArquivoPadrao(models.Model):
    """PDF de padrão associado a calibração"""
    arquivo = models.FileField(
        upload_to='padroes_historico/',
        verbose_name='PDF do Padrão'
    )
    nome = models.CharField(max_length=200, blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    instrumento = models.ForeignKey(
        Instrumento,
        on_delete=models.CASCADE,
        related_name="arquivos_padroes_instrumento",
        null=True,
        blank=True,
    )

    def __str__(self):
        historico = self.historicos.first()
        if historico:
            return f"{self.nome or self.arquivo.name} ({historico.data_calibracao})"
        return self.nome or self.arquivo.name

    class Meta:
        verbose_name = "Arquivo de Padrão"
        verbose_name_plural = "Arquivos de Padrão"


@receiver([post_save, post_delete], sender=HistoricoCalibracao)
def atualizar_datas_instrumento(sender, instance, **kwargs):
    """Atualiza datas de última e próxima calibração do instrumento"""
    inst = instance.instrumento
    if not inst:
        return
    
    ultima_calib = HistoricoCalibracao.objects.filter(
        instrumento=inst
    ).order_by("-data_calibracao").first()
    
    if ultima_calib:
        inst.data_ultima_calibracao = ultima_calib.data_calibracao
        inst.data_proxima_calibracao = ultima_calib.proxima_calibracao
    else:
        inst.data_ultima_calibracao = None
        inst.data_proxima_calibracao = None
    inst.save()


class ResultadoFaixaCalibracao(models.Model):
    """Resultado detalhado de calibração por faixa de medição"""
    RESULTADO_CHOICES = [
        ("APROVADO_SEM_CORRECAO", "Aprovado sem correção"),
        ("APROVADO_COM_CORRECAO", "Aprovado com Correção"),
        ("REPROVADO", "Reprovado"),
    ]
    
    historico = models.ForeignKey(
        HistoricoCalibracao,
        on_delete=models.CASCADE,
        related_name='resultados_faixas',
        verbose_name='Histórico de Calibração'
    )
    
    faixa_medicao = models.ForeignKey(
        FaixaMedicao,
        on_delete=models.CASCADE,
        related_name='resultados_calibracao',
        verbose_name='Faixa de Medição'
    )
    
    erro_encontrado = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name='Erro Encontrado'
    )
    
    incerteza = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name='Incerteza Expandida'
    )
    
    tolerancia_usada = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name='Tolerância Usada'
    )
    
    resultado = models.CharField(
        max_length=30,
        choices=RESULTADO_CHOICES,
        verbose_name='Resultado da Calibração',
        editable=False
    )
    
    desconsiderada = models.BooleanField(
        default=False,
        verbose_name='Desconsiderar esta faixa',
        help_text='Marque se esta faixa não foi calibrada neste certificado'
    )
    
    def save(self, *args, **kwargs):
        """Calcula automaticamente o resultado baseado em EME e EMA"""
        if not self.desconsiderada:
            EMA = self.tolerancia_usada / 2
            EME = abs(self.erro_encontrado) + self.incerteza
            
            if EME <= EMA:
                self.resultado = "APROVADO_SEM_CORRECAO"
            elif EME <= self.tolerancia_usada:
                self.resultado = "APROVADO_COM_CORRECAO"
            else:
                self.resultado = "REPROVADO"
        else:
            self.resultado = ""
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.historico.instrumento.tag} - {self.faixa_medicao} - {self.resultado}"
    
    class Meta:
        verbose_name = 'Resultado por Faixa'
        verbose_name_plural = 'Resultados por Faixa'
        unique_together = ('historico', 'faixa_medicao')
        ordering = ['faixa_medicao__valor_minimo']


class SolicitacaoInstrumento(models.Model):
    """Solicitação de novo instrumento ou substituição"""
    TIPO_CHOICES = [
        ("NOVA", "Nova Aplicação"),
        ("SUBSTITUICAO", "Substituição (Dano/Perda)"),
    ]
    STATUS_CHOICES = [
        ("PENDENTE", "Pendente"),
        ("EM_ANALISE", "Em Análise pelo Qualidade"),
        ("APROVADO", "Aprovado"),
        ("REJEITADO", "Rejeitado"),
        ("CONCLUIDO", "Entregue/Resolvido"),
    ]

    solicitante = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="solicitacoes"
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    instrumento_alvo = models.ForeignKey(
        Instrumento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Preencher caso seja substituição de um item existente",
    )
    motivo = models.TextField(
        help_text="Descreva a necessidade da aplicação ou o motivo da troca",
        default=""
    )
    data_solicitacao = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDENTE")
    resposta_qualidade = models.TextField(
        blank=True,
        null=True,
        help_text="Parecer do setor de qualidade"
    )

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.solicitante.username} - {self.status}"

    class Meta:
        verbose_name = "Solicitação de Instrumento"
        verbose_name_plural = "Solicitações de Instrumento"


class OcorrenciaInstrumento(models.Model):
    """Registro de ocorrências de instrumentos (avarias, perdas, etc)"""
    TIPO_OCORRENCIA = [
        ("CALIBRACAO", "Calibração"),
        ("VERIFICACAO", "Verificação"),
        ("INSPECAO", "Inspeção"),
        ("AJUSTE", "Ajuste"),
        ("MANUTENCAO", "Manutenção"),
        ("AVARIA", "Avaria/Dano"),
        ("EXTRAVIO", "Extravio/Perda"),
        ("OUTRO", "Outro"),
    ]

    instrumento = models.ForeignKey(
        Instrumento,
        on_delete=models.CASCADE,
        related_name="ocorrencias",
        null=True,
        blank=True,
    )
    tipo = models.CharField(max_length=20, choices=TIPO_OCORRENCIA)
    descricao = models.TextField()
    data_ocorrencia = models.DateField(default=timezone.now)
    usuario_responsavel = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    custo_reparo = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    def __str__(self):
        return f"{self.instrumento} - {self.get_tipo_display()} ({self.data_ocorrencia})"

    class Meta:
        verbose_name = "Ocorrência de Instrumento"
        verbose_name_plural = "Ocorrências de Instrumento"


class OrdemCalibracao(models.Model):
    """Controle e rastreio de calibração"""
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
        """Verifica se instrumento está fora da empresa"""
        return self.tipo_local == "EXTERNO" and self.status == "ENVIADO"

    class Meta:
        verbose_name = "Ordem de Calibração"
        verbose_name_plural = "Ordens de Calibração"


class ImportJob(models.Model):
    """Rastreamento de jobs de importação"""
    STATUS_CHOICES = [
        ("PENDING", "Pendente"),
        ("STARTED", "Em Progresso"),
        ("SUCCESS", "Concluído"),
        ("FAILURE", "Falha"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    filename = models.CharField(max_length=255)
    filepath = models.CharField(max_length=1024, null=True, blank=True)
    job_type = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    result = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ImportJob {self.id} - {self.filename} ({self.status})"

    class Meta:
        verbose_name = "Import Job"
        verbose_name_plural = "Import Jobs"
