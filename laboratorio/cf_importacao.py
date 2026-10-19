"""Importação de planilhas (xlsx/csv) para o Retrabalho CF, com mapeamento coluna -> campo do sistema."""
import hashlib
import re
from collections import Counter
from datetime import date, datetime, timedelta

from django.db import transaction

from maquinas.models import Maquina

from . import cf_retrabalho as cf
from .hc_importacao import _atualizar_horas, _compacto, _data, _hora, _int, ler_planilha  # noqa: F401  (ler_planilha reexportada para as views)
from .hc_rendimento import norm
from .models import (
    CFCadastro,
    CFCampoFormulario,
    RegraTurnoCoating,
    RetrabalhoCFItem,
    RetrabalhoCFRegistro,
    TratamentoAntiReflexo,
)

ANO_MIN = 2020
LOTE = 500

# (chave, rótulo, obrigatório, cabeçalhos aceitos — sem espaços/acentos)
CAMPOS_FIXOS = [
    ("id", "Id do registro (evita duplicar ao reimportar)", False, ["ID"]),
    ("data", "Data do lote", True, ["DATA"]),
    ("data_ref", "Data/hora de preenchimento (hora do lançamento; corrige datas com dia/mês invertidos)", False, ["STARTTIME", "COMPLETIONTIME", "HORA", "HORADOLANCAMENTO"]),
    ("turno", "Turno", False, ["TURNO"]),
    ("numero_lote", "Número do lote", False, ["NUMERODOLOTE", "LOTE"]),
    ("total_lentes", "Total de lentes no lote", True, ["TOTALDELENTESNOLOTE", "TOTALDELENTES"]),
    ("maquina", "Máquina", False, ["MAQUINA"]),
    ("tratamento", "Tratamento", False, ["TRATAMENTO"]),
    ("colaborador_cf", "Colaborador CF (inspeção do lote)", False, ["COLABORADORCFRESPONSAVELINSPECAODOLOTE", "COLABORADORCF"]),
    ("colaborador_ar", "Colaborador AR (montagem do lote)", False, ["COLABORADORARRESPONSAVELMONTAGEMLOTE", "COLABORADORAR"]),
    ("lote_reprovado", "Lote reprovado? (Sim/Não)", False, ["LOTEREPROVADO"]),
    ("motivo_reprovacao", "Motivo da reprovação", False, ["MOTIVODAREPROVACAO"]),
    ("observacoes", "Observações", False, ["OBSERVACOES", "OBSERVACAO"]),
]


def alvos():
    out = [{"chave": k, "rotulo": r, "obrigatorio": o, "grupo": "Dados do lote"} for k, r, o, _a in CAMPOS_FIXOS]
    for origem, nome in CFCadastro.ORIGEM_CHOICES:
        for m in CFCadastro.objects.filter(tipo="MOTIVO", grupo=origem, ativo=True):
            out.append({"chave": f"mt_{m.pk}", "rotulo": f"Retrabalho {origem} — {m.nome}", "obrigatorio": False, "grupo": f"Retrabalho por motivo — {nome}"})
    for c in CFCampoFormulario.objects.filter(sistema=False):
        out.append({"chave": f"x_{c.chave}", "rotulo": c.rotulo, "obrigatorio": False, "grupo": "Perguntas personalizadas"})
    return out


def sugerir_mapa(cabecalhos):
    comp = [_compacto(c) for c in cabecalhos]
    usados, mapa = set(), {}
    for chave, _r, _o, aliases in CAMPOS_FIXOS:
        for a in aliases:
            i = next((i for i, c in enumerate(comp) if c == a and i not in usados), None)
            if i is not None:
                mapa[chave] = i
                usados.add(i)
                break
    # motivos: o cabeçalho começa por "RETRABALHO"+origem e contém o nome do motivo (vale o nome mais longo)
    motivos = list(CFCadastro.objects.filter(tipo="MOTIVO", ativo=True))
    for i, c in enumerate(comp):
        if i in usados:
            continue
        for origem in ("AR", "HC", "CF"):
            if c.startswith("RETRABALHO" + origem):
                cand = [m for m in motivos if m.grupo == origem and _compacto(m.nome) in c[len("RETRABALHO" + origem):] and f"mt_{m.pk}" not in mapa]
                if cand:
                    m = max(cand, key=lambda m: len(_compacto(m.nome)))
                    mapa[f"mt_{m.pk}"] = i
                    usados.add(i)
                break
    for c in CFCampoFormulario.objects.filter(sistema=False):
        i = next((i for i, x in enumerate(comp) if x == _compacto(c.rotulo) and i not in usados), None)
        if i is not None:
            mapa[f"x_{c.chave}"] = i
            usados.add(i)
    return mapa


def _sim(v):
    return norm(str(v or "")) in ("SIM", "S", "TRUE", "1", "YES")


def _data_corrigida(dia, ref):
    """Data lançada vs data/hora de preenchimento: se destoar >1 dia e trocar dia<->mês resolver, usa a trocada."""
    if not ref or abs((dia - ref).days) <= 1:
        return dia, False
    if dia.day <= 12:
        try:
            trocada = dia.replace(day=dia.month, month=dia.day)
        except ValueError:
            trocada = None
        if trocada and abs((trocada - ref).days) <= 1:
            return trocada, True
    return dia, False


def importar(linhas, mapa, a_partir=None, simular=False, usuario=None):
    cf.garantir_padroes()
    mapa = {k: int(v) for k, v in mapa.items() if v not in (None, "")}
    if "data" not in mapa or "total_lentes" not in mapa:
        raise ValueError("Relacione ao menos as colunas de Data e de Total de lentes no lote.")

    def cel(row, chave):
        i = mapa.get(chave)
        return row[i] if i is not None and i < len(row) else None

    trats = {norm(t.nome): t for t in TratamentoAntiReflexo.objects.all()}
    turnos = {norm(t.nome): t for t in RegraTurnoCoating.objects.all()}
    turnos_num = {}
    for t in RegraTurnoCoating.objects.all():
        m = re.search(r"[1-9]", t.nome)
        if m:
            turnos_num.setdefault(int(m.group()), t)
    maquinas = list(Maquina.objects.all())
    candidatos, preferidos = cf.candidatos_colaborador(), cf.preferidos_colaborador()
    cache = {}
    reprov_nomes = {norm(n) for n in CFCadastro.objects.filter(tipo="REPROVACAO").values_list("nome", flat=True)}
    mt = [(k, int(k[3:])) for k in mapa if k.startswith("mt_")]
    extras_keys = [k for k in mapa if k.startswith("x_")]

    existentes = set(RetrabalhoCFRegistro.objects.exclude(chave_importacao=None).values_list("chave_importacao", flat=True))
    hoje = date.today()
    novos, pendentes, st = [], [], Counter()
    horas_existentes = {}
    sem_turno, sem_trat, sem_maq = Counter(), Counter(), Counter()

    for row in linhas:
        dia = _data(cel(row, "data"))
        if not dia or dia.year < ANO_MIN or dia > date(hoje.year + 1, 12, 31):
            st["ignoradas"] += 1
            continue
        ref = _data(cel(row, "data_ref")) if "data_ref" in mapa else None
        dia, corrigida = _data_corrigida(dia, ref)
        if corrigida:
            st["datas_corrigidas"] += 1
        if a_partir and dia < a_partir:
            st["antes_do_corte"] += 1
            continue
        id_ext = _int(cel(row, "id")) if "id" in mapa else 0
        chave = f"id:{id_ext}" if id_ext else "sha:" + hashlib.md5(repr(tuple(row)).encode()).hexdigest()[:24]
        hora = _hora(cel(row, "data_ref")) if "data_ref" in mapa else None
        hora = hora or _hora(cel(row, "data"))
        if chave in existentes:
            st["repetidas"] += 1
            if hora:
                horas_existentes[chave] = hora
            continue
        existentes.add(chave)

        turno_txt = str(cel(row, "turno") or "").strip()
        turno = turnos.get(norm(turno_txt))
        if not turno and turno_txt:
            m = re.search(r"[1-9]", turno_txt)
            turno = turnos_num.get(int(m.group())) if m else None
        if turno_txt and not turno:
            sem_turno[turno_txt] += 1

        def pessoa(chave_campo):
            nome = str(cel(row, chave_campo) or "").strip()
            if (chave_campo, nome) not in cache:
                cache[(chave_campo, nome)] = cf.resolver_colaborador(nome, candidatos, preferidos)
            return nome, cache[(chave_campo, nome)]

        nome_cf, colab_cf = pessoa("colaborador_cf")
        nome_ar, colab_ar = pessoa("colaborador_ar")
        maq_txt = str(cel(row, "maquina") or "").strip()
        if ("m", maq_txt) not in cache:
            cache[("m", maq_txt)] = cf.resolver_maquina(maq_txt, maquinas)
        maq = cache[("m", maq_txt)]
        if maq_txt and not maq:
            sem_maq[maq_txt] += 1
        trat_txt = str(cel(row, "tratamento") or "").strip()
        trat = trats.get(norm(trat_txt))
        if trat_txt and not trat:
            sem_trat[trat_txt] += 1

        itens = [(cid, _int(cel(row, k))) for k, cid in mt if _int(cel(row, k))]
        total = sum(q for _c, q in itens)
        qtd = _int(cel(row, "total_lentes"))
        reprovado = _sim(cel(row, "lote_reprovado"))
        extras = {}
        for k in extras_keys:
            v = cel(row, k)
            if v not in (None, ""):
                extras[k[2:]] = v.isoformat() if isinstance(v, (date, datetime)) else v
        numero = cel(row, "numero_lote")
        novos.append(RetrabalhoCFRegistro(
            data=dia, hora=hora, turno=turno, turno_nome=turno.nome if turno else turno_txt[:50],
            numero_lote=("" if numero is None else str(int(numero)) if isinstance(numero, float) and numero.is_integer() else str(numero)).strip()[:30],
            total_lentes=qtd, maquina=maq, maquina_nome=cf.nome_maquina(maq) if maq else maq_txt[:100],
            tratamento=trat, tratamento_nome=trat.nome if trat else trat_txt[:150],
            colaborador_cf=colab_cf, colaborador_cf_nome=colab_cf.nome_completo if colab_cf else nome_cf[:150],
            colaborador_ar=colab_ar, colaborador_ar_nome=colab_ar.nome_completo if colab_ar else nome_ar[:150],
            teve_retrabalho=total > 0, qtd_retrabalho=total, reprovado=reprovado,
            motivo_reprovacao=str(cel(row, "motivo_reprovacao") or "")[:150] if reprovado else "",
            observacoes=str(cel(row, "observacoes") or "")[:2000], extras=extras,
            origem=RetrabalhoCFRegistro.ORIGEM_IMPORT, chave_importacao=chave, usuario=usuario,
        ))
        pendentes.append(itens)
        if qtd == 0 or total > qtd:
            st["a_revisar"] += 1

    resultado = {
        "validas": len(novos), "repetidas": st["repetidas"], "ignoradas": st["ignoradas"], "antes_do_corte": st["antes_do_corte"],
        "datas_corrigidas": st["datas_corrigidas"], "a_revisar": st["a_revisar"],
        "com_colaborador": sum(1 for r in novos if r.colaborador_cf_id),
        "sem_colaborador": sorted({r.colaborador_cf_nome for r in novos if not r.colaborador_cf_id and r.colaborador_cf_nome})[:30],
        "turno_sem_regra": dict(sem_turno), "maquina_sem_cadastro": dict(sem_maq), "tratamento_sem_cadastro": dict(sem_trat),
        "simulado": simular, "importadas": 0,
    }
    resultado["horas_preenchidas"] = len(horas_existentes) if simular else _atualizar_horas(RetrabalhoCFRegistro, horas_existentes)
    if simular or not novos:
        return resultado
    with transaction.atomic():
        for ini in range(0, len(novos), LOTE):
            lote = novos[ini: ini + LOTE]
            RetrabalhoCFRegistro.objects.bulk_create(lote)
            ids = {r.chave_importacao: r.pk for r in RetrabalhoCFRegistro.objects.filter(chave_importacao__in=[r.chave_importacao for r in lote])}
            itens = []
            for reg, pend in zip(lote, pendentes[ini: ini + LOTE]):
                pk = reg.pk or ids.get(reg.chave_importacao)
                itens += [RetrabalhoCFItem(registro_id=pk, motivo_id=cid, quantidade=q) for cid, q in pend if pk]
            RetrabalhoCFItem.objects.bulk_create(itens)
    resultado["importadas"] = len(novos)
    return resultado
