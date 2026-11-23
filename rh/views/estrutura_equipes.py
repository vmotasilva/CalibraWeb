# -*- coding: utf-8 -*-
"""
Estrutura de Equipes e Turnos (módulo Pessoas).

Grupos e subgrupos em árvore; cada grupo pode ter, por turno, um responsável (titular),
situação e efetivo planejado. Os colaboradores se vinculam ao grupo via ``Colaborador.equipe``
e o turno de cada um vem do cadastro do colaborador.
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from core.models import TURNOS_CHOICES
from organization.models import GrupoEquipe, GrupoEquipeTurno, Setor
from rh.models import Colaborador
from shared.permissions import has_view_access

logger = logging.getLogger(__name__)

TURNOS_VALIDOS = {codigo for codigo, _ in TURNOS_CHOICES}
TURNO_LABEL = dict(TURNOS_CHOICES)
SITUACOES_VALIDAS = {c for c, _ in GrupoEquipeTurno.SITUACAO_CHOICES}
SITUACOES_SEM_TITULAR = {"VAGO", "RESERVA"}
LIMITE_MEMBROS = 500

VIEW_PERM = "rh:estrutura_equipes"
EDIT_PERM = "rh:api_estrutura_equipes_salvar"


def _pode_ver(user):
    return has_view_access(user, VIEW_PERM)


def _pode_editar(user):
    return has_view_access(user, EDIT_PERM)


def _negado(msg="Sem permissão."):
    return JsonResponse({"success": False, "error": msg}, status=403)


def _erro(msg, status=400):
    return JsonResponse({"success": False, "error": msg}, status=status)


def _body(request):
    try:
        data = json.loads(request.body or "{}")
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _int_ou_none(valor):
    if valor in (None, "", "null"):
        return None
    try:
        return int(valor)
    except (ValueError, TypeError):
        raise ValueError("valor numérico inválido")


# ------------------------------------------------------------------ página
@login_required
def estrutura_equipes_view(request):
    if not _pode_ver(request.user):
        raise PermissionDenied
    return render(
        request,
        "rh/estrutura_equipes.html",
        {"turnos": TURNOS_CHOICES, "pode_editar": _pode_editar(request.user)},
    )


# ------------------------------------------------------------------ leitura
def _serializa_colab(c, caminhos):
    return {
        "id": c.id,
        "nome": c.nome_completo,
        "matricula": c.matricula,
        "cargo": c.cargo or "",
        "setor": c.setor.nome if c.setor_id else "",
        "turno": c.turno,
        "turno_label": TURNO_LABEL.get(c.turno, c.turno),
        "equipe_id": c.equipe_id,
        "equipe": caminhos.get(c.equipe_id, ""),
        "afastado": bool(c.afastado),
        "em_ferias": bool(c.em_ferias),
    }


@login_required
@require_GET
def api_estrutura_equipes_dados(request):
    if not _pode_ver(request.user):
        return _negado()

    grupos = list(GrupoEquipe.objects.select_related("setor").order_by("ordem", "nome"))
    configs = {}
    for cfg in GrupoEquipeTurno.objects.select_related("responsavel"):
        configs.setdefault(cfg.grupo_id, []).append(
            {
                "turno": cfg.turno,
                "responsavel_id": cfg.responsavel_id,
                "responsavel_nome": cfg.responsavel.nome_completo if cfg.responsavel_id else "",
                "situacao": cfg.situacao,
                "efetivo_planejado": cfg.efetivo_planejado,
            }
        )

    contagem = {}
    sem_grupo = {}
    qs = (
        Colaborador.objects.filter(is_active=True)
        .values("equipe_id", "turno")
        .annotate(n=Count("id"))
    )
    for row in qs:
        if row["equipe_id"] is None:
            sem_grupo[row["turno"]] = row["n"]
        else:
            contagem.setdefault(row["equipe_id"], {})[row["turno"]] = row["n"]

    return JsonResponse(
        {
            "success": True,
            "pode_editar": _pode_editar(request.user),
            "turnos": [{"codigo": c, "nome": n} for c, n in TURNOS_CHOICES],
            "setores": [{"id": s.id, "nome": s.nome} for s in Setor.objects.order_by("nome")],
            "sem_grupo": sem_grupo,
            "grupos": [
                {
                    "id": g.id,
                    "nome": g.nome,
                    "parent_id": g.parent_id,
                    "setor_id": g.setor_id,
                    "setor_nome": g.setor.nome if g.setor_id else "",
                    "descricao": g.descricao,
                    "ordem": g.ordem,
                    "ativo": g.ativo,
                    "nivel": g.nivel,
                    "turnos": sorted(configs.get(g.id, []), key=lambda t: t["turno"]),
                    "contagem": contagem.get(g.id, {}),
                }
                for g in grupos
            ],
        }
    )


@login_required
@require_GET
def api_estrutura_equipes_membros(request):
    """Colaboradores ativos. ?grupo=<id>|sem|todos &subgrupos=1 &turno= &q="""
    if not _pode_ver(request.user):
        return _negado()

    grupo = (request.GET.get("grupo") or "todos").strip()
    turno = (request.GET.get("turno") or "").strip()
    q = (request.GET.get("q") or "").strip()

    qs = Colaborador.objects.filter(is_active=True).select_related("setor")
    if grupo == "sem":
        qs = qs.filter(equipe__isnull=True)
    elif grupo != "todos":
        try:
            g = GrupoEquipe.objects.get(pk=int(grupo))
        except (ValueError, GrupoEquipe.DoesNotExist):
            return _erro("Grupo não encontrado.", 404)
        ids = [g.pk]
        if request.GET.get("subgrupos") == "1":
            ids += g.ids_descendentes()
        qs = qs.filter(equipe_id__in=ids)
    if turno:
        if turno not in TURNOS_VALIDOS:
            return _erro("Turno inválido.")
        qs = qs.filter(turno=turno)
    if q:
        qs = qs.filter(Q(nome_completo__icontains=q) | Q(matricula__icontains=q))

    total = qs.count()
    colabs = list(qs.order_by("nome_completo")[:LIMITE_MEMBROS])
    caminhos = {g.pk: g.caminho for g in GrupoEquipe.objects.select_related("parent")}
    return JsonResponse(
        {
            "success": True,
            "total": total,
            "truncado": total > len(colabs),
            "membros": [_serializa_colab(c, caminhos) for c in colabs],
        }
    )


# ------------------------------------------------------------------ escrita
@login_required
@require_POST
def api_estrutura_equipes_salvar(request):
    if not _pode_editar(request.user):
        return _negado("Sem permissão para editar a estrutura de equipes.")
    data = _body(request)
    if data is None:
        return _erro("Requisição inválida.")

    nome = str(data.get("nome") or "").strip()
    if not nome:
        return _erro("Informe o nome.")
    if len(nome) > 100:
        return _erro("Nome muito longo (máx. 100 caracteres).")

    try:
        grupo_id = _int_ou_none(data.get("id"))
        parent_id = _int_ou_none(data.get("parent_id"))
        setor_id = _int_ou_none(data.get("setor_id"))
        ordem = _int_ou_none(data.get("ordem")) or 0
    except ValueError:
        return _erro("Dados numéricos inválidos.")
    if ordem < 0:
        return _erro("A ordem não pode ser negativa.")

    grupo = None
    if grupo_id:
        grupo = GrupoEquipe.objects.filter(pk=grupo_id).first()
        if not grupo:
            return _erro("Grupo não encontrado.", 404)
    if parent_id and not GrupoEquipe.objects.filter(pk=parent_id).exists():
        return _erro("Bloco não encontrado.")
    if setor_id and not Setor.objects.filter(pk=setor_id).exists():
        return _erro("Setor não encontrado.")
    if not parent_id and not setor_id:
        return _erro("Informe o setor do bloco.")

    irmaos = GrupoEquipe.objects.filter(parent_id=parent_id, nome__iexact=nome)
    if grupo:
        irmaos = irmaos.exclude(pk=grupo.pk)
    if irmaos.exists():
        return _erro("Já existe um grupo com esse nome neste mesmo nível.")

    # Turnos: lista de {turno, responsavel_id, situacao, efetivo_planejado}
    turnos_in = data.get("turnos") or []
    if not isinstance(turnos_in, list):
        return _erro("Turnos inválidos.")
    configs, vistos = [], set()
    for item in turnos_in:
        if not isinstance(item, dict):
            return _erro("Turnos inválidos.")
        t = item.get("turno")
        if t not in TURNOS_VALIDOS:
            return _erro(f"Turno inválido: {t}.")
        if t in vistos:
            return _erro(f"Turno repetido: {TURNO_LABEL[t]}.")
        vistos.add(t)
        try:
            resp_id = _int_ou_none(item.get("responsavel_id"))
            efetivo = _int_ou_none(item.get("efetivo_planejado"))
        except ValueError:
            return _erro("Responsável ou efetivo planejado inválido.")
        situacao = item.get("situacao") or ("ATIVO" if item.get("responsavel_id") else "VAGO")
        if situacao not in SITUACOES_VALIDAS:
            return _erro("Situação inválida.")
        if efetivo is not None and efetivo < 0:
            return _erro("O efetivo planejado não pode ser negativo.")
        if situacao in SITUACOES_SEM_TITULAR:
            resp_id = None  # vago/reserva não têm titular
        elif situacao == "ATIVO" and not resp_id:
            return _erro(
                f"{TURNO_LABEL[t]}: posto sem pessoa associada deve ser marcado como Vago (contratar) ou Reserva (equipamento reserva)."
            )
        if resp_id and not Colaborador.objects.filter(pk=resp_id, is_active=True).exists():
            return _erro("Responsável não encontrado ou inativo.")
        configs.append((t, resp_id, situacao, efetivo))

    try:
        with transaction.atomic():
            novo = grupo is None
            if novo:
                grupo = GrupoEquipe()
            grupo.nome = nome
            grupo.parent_id = parent_id
            grupo.setor_id = setor_id
            grupo.descricao = str(data.get("descricao") or "").strip()[:255]
            grupo.ordem = ordem
            grupo.ativo = bool(data.get("ativo", True))
            grupo.clean()  # impede ciclos na árvore
            grupo.save()
            grupo.turnos_config.exclude(turno__in=vistos).delete()
            for t, resp_id, situacao, efetivo in configs:
                GrupoEquipeTurno.objects.update_or_create(
                    grupo=grupo,
                    turno=t,
                    defaults={"responsavel_id": resp_id, "situacao": situacao, "efetivo_planejado": efetivo},
                )
    except Exception as exc:  # ValidationError do clean() e demais
        mensagens = getattr(exc, "messages", None)
        if mensagens:
            return _erro(" ".join(mensagens))
        logger.exception("Erro ao salvar grupo de equipe")
        return _erro("Não foi possível salvar o grupo.", 500)

    return JsonResponse({"success": True, "id": grupo.pk, "criado": novo})


@login_required
@require_POST
def api_estrutura_equipes_excluir(request):
    """Exclui o bloco (sem postos) ou o posto; os colaboradores vinculados ficam sem posto."""
    if not _pode_editar(request.user):
        return _negado("Sem permissão para editar a estrutura de equipes.")
    data = _body(request)
    if data is None:
        return _erro("Requisição inválida.")
    try:
        grupo = GrupoEquipe.objects.filter(pk=_int_ou_none(data.get("id"))).first()
    except ValueError:
        grupo = None
    if not grupo:
        return _erro("Grupo não encontrado.", 404)

    if grupo.subgrupos.exists():
        return _erro("Este bloco ainda possui postos de trabalho. Exclua ou mova os postos antes de excluí-lo.")
    with transaction.atomic():
        membros = Colaborador.objects.filter(equipe=grupo).update(equipe=None)
        grupo.delete()
    return JsonResponse({"success": True, "membros_desvinculados": membros})


@login_required
@require_POST
def api_estrutura_equipes_membros_atualizar(request):
    """Vincula colaboradores a um grupo (ou remove o vínculo) e, opcionalmente, ajusta o turno.

    Body: {colaborador_ids: [..], grupo_id: <id|null>, turno: <código|""> }
    Sem a chave ``grupo_id`` o grupo atual dos colaboradores não é alterado.
    """
    if not _pode_editar(request.user):
        return _negado("Sem permissão para editar a estrutura de equipes.")
    data = _body(request)
    if data is None:
        return _erro("Requisição inválida.")

    ids = data.get("colaborador_ids")
    if not isinstance(ids, list) or not ids:
        return _erro("Selecione ao menos um colaborador.")
    try:
        ids = [int(i) for i in ids]
        grupo_id = _int_ou_none(data.get("grupo_id"))
    except (ValueError, TypeError):
        return _erro("Dados inválidos.")
    if len(ids) > 1000:
        return _erro("Máximo de 1000 colaboradores por operação.")

    turno = str(data.get("turno") or "").strip()
    if turno and turno not in TURNOS_VALIDOS:
        return _erro("Turno inválido.")
    if grupo_id and not GrupoEquipe.objects.filter(pk=grupo_id).exists():
        return _erro("Grupo não encontrado.", 404)
    if "grupo_id" not in data and not turno:
        return _erro("Informe o grupo de destino ou o turno.")

    alterados = 0
    with transaction.atomic():
        for colab in Colaborador.objects.filter(pk__in=ids, is_active=True):
            campos = []
            if "grupo_id" in data and colab.equipe_id != grupo_id:
                colab.equipe_id = grupo_id
                campos.append("equipe")
            if turno and colab.turno != turno:
                colab.turno = turno
                campos.append("turno")
            if campos:
                colab.save(update_fields=campos)
                alterados += 1
    return JsonResponse({"success": True, "alterados": alterados})
