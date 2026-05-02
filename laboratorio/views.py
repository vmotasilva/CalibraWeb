import json
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import (
    CategoriaLaboratorioForm,
    OcorrenciaAnotacaoForm,
    OcorrenciaEncerramentoForm,
    OcorrenciaLaboratorioForm,
)
from .models import CategoriaLaboratorio, OcorrenciaLaboratorio, OcorrenciaLaboratorioAnotacao


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_week(value):
    if not value:
        return None
    try:
        iso_year, iso_week = value.split("-W", maxsplit=1)
        return date.fromisocalendar(int(iso_year), int(iso_week), 1)
    except (TypeError, ValueError):
        return None


def _format_week_label(week_start):
    if not week_start:
        return ""
    week_end = week_start + timedelta(days=6)
    iso_year, iso_week, _ = week_start.isocalendar()
    return f"Semana {iso_week:02d}/{iso_year} ({week_start.strftime('%d/%m/%Y')} a {week_end.strftime('%d/%m/%Y')})"


def _calcular_media_duracao(ocorrencias):
    duracoes = [ocorrencia.duracao for ocorrencia in ocorrencias if ocorrencia.duracao]
    if not duracoes:
        return None

    total = sum(duracoes, timedelta())
    return total / len(duracoes)


def _get_ocorrencia_detail_queryset():
    return OcorrenciaLaboratorio.objects.select_related("categoria", "responsavel").prefetch_related(
        "anotacoes_registradas__usuario"
    )


def _build_ocorrencia_detail_context(
    request,
    ocorrencia,
    notes_form=None,
    close_form=None,
    open_modal=None,
    close_next=None,
):
    detail_url = reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk])
    return {
        "ocorrencia": ocorrencia,
        "current_path": detail_url,
        "close_next": close_next or request.GET.get("next") or detail_url,
        "notes_form": notes_form or OcorrenciaAnotacaoForm(),
        "close_form": close_form or OcorrenciaEncerramentoForm(instance=ocorrencia),
        "anotacoes_registradas": list(ocorrencia.anotacoes_registradas.all()),
        "open_modal": open_modal or request.GET.get("modal") or "",
    }


def _build_ocorrencia_form_context(form):
    categorias_sugestoes = CategoriaLaboratorio.objects.order_by("nome")
    maquinas_modal = []
    colaboradores_modal = []
    maquinas_categorias_map = {}
    colaboradores_setores_map = {}

    for maquina in form.fields["maquina"].queryset.select_related("categoria", "setor"):
        categoria_filtro = str(maquina.categoria_id) if maquina.categoria_id else "__none__"
        categoria_nome = maquina.categoria.nome if maquina.categoria_id else "Sem categoria"
        maquinas_categorias_map[categoria_filtro] = categoria_nome
        maquinas_modal.append(
            {
                "id": maquina.pk,
                "nome": maquina.display_name,
                "categoria_filtro": categoria_filtro,
                "categoria_nome": categoria_nome,
                "setor_nome": maquina.setor.nome if maquina.setor_id else "",
            }
        )

    for colaborador in form.fields["colaborador"].queryset.select_related("setor"):
        setor_filtro = str(colaborador.setor_id) if colaborador.setor_id else "__none__"
        setor_nome = colaborador.setor.nome if colaborador.setor_id else "Sem setor"
        colaboradores_setores_map[setor_filtro] = setor_nome
        colaboradores_modal.append(
            {
                "id": colaborador.pk,
                "nome": colaborador.nome_completo,
                "setor_filtro": setor_filtro,
                "setor_nome": setor_nome,
                "matricula": colaborador.matricula,
            }
        )

    maquina_atual = next(
        (
            maquina
            for maquina in maquinas_modal
            if str(maquina["id"]) == str(form["maquina"].value() or "")
        ),
        None,
    )
    colaborador_atual = next(
        (
            colaborador
            for colaborador in colaboradores_modal
            if str(colaborador["id"]) == str(form["colaborador"].value() or "")
        ),
        None,
    )

    maquinas_categorias_modal = [
        {"id": filtro, "nome": nome}
        for filtro, nome in sorted(
            maquinas_categorias_map.items(),
            key=lambda item: (item[1] == "Sem categoria", item[1].lower()),
        )
    ]
    colaboradores_setores_modal = [
        {"id": filtro, "nome": nome}
        for filtro, nome in sorted(
            colaboradores_setores_map.items(),
            key=lambda item: (item[1] == "Sem setor", item[1].lower()),
        )
    ]

    return {
        "categorias_sugestoes": categorias_sugestoes,
        "categorias_json": list(categorias_sugestoes.values("id", "nome", "impacto")),
        "maquinas_modal": maquinas_modal,
        "maquinas_categorias_modal": maquinas_categorias_modal,
        "colaboradores_modal": colaboradores_modal,
        "colaboradores_setores_modal": colaboradores_setores_modal,
        "maquina_resumo": maquina_atual["nome"] if maquina_atual else "Nenhuma máquina selecionada.",
        "maquina_detalhe": (
            "Categoria: "
            + maquina_atual["categoria_nome"]
            + (f" | Setor: {maquina_atual['setor_nome']}" if maquina_atual and maquina_atual["setor_nome"] else "")
        )
        if maquina_atual
        else "Abra o pop-up para filtrar por categoria e escolher a máquina.",
        "colaborador_resumo": colaborador_atual["nome"] if colaborador_atual else "Nenhum colaborador selecionado.",
        "colaborador_detalhe": (
            "Setor: "
            + colaborador_atual["setor_nome"]
            + (f" | Matrícula: {colaborador_atual['matricula']}" if colaborador_atual and colaborador_atual["matricula"] else "")
        )
        if colaborador_atual
        else "Abra o pop-up para filtrar por setor e escolher o colaborador.",
    }


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
    total_registros = OcorrenciaLaboratorio.objects.count()
    ocorrencias = OcorrenciaLaboratorio.objects.select_related("categoria", "responsavel")
    filtros = {
        "q": (request.GET.get("q") or "").strip(),
        "categoria": request.GET.get("categoria") or "",
        "semana": request.GET.get("semana") or "",
        "impacto": request.GET.get("impacto") or "",
        "status": request.GET.get("status") or "",
        "inicio": request.GET.get("inicio") or "",
        "fim": request.GET.get("fim") or "",
    }

    semana_inicio = _parse_week(filtros["semana"])
    semana_fim = semana_inicio + timedelta(days=6) if semana_inicio else None
    inicio = _parse_date(filtros["inicio"])
    fim = _parse_date(filtros["fim"])

    if filtros["q"]:
        termo = filtros["q"]
        ocorrencias = ocorrencias.filter(
            Q(assunto__icontains=termo)
            | Q(detalhamento__icontains=termo)
            | Q(consequencias__icontains=termo)
        )

    if filtros["categoria"]:
        ocorrencias = ocorrencias.filter(categoria_id=filtros["categoria"])

    if filtros["impacto"]:
        ocorrencias = ocorrencias.filter(impacto=filtros["impacto"])

    if filtros["status"] == "abertas":
        ocorrencias = ocorrencias.filter(data_encerramento__isnull=True)
    elif filtros["status"] == "encerradas":
        ocorrencias = ocorrencias.filter(data_encerramento__isnull=False)

    if semana_inicio and semana_fim:
        ocorrencias = ocorrencias.filter(data_abertura__date__lte=semana_fim).filter(
            Q(data_encerramento__isnull=True) | Q(data_encerramento__date__gte=semana_inicio)
        )

    if inicio:
        ocorrencias = ocorrencias.filter(data_abertura__date__gte=inicio)
    if fim:
        ocorrencias = ocorrencias.filter(data_abertura__date__lte=fim)

    total_filtrados = ocorrencias.count()

    context = {
        "ocorrencias": ocorrencias.order_by("-data_abertura"),
        "categorias": CategoriaLaboratorio.objects.order_by("nome"),
        "impacto_choices": CategoriaLaboratorio.IMPACTO_CHOICES,
        "filtros": filtros,
        "semana_filtro_label": _format_week_label(semana_inicio),
        "total_filtrados": total_filtrados,
        "total_registros": total_registros,
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

    context = {
        "form": form,
        "titulo": "Nova ocorrencia",
        "acao": "Registrar ocorrencia",
        "duracao_atual": "Sera calculada automaticamente ao informar o encerramento.",
    }
    context.update(_build_ocorrencia_form_context(form))
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

    context = {
        "form": form,
        "titulo": "Atualizar ocorrencia",
        "acao": "Salvar alteracoes",
        "duracao_atual": ocorrencia.duracao_formatada,
        "ocorrencia": ocorrencia,
    }
    context.update(_build_ocorrencia_form_context(form))
    return render(request, "laboratorio/ocorrencia_form.html", context)


@login_required
def ocorrencia_detail(request, pk):
    ocorrencia = get_object_or_404(
        _get_ocorrencia_detail_queryset(),
        pk=pk,
    )
    return render(request, "laboratorio/ocorrencia_detail.html", _build_ocorrencia_detail_context(request, ocorrencia))


@login_required
def ocorrencia_notes(request, pk):
    ocorrencia = get_object_or_404(
        _get_ocorrencia_detail_queryset(),
        pk=pk,
    )
    detail_url = reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk])
    if request.method != "POST":
        return redirect(detail_url)

    form = OcorrenciaAnotacaoForm(request.POST)
    if form.is_valid():
        anotacao = form.save(commit=False)
        anotacao.ocorrencia = ocorrencia
        anotacao.usuario = request.user
        anotacao.save()
        messages.success(request, f"Nova anotacao registrada para a ocorrencia '{ocorrencia.assunto}'.")
        return redirect(detail_url)

    context = _build_ocorrencia_detail_context(
        request,
        ocorrencia,
        notes_form=form,
        open_modal="anotacoes",
    )
    return render(request, "laboratorio/ocorrencia_detail.html", context)


@login_required
def ocorrencia_close(request, pk):
    ocorrencia = get_object_or_404(
        _get_ocorrencia_detail_queryset(),
        pk=pk,
    )
    detail_url = reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk])
    if request.method != "POST":
        return redirect(detail_url)

    close_next = request.POST.get("next") or detail_url
    ja_estava_encerrada = bool(ocorrencia.data_encerramento)
    form = OcorrenciaEncerramentoForm(request.POST, instance=ocorrencia)
    if form.is_valid():
        ocorrencia = form.save()
        if ja_estava_encerrada:
            messages.success(
                request,
                f"Dados de encerramento da ocorrencia '{ocorrencia.assunto}' atualizados com sucesso.",
            )
        else:
            messages.success(request, f"Ocorrencia '{ocorrencia.assunto}' encerrada com sucesso.")
        return redirect(close_next)

    context = _build_ocorrencia_detail_context(
        request,
        ocorrencia,
        close_form=form,
        open_modal="encerramento",
        close_next=close_next,
    )
    return render(request, "laboratorio/ocorrencia_detail.html", context)


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
    taxa_encerramento = (encerradas / total * 100) if total else 0
    total_horas_indisponibilidade = sum(
        (ocorrencia.horas_indisponibilidade or Decimal("0"))
        for ocorrencia in ocorrencias_lista
    )
    total_impacto_financeiro = sum(
        (ocorrencia.impacto_financeiro or Decimal("0"))
        for ocorrencia in ocorrencias_lista
    )
    impactos_registrados = sum(1 for ocorrencia in ocorrencias_lista if ocorrencia.possui_impacto_registrado)

    impacto_counter = Counter(ocorrencia.impacto for ocorrencia in ocorrencias_lista)
    por_impacto = [
        {"codigo": codigo, "nome": nome, "total": impacto_counter.get(codigo, 0)}
        for codigo, nome in CategoriaLaboratorio.IMPACTO_CHOICES
    ]

    categoria_counter = Counter(
        ocorrencia.categoria.nome for ocorrencia in ocorrencias_lista if ocorrencia.categoria
    )
    sem_categoria = sum(1 for ocorrencia in ocorrencias_lista if not ocorrencia.categoria)
    if sem_categoria:
        categoria_counter["Sem categoria definida"] = sem_categoria
    por_categoria = [
        {"nome": nome, "total": total_categoria}
        for nome, total_categoria in categoria_counter.most_common(10)
    ]

    assunto_counter = Counter(
        ocorrencia.assunto for ocorrencia in ocorrencias_lista if ocorrencia.assunto
    )
    por_assunto = [
        {"nome": nome, "total": total_assunto}
        for nome, total_assunto in assunto_counter.most_common(10)
    ]

    perdas_por_unidade_map = {}
    for ocorrencia in ocorrencias_lista:
        if not ocorrencia.perda_producao:
            continue
        unidade = ocorrencia.unidade_perda_producao or "Sem unidade definida"
        perdas_por_unidade_map[unidade] = perdas_por_unidade_map.get(unidade, Decimal("0")) + ocorrencia.perda_producao

    perdas_por_unidade = [
        {"unidade": unidade, "total": total_perdido}
        for unidade, total_perdido in sorted(
            perdas_por_unidade_map.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]

    ocorrencias_prioritarias = [
        ocorrencia
        for ocorrencia in ocorrencias_lista
        if not ocorrencia.data_encerramento
        and ocorrencia.impacto in (
            CategoriaLaboratorio.IMPACTO_ALTO,
            CategoriaLaboratorio.IMPACTO_CRITICO,
        )
    ][:5]

    resumo_executivo = []
    if total:
        resumo_executivo.append(
            f"{total} ocorrencias registradas no periodo, com taxa de encerramento de {taxa_encerramento:.1f}% e {abertas} ainda em aberto."
        )
        if por_categoria:
            resumo_executivo.append(
                f"A categoria mais recorrente foi {por_categoria[0]['nome']} ({por_categoria[0]['total']} registros)."
            )
        if por_assunto:
            resumo_executivo.append(
                f"O assunto mais recorrente foi {por_assunto[0]['nome']} ({por_assunto[0]['total']} registros)."
            )
        if total_impacto_financeiro:
            resumo_executivo.append(
                f"O impacto financeiro estimado acumulado no recorte foi de R$ {total_impacto_financeiro:.2f}."
            )
        if ocorrencias_prioritarias:
            resumo_executivo.append(
                f"Existem {len(ocorrencias_prioritarias)} ocorrencias abertas com prioridade alta ou critica exigindo acompanhamento gerencial."
            )
    else:
        resumo_executivo.append("Nao ha ocorrencias no periodo selecionado para compor o relatorio gerencial.")

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
        "taxa_encerramento": taxa_encerramento,
        "media_duracao": OcorrenciaLaboratorio.formatar_duracao(media_duracao),
        "impactos_registrados": impactos_registrados,
        "total_horas_indisponibilidade": total_horas_indisponibilidade,
        "total_impacto_financeiro": total_impacto_financeiro,
        "perdas_por_unidade": perdas_por_unidade,
        "por_impacto": por_impacto,
        "por_categoria": por_categoria,
        "por_assunto": por_assunto,
        "por_periodo": por_periodo,
        "resumo_executivo": resumo_executivo,
        "ocorrencias_prioritarias": ocorrencias_prioritarias,
        "ocorrencias_recentes": ocorrencias_lista[:10],
        "chart_impacto_labels": json.dumps([item["nome"] for item in por_impacto]),
        "chart_impacto_values": json.dumps([item["total"] for item in por_impacto]),
        "chart_periodo_labels": json.dumps([item["periodo"] for item in por_periodo]),
        "chart_periodo_values": json.dumps([item["total"] for item in por_periodo]),
    }
    return render(request, "laboratorio/dashboard_laboratorio.html", context)
