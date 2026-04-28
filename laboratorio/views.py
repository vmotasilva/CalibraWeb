import json
from collections import Counter
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import CategoriaLaboratorioForm, OcorrenciaLaboratorioForm
from .models import CategoriaLaboratorio, OcorrenciaLaboratorio


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _calcular_media_duracao(ocorrencias):
    duracoes = [ocorrencia.duracao for ocorrencia in ocorrencias if ocorrencia.duracao]
    if not duracoes:
        return None

    total = sum(duracoes, timedelta())
    return total / len(duracoes)


@login_required
def modulo_laboratorio_view(request):
    ocorrencias = list(
        OcorrenciaLaboratorio.objects.select_related("categoria", "responsavel")[:6]
    )
    hoje = timezone.localdate()
    inicio_mes = hoje.replace(day=1)
    ocorrencias_mes = list(
        OcorrenciaLaboratorio.objects.filter(
            data_abertura__date__gte=inicio_mes,
            data_abertura__date__lte=hoje,
        )
    )

    context = {
        "total_ocorrencias": OcorrenciaLaboratorio.objects.count(),
        "ocorrencias_abertas": OcorrenciaLaboratorio.objects.filter(data_encerramento__isnull=True).count(),
        "categorias_ativas": CategoriaLaboratorio.objects.filter(ativo=True).count(),
        "media_mes": OcorrenciaLaboratorio.formatar_duracao(_calcular_media_duracao(ocorrencias_mes)),
        "ocorrencias_recentes": ocorrencias,
    }
    return render(request, "laboratorio/modulo_laboratorio.html", context)


@login_required
def ocorrencias_list(request):
    ocorrencias = OcorrenciaLaboratorio.objects.select_related("categoria", "responsavel")
    filtros = {
        "q": (request.GET.get("q") or "").strip(),
        "impacto": request.GET.get("impacto") or "",
        "status": request.GET.get("status") or "",
        "inicio": request.GET.get("inicio") or "",
        "fim": request.GET.get("fim") or "",
    }

    inicio = _parse_date(filtros["inicio"])
    fim = _parse_date(filtros["fim"])

    if filtros["q"]:
        termo = filtros["q"]
        ocorrencias = ocorrencias.filter(
            Q(assunto__icontains=termo)
            | Q(detalhamento__icontains=termo)
            | Q(consequencias__icontains=termo)
        )

    if filtros["impacto"]:
        ocorrencias = ocorrencias.filter(impacto=filtros["impacto"])

    if filtros["status"] == "abertas":
        ocorrencias = ocorrencias.filter(data_encerramento__isnull=True)
    elif filtros["status"] == "encerradas":
        ocorrencias = ocorrencias.filter(data_encerramento__isnull=False)

    if inicio:
        ocorrencias = ocorrencias.filter(data_abertura__date__gte=inicio)
    if fim:
        ocorrencias = ocorrencias.filter(data_abertura__date__lte=fim)

    context = {
        "ocorrencias": ocorrencias.order_by("-data_abertura"),
        "impacto_choices": CategoriaLaboratorio.IMPACTO_CHOICES,
        "filtros": filtros,
    }
    return render(request, "laboratorio/ocorrencias_list.html", context)


@login_required
def ocorrencia_create(request):
    if request.method == "POST":
        form = OcorrenciaLaboratorioForm(request.POST, user=request.user)
        if form.is_valid():
            ocorrencia = form.save()
            messages.success(request, f"Ocorrencia '{ocorrencia.assunto}' registrada com sucesso.")
            return redirect("laboratorio:ocorrencias_list")
    else:
        form = OcorrenciaLaboratorioForm(user=request.user)

    categorias = list(CategoriaLaboratorio.objects.order_by("nome").values("id", "nome", "impacto"))
    context = {
        "form": form,
        "titulo": "Nova ocorrencia",
        "acao": "Registrar ocorrencia",
        "categorias_sugestoes": CategoriaLaboratorio.objects.order_by("nome"),
        "categorias_json": categorias,
        "duracao_atual": "Sera calculada automaticamente ao informar o encerramento.",
    }
    return render(request, "laboratorio/ocorrencia_form.html", context)


@login_required
def ocorrencia_update(request, pk):
    ocorrencia = get_object_or_404(OcorrenciaLaboratorio, pk=pk)
    if request.method == "POST":
        form = OcorrenciaLaboratorioForm(request.POST, instance=ocorrencia, user=request.user)
        if form.is_valid():
            ocorrencia = form.save()
            messages.success(request, f"Ocorrencia '{ocorrencia.assunto}' atualizada com sucesso.")
            return redirect("laboratorio:ocorrencias_list")
    else:
        form = OcorrenciaLaboratorioForm(instance=ocorrencia, user=request.user)

    categorias = list(CategoriaLaboratorio.objects.order_by("nome").values("id", "nome", "impacto"))
    context = {
        "form": form,
        "titulo": "Atualizar ocorrencia",
        "acao": "Salvar alteracoes",
        "categorias_sugestoes": CategoriaLaboratorio.objects.order_by("nome"),
        "categorias_json": categorias,
        "duracao_atual": ocorrencia.duracao_formatada,
        "ocorrencia": ocorrencia,
    }
    return render(request, "laboratorio/ocorrencia_form.html", context)


@login_required
def ocorrencia_detail(request, pk):
    ocorrencia = get_object_or_404(
        OcorrenciaLaboratorio.objects.select_related("categoria", "responsavel"),
        pk=pk,
    )
    return render(
        request,
        "laboratorio/ocorrencia_detail.html",
        {"ocorrencia": ocorrencia, "current_path": request.get_full_path()},
    )


@login_required
def ocorrencia_close(request, pk):
    ocorrencia = get_object_or_404(OcorrenciaLaboratorio, pk=pk)
    if request.method != "POST":
        return redirect("laboratorio:ocorrencia_detail", pk=ocorrencia.pk)

    if ocorrencia.data_encerramento:
        messages.info(request, f"A ocorrencia '{ocorrencia.assunto}' ja estava encerrada.")
    else:
        ocorrencia.data_encerramento = timezone.now()
        ocorrencia.save(update_fields=["data_encerramento", "duracao", "atualizado_em"])
        messages.success(request, f"Ocorrencia '{ocorrencia.assunto}' encerrada com sucesso.")

    next_url = request.POST.get("next") or reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk])
    return redirect(next_url)


@login_required
def ocorrencia_delete(request, pk):
    ocorrencia = get_object_or_404(OcorrenciaLaboratorio, pk=pk)
    if request.method != "POST":
        return redirect("laboratorio:ocorrencia_detail", pk=ocorrencia.pk)

    assunto = ocorrencia.assunto
    ocorrencia.delete()
    messages.success(request, f"Ocorrencia '{assunto}' excluida com sucesso.")
    return redirect("laboratorio:ocorrencias_list")


@login_required
def categorias_list(request):
    categorias = CategoriaLaboratorio.objects.annotate(total_ocorrencias=Count("ocorrencias")).order_by("nome")
    return render(
        request,
        "laboratorio/categorias_list.html",
        {"categorias": categorias},
    )


@login_required
def categoria_create(request):
    if request.method == "POST":
        form = CategoriaLaboratorioForm(request.POST)
        if form.is_valid():
            categoria = form.save()
            messages.success(request, f"Categoria '{categoria.nome}' criada com sucesso.")
            return redirect("laboratorio:categorias_list")
    else:
        form = CategoriaLaboratorioForm()

    return render(
        request,
        "laboratorio/categoria_form.html",
        {"form": form, "titulo": "Nova categoria", "acao": "Salvar categoria"},
    )


@login_required
def categoria_update(request, pk):
    categoria = get_object_or_404(CategoriaLaboratorio, pk=pk)
    if request.method == "POST":
        form = CategoriaLaboratorioForm(request.POST, instance=categoria)
        if form.is_valid():
            categoria = form.save()
            messages.success(request, f"Categoria '{categoria.nome}' atualizada com sucesso.")
            return redirect("laboratorio:categorias_list")
    else:
        form = CategoriaLaboratorioForm(instance=categoria)

    return render(
        request,
        "laboratorio/categoria_form.html",
        {"form": form, "titulo": "Editar categoria", "acao": "Salvar alteracoes", "categoria": categoria},
    )


@login_required
def dashboard_laboratorio(request):
    hoje = timezone.localdate()
    inicio_padrao = hoje.replace(day=1)

    inicio_str = request.GET.get("inicio") or inicio_padrao.strftime("%Y-%m-%d")
    fim_str = request.GET.get("fim") or hoje.strftime("%Y-%m-%d")
    impacto = request.GET.get("impacto") or ""

    inicio = _parse_date(inicio_str) or inicio_padrao
    fim = _parse_date(fim_str) or hoje

    ocorrencias = OcorrenciaLaboratorio.objects.select_related("categoria", "responsavel").filter(
        data_abertura__date__gte=inicio,
        data_abertura__date__lte=fim,
    )
    if impacto:
        ocorrencias = ocorrencias.filter(impacto=impacto)

    ocorrencias_lista = list(ocorrencias.order_by("-data_abertura"))
    total = len(ocorrencias_lista)
    abertas = sum(1 for ocorrencia in ocorrencias_lista if not ocorrencia.data_encerramento)
    encerradas = total - abertas
    media_duracao = _calcular_media_duracao(ocorrencias_lista)

    impacto_counter = Counter(ocorrencia.impacto for ocorrencia in ocorrencias_lista)
    por_impacto = [
        {"codigo": codigo, "nome": nome, "total": impacto_counter.get(codigo, 0)}
        for codigo, nome in CategoriaLaboratorio.IMPACTO_CHOICES
    ]

    categoria_counter = Counter(
        (ocorrencia.categoria.nome if ocorrencia.categoria else ocorrencia.assunto)
        for ocorrencia in ocorrencias_lista
    )
    por_categoria = [
        {"nome": nome, "total": total_categoria}
        for nome, total_categoria in categoria_counter.most_common(10)
    ]

    por_periodo_qs = (
        ocorrencias.annotate(periodo=TruncDate("data_abertura"))
        .values("periodo")
        .annotate(total=Count("id"))
        .order_by("periodo")
    )
    por_periodo = [
        {"periodo": item["periodo"].strftime("%d/%m/%Y"), "total": item["total"]}
        for item in por_periodo_qs
        if item["periodo"]
    ]

    context = {
        "inicio": inicio_str,
        "fim": fim_str,
        "impacto": impacto,
        "impacto_choices": CategoriaLaboratorio.IMPACTO_CHOICES,
        "total": total,
        "abertas": abertas,
        "encerradas": encerradas,
        "media_duracao": OcorrenciaLaboratorio.formatar_duracao(media_duracao),
        "por_impacto": por_impacto,
        "por_categoria": por_categoria,
        "por_periodo": por_periodo,
        "ocorrencias_recentes": ocorrencias_lista[:10],
        "chart_impacto_labels": json.dumps([item["nome"] for item in por_impacto]),
        "chart_impacto_values": json.dumps([item["total"] for item in por_impacto]),
        "chart_periodo_labels": json.dumps([item["periodo"] for item in por_periodo]),
        "chart_periodo_values": json.dumps([item["total"] for item in por_periodo]),
    }
    return render(request, "laboratorio/dashboard_laboratorio.html", context)
