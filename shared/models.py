from django.conf import settings
from django.db import models
from django.utils import timezone


class AcaoOcorrencia(models.Model):
    """Ação do plano de tratativa de uma ocorrência (de qualquer módulo), com responsável e prazo definidos.

    Uma ocorrência pode ter várias ações, cada uma com um ou mais responsáveis (qualquer um deles pode
    concluí-la). Ao redirecionar uma ação, ela é encerrada como REDIRECIONADA e
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
    responsaveis = models.ManyToManyField(
        "rh.Colaborador", blank=True, related_name="acoes_ocorrencia", verbose_name="Responsáveis",
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


class ComentarioAcao(models.Model):
    """Comentário de uma ação do plano: tratativas, dúvidas e respostas sobre a execução da ação."""
    acao = models.ForeignKey(AcaoOcorrencia, on_delete=models.CASCADE, related_name="comentarios")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    texto = models.TextField("Comentário")
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["criado_em", "id"]
        verbose_name = "Comentário de ação"
        verbose_name_plural = "Comentários de ações"

    def __str__(self):
        return f"{self.acao_id}: {self.texto[:40]}"


class ModeloApresentacao(models.Model):
    """Modelo de apresentação (playlist do telão) criado pelos usuários: quais módulos entram, em que ordem e por quanto tempo.

    `itens` é uma lista ordenada de {"provedor": "<chave em shared.telao.providers.PROVEDORES>", "duracao": segundos ou null}.
    Os modelos padrão (Geral, Qualidade...) ficam no código; estes são os personalizados.
    """
    nome = models.CharField("Nome", max_length=100)
    descricao = models.CharField("Descrição", max_length=200, blank=True)
    icone = models.CharField("Ícone", max_length=40, default="bi-display", help_text="Classe do Bootstrap Icons.")
    itens = models.JSONField("Conteúdo", default=list, blank=True)
    slides = models.JSONField("Slides", default=list, blank=True,
                              help_text="Formato com slides automáticos e manuais (ver shared.telao.layout). Se preenchido, vale no lugar de `itens`.")
    duracao_padrao = models.PositiveSmallIntegerField("Segundos por slide", default=15)
    resumo = models.BooleanField("Modo resumido", default=False,
                                 help_text="Oculta descrições e nomes de responsáveis (para telas em locais públicos).")
    TEMAS = [("escuro", "Escuro"), ("claro", "Claro")]
    tema = models.CharField("Tema dos slides", max_length=10, choices=TEMAS, default="escuro")
    compartilhada = models.BooleanField("Compartilhada", default=False,
                                        help_text="Aparece no menu de todos os usuários (cada um vê só o que tem permissão).")
    ativo = models.BooleanField("Ativo", default=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    criado_em = models.DateTimeField(default=timezone.now)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome", "id"]
        verbose_name = "Modelo de apresentação"
        verbose_name_plural = "Modelos de apresentação"

    def __str__(self):
        return self.nome

    @property
    def chave(self) -> str:
        return f"m{self.pk}"

    def visivel_para(self, user) -> bool:
        if not getattr(user, "is_authenticated", False) or not self.ativo:
            return False
        return bool(self.compartilhada or self.criado_por_id == user.pk or user.is_staff or user.is_superuser)

    def editavel_por(self, user) -> bool:
        return bool(getattr(user, "is_authenticated", False)
                    and (self.criado_por_id == user.pk or user.is_staff or user.is_superuser))


class FavoritoApresentacao(models.Model):
    """Apresentação marcada pelo usuário para o acesso rápido do menu (chave "m<id>" de um ModeloApresentacao)."""
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    modelo = models.ForeignKey(ModeloApresentacao, on_delete=models.CASCADE, related_name="favoritos")
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("usuario", "modelo")]
        ordering = ["criado_em", "id"]
        verbose_name = "Favorito de apresentação"
        verbose_name_plural = "Favoritos de apresentação"
