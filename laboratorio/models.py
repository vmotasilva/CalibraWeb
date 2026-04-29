from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


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
        if not self.assunto and self.categoria:
            self.assunto = self.categoria.nome

        if not self.assunto:
            raise ValidationError({"assunto": "Informe um assunto ou selecione uma categoria."})

        if self.data_encerramento and self.data_encerramento <= self.data_abertura:
            raise ValidationError(
                {"data_encerramento": "O encerramento deve ser posterior a abertura."}
            )

        if not self.impacto and self.categoria:
            self.impacto = self.categoria.impacto

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
