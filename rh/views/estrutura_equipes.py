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
from organization.models import AlocacaoPosto, GrupoEquipe, Setor, SetorEquipe, TurnoEquipe
from rh.models import Colaborador
from shared.permissions import has_view_access

logger = logging.getLogger(__name__)

# Os turnos DESTA tela são cadastrados por setor (TurnoEquipe). Os códigos abaixo são só os do cadastro de
# colaboradores (outro módulo), usados para filtrar/exibir o turno do cadastro de uma pessoa.
TURNOS_CADASTRO_VALIDOS = {codigo for codigo, _ in TURNOS_CHOICES}
TURNO_LABEL = dict(TURNOS_CHOICES)
LIMITE_TURNOS_SETOR = 12
TAMANHO_NOME_TURNO = 50
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
        {"pode_editar": _pode_editar(request.user)},
    )


# ------------------------------------------------------------------ leitura
def _serializa_alocacao(a):
    c = a.colaborador
    return {
        "id": a.id,
        "posto_id": a.posto_id,
        "turno_id": a.turno_estrutura_id,
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
    grupos = GrupoEquipe.objects.select_related("setor_estrutura").order_by("ordem", "nome")
    alocacoes = (
        AlocacaoPosto.objects.filter(turno_estrutura__isnull=False)
        .select_related("colaborador")
        .order_by("tipo", "colaborador__nome_completo", "id")
    )
    setores = SetorEquipe.objects.order_by("nome").prefetch_related("turnos")
    return JsonResponse(
        {
            "success": True,
            "pode_editar": _pode_editar(request.user),
            "turno_labels": TURNO_LABEL,
            # Setores da estrutura: cadastro próprio desta tela, cada um com os seus turnos.
            "setores": [
                {"id": s.id, "nome": s.nome, "turnos": [{"id": t.id, "nome": t.nome} for t in s.turnos.all()]}
                for s in setores
            ],
            # Setores do cadastro de colaboradores: só para filtrar pessoas na aba Colaboradores.
            "setores_cadastro": [{"id": s.id, "nome": s.nome} for s in Setor.objects.order_by("nome")],
            "grupos": [
                {
                    "id": g.id,
                    "nome": g.nome,
                    "parent_id": g.parent_id,
                    "setor_id": g.setor_estrutura_id,
                    "setor_nome": g.setor_estrutura.nome if g.setor_estrutura_id else "",
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

    ?q= (nome/matrícula)  &setor_cadastro_id= (setor no cadastro do colaborador)  &turno= (turno do cadastro)
    &sem_posto=1 (só quem não está alocado em nenhum posto)  &limite= (padrão 30, máx. 200)
    &lider_id= (líder direto)  &cargo= (cargo exato)
    &pagina= &por_pagina= (paginação, máx. 100; sem `pagina` vale o modo `limite`)
    &opcoes=1 (devolve também as opções dos filtros: setores, turnos, líderes e cargos)
    """
    if not _pode_ver(request.user):
        return _negado()
    q = (request.GET.get("q") or "").strip()
    turno = (request.GET.get("turno") or "").strip()
    try:
        setor_id = _int_ou_none(request.GET.get("setor_cadastro_id"))
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
    try:
        lider_id = _int_ou_none(request.GET.get("lider_id"))
        pagina = _int_ou_none(request.GET.get("pagina"))
        por_pagina = min(max(_int_ou_none(request.GET.get("por_pagina")) or 10, 1), 100)
    except ValueError:
        return _erro("Parâmetros inválidos.")
    if lider_id:
        qs = qs.filter(lider_id=lider_id)
    cargo = (request.GET.get("cargo") or "").strip()
    if cargo:
        qs = qs.filter(cargo=cargo)
    if request.GET.get("sem_posto") == "1":
        qs = qs.filter(alocacoes_posto__isnull=True)
    if q:
        qs = qs.filter(Q(nome_completo__icontains=q) | Q(matricula__icontains=q))
    total = qs.count()
    ordenado = qs.order_by("nome_completo")
    paginas = None
    if pagina:
        paginas = max(1, -(-total // por_pagina))
        pagina = min(pagina, paginas)
        recorte = ordenado[(pagina - 1) * por_pagina : pagina * por_pagina]
    else:
        recorte = ordenado[:limite]
    membros = []
    for c in recorte:
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
    resposta = {"success": True, "total": total, "truncado": paginas is None and total > len(membros), "membros": membros}
    if paginas is not None:
        resposta.update(pagina=pagina, paginas=paginas, por_pagina=por_pagina)
    if request.GET.get("opcoes") == "1":
        ativos = Colaborador.objects.filter(is_active=True)
        resposta["opcoes"] = {
            "setores": [{"id": x.id, "nome": x.nome} for x in Setor.objects.order_by("nome")],
            "turnos": [{"id": k, "nome": v} for k, v in TURNO_LABEL.items() if k in TURNOS_CADASTRO_VALIDOS],
            "lideres": [
                {"id": x.id, "nome": x.nome_completo}
                for x in Colaborador.objects.filter(liderados__is_active=True).distinct().order_by("nome_completo")
            ],
            "cargos": sorted(c for c in ativos.exclude(cargo__isnull=True).exclude(cargo="").values_list("cargo", flat=True).distinct()),
        }
    return JsonResponse(resposta)


# ------------------------------------------------------------------ setor / bloco / posto
class ErroValidacao(Exception):
    """Erro de validação de entrada, mostrado ao usuário."""


def _normaliza_turnos(lista):
    """Valida a lista de turnos enviada: [{id?, nome}] (ou só nomes). Devolve [(id|None, nome)]."""
    if not isinstance(lista, list):
        raise ErroValidacao("Turnos inválidos.")
    if len(lista) > LIMITE_TURNOS_SETOR:
        raise ErroValidacao(f"Um setor pode ter no máximo {LIMITE_TURNOS_SETOR} turnos.")
    saida, vistos = [], set()
    for item in lista:
        if isinstance(item, str):
            item = {"nome": item}
        if not isinstance(item, dict):
            raise ErroValidacao("Turnos inválidos.")
        nome = str(item.get("nome") or "").strip()
        if not nome:
            raise ErroValidacao("Há turno sem nome.")
        if len(nome) > TAMANHO_NOME_TURNO:
            raise ErroValidacao(f"Nome de turno muito longo (máx. {TAMANHO_NOME_TURNO} caracteres): {nome[:20]}…")
        chave = nome.casefold()
        if chave in vistos:
            raise ErroValidacao(f'Turno repetido: "{nome}".')
        vistos.add(chave)
        try:
            tid = _int_ou_none(item.get("id"))
        except ValueError:
            raise ErroValidacao("Turno inválido.")
        saida.append((tid, nome))
    return saida


def _aplica_turnos(setor, lista):
    """Sincroniza os turnos do setor com a lista: renomeia, cria e remove (só sem alocações)."""
    existentes = {t.id: t for t in setor.turnos.all()}
    enviados = {tid for tid, _ in lista if tid}
    if enviados - set(existentes):
        raise ErroValidacao("Turno não encontrado neste setor.")
    for tid, turno in existentes.items():
        if tid not in enviados:
            n = turno.alocacoes.count()
            if n:
                raise ErroValidacao(
                    f'O turno "{turno.nome}" tem {n} alocação(ões). Remova-as antes de excluir o turno.'
                )
            turno.delete()
    # renomeia em duas fases (evita conflito temporário ao trocar nomes entre turnos)
    mudar = [(existentes[tid], nome) for tid, nome in lista if tid and existentes[tid].nome != nome]
    for turno, _ in mudar:
        turno.nome = f"~{turno.id}"
        turno.save(update_fields=["nome"])
    for turno, nome in mudar:
        turno.nome = nome
        turno.save(update_fields=["nome"])
    for tid, nome in lista:
        if not tid:
            TurnoEquipe.objects.create(setor=setor, nome=nome)


def _serializa_turnos(setor):
    return [{"id": t.id, "nome": t.nome} for t in setor.turnos.all()]


@login_required
@require_POST
def api_estrutura_equipes_setor_criar(request):
    """Cria um setor da estrutura ou, com ``id``, edita um existente; ``turnos`` define os turnos do setor.

    Cadastro próprio, independente do de setores da empresa e dos turnos de outros módulos.
    Body: {id?, nome, turnos?: [{id?, nome}]}  (sem ``turnos`` na edição, os turnos não mudam)
    """
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
    try:
        turnos = _normaliza_turnos(data["turnos"]) if "turnos" in data else None
    except ErroValidacao as exc:
        return _erro(str(exc))
    setor = None
    if setor_id:
        setor = SetorEquipe.objects.filter(pk=setor_id).first()
        if not setor:
            return _erro("Setor não encontrado.", 404)
    duplicado = SetorEquipe.objects.filter(nome__iexact=nome)
    if setor:
        duplicado = duplicado.exclude(pk=setor.pk)
    if duplicado.exists():
        return _erro("Já existe um setor com esse nome.")
    try:
        with transaction.atomic():
            criado = setor is None
            if criado:
                setor = SetorEquipe.objects.create(nome=nome)
            else:
                setor.nome = nome
                setor.save(update_fields=["nome"])
            if turnos is not None:
                _aplica_turnos(setor, turnos)
    except ErroValidacao as exc:
        return _erro(str(exc))
    return JsonResponse({"success": True, "id": setor.id, "criado": criado, "turnos": _serializa_turnos(setor)})


@login_required
@require_POST
def api_estrutura_equipes_setor_excluir(request):
    """Exclui um setor da estrutura. Só é possível sem blocos dentro dele."""
    if not _pode_editar(request.user):
        return _negado("Sem permissão para editar a estrutura de equipes.")
    data = _body(request)
    if data is None:
        return _erro("Requisição inválida.")
    try:
        setor = SetorEquipe.objects.filter(pk=_int_ou_none(data.get("id"))).first()
    except ValueError:
        setor = None
    if not setor:
        return _erro("Setor não encontrado.", 404)
    if setor.blocos.exists():
        return _erro("Este setor ainda possui blocos. Exclua ou mova os blocos antes de excluí-lo.")
    setor.delete()
    return JsonResponse({"success": True})


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
    if setor_id and not SetorEquipe.objects.filter(pk=setor_id).exists():
        return _erro("Setor não encontrado.")
    if not parent_id and not setor_id:
        return _erro("Informe o setor do bloco.")

    irmaos = GrupoEquipe.objects.filter(parent_id=parent_id, nome__iexact=nome)
    if not parent_id:
        irmaos = irmaos.filter(setor_estrutura_id=setor_id)  # blocos de setores diferentes podem ter o mesmo nome
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
            grupo.setor_estrutura_id = setor_id
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
    """Aloca em um posto, em um ou mais turnos do SETOR do posto: colaboradores, VAGO ou RESERVA.

    Body: {posto_id, turno_ids: [..], tipo: PESSOA|VAGO|RESERVA, colaborador_ids?, quantidade?, observacao?}
    A quantidade de vagas/reservas vale para cada turno marcado.
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
    tipo = data.get("tipo")
    if tipo not in TIPOS_VALIDOS:
        return _erro("Tipo inválido.")
    ids_turno = data.get("turno_ids")
    if not isinstance(ids_turno, list) or not ids_turno:
        return _erro("Marque ao menos um turno.")
    try:
        ids_turno = list(dict.fromkeys(int(i) for i in ids_turno))
    except (ValueError, TypeError):
        return _erro("Turno inválido.")
    turnos_ok = {t.id: t for t in TurnoEquipe.objects.filter(setor_id=posto.setor_estrutura_id, id__in=ids_turno)}
    if len(turnos_ok) != len(ids_turno):
        return _erro("Turno inválido para o setor deste posto.")
    turnos = [turnos_ok[i] for i in ids_turno]
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
            for turno in turnos:
                for cid in ids:
                    _, criou = AlocacaoPosto.objects.get_or_create(
                        posto=posto, turno_estrutura=turno, colaborador_id=cid,
                        defaults={"tipo": "PESSOA", "observacao": obs},
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
                [AlocacaoPosto(posto=posto, turno_estrutura=t, tipo=tipo, observacao=obs) for t in turnos for _ in range(qtd)]
            )
            criadas = qtd * len(turnos)
    return JsonResponse({"success": True, "criadas": criadas, "ja_existiam": ja_existiam, "turnos": len(turnos)})


@login_required
@require_POST
def api_estrutura_equipes_alocacoes_atualizar(request):
    """Edita uma alocação: turno (do setor do posto), posto, tipo/colaborador (VAGO vira contratado) e observação."""
    if not _pode_editar(request.user):
        return _negado("Sem permissão para editar a estrutura de equipes.")
    data = _body(request)
    if data is None:
        return _erro("Requisição inválida.")
    try:
        aloc = AlocacaoPosto.objects.select_related("posto", "turno_estrutura").filter(pk=_int_ou_none(data.get("id"))).first()
    except ValueError:
        aloc = None
    if not aloc:
        return _erro("Alocação não encontrada.", 404)

    try:
        if "turno_id" in data:
            turno = TurnoEquipe.objects.filter(pk=_int_ou_none(data["turno_id"])).first()
            if not turno:
                return _erro("Turno inválido.")
            aloc.turno_estrutura = turno
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
