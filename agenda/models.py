from django.conf import settings
from django.db import models
from django.db.models import Q


class Checklist(models.Model):
    """Modelo de checklist (lista de itens) criado direto pelo usuário e associável a eventos/rotinas da Agenda."""

    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agenda_checklists")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["titulo"]

    def __str__(self):
        return self.titulo

    def pode_editar(self, user):
        return user.is_superuser or self.criado_por_id == user.id


class ChecklistItem(models.Model):
    checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name="itens")
    texto = models.CharField(max_length=300)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordem", "id"]

    def __str__(self):
        return self.texto


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
        return user.is_superuser or self.criado_por_id == user.id


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
