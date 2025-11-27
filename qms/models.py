from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone
import uuid

# ==============================================================================
# CONSTANTES E OPÇÕES GERAIS
# ==============================================================================
STATUS_CHOICES = [("ATIVO", "Ativo"), ("INATIVO", "Inativo"), ("INSS", "Afastado INSS")]
TURNOS_CHOICES = [
    ("ADM", "Administrativo"),
    ("TURNO_1", "Turno 1"),
    ("TURNO_2", "Turno 2"),
    ("TURNO_3", "Turno 3"),
    ("12X36", "12x36"),
]


# ==============================================================================
# MÓDULO 0: ESTRUTURA ORGANIZACIONAL
# ==============================================================================
class Setor(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome do Setor")
    responsavel = models.CharField(
        max_length=100, null=True, blank=True, verbose_name="Responsável Genérico"
    )

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Setor"
        verbose_name_plural = "0.1 Cadastro de Setores"
        ordering = ["nome"]


class CentroCusto(models.Model):
    setor = models.ForeignKey(
        Setor,
        on_delete=models.CASCADE,
        related_name="centros_custo",
        verbose_name="Setor Pertencente",
    )
    codigo = models.CharField(max_length=20, verbose_name="Código")
    descricao = models.CharField(
        max_length=100, null=True, blank=True, verbose_name="Descrição"
    )

    def __str__(self):
        return f"{self.codigo} - {self.descricao or self.setor.nome}"

    class Meta:
        verbose_name = "Centro de Custo"
        verbose_name_plural = "0.2 Centros de Custo"
        unique_together = ("setor", "codigo")


# ==============================================================================
# MÓDULO 1: RECURSOS HUMANOS (COLABORADORES)
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

    pacotes_treinamento = models.ManyToManyField(
        "PacoteTreinamento",
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
        except HierarquiaSetor.DoesNotExist:
            return None

    def __str__(self):
        return f"{self.nome_completo} ({self.matricula})"

    class Meta:
        verbose_name = "Colaborador"
        verbose_name_plural = "1. Colaboradores (RH)"


class HierarquiaSetor(models.Model):
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
        verbose_name_plural = "1.1 Hierarquia (Setor x Turno)"
        unique_together = ("setor", "turno")


class Ferias(models.Model):
    # ... seus campos existentes ...
    colaborador = models.ForeignKey(
        Colaborador, on_delete=models.CASCADE, related_name="ferias_set"
    )  # (Verifique se o related_name está assim ou padrão)
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
    c = instance.colaborador
    h = date.today()
    em = c.historico_ferias.filter(data_inicio__lte=h, data_fim__gte=h).exists()
    if c.em_ferias != em:
        c.em_ferias = em
        c.save()


class Ocorrencia(models.Model):
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
        verbose_name_plural = "1.3 Ocorrências"


class DocumentoPessoal(models.Model):
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


# ==============================================================================
# MÓDULO 3: RASTREABILIDADE (PADRÕES DE REFERÊNCIA) - NOVO!
# ==============================================================================
class Padrao(models.Model):
    codigo = models.CharField(
        max_length=50, unique=True, verbose_name="Código do Padrão"
    )
    descricao = models.CharField(max_length=200, verbose_name="Descrição")
    fabricante = models.CharField(max_length=100, null=True, blank=True)
    numero_certificado = models.CharField(max_length=100, verbose_name="Nº Certificado")

    data_calibracao = models.DateField(verbose_name="Data Calib.")
    data_validade = models.DateField(verbose_name="Validade do Padrão")

    certificado = models.FileField(
        upload_to="padroes/", null=True, blank=True, verbose_name="PDF do Certificado"
    )
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.codigo} - {self.descricao} (Val: {self.data_validade})"

    @property
    def esta_vencido(self):
        return self.data_validade < date.today()

    class Meta:
        verbose_name = "Padrão / Kit"
        verbose_name_plural = "3. Padrões de Rastreabilidade"


# ==============================================================================
# MÓDULO 2: METROLOGIA (INSTRUMENTOS E CALIBRAÇÃO)
# ==============================================================================


class UnidadeMedida(models.Model):
    nome = models.CharField(max_length=50)
    sigla = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.nome} ({self.sigla})"

    class Meta:
        verbose_name_plural = "2.1 Unidades de Medida"


class CategoriaInstrumento(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    unidade_padrao = models.ForeignKey(
        'UnidadeMedida', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Unidade Padrão'
    )

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name_plural = "2.2 Categorias de Instrumentos"


# --- 1. Solicitação de Instrumentos ---
class SolicitacaoInstrumento(models.Model):
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
    # Instrumento é opcional pois pode ser uma solicitação de algo que ainda não existe
    instrumento_alvo = models.ForeignKey(
        "Instrumento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Preencher caso seja substituição de um item existente",
    )
    motivo = models.TextField(
        help_text="Descreva a necessidade da aplicação ou o motivo da troca", default=""
    )
    data_solicitacao = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDENTE")
    resposta_qualidade = models.TextField(
        blank=True, null=True, help_text="Parecer do setor de qualidade"
    )

    def __str__(self):
        return (
            f"{self.get_tipo_display()} - {self.solicitante.username} - {self.status}"
        )


# --- 2. Registro de Ocorrências ---
class OcorrenciaInstrumento(models.Model):
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
        "Instrumento",
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
        return (
            f"{self.instrumento} - {self.get_tipo_display()} ({self.data_ocorrencia})"
        )


# --- 3. Controle de Calibração (Rastreio) ---
class OrdemCalibracao(models.Model):
    LOCAL_CHOICES = [
        ("EXTERNO", "Laboratório Externo"),
        ("IN_LOCO", "Calibração In Loco (Na Empresa)"),
    ]
    STATUS_CALIBRACAO = [
        ("AGENDADO", "Agendado"),
        ("ENVIADO", "Enviado ao Fornecedor"),  # Apenas para externo
        ("EM_CALIBRACAO", "Em Calibração"),
        ("RETORNOU", "Retornou do Fornecedor"),  # Apenas para externo
        ("FINALIZADO", "Finalizado e Aprovado"),
    ]

    instrumento = models.ForeignKey(
        "Instrumento",
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

    # Datas de Rastreio
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

    # Validação simples para saber se está fora da empresa
    @property
    def esta_fora(self):
        return self.tipo_local == "EXTERNO" and self.status == "ENVIADO"


class Instrumento(models.Model):
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

    class Meta:
        verbose_name = "Instrumento"
        verbose_name_plural = "2. Instrumentos"

    def __str__(self):
        return f"{self.tag} - {self.descricao}"


class ImportJob(models.Model):
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


class FaixaMedicao(models.Model):
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
        verbose_name_plural = "2.3 Faixas de Medição"


class HistoricoCalibracao(models.Model):
    instrumento = models.ForeignKey(
        Instrumento,
        on_delete=models.CASCADE,
        related_name="historico_calibracoes",
        null=True,
        blank=True,
    )

    data_calibracao = models.DateField()
    data_aprovacao = models.DateField(default=date.today)
    numero_certificado = models.CharField(max_length=100, default="S/N")

    # --- RASTREABILIDADE ---
    tem_selo_rbc = models.BooleanField(default=False, verbose_name="Possui Selo RBC?")
    padroes_utilizados = models.ManyToManyField(
        Padrao, blank=True, verbose_name="Padrões Utilizados (Kits)"
    )

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

    # DADOS MATEMÁTICOS
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

    RESULTADO_CHOICES = [
        ("APROVADO", "Aprovado sem correções"),
        ("CONDICIONAL", "Aprovado com correções"),
        ("REPROVADO", "Reprovado"),
    ]
    resultado = models.CharField(
        max_length=50, choices=RESULTADO_CHOICES, default="APROVADO"
    )

    observacoes = models.TextField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Histórico de Calibração"
        verbose_name_plural = "4. Histórico de Calibrações"
        ordering = ["-data_calibracao"]
        unique_together = (
            "instrumento",
            "data_calibracao",
            "data_aprovacao",
            "numero_certificado",
        )

    def __str__(self):
        return f"{self.instrumento.tag} - {self.data_calibracao}"

    # Propriedade para alertas visuais
    @property
    def pendencia_rastreabilidade(self):
        # Se NÃO é RBC e NÃO tem padrões vinculados -> Alerta!
        if not self.tem_selo_rbc and not self.padroes_utilizados.exists():
            return True
        return False

    def save(self, *args, **kwargs):
        # CÁLCULO AUTOMÁTICO
        if (
            self.erro_encontrado is not None
            and self.incerteza is not None
            and self.tolerancia_usada is not None
        ):
            try:
                erro = abs(Decimal(str(self.erro_encontrado)))
                inc = abs(Decimal(str(self.incerteza)))
                tol = abs(Decimal(str(self.tolerancia_usada)))
                ema = tol / Decimal(2)
                eme = erro + inc
                if eme <= ema:
                    self.resultado = "APROVADO"
                elif eme > (ema * Decimal(3)):
                    self.resultado = "REPROVADO"
                else:
                    self.resultado = "CONDICIONAL"
            except:
                pass
        super().save(*args, **kwargs)


@receiver([post_save, post_delete], sender=HistoricoCalibracao)
def atualizar_datas_instrumento(sender, instance, **kwargs):
    inst = instance.instrumento
    ultima_calib = inst.historico_calibracoes.order_by("-data_calibracao").first()
    if ultima_calib:
        inst.data_ultima_calibracao = ultima_calib.data_calibracao
        inst.data_proxima_calibracao = ultima_calib.proxima_calibracao
    else:
        inst.data_ultima_calibracao = None
        inst.data_proxima_calibracao = None
    inst.save()


# ==============================================================================
# MÓDULO 5: SUPRIMENTOS (FORNECEDORES)
# ==============================================================================
class Fornecedor(models.Model):
    STATUS = [
        ("HOMOLOGADO", "Homologado"),
        ("BLOQUEADO", "Bloqueado"),
        ("EM_ANALISE", "Em Análise"),
    ]
    nome_fantasia = models.CharField(max_length=100)
    razao_social = models.CharField(max_length=150, null=True, blank=True)
    cnpj = models.CharField(max_length=20, unique=True)
    contato = models.CharField(max_length=100)
    email = models.EmailField()
    telefone = models.CharField(max_length=20)
    escopo_servico = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS, default="EM_ANALISE")
    nota_media = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)

    def __str__(self):
        return f"{self.nome_fantasia}"

    class Meta:
        verbose_name_plural = "5. Fornecedores"


class AvaliacaoFornecedor(models.Model):
    fornecedor = models.ForeignKey(
        Fornecedor, on_delete=models.CASCADE, related_name="avaliacoes"
    )
    data_avaliacao = models.DateField(auto_now_add=True)
    avaliador = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True)
    nota_tecnica = models.IntegerField(default=10)
    nota_pontualidade = models.IntegerField(default=10)
    nota_atendimento = models.IntegerField(default=10)
    observacao = models.TextField(null=True, blank=True)

    def media(self):
        return round(
            (self.nota_tecnica + self.nota_pontualidade + self.nota_atendimento) / 3, 1
        )


@receiver(post_save, sender="qms.AvaliacaoFornecedor")
def update_fornecedor_score(sender, instance, **kwargs):
    f = instance.fornecedor
    avgs = f.avaliacoes.all()
    if avgs:
        f.nota_media = round(sum([a.media() for a in avgs]) / len(avgs), 1)
    f.save()


class ProcessoCotacao(models.Model):
    STATUS = [("ABERTO", "Aberto"), ("FECHADO", "Fechado"), ("CANCELADO", "Cancelado")]
    titulo = models.CharField(max_length=100)
    data_abertura = models.DateField(auto_now_add=True)
    prazo_limite = models.DateField()
    instrumentos = models.ManyToManyField(Instrumento)
    status = models.CharField(max_length=20, choices=STATUS, default="ABERTO")
    responsavel = models.ForeignKey(Colaborador, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.titulo} ({self.status})"

    class Meta:
        verbose_name_plural = "6. Processos de Cotação"


class Orcamento(models.Model):
    processo = models.ForeignKey(
        ProcessoCotacao, on_delete=models.CASCADE, related_name="orcamentos"
    )
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2)
    prazo_execucao_dias = models.IntegerField()
    arquivo_proposta = models.FileField(upload_to="orcamentos/")
    vencedor = models.BooleanField(default=False)
    observacoes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"R$ {self.valor_total} - {self.fornecedor}"


# ==============================================================================
# MÓDULO 7: DOCUMENTOS E TREINAMENTOS
# ==============================================================================
class Procedimento(models.Model):
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código")
    titulo = models.CharField(max_length=200, verbose_name="Título")
    revisao_atual = models.CharField(max_length=10, verbose_name="Revisão Atual")
    data_revisao = models.DateField(verbose_name="Data Rev.", null=True, blank=True)
    setor = models.ForeignKey(
        Setor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Setor Aplicável",
    )
    prioridade = models.CharField(max_length=50, null=True, blank=True)
    habilidade_vinculada = models.CharField(max_length=100, null=True, blank=True)
    tem_copia_fisica = models.BooleanField(default=False)
    aplica_treinamento = models.BooleanField(default=False)
    link_externo = models.URLField(null=True, blank=True)

    def save(self, *args, **kwargs):
        self.codigo = self.codigo.upper().strip()
        self.titulo = self.titulo.upper().strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} - {self.titulo}"

    class Meta:
        verbose_name = "Procedimento"
        verbose_name_plural = "7.1 Procedimentos (GED)"
        ordering = ["codigo"]


class PacoteTreinamento(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome do Pacote")
    descricao = models.TextField(null=True, blank=True, verbose_name="Descrição")
    procedimentos = models.ManyToManyField(
        Procedimento, verbose_name="Procedimentos Incluídos", related_name="pacotes"
    )

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Pacote de Treinamento"
        verbose_name_plural = "7.3 Pacotes de Treinamento"


class RegistroTreinamento(models.Model):
    colaborador = models.ForeignKey(
        Colaborador, on_delete=models.CASCADE, related_name="treinamentos"
    )
    procedimento = models.ForeignKey(
        Procedimento, on_delete=models.CASCADE, related_name="registros_treinamento"
    )
    revisao_treinada = models.CharField(max_length=10)
    data_treinamento = models.DateField()
    validade_treinamento = models.DateField(null=True, blank=True)
    observacoes = models.TextField(null=True, blank=True)

    @property
    def status_treinamento(self):
        if (
            str(self.revisao_treinada).strip()
            == str(self.procedimento.revisao_atual).strip()
        ):
            return "VIGENTE"
        return "PENDENTE"

    class Meta:
        verbose_name_plural = "7.2 Matriz de Treinamentos"
        unique_together = ("colaborador", "procedimento")


@receiver(m2m_changed, sender=Colaborador.pacotes_treinamento.through)
def aplicar_pacotes_treinamento(sender, instance, action, pk_set, **kwargs):
    if action == "post_add":
        pacotes = PacoteTreinamento.objects.filter(pk__in=pk_set)
        for pacote in pacotes:
            for proc in pacote.procedimentos.all():
                if not getattr(proc, "aplica_treinamento", False):
                    continue
                RegistroTreinamento.objects.get_or_create(
                    colaborador=instance,
                    procedimento=proc,
                    defaults={
                        "revisao_treinada": "PENDENTE",
                        "data_treinamento": date.today(),
                    },
                )
