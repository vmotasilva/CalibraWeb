import json
import io
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.http import JsonResponse
import json

from .forms import (
    CategoriaLaboratorioForm,
    OcorrenciaAnotacaoForm,
    OcorrenciaEncerramentoForm,
    OcorrenciaLaboratorioForm,
    TratamentoAntiReflexoForm,
    RegraTurnoCoatingForm,
    RegistroCoatingForm,
    NovoLoteCoatingForm,
    TurnoCoatingForm,
)
from django.db.models import Q
from .models import (
    CategoriaLaboratorio, 
    OcorrenciaLaboratorio, 
    OcorrenciaLaboratorioAnotacao,
    TratamentoAntiReflexo,
    RegraTurnoCoating,
    TurnoCoating,
    RegistroCoating,
)
from maquinas.models import Maquina


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


def _is_absenteismo_ocorrencia(ocorrencia):
    categoria_nome = (ocorrencia.categoria.nome if ocorrencia.categoria else "")
    texto = f"{categoria_nome} {ocorrencia.assunto or ''}".lower()
    return "falta de colaborador" in texto or "absenteismo" in texto or "absente\u00edsmo" in texto


def _duracao_em_horas(ocorrencia):
    duracao = ocorrencia.duracao
    if not duracao and ocorrencia.data_abertura and not ocorrencia.data_encerramento:
        duracao = timezone.now() - ocorrencia.data_abertura
    if not duracao:
        return Decimal("0")
    return Decimal(str(duracao.total_seconds())) / Decimal("3600")


def _build_contexto_personalizado(ocorrencia):
    if ocorrencia.colaborador:
        return ocorrencia.colaborador.nome_completo

    if ocorrencia.maquina:
        return str(ocorrencia.maquina)

    return "-"


def _calcular_media_duracao(ocorrencias):
    duracoes = [ocorrencia.duracao for ocorrencia in ocorrencias if ocorrencia.duracao]
    if not duracoes:
        return None

    total = sum(duracoes, timedelta())
    return total / len(duracoes)


def _get_ocorrencia_detail_queryset():
    return OcorrenciaLaboratorio.objects.select_related("categoria", "responsavel", "criado_por").prefetch_related(
        "anotacoes_registradas__usuario"
    )


def _can_user_close_occurrence(user, ocorrencia):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return ocorrencia.criado_por_id == user.id


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
        "can_close_occurrence": _can_user_close_occurrence(request.user, ocorrencia),
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
        "categorias_json": [
            {
                "id": categoria.id,
                "nome": categoria.nome,
                "impacto": categoria.impacto,
                "exige_colaborador": categoria.exige_colaborador,
                "exige_maquina": categoria.exige_maquina,
            }
            for categoria in categorias_sugestoes
        ],
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
    ocorrencias = OcorrenciaLaboratorio.objects.select_related(
        "categoria",
        "responsavel",
        "colaborador",
        "maquina",
    )
    filtros = {
        "q": (request.GET.get("q") or "").strip(),
        "categoria": request.GET.get("categoria") or "",
        "responsavel": request.GET.get("responsavel") or "",
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

    if filtros["responsavel"]:
        ocorrencias = ocorrencias.filter(responsavel_id=filtros["responsavel"])

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

    from django.contrib.auth import get_user_model
    responsaveis = get_user_model().objects.order_by("first_name", "username")

    context = {
        "ocorrencias": ocorrencias.order_by("-data_abertura"),
        "categorias": CategoriaLaboratorio.objects.order_by("nome"),
        "responsaveis": responsaveis,
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
            ocorrencia = form.save(commit=False)
            if not ocorrencia.criado_por_id:
                ocorrencia.criado_por = request.user
            ocorrencia.save()
            messages.success(request, f"Ocorrencia '{ocorrencia.assunto}' registrada com sucesso.")
            return redirect("laboratorio:ocorrencias_list")
    else:
        initial = {}
        maquina_id = (request.GET.get("maquina_id") or "").strip()
        if maquina_id:
            initial["maquina"] = maquina_id
        form = OcorrenciaLaboratorioForm(initial=initial, user=request.user)

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

    if not _can_user_close_occurrence(request.user, ocorrencia):
        messages.error(
            request,
            "Apenas quem criou a ocorrencia ou um usuario staff/superuser pode encerra-la.",
        )
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
def _build_dashboard_context(request):
    hoje = timezone.localdate()
    inicio_padrao = hoje.replace(day=1)

    semana = request.GET.get("semana") or ""
    inicio_param = request.GET.get("inicio") or ""
    fim_param = request.GET.get("fim") or ""

    semana_inicio = _parse_week(semana)
    semana_fim = semana_inicio + timedelta(days=6) if semana_inicio else None

    if semana_inicio and semana_fim:
        inicio_str = semana_inicio.strftime("%Y-%m-%d")
        fim_str = semana_fim.strftime("%Y-%m-%d")
    else:
        inicio_str = inicio_param or inicio_padrao.strftime("%Y-%m-%d")
        fim_str = fim_param or hoje.strftime("%Y-%m-%d")

    impacto = request.GET.get("impacto") or ""

    inicio = _parse_date(inicio_str)
    fim = _parse_date(fim_str)

    ocorrencias = OcorrenciaLaboratorio.objects.select_related(
        "categoria",
        "responsavel",
        "colaborador",
        "maquina",
    )

    if semana_inicio and semana_fim:
        ocorrencias = ocorrencias.filter(data_abertura__date__lte=semana_fim).filter(
            Q(data_encerramento__isnull=True) | Q(data_encerramento__date__gte=semana_inicio)
        )
    else:
        if inicio:
            ocorrencias = ocorrencias.filter(data_abertura__date__gte=inicio)
        if fim:
            ocorrencias = ocorrencias.filter(data_abertura__date__lte=fim)

    if impacto:
        ocorrencias = ocorrencias.filter(impacto=impacto)

    ocorrencias_lista = list(ocorrencias.order_by("-data_abertura"))
    total = len(ocorrencias_lista)
    abertas = sum(1 for ocorrencia in ocorrencias_lista if not ocorrencia.data_encerramento)
    encerradas = total - abertas
    media_duracao = _calcular_media_duracao(ocorrencias_lista)
    taxa_encerramento = (encerradas / total * 100) if total else 0
    total_absenteismo_horas = sum(
        (_duracao_em_horas(ocorrencia) for ocorrencia in ocorrencias_lista if _is_absenteismo_ocorrencia(ocorrencia)),
        Decimal("0"),
    )



    # Calcular totais por categoria, incluindo horas (em horas e minutos)
    categoria_horas = {}
    categoria_counter = Counter()
    sem_categoria_total = 0
    sem_categoria_horas = 0
    for ocorrencia in ocorrencias_lista:
        nome = ocorrencia.categoria.nome if ocorrencia.categoria else "Sem categoria definida"
        horas = float(_duracao_em_horas(ocorrencia))
        if ocorrencia.categoria:
            categoria_counter[nome] += 1
            categoria_horas[nome] = categoria_horas.get(nome, 0) + horas
        else:
            sem_categoria_total += 1
            sem_categoria_horas += horas
    if sem_categoria_total:
        categoria_counter["Sem categoria definida"] = sem_categoria_total
        categoria_horas["Sem categoria definida"] = sem_categoria_horas

    def formatar_horas_minutos(valor_horas):
        total_min = int(round(valor_horas * 60))
        horas = total_min // 60
        minutos = total_min % 60
        if horas:
            return f"{horas}h {minutos}min"
        return f"{minutos}min"

    por_categoria = [
        {"nome": nome, "total": total_categoria, "horas": categoria_horas.get(nome, 0), "horas_formatada": formatar_horas_minutos(categoria_horas.get(nome, 0))}
        for nome, total_categoria in categoria_counter.most_common(10)
    ]

    # Remover cálculo e uso de por_assunto
    por_assunto = []

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

    ocorrencias_recentes = ocorrencias_lista[:20]
    ocorrencias_recentes_por_categoria = []
    grupos_recentes = {}

    for ocorrencia in ocorrencias_recentes:
        categoria_nome = ocorrencia.categoria.nome if ocorrencia.categoria else "Sem categoria definida"
        if categoria_nome not in grupos_recentes:
            grupos_recentes[categoria_nome] = {
                "categoria": categoria_nome,
                "ocorrencias": [],
                "total_horas": 0.0,
            }
            ocorrencias_recentes_por_categoria.append(grupos_recentes[categoria_nome])

        grupos_recentes[categoria_nome]["ocorrencias"].append(
            {
                "obj": ocorrencia,
                "contexto_personalizado": _build_contexto_personalizado(ocorrencia),
            }
        )
        grupos_recentes[categoria_nome]["total_horas"] += float(_duracao_em_horas(ocorrencia))

    for grupo in ocorrencias_recentes_por_categoria:
        grupo["total"] = len(grupo["ocorrencias"])
        grupo["total_horas_formatada"] = formatar_horas_minutos(grupo["total_horas"])

    context = {
        "inicio": inicio_str,
        "fim": fim_str,
        "semana": semana,
        "semana_filtro_label": _format_week_label(semana_inicio),
        "impacto": impacto,
        "impacto_choices": CategoriaLaboratorio.IMPACTO_CHOICES,
        "total": total,
        "abertas": abertas,
        "encerradas": encerradas,
        "taxa_encerramento": taxa_encerramento,
        "media_duracao": OcorrenciaLaboratorio.formatar_duracao(media_duracao),
        "total_absenteismo_horas": total_absenteismo_horas,
        "perdas_por_unidade": perdas_por_unidade,
        "por_categoria": por_categoria,
        "por_assunto": por_assunto,  # Mantido vazio para compatibilidade do template
        "por_periodo": por_periodo,
        "resumo_executivo": resumo_executivo,
        "ocorrencias_recentes_por_categoria": ocorrencias_recentes_por_categoria,
        "chart_periodo_labels": json.dumps([item["periodo"] for item in por_periodo]),
        "chart_periodo_values": json.dumps([item["total"] for item in por_periodo]),
    }
    return context


@login_required
def dashboard_laboratorio(request):
    context = _build_dashboard_context(request)
    return render(request, "laboratorio/dashboard_laboratorio.html", context)


@login_required
def dashboard_laboratorio_pdf(request):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    context = _build_dashboard_context(request)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=24,
        title="Dashboard gerencial do laboratorio",
    )

    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    subtitle_style = styles["Heading3"]
    label_style = ParagraphStyle(
        "LabelStyle",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#4B5563"),
    )
    small_style = ParagraphStyle(
        "SmallStyle",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
    )

    periodo_exibicao = f"{context['inicio']} a {context['fim']}"
    if context.get("semana_filtro_label"):
        periodo_exibicao = context["semana_filtro_label"]

    impacto_filtro = "Todos"
    if context.get("impacto"):
        impacto_filtro = dict(CategoriaLaboratorio.IMPACTO_CHOICES).get(context["impacto"], context["impacto"])

    story = [
        Paragraph("Relatorio Gerencial - Dashboard Laboratorio", title_style),
        Paragraph(
            f"Gerado em: {timezone.localtime().strftime('%d/%m/%Y %H:%M')} | Periodo: {periodo_exibicao} | Impacto: {impacto_filtro}",
            label_style,
        ),
        Spacer(1, 10),
        Paragraph("Indicadores principais", subtitle_style),
        Spacer(1, 6),
    ]

    indicadores_data = [
        ["Total", "Abertas", "Encerradas", "Taxa encerramento", "Duracao media", "Absenteismo (h)"],
        [
            str(context["total"]),
            str(context["abertas"]),
            str(context["encerradas"]),
            f"{context['taxa_encerramento']:.1f}%",
            context["media_duracao"],
            f"{context['total_absenteismo_horas']:.2f}",
        ],
    ]
    indicadores_table = Table(indicadores_data, colWidths=[95, 95, 95, 130, 130, 130])
    indicadores_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
            ]
        )
    )
    story.append(indicadores_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("Resumo executivo", subtitle_style))
    for linha in context["resumo_executivo"]:
        story.append(Paragraph(f"- {linha}", small_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Categorias mais recorrentes", subtitle_style))
    categorias_data = [["Categoria", "Total"]]
    categorias_data.extend([[item["nome"], str(item["total"])] for item in context["por_categoria"]])
    if len(categorias_data) == 1:
        categorias_data.append(["Sem dados", "0"])
    categorias_table = Table(categorias_data, colWidths=[560, 120])
    categorias_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(categorias_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("Ocorrencias recentes por categoria", subtitle_style))
    if not context["ocorrencias_recentes_por_categoria"]:
        story.append(Paragraph("Sem ocorrencias para o recorte selecionado.", label_style))
    else:
        for grupo in context["ocorrencias_recentes_por_categoria"]:
            story.append(Spacer(1, 4))
            story.append(Paragraph(f"Categoria: {grupo['categoria']} ({grupo['total']} registros)", label_style))

            ocorrencias_data = [["Informacao", "Detalhamento", "Abertura", "Duracao", "Impacto"]]
            for item in grupo["ocorrencias"]:
                ocorrencia = item["obj"]
                ocorrencias_data.append(
                    [
                        Paragraph(item["contexto_personalizado"], small_style),
                        Paragraph((ocorrencia.detalhamento or "-")[:220], small_style),
                        ocorrencia.data_abertura.strftime("%d/%m/%Y %H:%M"),
                        ocorrencia.duracao_formatada,
                        ocorrencia.get_impacto_display(),
                    ]
                )

            ocorrencias_table = Table(ocorrencias_data, colWidths=[160, 330, 90, 70, 70])
            ocorrencias_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F9FAFB")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#E5E7EB")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            story.append(ocorrencias_table)

    doc.build(story)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/pdf")
    data_arquivo = timezone.localdate().strftime("%Y%m%d")
    response["Content-Disposition"] = (
        f'attachment; filename="dashboard_laboratorio_{data_arquivo}.pdf"'
    )
    return response


@login_required
def tratamento_list(request):
    tratamentos = TratamentoAntiReflexo.objects.all()
    return render(
        request,
        "laboratorio/tratamento_list.html",
        {"tratamentos": tratamentos},
    )


@login_required
def tratamento_create(request):
    if request.method == "POST":
        form = TratamentoAntiReflexoForm(request.POST)
        if form.is_valid():
            tratamento = form.save()
            messages.success(request, f"Tratamento '{tratamento.nome}' criado com sucesso.")
            return redirect("laboratorio:tratamento_list")
    else:
        form = TratamentoAntiReflexoForm()

    return render(
        request,
        "laboratorio/tratamento_form.html",
        {"form": form, "titulo": "Novo Tratamento Antirreflexo", "acao": "Salvar tratamento"},
    )


@login_required
def tratamento_update(request, pk):
    tratamento = get_object_or_404(TratamentoAntiReflexo, pk=pk)
    if request.method == "POST":
        form = TratamentoAntiReflexoForm(request.POST, instance=tratamento)
        if form.is_valid():
            tratamento = form.save()
            messages.success(request, f"Tratamento '{tratamento.nome}' atualizado com sucesso.")
            return redirect("laboratorio:tratamento_list")
    else:
        form = TratamentoAntiReflexoForm(instance=tratamento)

    return render(
        request,
        "laboratorio/tratamento_form.html",
        {"form": form, "titulo": "Editar Tratamento Antirreflexo", "acao": "Salvar alterações", "tratamento": tratamento},
    )


@login_required
def coating_painel(request):
    hoje = timezone.localdate()
    
    # Process form submission
    if request.method == "POST":
        if "btn_salvar_registro" in request.POST:
            registro_form = NovoLoteCoatingForm(request.POST)
            if registro_form.is_valid():
                cleaned_data = registro_form.cleaned_data
                
                # Descobrir a regra de turno baseado na hora_entrada
                hora_entrada = cleaned_data['hora_entrada']
                regras = RegraTurnoCoating.objects.filter(ativo=True)
                
                regra_encontrada = None
                for regra in regras:
                    # Lógica simples de verificação se a hora está entre inicio e fim
                    # Pode precisar de ajustes se o turno virar a meia noite
                    if regra.hora_inicio <= regra.hora_fim:
                        if regra.hora_inicio <= hora_entrada <= regra.hora_fim:
                            regra_encontrada = regra
                            break
                    else:
                        # Turno vira a meia noite (ex: 22:00 as 06:00)
                        if hora_entrada >= regra.hora_inicio or hora_entrada <= regra.hora_fim:
                            regra_encontrada = regra
                            break
                            
                if regra_encontrada:
                    data_escolhida = cleaned_data.get('data_registro', hoje)
                    # Pega ou cria o Turno Diário para a data e regra
                    turno_diario, created = TurnoCoating.objects.get_or_create(
                        data=data_escolhida,
                        regra=regra_encontrada
                    )
                    
                    lado_alvo = cleaned_data.get('lado_entrada', 'CC')
                    
                    # Salva CC e CX casados
                    RegistroCoating.objects.create(
                        turno_coating=turno_diario,
                        maquina=cleaned_data['maquina'],
                        lote=cleaned_data['lote'],
                        tratamento=cleaned_data['tratamento'],
                        hora_entrada=hora_entrada if lado_alvo == 'CC' else None,
                        lado='CC'
                    )
                    RegistroCoating.objects.create(
                        turno_coating=turno_diario,
                        maquina=cleaned_data['maquina'],
                        lote=cleaned_data['lote'],
                        tratamento=cleaned_data['tratamento'],
                        hora_entrada=hora_entrada if lado_alvo == 'CX' else None,
                        lado='CX'
                    )
                    
                    messages.success(request, "Lote adicionado com sucesso para CC e CX. Turno detectado automaticamente.")
                    return redirect("laboratorio:coating_painel")
                else:
                    messages.error(request, "Nenhum turno ativo encontrado para o horário de entrada informado.")
            else:
                messages.error(request, "Erro ao adicionar registro. Verifique os dados inseridos.")
    
    # Initialize form for GET
    registro_form = NovoLoteCoatingForm()
    
    # Fetch today's records
    registros = RegistroCoating.objects.filter(turno_coating__data=hoje).select_related(
        'turno_coating', 'maquina', 'tratamento', 'preparacao', 'montagem'
    ).order_by('-hora_entrada', '-id')
    
    # Identify machines (Evaporadoras)
    evaporadoras = Maquina.objects.filter(
        Q(categoria__nome__icontains='evaporadora') | 
        Q(nome__icontains='evaporadora')
    ).distinct().order_by("codigo", "fabricante")
    
    if not evaporadoras.exists():
        # Fallback to all lab machines if category isn't set
        evaporadoras = Maquina.objects.filter(setor__nome__icontains='laboratorio').order_by("codigo", "fabricante")
        if not evaporadoras.exists():
            evaporadoras = Maquina.objects.all().order_by("codigo", "fabricante")

    # Update form queryset to only show these machines
    registro_form.fields["maquina"].queryset = evaporadoras
    
    # Configuração de Ciclos (Limpeza e Troca)
    alertas_limpeza = []
    alertas_troca = []
    contagem_limpeza = {}
    contagem_troca = {}

    for maquina in evaporadoras:
        ciclo, _ = CicloManutencaoCoating.objects.get_or_create(maquina=maquina)
        
        # Limpeza
        ultima_limpeza = RegistroCoating.objects.filter(maquina=maquina, limpeza=True).order_by('-id').first()
        if ultima_limpeza:
            qtd_limpeza = RegistroCoating.objects.filter(maquina=maquina, id__gt=ultima_limpeza.id).count()
        else:
            qtd_limpeza = RegistroCoating.objects.filter(maquina=maquina).count()
        contagem_limpeza[maquina.id] = f"{qtd_limpeza}/{ciclo.limite_limpeza}"
        if qtd_limpeza >= ciclo.limite_limpeza:
            alertas_limpeza.append(maquina)
            
        # Troca
        ultima_troca = RegistroCoating.objects.filter(maquina=maquina, troca=True).order_by('-id').first()
        if ultima_troca:
            qtd_troca = RegistroCoating.objects.filter(maquina=maquina, id__gt=ultima_troca.id).count()
        else:
            qtd_troca = RegistroCoating.objects.filter(maquina=maquina).count()
        contagem_troca[maquina.id] = f"{qtd_troca}/{ciclo.limite_troca}"
        if qtd_troca >= ciclo.limite_troca:
            alertas_troca.append(maquina)

    # Cálculo dos tempos Rodando e Parado
    # Como `registros` está ordenado de forma decrescente (mais recente primeiro), 
    # o lote "anterior" chronologicamente é o próximo item da lista para a mesma máquina.
    last_seen = {}
    for reg in reversed(registros): # Iterar do mais antigo para o mais novo
        maq_id = reg.maquina_id
        
        # Tempo Rodando
        if reg.hora_entrada and reg.hora_saida:
            td = datetime.combine(date.min, reg.hora_saida) - datetime.combine(date.min, reg.hora_entrada)
            reg.tempo_rodando = (datetime.min + td).time()
        else:
            reg.tempo_rodando = None
            
        # Tempo Parado
        if maq_id in last_seen and reg.hora_entrada and last_seen[maq_id]:
            # Entrada atual - Saída anterior
            td_parado = datetime.combine(date.min, reg.hora_entrada) - datetime.combine(date.min, last_seen[maq_id])
            # Se for negativo (ex: virada de dia), ignora ou ajusta
            if td_parado.total_seconds() >= 0:
                reg.tempo_parado = (datetime.min + td_parado).time()
            else:
                reg.tempo_parado = None
        else:
            reg.tempo_parado = None
            
        last_seen[maq_id] = reg.hora_saida

    maquinas_com_registros = set(r.maquina_id for r in registros)

    context = {
        "registros": registros,
        "maquinas_com_registros": maquinas_com_registros,
        "registro_form": registro_form,
        "alertas_limpeza": alertas_limpeza,
        "alertas_troca": alertas_troca,
        "contagem_limpeza": contagem_limpeza,
        "contagem_troca": contagem_troca,
        "evaporadoras": evaporadoras,
    }
    
    return render(request, "laboratorio/coating_painel.html", context)

@login_required
@require_POST
def registro_coating_delete(request, pk):
    registro = get_object_or_404(RegistroCoating, pk=pk)
    # Could check permissions here if needed
    registro.delete()
    messages.success(request, f"Registro de Lote {registro.lote} (Lado {registro.lado}) excluído com sucesso.")
    return redirect("laboratorio:coating_painel")

@login_required
@require_POST
def atualizar_celula_coating(request):
    try:
        data = json.loads(request.body)
        registro_id = data.get('id')
        campo = data.get('campo')
        valor = data.get('valor')
        
        registro = get_object_or_404(RegistroCoating, pk=registro_id)
        
        if campo in ['limpeza', 'troca']:
            setattr(registro, campo, valor.lower() == 'true')
        elif campo in ['preparacao_id', 'montagem_id']:
            if not valor:
                setattr(registro, campo, None)
            else:
                setattr(registro, campo, int(valor))
        elif campo in ['hora_entrada', 'hora_saida']:
            if not valor:
                setattr(registro, campo, None)
            else:
                from datetime import datetime
                setattr(registro, campo, datetime.strptime(valor, "%H:%M").time())
        else:
            return JsonResponse({'success': False, 'error': 'Campo não permitido para edição rápida.'}, status=400)
            
        registro.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def regra_turno_list(request):
    regras = RegraTurnoCoating.objects.all()
    return render(request, "laboratorio/regra_turno_list.html", {"regras": regras})


@login_required
def regra_turno_create(request):
    if request.method == "POST":
        form = RegraTurnoCoatingForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Regra de turno criada com sucesso.")
            return redirect("laboratorio:regra_turno_list")
    else:
        form = RegraTurnoCoatingForm()
    
    return render(
        request, 
        "laboratorio/regra_turno_form.html", 
        {"form": form, "titulo": "Nova Regra de Turno", "acao": "Salvar regra"}
    )


@login_required
def regra_turno_update(request, pk):
    regra = get_object_or_404(RegraTurnoCoating, pk=pk)
    if request.method == "POST":
        form = RegraTurnoCoatingForm(request.POST, instance=regra)
        if form.is_valid():
            form.save()
            messages.success(request, "Regra de turno atualizada com sucesso.")
            return redirect("laboratorio:regra_turno_list")
    else:
        form = RegraTurnoCoatingForm(instance=regra)
        
    return render(
        request, 
        "laboratorio/regra_turno_form.html", 
        {"form": form, "titulo": "Editar Regra de Turno", "acao": "Salvar alterações"}
    )
