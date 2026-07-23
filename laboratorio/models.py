from datetime import timedelta
import unicodedata

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def _normalizar_texto_categoria(valor):
    texto = unicodedata.normalize("NFKD", valor or "")
    return "".join(caractere for caractere in texto if not unicodedata.combining(caractere)).lower().strip()


class CategoriaLaboratorio(models.Model):
    IMPACTO_BAIXO = "BAIXO"
    IMPACTO_MEDIO = "MEDIO"
    IMPACTO_ALTO = "ALTO"
    IMPACTO_CRITICO = "CRITICO"

    IMPACTO_CHOICES = [
        (IMPACTO_BAIXO, "Baixo"),
        (IMPACTO_MEDIO, "Medio"),
        (IMPACTO_ALTO, "Alto"),
        (IMPACTO_CRITICO, "Critico"),
    ]

    nome = models.CharField(max_length=150, unique=True, verbose_name="Categoria")
    impacto = models.CharField(
        max_length=20,
        choices=IMPACTO_CHOICES,
        default=IMPACTO_MEDIO,
        verbose_name="Impacto padrao",
    )
    descricao = models.TextField(blank=True, verbose_name="Descricao")
    ativo = models.BooleanField(default=True, verbose_name="Ativa")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Categoria de ocorrencia do laboratorio"
        verbose_name_plural = "Categorias de ocorrencia do laboratorio"

    def __str__(self):
        return self.nome

    @property
    def nome_normalizado(self):
        return _normalizar_texto_categoria(self.nome)

    @property
    def exige_colaborador(self):
        return self.nome_normalizado.startswith("falta de colaborador")

    @property
    def exige_maquina(self):
        return self.nome_normalizado.startswith("parada de maquina") or self.nome_normalizado.startswith("parada de manutencao")


from rh.models import Colaborador
from maquinas.models import Maquina

class OcorrenciaLaboratorio(models.Model):
    categoria = models.ForeignKey(
        CategoriaLaboratorio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocorrencias",
        verbose_name="Categoria",
    )
    assunto = models.CharField(max_length=200, verbose_name="Assunto")
    colaborador = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocorrencias_laboratorio_colaborador",
        verbose_name="Colaborador (se aplicável)",
    )
    maquina = models.ForeignKey(
        Maquina,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocorrencias_laboratorio_maquina",
        verbose_name="Máquina (se aplicável)",
    )
    detalhamento = models.TextField(verbose_name="Detalhamento")
    consequencias = models.TextField(blank=True, verbose_name="Consequencias")
    impacto = models.CharField(
        max_length=20,
        choices=CategoriaLaboratorio.IMPACTO_CHOICES,
        default=CategoriaLaboratorio.IMPACTO_MEDIO,
        verbose_name="Impacto",
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocorrencias_laboratorio",
        verbose_name="Responsavel",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocorrencias_laboratorio_criadas",
        verbose_name="Criado por",
    )
    data_abertura = models.DateTimeField(
        default=timezone.now,
        verbose_name="Data e hora da abertura",
    )
    data_encerramento = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data e hora do encerramento",
    )
    perda_producao = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Perda de producao",
    )
    unidade_perda_producao = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Unidade da perda de producao",
    )
    horas_indisponibilidade = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Horas de indisponibilidade",
    )
    impacto_financeiro = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Impacto financeiro estimado",
    )
    observacoes_encerramento = models.TextField(
        blank=True,
        verbose_name="Observacoes do encerramento",
    )
    duracao = models.DurationField(
        null=True,
        blank=True,
        editable=False,
        verbose_name="Duracao da ocorrencia",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data_abertura"]
        verbose_name = "Ocorrencia do laboratorio"
        verbose_name_plural = "Ocorrencias do laboratorio"
        indexes = [
            models.Index(fields=["data_abertura"]),
            models.Index(fields=["impacto"]),
        ]

    def __str__(self):
        return self.assunto

    def clean(self):
        errors = {}

        if not self.assunto and self.categoria:
            self.assunto = self.categoria.nome

        if not self.assunto:
            errors["assunto"] = "Informe um assunto ou selecione uma categoria."

        if self.data_encerramento and self.data_encerramento <= self.data_abertura:
            errors["data_encerramento"] = "O encerramento deve ser posterior a abertura."

        if not self.impacto and self.categoria:
            self.impacto = self.categoria.impacto

        if self.categoria and self.categoria.exige_colaborador and not self.colaborador:
            errors["colaborador"] = "Selecione o colaborador vinculado a esta ocorrencia."

        if self.categoria and self.categoria.exige_maquina and not self.maquina:
            errors["maquina"] = "Selecione a maquina vinculada a esta ocorrencia."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.categoria and not self.assunto:
            self.assunto = self.categoria.nome

        if self.categoria and not self.impacto:
            self.impacto = self.categoria.impacto

        self.duracao = None
        if self.data_abertura and self.data_encerramento:
            self.duracao = self.data_encerramento - self.data_abertura

        super().save(*args, **kwargs)

    @property
    def status(self):
        return "Encerrada" if self.data_encerramento else "Aberta"

    @property
    def impacto_badge_class(self):
        return {
            CategoriaLaboratorio.IMPACTO_BAIXO: "success",
            CategoriaLaboratorio.IMPACTO_MEDIO: "warning text-dark",
            CategoriaLaboratorio.IMPACTO_ALTO: "danger",
            CategoriaLaboratorio.IMPACTO_CRITICO: "dark",
        }.get(self.impacto, "secondary")

    @property
    def possui_impacto_registrado(self):
        return any(
            valor not in (None, "")
            for valor in (
                self.perda_producao,
                self.horas_indisponibilidade,
                self.impacto_financeiro,
                self.observacoes_encerramento,
            )
        )

    @staticmethod
    def formatar_duracao(valor):
        if not valor:
            return "-"

        total_segundos = int(valor.total_seconds())
        total_segundos = abs(total_segundos)
        dias, resto = divmod(total_segundos, 86400)
        horas, resto = divmod(resto, 3600)
        minutos, _segundos = divmod(resto, 60)

        partes = []
        if dias:
            partes.append(f"{dias}d")
        if horas:
            partes.append(f"{horas}h")
        partes.append(f"{minutos}min")
        return " ".join(partes)

    @property
    def duracao_formatada(self):
        valor = self.duracao
        if not valor and self.data_abertura and not self.data_encerramento:
            valor = timezone.now() - self.data_abertura
        return self.formatar_duracao(valor)


class OcorrenciaLaboratorioAnotacao(models.Model):
    ocorrencia = models.ForeignKey(
        OcorrenciaLaboratorio,
        on_delete=models.CASCADE,
        related_name="anotacoes_registradas",
        verbose_name="Ocorrencia",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="anotacoes_ocorrencias_laboratorio",
        verbose_name="Responsavel pela anotacao",
    )
    texto = models.TextField(verbose_name="Anotacao")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Data e hora da anotacao")

    class Meta:
        ordering = ["-criado_em", "-id"]
        verbose_name = "Anotacao da ocorrencia do laboratorio"
        verbose_name_plural = "Anotacoes das ocorrencias do laboratorio"

    def __str__(self):
        return f"Anotacao de {self.autor_display} em {timezone.localtime(self.criado_em).strftime('%d/%m/%Y %H:%M:%S')}"

    @property
    def autor_display(self):
        if not self.usuario:
            return "Usuario nao informado"
        return self.usuario.get_full_name() or self.usuario.username


class TratamentoAntiReflexo(models.Model):
    nome = models.CharField(max_length=150, unique=True, verbose_name="Nome do Tratamento")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Tratamento Antirreflexo"
        verbose_name_plural = "Tratamentos Antirreflexo"

    def __str__(self):
        return self.nome


class TurnoCoating(models.Model):
    TURNO_CHOICES = [
        ('1', 'Turno 01'),
        ('2', 'Turno 02'),
        ('3', 'Turno 03'),
    ]
    data = models.DateField(default=timezone.now, verbose_name="Data do Turno")
    turno = models.CharField(max_length=1, choices=TURNO_CHOICES, verbose_name="Turno")
    inicio = models.DateTimeField(verbose_name="Início do Turno")
    fim = models.DateTimeField(null=True, blank=True, verbose_name="Fim do Turno")
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Responsável pelo Fechamento",
    )

    class Meta:
        ordering = ["-data", "-turno"]
        verbose_name = "Turno de Coating"
        verbose_name_plural = "Turnos de Coating"
        unique_together = [('data', 'turno')]

    def __str__(self):
        return f"{self.get_turno_display()} - {self.data.strftime('%d/%m/%Y')}"


class RegistroCoating(models.Model):
    LADO_CHOICES = [
        ('CC', 'Côncavo'),
        ('CX', 'Convexo'),
    ]
    turno_coating = models.ForeignKey(
        TurnoCoating, 
        on_delete=models.PROTECT, 
        related_name="registros",
        verbose_name="Turno de Referência"
    )
    maquina = models.ForeignKey(Maquina, on_delete=models.PROTECT, verbose_name="Máquina")
    lote = models.IntegerField(verbose_name="Número do Lote")
    tratamento = models.ForeignKey(TratamentoAntiReflexo, on_delete=models.PROTECT, verbose_name="Tratamento")
    lado = models.CharField(max_length=2, choices=LADO_CHOICES, verbose_name="Lado da Lente")
    
    hora_entrada = models.TimeField(verbose_name="Hora de Entrada")
    hora_saida = models.TimeField(null=True, blank=True, verbose_name="Hora de Saída")
    
    preparacao = models.ForeignKey(Colaborador, on_delete=models.PROTECT, related_name="preparacoes_coating", verbose_name="Preparação")
    montagem = models.ForeignKey(Colaborador, on_delete=models.PROTECT, related_name="montagens_coating", verbose_name="Montagem")
    
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-turno_coating__data", "-hora_entrada", "lote"]
        verbose_name = "Registro de Coating"
        verbose_name_plural = "Registros de Coating"

    def __str__(self):
        return f"Lote {self.lote} - {self.maquina} ({self.get_lado_display()})"

