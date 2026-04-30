from django.conf import settings
from django.db import models
from django.utils import timezone
import re
import unicodedata
import uuid


class ModeloAuditoria(models.Model):
    PERIODICIDADE_CHOICES = [
        ("UNICA", "Aplicação Única"),
        ("DIARIA", "Diária"),
        ("SEMANAL", "Semanal"),
        ("QUINZENAL", "Quinzenal"),
        ("MENSAL", "Mensal"),
        ("TRIMESTRAL", "Trimestral"),
        ("SEMESTRAL", "Semestral"),
        ("ANUAL", "Anual"),
    ]
    
    DIA_SEMANA_CHOICES = [
        ("SEGUNDA", "Segunda-feira"),
        ("TERCA", "Terça-feira"),
        ("QUARTA", "Quarta-feira"),
        ("QUINTA", "Quinta-feira"),
        ("SEXTA", "Sexta-feira"),
        ("SABADO", "Sábado"),
        ("DOMINGO", "Domingo"),
    ]

    nome = models.CharField(max_length=150, unique=True)
    objeto_auditoria = models.TextField(verbose_name="Objeto da Auditoria")
    link_sharepoint = models.URLField(blank=True, verbose_name="Link SharePoint")
    periodicidade = models.CharField(max_length=20, choices=PERIODICIDADE_CHOICES, default="MENSAL")
    
    # Campos de referência para periodicidade
    dia_semana = models.CharField(
        max_length=10, 
        choices=DIA_SEMANA_CHOICES, 
        blank=True, 
        null=True,
        verbose_name="Dia da Semana",
        help_text="Para periodicidade semanal"
    )
    dias_quinzenal = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name="Dias da Quinzena",
        help_text="Dois dias do mês separados por vírgula (ex: 1,16)"
    )
    dia_mes = models.IntegerField(
        blank=True,
        null=True,
        verbose_name="Dia do Mês",
        help_text="Dia do mês para execução (1-31)"
    )
    
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="modelos_auditoria_responsavel",
        verbose_name="Responsável pela Auditoria",
        help_text="Usuário responsável pela realização da auditoria"
    )

    responsaveis = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="modelos_auditoria_responsaveis",
        verbose_name="Responsáveis pela Auditoria",
        help_text="Usuários autorizados a preencher/atualizar auditorias deste modelo.",
    )

    preenchimento_grid = models.BooleanField(
        default=False,
        verbose_name="Preenchimento em GRID",
        help_text="Habilita preenchimento em tabela para repetir as mesmas perguntas por múltiplos itens/equipamentos/serviços.",
    )

    grid_rotulo_item = models.CharField(
        max_length=60,
        blank=True,
        default="Item",
        verbose_name="Rótulo do item (GRID)",
        help_text="Ex.: Equipamento, Serviço, Item, Ativo.",
    )

    grid_colunas = models.TextField(
        blank=True,
        default="",
        verbose_name="Colunas do GRID",
        help_text="Uma coluna por linha (ex.: EQP-001). Se vazio, as colunas serão informadas no registro.",
    )

    subcategorias = models.TextField(
        blank=True,
        default="",
        verbose_name="Sub-categorias",
        help_text="Uma sub-categoria por linha (ex.: Segurança, Qualidade, 5S).",
    )
    
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Modelo de Auditoria"
        verbose_name_plural = "Modelos de Auditoria"
        ordering = ["nome"]

    def __str__(self):
        return self.nome
    
    def get_periodicidade_completa(self):
        """Retorna descrição completa da periodicidade incluindo referências"""
        base = self.get_periodicidade_display()
        
        if self.periodicidade == 'SEMANAL' and self.dia_semana:
            dia_label = dict(self.DIA_SEMANA_CHOICES).get(self.dia_semana, self.dia_semana)
            return f"{base} ({dia_label})"
        elif self.periodicidade == 'QUINZENAL' and self.dias_quinzenal:
            return f"{base} (dias {self.dias_quinzenal})"
        elif self.periodicidade in ['MENSAL', 'TRIMESTRAL', 'SEMESTRAL', 'ANUAL'] and self.dia_mes:
            return f"{base} (dia {self.dia_mes})"
        
        return base

    @property
    def subcategorias_list(self) -> list[str]:
        raw = (self.subcategorias or "").replace("\r\n", "\n")
        parts = [p.strip() for p in raw.split("\n")]
        seen: set[str] = set()
        values: list[str] = []
        for p in parts:
            if not p:
                continue
            key = p.lower()
            if key in seen:
                continue
            seen.add(key)
            values.append(p)
        return values


class PerguntaAuditoria(models.Model):
    TIPO_RESPOSTA_CHOICES = [
        ("SIM_NAO", "Sim/Não"),
        ("LISTA", "Lista (opções)"),
        ("NUMERO", "Número inteiro"),
        ("DECIMAL", "Número decimal"),
    ]

    PREENCHIMENTO_SEMANAL_CHOICES = [
        ("UNICO", "Uma resposta (sem detalhar por dia)"),
        ("POR_DIA", "Responder para cada dia da semana"),
    ]

    modelo = models.ForeignKey(
        ModeloAuditoria,
        on_delete=models.CASCADE,
        related_name="perguntas",
        verbose_name="Modelo",
    )
    pergunta = models.CharField(max_length=255)
    descricao_detalhada = models.TextField(
        blank=True,
        default="",
        verbose_name="Descrição detalhada",
        help_text="Texto exibido no ícone informativo durante o preenchimento do registro.",
    )
    tipo_resposta = models.CharField(max_length=20, choices=TIPO_RESPOSTA_CHOICES, default="SIM_NAO")
    preenchimento_semanal = models.CharField(
        max_length=10,
        choices=PREENCHIMENTO_SEMANAL_CHOICES,
        default="UNICO",
        verbose_name="Preenchimento (semanal)",
        help_text="Apenas para modelos com periodicidade semanal.",
    )

    opcoes_resposta = models.TextField(
        blank=True,
        default="",
        verbose_name="Opções de resposta",
        help_text="Apenas para tipo 'Lista (opções)'. Use uma opção por linha.",
    )
    opcoes_resposta_cores = models.JSONField(
        blank=True,
        default=dict,
        verbose_name="Cores das opções",
        help_text="Mapa de cores por opção (hex), usado em tipo Lista e Sim/Não.",
    )

    aplicar_no_grid = models.BooleanField(
        default=True,
        verbose_name="Aplicar no GRID",
        help_text="Se marcado, esta pergunta aparece no preenchimento em GRID (quando habilitado no modelo).",
    )
    ordem = models.PositiveIntegerField(default=1)
    subcategoria = models.CharField(
        max_length=80,
        blank=True,
        default="",
        verbose_name="Sub-categoria",
        help_text="Opcional. Deve existir nas sub-categorias do modelo (quando definidas).",
    )
    obrigatoria = models.BooleanField(default=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Pergunta da Auditoria"
        verbose_name_plural = "Perguntas da Auditoria"
        ordering = ["modelo__nome", "ordem", "id"]

    def __str__(self):
        return f"{self.modelo.nome} - {self.pergunta}"

    @staticmethod
    def _normalize_option_key(value: str) -> str:
        s = str(value or "").strip().lower()
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        return re.sub(r"\s+", " ", s)

    @staticmethod
    def _is_hex_color(value: str) -> bool:
        return bool(re.fullmatch(r"#[0-9a-fA-F]{6}", str(value or "").strip()))

    def _default_color_for_label(self, label: str) -> str:
        key = self._normalize_option_key(label)
        if key in {"sim", "conforme"}:
            return "#198754"
        if key in {"nao", "nao conforme"}:
            return "#dc3545"
        return ""

    @property
    def opcoes_resposta_list(self) -> list[str]:
        raw = (self.opcoes_resposta or "").replace("\r\n", "\n")
        parts = [p.strip() for p in raw.split("\n")]
        seen: set[str] = set()
        values: list[str] = []
        for p in parts:
            if not p:
                continue
            key = p.lower()
            if key in seen:
                continue
            seen.add(key)
            values.append(p)
        return values

    @property
    def opcoes_resposta_cores_normalized(self) -> dict[str, str]:
        raw = self.opcoes_resposta_cores if isinstance(self.opcoes_resposta_cores, dict) else {}
        result: dict[str, str] = {}
        for key, value in raw.items():
            normalized_key = self._normalize_option_key(key)
            color = str(value or "").strip()
            if not normalized_key:
                continue
            if not self._is_hex_color(color):
                continue
            result[normalized_key] = color.lower()
        return result

    @property
    def opcoes_resposta_com_cores(self) -> list[dict[str, str]]:
        color_map = self.opcoes_resposta_cores_normalized
        options: list[dict[str, str]] = []
        for opt in self.opcoes_resposta_list:
            color = color_map.get(self._normalize_option_key(opt), "")
            if not color:
                color = self._default_color_for_label(opt)
            options.append({"label": opt, "color": color})
        return options

    def get_cor_resposta(self, valor: str) -> str:
        color_map = self.opcoes_resposta_cores_normalized
        key = self._normalize_option_key(valor)
        color = color_map.get(key, "")
        if color:
            return color
        return self._default_color_for_label(valor)


class RegistroAuditoria(models.Model):
    modelo = models.ForeignKey(
        ModeloAuditoria,
        on_delete=models.PROTECT,
        related_name="registros",
        verbose_name="Modelo",
    )
    data_auditoria = models.DateField(verbose_name="Data da Auditoria")
    periodo_inicio = models.DateField(verbose_name="Período Inicial")
    periodo_fim = models.DateField(verbose_name="Período Final")
    avaliador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auditorias_realizadas",
    )
    item_os = models.CharField(
        max_length=120,
        blank=True,
        default="",
        verbose_name="ITEM/O.S.",
        help_text="Preencher se necessário para identificar ordens de serviço ou pontos específicos.",
    )

    grid_itens = models.TextField(
        blank=True,
        default="",
        verbose_name="Itens (GRID)",
        help_text="Use uma linha por item/equipamento/serviço quando o modelo estiver em modo GRID.",
    )
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de Auditoria"
        verbose_name_plural = "Registros de Auditoria"
        ordering = ["-data_auditoria", "-id"]

    def __str__(self):
        return f"{self.modelo.nome} - {self.data_auditoria:%d/%m/%Y}"


class RespostaAuditoria(models.Model):
    registro = models.ForeignKey(
        RegistroAuditoria,
        on_delete=models.CASCADE,
        related_name="respostas",
    )
    pergunta = models.ForeignKey(
        PerguntaAuditoria,
        on_delete=models.PROTECT,
        related_name="respostas",
    )
    dia_semana = models.CharField(
        max_length=10,
        choices=ModeloAuditoria.DIA_SEMANA_CHOICES,
        blank=True,
        null=True,
        verbose_name="Dia da Semana",
        help_text="Usado quando a pergunta exige resposta por dia (auditoria semanal).",
    )
    grid_item = models.CharField(
        max_length=120,
        blank=True,
        default="",
        verbose_name="Item (GRID)",
        help_text="Identifica o item/equipamento/serviço quando o preenchimento é em GRID.",
    )
    valor = models.TextField(blank=True)

    class Meta:
        verbose_name = "Resposta de Auditoria"
        verbose_name_plural = "Respostas de Auditoria"
        ordering = ["registro", "pergunta__ordem", "dia_semana", "id"]
        unique_together = ("registro", "pergunta", "dia_semana", "grid_item")

    def __str__(self):
        return f"{self.registro} - {self.pergunta.pergunta[:60]}"


class ComentarioAuditoria(models.Model):
    modelo = models.ForeignKey(
        ModeloAuditoria,
        on_delete=models.CASCADE,
        related_name="comentarios",
        verbose_name="Modelo",
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auditoria_comentarios",
        verbose_name="Autor",
    )
    texto = models.TextField(verbose_name="Comentário")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Comentário de Auditoria"
        verbose_name_plural = "Comentários de Auditoria"
        ordering = ["-criado_em", "-id"]

    def __str__(self):
        base = (self.texto or "").strip().replace("\n", " ")
        base = base[:60] + ("..." if len(base) > 60 else "")
        return f"{self.modelo.nome} - {base}"


class ComentarioRespostaAuditoria(models.Model):
    registro = models.ForeignKey(
        RegistroAuditoria,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="comentarios_resposta",
        verbose_name="Registro",
    )
    pergunta = models.ForeignKey(
        PerguntaAuditoria,
        on_delete=models.CASCADE,
        related_name="comentarios_resposta",
        verbose_name="Pergunta",
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auditoria_comentarios_resposta",
        verbose_name="Autor",
    )
    texto = models.TextField(verbose_name="Comentário")
    data_referencia = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Data de Referência",
        help_text="Data usada para vincular o comentário ao período/auditoria, inclusive quando ainda não há registro.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Comentário da Resposta (Auditoria)"
        verbose_name_plural = "Comentários das Respostas (Auditoria)"
        ordering = ["-atualizado_em", "-id"]

    def __str__(self):
        base = (self.texto or "").strip().replace("\n", " ")
        base = base[:60] + ("..." if len(base) > 60 else "")
        referencia = self.registro if self.registro_id else (self.data_referencia or "sem data")
        return f"{referencia} - {self.pergunta.pergunta[:40]} - {base}"


class RelatorioCompartilhadoAuditoria(models.Model):
    modelo = models.ForeignKey(
        ModeloAuditoria,
        on_delete=models.CASCADE,
        related_name="relatorios_compartilhados",
        verbose_name="Modelo",
    )
    remetente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="auditoria_relatorios_enviados",
        verbose_name="Remetente",
    )
    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="auditoria_relatorios_recebidos",
        verbose_name="Destinatário",
    )
    token = models.CharField(max_length=64, unique=True, db_index=True, default="")
    inicio = models.DateField(null=True, blank=True, verbose_name="Período Inicial")
    fim = models.DateField(null=True, blank=True, verbose_name="Período Final")
    subcategoria = models.CharField(max_length=80, blank=True, default="", verbose_name="Sub-categoria")
    criado_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField(null=True, blank=True, verbose_name="Expira em")
    primeiro_acesso_em = models.DateTimeField(null=True, blank=True, verbose_name="Primeiro acesso")
    recebido_em = models.DateTimeField(null=True, blank=True, verbose_name="Comprovante de recebimento")
    recebido_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP de recebimento")
    recebido_user_agent = models.CharField(max_length=255, blank=True, default="", verbose_name="Navegador")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Relatório Compartilhado (Auditoria)"
        verbose_name_plural = "Relatórios Compartilhados (Auditoria)"
        ordering = ["-criado_em", "-id"]

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = uuid.uuid4().hex
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        return bool(self.expira_em and self.expira_em <= timezone.now())

    def __str__(self):
        return f"{self.modelo.nome} | {self.remetente} -> {self.destinatario}"
