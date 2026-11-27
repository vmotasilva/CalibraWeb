# -*- coding: utf-8 -*-
"""Exportação da Estrutura de Equipes e Turnos para Excel: uma aba por setor."""
import logging
import re
from datetime import datetime
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_GET
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from organization.models import AlocacaoPosto, GrupoEquipe, SetorEquipe
from rh.views.estrutura_equipes import _erro, _negado, _pode_ver

logger = logging.getLogger(__name__)
_INVALIDOS_ABA = re.compile(r"[\[\]:*?/\\]")
_ORDEM_TIPO = {"PESSOA": 0, "RESERVA": 1, "VAGO": 2}
_COL_TOTAL = {"PESSOA": 0, "VAGO": 1, "RESERVA": 2}
_BORDA = Border(*(Side(style="thin", color="BFBFBF"),) * 4)
_FILL_CAB = PatternFill("solid", fgColor="1F2937")
_FILL_BLOCO = PatternFill("solid", fgColor="E5E7EB")
_FILL_VAGO = PatternFill("solid", fgColor="FDE2E2")
_FILL_RESERVA = PatternFill("solid", fgColor="D9F2F9")


def _nome_aba(nome, usados):
    base = (re.sub(r"\s+", " ", _INVALIDOS_ABA.sub(" ", nome)).strip() or "Setor")[:31]
    aba, n = base, 2
    while aba.lower() in usados:
        sufixo = f" ({n})"
        aba = base[: 31 - len(sufixo)] + sufixo
        n += 1
    usados.add(aba.lower())
    return aba


def _limpo(texto):
    """Remove caracteres de controle que o Excel não aceita (IllegalCharacterError do openpyxl)."""
    return ILLEGAL_CHARACTERS_RE.sub("", str(texto or ""))


def _texto_aloc(a):
    if a.tipo == "PESSOA":
        rotulo = a.colaborador.nome_completo if a.colaborador_id else "(sem colaborador)"
    elif a.tipo == "VAGO":
        rotulo = "VAGO"
    else:
        rotulo = "RESERVA"
    return _limpo(f"{rotulo} ({a.observacao})" if a.observacao else rotulo)


def _ordem_aloc(a):
    nome = a.colaborador.nome_completo.lower() if a.colaborador_id else ""
    return (_ORDEM_TIPO.get(a.tipo, 9), nome, a.id)


def _preenche_aba(ws, setor, grupos, alocs_por_celula):
    turnos = list(setor.turnos.all())
    ws.cell(row=1, column=1, value=_limpo(f"Setor: {setor.nome}")).font = Font(bold=True, size=14)
    ws.cell(row=2, column=1, value=f"Gerado em {timezone.localtime().strftime('%d/%m/%Y %H:%M')}").font = Font(italic=True, color="6B7280")
    if not turnos:
        ws.cell(row=4, column=1, value="Este setor ainda não tem turnos cadastrados.")
        ws.column_dimensions["A"].width = 60
        return
    cab = ["Bloco", "Posto de trabalho"] + [_limpo(t.nome) for t in turnos]
    for c, texto in enumerate(cab, 1):
        cel = ws.cell(row=4, column=c, value=texto)
        cel.font, cel.fill, cel.border = Font(bold=True, color="FFFFFF"), _FILL_CAB, _BORDA
        cel.alignment = Alignment(horizontal="center", vertical="center")
    linha = 5
    totais = {t.id: [0, 0, 0] for t in turnos}  # pessoas, vagas, reservas
    blocos = sorted((g for g in grupos if g.parent_id is None and g.setor_estrutura_id == setor.id), key=lambda g: g.nome.lower())
    for bloco in blocos:
        postos = sorted((g for g in grupos if g.parent_id == bloco.id), key=lambda g: g.nome.lower())
        if not postos:
            ws.cell(row=linha, column=1, value=_limpo(bloco.nome)).font = Font(bold=True)
            ws.cell(row=linha, column=2, value="(sem postos)").font = Font(italic=True, color="6B7280")
            for c in range(1, len(cab) + 1):
                ws.cell(row=linha, column=c).border = _BORDA
            linha += 1
            continue
        for posto in postos:
            ws.cell(row=linha, column=1, value=_limpo(bloco.nome)).font = Font(bold=True)
            ws.cell(row=linha, column=1).fill = _FILL_BLOCO
            ws.cell(row=linha, column=2, value=_limpo(posto.nome + ("" if posto.ativo else " (inativo)")))
            maior = 1
            for i, t in enumerate(turnos, 3):
                lista = sorted(alocs_por_celula.get((posto.id, t.id), []), key=_ordem_aloc)
                cel = ws.cell(row=linha, column=i, value="\n".join(_texto_aloc(a) for a in lista) or None)
                cel.alignment = Alignment(wrap_text=True, vertical="top")
                if any(a.tipo == "VAGO" for a in lista):
                    cel.fill = _FILL_VAGO
                elif any(a.tipo == "RESERVA" for a in lista):
                    cel.fill = _FILL_RESERVA
                maior = max(maior, len(lista))
                for a in lista:
                    totais[t.id][_COL_TOTAL.get(a.tipo, 0)] += 1
            for c in range(1, len(cab) + 1):
                ws.cell(row=linha, column=c).border = _BORDA
            ws.cell(row=linha, column=1).alignment = ws.cell(row=linha, column=2).alignment = Alignment(vertical="top", wrap_text=True)
            ws.row_dimensions[linha].height = max(18, 15 * maior)
            linha += 1
    # totais por turno
    ws.cell(row=linha, column=1, value="Total").font = Font(bold=True)
    for i, t in enumerate(turnos, 3):
        p, v, r = totais[t.id]
        cel = ws.cell(row=linha, column=i, value=f"{p} pessoa(s) · {v} vaga(s) · {r} reserva(s)")
        cel.font, cel.alignment = Font(bold=True), Alignment(horizontal="center")
    for c in range(1, len(cab) + 1):
        ws.cell(row=linha, column=c).border = _BORDA
        ws.cell(row=linha, column=c).fill = _FILL_BLOCO
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 30
    for i in range(3, len(cab) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 34
    ws.freeze_panes = "C5"
    ws.sheet_view.showGridLines = False


@login_required
@require_GET
def exportar_estrutura_equipes(request):
    """Excel com um setor por aba (linhas = postos por bloco; colunas = turnos do setor). ?setor=<id> exporta só um."""
    if not _pode_ver(request.user):
        return _negado()
    setores = SetorEquipe.objects.prefetch_related("turnos").order_by("nome")
    setor_param = (request.GET.get("setor") or "").strip()
    if setor_param:
        if not setor_param.isdigit():
            return _erro("Setor inválido.")
        setores = setores.filter(pk=int(setor_param))
        if not setores:
            return _erro("Setor não encontrado.", 404)
    setores = list(setores)
    grupos = list(GrupoEquipe.objects.all())
    alocs = AlocacaoPosto.objects.select_related("colaborador").all()
    por_celula = {}
    for a in alocs:
        por_celula.setdefault((a.posto_id, a.turno_estrutura_id), []).append(a)

    try:
        return _gera_planilha(setores, grupos, por_celula, setor_param)
    except Exception:  # não devolve página de erro do servidor para um download
        logger.exception("Erro ao exportar a estrutura de equipes")
        return _erro("Não foi possível gerar o Excel. Tente novamente.", 500)


def _gera_planilha(setores, grupos, por_celula, setor_param):
    wb = Workbook()
    wb.remove(wb.active)
    usados = set()
    for setor in setores:
        _preenche_aba(wb.create_sheet(_nome_aba(setor.nome, usados)), setor, grupos, por_celula)
    if not setores:
        ws = wb.create_sheet("Estrutura")
        ws.cell(row=1, column=1, value="Nenhum setor cadastrado.")
    buf = BytesIO()
    wb.save(buf)
    nome = "estrutura_equipes" + (f"_{slugify(setores[0].nome)}" if setor_param and setores else "") + f"_{datetime.now():%Y-%m-%d}.xlsx"
    resp = HttpResponse(buf.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{nome}"'
    return resp
