from django.conf import settings
from django.db import models
from django.utils import timezone


class AcaoOcorrencia(models.Model):
    """Ação do plano de tratativa de uma ocorrência (de qualquer módulo), com responsável e prazo definidos.

    Uma ocorrência pode ter várias ações. Ao redirecionar uma ação, ela é encerrada como REDIRECIONADA e
    nasce uma nova ação (ligada à anterior por `origem_acao`), de modo que o histórico de responsáveis e
    prazos fica preservado.
    """
    ABERTA, CONCLUIDA, REDIRECIONADA, CANCELADA = "ABERTA", "CONCLUIDA", "REDIRECIONADA", "CANCELADA"
    STATUS = [
        (ABERTA, "Em aberto"),
        (CONCLUIDA, "Concluída"),
        (REDIRECIONADA, "Redirecionada"),
        (CANCELADA, "Cancelada"),
    ]

    origem = models.CharField("Origem", max_length=20, db_index=True)
    ocorrencia_id = models.PositiveIntegerField("Ocorrência", db_index=True)
    descricao = models.TextField("Ação a realizar")
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="acoes_ocorrencia", verbose_name="Responsável",
    )
    prazo = models.DateField("Prazo", null=True, blank=True)
    status = models.CharField("Situação", max_length=14, choices=STATUS, default=ABERTA, db_index=True)
    resultado = models.TextField("Resultado / motivo", blank=True)
    origem_acao = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="redirecionamentos",
        verbose_name="Redirecionada de",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    criado_em = models.DateTimeField(default=timezone.now)
    encerrada_em = models.DateTimeField(null=True, blank=True)
    encerrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )

    class Meta:
        ordering = ["criado_em", "id"]
        indexes = [models.Index(fields=["origem", "ocorrencia_id"])]
        verbose_name = "Ação de ocorrência"
        verbose_name_plural = "Ações de ocorrências"

    def __str__(self):
        return f"{self.origem}:{self.ocorrencia_id} — {self.descricao[:40]}"

    @property
    def aberta(self) -> bool:
        return self.status == self.ABERTA
