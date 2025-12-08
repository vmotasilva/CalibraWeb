# RH - Modelos de Recursos Humanos
from datetime import date
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import TURNOS_CHOICES, STATUS_CHOICES
from organization.models import Setor, CentroCusto


class Colaborador(models.Model):
    """Informações de colaboradores/funcionários"""
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
        Setor, on_delete=models.SET_NULL, null=True, verbose_name="Setor"
    )
    centro_custo = models.ForeignKey(
        CentroCusto,
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
    is_active = models.BooleanField(default=True, verbose_name="Colaborador Ativo (RH)")
    criado_em = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.matricula = self.matricula.upper().strip()
        self.nome_completo = self.nome_completo.upper().strip()
        if self.cpf:
            self.cpf = self.cpf.replace(".", "").replace("-", "").strip()
        super().save(*args, **kwargs)

    def get_chefia(self):
        """Retorna a hierarquia do setor/turno do colaborador"""
        if not self.setor:
            return None
        try:
            return HierarquiaSetor.objects.get(setor=self.setor, turno=self.turno)
        except HierarquiaSetor.DoesNotExist:
            return None

    def __str__(self):
        return f"{self.nome_completo} ({self.matricula})"

    class Meta:
        verbose_name = "Colaborador"
        verbose_name_plural = "Colaboradores (RH)"


class HierarquiaSetor(models.Model):
    """Hierarquia de liderança por setor e turno"""
    setor = models.ForeignKey(Setor, on_delete=models.CASCADE, verbose_name="Setor")
    turno = models.CharField(
        max_length=20, choices=TURNOS_CHOICES, verbose_name="Turno"
    )
    lider = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="liderados_setor",
        verbose_name="Líder",
    )
    supervisor = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supervisionados_setor",
        verbose_name="Supervisor",
    )
    gerente = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gerenciados_setor",
        verbose_name="Gerente",
    )
    diretor = models.ForeignKey(
        Colaborador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diretoria_setor",
        verbose_name="Diretor",
    )

    def __str__(self):
        return f"Hierarquia: {self.setor.nome} - {self.get_turno_display()}"

    class Meta:
        verbose_name = "Hierarquia"
        verbose_name_plural = "Hierarquia (Setor x Turno)"
        unique_together = ("setor", "turno")


class Ferias(models.Model):
    """Registro de férias de colaboradores"""
    colaborador = models.ForeignKey(
        Colaborador, on_delete=models.CASCADE, related_name="ferias_set"
    )
    periodo_aquisitivo_inicio = models.DateField(null=True, blank=True)
    periodo_aquisitivo_fim = models.DateField(null=True, blank=True)
    data_limite = models.DateField(null=True, blank=True)
    data_inicio = models.DateField(null=True, blank=True)
    data_fim = models.DateField(null=True, blank=True)
    saldo_dias = models.IntegerField(default=30)
    dias_gozados = models.IntegerField(default=0)
    dias_vendidos = models.IntegerField(
        default=0, null=True, blank=True, verbose_name="Dias Vendidos (Abono)"
    )
    status = models.CharField(max_length=20, default="AQUISITIVO")


@receiver(post_save, sender=Ferias)
def atualizar_status_ferias(sender, instance, **kwargs):
    """Atualiza status em_ferias do colaborador quando férias são registradas"""
    c = instance.colaborador
    h = date.today()
    em = c.ferias_set.filter(data_inicio__lte=h, data_fim__gte=h).exists()
    if c.em_ferias != em:
        c.em_ferias = em
        c.save()


class Ocorrencia(models.Model):
    """Registro de ocorrências de colaboradores (faltas, atrasos, elogios, etc)"""
    TIPO = [
        ("FALTA", "Falta"),
        ("ATRASO", "Atraso"),
        ("ADV", "Advertência"),
        ("ELOGIO", "Elogio"),
        ("OUTRO", "Outro"),
    ]
    NATUREZA = [
        ("NEGATIVA", "🔴 Negativa"),
        ("POSITIVA", "🟢 Positiva"),
        ("NEUTRA", "⚪ Neutra"),
    ]
    colaborador = models.ForeignKey(
        Colaborador,
        on_delete=models.CASCADE,
        related_name="ocorrencias",
        null=True,
        blank=True,
    )
    data_ocorrencia = models.DateField(verbose_name="Data")
    tipo = models.CharField(max_length=20, choices=TIPO)
    natureza = models.CharField(max_length=10, choices=NATUREZA, default="NEGATIVA")
    titulo = models.CharField(
        max_length=100, verbose_name="Resumo", null=True, blank=True
    )
    descricao = models.TextField(verbose_name="Detalhes")
    arquivo_evidencia = models.FileField(
        upload_to="ocorrencias/", null=True, blank=True
    )

    def save(self, *args, **kwargs):
        if self.tipo in ["FALTA", "ATRASO", "ADV"]:
            self.natureza = "NEGATIVA"
        elif self.tipo == "ELOGIO":
            self.natureza = "POSITIVA"
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Ocorrência"
        verbose_name_plural = "Ocorrências"


class DocumentoPessoal(models.Model):
    """Documentos pessoais de colaboradores (certificados, etc)"""
    colaborador = models.ForeignKey(
        Colaborador, on_delete=models.CASCADE, related_name="documentos_pessoais"
    )
    tipo = models.CharField(max_length=50, verbose_name="Tipo")
    arquivo = models.FileField(upload_to="rh_docs/", verbose_name="Arquivo")
    descricao = models.CharField(max_length=100, null=True, blank=True)
    data_upload = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "Documento Pessoal"
        verbose_name_plural = "Documentos Pessoais"
