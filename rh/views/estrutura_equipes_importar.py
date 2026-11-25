# -*- coding: utf-8 -*-
"""
Importação da Estrutura de Equipes e Turnos por planilha, em duas etapas:
  1. prévia  -> lê o arquivo e devolve o que seria criado/atualizado (não grava nada);
  2. confirmar -> grava, numa única transação, exatamente o que foi revisado na tela.
"""
import json
import logging
import re

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from core.models import TURNOS_CHOICES
from organization.models import AlocacaoPosto, GrupoEquipe, Setor
from rh.models import Colaborador
from rh.services.estrutura_import import PlanilhaInvalida, ler_planilha, monta_previa, normaliza
from rh.views.estrutura_equipes import (
    TURNOS_VALIDOS,
    _erro,
    _negado,
    _pode_editar,
)

logger = logging.getLogger(__name__)

TAMANHO_MAX = 5 * 1024 * 1024
SITUACOES_DECISAO = {"VAGO", "RESERVA", "PARADO"}


@login_required
def estrutura_equipes_importar_view(request):
    if not _pode_editar(request.user):
        raise PermissionDenied
    return render(
        request,
        "rh/estrutura_equipes_importar.html",
        {"setores": Setor.objects.order_by("nome"), "turnos": TURNOS_CHOICES},
    )


@login_required
@require_POST
def api_estrutura_equipes_importar_previa(request):
    """Lê a planilha e devolve a prévia para revisão. Não grava nada."""
    if not _pode_editar(request.user):
        return _negado("Sem permissão para importar a estrutura.")
    arquivo = request.FILES.get("arquivo")
    if not arquivo:
        return _erro("Envie a planilha (.xlsx).")
    if not arquivo.name.lower().endswith(".xlsx"):
        return _erro("Formato inválido: envie um arquivo .xlsx.")
    if arquivo.size > TAMANHO_MAX:
        return _erro("Arquivo muito grande (máx. 5 MB).")

    setor_id = None
    if request.POST.get("setor_id"):
        try:
            setor_id = int(request.POST["setor_id"])
        except ValueError:
            return _erro("Setor inválido.")
        if not Setor.objects.filter(pk=setor_id).exists():
            return _erro("Setor não encontrado.")

    try:
        dados = ler_planilha(arquivo)
    except PlanilhaInvalida as exc:
        return _erro(str(exc))
    except Exception:
        logger.exception("Erro ao ler planilha de estrutura")
        return _erro("Não foi possível ler a planilha.", 500)

    monta_previa(dados, setor_id)

    for bloco in dados["blocos"]:
        existente = (
            GrupoEquipe.objects.filter(parent__isnull=True, setor_id=setor_id, nome__iexact=bloco["nome"]).first()
            if setor_id else None
        )
        bloco["existe"] = bool(existente)
        bloco["setor_existente"] = ""
        postos_db = (
            {normaliza(n) for n in existente.subgrupos.values_list("nome", flat=True)} if existente else set()
        )
        for posto in bloco["postos"]:
            posto["existe"] = normaliza(posto["nome"]) in postos_db
    return JsonResponse({"success": True, **dados})


def _decisao_valida(decisao):
    if isinstance(decisao, str):
        if decisao.startswith("s:") and decisao[2:] in SITUACOES_DECISAO:
            return "situacao", decisao[2:]
        m = re.fullmatch(r"c:(\d+)", decisao)
        if m:
            return "pessoa", int(m.group(1))
    return None, None


@login_required
@require_POST
def api_estrutura_equipes_importar_confirmar(request):
    """Grava o que foi revisado. Tudo ou nada."""
    if not _pode_editar(request.user):
        return _negado("Sem permissão para importar a estrutura.")
    try:
        data = json.loads(request.body or "{}")
    except (ValueError, TypeError):
        return _erro("Requisição inválida.")
    if not isinstance(data, dict) or not isinstance(data.get("blocos"), list) or not data["blocos"]:
        return _erro("Nada para importar.")

    # --- setor
    setor_novo = str(data.get("setor_novo") or "").strip()
    setor = None
    if data.get("setor_id"):
        try:
            setor = Setor.objects.filter(pk=int(data["setor_id"])).first()
        except (ValueError, TypeError):
            setor = None
        if not setor:
            return _erro("Setor não encontrado.")
    elif setor_novo:
        if len(setor_novo) > 100:
            return _erro("Nome do setor muito longo.")
    else:
        return _erro("Informe o setor.")

    # --- validação completa antes de gravar qualquer coisa
    plano, nomes_blocos, ids_pessoas = [], set(), set()
    for bloco in data["blocos"]:
        nome_b = str((bloco or {}).get("nome") or "").strip()
        if not nome_b or len(nome_b) > 100:
            return _erro("Há bloco sem nome (ou com nome maior que 100 caracteres).")
        if normaliza(nome_b) in nomes_blocos:
            return _erro(f'Bloco repetido: "{nome_b}".')
        nomes_blocos.add(normaliza(nome_b))
        postos, nomes_postos = [], set()
        for posto in (bloco.get("postos") or []):
            nome_p = str((posto or {}).get("nome") or "").strip()
            if not nome_p or len(nome_p) > 100:
                return _erro(f'Bloco "{nome_b}": há posto sem nome (ou com nome maior que 100 caracteres).')
            if normaliza(nome_p) in nomes_postos:
                return _erro(f'Bloco "{nome_b}": posto repetido "{nome_p}".')
            nomes_postos.add(normaliza(nome_p))
            turnos, vistos = [], set()
            for cel in (posto.get("turnos") or []):
                t = (cel or {}).get("turno")
                if t not in TURNOS_VALIDOS or t in vistos:
                    return _erro(f'"{nome_b} › {nome_p}": turno inválido ou repetido.')
                vistos.add(t)
                tipo, valor = _decisao_valida(cel.get("decisao"))
                if tipo is None:
                    return _erro(f'"{nome_b} › {nome_p}": falta definir o titular ou a situação de um turno.')
                if tipo == "pessoa":
                    ids_pessoas.add(valor)
                turnos.append((t, tipo, valor))
            postos.append((nome_p, turnos))
        if postos:
            plano.append((nome_b, postos))
    if not plano:
        return _erro("Nada para importar.")

    ativos = set(Colaborador.objects.filter(pk__in=ids_pessoas, is_active=True).values_list("pk", flat=True))
    if ids_pessoas - ativos:
        return _erro("Há titular que não existe mais ou está inativo. Refaça a prévia.")

    r = {"blocos_criados": 0, "postos_criados": 0, "postos_atualizados": 0,
         "colaboradores": 0, "vagos": 0, "reservas": 0, "postos_parados": 0}
    try:
        with transaction.atomic():
            if setor is None:
                setor, _ = Setor.objects.get_or_create(nome=setor_novo)
            for ordem_b, (nome_b, postos) in enumerate(plano, start=1):
                bloco = GrupoEquipe.objects.filter(parent__isnull=True, setor=setor, nome__iexact=nome_b).first()
                if bloco is None:
                    bloco = GrupoEquipe(nome=nome_b, setor=setor, ordem=ordem_b)
                    bloco.clean()
                    bloco.save()
                    r["blocos_criados"] += 1
                for ordem_p, (nome_p, turnos) in enumerate(postos, start=1):
                    posto = bloco.subgrupos.filter(nome__iexact=nome_p).first()
                    if posto is None:
                        posto = GrupoEquipe(nome=nome_p, parent=bloco, ordem=ordem_p)
                        posto.clean()
                        posto.save()
                        r["postos_criados"] += 1
                    else:
                        r["postos_atualizados"] += 1
                    for t, tipo, valor in turnos:
                        if tipo == "pessoa":
                            _, criou = AlocacaoPosto.objects.get_or_create(
                                posto=posto, turno=t, colaborador_id=valor, defaults={"tipo": "PESSOA"}
                            )
                            r["colaboradores"] += criou
                        elif valor in ("VAGO", "RESERVA"):
                            # garante ao menos uma vaga/reserva no turno (reimportar não duplica)
                            if not AlocacaoPosto.objects.filter(posto=posto, turno=t, tipo=valor).exists():
                                AlocacaoPosto.objects.create(posto=posto, turno=t, tipo=valor)
                                r["vagos" if valor == "VAGO" else "reservas"] += 1
                        else:  # PARADO: o posto inteiro fica inativo
                            if posto.ativo:
                                posto.ativo = False
                                posto.save(update_fields=["ativo"])
                                r["postos_parados"] += 1
    except ValueError as exc:
        return _erro(str(exc))
    except Exception:
        logger.exception("Erro ao importar estrutura de equipes")
        return _erro("Não foi possível gravar a importação. Nada foi alterado.", 500)

    return JsonResponse({"success": True, "resumo": r, "setor": setor.nome})
