"""Expansão de recorrência e consulta de ocorrências da Agenda."""
import calendar
from datetime import date, datetime, timedelta

from django.utils import timezone

from django.db.models import Q

from agenda import regras
from agenda.models import (
    Checklist,
    ChecklistCompartilhamento,
    ChecklistDiarioConclusao,
    Evento,
    EventoConclusao,
    ItemConclusao,
)

LIMITE_OCORRENCIAS = 1000  # proteção contra intervalos gigantes


def _add_months(d: date, meses: int) -> date:
    m = d.month - 1 + meses
    ano, mes = d.year + m // 12, m % 12 + 1
    return d.replace(year=ano, month=mes, day=min(d.day, calendar.monthrange(ano, mes)[1]))


def datas_do_evento(evento: Evento, de: date, ate: date):
    """Datas (no fuso local) em que o evento ocorre dentro de [de, ate]."""
    inicio = timezone.localtime(evento.inicio).date()
    limite = min(ate, evento.recorrencia_ate) if evento.recorrencia_ate else ate
    if evento.recorrencia == Evento.REC_NENHUMA:
        fim = timezone.localtime(evento.fim).date() if evento.fim else inicio
        # evento de vários dias aparece em cada dia do intervalo
        d, saida = max(inicio, de), []
        while d <= min(fim, ate) and len(saida) < LIMITE_OCORRENCIAS:
            saida.append((d, inicio))
            d += timedelta(days=1)
        return saida
    saida, n = [], 0
    while len(saida) < LIMITE_OCORRENCIAS:
        if evento.recorrencia == Evento.REC_DIARIA:
            d = inicio + timedelta(days=n)
        elif evento.recorrencia == Evento.REC_SEMANAL:
            d = inicio + timedelta(weeks=n)
        else:
            d = _add_months(inicio, n)
        if d > limite:
            break
        if d >= de:
            saida.append((d, d))
        n += 1
    return saida


def agrupar(itens, condicoes=None):
    """Itens (dicts com "grupo" e "feito") agrupados na ordem em que aparecem: [{nome, itens, feitos, total, condicao}].

    `condicoes` {nome do agrupamento: texto da condição especial} (opcional).
    """
    condicoes = condicoes or {}
    grupos = []
    for it in itens:
        if not grupos or grupos[-1]["nome"] != it["grupo"]:
            grupos.append({"nome": it["grupo"], "itens": [], "condicao": condicoes.get(it["grupo"], "")})
        grupos[-1]["itens"].append(it)
    for g in grupos:
        g["total"] = len(g["itens"])
        g["feitos"] = sum(1 for i in g["itens"] if i["feito"])
    return grupos


def referencia_do_checklist(c):
    """Data de partida do checklist (referência de intervalos e meses): `diario_desde` ou a de criação."""
    return c.diario_desde or timezone.localtime(c.criado_em).date()


def itens_do_dia(c, itens, dia):
    """Itens do checklist que valem em `dia`: os de agrupamentos sem condição e os cuja condição especial se cumpre.

    Devolve (itens, {nome do agrupamento: texto da condição}).
    """
    grupos = list(c.grupos.all())
    if not grupos:
        return list(itens), {}
    ref = referencia_do_checklist(c)
    por_nome = {g.nome: g.regra for g in grupos}
    visiveis = [i for i in itens if regras.aplica(por_nome.get(i.grupo), dia, ref)]
    return visiveis, {g.nome: regras.descrever(g.regra) for g in grupos}


def ocorrencias(user, de: date, ate: date, so_checklist=False, editor=None):
    """Lista de dicts (um por dia/ocorrência) visíveis para o usuário no intervalo.

    `editor` é quem está olhando (a chefia, ao vistoriar um liderado): define o campo "editavel".
    """
    editor = editor or user
    qs = Evento.visiveis_para(user).select_related("criado_por", "checklist_modelo").prefetch_related("checklist_modelo__itens", "checklist_modelo__grupos")
    if so_checklist:
        qs = qs.filter(Q(checklist=True) | Q(checklist_modelo__isnull=False))
    # só eventos que podem tocar o intervalo: sem recorrência até o fim, ou recorrentes ainda vigentes
    fim_dt = timezone.make_aware(datetime.combine(ate, datetime.min.time())) + timedelta(days=1)
    qs = qs.filter(inicio__lt=fim_dt)
    eventos = list(qs)
    feitos = set(
        EventoConclusao.objects.filter(usuario=user, data__gte=de, data__lte=ate, evento__in=eventos).values_list(
            "evento_id", "data"
        )
    )
    itens_feitos = {}
    for ev_id, item_id, dia in ItemConclusao.objects.filter(
        usuario=user, data__gte=de, data__lte=ate, evento__in=eventos
    ).values_list("evento_id", "item_id", "data"):
        itens_feitos.setdefault((ev_id, dia), set()).add(item_id)
    saida = []
    for ev in eventos:
        modelo = ev.checklist_modelo
        itens_modelo = list(modelo.itens.all()) if modelo else []
        inicio_local = timezone.localtime(ev.inicio)
        duracao = (ev.fim - ev.inicio) if ev.fim else None
        for dia, base in datas_do_evento(ev, de, ate):
            marcados = itens_feitos.get((ev.id, dia), set())
            visiveis, condicoes = itens_do_dia(modelo, itens_modelo, dia) if modelo else ([], {})
            if so_checklist and modelo and itens_modelo and not visiveis:
                continue  # nenhum agrupamento do checklist vale neste dia
            itens = [{"id": i.id, "texto": i.texto, "grupo": i.grupo, "feito": i.id in marcados} for i in visiveis]
            # com modelo associado, a ocorrência só está "feita" quando todos os itens estão marcados
            feito = (bool(itens) and all(i["feito"] for i in itens)) if modelo else (ev.id, dia) in feitos
            saida.append(
                {
                    "tipo": "evento",
                    "origem": "",
                    "checklist_id": None,
                    "id": ev.id,
                    "titulo": ev.titulo,
                    "descricao": ev.descricao,
                    "local": ev.local,
                    "escopo": ev.escopo,
                    "cor": ev.cor,
                    "dia": dia,
                    "hora_inicio": None if ev.dia_inteiro else inicio_local.time(),
                    "hora_fim": (
                        None
                        if ev.dia_inteiro or not duracao or ev.recorrencia == Evento.REC_NENHUMA and dia != base
                        else (inicio_local + duracao).time()
                    ),
                    "dia_inteiro": ev.dia_inteiro,
                    "checklist": ev.checklist or modelo is not None,
                    "checklist_titulo": modelo.titulo if modelo else "",
                    "itens": itens,
                    "grupos": agrupar(itens, condicoes),
                    "feito": feito,
                    "recorrente": ev.recorrencia != Evento.REC_NENHUMA,
                    "editavel": ev.pode_editar(editor),
                }
            )
    saida.sort(key=lambda o: (o["dia"], o["hora_inicio"] or datetime.min.time(), o["titulo"]))
    return saida


def datas_do_checklist(c: Checklist, inicio: date, ate: date):
    """Datas em [inicio, ate] em que o checklist recorrente vale, conforme a periodicidade.

    A referência (semana ou mês de partida) é `diario_desde`.
    """
    ref = referencia_do_checklist(c)
    if c.periodicidade == Checklist.PER_CADA_DIAS:  # a cada N dias, a partir da referência
        passo = max(1, c.intervalo)
        d = ref if inicio <= ref else ref + timedelta(days=-(-(inicio - ref).days // passo) * passo)
        saida = []
        while d <= ate and len(saida) < LIMITE_OCORRENCIAS:
            saida.append(d)
            d += timedelta(days=passo)
        return saida
    passo_meses = c.passo_meses
    if passo_meses:
        dia_mes = c.dia_mes or ref.day
        m_ref = ref.year * 12 + ref.month - 1
        m = inicio.year * 12 + inicio.month - 1
        saida = []
        while m <= ate.year * 12 + ate.month - 1 and len(saida) < LIMITE_OCORRENCIAS:
            if (m - m_ref) % passo_meses == 0:
                ano, mes = divmod(m, 12)
                d = date(ano, mes + 1, min(dia_mes, calendar.monthrange(ano, mes + 1)[1]))
                if inicio <= d <= ate:
                    saida.append(d)
            m += 1
        return saida
    dias = c.dias_set
    semana_ref = ref - timedelta(days=ref.weekday())
    passo_semanas = {Checklist.PER_QUINZENAL: 2, Checklist.PER_CADA_SEMANAS: max(1, c.intervalo)}.get(c.periodicidade, 1)
    saida, d = [], inicio
    while d <= ate and len(saida) < LIMITE_OCORRENCIAS:
        if d.weekday() in dias and ((d - timedelta(days=d.weekday()) - semana_ref).days // 7) % passo_semanas == 0:
            saida.append(d)
        d += timedelta(days=1)
    return saida


def checklists_diarios(user, de: date, ate: date, so_agenda=False):
    """Ocorrências dos checklists diários do usuário (um por dia válido), no mesmo formato de `ocorrencias`.

    so_agenda=True devolve só os que o usuário quis mostrar no calendário como atividade fixa.
    """
    recebidos = dict(ChecklistCompartilhamento.objects.filter(usuario=user).values_list("checklist_id", "desde"))
    qs = (
        Checklist.objects.filter(diario=True)
        .filter(Q(criado_por=user, incluir_dono=True) | Q(pk__in=recebidos.keys()))
        .select_related("criado_por")
        .prefetch_related("itens", "grupos")
    )
    if so_agenda:
        qs = qs.filter(na_agenda=True)
    checklists = list(qs)
    if not checklists:
        return []
    marcados = {}
    for item_id, dia, ck_id in ChecklistDiarioConclusao.objects.filter(
        usuario=user, data__gte=de, data__lte=ate, item__checklist__in=checklists
    ).values_list("item_id", "data", "item__checklist_id"):
        marcados.setdefault((ck_id, dia), set()).add(item_id)
    saida = []
    for c in checklists:
        itens_modelo = list(c.itens.all())
        inicio = max(x for x in (de, c.diario_desde, recebidos.get(c.id)) if x)  # recebido: vale da data do envio
        recebido = c.criado_por_id != user.pk
        for dia in datas_do_checklist(c, inicio, ate):
            feitos = marcados.get((c.id, dia), set())
            visiveis, condicoes = itens_do_dia(c, itens_modelo, dia)
            if itens_modelo and not visiveis:
                continue  # todos os agrupamentos têm condição e nenhuma vale neste dia
            itens = [{"id": i.id, "texto": i.texto, "grupo": i.grupo, "feito": i.id in feitos} for i in visiveis]
            saida.append(
                {
                    "tipo": "checklist_diario",
                    "checklist_id": c.id,
                    "id": c.id,
                    "titulo": c.titulo,
                    "origem": (c.criado_por.get_full_name() or c.criado_por.username) if recebido else "",
                    "descricao": c.descricao,
                    "local": "",
                    "escopo": Evento.ESCOPO_PESSOAL,
                    "cor": c.cor,
                    "dia": dia,
                    "hora_inicio": c.hora,
                    "hora_fim": None,
                    "dia_inteiro": c.hora is None,
                    "checklist": True,
                    "checklist_titulo": c.titulo,
                    "itens": itens,
                    "grupos": agrupar(itens, condicoes),
                    "feito": bool(itens) and all(i["feito"] for i in itens),
                    "recorrente": True,
                    "editavel": not recebido,
                }
            )
    saida.sort(key=lambda o: (o["dia"], o["hora_inicio"] or datetime.min.time(), o["titulo"]))
    return saida


def agenda_do_periodo(user, de: date, ate: date, editor=None):
    """Eventos + checklists diários marcados para aparecer na agenda (atividades fixas)."""
    todos = ocorrencias(user, de, ate, editor=editor) + checklists_diarios(user, de, ate, so_agenda=True)
    todos.sort(key=lambda o: (o["dia"], o["hora_inicio"] or datetime.min.time(), o["titulo"]))
    return todos


def checklist_do_dia(user, dia: date):
    """Tudo o que entra no Checklist do dia: eventos com checklist + checklists diários (com ou sem agenda)."""
    todos = ocorrencias(user, dia, dia, so_checklist=True) + checklists_diarios(user, dia, dia)
    todos.sort(key=lambda o: (o["hora_inicio"] or datetime.min.time(), o["titulo"]))
    return todos
