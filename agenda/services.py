"""Expansão de recorrência e consulta de ocorrências da Agenda."""
import calendar
from datetime import date, datetime, timedelta

from django.utils import timezone

from django.db.models import Q

from agenda.models import Evento, EventoConclusao, ItemConclusao

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


def ocorrencias(user, de: date, ate: date, so_checklist=False):
    """Lista de dicts (um por dia/ocorrência) visíveis para o usuário no intervalo."""
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
                    "editavel": ev.pode_editar(user),
                }
            )
    saida.sort(key=lambda o: (o["dia"], o["hora_inicio"] or datetime.min.time(), o["titulo"]))
    return saida
