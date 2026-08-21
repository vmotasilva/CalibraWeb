from django.conf import settings
from django.db import models
from django.utils import timezone
import re
import unicodedata
import uuid


PERGUNTA_RESPOSTA_PRESETS = {
    "ISO": {
        "label": "ISO",
        "tipo_resposta": "LISTA",
        "opcoes_resposta": [
            "Conforme",
            "Não Conforme",
            "Não Se Aplica",
            "Oportunidade de Melhoria",
        ],
        "opcoes_resposta_cores": {
            "Conforme": "#198754",
            "Não Conforme": "#ff0000",
            "Não Se Aplica": "#d9d9d9",
            "Oportunidade de Melhoria": "#fd7e14",
        },
        "exibir_grafico": True,
        "aplicar_no_grid": True,
    },
}


def list_pergunta_resposta_presets() -> list[dict]:
    presets: list[dict] = []
    for key, data in PERGUNTA_RESPOSTA_PRESETS.items():
        options = list(data.get("opcoes_resposta") or [])
        colors = dict(data.get("opcoes_resposta_cores") or {})
        presets.append(
            {
                "key": key,
                "label": str(data.get("label") or key),
                "tipo_resposta": str(data.get("tipo_resposta") or "SIM_NAO"),
                "opcoes_resposta": options,
                "opcoes_resposta_texto": "\n".join(options),
                "opcoes_resposta_cores": colors,
                "exibir_grafico": bool(data.get("exibir_grafico", True)),
                "aplicar_no_grid": bool(data.get("aplicar_no_grid", True)),
            }
        )
    return presets


def get_pergunta_resposta_preset_choices() -> list[tuple[str, str]]:
    return [(preset["key"], preset["label"]) for preset in list_pergunta_resposta_presets()]


def get_pergunta_resposta_preset(key: str) -> dict | None:
    lookup = str(key or "").strip().upper()
    raw = PERGUNTA_RESPOSTA_PRESETS.get(lookup)
    if not raw:
        return None

    options = list(raw.get("opcoes_resposta") or [])
    return {
        "key": lookup,
        "label": str(raw.get("label") or lookup),
        "tipo_resposta": str(raw.get("tipo_resposta") or "SIM_NAO"),
        "opcoes_resposta": options,
        "opcoes_resposta_texto": "\n".join(options),
        "opcoes_resposta_cores": dict(raw.get("opcoes_resposta_cores") or {}),
        "exibir_grafico": bool(raw.get("exibir_grafico", True)),
        "aplicar_no_grid": bool(raw.get("aplicar_no_grid", True)),
    }


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


    
    ativo = models.BooleanField(default=True)
    arquivado = models.BooleanField(default=False)
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







class TopicoAuditoria(models.Model):
    modelo = models.ForeignKey(
        ModeloAuditoria,
        on_delete=models.CASCADE,
        related_name="topicos",
        verbose_name="Modelo",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="subtopicos",
        null=True,
        blank=True,
        verbose_name="Tópico Pai",
    )
    nome = models.CharField(max_length=255)
    ordem = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Tópico de Auditoria"
        verbose_name_plural = "Tópicos de Auditoria"
        ordering = ["modelo", "parent__ordem", "ordem", "nome"]

    def __str__(self):
        if self.parent:
            return f"{self.parent} > {self.nome}"
        return f"{self.modelo.nome} - {self.nome}"

    def get_path(self):
        """Retorna uma lista contendo a hierarquia desde o Tópico raiz até este Tópico."""
        path = []
        current = self
        while current is not None:
            path.append(current)
            current = current.parent
        return path[::-1]

    def get_full_name(self, separator=" > "):
        return separator.join([t.nome for t in self.get_path()])

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
    exibir_grafico = models.BooleanField(
        default=True,
        verbose_name="Exibir gráfico",
        help_text="Controla se esta pergunta pode aparecer em relatórios com gráfico.",
    )

    aplicar_no_grid = models.BooleanField(
        default=True,
        verbose_name="Aplicar no GRID",
        help_text="Se marcado, esta pergunta aparece no preenchimento em GRID (quando habilitado no modelo).",
    )
    ordem = models.PositiveIntegerField(default=1)

    topico = models.ForeignKey(
        TopicoAuditoria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="perguntas",
        verbose_name="Tópico / Estrutura",
        help_text="Tópico hierárquico da pergunta",
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
    STATUS_CHOICES = [
        ("RASCUNHO", "Em Andamento"),
        ("CONCLUIDO", "Concluído"),
    ]

    modelo = models.ForeignKey(
        ModeloAuditoria,
        on_delete=models.PROTECT,
        related_name="registros",
        verbose_name="Modelo",
    )
    nome = models.CharField(max_length=150, default="Ciclo de Auditoria", verbose_name="Nome do Ciclo")
    alvo = models.CharField(
        max_length=150,
        blank=True,
        default="",
        verbose_name="Alvo da Auditoria",
        help_text="Empresa, setor ou departamento alvo deste ciclo.",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="RASCUNHO")
    progresso = models.PositiveIntegerField(default=0, help_text="Progresso do ciclo em % (0 a 100).")
    
    data_auditoria = models.DateField(verbose_name="Data da Auditoria", null=True, blank=True)
    periodo_inicio = models.DateField(verbose_name="Período Inicial")
    periodo_fim = models.DateField(verbose_name="Período Final Previsto")
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
        verbose_name="ITEM/O.S. (Legado)",
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
    atualizado_em = models.DateTimeField(auto_now=True)

    def calcular_progresso(self):
        """Calcula o progresso do ciclo (0-100%) baseado nas perguntas obrigatórias"""
        perguntas = self.modelo.perguntas.filter(ativo=True, obrigatoria=True)
        total_esperado = 0
        total_respondido = 0
        
        # O total esperado e respondido varia de acordo com o formato (GRID, Semanal, etc).
        # Para simplificar de maneira genérica sem refazer a lógica pesada de views:
        # Contamos quantas RespostaAuditoria válidas (não vazias) estão vinculadas às perguntas obrigatórias.
        # Porém, precisamos saber o universo exato (total_esperado).
        
        # Uma aproximação genérica para preenchimento progressivo:
        grid_items = []
        if self.grid_itens:
            grid_items = [i.strip() for i in self.grid_itens.split('\n') if i.strip()]
        
        is_semanal = self.modelo.periodicidade == 'SEMANAL'
        
        for p in perguntas:
            # Multiplicador (GRID)
            fator_grid = len(grid_items) if grid_items else 1
            
            # Multiplicador (Semanal)
            fator_semanal = 7 if (is_semanal and getattr(p, 'preenchimento_semanal', 'UNICO') == 'POR_DIA') else 1
            
            total_esperado += (fator_grid * fator_semanal)
            
            # Conta respostas não vazias
            respostas_validas = self.respostas.filter(pergunta=p).exclude(valor="")
            total_respondido += respostas_validas.count()
            
        if total_esperado == 0:
            return 100
        
        progresso = int((total_respondido / total_esperado) * 100)
        return min(progresso, 100)

    def atualizar_progresso(self):
        prog = self.calcular_progresso()
        if self.progresso != prog:
            self.progresso = prog
            self.save(update_fields=['progresso'])


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


class JustificativaAuditoria(models.Model):
    modelo = models.ForeignKey(
        ModeloAuditoria,
        on_delete=models.CASCADE,
        related_name="justificativas",
        verbose_name="Modelo",
    )
    periodo_inicio = models.DateField(verbose_name="Início do Período", null=True)
    periodo_fim = models.DateField(verbose_name="Fim do Período", null=True)
    justificativa = models.TextField(verbose_name="Justificativa")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Justificado por",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Data da Justificativa")

    class Meta:
        verbose_name = "Justificativa de Auditoria"
        verbose_name_plural = "Justificativas de Auditoria"
        ordering = ["-periodo_inicio", "-criado_em"]

    def __str__(self):
        return f"Justificativa para {self.modelo.nome} ({self.periodo_inicio} a {self.periodo_fim})"


# ==========================================
# MODELOS PARA AUDITORIA MODO ENTREVISTA (ISO)
# ==========================================

class Norma(models.Model):
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código da Norma (ex: ISO 13485:2016)")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    ativa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Norma"
        verbose_name_plural = "Normas"

    def __str__(self):
        return self.codigo


class RegraVeredictoNorma(models.Model):
    """
    Parametrização do Motor de Aprovação por Norma.
    Define as regras e tolerâncias para: APTO, RESSALVA e INAPTO.
    """
    STATUS_CHOICES = [
        ('APTO', 'Apto (Recomendado)'),
        ('RESSALVA', 'Apto com Ressalvas'),
        ('INAPTO', 'Inapto / Não Conforme'),
    ]

    norma = models.ForeignKey(Norma, on_delete=models.CASCADE, related_name="regras_veredicto")
    status_resultado = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name="Status do Parecer")
    
    min_percentual_conformidade = models.FloatField(
        default=90.0,
        verbose_name="Índice Mínimo de Conformidade (%)",
        help_text="Abaixo deste percentual, o status não é concedido."
    )
    max_nc_maior = models.PositiveIntegerField(
        default=0, 
        verbose_name="Qtd Máxima de NC Maior Tolerada"
    )
    max_nc_menor = models.PositiveIntegerField(
        default=2, 
        verbose_name="Qtd Máxima de NC Menor Tolerada"
    )
    texto_parecer_padrao = models.TextField(
        verbose_name="Texto do Parecer Padrão no Relatório",
        help_text="Texto institucional que será exibido no slide de fechamento."
    )
    cor_badge = models.CharField(
        max_length=20, 
        default="#198754", 
        verbose_name="Cor Hexadecimal / CSS"
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Regra de Veredicto da Norma"
        verbose_name_plural = "Regras de Veredicto das Normas"
        unique_together = ('norma', 'status_resultado')

    def __str__(self):
        return f"[{self.norma.codigo}] {self.get_status_resultado_display()}"


class ItemNorma(models.Model):
    norma = models.ForeignKey(Norma, on_delete=models.CASCADE, related_name="itens")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name="subitens")
    referencia = models.CharField(max_length=50, verbose_name="Referência (ex: 4.1.6)")
    titulo = models.CharField(max_length=255, verbose_name="Título do Item")
    descricao = models.TextField(blank=True, verbose_name="Descrição / Requisito")
    pergunta_padrao = models.TextField(blank=True, verbose_name="Pergunta Padrão")
    evidencia_padrao = models.TextField(blank=True, verbose_name="Evidências Esperadas (Padrão)")
    ordem = models.PositiveIntegerField(default=1)
    atalho_especial = models.BooleanField(default=False, verbose_name="Atalho Especial (Acesso Rápido)", help_text="Permite acesso e criação de solicitações rápidas em qualquer bloco no modo entrevista")

    class Meta:
        verbose_name = "Item da Norma"
        verbose_name_plural = "Itens da Norma"
        ordering = ['norma', 'referencia']

    def __str__(self):
        return f"{self.referencia} - {self.titulo}"

    @property
    def referencia_raiz(self):
        if self.parent:
            return f"{self.parent.referencia} - {self.parent.titulo}"
        parts = self.referencia.split('.')
        if len(parts) > 1:
            return '.'.join(parts[:-1])
        return "— (Seção Raiz)"

    def save(self, *args, **kwargs):
        if not self.parent and '.' in self.referencia:
            parent_ref = '.'.join(self.referencia.split('.')[:-1])
            parent_item = ItemNorma.objects.filter(norma=self.norma, referencia=parent_ref).first()
            if parent_item:
                self.parent = parent_item
        super().save(*args, **kwargs)


class BancoPergunta(models.Model):
    texto_pergunta = models.TextField(verbose_name="Pergunta (Linguagem Natural)")
    dica_auditor = models.TextField(blank=True, verbose_name="Dicas / O que procurar")
    itens_norma = models.ManyToManyField(ItemNorma, related_name="perguntas_vinculadas", verbose_name="Itens da Norma Avaliados")
    ativa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Banco de Pergunta (ISO)"
        verbose_name_plural = "Banco de Perguntas (ISO)"

    def __str__(self):
        return self.texto_pergunta[:80]


class BancoSolicitacaoIso(models.Model):
    norma = models.ForeignKey(Norma, on_delete=models.CASCADE, related_name="banco_solicitacoes", verbose_name="Norma de Referência")
    titulo_solicitacao = models.TextField(verbose_name="Solicitação / Item Solicitado")
    dica_evidencia = models.TextField(blank=True, verbose_name="Dicas de Evidência / O que verificar")
    itens_norma = models.ManyToManyField(ItemNorma, blank=True, related_name="solicitacoes_modelo_vinculadas", verbose_name="Itens da Norma Avaliados")
    ativa = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Banco de Solicitação de Evidência (ISO)"
        verbose_name_plural = "Banco de Solicitações de Evidências (ISO)"

    def __str__(self):
        return self.titulo_solicitacao[:80]


class AuditoriaIso(models.Model):
    STATUS_CHOICES = [
        ("PLANEJADA", "Planejada"),
        ("EM_ANDAMENTO", "Em Andamento"),
        ("CONCLUIDA", "Concluída"),
        ("ARQUIVADA", "Arquivada"),
    ]
    norma = models.ForeignKey(Norma, on_delete=models.PROTECT, related_name="auditorias")
    data_inicio = models.DateField(verbose_name="Data de Início")
    data_fim = models.DateField(verbose_name="Data de Fim Prevista")
    auditores = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="auditorias_iso_realizadas", verbose_name="Auditores")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PLANEJADA")
    escopo_itens = models.ManyToManyField(ItemNorma, related_name="auditorias_escopo", verbose_name="Escopo (Itens Aplicáveis)", help_text="Itens da norma que serão avaliados nesta auditoria")
    itens_nao_aplicaveis = models.ManyToManyField(ItemNorma, blank=True, related_name="auditorias_nao_aplicaveis", verbose_name="Itens Marcados como Não Aplicáveis")
    
    abertura_auditores = models.CharField(max_length=255, blank=True, verbose_name="Auditores (Abertura)")
    abertura_representantes = models.CharField(max_length=255, blank=True, verbose_name="Representantes (Abertura)")
    revisao_auditores = models.CharField(max_length=255, blank=True, verbose_name="Auditores (Revisão)")
    revisao_representantes = models.CharField(max_length=255, blank=True, verbose_name="Representantes (Revisão)")
    encerramento_auditores = models.CharField(max_length=255, blank=True, verbose_name="Auditores (Encerramento)")
    encerramento_representantes = models.CharField(max_length=255, blank=True, verbose_name="Representantes (Encerramento)")

    empresa_auditada = models.CharField(max_length=255, blank=True, default="", verbose_name="Empresa / Laboratório Auditado")
    escopo = models.CharField(max_length=500, blank=True, default="Fabricação de Lentes Oftálmicas", verbose_name="Escopo da Auditoria")
    
    sintese = models.TextField(blank=True, default="", verbose_name="Síntese da Auditoria", help_text="Síntese executiva formatada em HTML/WYSIWYG com tabelas e imagens")
    conclusao_texto = models.TextField(blank=True, default="", verbose_name="Conclusão / Parecer Final da Auditoria")
    
    arquivada = models.BooleanField(default=False, verbose_name="Arquivada")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Auditoria (Modo Entrevista)"
        verbose_name_plural = "Auditorias (Modo Entrevista)"

    def __str__(self):
        return f"Auditoria {self.norma.codigo} - {self.data_inicio:%d/%m/%Y}"


class PontoForteAuditoriaIso(models.Model):
    auditoria = models.ForeignKey(AuditoriaIso, on_delete=models.CASCADE, related_name="pontos_fortes", verbose_name="Auditoria")
    titulo = models.CharField(max_length=255, verbose_name="Título do Ponto Forte")
    descricao = models.TextField(blank=True, default="", verbose_name="Descrição / Detalhamento")
    icone = models.CharField(max_length=60, default="bi-shield-fill-check", verbose_name="Ícone Bootstrap")
    ordem = models.IntegerField(default=0, verbose_name="Ordem de Exibição")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ponto Forte da Auditoria"
        verbose_name_plural = "Pontos Fortes da Auditoria"
        ordering = ["ordem", "id"]

    def __str__(self):
        return f"{self.titulo} ({self.auditoria})"


class ModeloAuditoriaIso(models.Model):
    titulo = models.CharField(max_length=255, verbose_name="Título do Modelo")
    norma = models.ForeignKey(Norma, on_delete=models.CASCADE, related_name="modelos_auditoria", verbose_name="Norma de Referência")
    descricao = models.TextField(blank=True, verbose_name="Descrição do Modelo")
    perguntas = models.ManyToManyField('BancoPergunta', blank=True, related_name="modelos_vinculados", verbose_name="Perguntas do Modelo")
    solicitacoes = models.ManyToManyField('BancoSolicitacaoIso', blank=True, related_name="modelos_vinculados", verbose_name="Solicitações do Modelo")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Modelo de Auditoria"
        verbose_name_plural = "Modelos de Auditoria"
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.titulo} ({self.norma.codigo})"


class BlocoModeloIso(models.Model):
    modelo = models.ForeignKey(ModeloAuditoriaIso, on_delete=models.CASCADE, related_name="blocos", verbose_name="Modelo de Origem")
    titulo = models.CharField(max_length=255, verbose_name="Título do Bloco")
    itens_norma = models.ManyToManyField('ItemNorma', blank=True, related_name="blocos_modelo_vinculados", verbose_name="Itens Alvo do Bloco")
    perguntas = models.ManyToManyField('BancoPergunta', blank=True, related_name="blocos_modelo_vinculados", verbose_name="Perguntas do Bloco")
    solicitacoes = models.ManyToManyField('BancoSolicitacaoIso', blank=True, related_name="blocos_modelo_vinculados", verbose_name="Solicitações do Bloco")
    ordem = models.IntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Bloco de Modelo"
        verbose_name_plural = "Blocos de Modelo"
        ordering = ['ordem', 'criado_em']

    def __str__(self):
        return f"{self.titulo} - {self.modelo.titulo}"


class AgendaAuditoriaIso(models.Model):
    auditoria = models.ForeignKey(AuditoriaIso, on_delete=models.CASCADE, related_name="agendas")
    modelo_base = models.ForeignKey(ModeloAuditoriaIso, on_delete=models.SET_NULL, null=True, blank=True, related_name="agendas_instanciadas", verbose_name="Modelo Base")
    titulo = models.CharField(max_length=255, verbose_name="Título da Agenda")
    data = models.DateField(null=True, blank=True, verbose_name="Data Prevista")
    hora_inicio = models.TimeField(null=True, blank=True, verbose_name="Hora de Início Prevista")
    hora_fim = models.TimeField(null=True, blank=True, verbose_name="Hora de Término Prevista")
    data_real = models.DateField(null=True, blank=True, verbose_name="Data Ajustada/Real")
    hora_inicio_real = models.TimeField(null=True, blank=True, verbose_name="Hora de Início Ajustada")
    hora_fim_real = models.TimeField(null=True, blank=True, verbose_name="Hora de Término Ajustada")
    itens_norma = models.ManyToManyField(ItemNorma, blank=True, related_name="agendas_vinculadas", verbose_name="Itens da Norma Observados")
    perguntas = models.ManyToManyField(BancoPergunta, blank=True, related_name="agendas_vinculadas", verbose_name="Perguntas Aplicáveis")
    auditores = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="agendas_iso_alocadas", verbose_name="Auditores do Bloco")
    auditores_nomes = models.CharField(max_length=255, blank=True, verbose_name="Auditores (Texto Livre)")
    representantes = models.CharField(max_length=255, blank=True, verbose_name="Representantes do Local")
    concluida = models.BooleanField(default=False, verbose_name="Etapa Concluída")
    arquivada = models.BooleanField(default=False, verbose_name="Arquivada")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Agenda de Auditoria"
        verbose_name_plural = "Agendas de Auditoria"
        ordering = ['criado_em']

    def __str__(self):
        return self.titulo

    def itens_cobertos(self):
        # Retorna os itens da norma associados através das perguntas
        return ItemNorma.objects.filter(perguntas_vinculadas__agendas_vinculadas=self).distinct()

    def progresso(self):
        perguntas_ids = self.perguntas.values_list('id', flat=True)
        if not perguntas_ids:
            return {'total': 0, 'respondidas': 0, 'percentual': 0}
            
        respondidas = RespostaEntrevistaIso.objects.filter(
            auditoria=self.auditoria,
            pergunta_id__in=perguntas_ids,
            classificacao__in=['C', 'NC', 'NA', 'OM']
        ).count()
        
        total = len(perguntas_ids)
        percentual = int((respondidas / total) * 100) if total > 0 else 0
        return {'total': total, 'respondidas': respondidas, 'percentual': percentual}


class RespostaEntrevistaIso(models.Model):
    CLASSIFICACAO_CHOICES = [
        ("C", "Conforme"),
        ("OBS", "Observação com Correção"),
        ("NC", "Não Conforme"),
        ("NA", "Não Aplicável"),
        ("OM", "Oportunidade de Melhoria"),
        ("P", "Pendente"),
    ]
    GRAU_NC_CHOICES = [
        ("MENOR", "NC Menor"),
        ("MAIOR", "NC Maior"),
    ]
    auditoria = models.ForeignKey(AuditoriaIso, on_delete=models.CASCADE, related_name="respostas")
    pergunta = models.ForeignKey(BancoPergunta, on_delete=models.PROTECT, related_name="respostas")
    texto_resposta = models.TextField(blank=True, verbose_name="Resposta do Auditado / Anotações")
    classificacao = models.CharField(max_length=4, choices=CLASSIFICACAO_CHOICES, default="P")
    grau_nc = models.CharField(max_length=10, choices=GRAU_NC_CHOICES, blank=True, null=True, verbose_name="Grau da Não Conformidade")
    respondida_em = models.DateTimeField(auto_now=True)
    respondida_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Resposta Entrevista ISO"
        verbose_name_plural = "Respostas Entrevista ISO"
        unique_together = ('auditoria', 'pergunta')

    def __str__(self):
        return f"{self.auditoria} - {self.pergunta.texto_pergunta[:30]}"


class SolicitacaoEvidenciaIso(models.Model):
    CLASSIFICACAO_CHOICES = [
        ("C", "Conforme"),
        ("OBS", "Observação com Correção"),
        ("NC", "Não Conforme"),
        ("NA", "Não Aplicável"),
        ("OM", "Oportunidade de Melhoria"),
        ("P", "Pendente"),
    ]
    GRAU_NC_CHOICES = [
        ("MENOR", "NC Menor"),
        ("MAIOR", "NC Maior"),
    ]
    resposta = models.ForeignKey(RespostaEntrevistaIso, on_delete=models.CASCADE, related_name="solicitacoes")
    agenda = models.ForeignKey('AgendaAuditoriaIso', on_delete=models.SET_NULL, null=True, blank=True, related_name="solicitacoes_registradas", verbose_name="Bloco da Agenda de Origem")
    solicitacao = models.TextField(verbose_name="Solicitação / Item Solicitado")
    evidencia = models.TextField(blank=True, verbose_name="Evidência Apresentada")
    conclusao = models.CharField(max_length=4, choices=CLASSIFICACAO_CHOICES, default="P")
    grau_nc = models.CharField(max_length=10, choices=GRAU_NC_CHOICES, blank=True, null=True, verbose_name="Grau da Não Conformidade")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Solicitação de Evidência ISO"
        verbose_name_plural = "Solicitações de Evidências ISO"
        ordering = ['criado_em']

    def __str__(self):
        return f"Solicitação: {self.solicitacao[:30]} ({self.conclusao})"


class ImagemSolicitacaoIso(models.Model):
    solicitacao = models.ForeignKey(
        SolicitacaoEvidenciaIso,
        on_delete=models.CASCADE,
        related_name="imagens",
        verbose_name="Solicitação de Evidência",
    )
    arquivo = models.ImageField(
        upload_to="auditoria/solicitacoes/%Y/%m/",
        blank=True,
        null=True,
        verbose_name="Arquivo de Imagem",
    )
    arquivo_base64 = models.TextField(
        blank=True,
        default="",
        verbose_name="Dados Base64",
        help_text="Backup base64 para persistência garantida em ambientes serverless",
    )
    nome_arquivo = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Nome do Arquivo",
    )
    legenda = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Legenda / Descrição da Evidência",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Imagem da Solicitação ISO"
        verbose_name_plural = "Imagens das Solicitações ISO"
        ordering = ["criado_em"]

    def __str__(self):
        return f"Imagem {self.id} - {self.solicitacao.solicitacao[:30]}"

    @property
    def url_imagem(self) -> str:
        """Retorna a URL acessível da imagem (preferindo media URL, com fallback para Data URI base64)."""
        if self.arquivo_base64 and self.arquivo_base64.startswith("data:"):
            return self.arquivo_base64
        if self.arquivo and hasattr(self.arquivo, "url"):
            try:
                return self.arquivo.url
            except Exception:
                pass
        if self.arquivo_base64:
            return f"data:image/jpeg;base64,{self.arquivo_base64}"
        return ""


class AvaliacaoFinalRequisitoIso(models.Model):
    CLASSIFICACAO_CHOICES = [
        ("C", "Conforme"),
        ("OBS", "Observação com Correção"),
        ("NC", "Não Conforme"),
        ("NA", "Não Aplicável"),
        ("OM", "Oportunidade de Melhoria"),
        ("P", "Pendente"),
    ]
    GRAU_NC_CHOICES = [
        ("MENOR", "NC Menor"),
        ("MAIOR", "NC Maior"),
    ]
    auditoria = models.ForeignKey(AuditoriaIso, on_delete=models.CASCADE, related_name="avaliacoes_finais")
    item_norma = models.ForeignKey(ItemNorma, on_delete=models.CASCADE, related_name="avaliacoes_finais")
    classificacao = models.CharField(max_length=4, choices=CLASSIFICACAO_CHOICES)
    grau_nc = models.CharField(max_length=10, choices=GRAU_NC_CHOICES, blank=True, null=True, verbose_name="Grau da Não Conformidade")
    justificativa = models.TextField(blank=True, verbose_name="Argumentação / Justificativa da Reversão")
    atualizado_em = models.DateTimeField(auto_now=True)
    atualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Avaliação Final do Requisito ISO"
        verbose_name_plural = "Avaliações Finais dos Requisitos ISO"
        unique_together = ('auditoria', 'item_norma')

    def __str__(self):
        return f"{self.auditoria} - {self.item_norma.referencia} ({self.classificacao})"


class SinteseSecaoAuditoriaIso(models.Model):
    """
    Síntese / Notas livres registradas pelo auditor por Seção / Macroárea funcional da Norma.
    Ex: Seção 4 (Sistema de Gestão), Seção 5 (Responsabilidade da Direção), etc.
    """
    auditoria = models.ForeignKey(AuditoriaIso, on_delete=models.CASCADE, related_name="sinteses_secao")
    secao_referencia = models.CharField(max_length=20, verbose_name="Referência da Seção (ex: 4, 5, 7.1)")
    secao_titulo = models.CharField(max_length=255, verbose_name="Título da Seção / Área")
    conteudo_html = models.TextField(blank=True, default="", verbose_name="Síntese da Seção (HTML)")
    atualizado_em = models.DateTimeField(auto_now=True)
    atualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Síntese por Seção da Auditoria"
        verbose_name_plural = "Sínteses por Seção da Auditoria"
        unique_together = ('auditoria', 'secao_referencia')
        ordering = ['secao_referencia']

    def __str__(self):
        return f"{self.auditoria} - Seção {self.secao_referencia}: {self.secao_titulo}"

