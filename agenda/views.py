import json
from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from agenda.models import Evento, EventoConclusao, EventoParticipante
from agenda.services import ocorrencias
from shared.permissions import user_has_nav_perm

User = get_user_model()
PERM_CRIAR_COMUM = "core.nav_agenda_criar_comum"
MAX_INTERVALO_DIAS = 62


def _nome(u):
    return u.get_full_name() or u.username


def _parse_data(valor, padrao=None):
    try:
        return date.fromisoformat(valor)
    except (TypeError, ValueError):
        return padrao


def _serializa(o):
    return {
        "id": o["id"],
        "titulo": o["titulo"],
        "descricao": o["descricao"],
        "local": o["local"],
        "escopo": o["escopo"],
        "cor": o["cor"],
        "dia": o["dia"].isoformat(),
        "hora_inicio": o["hora_inicio"].strftime("%H:%M") if o["hora_inicio"] else None,
        "hora_fim": o["hora_fim"].strftime("%H:%M") if o["hora_fim"] else None,
        "dia_inteiro": o["dia_inteiro"],
        "checklist": o["checklist"],
        "feito": o["feito"],
        "recorrente": o["recorrente"],
        "editavel": o["editavel"],
    }


@login_required
def calendario_view(request):
    usuarios = User.objects.filter(is_active=True).exclude(pk=request.user.pk).order_by("first_name", "username")
    return render(
        request,
        "agenda/calendario.html",
        {
            "usuarios": [{"id": u.id, "nome": _nome(u)} for u in usuarios],
            "pode_criar_comum": user_has_nav_perm(request.user, PERM_CRIAR_COMUM),
        },
    )


@login_required
@require_GET
def api_eventos(request):
    hoje = timezone.localdate()
    de = _parse_data(request.GET.get("inicio"), hoje)
    ate = _parse_data(request.GET.get("fim"), de + timedelta(days=30))
    if ate < de or (ate - de).days > MAX_INTERVALO_DIAS:
        return JsonResponse({"success": False, "error": "Intervalo inválido."}, status=400)
    return JsonResponse({"success": True, "eventos": [_serializa(o) for o in ocorrencias(request.user, de, ate)]})


@login_required
@require_GET
def api_evento_detalhe(request, evento_id):
    ev = get_object_or_404(Evento.visiveis_para(request.user), pk=evento_id)
    inicio = timezone.localtime(ev.inicio)
    fim = timezone.localtime(ev.fim) if ev.fim else None
    return JsonResponse(
        {
            "success": True,
            "evento": {
                "id": ev.id,
                "titulo": ev.titulo,
                "descricao": ev.descricao,
                "local": ev.local,
                "escopo": ev.escopo,
                "inicio": inicio.strftime("%Y-%m-%dT%H:%M"),
                "fim": fim.strftime("%Y-%m-%dT%H:%M") if fim else "",
                "dia_inteiro": ev.dia_inteiro,
                "recorrencia": ev.recorrencia,
                "recorrencia_ate": ev.recorrencia_ate.isoformat() if ev.recorrencia_ate else "",
                "checklist": ev.checklist,
                "lembrete_minutos": ev.lembrete_minutos,
                "cor": ev.cor,
                "criador": _nome(ev.criado_por),
                "editavel": ev.pode_editar(request.user),
                "participantes": [
                    {"id": c.usuario_id, "nome": _nome(c.usuario), "resposta": c.resposta}
                    for c in ev.convites.select_related("usuario")
                ],
                "minha_resposta": next(
                    (c.resposta for c in ev.convites.all() if c.usuario_id == request.user.id), None
                ),
            },
        }
    )


def _aware(valor):
    if not valor:
        return None
    dt = datetime.fromisoformat(valor)
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt


@login_required
@require_POST
def evento_salvar(request):
    try:
        d = json.loads(request.body or "{}")
    except ValueError:
        return JsonResponse({"success": False, "error": "JSON inválido."}, status=400)

    titulo = (d.get("titulo") or "").strip()
    if not titulo:
        return JsonResponse({"success": False, "error": "Informe o título."}, status=400)
    try:
        inicio = _aware(d.get("inicio"))
        fim = _aware(d.get("fim"))
    except ValueError:
        return JsonResponse({"success": False, "error": "Data/hora inválida."}, status=400)
    if not inicio:
        return JsonResponse({"success": False, "error": "Informe o início."}, status=400)
    if fim and fim < inicio:
        return JsonResponse({"success": False, "error": "O fim não pode ser antes do início."}, status=400)

    escopo = d.get("escopo") if d.get("escopo") in (Evento.ESCOPO_PESSOAL, Evento.ESCOPO_COMUM) else Evento.ESCOPO_PESSOAL
    recorrencia = d.get("recorrencia") if d.get("recorrencia") in dict(Evento.RECORRENCIAS) else Evento.REC_NENHUMA
    rec_ate = _parse_data(d.get("recorrencia_ate"))
    if recorrencia != Evento.REC_NENHUMA and rec_ate and rec_ate < timezone.localtime(inicio).date():
        return JsonResponse({"success": False, "error": "'Repetir até' é anterior ao início."}, status=400)
    lembrete = d.get("lembrete_minutos")
    lembrete = int(lembrete) if str(lembrete or "").isdigit() else None
    cor = d.get("cor") if isinstance(d.get("cor"), str) and len(d["cor"]) == 7 and d["cor"].startswith("#") else "#0d6efd"

    ev_id = d.get("id")
    if ev_id:
        ev = get_object_or_404(Evento, pk=ev_id)
        if not ev.pode_editar(request.user):
            return JsonResponse({"success": False, "error": "Só o criador pode editar este evento."}, status=403)
    else:
        ev = Evento(criado_por=request.user)
    if escopo == Evento.ESCOPO_COMUM and ev.escopo != Evento.ESCOPO_COMUM and not user_has_nav_perm(
        request.user, PERM_CRIAR_COMUM
    ):
        return JsonResponse({"success": False, "error": "Sem permissão para criar na Agenda Comum."}, status=403)

    with transaction.atomic():
        ev.titulo, ev.descricao, ev.local = titulo, (d.get("descricao") or "").strip(), (d.get("local") or "").strip()
        ev.escopo, ev.inicio, ev.fim = escopo, inicio, fim
        ev.dia_inteiro = bool(d.get("dia_inteiro"))
        ev.recorrencia, ev.recorrencia_ate = recorrencia, rec_ate if recorrencia != Evento.REC_NENHUMA else None
        ev.checklist, ev.lembrete_minutos, ev.cor = bool(d.get("checklist")), lembrete, cor
        ev.save()

        ids = {int(i) for i in (d.get("participantes") or []) if str(i).isdigit()} - {request.user.id}
        validos = set(User.objects.filter(pk__in=ids, is_active=True).values_list("pk", flat=True))
        ev.convites.exclude(usuario_id__in=validos).delete()
        for uid in validos:
            EventoParticipante.objects.get_or_create(evento=ev, usuario_id=uid)
    _invalida_inbox(ev)
    return JsonResponse({"success": True, "id": ev.id})


@login_required
@require_POST
def evento_excluir(request, evento_id):
    ev = get_object_or_404(Evento.visiveis_para(request.user), pk=evento_id)
    if not ev.pode_editar(request.user):
        return JsonResponse({"success": False, "error": "Só o criador pode excluir este evento."}, status=403)
    _invalida_inbox(ev)
    ev.delete()
    return JsonResponse({"success": True})


@login_required
@require_POST
def api_responder_convite(request, evento_id):
    try:
        resposta = json.loads(request.body or "{}").get("resposta")
    except ValueError:
        resposta = None
    if resposta not in (EventoParticipante.ACEITO, EventoParticipante.RECUSADO):
        return JsonResponse({"success": False, "error": "Resposta inválida."}, status=400)
    convite = get_object_or_404(EventoParticipante, evento_id=evento_id, usuario=request.user)
    convite.resposta = resposta
    convite.save(update_fields=["resposta"])
    _invalida_inbox(None, request.user)
    return JsonResponse({"success": True})


@login_required
def checklist_view(request):
    dia = _parse_data(request.GET.get("data"), timezone.localdate())
    itens = ocorrencias(request.user, dia, dia, so_checklist=True)
    return render(
        request,
        "agenda/checklist.html",
        {
            "dia": dia,
            "anterior": dia - timedelta(days=1),
            "proximo": dia + timedelta(days=1),
            "eh_hoje": dia == timezone.localdate(),
            "itens": itens,
            "total": len(itens),
            "feitos": sum(1 for i in itens if i["feito"]),
        },
    )


@login_required
@require_POST
def api_checklist_toggle(request, evento_id):
    ev = get_object_or_404(Evento.visiveis_para(request.user), pk=evento_id, checklist=True)
    try:
        dia = _parse_data(json.loads(request.body or "{}").get("data"))
    except ValueError:
        dia = None
    if not dia:
        return JsonResponse({"success": False, "error": "Data inválida."}, status=400)
    # a data precisa ser uma ocorrência real do evento
    if not any(o["id"] == ev.id for o in ocorrencias(request.user, dia, dia, so_checklist=True)):
        return JsonResponse({"success": False, "error": "O item não ocorre nesta data."}, status=400)
    obj, criado = EventoConclusao.objects.get_or_create(evento=ev, usuario=request.user, data=dia)
    if not criado:
        obj.delete()
    _invalida_inbox(None, request.user)
    return JsonResponse({"success": True, "feito": criado})


def _invalida_inbox(evento, user=None):
    try:
        from shared.inbox import invalidar_cache_inbox

        if user is not None:
            invalidar_cache_inbox(user)
        if evento is not None:
            invalidar_cache_inbox(evento.criado_por)
            for uid in evento.convites.values_list("usuario_id", flat=True):
                invalidar_cache_inbox(uid)
    except Exception:
        pass
