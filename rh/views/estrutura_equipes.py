# -*- coding: utf-8 -*-
"""
Estrutura de Equipes e Turnos (módulo Pessoas).

Construção livre: Setor > Bloco > Posto de trabalho > alocações por turno, onde cada alocação
é um Colaborador, uma VAGA (necessário contratar) ou uma RESERVA (equipamento reserva instalado).
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from core.models import TURNOS_CHOICES
from organization.models import AlocacaoPosto, GrupoEquipe, Setor
from rh.models import Colaborador
from shared.permissions import has_view_access

logger = logging.getLogger(__name__)

# Turnos usados nesta estrutura (o cadastro de colaboradores pode ter outros, como 12x36).
TURNOS_ESTRUTURA = [("ADM", "Administrativo"), ("TURNO_1", "Turno 01"), ("TURNO_2", "Turno 02"), ("TURNO_3", "Turno 03")]
TURNOS_VALIDOS = {codigo for codigo, _ in TURNOS_ESTRUTURA}
TURNOS_CADASTRO_VALIDOS = {codigo for codigo, _ in TURNOS_CHOICES}
# Rótulos para exibir também o turno do cadastro do colaborador (inclui os que não são da estrutura).
TURNO_LABEL = {**dict(TURNOS_CHOICES), **dict(TURNOS_ESTRUTURA)}
TIPOS_VALIDOS = {c for c, _ in AlocacaoPosto.TIPO_CHOICES}
LIMITE_BUSCA = 30
LIMITE_MAXIMO = 200
LIMITE_QUANTIDADE = 20

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
        {"turnos": TURNOS_ESTRUTURA, "pode_editar": _pode_editar(request.user)},
    )


# ------------------------------------------------------------------ leitura
def _serializa_alocacao(a):
    c = a.colaborador
    return {
        "id": a.id,
        "posto_id": a.posto_id,
        "turno": a.turno,
        "tipo": a.tipo,
        "colaborador_id": a.colaborador_id,
        "nome": c.nome_completo if c else "",
        "matricula": c.matricula if c else "",
        "cargo": (c.cargo or "") if c else "",
        "turno_cadastro": c.turno if c else "",
        "afastado": bool(c and c.afastado),
        "em_ferias": bool(c and c.em_ferias),
        "observacao": a.observacao,
    }


@login_required
@require_GET
def api_estrutura_equipes_dados(request):
    if not _pode_ver(request.user):
        return _negado()
    grupos = GrupoEquipe.objects.select_related("setor").order_by("ordem", "nome")
    alocacoes = (
        AlocacaoPosto.objects.filter(turno__in=TURNOS_VALIDOS)
        .select_related("colaborador")
        .order_by("turno", "tipo", "colaborador__nome_completo", "id")
    )
    return JsonResponse(
        {
            "success": True,
            "pode_editar": _pode_editar(request.user),
            "turnos": [{"codigo": c, "nome": n} for c, n in TURNOS_ESTRUTURA],
            "turno_labels": TURNO_LABEL,
            "setores": [{"id": s.id, "nome": s.nome} for s in Setor.objects.order_by("nome")],
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
                }
                for g in grupos
            ],
            "alocacoes": [_serializa_alocacao(a) for a in alocacoes],
        }
    )


@login_required
@require_GET
def api_estrutura_equipes_membros(request):
    """Colaboradores ativos, para consultar e alocar.

    ?q= (nome/matrícula)  &setor_id= (setor do cadastro)  &turno= (turno do cadastro)
    &sem_posto=1 (só quem não está alocado em nenhum posto)  &limite= (padrão 30, máx. 200)
    """
    if not _pode_ver(request.user):
        return _negado()
    q = (request.GET.get("q") or "").strip()
    turno = (request.GET.get("turno") or "").strip()
    try:
        setor_id = _int_ou_none(request.GET.get("setor_id"))
        limite = min(max(_int_ou_none(request.GET.get("limite")) or LIMITE_BUSCA, 1), LIMITE_MAXIMO)
    except ValueError:
        return _erro("Parâmetros inválidos.")
    qs = Colaborador.objects.filter(is_active=True).select_related("setor").prefetch_related("alocacoes_posto__posto__parent")
    if turno:
        if turno not in TURNOS_CADASTRO_VALIDOS:
            return _erro("Turno inválido.")
        qs = qs.filter(turno=turno)
    if setor_id:
        qs = qs.filter(setor_id=setor_id)
    if request.GET.get("sem_posto") == "1":
        qs = qs.filter(alocacoes_posto__isnull=True)
    if q:
        qs = qs.filter(Q(nome_completo__icontains=q) | Q(matricula__icontains=q))
    total = qs.count()
    membros = []
    for c in qs.order_by("nome_completo")[:limite]:
        postos = sorted(
            {f"{a.posto.parent.nome} › {a.posto.nome}" if a.posto.parent_id else a.posto.nome for a in c.alocacoes_posto.all()}
        )
        membros.append(
            {
                "id": c.id,
                "nome": c.nome_completo,
                "matricula": c.matricula,
                "cargo": c.cargo or "",
                "setor": c.setor.nome if c.setor_id else "",
                "turno": c.turno,
                "turno_label": TURNO_LABEL.get(c.turno, c.turno),
                "afastado": bool(c.afastado),
                "em_ferias": bool(c.em_ferias),
                "postos": postos,
            }
        )
    return JsonResponse({"success": True, "total": total, "truncado": total > len(membros), "membros": membros})


# ------------------------------------------------------------------ setor / bloco / posto
@login_required
@require_POST
def api_estrutura_equipes_setor_criar(request):
    """Cria um Setor (cadastro de setores da empresa) ou, com ``id``, renomeia um setor existente."""
    if not _pode_editar(request.user):
        return _negado("Sem permissão para editar a estrutura de equipes.")
    data = _body(request)
    if data is None:
        return _erro("Requisição inválida.")
    nome = str(data.get("nome") or "").strip()
    if not nome:
        return _erro("Informe o nome do setor.")
    if len(nome) > 100:
        return _erro("Nome muito longo (máx. 100 caracteres).")
    try:
        setor_id = _int_ou_none(data.get("id"))
    except ValueError:
        return _erro("Setor inválido.")
    setor = None
    if setor_id:
        setor = Setor.objects.filter(pk=setor_id).first()
        if not setor:
            return _erro("Setor não encontrado.", 404)
    duplicado = Setor.objects.filter(nome__iexact=nome)
    if setor:
        duplicado = duplicado.exclude(pk=setor.pk)
    if duplicado.exists():
        return _erro("Já existe um setor com esse nome.")
    if setor:
        setor.nome = nome
        setor.save(update_fields=["nome"])
        return JsonResponse({"success": True, "id": setor.id, "criado": False})
    setor = Setor.objects.create(nome=nome)
    return JsonResponse({"success": True, "id": setor.id, "criado": True})


@login_required
@require_POST
def api_estrutura_equipes_salvar(request):
    """Cria ou edita um bloco (sem pai, com setor) ou um posto de trabalho (dentro de um bloco)."""
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
        ordem = _int_ou_none(data.get("ordem"))
    except ValueError:
        return _erro("Dados numéricos inválidos.")
    if ordem is not None and ordem < 0:
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
    if not parent_id:
        irmaos = irmaos.filter(setor_id=setor_id)  # blocos de setores diferentes podem ter o mesmo nome
    if grupo:
        irmaos = irmaos.exclude(pk=grupo.pk)
    if irmaos.exists():
        return _erro("Já existe um item com esse nome neste mesmo nível.")

    try:
        with transaction.atomic():
            novo = grupo is None
            if novo:
                grupo = GrupoEquipe()
            grupo.nome = nome
            grupo.parent_id = parent_id
            grupo.setor_id = setor_id
            grupo.descricao = str(data.get("descricao") or "").strip()[:255]
            if ordem is not None:
                grupo.ordem = ordem  # a tela ordena sempre por nome; "ordem" fica só por compatibilidade
            grupo.ativo = bool(data.get("ativo", True))
            grupo.clean()
            grupo.save()
    except ValidationError as exc:
        return _erro(" ".join(exc.messages))
    except IntegrityError:
        return _erro("Já existe um item com esse nome neste mesmo nível.")
    except Exception:
        logger.exception("Erro ao salvar bloco/posto")
        return _erro("Não foi possível salvar.", 500)
    return JsonResponse({"success": True, "id": grupo.pk, "criado": novo})


@login_required
@require_POST
def api_estrutura_equipes_excluir(request):
    """Exclui um bloco (sem postos) ou um posto (e suas alocações)."""
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
    removidas = grupo.alocacoes.count()
    grupo.delete()
    return JsonResponse({"success": True, "alocacoes_removidas": removidas})


# ------------------------------------------------------------------ alocações
@login_required
@require_POST
def api_estrutura_equipes_alocacoes_criar(request):
    """Aloca em um posto, num turno: colaboradores (colaborador_ids), VAGO ou RESERVA (quantidade).

    Body: {posto_id, turno, tipo: PESSOA|VAGO|RESERVA, colaborador_ids?, quantidade?, observacao?}
    """
    if not _pode_editar(request.user):
        return _negado("Sem permissão para editar a estrutura de equipes.")
    data = _body(request)
    if data is None:
        return _erro("Requisição inválida.")
    try:
        posto = GrupoEquipe.objects.filter(pk=_int_ou_none(data.get("posto_id"))).first()
    except ValueError:
        posto = None
    if not posto:
        return _erro("Posto não encontrado.", 404)
    if not posto.parent_id:
        return _erro("Aloque em um posto de trabalho (dentro de um bloco).")
    turno, tipo = data.get("turno"), data.get("tipo")
    if turno not in TURNOS_VALIDOS:
        return _erro("Turno inválido.")
    if tipo not in TIPOS_VALIDOS:
        return _erro("Tipo inválido.")
    obs = str(data.get("observacao") or "").strip()[:255]

    criadas = ja_existiam = 0
    with transaction.atomic():
        if tipo == "PESSOA":
            ids = data.get("colaborador_ids")
            if not isinstance(ids, list) or not ids:
                return _erro("Selecione ao menos um colaborador.")
            try:
                ids = list(dict.fromkeys(int(i) for i in ids))
            except (ValueError, TypeError):
                return _erro("Colaboradores inválidos.")
            if len(ids) > 200:
                return _erro("Máximo de 200 colaboradores por operação.")
            ativos = set(Colaborador.objects.filter(pk__in=ids, is_active=True).values_list("pk", flat=True))
            if len(ativos) != len(ids):
                return _erro("Há colaborador inexistente ou inativo na seleção.")
            for cid in ids:
                _, criou = AlocacaoPosto.objects.get_or_create(
                    posto=posto, turno=turno, colaborador_id=cid, defaults={"tipo": "PESSOA", "observacao": obs}
                )
                criadas += criou
                ja_existiam += (not criou)
        else:
            try:
                qtd = _int_ou_none(data.get("quantidade")) or 1
            except ValueError:
                return _erro("Quantidade inválida.")
            if not 1 <= qtd <= LIMITE_QUANTIDADE:
                return _erro(f"A quantidade deve ficar entre 1 e {LIMITE_QUANTIDADE}.")
            AlocacaoPosto.objects.bulk_create(
                [AlocacaoPosto(posto=posto, turno=turno, tipo=tipo, observacao=obs) for _ in range(qtd)]
            )
            criadas = qtd
    return JsonResponse({"success": True, "criadas": criadas, "ja_existiam": ja_existiam})


@login_required
@require_POST
def api_estrutura_equipes_alocacoes_atualizar(request):
    """Edita uma alocação: turno, posto, tipo/colaborador (ex.: VAGO vira colaborador contratado) e observação."""
    if not _pode_editar(request.user):
        return _negado("Sem permissão para editar a estrutura de equipes.")
    data = _body(request)
    if data is None:
        return _erro("Requisição inválida.")
    try:
        aloc = AlocacaoPosto.objects.select_related("posto").filter(pk=_int_ou_none(data.get("id"))).first()
    except ValueError:
        aloc = None
    if not aloc:
        return _erro("Alocação não encontrada.", 404)

    try:
        if "turno" in data:
            if data["turno"] not in TURNOS_VALIDOS:
                return _erro("Turno inválido.")
            aloc.turno = data["turno"]
        if "posto_id" in data:
            posto = GrupoEquipe.objects.filter(pk=_int_ou_none(data["posto_id"])).first()
            if not posto:
                return _erro("Posto não encontrado.", 404)
            aloc.posto = posto
        if "tipo" in data:
            if data["tipo"] not in TIPOS_VALIDOS:
                return _erro("Tipo inválido.")
            aloc.tipo = data["tipo"]
        if "colaborador_id" in data:
            cid = _int_ou_none(data["colaborador_id"])
            if cid and not Colaborador.objects.filter(pk=cid, is_active=True).exists():
                return _erro("Colaborador inexistente ou inativo.")
            aloc.colaborador_id = cid
        if aloc.tipo != "PESSOA":
            aloc.colaborador_id = None  # vaga/reserva nunca guardam colaborador
        if "observacao" in data:
            aloc.observacao = str(data["observacao"] or "").strip()[:255]
    except ValueError:
        return _erro("Dados numéricos inválidos.")

    try:
        aloc.clean()
        with transaction.atomic():
            aloc.save()
    except ValidationError as exc:
        return _erro(" ".join(exc.messages))
    except IntegrityError:
        return _erro("Este colaborador já está neste posto neste turno.")
    return JsonResponse({"success": True})


@login_required
@require_POST
def api_estrutura_equipes_alocacoes_excluir(request):
    """Remove alocações. Body: {ids: [..]}"""
    if not _pode_editar(request.user):
        return _negado("Sem permissão para editar a estrutura de equipes.")
    data = _body(request)
    ids = (data or {}).get("ids")
    if not isinstance(ids, list) or not ids:
        return _erro("Nada selecionado.")
    try:
        ids = [int(i) for i in ids]
    except (ValueError, TypeError):
        return _erro("Dados inválidos.")
    removidas, _ = AlocacaoPosto.objects.filter(pk__in=ids).delete()
    return JsonResponse({"success": True, "removidas": removidas})
