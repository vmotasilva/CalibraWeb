"""Execuções da Auditoria Livre: criar uma nova execução a partir de uma concluída e comparar a evolução.

Uma nova execução copia a estrutura da anterior (solicitações, itens, tópicos e auditados) com os dados
limpos (evidência em branco, classificação Pendente). Cada item novo guarda o item de origem em `anterior`,
o que permite comparar, item a item, o que foi resolvido, o que persiste e o que piorou.
"""
from datetime import date

from django.db import transaction

from ..models import AuditoriaLivre, SolicitacaoLivre

# Gravidade de cada classificação: C e N/A = 0, OM = 1, NC = 2.
GRAVIDADE = {"C": 0, "NA": 0, "OM": 1, "NC": 2}
ABERTOS = ("NC", "OM", "P")  # o que uma execução "só pendências" volta a avaliar

# código -> (rótulo, classe de cor Bootstrap)
CATEGORIAS = {
    "RESOLVIDO": ("Resolvido", "success"),
    "MELHOROU": ("Melhorou", "info"),
    "MANTIDO": ("Mantido conforme", "secondary"),
    "PERSISTE": ("Persiste", "warning"),
    "PIOROU": ("Piorou", "danger"),
    "NOVO": ("Item novo", "primary"),
    "PENDENTE": ("Ainda pendente", "light"),
    "AVALIADO": ("Avaliado agora", "info"),
    "REMOVIDO": ("Removido", "dark"),
    "NAO_REAVALIADO": ("Não reavaliado (estava conforme)", "secondary"),
}
ORDEM_CATEGORIAS = ["PIOROU", "PERSISTE", "MELHOROU", "RESOLVIDO", "AVALIADO", "NOVO", "PENDENTE", "MANTIDO",
                    "NAO_REAVALIADO", "REMOVIDO"]
CLASSES = ("C", "NC", "OM", "NA", "P")
ROTULO_CLASSE = dict(SolicitacaoLivre.CLASSIFICACAO_CHOICES)


class ExecucaoInvalida(Exception):
    """A nova execução não pode ser criada (mensagem em português para o usuário)."""


def pode_criar_nova_execucao(aud):
    """(ok, motivo). Só a última execução de uma auditoria concluída gera a próxima."""
    if aud.status != "CONCLUIDA":
        return False, "Conclua a auditoria antes de abrir uma nova execução."
    if aud.proximas.exists():
        return False, "Esta auditoria já tem uma nova execução."
    return True, ""


def criar_nova_execucao(aud, user, somente_pendencias=False):
    ok, motivo = pode_criar_nova_execucao(aud)
    if not ok:
        raise ExecucaoInvalida(motivo)
    with transaction.atomic():
        nova = AuditoriaLivre.objects.create(
            titulo=aud.titulo, objetivo=aud.objetivo, escopo=aud.escopo, criterio=aud.criterio, local=aud.local,
            auditor_lider=aud.auditor_lider, auditados=aud.auditados, data_inicio=date.today(),
            status="PLANEJADA", anterior=aud, execucao=aud.execucao + 1,
            somente_pendencias=bool(somente_pendencias), criado_por=user,
        )
        nova.auditores.set(aud.auditores.all())

        # agrupa por solicitação (linha original + itens extras), na ordem em que foram criadas
        grupos, por_raiz = [], {}
        for linha in aud.solicitacoes.order_by("ordem", "id"):
            raiz = linha.pai_id or linha.pk
            if raiz not in por_raiz:
                por_raiz[raiz] = []
                grupos.append(por_raiz[raiz])
            por_raiz[raiz].append(linha)

        ordem = 0
        for itens in grupos:
            if somente_pendencias:
                itens = [i for i in itens if i.conclusao in ABERTOS]
            if not itens:
                continue
            ordem += 1
            raiz_nova = None
            for velho in itens:
                novo = SolicitacaoLivre.objects.create(
                    auditoria=nova, pai=raiz_nova, topico=velho.topico, auditado=velho.auditado,
                    solicitacao=velho.solicitacao, ordem=ordem, anterior=velho, criado_por=user,
                )
                raiz_nova = raiz_nova or novo  # o primeiro item que entra vira a linha original
    return nova


# ---------------------------------------------------------------- comparação

def indice_conformidade(res):
    """% de conformes entre os itens classificados (sem N/A e pendentes); None se ainda não há classificados."""
    classificados = res["C"] + res["NC"] + res["OM"]
    return round(res["C"] * 100 / classificados, 1) if classificados else None


def _contar(linhas):
    res = {c: 0 for c in CLASSES}
    for l in linhas:
        res[l.conclusao] += 1
    res["total"] = len(linhas)
    res["indice"] = indice_conformidade(res)
    return res


def _categoria(velho, novo):
    if velho is None:
        return "NOVO"
    if novo.conclusao == "P":
        return "PENDENTE"
    if velho.conclusao == "P":
        return "AVALIADO"
    gv, gn = GRAVIDADE[velho.conclusao], GRAVIDADE[novo.conclusao]
    if gn < gv:
        return "RESOLVIDO" if gn == 0 else "MELHOROU"
    if gn > gv:
        return "PIOROU"
    return "MANTIDO" if gn == 0 else "PERSISTE"


def serie(aud):
    """Resumo de cada execução da série, em ordem — alimenta o gráfico de evolução."""
    out = []
    for a in aud.cadeia():
        res = _contar(list(a.solicitacoes.all()))
        out.append({"aud": a, "execucao": a.execucao, "data": a.data_inicio, "status": a.status, "res": res})
    return out


def _numeros(execucao):
    ids = execucao.solicitacoes.order_by("ordem", "id").values_list("id", flat=True)
    return {i: n for n, i in enumerate(ids, start=1)}


def _por_topico(linhas):
    topicos = {}
    for l in linhas:
        topicos.setdefault(l.topico or "", []).append(l)
    return topicos


def comparar(atual, base):
    """Compara `atual` com `base` (uma execução anterior da mesma série). Retorna um dict para tela e relatórios."""
    cadeia = atual.cadeia()
    ids = [a.pk for a in cadeia]
    if base.pk not in ids or atual.pk not in ids or ids.index(base.pk) >= ids.index(atual.pk):
        raise ExecucaoInvalida("A execução de comparação precisa ser anterior à atual, na mesma série.")

    linhas_atual = list(atual.solicitacoes.order_by("ordem", "id"))
    linhas_base = list(base.solicitacoes.order_by("ordem", "id"))
    todas = {l.pk: l for l in SolicitacaoLivre.objects.filter(auditoria_id__in=ids)}

    def ancestral(linha):
        r = linha
        while r is not None and r.auditoria_id != base.pk:
            r = todas.get(r.anterior_id) if r.anterior_id else None
        return r

    num_atual, num_base = _numeros(atual), _numeros(base)
    itens, casadas = [], set()
    for linha in linhas_atual:
        velho = ancestral(linha)
        if velho is not None:
            casadas.add(velho.pk)
        itens.append({"atual": linha, "base": velho, "categoria": _categoria(velho, linha),
                      "n_atual": num_atual[linha.pk], "n_base": num_base.get(velho.pk) if velho else None})
    for velho in linhas_base:
        if velho.pk in casadas:
            continue
        sem_reavaliar = atual.somente_pendencias and velho.conclusao in ("C", "NA")
        itens.append({"atual": None, "base": velho, "categoria": "NAO_REAVALIADO" if sem_reavaliar else "REMOVIDO",
                      "n_atual": None, "n_base": num_base[velho.pk]})

    ordem_cat = {c: i for i, c in enumerate(ORDEM_CATEGORIAS)}
    itens.sort(key=lambda i: (ordem_cat[i["categoria"]], i["n_atual"] or 10**6, i["n_base"] or 10**6))
    for i in itens:
        i["rotulo"], i["cor"] = CATEGORIAS[i["categoria"]]

    contagem = {c: 0 for c in ORDEM_CATEGORIAS}
    for i in itens:
        contagem[i["categoria"]] += 1

    res_atual, res_base = _contar(linhas_atual), _contar(linhas_base)
    deltas = {c: res_atual[c] - res_base[c] for c in (*CLASSES, "total")}
    deltas["indice"] = (
        round(res_atual["indice"] - res_base["indice"], 1)
        if res_atual["indice"] is not None and res_base["indice"] is not None else None
    )

    topicos = []
    tp_atual, tp_base = _por_topico(linhas_atual), _por_topico(linhas_base)
    for nome in sorted(set(tp_atual) | set(tp_base), key=lambda t: (t == "", t.casefold())):
        auditados = []
        for l in tp_atual.get(nome, []) + tp_base.get(nome, []):
            if l.auditado and l.auditado not in auditados:
                auditados.append(l.auditado)
        topicos.append({"topico": nome, "auditados": auditados,
                        "antes": _contar(tp_base.get(nome, [])), "depois": _contar(tp_atual.get(nome, []))})

    return {
        "atual": atual, "base": base, "res_atual": res_atual, "res_base": res_base, "deltas": deltas,
        "itens": itens, "contagem": contagem, "topicos": topicos, "serie": serie(atual),
        "categorias": [(c, *CATEGORIAS[c], contagem[c]) for c in ORDEM_CATEGORIAS],
    }


# ------------------------------------------------------------------ dashboard

def _parse_data(valor):
    try:
        return date.fromisoformat(str(valor or "").strip())
    except ValueError:
        return None


def dados_dashboard(inicio=None, fim=None):
    """Evolução das Auditorias Livres para o dashboard: uma série por auditoria (primeira execução → última).

    `inicio` e `fim` (AAAA-MM-DD) filtram as execuções pela data de início; datas inválidas são ignoradas.
    Auditorias arquivadas ficam de fora.
    """
    from django.db.models import Count

    inicio, fim = _parse_data(inicio), _parse_data(fim)
    todas = {
        a.pk: a for a in AuditoriaLivre.objects.filter(arquivada=False).only(
            "id", "titulo", "anterior_id", "execucao", "data_inicio", "status")
    }

    def raiz_de(a):
        vistos = set()
        while a.anterior_id in todas and a.pk not in vistos:  # se a anterior foi arquivada/excluída, esta vira a primeira
            vistos.add(a.pk)
            a = todas[a.anterior_id]
        return a.pk

    por_serie = {}
    for a in todas.values():
        if (inicio and a.data_inicio < inicio) or (fim and a.data_inicio > fim):
            continue
        por_serie.setdefault(raiz_de(a), []).append(a)

    ids = [a.pk for execs in por_serie.values() for a in execs]
    contagens = {}
    for linha in (SolicitacaoLivre.objects.filter(auditoria_id__in=ids)
                  .values("auditoria_id", "conclusao").annotate(n=Count("id"))):
        contagens.setdefault(linha["auditoria_id"], {})[linha["conclusao"]] = linha["n"]

    series = []
    for execs in por_serie.values():
        execs.sort(key=lambda a: (a.execucao, a.pk))
        itens = []
        for a in execs:
            res = {c: contagens.get(a.pk, {}).get(c, 0) for c in CLASSES}
            res["total"] = sum(res.values())
            res["indice"] = indice_conformidade(res)
            itens.append({"id": a.pk, "execucao": a.execucao, "data": f"{a.data_inicio:%d/%m/%Y}",
                          "status": a.get_status_display(), **res})
        series.append({"id": execs[0].pk, "titulo": execs[-1].titulo, "ultima_id": execs[-1].pk, "execucoes": itens})
    series.sort(key=lambda s: s["titulo"].casefold())

    ultimas = [s["execucoes"][-1] for s in series]
    indices_ultimos = [u["indice"] for u in ultimas if u["indice"] is not None]
    variacoes = [
        round(s["execucoes"][-1]["indice"] - s["execucoes"][0]["indice"], 1)
        for s in series
        if len(s["execucoes"]) > 1 and s["execucoes"][-1]["indice"] is not None and s["execucoes"][0]["indice"] is not None
    ]
    for s in series:
        primeira, ultima = s["execucoes"][0], s["execucoes"][-1]
        s["variacao"] = (round(ultima["indice"] - primeira["indice"], 1)
                         if len(s["execucoes"]) > 1 and ultima["indice"] is not None and primeira["indice"] is not None else None)
    return {
        "series": series,
        "kpis": {
            "auditorias": len(series),
            "execucoes": len(ids),
            "com_evolucao": sum(1 for s in series if len(s["execucoes"]) > 1),
            "indice_medio": round(sum(indices_ultimos) / len(indices_ultimos), 1) if indices_ultimos else None,
            "variacao_media": round(sum(variacoes) / len(variacoes), 1) if variacoes else None,
            "nc_abertas": sum(u["NC"] for u in ultimas),
        },
    }
