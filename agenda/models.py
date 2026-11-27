from django.conf import settings
from django.db import models
from django.db.models import Q


class Checklist(models.Model):
    """Modelo de checklist (lista de itens) criado direto pelo usuário e associável a eventos/rotinas da Agenda."""

    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agenda_checklists")
    # --- Checklist diário (independe de eventos) ---
    diario = models.BooleanField(
        default=False, help_text="Aparece todo dia (nos dias escolhidos) no Checklist do dia, sem precisar de evento."
    )
    dias_semana = models.CharField(
        max_length=13, default="0,1,2,3,4,5,6", help_text="Dias da semana (0=segunda ... 6=domingo), separados por vírgula."
    )
    PER_DIARIA, PER_SEMANAL, PER_QUINZENAL = "diaria", "semanal", "quinzenal"
    PER_MENSAL, PER_BIMESTRAL, PER_TRIMESTRAL = "mensal", "bimestral", "trimestral"
    PER_SEMESTRAL, PER_ANUAL = "semestral", "anual"
    # intervalo livre: "a cada N" dias/semanas/meses/anos (N em `intervalo`)
    PER_CADA_DIAS, PER_CADA_SEMANAS = "cada_dias", "cada_semanas"
    PER_CADA_MESES, PER_CADA_ANOS = "cada_meses", "cada_anos"
    PERIODICIDADES = [
        (PER_DIARIA, "Diária (dias da semana)"),
        (PER_SEMANAL, "Semanal"),
        (PER_QUINZENAL, "Quinzenal (a cada 2 semanas)"),
        (PER_MENSAL, "Mensal"),
        (PER_BIMESTRAL, "Bimestral"),
        (PER_TRIMESTRAL, "Trimestral"),
        (PER_SEMESTRAL, "Semestral"),
        (PER_ANUAL, "Anual"),
        (PER_CADA_DIAS, "A cada N dias"),
        (PER_CADA_SEMANAS, "A cada N semanas (nos dias marcados)"),
        (PER_CADA_MESES, "A cada N meses (no dia do mês)"),
        (PER_CADA_ANOS, "A cada N anos (no dia do mês)"),
    ]
    # N máximo de cada periodicidade de intervalo livre
    LIMITE_INTERVALO = {PER_CADA_DIAS: 365, PER_CADA_SEMANAS: 52, PER_CADA_MESES: 60, PER_CADA_ANOS: 20}
    # meses entre ocorrências nas periodicidades por dia do mês
    MESES_PASSO = {PER_MENSAL: 1, PER_BIMESTRAL: 2, PER_TRIMESTRAL: 3, PER_SEMESTRAL: 6, PER_ANUAL: 12}
    periodicidade = models.CharField(max_length=20, choices=PERIODICIDADES, default=PER_DIARIA)
    intervalo = models.PositiveSmallIntegerField(
        default=1, help_text="N das periodicidades 'a cada N dias/semanas/meses/anos'."
    )
    dia_mes = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Dia do mês (1-31) das periodicidades mensal ou maior; meses curtos usam o último dia."
    )
    hora = models.TimeField(null=True, blank=True, help_text="Horário de referência (opcional).")
    na_agenda = models.BooleanField(default=False, help_text="Mostra o checklist no calendário como atividade fixa.")
    cor = models.CharField(max_length=7, default="#20c997")
    diario_desde = models.DateField(null=True, blank=True, help_text="Primeiro dia em que o checklist diário vale.")
    incluir_dono = models.BooleanField(
        default=True,
        help_text="Se desmarcado, o dono só distribui o checklist aos liderados e não o preenche.",
    )
    ajustado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Chefia que criou ou ajustou este checklist em nome do dono (vazio = o próprio dono).",
    )
    ajustado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["titulo"]

    def __str__(self):
        return self.titulo

    def pode_editar(self, user):
        """O dono, o superusuário ou a chefia (líder, vice-líder, supervisor, gerente) do dono."""
        from agenda.hierarquia import pode_gerir

        return pode_gerir(user, self.criado_por)

    @property
    def itens_vigentes(self):
        """Itens do cadastro padrão que valem hoje (sem os avulsos e sem os já removidos)."""
        from django.utils import timezone

        hoje = timezone.localdate()
        return [i for i in self.itens.all() if not i.avulso and i.vale_em(hoje)]

    @property
    def periodicidade_label(self):
        return dict(self.PERIODICIDADES).get(self.periodicidade, "Diária").split(" (")[0]

    @classmethod
    def por_mes(cls, periodicidade):
        """Periodicidades que valem num dia do mês (mensal ou maior e 'a cada N meses/anos')."""
        return periodicidade in cls.MESES_PASSO or periodicidade in (cls.PER_CADA_MESES, cls.PER_CADA_ANOS)

    @classmethod
    def usa_dias_semana(cls, periodicidade):
        return periodicidade in (cls.PER_DIARIA, cls.PER_SEMANAL, cls.PER_QUINZENAL, cls.PER_CADA_SEMANAS)

    @property
    def passo_meses(self):
        """Meses entre ocorrências nas periodicidades por dia do mês (None nas demais)."""
        if self.periodicidade == self.PER_CADA_MESES:
            return self.intervalo
        if self.periodicidade == self.PER_CADA_ANOS:
            return 12 * self.intervalo
        return self.MESES_PASSO.get(self.periodicidade)

    @property
    def frequencia_texto(self):
        """Texto da periodicidade para as telas: "Mensal · dia 5", "A cada 15 dias", "A cada 3 meses · dia 10"."""
        n, per = self.intervalo, self.periodicidade
        if per == self.PER_CADA_DIAS:
            return f"A cada {n} dias" if n > 1 else "Diária"
        if per == self.PER_CADA_SEMANAS:
            return f"A cada {n} semanas" if n > 1 else "Semanal"
        if per == self.PER_CADA_MESES:
            base = f"A cada {n} meses" if n > 1 else "Mensal"
        elif per == self.PER_CADA_ANOS:
            base = f"A cada {n} anos" if n > 1 else "Anual"
        else:
            base = self.periodicidade_label
        return f"{base} · dia {self.dia_mes}" if self.dia_mes else base

    @property
    def dias_set(self):
        return {int(x) for x in self.dias_semana.split(",") if x.strip().isdigit() and 0 <= int(x) <= 6}


class ChecklistItem(models.Model):
    checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name="itens")
    texto = models.CharField(max_length=300)
    grupo = models.CharField(max_length=120, blank=True, default="", help_text="Agrupamento do item (vazio = sem agrupamento).")
    ordem = models.PositiveIntegerField(default=0)
    valido_desde = models.DateField(
        null=True, blank=True, help_text="Primeiro dia em que o item vale (vazio = desde sempre). Itens inseridos valem da data da mudança."
    )
    valido_ate = models.DateField(
        null=True, blank=True, help_text="Último dia em que o item vale (vazio = sem fim). Itens removidos valem até o dia anterior à mudança."
    )
    avulso = models.BooleanField(
        default=False, help_text="Item não fixo, adicionado para um dia (ou período) no Meu checklist; fora do cadastro padrão."
    )

    class Meta:
        ordering = ["ordem", "id"]

    def __str__(self):
        return self.texto

    def vale_em(self, dia):
        """True se o item vale em `dia` (inserções e remoções contam a partir da data da mudança)."""
        return (self.valido_desde is None or dia >= self.valido_desde) and (self.valido_ate is None or dia <= self.valido_ate)


class Evento(models.Model):
    ESCOPO_PESSOAL = "pessoal"
    ESCOPO_COMUM = "comum"
    ESCOPOS = [(ESCOPO_PESSOAL, "Pessoal"), (ESCOPO_COMUM, "Comum")]

    REC_NENHUMA = "nenhuma"
    REC_DIARIA = "diaria"
    REC_SEMANAL = "semanal"
    REC_MENSAL = "mensal"
    RECORRENCIAS = [
        (REC_NENHUMA, "Não repete"),
        (REC_DIARIA, "Todos os dias"),
        (REC_SEMANAL, "Toda semana"),
        (REC_MENSAL, "Todo mês"),
    ]

    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    local = models.CharField(max_length=200, blank=True)
    escopo = models.CharField(max_length=10, choices=ESCOPOS, default=ESCOPO_PESSOAL)
    inicio = models.DateTimeField()
    fim = models.DateTimeField(null=True, blank=True)
    dia_inteiro = models.BooleanField(default=False)
    recorrencia = models.CharField(max_length=10, choices=RECORRENCIAS, default=REC_NENHUMA)
    recorrencia_ate = models.DateField(null=True, blank=True)
    checklist = models.BooleanField(
        default=False, help_text="Aparece no checklist diário e pode ser marcado como feito em cada dia."
    )
    checklist_modelo = models.ForeignKey(
        Checklist,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="eventos",
        help_text="Checklist cujos itens aparecem no checklist diário em cada ocorrência deste evento.",
    )
    lembrete_minutos = models.PositiveIntegerField(
        null=True, blank=True, help_text="Avisar este número de minutos antes do início (nas notificações)."
    )
    cor = models.CharField(max_length=7, default="#0d6efd")
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agenda_eventos")
    ajustado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Chefia que criou ou ajustou este evento em nome do dono (vazio = o próprio dono).",
    )
    ajustado_em = models.DateTimeField(null=True, blank=True)
    participantes = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through="EventoParticipante", related_name="agenda_convites", blank=True
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["inicio"]
        indexes = [models.Index(fields=["inicio"]), models.Index(fields=["escopo"])]

    def __str__(self):
        return self.titulo

    @classmethod
    def visiveis_para(cls, user):
        """Eventos comuns (todos), os próprios e aqueles em que o usuário foi convidado."""
        return cls.objects.filter(
            Q(escopo=cls.ESCOPO_COMUM) | Q(criado_por=user) | Q(participantes=user)
        ).distinct()

    def pode_editar(self, user):
        """O criador, o superusuário ou a chefia (líder, vice-líder, supervisor, gerente) do criador."""
        from agenda.hierarquia import pode_gerir

        return pode_gerir(user, self.criado_por)


class EventoParticipante(models.Model):
    PENDENTE = "pendente"
    ACEITO = "aceito"
    RECUSADO = "recusado"
    RESPOSTAS = [(PENDENTE, "Pendente"), (ACEITO, "Aceito"), (RECUSADO, "Recusado")]

    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="convites")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agenda_participacoes")
    resposta = models.CharField(max_length=10, choices=RESPOSTAS, default=PENDENTE)

    class Meta:
        unique_together = [("evento", "usuario")]


class EventoConclusao(models.Model):
    """Marca, por usuário e por dia, que uma ocorrência de item de checklist foi feita."""

    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="conclusoes")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agenda_conclusoes")
    data = models.DateField()
    concluido_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("evento", "usuario", "data")]


class ItemConclusao(models.Model):
    """Item de um checklist associado, marcado como feito por um usuário numa ocorrência (dia) do evento."""

    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="itens_concluidos")
    item = models.ForeignKey(ChecklistItem, on_delete=models.CASCADE, related_name="conclusoes")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agenda_itens_concluidos")
    data = models.DateField()
    concluido_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("evento", "item", "usuario", "data")]


class ChecklistDiarioConclusao(models.Model):
    """Item de um checklist diário marcado como feito por um usuário num dia (independe de evento)."""

    item = models.ForeignKey(ChecklistItem, on_delete=models.CASCADE, related_name="conclusoes_diarias")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agenda_diario_concluidos"
    )
    data = models.DateField()
    concluido_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("item", "usuario", "data")]


class ChecklistCompartilhamento(models.Model):
    """Checklist diário enviado a um colaborador: ele preenche a sua própria folha (marcações por usuário e dia)."""

    checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name="compartilhamentos")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agenda_checklists_recebidos"
    )
    desde = models.DateField(help_text="Primeiro dia da folha do colaborador (não gera pendência retroativa).")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("checklist", "usuario")]


# ----------------------------------------------------------------------------------------------
# Checklists compartilhados: tarefas com responsável e prazo, estado único para o grupo, com cobrança
# ----------------------------------------------------------------------------------------------
class ChecklistCompartilhado(models.Model):
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    cor = models.CharField(max_length=7, default="#6f42c1")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agenda_compartilhados_criados"
    )
    arquivado = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["arquivado", "titulo"]

    def __str__(self):
        return self.titulo

    @classmethod
    def visiveis_para(cls, user):
        """Os de que o usuário é membro, os que criou e (chefia/superusuário) os dos seus liderados."""
        from agenda.hierarquia import liderados_ids

        if user.is_superuser:
            return cls.objects.all()
        return cls.objects.filter(
            models.Q(membros__usuario=user) | models.Q(criado_por=user) | models.Q(criado_por_id__in=liderados_ids(user))
        ).distinct()

    def pode_editar(self, user):
        """Quem criou, o superusuário ou a chefia de quem criou (muda título, membros e tarefas)."""
        from agenda.hierarquia import pode_gerir

        return pode_gerir(user, self.criado_por)

    def eh_membro(self, user):
        return self.membros.filter(usuario=user).exists()


class CompartilhadoMembro(models.Model):
    lista = models.ForeignKey(ChecklistCompartilhado, on_delete=models.CASCADE, related_name="membros")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agenda_compartilhados"
    )

    class Meta:
        unique_together = [("lista", "usuario")]


class CompartilhadoTarefa(models.Model):
    lista = models.ForeignKey(ChecklistCompartilhado, on_delete=models.CASCADE, related_name="tarefas")
    texto = models.CharField(max_length=300)
    grupo = models.CharField(max_length=120, blank=True, default="", help_text="Agrupamento do item (vazio = sem agrupamento).")
    ordem = models.PositiveIntegerField(default=0)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="agenda_tarefas"
    )
    prazo = models.DateField(null=True, blank=True)
    concluida = models.BooleanField(default=False)
    concluida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    concluida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["ordem", "id"]

    def __str__(self):
        return self.texto

    def atrasada(self, hoje):
        return (not self.concluida) and self.prazo is not None and self.prazo < hoje


class CompartilhadoCobranca(models.Model):
    """Lembrete que um membro mandou ao responsável de uma tarefa pendente (aparece no sino dele)."""

    tarefa = models.ForeignKey(CompartilhadoTarefa, on_delete=models.CASCADE, related_name="cobrancas")
    de = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    para = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agenda_cobrancas")
    criado_em = models.DateTimeField(auto_now_add=True)
    lida = models.BooleanField(default=False)

    class Meta:
        ordering = ["-criado_em"]


class ChecklistGrupo(models.Model):
    """Condição especial de um agrupamento (itens com o mesmo `grupo`): só aparece nos dias em que a regra vale.

    Existe só para agrupamentos com condição; agrupamentos sem registro aparecem em todas as ocorrências.
    """

    checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name="grupos")
    nome = models.CharField(max_length=120)
    regra = models.JSONField(default=dict, help_text="Veja agenda.regras.")

    class Meta:
        unique_together = [("checklist", "nome")]


# ----------------------------------------------------------------------------------------------
# Comentários e ocorrências no preenchimento do checklist
# ----------------------------------------------------------------------------------------------
class OcorrenciaChecklist(models.Model):
    """Ocorrência aberta a partir de um item do checklist (aparece na Central de Ocorrências, origem "Agenda")."""

    ABERTA = "aberta"
    ENCERRADA = "encerrada"
    STATUS = [(ABERTA, "Aberta"), (ENCERRADA, "Encerrada")]

    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default=ABERTA)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agenda_ocorrencias")
    criado_em = models.DateTimeField(auto_now_add=True)
    data = models.DateField(help_text="Dia do checklist em que a ocorrência aconteceu.")
    # origem (a ligação some se o item for apagado; os textos abaixo guardam o contexto)
    checklist_titulo = models.CharField(max_length=200, blank=True)
    item_texto = models.CharField(max_length=300, blank=True)
    item = models.ForeignKey(ChecklistItem, null=True, blank=True, on_delete=models.SET_NULL, related_name="ocorrencias")
    tarefa = models.ForeignKey(CompartilhadoTarefa, null=True, blank=True, on_delete=models.SET_NULL, related_name="ocorrencias")
    evento = models.ForeignKey(Evento, null=True, blank=True, on_delete=models.SET_NULL, related_name="ocorrencias_checklist")
    resolucao = models.TextField(blank=True)
    encerrada_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    encerrada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["criado_por", "data"])]

    def __str__(self):
        return self.titulo


class ComentarioChecklist(models.Model):
    """Comentário de quem preenche sobre um item numa data (da folha dele). Pode ser convertido em ocorrência."""

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agenda_comentarios")
    data = models.DateField(help_text="Dia do checklist a que o comentário se refere.")
    # a que o comentário se refere: um dos três
    item = models.ForeignKey(ChecklistItem, null=True, blank=True, on_delete=models.CASCADE, related_name="comentarios")
    tarefa = models.ForeignKey(CompartilhadoTarefa, null=True, blank=True, on_delete=models.CASCADE, related_name="comentarios")
    evento = models.ForeignKey(Evento, null=True, blank=True, on_delete=models.CASCADE, related_name="comentarios_checklist")
    texto = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)
    ocorrencia = models.ForeignKey(
        OcorrenciaChecklist, null=True, blank=True, on_delete=models.SET_NULL, related_name="comentarios",
        help_text="Preenchido quando o comentário foi convertido em ocorrência.",
    )

    class Meta:
        ordering = ["criado_em"]
        indexes = [models.Index(fields=["usuario", "data"])]
