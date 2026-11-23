"""Auditoria Livre: auditoria sem norma/checklist, baseada em solicitação de evidência.

O auditor define objetivo/escopo, vai solicitando evidências e direciona cada uma como
Conforme, Não Conformidade, Oportunidade de Melhoria (ou N/A / Pendente).
"""
import io
import json
import re
from datetime import date

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import AuditoriaLivre, SolicitacaoLivre

CLASSIFICACOES = dict(SolicitacaoLivre.CLASSIFICACAO_CHOICES)


def _parse_date(value):
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        return None


def _next_url(request, default):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return nxt
    return default


def _serialize(sol):
    return {
        "id": sol.id,
        "topico": sol.topico,
        "solicitacao": sol.solicitacao,
        "evidencia": sol.evidencia,
        "conclusao": sol.conclusao,
        "grau_nc": sol.grau_nc or "",
        "observacao": sol.observacao,
    }


# ------------------------------------------------------------------ lista

@login_required
def livre_list(request):
    mostrar_arquivadas = request.GET.get("arquivadas") == "1"
    total_arquivadas = AuditoriaLivre.objects.filter(arquivada=True).count()
    auditorias = list(AuditoriaLivre.objects.filter(arquivada=mostrar_arquivadas))
    for aud in auditorias:
        aud.res = aud.resumo()
    return render(request, "auditoria/livre_list.html", {
        "auditorias": auditorias,
        "mostrar_arquivadas": mostrar_arquivadas,
        "total_arquivadas": total_arquivadas,
    })


# ------------------------------------------------------------- criar/editar

def _salvar_form(request, aud):
    """Aplica o POST na auditoria. Retorna mensagem de erro ou None."""
    titulo = (request.POST.get("titulo") or "").strip()
    data_inicio = _parse_date(request.POST.get("data_inicio"))
    data_fim = _parse_date(request.POST.get("data_fim"))
    if not titulo:
        return "Informe o título da auditoria."
    if not data_inicio:
        return "Informe a data de início."
    if data_fim and data_fim < data_inicio:
        return "A data de fim não pode ser anterior à data de início."

    aud.titulo = titulo
    aud.objetivo = (request.POST.get("objetivo") or "").strip()
    aud.escopo = (request.POST.get("escopo") or "").strip()
    aud.criterio = (request.POST.get("criterio") or "").strip()
    aud.local = (request.POST.get("local") or "").strip()
    aud.auditor_lider = (request.POST.get("auditor_lider") or "").strip()
    aud.auditados = (request.POST.get("auditados") or "").strip()
    aud.data_inicio = data_inicio
    aud.data_fim = data_fim
    if not aud.pk:
        aud.criado_por = request.user
    aud.save()

    ids = [int(i) for i in request.POST.getlist("auditores") if i.isdigit()]
    aud.auditores.set(get_user_model().objects.filter(pk__in=ids, is_active=True))
    return None


def _form_context(aud):
    User = get_user_model()
    return {
        "aud": aud,
        "usuarios": User.objects.filter(is_active=True).order_by("first_name", "username"),
        "selecionados": set(aud.auditores.values_list("pk", flat=True)) if aud and aud.pk else set(),
    }


@login_required
def livre_create(request):
    aud = AuditoriaLivre(data_inicio=date.today())
    if request.method == "POST":
        erro = _salvar_form(request, aud)
        if not erro:
            messages.success(request, "Auditoria livre criada. Comece a solicitar evidências.")
            return redirect("auditoria:livre_execucao", pk=aud.pk)
        messages.error(request, erro)
    ctx = _form_context(aud)
    if request.method == "POST":
        ctx["selecionados"] = {int(i) for i in request.POST.getlist("auditores") if i.isdigit()}
    return render(request, "auditoria/livre_form.html", ctx)


@login_required
def livre_edit(request, pk):
    aud = get_object_or_404(AuditoriaLivre, pk=pk)
    if request.method == "POST":
        erro = _salvar_form(request, aud)
        if not erro:
            messages.success(request, "Dados da auditoria atualizados.")
            return redirect("auditoria:livre_execucao", pk=aud.pk)
        messages.error(request, erro)
    return render(request, "auditoria/livre_form.html", _form_context(aud))


# ------------------------------------------------------------------ execução

@login_required
def livre_execucao(request, pk):
    aud = get_object_or_404(AuditoriaLivre, pk=pk)
    if aud.status == "PLANEJADA":
        aud.status = "EM_ANDAMENTO"
        aud.save(update_fields=["status", "atualizado_em"])
    solicitacoes = [_serialize(s) for s in aud.solicitacoes.all()]
    topicos = sorted(
        {s["topico"] for s in solicitacoes if s["topico"]}, key=str.casefold
    )
    return render(request, "auditoria/livre_execucao.html", {
        "aud": aud,
        "solicitacoes_json": solicitacoes,
        "topicos": topicos,
        "classificacoes": SolicitacaoLivre.CLASSIFICACAO_CHOICES,
        "resumo": aud.resumo(),
    })


# ---------------------------------------------------------------------- API

def _json_body(request):
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _aplicar(sol, data):
    """Aplica campos válidos do payload. Retorna mensagem de erro ou None."""
    if "topico" in data:
        sol.topico = str(data["topico"] or "").strip()[:255]
    if "solicitacao" in data:
        texto = str(data["solicitacao"] or "").strip()
        if not texto:
            return "Descreva a evidência solicitada."
        sol.solicitacao = texto
    if "evidencia" in data:
        sol.evidencia = str(data["evidencia"] or "").strip()
    if "observacao" in data:
        sol.observacao = str(data["observacao"] or "").strip()
    if "conclusao" in data:
        if data["conclusao"] not in CLASSIFICACOES:
            return "Classificação inválida."
        sol.conclusao = data["conclusao"]
    if "grau_nc" in data:
        sol.grau_nc = data["grau_nc"] if data["grau_nc"] in ("MENOR", "MAIOR") else None
    if sol.conclusao != "NC":
        sol.grau_nc = None
    return None


@login_required
@require_POST
def api_livre_sol_create(request, pk):
    aud = get_object_or_404(AuditoriaLivre, pk=pk)
    data = _json_body(request)
    if data is None:
        return JsonResponse({"success": False, "error": "Requisição inválida."}, status=400)
    sol = SolicitacaoLivre(auditoria=aud, criado_por=request.user)
    erro = None if str(data.get("solicitacao") or "").strip() else "Descreva a evidência solicitada."
    erro = erro or _aplicar(sol, data)
    if erro:
        return JsonResponse({"success": False, "error": erro}, status=400)
    sol.ordem = (aud.solicitacoes.aggregate(m=Max("ordem"))["m"] or 0) + 1
    sol.save()
    return JsonResponse({"success": True, "solicitacao": _serialize(sol), "resumo": aud.resumo()})


@login_required
@require_POST
def api_livre_sol_update(request, pk):
    sol = get_object_or_404(SolicitacaoLivre, pk=pk)
    data = _json_body(request)
    if data is None:
        return JsonResponse({"success": False, "error": "Requisição inválida."}, status=400)
    erro = _aplicar(sol, data)
    if erro:
        return JsonResponse({"success": False, "error": erro}, status=400)
    sol.save()
    return JsonResponse({"success": True, "solicitacao": _serialize(sol), "resumo": sol.auditoria.resumo()})


@login_required
@require_POST
def api_livre_sol_delete(request, pk):
    sol = get_object_or_404(SolicitacaoLivre, pk=pk)
    aud = sol.auditoria
    sol.delete()
    return JsonResponse({"success": True, "resumo": aud.resumo()})


@login_required
@require_POST
def api_livre_conclusao_salvar(request, pk):
    aud = get_object_or_404(AuditoriaLivre, pk=pk)
    data = _json_body(request)
    if data is None:
        return JsonResponse({"success": False, "error": "Requisição inválida."}, status=400)
    aud.conclusao_texto = str(data.get("conclusao_texto") or "").strip()
    aud.save(update_fields=["conclusao_texto", "atualizado_em"])
    return JsonResponse({"success": True})


# -------------------------------------------------------- ações da auditoria

@login_required
@require_POST
def livre_toggle_conclusao(request, pk):
    aud = get_object_or_404(AuditoriaLivre, pk=pk)
    if aud.status == "CONCLUIDA":
        aud.status = "EM_ANDAMENTO"
        messages.success(request, "Auditoria reaberta.")
    else:
        aud.status = "CONCLUIDA"
        if not aud.data_fim:
            aud.data_fim = date.today()
        pendentes = aud.solicitacoes.filter(conclusao="P").count()
        if pendentes:
            messages.warning(
                request,
                f"Auditoria concluída com {pendentes} solicitação(ões) ainda pendente(s) de classificação.",
            )
        else:
            messages.success(request, "Auditoria concluída.")
    aud.save()
    return redirect(_next_url(request, reverse("auditoria:livre_execucao", args=[aud.pk])))


@login_required
@require_POST
def livre_arquivar(request, pk):
    aud = get_object_or_404(AuditoriaLivre, pk=pk)
    aud.arquivada = not aud.arquivada
    aud.save(update_fields=["arquivada", "atualizado_em"])
    messages.success(request, "Auditoria arquivada." if aud.arquivada else "Auditoria desarquivada.")
    return redirect(_next_url(request, reverse("auditoria:livre_list")))


@login_required
@require_POST
def livre_delete(request, pk):
    aud = get_object_or_404(AuditoriaLivre, pk=pk)
    if not aud.arquivada:
        messages.error(request, "Arquive a auditoria antes de excluí-la.")
        return redirect(_next_url(request, reverse("auditoria:livre_list")))
    aud.delete()
    messages.success(request, "Auditoria excluída.")
    return redirect(reverse("auditoria:livre_list") + "?arquivadas=1")


# ------------------------------------------------------------------- Excel

@login_required
def livre_export_excel(request, pk):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    aud = get_object_or_404(AuditoriaLivre, pk=pk)
    wb = Workbook()

    ws = wb.active
    ws.title = "Resumo"
    resumo = aud.resumo()
    linhas = [
        ("Título", aud.titulo),
        ("Objetivo", aud.objetivo),
        ("Escopo", aud.escopo),
        ("Critério / Referência", aud.criterio),
        ("Local / Setor / Processo", aud.local),
        ("Auditor líder", aud.auditor_lider),
        ("Auditores", ", ".join(u.get_full_name() or u.get_username() for u in aud.auditores.all())),
        ("Auditados", aud.auditados),
        ("Período", f"{aud.data_inicio:%d/%m/%Y}" + (f" a {aud.data_fim:%d/%m/%Y}" if aud.data_fim else "")),
        ("Status", aud.get_status_display()),
        ("", ""),
        ("Total de solicitações", resumo["total"]),
    ] + [(label, resumo[cod]) for cod, label in SolicitacaoLivre.CLASSIFICACAO_CHOICES] + [
        ("", ""),
        ("Conclusão / Parecer", aud.conclusao_texto),
    ]
    for r, (k, v) in enumerate(linhas, start=1):
        ws.cell(row=r, column=1, value=k).font = Font(bold=True)
        c = ws.cell(row=r, column=2, value=v)
        c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 90

    ws2 = wb.create_sheet("Evidências")
    cab = ["#", "Tópico", "Evidência solicitada", "Evidência apresentada", "Classificação", "Grau NC", "Observação"]
    fill = PatternFill("solid", fgColor="1F2937")
    for col, titulo in enumerate(cab, start=1):
        c = ws2.cell(row=1, column=col, value=titulo)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = fill
    cores = {"C": "D1FAE5", "NC": "FEE2E2", "OM": "FEF3C7", "NA": "E5E7EB", "P": "FFFFFF"}
    for i, s in enumerate(aud.solicitacoes.all(), start=1):
        valores = [
            i, s.topico, s.solicitacao, s.evidencia, s.get_conclusao_display(),
            s.get_grau_nc_display() if s.grau_nc else "", s.observacao,
        ]
        for col, v in enumerate(valores, start=1):
            c = ws2.cell(row=i + 1, column=col, value=v)
            c.alignment = Alignment(wrap_text=True, vertical="top")
        ws2.cell(row=i + 1, column=5).fill = PatternFill("solid", fgColor=cores.get(s.conclusao, "FFFFFF"))
    for col, w in enumerate([5, 24, 50, 50, 24, 12, 40], start=1):
        ws2.column_dimensions[get_column_letter(col)].width = w
    ws2.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    nome = re.sub(r"[^a-zA-Z0-9_-]+", "_", aud.titulo).strip("_")[:60] or "auditoria"
    resp = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="Auditoria_Livre_{nome}_{aud.pk}.xlsx"'
    return resp
