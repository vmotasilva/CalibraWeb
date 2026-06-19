from django.db import models
from django.contrib.auth.models import User
from datetime import date, timedelta
from decimal import Decimal
from core.models import TURNOS_CHOICES
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
    afastado = models.BooleanField(
        default=False, 
        verbose_name="Colaborador Afastado?",
        help_text="Marque se colaborador está afastado (INSS, Licença, etc.)"
    )
    tipo_afastamento = models.CharField(
        max_length=100, 
        null=True, 
        blank=True,
        verbose_name="Tipo de Afastamento",
        help_text="Ex: INSS, LICENÇA_MATERNIDADE, LICENÇA_PATERNIDADE, FÉRIAS, OUTRO"
    )
    data_inicio_afastamento = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data Início do Afastamento"
    )
    data_fim_afastamento = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data Fim do Afastamento"
    )
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
        "procedures.PacoteTreinamento",
        blank=True,
        verbose_name="Pacotes Atribuídos",
        related_name="colaboradores",
    )
    is_active = models.BooleanField(default=True, verbose_name="Colaborador Ativo (RH)")
    criado_em = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def get_chefia(self):
        if not self.setor:
            return None
        try:
            return HierarquiaSetor.objects.get(setor=self.setor, turno=self.turno)
        except Exception:
            return None

    def get_ultimo_setor_historico(self):
        """Retorna o último registro de mudança de setor"""
        return self.historico_setor.first() if self.historico_setor.exists() else None

    def get_ultimo_cargo_historico(self):
        """Retorna o último registro de mudança de cargo"""
        return self.historico_posto.first() if self.historico_posto.exists() else None

    def get_ultimo_salario_historico(self):
        """Retorna o último registro de mudança de salário"""
        return self.historico_salario.first() if self.historico_salario.exists() else None

    def get_historico_completo(self):
        """Retorna o histórico completo de mudanças ordenado por data"""
        return self.historico_geral.all().order_by('-data_mudanca')

    def __str__(self):
        return f"{self.nome_completo} ({self.matricula})"

    class Meta:
        verbose_name = "Colaborador"
        verbose_name_plural = "Colaboradores (RH)"
        indexes = [
            models.Index(fields=['setor', 'is_active']),
            models.Index(fields=['lider', '-matricula']),
            models.Index(fields=['em_ferias', 'setor']),
            models.Index(fields=['is_active', '-criado_em']),
            models.Index(fields=['turno'], name='rh_colaborador_turno_idx'),
            models.Index(fields=['is_active', 'afastado', 'em_ferias', 'turno', 'setor'], name='rh_colab_dash_filters_idx'),
        ]


class Ferias(models.Model):
    colaborador = models.ForeignKey(
        Colaborador, on_delete=models.CASCADE, verbose_name="Colaborador"
    )

    STATUS_CHOICES = [
        ("PLANEJADO", "Planejado"),
        ("EM_ANDAMENTO", "Em andamento"),
        ("CONCLUIDO", "Concluído")
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        verbose_name="Status das Férias",
        default="PLANEJADO"
    )
    data_inicio = models.DateField(verbose_name="Data de Início")
    data_fim = models.DateField(verbose_name="Data de Término")
    dias_solicitados = models.IntegerField(verbose_name="Dias Solicitados")
    aprovada = models.BooleanField(default=False, verbose_name="Aprovada?")
    vencimento = models.DateField(verbose_name="Vencimento das Férias", null=True, blank=True)
    descricao = models.TextField(null=True, blank=True, verbose_name="Observações")

    def dias_decorridos(self):
        return (date.today() - self.data_inicio).days

    def dias_restantes(self):
        return (self.data_fim - date.today()).days


    def esta_em_ferias(self):
        return self.data_inicio <= date.today() <= self.data_fim

    def save(self, *args, **kwargs):
        hoje = date.today()
        # Atualiza status automaticamente
        if self.data_inicio and self.data_fim:
            if self.data_inicio > hoje:
                self.status = "PLANEJADO"
            elif self.data_inicio <= hoje <= self.data_fim:
                self.status = "EM_ANDAMENTO"
            elif hoje > self.data_fim:
                self.status = "CONCLUIDO"
        super().save(*args, **kwargs)
        # Atualiza o campo em_ferias do colaborador
        colaborador = self.colaborador
        ferias_ativas = Ferias.objects.filter(
            colaborador=colaborador,
            aprovada=True,
            data_inicio__lte=hoje,
            data_fim__gte=hoje
        ).exists()
        colaborador.em_ferias = ferias_ativas
        colaborador.save(update_fields=["em_ferias"])

    def __str__(self):
        return f"{self.colaborador.nome_completo} ({self.data_inicio} a {self.data_fim})"

    class Meta:
        verbose_name = "Férias"
        verbose_name_plural = "Período de Férias"
        ordering = ["-data_inicio"]
        indexes = [
            models.Index(fields=['colaborador', 'data_inicio', 'data_fim']),
            models.Index(fields=['status', '-data_inicio']),
            models.Index(fields=['aprovada', 'data_inicio', 'data_fim']),
        ]


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
        ("FEEDBACK", "Feedback"),
    ]

    colaborador = models.ForeignKey(
        Colaborador,
        on_delete=models.CASCADE,
        verbose_name="Colaborador",
        related_name="ocorrencias",
    )
    condutor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Responsável pela Ocorrência (Quem está conduzindo)",
        related_name="ocorrencias_conduzidas",
    )
    data_ocorrencia = models.DateField(default=date.today, verbose_name="Data da Ocorrência")
    tipo = models.CharField(
        max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo de Ocorrência"
    )
    natureza = models.CharField(
        max_length=20, choices=NATUREZA_CHOICES, verbose_name="Natureza"
    )
    descricao = models.TextField(verbose_name="Descrição")
    motivo = models.CharField(max_length=300, null=True, blank=True, verbose_name="Motivo")
    arquivo_evidencia = models.FileField(
        upload_to="ocorrencias_evidencias/",
        null=True,
        blank=True,
        verbose_name="Arquivo de Evidência"
    )

    def save(self, *args, **kwargs):
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


# ==============================================================================
# HISTÓRICO DE MUDANÇAS - RASTREABILIDADE
# ==============================================================================

class HistoricoSetor(models.Model):
    """Histórico de mudanças de setor do colaborador"""
    colaborador = models.ForeignKey(
        Colaborador,
        on_delete=models.CASCADE,
        related_name="historico_setor",
        verbose_name="Colaborador"
    )
    setor_anterior = models.ForeignKey(
        'organization.Setor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="historico_saida",
        verbose_name="Setor Anterior"
    )
    setor_novo = models.ForeignKey(
        'organization.Setor',
        on_delete=models.SET_NULL,
        null=True,
        related_name="historico_entrada",
        verbose_name="Setor Novo"
    )
    data_mudanca = models.DateField(auto_now_add=True, verbose_name="Data da Mudança")
    data_efetiva = models.DateField(verbose_name="Data Efetiva", null=True, blank=True)
    motivo = models.CharField(
        max_length=200, null=True, blank=True, verbose_name="Motivo"
    )
    registrado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mudancas_setor_registradas",
        verbose_name="Registrado por"
    )

    def __str__(self):
        return f"{self.colaborador.nome_completo} - {self.setor_anterior} → {self.setor_novo} ({self.data_mudanca})"

    class Meta:
        verbose_name = "Histórico de Setor"
        verbose_name_plural = "Histórico de Setores"
        ordering = ["-data_mudanca"]


class HistoricoPosto(models.Model):
    """Histórico de mudanças de posto/cargo do colaborador"""
    colaborador = models.ForeignKey(
        Colaborador,
        on_delete=models.CASCADE,
        related_name="historico_posto",
        verbose_name="Colaborador"
    )
    cargo_anterior = models.CharField(
        max_length=100, null=True, blank=True, verbose_name="Cargo Anterior"
    )
    cargo_novo = models.CharField(
        max_length=100, verbose_name="Novo Cargo"
    )
    data_mudanca = models.DateField(auto_now_add=True, verbose_name="Data da Mudança")
    data_efetiva = models.DateField(verbose_name="Data Efetiva", null=True, blank=True)
    motivo = models.CharField(
        max_length=200, null=True, blank=True, verbose_name="Motivo"
    )
    registrado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mudancas_cargo_registradas",
        verbose_name="Registrado por"
    )

    def __str__(self):
        return f"{self.colaborador.nome_completo} - {self.cargo_anterior} → {self.cargo_novo} ({self.data_mudanca})"

    class Meta:
        verbose_name = "Histórico de Posto"
        verbose_name_plural = "Histórico de Postos"
        ordering = ["-data_mudanca"]


class HistoricoSalario(models.Model):
    """Histórico de mudanças de salário do colaborador"""
    colaborador = models.ForeignKey(
        Colaborador,
        on_delete=models.CASCADE,
        related_name="historico_salario",
        verbose_name="Colaborador"
    )
    salario_anterior = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Salário Anterior"
    )
    salario_novo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Novo Salário"
    )
    diferenca = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Diferença"
    )
    data_mudanca = models.DateField(auto_now_add=True, verbose_name="Data da Mudança")
    data_efetiva = models.DateField(verbose_name="Data Efetiva", null=True, blank=True)
    motivo = models.CharField(
        max_length=200, null=True, blank=True, verbose_name="Motivo"
    )
    registrado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mudancas_salario_registradas",
        verbose_name="Registrado por"
    )

    def save(self, *args, **kwargs):
        if self.salario_anterior and self.salario_novo:
            self.diferenca = self.salario_novo - self.salario_anterior
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.colaborador.nome_completo} - R$ {self.salario_anterior} → R$ {self.salario_novo} ({self.data_mudanca})"

    class Meta:
        verbose_name = "Histórico de Salário"
        verbose_name_plural = "Histórico de Salários"
        ordering = ["-data_mudanca"]


class HistoricoColaborador(models.Model):
    """Histórico geral de mudanças do colaborador (log consolidado)"""
    TIPOS_MUDANCA = [
        ("SETOR", "Mudança de Setor"),
        ("CARGO", "Mudança de Cargo"),
        ("SALARIO", "Mudança de Salário"),
        ("TURNO", "Mudança de Turno"),
        ("STATUS", "Mudança de Status"),
        ("OUTRO", "Outro"),
    ]
    
    colaborador = models.ForeignKey(
        Colaborador,
        on_delete=models.CASCADE,
        related_name="historico_geral",
        verbose_name="Colaborador"
    )
    tipo_mudanca = models.CharField(
        max_length=20, choices=TIPOS_MUDANCA, verbose_name="Tipo de Mudança"
    )
    descricao = models.TextField(verbose_name="Descrição da Mudança")
    dados_anteriores = models.JSONField(
        null=True, blank=True, verbose_name="Dados Anteriores"
    )
    dados_novos = models.JSONField(
        verbose_name="Dados Novos"
    )
    data_mudanca = models.DateField(auto_now_add=True, verbose_name="Data da Mudança")
    data_efetiva = models.DateField(verbose_name="Data Efetiva", null=True, blank=True)
    registrado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mudancas_colaborador_registradas",
        verbose_name="Registrado por"
    )
    aprovado = models.BooleanField(default=False, verbose_name="Aprovado")
    aprovado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mudancas_colaborador_aprovadas",
        verbose_name="Aprovado por"
    )
    data_aprovacao = models.DateTimeField(null=True, blank=True, verbose_name="Data de Aprovação")

    def __str__(self):
        return f"{self.colaborador.nome_completo} - {self.get_tipo_mudanca_display()} ({self.data_mudanca})"

    class Meta:
        verbose_name = "Histórico de Colaborador"
        verbose_name_plural = "Histórico Geral de Colaboradores"
        ordering = ["-data_mudanca"]


class MotivoPlanejamento(models.Model):
    TIPO_CHOICES = [
        ('HORA_EXTRA', 'Hora Extra'),
        ('FOLGA', 'Folga Planejada'),
        ('AMBOS', 'Ambos'),
    ]
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome do Motivo")
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='AMBOS',
        verbose_name="Categoria/Tipo"
    )

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"

    class Meta:
        verbose_name = "Motivo de Planejamento"
        verbose_name_plural = "Motivos de Planejamento"
        ordering = ["nome"]

class PlanejamentoHoraExtra(models.Model):
    TIPO_CHOICES = [
        ('HORA_EXTRA', 'Hora Extra'),
        ('FOLGA', 'Folga Planejada'),
    ]
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='HORA_EXTRA',
        verbose_name="Tipo de Registro"
    )
    data = models.DateField(verbose_name="Data do Planejamento", null=True, blank=True)
    motivos = models.ManyToManyField(
        MotivoPlanejamento,
        blank=True,
        related_name="planejamentos",
        verbose_name="Motivos Categorizados"
    )
    motivo = models.CharField(max_length=255, verbose_name="Motivo")
    horas_extras = models.DurationField(verbose_name="Horas Extras", null=True, blank=True)
    data_hora_inicio = models.DateTimeField(verbose_name="Início", null=True, blank=True)
    data_hora_fim = models.DateTimeField(verbose_name="Fim", null=True, blank=True)
    colaboradores = models.ManyToManyField(
        Colaborador,
        related_name="planejamentos_hora_extra",
        verbose_name="Colaboradores convocados"
    )
    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Criado por"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Planejamento (Hora Extra / Folga)"
        verbose_name_plural = "Planejamentos (Horas Extras e Absenteísmo)"
        ordering = ["-data", "-id"]

    def save(self, *args, **kwargs):
        if self.data_hora_inicio and self.data_hora_fim:
            self.horas_extras = self.data_hora_fim - self.data_hora_inicio
            self.data = self.data_hora_inicio.date()
        super().save(*args, **kwargs)

    def __str__(self):
        data_str = self.data.strftime('%d/%m/%Y') if self.data else 'Sem Data'
        tipo_str = dict(self.TIPO_CHOICES).get(self.tipo, self.tipo)
        return f"Planejamento #{self.id} [{tipo_str}] - {data_str} ({self.motivo})"

    @property
    def duracao(self):
        """Return the duration of the extra hours (horas_extras)."""
        return self.horas_extras

    @property
    def total_hh(self):
        """Return total HH considering duration multiplied by number of collaborators."""
        if not self.horas_extras:
            return None
        return self.horas_extras * self.colaboradores.count()




