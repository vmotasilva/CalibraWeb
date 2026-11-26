"""Expansão de recorrência e consulta de ocorrências da Agenda."""
import calendar
from datetime import date, datetime, timedelta

from django.utils import timezone

from django.db.models import Q

from agenda.models import Checklist, ChecklistDiarioConclusao, Evento, EventoConclusao, ItemConclusao

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


def ocorrencias(user, de: date, ate: date, so_checklist=False, editor=None):
    """Lista de dicts (um por dia/ocorrência) visíveis para o usuário no intervalo.

    `editor` é quem está olhando (a chefia, ao vistoriar um liderado): define o campo "editavel".
    """
    editor = editor or user
    qs = Evento.visiveis_para(user).select_related("criado_por", "checklist_modelo").prefetch_related("checklist_modelo__itens")
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
            itens = [{"id": i.id, "texto": i.texto, "feito": i.id in marcados} for i in itens_modelo]
            # com modelo associado, a ocorrência só está "feita" quando todos os itens estão marcados
            feito = (bool(itens) and all(i["feito"] for i in itens)) if modelo else (ev.id, dia) in feitos
            saida.append(
                {
                    "tipo": "evento",
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
                    "feito": feito,
                    "recorrente": ev.recorrencia != Evento.REC_NENHUMA,
                    "editavel": ev.pode_editar(editor),
                }
            )
    saida.sort(key=lambda o: (o["dia"], o["hora_inicio"] or datetime.min.time(), o["titulo"]))
    return saida


def checklists_diarios(user, de: date, ate: date, so_agenda=False):
    """Ocorrências dos checklists diários do usuário (um por dia válido), no mesmo formato de `ocorrencias`.

    so_agenda=True devolve só os que o usuário quis mostrar no calendário como atividade fixa.
    """
    qs = Checklist.objects.filter(criado_por=user, diario=True).prefetch_related("itens")
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
        dias_validos = c.dias_set
        itens_modelo = list(c.itens.all())
        dia, n = max(de, c.diario_desde) if c.diario_desde else de, 0
        while dia <= ate and n < LIMITE_OCORRENCIAS:
            if dia.weekday() in dias_validos:
                feitos = marcados.get((c.id, dia), set())
                itens = [{"id": i.id, "texto": i.texto, "feito": i.id in feitos} for i in itens_modelo]
                saida.append(
                    {
                        "tipo": "checklist_diario",
                        "checklist_id": c.id,
                        "id": c.id,
                        "titulo": c.titulo,
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
                        "feito": bool(itens) and all(i["feito"] for i in itens),
                        "recorrente": True,
                        "editavel": True,
                    }
                )
                n += 1
            dia += timedelta(days=1)
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
