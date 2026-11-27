import json
from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from agenda.models import (
    Checklist,
    ChecklistCompartilhamento,
    ChecklistDiarioConclusao,
    ChecklistGrupo,
    ChecklistCompartilhado,
    ChecklistItem,
    CompartilhadoCobranca,
    CompartilhadoMembro,
    CompartilhadoTarefa,
    Evento,
    EventoConclusao,
    EventoParticipante,
    ItemConclusao,
)
from agenda import regras
from agenda.hierarquia import equipe_de, liderados_ids, nome_do_usuario, papel_sobre, pode_gerir
from agenda.services import acompanhamento, agenda_do_periodo, checklist_do_dia, checklists_diarios, ocorrencias
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
    """Meu checklist: acompanhamento único de todos os checklists ativos do usuário (ou do liderado, para a chefia)."""
    alvo = _alvo(request)
    dia = _parse_data(request.GET.get("data"), timezone.localdate())
    ac = acompanhamento(alvo, dia)
    por_lista = []  # itens compartilhados agrupados pelo checklist de origem, na ordem de aparição
    for t in ac["compartilhados"]:
        if not por_lista or por_lista[-1]["lista_id"] != t["lista_id"]:
            por_lista.append({"lista_id": t["lista_id"], "titulo": t["lista_titulo"], "cor": t["cor"], "itens": []})
        por_lista[-1]["itens"].append(t)
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
            "itens": ac["itens"],
            "compartilhados": por_lista,
            "pendencias": ac["pendencias"],
            "pendencias_total": ac["pendencias_total"],
            "total": ac["total"],
            "feitos": ac["feitos"],
            "total_dia": ac["total_dia"],
            "feitos_dia": ac["feitos_dia"],
            "total_compartilhados": ac["total_compartilhados"],
            "feitos_compartilhados": ac["feitos_compartilhados"],
            # onde um item avulso pode entrar neste dia: nos próprios checklists que ocorrem nele
            "destinos_avulso": [
                {"id": o["id"], "titulo": o["titulo"], "grupos": sorted({g["nome"] for g in o["grupos"] if g["nome"]})}
                for o in ac["itens"]
                if o["tipo"] == "checklist_diario" and not o["origem"]
            ],
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
    ocorr = next((o for o in ocorrencias(request.user, dia, dia, so_checklist=True) if o["id"] == ev.id), None)
    if not ocorr:
        return JsonResponse({"success": False, "error": "O item não ocorre nesta data."}, status=400)
    if item.id not in {i["id"] for i in ocorr["itens"]}:  # agrupamento com condição especial que não vale neste dia
        return JsonResponse({"success": False, "error": "Este item não vale nesta data (condição do agrupamento)."}, status=400)
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
        ac = acompanhamento(m["usuario"], dia)  # os mesmos números do "Meu checklist" do liderado
        itens, total, feitos = ac["itens"], ac["total"], ac["feitos"]
        eventos = [o for o in agenda_do_periodo(m["usuario"], dia, dia) if o["tipo"] == "evento"]
        acoes = list(CompartilhadoTarefa.objects.filter(responsavel=m["usuario"], concluida=False, lista__arquivado=False))
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
                "pendencias": ac["pendencias_total"],
                "acoes_pendentes": len(acoes),
                "acoes_atrasadas": sum(1 for a in acoes if a.prazo and a.prazo < timezone.localdate()),
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
    qs = (
        Checklist.objects.prefetch_related("itens", "compartilhamentos__usuario")
        .select_related("ajustado_por")
        .filter(criado_por=alvo)
    )
    recebidos = Checklist.objects.filter(compartilhamentos__usuario=alvo).select_related("criado_por").prefetch_related("itens")
    liderados = (
        [{"id": m["usuario"].pk, "nome": m["colaborador"].nome_completo, "papel": m["papel"]} for m in equipe_de(request.user)]
        if alvo.pk == request.user.pk
        else []
    )
    return render(
        request,
        "agenda/checklists.html",
        {"checklists": qs, "recebidos": recebidos, "liderados": liderados, "periodicidades": Checklist.PERIODICIDADES, **_ctx_alvo(request, alvo)},
    )


@login_required
@require_POST
def api_diario_toggle(request, checklist_id, item_id):
    """Marca/desmarca um item de checklist diário (independe de evento) num dia."""
    visiveis = Checklist.objects.filter(
        Q(criado_por=request.user, incluir_dono=True) | Q(compartilhamentos__usuario=request.user)
    ).distinct()
    c = get_object_or_404(visiveis, pk=checklist_id, diario=True)  # o dono ou quem recebeu preenche a sua folha
    item = get_object_or_404(ChecklistItem, pk=item_id, checklist=c)
    try:
        dia = _parse_data(json.loads(request.body or "{}").get("data"))
    except ValueError:
        dia = None
    if not dia:
        return JsonResponse({"success": False, "error": "Data inválida."}, status=400)
    ocorr = next((o for o in checklists_diarios(request.user, dia, dia) if o["checklist_id"] == c.id), None)
    if not ocorr:
        return JsonResponse({"success": False, "error": "O checklist não vale nesta data."}, status=400)
    if item.id not in {i["id"] for i in ocorr["itens"]}:  # agrupamento com condição especial que não vale neste dia
        return JsonResponse({"success": False, "error": "Este item não vale nesta data (condição do agrupamento)."}, status=400)
    obj, criado = ChecklistDiarioConclusao.objects.get_or_create(item=item, usuario=request.user, data=dia)
    if not criado:
        obj.delete()
    _invalida_inbox(None, request.user)
    return JsonResponse({"success": True, "feito": criado})


AVULSOS_TITULO = "Itens avulsos"
MAX_DIAS_AVULSO = 366


def _lista_de_avulsos(user, desde):
    """Checklist pessoal que reúne os itens avulsos sem checklist de destino (criado na primeira vez que se usa)."""
    c = Checklist.objects.filter(criado_por=user, titulo=AVULSOS_TITULO, diario=True, incluir_dono=True).first()
    if not c:
        return Checklist.objects.create(
            titulo=AVULSOS_TITULO, criado_por=user, diario=True, diario_desde=desde, cor="#6c757d",
            descricao="Itens não fixos adicionados no Meu checklist.",
        )
    if c.diario_desde is None or desde < c.diario_desde:
        c.diario_desde = desde  # o item avulso pode ser de um dia anterior ao primeiro uso
        c.save(update_fields=["diario_desde"])
    return c


@login_required
@require_POST
def item_avulso_criar(request):
    """Adiciona um item não fixo ao Meu checklist: vale no dia escolhido (ou até uma data) e depois volta ao padrão."""
    try:
        d = json.loads(request.body or "{}")
    except ValueError:
        return JsonResponse({"success": False, "error": "JSON inválido."}, status=400)
    texto = (d.get("texto") or "").strip()
    if not texto or len(texto) > 300:
        return JsonResponse({"success": False, "error": "Informe o item (até 300 caracteres)."}, status=400)
    dia = _parse_data(d.get("data"))
    if not dia:
        return JsonResponse({"success": False, "error": "Data inválida."}, status=400)
    ate = _parse_data(d.get("ate")) if d.get("ate") else dia
    if not ate or ate < dia:
        return JsonResponse({"success": False, "error": "'Repetir até' deve ser a mesma data ou posterior."}, status=400)
    if (ate - dia).days > MAX_DIAS_AVULSO:
        return JsonResponse({"success": False, "error": f"O período do item avulso é de no máximo {MAX_DIAS_AVULSO} dias."}, status=400)
    grupo = (d.get("grupo") or "").strip()[:120]
    if d.get("checklist_id"):
        # só nos próprios checklists recorrentes (não nos recebidos da chefia)
        c = get_object_or_404(Checklist, pk=d["checklist_id"], criado_por=request.user, diario=True)
    else:
        c = _lista_de_avulsos(request.user, dia)
    ordem = (c.itens.aggregate(m=Max("ordem"))["m"] or 0) + 1
    item = ChecklistItem.objects.create(
        checklist=c, texto=texto, grupo=grupo, ordem=ordem, avulso=True, valido_desde=dia, valido_ate=ate
    )
    _invalida_inbox(None, request.user)
    return JsonResponse({"success": True, "id": item.id, "checklist_id": c.id})


@login_required
@require_POST
def item_avulso_excluir(request, item_id):
    """Remove um item avulso. Com marcações feitas, ele só deixa de valer a partir de hoje (o histórico fica)."""
    item = get_object_or_404(ChecklistItem, pk=item_id, avulso=True, checklist__criado_por=request.user)
    hoje = timezone.localdate()
    if item.conclusoes_diarias.exists() or item.conclusoes.exists():
        if item.valido_ate is None or item.valido_ate >= hoje:
            item.valido_ate = hoje - timedelta(days=1)
            item.save(update_fields=["valido_ate"])
    else:
        item.delete()
    _invalida_inbox(None, request.user)
    return JsonResponse({"success": True})


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
                "periodicidade": c.periodicidade,
                "intervalo": c.intervalo,
                "dia_mes": c.dia_mes,
                "condicoes": {g.nome: g.regra for g in c.grupos.all()},
                "desde": c.diario_desde.isoformat() if c.diario_desde else "",
                "hora": c.hora.strftime("%H:%M") if c.hora else "",
                "na_agenda": c.na_agenda,
                "cor": c.cor,
                "incluir_dono": c.incluir_dono,
                "compartilhar_com": list(c.compartilhamentos.values_list("usuario_id", flat=True)),
                "ajustado_por": _nome(c.ajustado_por) if c.ajustado_por_id else "",
                "itens": [{"id": i.id, "texto": i.texto, "grupo": i.grupo} for i in c.itens_vigentes],
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
    itens = [
        {"id": i.get("id"), "texto": (i.get("texto") or "").strip(), "grupo": (i.get("grupo") or "").strip()[:120]}
        for i in (d.get("itens") or [])
        if isinstance(i, dict)
    ]
    itens = [i for i in itens if i["texto"]]
    if not itens:
        return JsonResponse({"success": False, "error": "Adicione pelo menos um item."}, status=400)
    if len(itens) > 100 or any(len(i["texto"]) > 300 for i in itens):
        return JsonResponse({"success": False, "error": "Máximo de 100 itens de até 300 caracteres."}, status=400)

    dias = sorted({int(x) for x in (d.get("dias_semana") or []) if str(x).isdigit() and 0 <= int(x) <= 6})
    periodicidade = d.get("periodicidade") or Checklist.PER_DIARIA
    if periodicidade not in dict(Checklist.PERIODICIDADES):
        return JsonResponse({"success": False, "error": "Periodicidade inválida."}, status=400)
    por_mes = Checklist.por_mes(periodicidade)
    intervalo = 1
    if periodicidade in Checklist.LIMITE_INTERVALO:
        limite = Checklist.LIMITE_INTERVALO[periodicidade]
        if not str(d.get("intervalo") or "").isdigit() or not 1 <= int(d["intervalo"]) <= limite:
            return JsonResponse({"success": False, "error": f"Informe o intervalo (1 a {limite})."}, status=400)
        intervalo = int(d["intervalo"])
    desde = None
    if d.get("desde"):
        desde = _parse_data(d["desde"])
        if not desde:
            return JsonResponse({"success": False, "error": "Data de início inválida."}, status=400)
    dia_mes = None
    if d.get("diario") and por_mes:
        if not str(d.get("dia_mes") or "").isdigit() or not 1 <= int(d["dia_mes"]) <= 31:
            return JsonResponse({"success": False, "error": "Informe o dia do mês (1 a 31)."}, status=400)
        dia_mes = int(d["dia_mes"])
    elif d.get("diario") and Checklist.usa_dias_semana(periodicidade) and not dias:
        return JsonResponse({"success": False, "error": "Escolha pelo menos um dia da semana."}, status=400)
    # condições especiais dos agrupamentos: {nome: regra}; só ficam as que têm condição
    condicoes = {}
    nomes_itens = {i["grupo"] for i in itens}
    for g in d.get("grupos") or []:
        if not isinstance(g, dict) or not (g.get("nome") or "").strip():
            continue
        nome = g["nome"].strip()[:120]
        try:
            regra = regras.normaliza(g.get("regra"))
        except ValueError as e:
            return JsonResponse({"success": False, "error": f"Agrupamento “{nome}”: {e}"}, status=400)
        if regra["tipo"] != "sempre" and nome in nomes_itens:
            condicoes[nome] = regra
    try:
        hora = datetime.strptime(d["hora"], "%H:%M").time() if d.get("hora") else None
    except ValueError:
        return JsonResponse({"success": False, "error": "Horário inválido."}, status=400)
    cor = d.get("cor") if isinstance(d.get("cor"), str) and len(d["cor"]) == 7 and d["cor"].startswith("#") else "#20c997"

    compartilhar = None
    if d.get("compartilhar_com") is not None:
        compartilhar = {int(x) for x in d["compartilhar_com"] if str(x).isdigit()} - {request.user.pk}
        permitidos = (
            set(User.objects.filter(is_active=True).values_list("pk", flat=True))
            if request.user.is_superuser
            else liderados_ids(request.user)  # só a chefia distribui, e só aos seus liderados
        )
        if compartilhar - permitidos:
            return JsonResponse({"success": False, "error": "Só é possível compartilhar com os seus liderados."}, status=403)
        if compartilhar and not d.get("diario"):
            return JsonResponse({"success": False, "error": "Para compartilhar, marque como checklist diário."}, status=400)

    with transaction.atomic():
        if d.get("id"):
            c = _checklist_do_usuario(request, d["id"])
        else:
            c = Checklist(criado_por=_alvo(request, d.get("usuario") or ""))  # chefia cria para o liderado
        c.titulo, c.descricao = titulo[:200], (d.get("descricao") or "").strip()
        eram_diario = c.diario
        c.diario = bool(d.get("diario"))
        c.dias_semana = ",".join(str(x) for x in dias)
        mudou_per = (c.periodicidade, c.intervalo) != (periodicidade, intervalo)
        c.periodicidade, c.intervalo, c.dia_mes = periodicidade, intervalo, dia_mes
        c.hora = hora
        c.na_agenda = c.diario and bool(d.get("na_agenda"))
        c.cor = cor
        if c.diario and desde:
            c.diario_desde = desde  # "começa em": referência de intervalos e meses
        elif c.diario and (not eram_diario or not c.diario_desde or mudou_per):
            c.diario_desde = timezone.localdate()  # vale a partir de hoje; dias passados não viram pendência
        if c.criado_por_id == request.user.pk and compartilhar is not None:
            c.incluir_dono = bool(d.get("incluir_dono", True)) or not compartilhar  # sem destinatário, fica com o dono
        _ajuste(c, request)
        c.save()
        if c.criado_por_id == request.user.pk and compartilhar is not None:
            atuais = set(c.compartilhamentos.values_list("usuario_id", flat=True))
            c.compartilhamentos.exclude(usuario_id__in=compartilhar).delete()
            for uid in compartilhar - atuais:
                ChecklistCompartilhamento.objects.create(checklist=c, usuario_id=uid, desde=timezone.localdate())
        c.grupos.exclude(nome__in=condicoes.keys()).delete()
        for nome, regra in condicoes.items():
            ChecklistGrupo.objects.update_or_create(checklist=c, nome=nome, defaults={"regra": regra})
        # Itens têm validade por data: o que entra vale da data da mudança; o que sai deixa de valer a partir dela,
        # e os dias anteriores ficam como eram (as marcações antigas são preservadas).
        hoje = timezone.localdate()
        existentes = {i.id: i for i in c.itens_vigentes}  # só o cadastro padrão vigente (sem avulsos nem removidos)
        mantidos = set()
        for ordem, i in enumerate(itens):
            item = existentes.get(int(i["id"])) if str(i["id"] or "").isdigit() else None
            if item:
                item.texto, item.grupo, item.ordem = i["texto"], i["grupo"], ordem
                item.save(update_fields=["texto", "grupo", "ordem"])
                mantidos.add(item.id)
            else:
                ChecklistItem.objects.create(
                    checklist=c, texto=i["texto"], grupo=i["grupo"], ordem=ordem,
                    valido_desde=hoje if d.get("id") else None,  # checklist novo: vale desde o início
                )
        for item in existentes.values():
            if item.id in mantidos:
                continue
            if (item.valido_desde and item.valido_desde >= hoje) and not (
                item.conclusoes_diarias.exists() or item.conclusoes.exists()
            ):
                item.delete()  # criado hoje e retirado hoje, sem nenhuma marcação: não há histórico a preservar
            else:
                item.valido_ate = hoje - timedelta(days=1)
                item.save(update_fields=["valido_ate"])
    return JsonResponse({"success": True, "id": c.id})


@login_required
@require_POST
def checklist_excluir(request, checklist_id):
    c = _checklist_do_usuario(request, checklist_id)
    c.delete()  # eventos associados ficam sem checklist (SET_NULL)
    _invalida_inbox(None, request.user)
    return JsonResponse({"success": True})


# ----------------------------------------------------------------------------------------------
# Checklists compartilhados: itens com responsável e prazo, estado único para o grupo, com cobrança
# ----------------------------------------------------------------------------------------------
def _lista_visivel(request, lista_id):
    return get_object_or_404(ChecklistCompartilhado.visiveis_para(request.user), pk=lista_id)


def _resumo_lista(lista, hoje, user):
    tarefas = list(lista.tarefas.all())
    return {
        "lista": lista,
        "total": len(tarefas),
        "feitas": sum(1 for t in tarefas if t.concluida),
        "atrasadas": sum(1 for t in tarefas if t.atrasada(hoje)),
        "minhas": sum(1 for t in tarefas if not t.concluida and t.responsavel_id == user.pk),
        "membros": lista.membros.count(),
    }


@login_required
def compartilhados_view(request):
    hoje = timezone.localdate()
    listas = ChecklistCompartilhado.visiveis_para(request.user).select_related("criado_por").prefetch_related("tarefas", "membros")
    usuarios = User.objects.filter(is_active=True).exclude(pk=request.user.pk).order_by("first_name", "username")
    resumos = []
    for l in listas:
        r = _resumo_lista(l, hoje, request.user)
        r["pct"] = round(100 * r["feitas"] / r["total"]) if r["total"] else 0
        r["pode_editar"] = l.pode_editar(request.user)
        resumos.append(r)
    return render(
        request,
        "agenda/compartilhados.html",
        {"resumos": resumos, "usuarios": [{"id": u.id, "nome": _nome(u)} for u in usuarios], "eu": {"id": request.user.pk, "nome": _nome(request.user)}},
    )


@login_required
def compartilhado_detalhe_view(request, lista_id):
    lista = _lista_visivel(request, lista_id)
    hoje = timezone.localdate()
    tarefas = list(lista.tarefas.select_related("responsavel", "concluida_por"))
    pendencias = {}
    for t in tarefas:
        if not t.concluida and t.responsavel_id:
            d = pendencias.setdefault(t.responsavel_id, {"nome": _nome(t.responsavel), "pendentes": 0, "atrasadas": 0})
            d["pendentes"] += 1
            d["atrasadas"] += 1 if t.atrasada(hoje) else 0
    membros = [
        {"nome": _nome(m.usuario), "pendentes": pendencias.get(m.usuario_id, {}).get("pendentes", 0), "atrasadas": pendencias.get(m.usuario_id, {}).get("atrasadas", 0)}
        for m in lista.membros.select_related("usuario")
    ]
    cobradas_hoje = set(
        CompartilhadoCobranca.objects.filter(de=request.user, criado_em__date=hoje, tarefa__lista=lista).values_list("tarefa_id", flat=True)
    )
    # abrir o checklist é "ver a cobrança": some do sino
    CompartilhadoCobranca.objects.filter(para=request.user, tarefa__lista=lista, lida=False).update(lida=True)
    _invalida_inbox(None, request.user)
    eh_membro = lista.eh_membro(request.user)
    total = len(tarefas)
    feitas = sum(1 for t in tarefas if t.concluida)
    linhas = [
        {
            "obj": t,
            "atrasada": t.atrasada(hoje),
            "pode_cobrar": eh_membro and not t.concluida and t.responsavel_id not in (None, request.user.pk),
            "ja_cobrou": t.pk in cobradas_hoje,
            "responsavel_nome": _nome(t.responsavel) if t.responsavel_id else "",
            "concluida_por_nome": _nome(t.concluida_por) if t.concluida_por_id else "",
            "minha": t.responsavel_id == request.user.pk,
        }
        for t in tarefas
    ]
    grupos = []
    for l in linhas:  # agrupamentos na ordem em que aparecem
        if not grupos or grupos[-1]["nome"] != l["obj"].grupo:
            grupos.append({"nome": l["obj"].grupo, "tarefas": []})
        grupos[-1]["tarefas"].append(l)
    for g in grupos:
        g["total"] = len(g["tarefas"])
        g["feitas"] = sum(1 for l in g["tarefas"] if l["obj"].concluida)
    return render(
        request,
        "agenda/compartilhado_detalhe.html",
        {
            "grupos": grupos,
            "lista": lista,
            "membros": membros,
            "total": total,
            "feitas": feitas,
            "pct": round(100 * feitas / total) if total else 0,
            "atrasadas": sum(1 for t in tarefas if t.atrasada(hoje)),
            "pode_editar": lista.pode_editar(request.user),
            "eh_membro": eh_membro,
            "criador_nome": _nome(lista.criado_por),
        },
    )


@login_required
@require_GET
def api_compartilhado_detalhe(request, lista_id):
    lista = _lista_visivel(request, lista_id)
    if not lista.pode_editar(request.user):
        raise Http404
    return JsonResponse(
        {
            "success": True,
            "lista": {
                "id": lista.id,
                "titulo": lista.titulo,
                "descricao": lista.descricao,
                "cor": lista.cor,
                "criador": {"id": lista.criado_por_id, "nome": _nome(lista.criado_por)},
                "membros": [{"id": m.usuario_id, "nome": _nome(m.usuario)} for m in lista.membros.select_related("usuario") if m.usuario_id != lista.criado_por_id],
                "tarefas": [
                    {"id": t.id, "texto": t.texto, "grupo": t.grupo, "responsavel": t.responsavel_id, "prazo": t.prazo.isoformat() if t.prazo else ""}
                    for t in lista.tarefas.all()
                ],
            },
        }
    )


@login_required
@require_POST
def compartilhado_salvar(request):
    try:
        d = json.loads(request.body or "{}")
    except ValueError:
        return JsonResponse({"success": False, "error": "JSON inválido."}, status=400)
    titulo = (d.get("titulo") or "").strip()
    if not titulo:
        return JsonResponse({"success": False, "error": "Informe o título do checklist."}, status=400)
    tarefas = []
    for t in d.get("tarefas") or []:
        if not isinstance(t, dict) or not (t.get("texto") or "").strip():
            continue
        prazo = None
        if t.get("prazo"):
            prazo = _parse_data(t["prazo"])
            if not prazo:
                return JsonResponse({"success": False, "error": "Prazo inválido."}, status=400)
        resp = t.get("responsavel")
        tarefas.append(
            {
                "id": t.get("id"),
                "texto": t["texto"].strip()[:300],
                "grupo": (t.get("grupo") or "").strip()[:120],
                "responsavel": int(resp) if str(resp or "").isdigit() else None,
                "prazo": prazo,
            }
        )
    if not tarefas:
        return JsonResponse({"success": False, "error": "Adicione pelo menos um item."}, status=400)
    if len(tarefas) > 100:
        return JsonResponse({"success": False, "error": "Máximo de 100 itens."}, status=400)
    cor = d.get("cor") if isinstance(d.get("cor"), str) and len(d["cor"]) == 7 and d["cor"].startswith("#") else "#6f42c1"

    if d.get("id"):
        lista = _lista_visivel(request, d["id"])
        if not lista.pode_editar(request.user):
            return JsonResponse({"success": False, "error": "Só quem criou o checklist (ou a chefia dele) pode alterá-lo."}, status=403)
    else:
        lista = ChecklistCompartilhado(criado_por=request.user)
    dono_id = lista.criado_por_id
    ids = {int(x) for x in (d.get("membros") or []) if str(x).isdigit()} | {dono_id}
    validos = set(User.objects.filter(pk__in=ids, is_active=True).values_list("pk", flat=True)) | {dono_id}
    if any(t["responsavel"] is not None and t["responsavel"] not in validos for t in tarefas):
        return JsonResponse({"success": False, "error": "O responsável precisa ser membro do checklist."}, status=400)

    with transaction.atomic():
        lista.titulo, lista.descricao, lista.cor = titulo[:200], (d.get("descricao") or "").strip(), cor
        lista.save()
        lista.membros.exclude(usuario_id__in=validos).delete()
        for uid in validos:
            CompartilhadoMembro.objects.get_or_create(lista=lista, usuario_id=uid)
        existentes = {t.id: t for t in lista.tarefas.all()}
        mantidas = set()
        for ordem, t in enumerate(tarefas):
            obj = existentes.get(int(t["id"])) if str(t["id"] or "").isdigit() else None
            if obj:
                obj.texto, obj.grupo, obj.ordem, obj.responsavel_id, obj.prazo = t["texto"], t["grupo"], ordem, t["responsavel"], t["prazo"]
                obj.save(update_fields=["texto", "grupo", "ordem", "responsavel", "prazo"])
                mantidas.add(obj.id)
            else:
                CompartilhadoTarefa.objects.create(
                    lista=lista, texto=t["texto"], grupo=t["grupo"], ordem=ordem, responsavel_id=t["responsavel"], prazo=t["prazo"]
                )
        lista.tarefas.filter(id__in=existentes.keys()).exclude(id__in=mantidas).delete()
    for uid in validos:
        _invalida_inbox(None, uid)
    return JsonResponse({"success": True, "id": lista.id})


@login_required
@require_POST
def compartilhado_excluir(request, lista_id):
    lista = _lista_visivel(request, lista_id)
    if not lista.pode_editar(request.user):
        return JsonResponse({"success": False, "error": "Só quem criou o checklist (ou a chefia dele) pode excluí-lo."}, status=403)
    membros = list(lista.membros.values_list("usuario_id", flat=True))
    lista.delete()
    for uid in membros:
        _invalida_inbox(None, uid)
    return JsonResponse({"success": True})


def _tarefa_do_membro(request, tarefa_id):
    """Item de um checklist em que o usuário é membro (só membros concluem e cobram)."""
    t = get_object_or_404(CompartilhadoTarefa.objects.select_related("lista"), pk=tarefa_id)
    if not t.lista.eh_membro(request.user):
        raise Http404
    return t


@login_required
@require_POST
def api_tarefa_toggle(request, tarefa_id):
    t = _tarefa_do_membro(request, tarefa_id)
    t.concluida = not t.concluida
    t.concluida_por, t.concluida_em = (request.user, timezone.now()) if t.concluida else (None, None)
    t.save(update_fields=["concluida", "concluida_por", "concluida_em"])
    if t.concluida:  # cobranças pendentes dessa item perdem o sentido
        t.cobrancas.filter(lida=False).update(lida=True)
    for uid in {request.user.pk, t.responsavel_id} - {None}:
        _invalida_inbox(None, uid)
    return JsonResponse({"success": True, "concluida": t.concluida, "feito": t.concluida})


@login_required
@require_POST
def api_tarefa_cobrar(request, tarefa_id):
    t = _tarefa_do_membro(request, tarefa_id)
    if t.concluida:
        return JsonResponse({"success": False, "error": "O item já está concluído."}, status=400)
    if not t.responsavel_id:
        return JsonResponse({"success": False, "error": "O item não tem responsável para cobrar."}, status=400)
    if t.responsavel_id == request.user.pk:
        return JsonResponse({"success": False, "error": "Você é o responsável por este item."}, status=400)
    if CompartilhadoCobranca.objects.filter(tarefa=t, de=request.user, criado_em__date=timezone.localdate()).exists():
        return JsonResponse({"success": False, "error": "Você já cobrou este item hoje."}, status=429)
    CompartilhadoCobranca.objects.create(tarefa=t, de=request.user, para_id=t.responsavel_id)
    _invalida_inbox(None, t.responsavel_id)
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
