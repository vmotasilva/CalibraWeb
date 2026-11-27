"""Condições especiais de um agrupamento de checklist ("aparecer só no 5º dia do mês", etc.).

Uma regra é um dict `{"tipo": ..., ...}` avaliado para uma data. Os itens de um agrupamento só aparecem nos dias
em que a regra vale (além da periodicidade do próprio checklist). Sem regra (ou "sempre"), o agrupamento aparece
em todas as ocorrências do checklist.

Tipos:
- sempre                      — sem condição
- dia_mes      {dia, n}       — no dia `dia` do mês, a cada `n` meses (meses curtos usam o último dia)
- ultimo_dia_mes {n}          — no último dia do mês, a cada `n` meses
- dias_semana  {dias}         — em certos dias da semana (0=segunda ... 6=domingo)
- semana_mes   {nth, dia, n}  — na `nth`-ésima (1 a 4, ou -1 = última) ocorrência do dia da semana `dia` no mês
- cada_dias    {n}            — a cada `n` dias, contando a partir da data de referência (início do checklist)

Meses e intervalos contam a partir de `ref` (a data de início do checklist).
"""
import calendar
from datetime import date

TIPOS = ("sempre", "dia_mes", "ultimo_dia_mes", "dias_semana", "semana_mes", "cada_dias")
DIAS_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
LIMITE_N = {"cada_dias": 365, "dia_mes": 60, "ultimo_dia_mes": 60, "semana_mes": 60}
SEMPRE = {"tipo": "sempre"}


def _int(valor, nome, minimo, maximo):
    try:
        v = int(valor)
    except (TypeError, ValueError):
        raise ValueError(f"{nome} inválido.")
    if not minimo <= v <= maximo:
        raise ValueError(f"{nome} deve estar entre {minimo} e {maximo}.")
    return v


def normaliza(regra):
    """Valida e limpa uma regra vinda da tela; devolve um dict só com as chaves do tipo. ValueError se inválida."""
    if not regra:
        return dict(SEMPRE)
    if not isinstance(regra, dict):
        raise ValueError("Condição inválida.")
    tipo = regra.get("tipo") or "sempre"
    if tipo not in TIPOS:
        raise ValueError("Tipo de condição inválido.")
    if tipo == "sempre":
        return dict(SEMPRE)
    out = {"tipo": tipo}
    if tipo in LIMITE_N:
        n = regra.get("n")
        out["n"] = 1 if n is None or n == "" else _int(n, "O intervalo", 1, LIMITE_N[tipo])  # 0 é inválido, vazio = 1
    if tipo == "dia_mes":
        out["dia"] = _int(regra.get("dia"), "O dia do mês", 1, 31)
    elif tipo == "dias_semana":
        dias = sorted({int(x) for x in (regra.get("dias") or []) if str(x).isdigit() and 0 <= int(x) <= 6})
        if not dias:
            raise ValueError("Escolha pelo menos um dia da semana na condição.")
        out["dias"] = dias
    elif tipo == "semana_mes":
        out["dia"] = _int(regra.get("dia"), "O dia da semana", 0, 6)
        nth = _int(regra.get("nth"), "A semana do mês", -1, 4)
        if nth == 0:
            raise ValueError("A semana do mês deve ser de 1 a 4 ou a última.")
        out["nth"] = nth
    return out


def aplica(regra, dia: date, ref: date | None) -> bool:
    """True se a regra vale em `dia`. `ref` é a data de início do checklist (referência de intervalos)."""
    tipo = (regra or SEMPRE).get("tipo", "sempre")
    if tipo == "sempre":
        return True
    ref = ref or dia
    n = max(1, int(regra.get("n") or 1))
    if tipo == "dias_semana":
        return dia.weekday() in set(regra.get("dias") or [])
    if tipo == "cada_dias":
        return dia >= ref and (dia - ref).days % n == 0
    meses_desde = (dia.year - ref.year) * 12 + dia.month - ref.month
    if meses_desde < 0 or meses_desde % n:
        return False
    ultimo = calendar.monthrange(dia.year, dia.month)[1]
    if tipo == "dia_mes":
        return dia.day == min(int(regra["dia"]), ultimo)
    if tipo == "ultimo_dia_mes":
        return dia.day == ultimo
    if tipo == "semana_mes":
        if dia.weekday() != int(regra["dia"]):
            return False
        nth = int(regra["nth"])
        return dia.day + 7 > ultimo if nth == -1 else (dia.day - 1) // 7 + 1 == nth
    return True


def descrever(regra) -> str:
    """Texto curto da condição, em português ("no dia 5 do mês"); vazio para "sempre"."""
    regra = regra or SEMPRE
    tipo, n = regra.get("tipo", "sempre"), int(regra.get("n") or 1)
    a_cada = f" (a cada {n} meses)" if n > 1 else ""
    if tipo == "dia_mes":
        return f"no dia {regra['dia']} do mês{a_cada}"
    if tipo == "ultimo_dia_mes":
        return f"no último dia do mês{a_cada}"
    if tipo == "dias_semana":
        nomes = [DIAS_SEMANA[d][:3] for d in regra.get("dias", [])]
        return "em " + ", ".join(nomes)
    if tipo == "semana_mes":
        nome = DIAS_SEMANA[int(regra["dia"])]
        quando = "na última" if int(regra["nth"]) == -1 else f"na {int(regra['nth'])}ª"
        return f"{quando} {nome} do mês{a_cada}"
    if tipo == "cada_dias":
        return f"a cada {n} dias" if n > 1 else "todo dia"
    return ""
