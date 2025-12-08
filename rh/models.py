from django.db import models
from django.contrib.auth.models import User
from datetime import date, timedelta
from decimal import Decimal
from core.models import TURNOS_CHOICES

# ==============================================================================
# RH - RECURSOS HUMANOS
# ==============================================================================

class Colaborador(models.Model):
    user_django = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Usuário de Acesso (Login)",
    )
    matricula = models.CharField(max_length=20, unique=True, verbose_name="Matrícula")
    cpf = models.CharField(
        max_length=14, unique=True, null=True, blank=True, verbose_name="CPF"
    )
    nome_completo = models.CharField(max_length=100, verbose_name="Nome Completo")
    cargo = models.CharField(max_length=100, null=True, blank=True)
    grupo = models.CharField(max_length=50, verbose_name="Grupo (Macro)")
    setor = models.ForeignKey(
        'organization.Setor', on_delete=models.SET_NULL, null=True, verbose_name="Setor"
    )
    centro_custo = models.ForeignKey(
        'organization.CentroCusto',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Centro de Custo",
    )
    turno = models.CharField(
        max_length=20, choices=TURNOS_CHOICES, default="ADM", verbose_name="Turno"
    )
    salario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Salário (R$)",
    )
    em_ferias = models.BooleanField(default=False, verbose_name="Está de Férias?")
    lider = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="liderados",
        verbose_name="Líder/Supervisor Direto",
    )
    supervisor = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supervisionados",
        verbose_name="Supervisor",
    )
    gerente = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gerenciados",
        verbose_name="Gerente",
    )
    pacotes_treinamento = models.ManyToManyField(
        "training.PacoteTreinamento",
        blank=True,
        verbose_name="Pacotes Atribuídos",
        related_name="colaboradores",
    )
    is_active = models.BooleanField(default=True, verbose_name="Colaborador Ativo (RH)")
    criado_em = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.matricula = self.matricula.upper().strip()
        self.nome_completo = self.nome_completo.upper().strip()
        if self.cpf:
            self.cpf = self.cpf.replace(".", "").replace("-", "").strip()
        super().save(*args, **kwargs)

    def get_chefia(self):
        if not self.setor:
            return None
        try:
            return HierarquiaSetor.objects.get(setor=self.setor, turno=self.turno)
        except Exception:
            return None

    def __str__(self):
        return f"{self.nome_completo} ({self.matricula})"

    class Meta:
        verbose_name = "Colaborador"
        verbose_name_plural = "Colaboradores (RH)"


class Ferias(models.Model):
    colaborador = models.ForeignKey(
        Colaborador, on_delete=models.CASCADE, verbose_name="Colaborador"
    )
    data_inicio = models.DateField(verbose_name="Data de Início")
    data_fim = models.DateField(verbose_name="Data de Término")
    dias_solicitados = models.IntegerField(verbose_name="Dias Solicitados")
    aprovada = models.BooleanField(default=False, verbose_name="Aprovada?")
    descricao = models.TextField(null=True, blank=True, verbose_name="Observações")

    def dias_decorridos(self):
        return (date.today() - self.data_inicio).days

    def dias_restantes(self):
        return (self.data_fim - date.today()).days

    def esta_em_ferias(self):
        return self.data_inicio <= date.today() <= self.data_fim

    def __str__(self):
        return f"{self.colaborador.nome_completo} ({self.data_inicio} a {self.data_fim})"

    class Meta:
        verbose_name = "Férias"
        verbose_name_plural = "Período de Férias"
        ordering = ["-data_inicio"]


class Ocorrencia(models.Model):
    NATUREZA_CHOICES = [
        ("POSITIVA", "Positiva"),
        ("NEGATIVA", "Negativa"),
        ("NEUTRA", "Neutra"),
    ]
    TIPO_CHOICES = [
        ("AVISO", "Aviso"),
        ("ADVERTENCIA", "Advertência"),
        ("SUSPENSAO", "Suspensão"),
        ("DEMISSAO", "Demissão"),
        ("ELOGIO", "Elogio"),
        ("REABILITACAO", "Reabilitação"),
    ]

    colaborador = models.ForeignKey(
        Colaborador,
        on_delete=models.CASCADE,
        verbose_name="Colaborador",
        related_name="ocorrencias",
    )
    data_ocorrencia = models.DateField(auto_now_add=True, verbose_name="Data da Ocorrência")
    tipo = models.CharField(
        max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo de Ocorrência"
    )
    natureza = models.CharField(
        max_length=20, choices=NATUREZA_CHOICES, verbose_name="Natureza"
    )
    descricao = models.TextField(verbose_name="Descrição")
    motivo = models.CharField(max_length=300, null=True, blank=True, verbose_name="Motivo")

    def save(self, *args, **kwargs):
        if self.tipo == "ELOGIO":
            self.natureza = "POSITIVA"
        elif self.tipo in ["AVISO", "ADVERTENCIA", "SUSPENSAO", "DEMISSAO"]:
            self.natureza = "NEGATIVA"
        else:
            self.natureza = "NEUTRA"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.colaborador.nome_completo} - {self.tipo} ({self.data_ocorrencia})"

    class Meta:
        verbose_name = "Ocorrência"
        verbose_name_plural = "Ocorrências (RH)"
        ordering = ["-data_ocorrencia"]


class DocumentoPessoal(models.Model):
    colaborador = models.ForeignKey(
        Colaborador,
        on_delete=models.CASCADE,
        verbose_name="Colaborador",
        related_name="documentos",
    )
    tipo_documento = models.CharField(
        max_length=50, verbose_name="Tipo de Documento"
    )
    numero_documento = models.CharField(
        max_length=50, null=True, blank=True, verbose_name="Número do Documento"
    )
    data_emissao = models.DateField(null=True, blank=True, verbose_name="Data de Emissão")
    data_validade = models.DateField(null=True, blank=True, verbose_name="Data de Validade")
    arquivo = models.FileField(
        upload_to="documentos_pessoais/", null=True, blank=True, verbose_name="Arquivo"
    )
    observacoes = models.TextField(null=True, blank=True, verbose_name="Observações")

    def __str__(self):
        return f"{self.colaborador.nome_completo} - {self.tipo_documento}"

    class Meta:
        verbose_name = "Documento Pessoal"
        verbose_name_plural = "Documentos Pessoais"
        ordering = ["colaborador", "tipo_documento"]
