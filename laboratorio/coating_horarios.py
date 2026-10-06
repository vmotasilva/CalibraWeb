"""
Validação e correção assistida dos horários de entrada/saída do Coating.

- validar_horarios: regras que espelham o Modo Auditoria do Painel (over_24h, negative, missing)
  e bloqueiam o lançamento. Mantenha em sincronia com
  templates/laboratorio/_coating_validacao_horarios.html (validação no navegador).
- validar_horarios_com_conflitos: acrescenta o conflito de horário com outros lotes gravados na
  mesma máquina (uma máquina processa um ciclo por vez) — também é motivo de Auditoria, exceto
  quando o usuário confirma mix de serviço (lote inserido no meio de outro em andamento). Ciclos
  com mix de serviço confirmado não entram na checagem de conflito, nem para os demais lotes.
- analisar_horarios: usa os lotes vizinhos (por número e por horário, na mesma máquina) e a
  duração típica do processo para sugerir a correção mais provável de um erro de digitação,
  deste lote e, havendo conflito, do lote vizinho.
"""
import math
from datetime import datetime, time, timedelta
from statistics import median

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import RegistroCoating, RegraTurnoCoating

DURACAO_MAXIMA = timedelta(hours=24)
TOLERANCIA_FUTURO = timedelta(minutes=10)
# Ciclos da mesma máquina são sequenciais; tolera pequenas diferenças de apontamento.
TOLERANCIA_SOBREPOSICAO = timedelta(minutes=10)
DURACAO_PADRAO = timedelta(minutes=90)  # usada só quando não há histórico
AMOSTRA_MINIMA_TRATAMENTO = 10
AMOSTRA_MINIMA_MAQUINA = 5
LOTES_VIZINHOS = 2  # quantos números de lote antes/depois considerar
MAX_SUGESTOES = 3
# Pesos da nota das sugestões (menor = melhor)
PESO_FORA_DO_TURNO = 2.5   # entrada deixaria de bater com a coluna Data (dia + turno) da linha
PESO_LOTE_FORA_DE_ORDEM = 0.4  # por número de lote vizinho fora da ordem
# Por ciclo sobreposto. Não descarta: o horário errado pode ser o do vizinho.
PESO_SOBREPOSICAO = 2.0


def parse_hora(valor):
    """Converte o valor recebido (string ISO/datetime-local ou datetime) em datetime aware."""
    if not valor:
        return None
    if isinstance(valor, str):
        dt = parse_datetime(valor)
        if dt is None:
            raise ValueError(f"Formato de data/hora inválido: {valor}")
    else:
        dt = valor
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def formatar_duracao(td):
    total_min = int(abs(td).total_seconds() // 60)
    dias, resto = divmod(total_min, 24 * 60)
    horas, minutos = divmod(resto, 60)
    partes = []
    if dias:
        partes.append(f"{dias}d")
    partes.append(f"{horas:02d}h{minutos:02d}min")
    return " ".join(partes)


def _fmt(dt):
    return timezone.localtime(dt).strftime("%d/%m/%Y %H:%M")


def _fmt_curto(dt):
    return timezone.localtime(dt).strftime("%d/%m %H:%M") if dt else "—"


def _fmt_input(dt):
    return timezone.localtime(dt).strftime("%Y-%m-%dT%H:%M") if dt else ""


def _duracao_valida(entrada, saida):
    return bool(entrada and saida) and timedelta(0) < saida - entrada <= DURACAO_MAXIMA


def validar_horarios(entrada, saida, lado=None):
    """
    Verifica se os horários de uma linha de coating configurariam motivo de auditoria.
    Retorna lista de dicts {codigo, titulo, detalhe}; lista vazia = horários válidos.
    """
    linha = f" da linha {lado}" if lado else ""
    agora = timezone.now()
    anomalias = []

    if saida and not entrada:
        anomalias.append({
            "codigo": "missing",
            "titulo": "Horário incompleto: saída sem entrada",
            "detalhe": f"A Hora Saída{linha} foi informada ({_fmt(saida)}), mas a Hora Entrada está vazia. "
                       f"Informe também a Hora Entrada desta linha.",
        })
    elif entrada and not saida and agora - entrada > DURACAO_MAXIMA:
        anomalias.append({
            "codigo": "missing",
            "titulo": "Horário incompleto: lote sem saída há mais de 24h",
            "detalhe": f"A entrada{linha} foi em {_fmt(entrada)} (há {formatar_duracao(agora - entrada)}) "
                       f"e a Hora Saída continua vazia. Informe a Hora Saída.",
        })

    if entrada and saida:
        duracao = saida - entrada
        if duracao == timedelta(0):
            anomalias.append({
                "codigo": "negative", "titulo": "Tempo negativo",
                "detalhe": f"A Hora Saída ({_fmt(saida)}) é IGUAL à Hora Entrada. "
                           f"A saída precisa ser posterior à entrada.",
            })
        elif duracao < timedelta(0):
            anomalias.append({
                "codigo": "negative", "titulo": "Tempo negativo",
                "detalhe": f"A Hora Saída ({_fmt(saida)}) é {formatar_duracao(duracao)} ANTERIOR à "
                           f"Hora Entrada ({_fmt(entrada)}). Um lote não pode sair antes de entrar.",
            })
        elif duracao > DURACAO_MAXIMA:
            anomalias.append({
                "codigo": "over_24h",
                "titulo": "Lote com mais de 24h",
                "detalhe": f"Entre a entrada ({_fmt(entrada)}) e a saída ({_fmt(saida)}) há "
                           f"{formatar_duracao(duracao)} — acima do limite de 24h. "
                           f"Provável erro na DATA da entrada ou da saída.",
            })

    for campo, valor in (("Entrada", entrada), ("Saída", saida)):
        if valor and valor - agora > TOLERANCIA_FUTURO:
            anomalias.append({
                "codigo": "future",
                "titulo": f"Hora {campo} no futuro",
                "detalhe": f"A Hora {campo}{linha} ({_fmt(valor)}) é posterior ao momento atual "
                           f"({_fmt(agora)}). Registre apenas horários que já ocorreram.",
            })

    return anomalias


# ---------------------------------------------------------------------------
# Análise com base nos lotes vizinhos
# ---------------------------------------------------------------------------

def duracao_tipica(maquina, tratamento):
    """Mediana da duração dos ciclos válidos (tratamento na máquina > máquina > padrão)."""
    base = RegistroCoating.objects.filter(
        maquina=maquina, hora_entrada__isnull=False, hora_saida__isnull=False
    ).order_by("-hora_entrada")

    def mediana(qs):
        duracoes = [s - e for e, s in qs.values_list("hora_entrada", "hora_saida")[:300] if _duracao_valida(e, s)]
        return (median(duracoes), len(duracoes)) if duracoes else (None, 0)

    nome_maquina = getattr(maquina, "codigo", "") or str(maquina)
    if tratamento is not None:
        valor, n = mediana(base.filter(tratamento=tratamento))
        if n >= AMOSTRA_MINIMA_TRATAMENTO:
            return valor, f"mediana de {n} ciclos de {tratamento} na {nome_maquina}", True
    valor, n = mediana(base)
    if n >= AMOSTRA_MINIMA_MAQUINA:
        return valor, f"mediana de {n} ciclos da {nome_maquina}", True
    return DURACAO_PADRAO, "valor padrão — pouco histórico nesta máquina", False


def regra_turno_para(hora, regras):
    """Regra de turno que contém o horário (mesma lógica que define a coluna Data do painel)."""
    for regra in regras:
        if regra.hora_inicio <= regra.hora_fim:
            if regra.hora_inicio <= hora <= regra.hora_fim:
                return regra
        elif hora >= regra.hora_inicio or hora <= regra.hora_fim:
            return regra
    return None


def _rotulo_turno(turno):
    if not turno:
        return ""
    return f"{turno.data:%d/%m/%Y}" + (f" · {turno.regra.nome}" if turno.regra_id else "")


def _coluna_data(turno):
    """Coluna Data da tabela de vizinhos, compacta: {'data': 'dd/mm', 'turno': nome da regra}."""
    if not turno:
        return {"data": "—", "turno": ""}
    return {"data": f"{turno.data:%d/%m}", "turno": turno.regra.nome if turno.regra_id else ""}


class _Ciclo:
    """Um ciclo (linha CC ou CX de um lote) numa máquina, com os horários considerados."""

    def __init__(self, reg, entrada=None, saida=None, lote=None, usar_valores=False):
        self.id = reg.id
        self.turno = reg.turno_coating
        self.tratamento = reg.tratamento
        self.coluna_data = _coluna_data(reg.turno_coating)
        self.lote = reg.lote if lote is None else lote
        self.lado = reg.lado
        self.entrada = entrada if usar_valores else reg.hora_entrada
        self.saida = saida if usar_valores else reg.hora_saida
        self.valido = _duracao_valida(self.entrada, self.saida)
        self.mix = reg.mix_servico

    def com_horarios(self, entrada, saida):
        copia = object.__new__(_Ciclo)
        copia.__dict__.update(self.__dict__)
        copia.entrada, copia.saida = entrada, saida
        copia.valido = _duracao_valida(entrada, saida)
        return copia

    @property
    def rotulo(self):
        return f"lote {self.lote} {self.lado}"

    @property
    def periodo(self):
        return f"{_fmt_curto(self.entrada)} → {_fmt_curto(self.saida)}"


def _sobreposicao(e1, s1, e2, s2):
    return min(s1, s2) - max(e1, e2)


def _variacoes(original, inicio, fim):
    """Mesmos minutos do valor digitado, variando hora e data dentro de [inicio, fim]."""
    local = timezone.localtime(original)
    tz = timezone.get_current_timezone()
    dia = timezone.localtime(inicio).date()
    ultimo_dia = timezone.localtime(fim).date()
    while dia <= ultimo_dia:
        for hora in range(24):
            candidato = timezone.make_aware(datetime.combine(dia, time(hora, local.minute)), tz)
            if inicio <= candidato <= fim and candidato != original:
                yield candidato
        dia += timedelta(days=1)


def _custo_digitacao(original, candidato):
    """Quanto o candidato se afasta do que foi digitado (data trocada, dígitos da hora trocados)."""
    o, c = timezone.localtime(original), timezone.localtime(candidato)
    custo = 0.0
    if o.date() != c.date():
        custo += 0.3
    if o.hour != c.hour:
        custo += 0.5 * sum(a != b for a, b in zip(f"{o.hour:02d}", f"{c.hour:02d}"))
    return custo


def _descrever_alteracao(campo, original, novo):
    o, n = timezone.localtime(original), timezone.localtime(novo)
    nome = "Hora Saída" if campo == "saida" else "Hora Entrada"
    if o.date() != n.date() and o.hour == n.hour:
        como = "corrigida apenas a data"
    elif o.date() == n.date():
        como = "corrigida apenas a hora, mantidos os minutos"
    else:
        como = "corrigidas a data e a hora, mantidos os minutos"
    return f"{nome}: {_fmt(original)} → {_fmt(novo)} ({como})"


def _anomalia_conflito(entrada, saida, outro):
    return {
        "codigo": "overlap",
        "titulo": "Conflito de horário com outro lote",
        "detalhe": f"Este ciclo ({_fmt_curto(entrada)} → {_fmt_curto(saida)}) se sobrepõe ao {outro.rotulo} "
                   f"({outro.periodo}) na mesma máquina, que processa um ciclo por vez. "
                   f"Corrija este lote ou o {outro.rotulo} — ou, se foi mix de serviço "
                   f"(lote inserido no meio de outro em andamento), confirme o mix de serviço.",
        "registro_id": outro.id,
    }


def conflitos_horario(registro_id, maquina_id, entrada, saida):
    """Ciclos válidos gravados na mesma máquina que se sobrepõem a [entrada, saida] (sem mix de serviço)."""
    if not _duracao_valida(entrada, saida):
        return []
    qs = RegistroCoating.objects.filter(
        maquina_id=maquina_id,
        mix_servico=False,
        hora_entrada__lt=saida - TOLERANCIA_SOBREPOSICAO,
        hora_saida__gt=entrada + TOLERANCIA_SOBREPOSICAO,
    ).exclude(pk=registro_id).select_related("turno_coating__regra", "tratamento")
    return [
        c for c in map(_Ciclo, qs)
        if c.valido and _sobreposicao(entrada, saida, c.entrada, c.saida) > TOLERANCIA_SOBREPOSICAO
    ]


def validar_horarios_com_conflitos(registro_id, maquina_id, entrada, saida, lado=None):
    """Regras da Auditoria + conflito de horário com outros lotes gravados (usado ao salvar)."""
    anomalias = validar_horarios(entrada, saida, lado)
    if not anomalias:
        anomalias = [_anomalia_conflito(entrada, saida, c) for c in conflitos_horario(registro_id, maquina_id, entrada, saida)]
    return anomalias


def mix_servico_mantido(registro, entrada, saida, gravados=None):
    """
    O mix de serviço já confirmado continua valendo enquanto os horários não mudarem.
    `gravados` = (entrada, saida) antes da edição, quando o registro já foi alterado em memória.
    """
    if not registro.mix_servico:
        return False
    entrada_gravada, saida_gravada = gravados or (registro.hora_entrada, registro.hora_saida)
    return (_fmt_input(entrada) == _fmt_input(entrada_gravada)
            and _fmt_input(saida) == _fmt_input(saida_gravada))


def anotar_conflito_horario(qs):
    """
    Anota `conflito_horario` (bool): o ciclo se sobrepõe a outro ciclo válido da mesma máquina.
    Sobreposição com ciclo de mix de serviço confirmado não conta.
    """
    from django.db.models import DateTimeField, DurationField, Exists, ExpressionWrapper, F, OuterRef

    duracao = ExpressionWrapper(F("hora_saida") - F("hora_entrada"), output_field=DurationField())
    outros = RegistroCoating.objects.annotate(_dur=duracao).filter(
        maquina=OuterRef("maquina"),
        mix_servico=False,
        _dur__gt=TOLERANCIA_SOBREPOSICAO,
        _dur__lte=DURACAO_MAXIMA,
        hora_entrada__lt=ExpressionWrapper(OuterRef("hora_saida") - TOLERANCIA_SOBREPOSICAO, output_field=DateTimeField()),
        hora_saida__gt=ExpressionWrapper(OuterRef("hora_entrada") + TOLERANCIA_SOBREPOSICAO, output_field=DateTimeField()),
    ).exclude(pk=OuterRef("pk"))
    return qs.annotate(_dur_conflito=duracao).annotate(conflito_horario=Exists(outros.values("pk")))


def filtro_conflito_horario():
    """Q para um queryset anotado por anotar_conflito_horario: só ciclos válidos em conflito (sem mix de serviço)."""
    from django.db.models import Q
    return Q(conflito_horario=True, mix_servico=False, _dur_conflito__gt=TOLERANCIA_SOBREPOSICAO, _dur_conflito__lte=DURACAO_MAXIMA)


class _Contexto:
    """Ciclos da máquina em torno do lançamento, regras de turno e duração típica por tratamento."""

    def __init__(self, maquina, janela_ini, janela_fim):
        self.maquina = maquina
        self.nome_maquina = getattr(maquina, "codigo", "") or str(maquina)
        self.ciclos = [
            _Ciclo(r) for r in RegistroCoating.objects.filter(
                maquina=maquina, hora_entrada__range=(janela_ini, janela_fim)
            ).select_related("turno_coating__regra", "tratamento")[:800]
        ]
        self.regras = list(RegraTurnoCoating.objects.filter(ativo=True))
        self._tipicas = {}

    def tipica(self, tratamento):
        chave = getattr(tratamento, "pk", None)
        if chave not in self._tipicas:
            self._tipicas[chave] = duracao_tipica(self.maquina, tratamento)
        return self._tipicas[chave]

    def ancoras(self, ciclo, extras=()):
        """
        Ciclos válidos que não podem se sobrepor a `ciclo` (extras substituem os gravados).
        Ciclos com mix de serviço confirmado podem se sobrepor a outros e ficam de fora.
        """
        ignorar = {ciclo.id} | {x.id for x in extras}
        return [a for a in self.ciclos if a.valido and not a.mix and a.id not in ignorar] + [x for x in extras if x.valido]

    def violacoes_ordem(self, ciclo, e):
        """Números de lote vizinhos (até LOTES_VIZINHOS de cada lado) fora da ordem de entrada."""
        outros = [c for c in self.ciclos if c.entrada and c.id != ciclo.id and c.lote != ciclo.lote]
        menores = sorted({c.lote for c in outros if c.lote < ciclo.lote}, reverse=True)[:LOTES_VIZINHOS]
        maiores = sorted({c.lote for c in outros if c.lote > ciclo.lote})[:LOTES_VIZINHOS]
        return sorted({
            c.lote for c in outros
            if (c.lote in menores and c.entrada > e) or (c.lote in maiores and c.entrada < e)
        })

    def no_turno(self, ciclo, e):
        turno = ciclo.turno
        if not turno or not turno.regra_id or not self.regras:
            return True
        local = timezone.localtime(e)
        regra = regra_turno_para(local.time(), self.regras)
        return local.date() == turno.data and regra is not None and regra.id == turno.regra_id


def _candidatos(entrada, saida, limite_futuro):
    """Correções de digitação plausíveis: (entrada, saida, campo, custo, descrição)."""
    candidatos = []
    for s in _variacoes(saida, entrada + timedelta(minutes=1), min(entrada + DURACAO_MAXIMA, limite_futuro)):
        candidatos.append((entrada, s, "saida", _custo_digitacao(saida, s), _descrever_alteracao("saida", saida, s)))
    if saida <= limite_futuro:
        for e in _variacoes(entrada, saida - DURACAO_MAXIMA, saida - timedelta(minutes=1)):
            candidatos.append((e, saida, "entrada", _custo_digitacao(entrada, e) + 0.15, _descrever_alteracao("entrada", entrada, e)))
    if saida < entrada and entrada - saida <= DURACAO_MAXIMA and entrada <= limite_futuro:
        candidatos.append((saida, entrada, "ambos", 0.4,
                           f"Entrada e saída estavam invertidas: entrada {_fmt(saida)}, saída {_fmt(entrada)}"))
    return candidatos


def _sugerir(ctx, ciclo, extras=(), limite=MAX_SUGESTOES, somente_sem_conflito=False):
    """Sugestões de correção para os horários de `ciclo`, ordenadas da mais provável."""
    limite_futuro = timezone.now() + TOLERANCIA_FUTURO
    tipica, base_tipica, tipica_confiavel = ctx.tipica(ciclo.tratamento)
    ancoras = ctx.ancoras(ciclo, extras)
    rotulo_turno = _rotulo_turno(ciclo.turno)

    def conflitos(e, s):
        return [a for a in ancoras if _sobreposicao(e, s, a.entrada, a.saida) > TOLERANCIA_SOBREPOSICAO]

    avaliados = []
    for e, s, campo, custo, descricao in _candidatos(ciclo.entrada, ciclo.saida, limite_futuro):
        if not _duracao_valida(e, s) or s > limite_futuro or e > limite_futuro:
            continue
        razao = (s - e) / tipica
        if tipica_confiavel and not (0.2 <= razao <= 5):
            continue
        sobrepostos = conflitos(e, s)
        if somente_sem_conflito and sobrepostos:
            continue
        fora_de_ordem = ctx.violacoes_ordem(ciclo, e)
        no_turno = ctx.no_turno(ciclo, e)
        nota = (abs(math.log(razao)) + custo + PESO_LOTE_FORA_DE_ORDEM * len(fora_de_ordem)
                + (0 if no_turno else PESO_FORA_DO_TURNO) + PESO_SOBREPOSICAO * len(sobrepostos))
        avaliados.append((nota, e, s, campo, descricao, fora_de_ordem, no_turno, sobrepostos))

    avaliados.sort(key=lambda x: x[0])
    sugestoes = []
    for i, (nota, e, s, campo, descricao, fora_de_ordem, no_turno, sobrepostos) in enumerate(avaliados[:limite]):
        anterior = max((a for a in ancoras if a.saida <= e + TOLERANCIA_SOBREPOSICAO), key=lambda a: a.saida, default=None)
        seguinte = min((a for a in ancoras if a.entrada >= s - TOLERANCIA_SOBREPOSICAO), key=lambda a: a.entrada, default=None)
        motivos = []
        if rotulo_turno and ctx.regras and ciclo.turno and ciclo.turno.regra_id:
            motivos.append(f"Entrada coerente com a coluna Data da linha ({rotulo_turno})." if no_turno else
                           f"Atenção: a entrada sairia da coluna Data da linha ({rotulo_turno}).")
        motivos.append(f"Duração resultante de {formatar_duracao(s - e)} (típica: {formatar_duracao(tipica)}, {base_tipica}).")
        if sobrepostos:
            motivos.append("Atenção: sobrepõe " + "; ".join(f"o {a.rotulo} ({a.periodo})" for a in sobrepostos)
                           + " na mesma máquina — confira se o horário desse(s) lote(s) também está errado.")
        elif anterior or seguinte:
            partes = []
            if anterior:
                partes.append(f"depois da saída do {anterior.rotulo} ({_fmt_curto(anterior.saida)})")
            if seguinte:
                partes.append(f"antes da entrada do {seguinte.rotulo} ({_fmt_curto(seguinte.entrada)})")
            motivos.append("Encaixa " + " e ".join(partes) + ", sem sobrepor outros ciclos da máquina.")
        else:
            motivos.append("Não há ciclos próximos registrados nesta máquina para confirmar o encaixe.")
        if fora_de_ordem:
            motivos.append("Atenção: fica fora da ordem numérica em relação a "
                           + ", ".join(f"lote {n}" for n in fora_de_ordem) + ".")
        elif any(c.lote != ciclo.lote and c.entrada for c in ctx.ciclos):
            motivos.append("Respeita a ordem dos números de lote vizinhos.")

        segunda = avaliados[i + 1][0] if i + 1 < len(avaliados) else None
        if sobrepostos:
            confianca = "baixa"
        elif i == 0 and (segunda is None or segunda - nota >= 0.5) and (anterior or seguinte) and not fora_de_ordem and no_turno:
            confianca = "alta"
        else:
            confianca = "media"
        sugestoes.append({
            "hora_entrada": _fmt_input(e),
            "hora_saida": _fmt_input(s),
            "campo": campo,
            "titulo": descricao,
            "duracao": formatar_duracao(s - e),
            "motivos": motivos,
            "confianca": confianca,
            "conflitos": [a.id for a in sobrepostos],
        })
    return sugestoes


def analisar_horarios(registro, entrada, saida, maquina=None, tratamento=None, lote=None):
    """
    Retorna {anomalias, avisos, contexto, sugestoes, correcoes_vizinhos, mix_servico} para os horários
    informados de uma linha. Sugestões só corrigem valores digitados (erro de data/hora);
    horários vazios não são inventados.
    """
    maquina = maquina or registro.maquina
    lote = lote if lote is not None else registro.lote

    referencias = [v for v in (entrada, saida) if v]
    if referencias:
        centro_ini, centro_fim = min(referencias), max(referencias)
    else:
        centro_ini = centro_fim = timezone.make_aware(datetime.combine(registro.turno_coating.data, time(12, 0)))
    ctx = _Contexto(maquina, centro_ini - timedelta(days=3), centro_fim + timedelta(days=3))

    atual = _Ciclo(registro, entrada, saida, lote=lote, usar_valores=True)
    if tratamento is not None:
        atual.tratamento = tratamento
    tipica, base_tipica, _ = ctx.tipica(atual.tratamento)

    anomalias = validar_horarios(entrada, saida, registro.lado)
    # Lote em andamento (sem saída) ou sem horários não tem intervalo para comparar
    if not anomalias and atual.valido:
        anomalias = [
            _anomalia_conflito(entrada, saida, a) for a in ctx.ancoras(atual)
            if _sobreposicao(entrada, saida, a.entrada, a.saida) > TOLERANCIA_SOBREPOSICAO
        ]

    codigos = {a["codigo"] for a in anomalias}
    sugestoes = []
    if entrada and saida and codigos & {"negative", "over_24h", "future", "overlap"}:
        sugestoes = _sugerir(ctx, atual)

    # O erro pode estar no vizinho: sugere corrigi-lo assumindo este lote com os horários
    # informados (se válidos) ou com a sugestão mais provável.
    base = None
    if "overlap" in codigos:
        base = atual
    elif sugestoes and sugestoes[0]["conflitos"]:
        base = atual.com_horarios(parse_hora(sugestoes[0]["hora_entrada"]), parse_hora(sugestoes[0]["hora_saida"]))
    correcoes_vizinhos = []
    if base is not None:
        conflitantes = [a for a in ctx.ancoras(base)
                        if _sobreposicao(base.entrada, base.saida, a.entrada, a.saida) > TOLERANCIA_SOBREPOSICAO]
        for vizinho in conflitantes:
            sug = _sugerir(ctx, vizinho, extras=[base], limite=1, somente_sem_conflito=True)
            if not sug:
                continue
            correcoes_vizinhos.append({
                "registro_id": vizinho.id,
                "rotulo": vizinho.rotulo,
                "periodo_atual": vizinho.periodo,
                "premissa": f"Se este lote estiver certo em {base.periodo}:",
                **sug[0],
            })

    # --- Contexto exibido ao usuário (lotes vizinhos na ordem numérica + os em conflito)
    data_ref = timezone.localtime(referencias[0]).date() if referencias else registro.turno_coating.data
    qs_lotes = RegistroCoating.objects.filter(
        maquina=maquina,
        turno_coating__data__range=(data_ref - timedelta(days=3), data_ref + timedelta(days=3)),
    ).exclude(pk=registro.pk).select_related("turno_coating__regra", "tratamento")
    anteriores = list(qs_lotes.filter(lote__lt=lote).order_by("-lote").values_list("lote", flat=True).distinct()[:LOTES_VIZINHOS])
    posteriores = list(qs_lotes.filter(lote__gt=lote).order_by("lote").values_list("lote", flat=True).distinct()[:LOTES_VIZINHOS])
    em_conflito = {a.get("registro_id") for a in anomalias} | {c["registro_id"] for c in correcoes_vizinhos}
    exibidos = [_Ciclo(r) for r in qs_lotes.filter(lote__in=anteriores + posteriores + [lote])]
    ja_exibidos = {c.id for c in exibidos}
    exibidos += [c for c in ctx.ciclos if c.id in em_conflito and c.id not in ja_exibidos and c.id != registro.pk]

    def status(c):
        if c.id in em_conflito:
            return "conflito"
        if c.mix and c.valido:
            return "mix"
        return "ok" if c.valido else ("aberto" if c.entrada and not c.saida else "anomalia")

    linhas = [{
        "lote": c.lote, "lado": c.lado, "atual": False, **c.coluna_data,
        "entrada": _fmt_curto(c.entrada) if c.entrada else "—",
        "saida": _fmt_curto(c.saida) if c.saida else "—",
        "status": status(c),
    } for c in exibidos]
    linhas.append({
        "lote": lote, "lado": registro.lado, "atual": True, **_coluna_data(registro.turno_coating),
        "entrada": _fmt_curto(entrada) if entrada else "—",
        "saida": _fmt_curto(saida) if saida else "—",
        "status": "anomalia" if anomalias else "ok",
    })
    linhas.sort(key=lambda l: (l["lote"], l["lado"]))

    confirmado_por = registro.mix_servico_confirmado_por
    mix_servico = {
        # Conflito já confirmado como mix de serviço com estes mesmos horários: não bloqueia
        "confirmado": mix_servico_mantido(registro, entrada, saida),
        "por": (confirmado_por.get_full_name() or confirmado_por.get_username()) if confirmado_por else "",
        "em": _fmt(registro.mix_servico_confirmado_em) if registro.mix_servico_confirmado_em else "",
    }

    return {
        "anomalias": anomalias,
        "avisos": [],
        "sugestoes": sugestoes,
        "correcoes_vizinhos": correcoes_vizinhos,
        "mix_servico": mix_servico,
        "contexto": {
            "maquina": ctx.nome_maquina,
            "duracao_tipica": formatar_duracao(tipica),
            "base_duracao_tipica": base_tipica,
            "vizinhos": linhas,
        },
    }
