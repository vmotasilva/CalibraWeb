import json
from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from agenda.models import (
    Checklist,
    ChecklistDiarioConclusao,
    ChecklistItem,
    Evento,
    EventoConclusao,
    EventoParticipante,
    ItemConclusao,
)
from agenda.hierarquia import equipe_de, nome_do_usuario, pode_gerir, papel_sobre
from agenda.services import agenda_do_periodo, checklist_do_dia, checklists_diarios, ocorrencias
from shared.permissions import user_has_nav_perm

User = get_user_model()
PERM_CRIAR_COMUM = "core.nav_agenda_criar_comum"
MAX_INTERVALO_DIAS = 62


def _nome(u):
    return u.get_full_name() or u.username


def _alvo(request, valor=None):
    """Usuário cuja agenda/checklists estão em foco: o próprio ou um liderado (para quem é chefia)."""
    bruto = valor if valor is not None else request.GET.get("usuario")
    if not str(bruto or "").isdigit() or int(bruto) == request.user.pk:
        return request.user
    alvo = User.objects.filter(pk=int(bruto), is_active=True).first()
    if not alvo or not pode_gerir(request.user, alvo):
        raise PermissionDenied
    return alvo


def _ctx_alvo(request, alvo):
    """Contexto comum das telas: de quem é a agenda e se o usuário é chefia (para o banner e links)."""
    gerindo = alvo.pk != request.user.pk
    return {
        "alvo": alvo,
        "alvo_nome": nome_do_usuario(alvo),
        "gerindo": gerindo,
        "alvo_papel": papel_sobre(request.user, alvo) if gerindo else "",
        "alvo_qs": f"?usuario={alvo.pk}" if gerindo else "",
        "alvo_id": alvo.pk if gerindo else "",
        "eh_chefia": request.user.is_superuser or bool(equipe_de(request.user)),
    }


def _ajuste(obj, request):
    """Registra que a chefia criou/ajustou em nome do dono (e limpa quando o próprio dono edita)."""
    if request.user.pk != obj.criado_por_id:
        obj.ajustado_por, obj.ajustado_em = request.user, timezone.now()
    else:
        obj.ajustado_por, obj.ajustado_em = None, None


def _parse_data(valor, padrao=None):
    try:
        return date.fromisoformat(valor)
    except (TypeError, ValueError):
        return padrao


def _serializa(o):
    return {
        "tipo": o["tipo"],
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
        "checklist_titulo": o["checklist_titulo"],
        "itens_total": len(o["itens"]),
        "itens_feitos": sum(1 for i in o["itens"] if i["feito"]),
        "feito": o["feito"],
        "recorrente": o["recorrente"],
        "editavel": o["editavel"],
    }


@login_required
def calendario_view(request):
    alvo = _alvo(request)
    usuarios = User.objects.filter(is_active=True).exclude(pk=alvo.pk).order_by("first_name", "username")
    return render(
        request,
        "agenda/calendario.html",
        {
            "usuarios": [{"id": u.id, "nome": _nome(u)} for u in usuarios],
            "pode_criar_comum": user_has_nav_perm(request.user, PERM_CRIAR_COMUM),
            "checklists": [{"id": c.id, "titulo": c.titulo} for c in Checklist.objects.filter(criado_por=alvo)],
            **_ctx_alvo(request, alvo),
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
    return JsonResponse({"success": True, "eventos": [_serializa(o) for o in agenda_do_periodo(_alvo(request), de, ate, editor=request.user)]})


@login_required
@require_GET
def api_evento_detalhe(request, evento_id):
    alvo = _alvo(request)
    ev = get_object_or_404(Evento.visiveis_para(alvo), pk=evento_id)
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
                "checklist_modelo": ev.checklist_modelo_id,
                "lembrete_minutos": ev.lembrete_minutos,
                "cor": ev.cor,
                "criador": _nome(ev.criado_por),
                "ajustado_por": _nome(ev.ajustado_por) if ev.ajustado_por_id else "",
                "ajustado_em": timezone.localtime(ev.ajustado_em).strftime("%d/%m/%Y %H:%M") if ev.ajustado_em else "",
                "editavel": ev.pode_editar(request.user),
                "participantes": [
                    {"id": c.usuario_id, "nome": _nome(c.usuario), "resposta": c.resposta}
                    for c in ev.convites.select_related("usuario")
                ],
                "minha_resposta": next(
                    (c.resposta for c in ev.convites.all() if c.usuario_id == alvo.id and alvo.id == request.user.id), None
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
            return JsonResponse({"success": False, "error": "Só o criador ou a chefia dele pode editar este evento."}, status=403)
    else:
        ev = Evento(criado_por=_alvo(request, d.get("usuario") or ""))  # chefia cria direto na agenda do liderado

    modelo = None
    if d.get("checklist_modelo"):
        modelo = Checklist.objects.filter(pk=d["checklist_modelo"], criado_por=ev.criado_por).first()
        if not modelo:
            return JsonResponse({"success": False, "error": "Checklist inválido."}, status=400)
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
        ev.checklist_modelo = modelo
        _ajuste(ev, request)
        ev.save()

        ids = {int(i) for i in (d.get("participantes") or []) if str(i).isdigit()} - {ev.criado_por_id}
        validos = set(User.objects.filter(pk__in=ids, is_active=True).values_list("pk", flat=True))
        ev.convites.exclude(usuario_id__in=validos).delete()
        for uid in validos:
            EventoParticipante.objects.get_or_create(evento=ev, usuario_id=uid)
    _invalida_inbox(ev)
    return JsonResponse({"success": True, "id": ev.id})


@login_required
@require_POST
def evento_excluir(request, evento_id):
    ev = get_object_or_404(Evento, pk=evento_id)
    if not ev.pode_editar(request.user):
        if not Evento.visiveis_para(request.user).filter(pk=ev.pk).exists():
            return JsonResponse({"success": False, "error": "Evento não encontrado."}, status=404)
        return JsonResponse({"success": False, "error": "Só o criador ou a chefia dele pode excluir este evento."}, status=403)
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
    alvo = _alvo(request)
    dia = _parse_data(request.GET.get("data"), timezone.localdate())
    itens = checklist_do_dia(alvo, dia)
    return render(
        request,
        "agenda/checklist.html",
        {
            **_ctx_alvo(request, alvo),
            "somente_leitura": alvo.pk != request.user.pk,
            "dia": dia,
            "anterior": dia - timedelta(days=1),
            "proximo": dia + timedelta(days=1),
            "eh_hoje": dia == timezone.localdate(),
            "itens": itens,
            "total": sum(len(i["itens"]) or 1 for i in itens),
            "feitos": sum(sum(1 for x in i["itens"] if x["feito"]) if i["itens"] else int(i["feito"]) for i in itens),
        },
    )


@login_required
@require_POST
def api_checklist_toggle(request, evento_id):
    ev = get_object_or_404(Evento.visiveis_para(request.user), pk=evento_id, checklist=True, checklist_modelo__isnull=True)
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


@login_required
@require_POST
def api_item_toggle(request, evento_id, item_id):
    """Marca/desmarca um item do checklist associado a um evento, numa ocorrência (dia)."""
    ev = get_object_or_404(Evento.visiveis_para(request.user), pk=evento_id, checklist_modelo__isnull=False)
    item = get_object_or_404(ChecklistItem, pk=item_id, checklist_id=ev.checklist_modelo_id)
    try:
        dia = _parse_data(json.loads(request.body or "{}").get("data"))
    except ValueError:
        dia = None
    if not dia:
        return JsonResponse({"success": False, "error": "Data inválida."}, status=400)
    if not any(o["id"] == ev.id for o in ocorrencias(request.user, dia, dia, so_checklist=True)):
        return JsonResponse({"success": False, "error": "O item não ocorre nesta data."}, status=400)
    obj, criado = ItemConclusao.objects.get_or_create(evento=ev, item=item, usuario=request.user, data=dia)
    if not criado:
        obj.delete()
    _invalida_inbox(None, request.user)
    return JsonResponse({"success": True, "feito": criado})


# ----------------------------------------------------------------------------------------------
# Checklists (modelos): criados direto e depois associados a eventos/rotinas
# ----------------------------------------------------------------------------------------------
@login_required
def equipe_view(request):
    """Vistoria da chefia: situação do dia (checklists e agenda) de cada liderado."""
    dia = _parse_data(request.GET.get("data"), timezone.localdate())
    linhas = []
    for m in equipe_de(request.user):
        itens = checklist_do_dia(m["usuario"], dia)
        total = sum(len(i["itens"]) or 1 for i in itens)
        feitos = sum(sum(1 for x in i["itens"] if x["feito"]) if i["itens"] else int(i["feito"]) for i in itens)
        eventos = [o for o in agenda_do_periodo(m["usuario"], dia, dia) if o["tipo"] == "evento"]
        if not total:
            situacao = "sem"
        elif feitos == total:
            situacao = "completo"
        elif feitos:
            situacao = "andamento"
        else:
            situacao = "pendente"
        linhas.append(
            {
                "usuario": m["usuario"],
                "nome": m["colaborador"].nome_completo,
                "cargo": m["colaborador"].cargo or "",
                "setor": getattr(m["colaborador"].setor, "nome", "") if m["colaborador"].setor_id else "",
                "papel": m["papel"],
                "checklists": len(itens),
                "total": total,
                "feitos": feitos,
                "pct": round(100 * feitos / total) if total else 0,
                "eventos": len(eventos),
                "situacao": situacao,
            }
        )
    com_checklist = [l for l in linhas if l["total"]]
    return render(
        request,
        "agenda/equipe.html",
        {
            "dia": dia,
            "anterior": dia - timedelta(days=1),
            "proximo": dia + timedelta(days=1),
            "eh_hoje": dia == timezone.localdate(),
            "linhas": linhas,
            "resumo": {
                "pessoas": len(linhas),
                "completos": sum(1 for l in linhas if l["situacao"] == "completo"),
                "pendentes": sum(1 for l in linhas if l["situacao"] in ("pendente", "andamento")),
                "sem": sum(1 for l in linhas if l["situacao"] == "sem"),
                "pct_geral": round(100 * sum(l["feitos"] for l in com_checklist) / sum(l["total"] for l in com_checklist)) if com_checklist else 0,
            },
        },
    )


@login_required
def checklists_view(request):
    alvo = _alvo(request)
    qs = Checklist.objects.prefetch_related("itens").select_related("ajustado_por").filter(criado_por=alvo)
    return render(request, "agenda/checklists.html", {"checklists": qs, **_ctx_alvo(request, alvo)})


@login_required
@require_POST
def api_diario_toggle(request, checklist_id, item_id):
    """Marca/desmarca um item de checklist diário (independe de evento) num dia."""
    c = get_object_or_404(Checklist, pk=checklist_id, criado_por=request.user, diario=True)
    item = get_object_or_404(ChecklistItem, pk=item_id, checklist=c)
    try:
        dia = _parse_data(json.loads(request.body or "{}").get("data"))
    except ValueError:
        dia = None
    if not dia:
        return JsonResponse({"success": False, "error": "Data inválida."}, status=400)
    if not any(o["checklist_id"] == c.id for o in checklists_diarios(request.user, dia, dia)):
        return JsonResponse({"success": False, "error": "O checklist não vale nesta data."}, status=400)
    obj, criado = ChecklistDiarioConclusao.objects.get_or_create(item=item, usuario=request.user, data=dia)
    if not criado:
        obj.delete()
    _invalida_inbox(None, request.user)
    return JsonResponse({"success": True, "feito": criado})


def _checklist_do_usuario(request, checklist_id):
    """Checklist que o usuário pode ajustar: o próprio, de liderado (chefia) ou qualquer um (superusuário)."""
    c = get_object_or_404(Checklist, pk=checklist_id)
    if not c.pode_editar(request.user):
        raise Http404
    return c


@login_required
@require_GET
def api_checklist_detalhe(request, checklist_id):
    c = _checklist_do_usuario(request, checklist_id)
    return JsonResponse(
        {
            "success": True,
            "checklist": {
                "id": c.id,
                "titulo": c.titulo,
                "descricao": c.descricao,
                "diario": c.diario,
                "dias_semana": sorted(c.dias_set),
                "hora": c.hora.strftime("%H:%M") if c.hora else "",
                "na_agenda": c.na_agenda,
                "cor": c.cor,
                "ajustado_por": _nome(c.ajustado_por) if c.ajustado_por_id else "",
                "itens": [{"id": i.id, "texto": i.texto} for i in c.itens.all()],
                "eventos": [{"id": e.id, "titulo": e.titulo} for e in c.eventos.all()],
            },
        }
    )


@login_required
@require_POST
def checklist_salvar(request):
    try:
        d = json.loads(request.body or "{}")
    except ValueError:
        return JsonResponse({"success": False, "error": "JSON inválido."}, status=400)
    titulo = (d.get("titulo") or "").strip()
    if not titulo:
        return JsonResponse({"success": False, "error": "Informe o título do checklist."}, status=400)
    itens = [{"id": i.get("id"), "texto": (i.get("texto") or "").strip()} for i in (d.get("itens") or []) if isinstance(i, dict)]
    itens = [i for i in itens if i["texto"]]
    if not itens:
        return JsonResponse({"success": False, "error": "Adicione pelo menos um item."}, status=400)
    if len(itens) > 100 or any(len(i["texto"]) > 300 for i in itens):
        return JsonResponse({"success": False, "error": "Máximo de 100 itens de até 300 caracteres."}, status=400)

    dias = sorted({int(x) for x in (d.get("dias_semana") or []) if str(x).isdigit() and 0 <= int(x) <= 6})
    if d.get("diario") and not dias:
        return JsonResponse({"success": False, "error": "Escolha pelo menos um dia da semana."}, status=400)
    try:
        hora = datetime.strptime(d["hora"], "%H:%M").time() if d.get("hora") else None
    except ValueError:
        return JsonResponse({"success": False, "error": "Horário inválido."}, status=400)
    cor = d.get("cor") if isinstance(d.get("cor"), str) and len(d["cor"]) == 7 and d["cor"].startswith("#") else "#20c997"

    with transaction.atomic():
        if d.get("id"):
            c = _checklist_do_usuario(request, d["id"])
        else:
            c = Checklist(criado_por=_alvo(request, d.get("usuario") or ""))  # chefia cria para o liderado
        c.titulo, c.descricao = titulo[:200], (d.get("descricao") or "").strip()
        eram_diario = c.diario
        c.diario = bool(d.get("diario"))
        c.dias_semana = ",".join(str(x) for x in dias)
        c.hora = hora
        c.na_agenda = c.diario and bool(d.get("na_agenda"))
        c.cor = cor
        if c.diario and (not eram_diario or not c.diario_desde):
            c.diario_desde = timezone.localdate()  # vale a partir de hoje; dias passados não viram pendência
        _ajuste(c, request)
        c.save()
        existentes = {i.id: i for i in c.itens.all()}
        mantidos = set()
        for ordem, i in enumerate(itens):
            item = existentes.get(int(i["id"])) if str(i["id"] or "").isdigit() else None
            if item:
                item.texto, item.ordem = i["texto"], ordem
                item.save(update_fields=["texto", "ordem"])
                mantidos.add(item.id)
            else:
                ChecklistItem.objects.create(checklist=c, texto=i["texto"], ordem=ordem)
        c.itens.exclude(id__in=mantidos).filter(id__in=existentes.keys()).delete()
    return JsonResponse({"success": True, "id": c.id})


@login_required
@require_POST
def checklist_excluir(request, checklist_id):
    c = _checklist_do_usuario(request, checklist_id)
    c.delete()  # eventos associados ficam sem checklist (SET_NULL)
    _invalida_inbox(None, request.user)
    return JsonResponse({"success": True})


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
