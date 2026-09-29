"""
Validação e correção assistida dos horários de entrada/saída do Coating.

- validar_horarios: regras que espelham o Modo Auditoria do Painel (over_24h, negative, missing)
  e bloqueiam o lançamento. Mantenha em sincronia com
  templates/laboratorio/_coating_validacao_horarios.html (validação no navegador).
- analisar_horarios: usa os lotes vizinhos (por número e por horário, na mesma máquina) e a
  duração típica do processo para sugerir a correção mais provável de um erro de digitação.
"""
import math
from datetime import datetime, time, timedelta
from statistics import median

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import RegistroCoating

DURACAO_MAXIMA = timedelta(hours=24)
TOLERANCIA_FUTURO = timedelta(minutes=10)
# Ciclos da mesma máquina são sequenciais; tolera pequenas diferenças de apontamento.
TOLERANCIA_SOBREPOSICAO = timedelta(minutes=10)
DURACAO_PADRAO = timedelta(minutes=90)  # usada só quando não há histórico
AMOSTRA_MINIMA_TRATAMENTO = 10
AMOSTRA_MINIMA_MAQUINA = 5
LOTES_VIZINHOS = 2  # quantos números de lote antes/depois considerar
MAX_SUGESTOES = 3


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


class _Ciclo:
    def __init__(self, reg):
        self.id = reg.id
        self.lote = reg.lote
        self.lado = reg.lado
        self.entrada = reg.hora_entrada
        self.saida = reg.hora_saida
        self.valido = _duracao_valida(self.entrada, self.saida)

    @property
    def rotulo(self):
        return f"lote {self.lote} {self.lado}"


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


def analisar_horarios(registro, entrada, saida, maquina=None, tratamento=None, lote=None):
    """
    Retorna {anomalias, avisos, contexto, sugestoes} para os horários informados de uma linha.
    Sugestões só são geradas para valores digitados (erro de data/hora); horários vazios não
    são inventados.
    """
    maquina = maquina or registro.maquina
    tratamento = tratamento or registro.tratamento
    lote = lote if lote is not None else registro.lote
    agora = timezone.now()
    limite_futuro = agora + TOLERANCIA_FUTURO

    anomalias = validar_horarios(entrada, saida, registro.lado)
    tipica, base_tipica, tipica_confiavel = duracao_tipica(maquina, tratamento)

    referencias = [v for v in (entrada, saida) if v]
    if referencias:
        janela_ini = min(referencias) - timedelta(days=2)
        janela_fim = max(referencias) + timedelta(days=2)
    else:
        meio_dia = timezone.make_aware(datetime.combine(registro.turno_coating.data, time(12, 0)))
        janela_ini, janela_fim = meio_dia - timedelta(days=2), meio_dia + timedelta(days=2)

    # Ciclos da mesma máquina próximos no tempo: não podem se sobrepor a este.
    ciclos_tempo = [
        _Ciclo(r) for r in RegistroCoating.objects.filter(
            maquina=maquina, hora_entrada__range=(janela_ini, janela_fim)
        ).exclude(pk=registro.pk)[:500]
    ]
    ancoras = [c for c in ciclos_tempo if c.valido]

    # Lotes vizinhos pelo número (mesma máquina, turnos próximos) + a outra face do mesmo lote.
    data_ref = timezone.localtime(referencias[0]).date() if referencias else registro.turno_coating.data
    qs_lotes = RegistroCoating.objects.filter(
        maquina=maquina,
        turno_coating__data__range=(data_ref - timedelta(days=3), data_ref + timedelta(days=3)),
    ).exclude(pk=registro.pk)
    anteriores = list(qs_lotes.filter(lote__lt=lote).order_by("-lote").values_list("lote", flat=True).distinct()[:LOTES_VIZINHOS])
    posteriores = list(qs_lotes.filter(lote__gt=lote).order_by("lote").values_list("lote", flat=True).distinct()[:LOTES_VIZINHOS])
    vizinhos = [_Ciclo(r) for r in qs_lotes.filter(lote__in=anteriores + posteriores + [lote])]

    def violacoes_ordem(e):
        """Lotes de número menor que entraram depois deste, ou maior que entraram antes."""
        return [
            v for v in vizinhos
            if v.entrada and v.lote != lote and ((v.lote < lote and v.entrada > e) or (v.lote > lote and v.entrada < e))
        ]

    def conflitos(e, s):
        return [a for a in ancoras if _sobreposicao(e, s, a.entrada, a.saida) > TOLERANCIA_SOBREPOSICAO]

    # --- Avisos (não bloqueiam): conflitos dos horários informados com os vizinhos
    avisos = []
    if not anomalias and _duracao_valida(entrada, saida):
        for a in conflitos(entrada, saida):
            avisos.append({
                "codigo": "overlap", "titulo": "Sobreposição com outro ciclo da máquina",
                "detalhe": f"Este ciclo ({_fmt_curto(entrada)} → {_fmt_curto(saida)}) se sobrepõe ao "
                           f"{a.rotulo} ({_fmt_curto(a.entrada)} → {_fmt_curto(a.saida)}) na mesma máquina. "
                           f"Confira qual dos dois está com o horário errado.",
            })

    # --- Sugestões de correção
    candidatos = []  # (entrada, saida, campo, custo_edicao, descricao)
    codigos = {a["codigo"] for a in anomalias}
    if entrada and saida and codigos & {"negative", "over_24h", "future"}:
        for s in _variacoes(saida, entrada + timedelta(minutes=1), min(entrada + DURACAO_MAXIMA, limite_futuro)):
            candidatos.append((entrada, s, "saida", _custo_digitacao(saida, s), _descrever_alteracao("saida", saida, s)))
        if saida <= limite_futuro:
            for e in _variacoes(entrada, saida - DURACAO_MAXIMA, saida - timedelta(minutes=1)):
                candidatos.append((e, saida, "entrada", _custo_digitacao(entrada, e) + 0.15, _descrever_alteracao("entrada", entrada, e)))
        if saida < entrada and entrada - saida <= DURACAO_MAXIMA and entrada <= limite_futuro:
            candidatos.append((saida, entrada, "ambos", 0.4,
                               f"Entrada e saída estavam invertidas: entrada {_fmt(saida)}, saída {_fmt(entrada)}"))

    avaliados = []
    for e, s, campo, custo, descricao in candidatos:
        duracao = s - e
        if not _duracao_valida(e, s) or s > limite_futuro or e > limite_futuro:
            continue
        razao = duracao / tipica
        if tipica_confiavel and not (0.2 <= razao <= 5):
            continue
        if conflitos(e, s):
            continue
        fora_de_ordem = violacoes_ordem(e)
        nota = abs(math.log(razao)) + custo + 0.4 * len(fora_de_ordem)
        avaliados.append((nota, e, s, campo, descricao, fora_de_ordem))

    avaliados.sort(key=lambda x: x[0])
    sugestoes = []
    for i, (nota, e, s, campo, descricao, fora_de_ordem) in enumerate(avaliados[:MAX_SUGESTOES]):
        anterior = max((a for a in ancoras if a.saida <= e + TOLERANCIA_SOBREPOSICAO), key=lambda a: a.saida, default=None)
        seguinte = min((a for a in ancoras if a.entrada >= s - TOLERANCIA_SOBREPOSICAO), key=lambda a: a.entrada, default=None)
        motivos = [f"Duração resultante de {formatar_duracao(s - e)} (típica: {formatar_duracao(tipica)}, {base_tipica})."]
        if anterior or seguinte:
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
                           + ", ".join(sorted({f"lote {v.lote}" for v in fora_de_ordem})) + ".")
        elif any(v.lote != lote and v.entrada for v in vizinhos):
            motivos.append("Respeita a ordem dos números de lote vizinhos.")

        segunda = avaliados[i + 1][0] if i + 1 < len(avaliados) else None
        confianca = "alta" if (
            i == 0 and (segunda is None or segunda - nota >= 0.5) and (anterior or seguinte) and not fora_de_ordem
        ) else "media"
        sugestoes.append({
            "hora_entrada": _fmt_input(e),
            "hora_saida": _fmt_input(s),
            "campo": campo,
            "titulo": descricao,
            "duracao": formatar_duracao(s - e),
            "motivos": motivos,
            "confianca": confianca,
        })

    # --- Contexto exibido ao usuário (lotes vizinhos na ordem numérica)
    linhas = [{
        "lote": v.lote, "lado": v.lado, "atual": False,
        "entrada": _fmt_curto(v.entrada) if v.entrada else "—",
        "saida": _fmt_curto(v.saida) if v.saida else "—",
        "status": "ok" if v.valido else ("aberto" if v.entrada and not v.saida else "anomalia"),
    } for v in vizinhos]
    linhas.append({
        "lote": lote, "lado": registro.lado, "atual": True,
        "entrada": _fmt_curto(entrada) if entrada else "—",
        "saida": _fmt_curto(saida) if saida else "—",
        "status": "anomalia" if anomalias else "ok",
    })
    linhas.sort(key=lambda l: (l["lote"], l["lado"]))

    return {
        "anomalias": anomalias,
        "avisos": avisos,
        "sugestoes": sugestoes,
        "contexto": {
            "maquina": getattr(maquina, "codigo", "") or str(maquina),
            "duracao_tipica": formatar_duracao(tipica),
            "base_duracao_tipica": base_tipica,
            "vizinhos": linhas,
        },
    }
