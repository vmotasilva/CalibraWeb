"""Nova execução e comparação de execuções da Auditoria Livre."""
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import AuditoriaLivre
from .services.comparativo_livre_export import frase_resumo, gerar_docx, gerar_excel
from .services.evolucao_livre import ExecucaoInvalida, comparar, criar_nova_execucao, serie


@login_required
@require_POST
def livre_nova_execucao(request, pk):
    aud = get_object_or_404(AuditoriaLivre, pk=pk)
    try:
        nova = criar_nova_execucao(aud, request.user, somente_pendencias=request.POST.get("somente_pendencias") == "1")
    except ExecucaoInvalida as e:
        messages.error(request, str(e))
        proxima = aud.proximas.order_by("id").first()
        return redirect("auditoria:livre_execucao", pk=proxima.pk if proxima else aud.pk)
    messages.success(
        request,
        f"Execução {nova.execucao} criada com {nova.solicitacoes.count()} item(ns) para reavaliar. "
        "O resultado da execução anterior aparece em cada item.",
    )
    return redirect("auditoria:livre_execucao", pk=nova.pk)


def _base_da_comparacao(atual, com):
    """Execução de comparação: a pedida (`?com=`), se anterior e da mesma série, senão a imediatamente anterior."""
    anteriores = [a for a in atual.cadeia() if a.execucao < atual.execucao]
    if com and str(com).isdigit():
        escolhida = next((a for a in anteriores if a.pk == int(com)), None)
        if escolhida:
            return escolhida, anteriores
    return (atual.anterior if atual.anterior_id else None), anteriores


def _comparacao(request, pk):
    atual = get_object_or_404(AuditoriaLivre, pk=pk)
    base, anteriores = _base_da_comparacao(atual, request.GET.get("com"))
    return atual, base, anteriores, (comparar(atual, base) if base else None)


@login_required
def livre_comparar(request, pk):
    atual, base, anteriores, comp = _comparacao(request, pk)
    serie_exec = serie(atual) if len(atual.cadeia()) > 1 else []
    return render(request, "auditoria/livre_comparar.html", {
        "aud": atual, "base": base, "anteriores": anteriores, "comp": comp,
        "frase": frase_resumo(comp) if comp else "",
        "proxima": atual.proximas.order_by("id").first(),
        "serie": serie_exec,
        "serie_json": [
            {"execucao": x["execucao"], "data": f"{x['data']:%d/%m/%Y}", "indice": x["res"]["indice"],
             "nc": x["res"]["NC"], "atual": x["aud"].pk == atual.pk}
            for x in serie_exec
        ],
    })


def _nome_arquivo(aud, tipo, ext):
    nome = re.sub(r"[^a-zA-Z0-9_-]+", "_", aud.titulo).strip("_")[:50] or "auditoria"
    return f"Comparativo_{tipo}_{nome}_exec{aud.execucao}.{ext}"


@login_required
def livre_comparar_excel(request, pk):
    atual, base, _, comp = _comparacao(request, pk)
    if not comp:
        messages.error(request, "Esta é a primeira execução: não há com o que comparar.")
        return redirect("auditoria:livre_execucao", pk=atual.pk)
    resp = HttpResponse(
        gerar_excel(comp).getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{_nome_arquivo(atual, "Excel", "xlsx")}"'
    return resp


@login_required
def livre_comparar_docx(request, pk):
    atual, base, _, comp = _comparacao(request, pk)
    if not comp:
        messages.error(request, "Esta é a primeira execução: não há com o que comparar.")
        return redirect("auditoria:livre_execucao", pk=atual.pk)
    resp = HttpResponse(
        gerar_docx(comp).getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    resp["Content-Disposition"] = f'attachment; filename="{_nome_arquivo(atual, "Relatorio", "docx")}"'
    return resp
