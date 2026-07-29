import json
import io
from collections import Counter
from datetime import date, datetime, timedelta, time
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django.db.models import Count, Q, Max
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.http import JsonResponse
import json
from collections import defaultdict

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
    EquipeCoatingForm,
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
    CicloManutencaoCoating,
    ManutencaoRealizadaCoating,
    EquipeCoating,
    ItemChecklistCiclo,
    RespostaChecklistManutencao,
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
    from django.core.paginator import Paginator
    
    # Process form submission
    if request.method == "POST":
        if "btn_salvar_registro" in request.POST:
            registro_form = NovoLoteCoatingForm(request.POST)
            if registro_form.is_valid():
                cleaned_data = registro_form.cleaned_data
                
                # Descobrir a regra de turno baseado na hora_entrada
                hora_entrada = cleaned_data['hora_entrada']
                hora_time = hora_entrada.time() if hora_entrada else None
                regras = RegraTurnoCoating.objects.filter(ativo=True)
                
                regra_encontrada = None
                if hora_time:
                    for regra in regras:
                        # Lógica simples de verificação se a hora está entre inicio e fim
                        # Pode precisar de ajustes se o turno virar a meia noite
                        if regra.hora_inicio <= regra.hora_fim:
                            if regra.hora_inicio <= hora_time <= regra.hora_fim:
                                regra_encontrada = regra
                                break
                        else:
                            # Turno vira a meia noite (ex: 22:00 as 06:00)
                            if hora_time >= regra.hora_inicio or hora_time <= regra.hora_fim:
                                regra_encontrada = regra
                                break
                            
                if regra_encontrada:
                    data_escolhida = hora_entrada.date() if hora_entrada else timezone.localdate()
                    # Pega ou cria o Turno Diário para a data e regra
                    turno_diario, created = TurnoCoating.objects.get_or_create(
                        data=data_escolhida,
                        regra=regra_encontrada
                    )
                    
                    lado_alvo = cleaned_data.get('lado_entrada', 'CC')
                    
                    # Verifica se o lote já existe para a máquina e turno
                    lote_existente = RegistroCoating.objects.filter(
                        turno_coating=turno_diario,
                        maquina=cleaned_data['maquina'],
                        lote=cleaned_data['lote']
                    ).exists()
                    
                    if lote_existente:
                        messages.error(request, f"O lote {cleaned_data['lote']} já está registrado para esta máquina no {turno_diario}.")
                        return redirect("laboratorio:coating_painel")
                    
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
    
    # Fetch all records
    todos_registros = RegistroCoating.objects.all().select_related(
        'turno_coating', 'maquina', 'tratamento', 'preparacao', 'montagem'
    ).order_by('-turno_coating__data', '-lote', 'lado')
    
    paginator = Paginator(todos_registros, 10)
    page_number = request.GET.get('page')
    registros = paginator.get_page(page_number)
    
    current_lote = None
    group_idx = 0
    for reg in registros:
        if current_lote is None:
            current_lote = reg.lote
        elif reg.lote != current_lote:
            current_lote = reg.lote
            group_idx = 1 - group_idx
        reg.bg_group = group_idx
    
    # Identify machines (Evaporadoras)
    evaporadoras = Maquina.objects.filter(
        Q(categoria__nome__icontains='evaporadora') | 
        Q(nome__icontains='evaporadora')
    ).distinct().order_by("codigo", "fabricante")
    
    if not evaporadoras.exists():
        # Fallback to all lab machines if category isn't set
        evaporadoras = Maquina.objects.all().order_by("codigo", "fabricante")

    # Update form queryset to only show these machines
    registro_form.fields["maquina"].queryset = evaporadoras
    # Configuração de Ciclos de Manutenção
    alertas_ciclos = {}
    status_maquinas = {}

    for maquina in evaporadoras:
        ciclos = list(maquina.ciclos_coating.all())
        status_maquinas[maquina.id] = []
        maquina.em_alerta = False
        
        # Busca todo o historico de lotes da maquina para simular os contadores
        lotes_historico = list(RegistroCoating.objects.filter(maquina=maquina).order_by('turno_coating__data', 'lote', 'id').values('id', 'lote', 'turno_coating__data', 'tratamento_id'))
        
        manutencoes = list(ManutencaoRealizadaCoating.objects.filter(registro__maquina=maquina).annotate(
            total_itens=Count('ciclo__itens_checklist'),
            itens_feitos=Count('respostas_checklist', filter=Q(respostas_checklist__feito=True))
        ).values('registro_id', 'ciclo_id', 'total_itens', 'itens_feitos', 'ciclo__tipo', 'valor_aferido', 'ciclo__valor_minimo', 'ciclo__valor_maximo'))
        
        manut_map = {}
        for m in manutencoes:
            if m['ciclo__tipo'] == 'VERIFICACAO':
                valor = m['valor_aferido']
                vmin = m['ciclo__valor_minimo']
                vmax = m['ciclo__valor_maximo']
                status_m = 'OK'
                if valor is not None:
                    if vmin is not None and valor < vmin:
                        status_m = 'NOK'
                    if vmax is not None and valor > vmax:
                        status_m = 'NOK'
                else:
                    # Se não informaram o valor, mas deveriam
                    if vmin is not None or vmax is not None:
                        status_m = 'NOK'
            else:
                status_m = 'PARCIAL' if m['total_itens'] > 0 and m['itens_feitos'] < m['total_itens'] else 'OK'
            
            manut_map.setdefault(m['registro_id'], []).append((m['ciclo_id'], status_m))
            
        lotes_agrupados = defaultdict(lambda: {'rids': [], 'tratamentos': set()})
        for reg_dict in lotes_historico:
            lote_key = (reg_dict['turno_coating__data'], reg_dict['lote'])
            lotes_agrupados[lote_key]['rids'].append(reg_dict['id'])
            if reg_dict['tratamento_id']:
                lotes_agrupados[lote_key]['tratamentos'].add(reg_dict['tratamento_id'])
            
        counters = {c.id: 0 for c in ciclos}
        never_done = {c.id: True for c in ciclos}
        last_period = {c.id: None for c in ciclos}
        registro_status = {}
        
        # Pre-fetch tratamentos_especificos for cycles
        ciclos_tratamentos_map = {c.id: set(c.tratamentos_especificos.values_list('id', flat=True)) for c in ciclos}
        
        for lote_key, lote_data in lotes_agrupados.items():
            data_lote = lote_key[0]
            rids = lote_data['rids']
            tratamentos_lote = lote_data['tratamentos']
            
            for cid, c_trats in ciclos_tratamentos_map.items():
                if not c_trats or c_trats.intersection(tratamentos_lote):
                    counters[cid] += 1
                
            m_cids_lote = {}
            for rid in rids:
                for cid, m_status in manut_map.get(rid, []):
                    m_cids_lote[cid] = m_status
                
            ciclos_status_lote = {}
            for c in ciclos:
                # Determinar período atual baseado na data do lote
                if c.criterio == 'DIARIO':
                    curr_period = f"{data_lote.year}-{data_lote.month:02d}-{data_lote.day:02d}"
                elif c.criterio == 'SEMANAL':
                    curr_period = f"{data_lote.isocalendar()[0]}-W{data_lote.isocalendar()[1]}"
                elif c.criterio == 'QUINZENAL':
                    curr_period = f"{data_lote.year}-{data_lote.month:02d}-Q{1 if data_lote.day <= 15 else 2}"
                elif c.criterio == 'MENSAL':
                    curr_period = f"{data_lote.year}-{data_lote.month:02d}"
                else:
                    curr_period = None

                estourou = False
                if c.id in m_cids_lote:
                    status = m_cids_lote[c.id] # OK or PARCIAL
                    counters[c.id] = 0
                    never_done[c.id] = False
                    last_period[c.id] = curr_period
                else:
                    if c.criterio in ['LOTES', 'DIAS']:
                        if never_done[c.id] or counters[c.id] >= c.limite_lotes:
                            status = 'PENDENTE'
                            estourou = True
                        else:
                            status = 'S_FAROL'
                    elif c.criterio == 'LIVRE':
                        status = 'S_FAROL'
                    else: # Criterio Calendário
                        if last_period[c.id] == curr_period:
                            status = 'S_FAROL'
                        else:
                            status = 'PENDENTE'
                            estourou = True
                            
                ciclos_status_lote[c.id] = {
                    'status': status,
                    'estourou': estourou,
                    'lotes_passados': counters[c.id]
                }
                
            for rid in rids:
                registro_status[rid] = ciclos_status_lote
                
        # Anexa o status calculado a cada registro renderizado na pagina
        import json
        for reg in registros:
            if reg.maquina_id == maquina.id:
                rs = registro_status.get(reg.id, {})
                status_list = []
                ok_cids = []
                ciclos_json_data = []
                
                for c in ciclos:
                    c_status_info = rs.get(c.id, {'status': 'S_FAROL', 'estourou': False, 'lotes_passados': 0})
                    
                    # Tratar caso o dict base não tenha as novas chaves
                    if isinstance(c_status_info, str):
                        c_status_info = {'status': c_status_info, 'estourou': False, 'lotes_passados': 0}
                        
                    status = c_status_info['status']
                    
                    status_list.append({
                        'ciclo': c,
                        'status': status
                    })
                    if status == 'OK':
                        ok_cids.append(c.id)
                        
                    # Prepare JSON for modal
                    itens_list = [{'id': it.id, 'ordem': it.ordem, 'texto': it.texto} for it in c.itens_checklist.all()]
                    ciclos_json_data.append({
                        'ciclo': {
                            'id': c.id,
                            'nome': c.nome,
                            'tipo': c.tipo,
                            'criterio': c.criterio,
                            'itens': itens_list
                        },
                        'estourou': c_status_info['estourou'],
                        'lotes_passados': c_status_info.get('lotes_passados', 0),
                        'limite': c.limite_lotes
                    })
                    
                reg.ciclos_status_list = status_list
                reg.ok_cids = ok_cids
                
                # Escape quotes properly so it can be safely used in HTML templates
                reg.ciclos_status_json_lote = json.dumps(ciclos_json_data).replace("'", "\\'").replace('"', '&quot;')
                
                reg.limpezas_ok = sum(1 for s in status_list if s['ciclo'].tipo == 'LIMPEZA' and s['status'] == 'OK')
                reg.limpezas_pendentes = sum(1 for s in status_list if s['ciclo'].tipo == 'LIMPEZA' and s['status'] in ['PENDENTE', 'PARCIAL', 'NOK'])
                reg.trocas_ok = sum(1 for s in status_list if s['ciclo'].tipo == 'TROCA' and s['status'] == 'OK')
                reg.trocas_pendentes = sum(1 for s in status_list if s['ciclo'].tipo == 'TROCA' and s['status'] in ['PENDENTE', 'PARCIAL', 'NOK'])
                reg.verificacoes_ok = sum(1 for s in status_list if s['ciclo'].tipo == 'VERIFICACAO' and s['status'] == 'OK')
                reg.verificacoes_pendentes = sum(1 for s in status_list if s['ciclo'].tipo == 'VERIFICACAO' and s['status'] in ['PENDENTE', 'PARCIAL', 'NOK'])
        
        # Prepara o status global atual da maquina
        hoje = timezone.now().date()
        for ciclo in ciclos:
            count = counters.get(ciclo.id, 0)
            itens = list(ciclo.itens_checklist.all().values('id', 'texto', 'ordem'))
            
            if ciclo.criterio in ['LOTES', 'DIAS']:
                estourou_agora = never_done[ciclo.id] or count >= ciclo.limite_lotes
                estourou_proximo = count == (ciclo.limite_lotes - 1)
                lotes_passados = count
            elif ciclo.criterio == 'LIVRE':
                estourou_agora = False
                estourou_proximo = False
                lotes_passados = 0
            else:
                if ciclo.criterio == 'DIARIO':
                    curr_period = f"{hoje.year}-{hoje.month:02d}-{hoje.day:02d}"
                elif ciclo.criterio == 'SEMANAL':
                    curr_period = f"{hoje.isocalendar()[0]}-W{hoje.isocalendar()[1]}"
                elif ciclo.criterio == 'QUINZENAL':
                    curr_period = f"{hoje.year}-{hoje.month:02d}-Q{1 if hoje.day <= 15 else 2}"
                elif ciclo.criterio == 'MENSAL':
                    curr_period = f"{hoje.year}-{hoje.month:02d}"
                else:
                    curr_period = None
                    
                estourou_agora = last_period[ciclo.id] != curr_period
                estourou_proximo = False
                lotes_passados = 0

            status_maquinas[maquina.id].append({
                "ciclo": {
                    "id": ciclo.id,
                    "nome": ciclo.nome,
                    "tipo": ciclo.tipo,
                    "criterio": ciclo.criterio,
                    "itens": itens
                },
                "count": count,
                "lotes_passados": lotes_passados,
                "limite": ciclo.limite_lotes,
                "estourou": estourou_agora
            })
            
            if estourou_agora or estourou_proximo:
                maquina.em_alerta = True
                if maquina.id not in alertas_ciclos:
                    alertas_ciclos[maquina.id] = {
                        "maquina": maquina,
                        "alertas": []
                    }
                alertas_ciclos[maquina.id]["alertas"].append({
                    "ciclo": ciclo,
                    "lotes_passados": lotes_passados,
                    "ultimo_lote": lotes_historico[-1]['lote'] if lotes_historico else "N/A",
                    "data": lotes_historico[-1]['turno_coating__data'] if lotes_historico else None,
                    "estourou_agora": estourou_agora,
                    "nunca_feito": never_done[ciclo.id]
                })

    # Cálculo dos tempos Rodando e Parado
    # Como `registros` está ordenado de forma decrescente (mais recente primeiro), 
    # o lote "anterior" chronologicamente é o próximo item da lista para a mesma máquina.
    last_seen = {}
    for reg in reversed(registros): # Iterar do mais antigo para o mais novo
        maq_id = reg.maquina_id
        
        # Trata legados onde SQLite ainda pode retornar tipo 'time'
        hora_entrada_dt = reg.hora_entrada
        hora_saida_dt = reg.hora_saida
        
        # Garante que lidamos com naive datetime no cálculo local
        if hora_entrada_dt and timezone.is_aware(hora_entrada_dt):
            hora_entrada_dt = timezone.localtime(hora_entrada_dt).replace(tzinfo=None)
        if hora_saida_dt and timezone.is_aware(hora_saida_dt):
            hora_saida_dt = timezone.localtime(hora_saida_dt).replace(tzinfo=None)
            
        if isinstance(hora_entrada_dt, time):
            hora_entrada_dt = datetime.combine(reg.turno_coating.data, hora_entrada_dt)
        if isinstance(hora_saida_dt, time):
            hora_saida_dt = datetime.combine(reg.turno_coating.data, hora_saida_dt)
            
        # Tempo Rodando
        if hora_entrada_dt and hora_saida_dt:
            td = hora_saida_dt - hora_entrada_dt
            seconds = int(td.total_seconds()) % 86400
            reg.tempo_rodando = (datetime.min + timedelta(seconds=seconds)).time()
        else:
            reg.tempo_rodando = None
            
        # Tempo Parado
        if hora_entrada_dt:
            hora_inicio_turno = None
            if reg.turno_coating and reg.turno_coating.regra and reg.turno_coating.regra.hora_inicio:
                inicio_time = reg.turno_coating.regra.hora_inicio
                hora_inicio_turno = datetime.combine(reg.turno_coating.data, inicio_time)
                
            if maq_id in last_seen and last_seen[maq_id]:
                saida_anterior = last_seen[maq_id]
                if isinstance(saida_anterior, time):
                    saida_anterior = datetime.combine(reg.turno_coating.data, saida_anterior)
                    
                # Se a saída anterior ocorreu antes do início do turno atual, o tempo parado conta só do início do turno
                if hora_inicio_turno and saida_anterior < hora_inicio_turno:
                    if hora_entrada_dt > hora_inicio_turno:
                        td_parado = hora_entrada_dt - hora_inicio_turno
                    else:
                        td_parado = timedelta(0)
                else:
                    td_parado = hora_entrada_dt - saida_anterior
                
                # Previne negativo se entrada atual < saída anterior (erro de preenchimento)
                seconds = int(td_parado.total_seconds())
                if seconds < 0:
                    seconds = 0
                else:
                    seconds = seconds % 86400
                reg.tempo_parado = (datetime.min + timedelta(seconds=seconds)).time()
            else:
                # Primeiro lote da máquina (no contexto visível).
                if hora_inicio_turno and hora_entrada_dt > hora_inicio_turno:
                    td_parado = hora_entrada_dt - hora_inicio_turno
                    seconds = int(td_parado.total_seconds())
                    if seconds < 0:
                        seconds = 0
                    else:
                        seconds = seconds % 86400
                    reg.tempo_parado = (datetime.min + timedelta(seconds=seconds)).time()
                else:
                    reg.tempo_parado = None
        else:
            reg.tempo_parado = None
            
        last_seen[maq_id] = hora_saida_dt

    maquinas_com_registros = set(r.maquina_id for r in registros)

    max_lote = RegistroCoating.objects.aggregate(max_lote=Max('lote'))['max_lote']
    proximo_lote = (max_lote or 0) + 1

    proximos_lotes_map = {}
    for maq in evaporadoras:
        max_maq = RegistroCoating.objects.filter(maquina=maq).aggregate(max_lote=Max('lote'))['max_lote']
        proximos_lotes_map[maq.id] = (max_maq or 0) + 1

    context = {
        "registros": registros,
        "maquinas_com_registros": maquinas_com_registros,
        "registro_form": registro_form,
        "alertas_ciclos": alertas_ciclos,
        "status_maquinas": status_maquinas,
        "evaporadoras": evaporadoras,
        "proximo_lote": proximo_lote,
        "proximos_lotes_map_json": json.dumps(proximos_lotes_map),
        "equipe": EquipeCoating.objects.select_related('colaborador').all().order_by('colaborador__nome_completo'),
    }
    
    return render(request, "laboratorio/coating_painel.html", context)

@login_required
@require_POST
def registro_coating_delete(request, pk):
    try:
        registro = RegistroCoating.objects.get(pk=pk)
    except RegistroCoating.DoesNotExist:
        messages.warning(request, "Este lote já foi excluído anteriormente.")
        return redirect("laboratorio:coating_painel")
        
    # Validação TOTP para operadores sem privilégio
    if not (request.user.is_staff or request.user.is_superuser):
        autorizador_username = request.POST.get('autorizador_username', '').strip()
        
        if not autorizador_username:
            messages.error(request, "Autorização negada: Credenciais do supervisor não fornecidas.")
            return redirect("laboratorio:coating_painel")
            
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        autorizador = User.objects.filter(username__iexact=autorizador_username, is_active=True).first()
        if not autorizador or not (autorizador.is_staff or autorizador.is_superuser):
            messages.error(request, "Autorização negada: O usuário informado não tem privilégios de supervisor.")
            return redirect("laboratorio:coating_painel")
            
        is_isento = autorizador.groups.filter(name='Isentos 2FA').exists()
        
        if not is_isento:
            autorizador_totp = request.POST.get('autorizador_totp', '').strip()
            if not autorizador_totp:
                messages.error(request, "Autorização negada: Código do autenticador não fornecido.")
                return redirect("laboratorio:coating_painel")
                
            from django_otp.plugins.otp_totp.models import TOTPDevice
            devices = TOTPDevice.objects.filter(user=autorizador, confirmed=True)
            if not devices.exists():
                messages.error(request, "Autorização negada: O supervisor informado não possui autenticador configurado.")
                return redirect("laboratorio:coating_painel")
                
            is_valid = False
            if autorizador_totp.isdigit() and len(autorizador_totp) == 6:
                token_int = int(autorizador_totp)
                for device in devices:
                    try:
                        if device.verify_token(token_int):
                            is_valid = True
                            break
                    except Exception:
                        continue
                        
            if not is_valid:
                messages.error(request, "Autorização negada: Código do autenticador inválido.")
                return redirect("laboratorio:coating_painel")
    
    lote_num = registro.lote
    
    registros_do_lote = RegistroCoating.objects.filter(
        lote=registro.lote,
        maquina=registro.maquina,
        turno_coating=registro.turno_coating
    )
    qtd = registros_do_lote.count()
    registros_do_lote.delete()
    
    messages.success(request, f"Lote {lote_num} excluído com sucesso ({qtd} registros removidos).")
    return redirect("laboratorio:coating_painel")

@login_required
@require_POST
def api_editar_linha_coating(request):
    import json
    try:
        data = json.loads(request.body)
        registro_id = data.get('id')
        registro = get_object_or_404(RegistroCoating, pk=registro_id)
        
        if 'lote' in data or 'maquina_id' in data or 'tratamento_id' in data:
            registros = RegistroCoating.objects.filter(
                lote=registro.lote,
                maquina=registro.maquina,
                turno_coating=registro.turno_coating
            )
            update_data = {}
            if 'lote' in data: update_data['lote'] = data['lote']
            if 'maquina_id' in data: update_data['maquina_id'] = data['maquina_id']
            if 'tratamento_id' in data: update_data['tratamento_id'] = data['tratamento_id']
            registros.update(**update_data)
            registro.refresh_from_db()
            
        if 'hora_entrada' in data:
            val = data['hora_entrada']
            registro.hora_entrada = val if val else None
        if 'hora_saida' in data:
            val = data['hora_saida']
            registro.hora_saida = val if val else None
        if 'preparacao_id' in data:
            val = data['preparacao_id']
            registro.preparacao_id = val if val else None
        if 'montagem_id' in data:
            val = data['montagem_id']
            registro.montagem_id = val if val else None
        if 'observacao' in data:
            registro.observacao = data['observacao']
            
        registro.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def editar_lote_completo_coating(request):
    try:
        data = json.loads(request.body)
        registro_id = data.get('id')
        lote_novo = data.get('lote')
        maquina_id = data.get('maquina_id')
        tratamento_id = data.get('tratamento_id')
        
        registro = get_object_or_404(RegistroCoating, pk=registro_id)
        
        registros = RegistroCoating.objects.filter(
            lote=registro.lote,
            maquina=registro.maquina,
            turno_coating=registro.turno_coating
        )
        
        registros.update(
            lote=lote_novo,
            maquina_id=maquina_id,
            tratamento_id=tratamento_id
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

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
                from django.utils.dateparse import parse_datetime
                parsed = parse_datetime(valor)
                if not parsed:
                    return JsonResponse({'success': False, 'error': 'Formato de data inválido.'}, status=400)
                
                # Auto-ajuste de data se o usuário preencher apenas a hora e ela cruzar a meia-noite
                if campo == 'hora_saida' and registro.hora_entrada:
                    # Precisamos garantir que estamos comparando na mesma "base" (aware/naive)
                    parsed_compare = parsed
                    entrada_compare = registro.hora_entrada
                    from django.utils import timezone
                    if timezone.is_aware(parsed_compare) and timezone.is_naive(entrada_compare):
                        entrada_compare = timezone.make_aware(entrada_compare)
                    elif timezone.is_naive(parsed_compare) and timezone.is_aware(entrada_compare):
                        parsed_compare = timezone.make_aware(parsed_compare)
                        
                    if parsed_compare < entrada_compare:
                        parsed += timedelta(days=1)
                        
                setattr(registro, campo, parsed)
        else:
            return JsonResponse({'success': False, 'error': 'Campo não permitido para edição rápida.'}, status=400)
            
        registro.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
def equipe_coating_list(request):
    equipe = EquipeCoating.objects.all().order_by('colaborador__nome_completo')
    
    if request.method == "POST":
        form = EquipeCoatingForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Colaborador adicionado à Equipe de Coating.")
            return redirect("laboratorio:equipe_coating_list")
    else:
        form = EquipeCoatingForm()
        
    return render(request, "laboratorio/equipe_coating_list.html", {
        "equipe": equipe,
        "form": form
    })

@login_required
@require_POST
def equipe_coating_delete(request, pk):
    membro = get_object_or_404(EquipeCoating, pk=pk)
    membro.delete()
    messages.success(request, f"{membro.colaborador.nome_completo} removido da Equipe de Coating.")
    return redirect("laboratorio:equipe_coating_list")

@login_required
@require_POST
def equipe_coating_update(request, pk):
    membro = get_object_or_404(EquipeCoating, pk=pk)
    
    # Checkbox sends "on" if checked, otherwise it's not in POST
    pode_preparar = request.POST.get('pode_preparar') == 'on'
    pode_montar = request.POST.get('pode_montar') == 'on'
    
    membro.pode_preparar = pode_preparar
    membro.pode_montar = pode_montar
    membro.save()
    
    messages.success(request, f"Permissões de {membro.colaborador.nome_completo} atualizadas com sucesso.")
    return redirect("laboratorio:equipe_coating_list")

@login_required
def ciclo_coating_list(request):
    evaporadoras = Maquina.objects.filter(
        Q(categoria__nome__icontains='evaporadora') | 
        Q(nome__icontains='evaporadora')
    ).distinct().order_by("codigo", "fabricante")
    
    if not evaporadoras.exists():
        evaporadoras = Maquina.objects.filter(setor__nome__icontains='laboratorio', status=True).order_by("codigo", "fabricante")
        if not evaporadoras.exists():
            evaporadoras = Maquina.objects.filter(status=True).order_by("codigo", "fabricante")

    from .models import TratamentoAntiReflexo
    tratamentos = TratamentoAntiReflexo.objects.filter(ativo=True).order_by('nome')
    return render(request, "laboratorio/ciclo_coating_list.html", {
        "maquinas": evaporadoras,
        "tratamentos": tratamentos,
    })

@login_required
def api_obter_ciclos_maquina(request):
    try:
        maquina_id = request.GET.get('maquina_id')
        ciclos = list(CicloManutencaoCoating.objects.filter(maquina_id=maquina_id).values('id', 'tipo', 'nome').order_by('tipo', 'nome'))
        return JsonResponse({'success': True, 'ciclos': ciclos})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def api_reordenar_ciclos(request):
    import json
    try:
        data = json.loads(request.body)
        ciclos_ordem = data.get('ciclos', [])
        
        for index, ciclo_id in enumerate(ciclos_ordem):
            CicloManutencaoCoating.objects.filter(id=ciclo_id).update(ordem=index)
            
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def copiar_ciclos_coating(request):
    try:
        maquina_destino_id = request.POST.get('maquina_destino_id')
        ciclos_ids = request.POST.getlist('ciclos_ids')
        
        destino = get_object_or_404(Maquina, pk=maquina_destino_id)
        count = 0
        
        for cid in ciclos_ids:
            ciclo_orig = CicloManutencaoCoating.objects.get(pk=cid)
            itens_orig = list(ciclo_orig.itens_checklist.all())
            
            # Duplicar
            ciclo_orig.pk = None
            ciclo_orig.maquina = destino
            ciclo_orig.save()
            count += 1
            
            for item in itens_orig:
                item.pk = None
                item.ciclo = ciclo_orig
                item.save()
                
        messages.success(request, f"{count} manutenções copiadas para a máquina {destino.codigo}.")
    except Exception as e:
        messages.error(request, f"Erro ao copiar ciclos: {str(e)}")
        
    return redirect('laboratorio:ciclo_coating_list')

@login_required
@require_POST
def ciclo_coating_create(request):
    try:
        maquina_id = request.POST.get('maquina_id')
        tipo = request.POST.get('tipo')
        nome = request.POST.get('nome')
        criterio = request.POST.get('criterio', 'LOTES')
        limite_lotes = request.POST.get('limite_lotes')
        valor_minimo = request.POST.get('valor_minimo')
        valor_maximo = request.POST.get('valor_maximo')
        
        maquina = get_object_or_404(Maquina, pk=maquina_id)
        
        try:
            lim_val = int(limite_lotes) if limite_lotes else 1
        except (ValueError, TypeError):
            lim_val = 1
        
        ciclo = CicloManutencaoCoating.objects.create(
            maquina=maquina,
            tipo=tipo,
            nome=nome,
            criterio=criterio,
            limite_lotes=lim_val,
            valor_minimo=float(valor_minimo) if valor_minimo else None,
            valor_maximo=float(valor_maximo) if valor_maximo else None
        )
        
        tratamentos_ids = request.POST.getlist('tratamentos')
        if tratamentos_ids:
            ciclo.tratamentos_especificos.set(tratamentos_ids)
        
        messages.success(request, f"Ciclo '{nome}' adicionado para a máquina {maquina.codigo}.")
    except Exception as e:
        messages.error(request, f"Erro ao adicionar ciclo: {str(e)}")
        
    return redirect("laboratorio:ciclo_coating_list")

@login_required
@require_POST
def ciclo_coating_update(request, pk):
    ciclo = get_object_or_404(CicloManutencaoCoating, pk=pk)
    try:
        limite_lotes = request.POST.get('limite_lotes')
        try:
            lim_val = int(limite_lotes) if limite_lotes else ciclo.limite_lotes
        except (ValueError, TypeError):
            lim_val = ciclo.limite_lotes
            
        ciclo.tipo = request.POST.get('tipo', ciclo.tipo)
        ciclo.nome = request.POST.get('nome', ciclo.nome)
        ciclo.criterio = request.POST.get('criterio', ciclo.criterio)
        ciclo.limite_lotes = lim_val
        
        valor_minimo = request.POST.get('valor_minimo')
        valor_maximo = request.POST.get('valor_maximo')
        ciclo.valor_minimo = float(valor_minimo) if valor_minimo else None
        ciclo.valor_maximo = float(valor_maximo) if valor_maximo else None
        
        ciclo.save()
        tratamentos = request.POST.getlist('tratamentos')
        if tratamentos:
            ciclo.tratamentos_especificos.set(tratamentos)
        else:
            ciclo.tratamentos_especificos.clear()
        
        tratamentos_ids = request.POST.getlist('tratamentos')
        if tratamentos_ids:
            ciclo.tratamentos_especificos.set(tratamentos_ids)
        else:
            ciclo.tratamentos_especificos.clear()
            
        messages.success(request, f"Ciclo '{ciclo.nome}' atualizado com sucesso.")
    except Exception as e:
        messages.error(request, f"Erro ao atualizar ciclo: {str(e)}")
        
    return redirect("laboratorio:ciclo_coating_list")

@login_required
def configurar_checklist_ciclo(request, ciclo_id):
    ciclo = get_object_or_404(CicloManutencaoCoating, pk=ciclo_id)
    if request.method == "POST":
        action = request.POST.get('action')
        if action == 'add':
            texto = request.POST.get('texto')
            ordem = request.POST.get('ordem', '1')
            if texto:
                ItemChecklistCiclo.objects.create(
                    ciclo=ciclo,
                    texto=texto,
                    ordem=int(ordem) if ordem.isdigit() else 1
                )
                messages.success(request, "Item adicionado ao checklist.")
        elif action == 'delete':
            item_id = request.POST.get('item_id')
            ItemChecklistCiclo.objects.filter(id=item_id, ciclo=ciclo).delete()
            messages.success(request, "Item removido do checklist.")
        return redirect('laboratorio:configurar_checklist_ciclo', ciclo_id=ciclo.id)
        
    return render(request, "laboratorio/ciclo_checklist_config.html", {
        "ciclo": ciclo,
    })

@login_required
@require_POST
def ciclo_coating_delete(request, pk):
    try:
        ciclo = get_object_or_404(CicloManutencaoCoating, pk=pk)
        nome = ciclo.nome
        maq = ciclo.maquina.codigo
        ciclo.delete()
        messages.success(request, f"Ciclo '{nome}' removido da máquina {maq}.")
    except Exception as e:
        if type(e).__name__ == 'ProtectedError' or 'protected foreign keys' in str(e):
            messages.error(request, f"Não é possível excluir o ciclo '{nome}'. Ele já possui manutenções registradas no histórico de lotes e está protegido para fins de auditoria.")
        else:
            messages.error(request, f"Erro ao remover ciclo: {str(e)}")
        
    return redirect("laboratorio:ciclo_coating_list")


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

@login_required
@require_POST
def registrar_manutencao_coating(request):
    try:
        registro_id = request.POST.get('registro_id')
        ciclo_ids = request.POST.getlist('ciclos')
        observacao = request.POST.get('observacao', '').strip()
        
        registro = get_object_or_404(RegistroCoating, pk=registro_id)
        
        # Validação: Pelo menos um item do checklist deve ser marcado
        for cid in ciclo_ids:
            ciclo = get_object_or_404(CicloManutencaoCoating, pk=cid)
            itens_checklist = ciclo.itens_checklist.all()
            if itens_checklist.exists():
                algum_feito = any(request.POST.get(f'checklist_{ciclo.id}_{item.id}') == 'on' for item in itens_checklist)
                if not algum_feito:
                    messages.error(request, f"Para a manutenção '{ciclo.nome}', é obrigatório preencher pelo menos um item do checklist.")
                    url_redirecionamento = request.META.get('HTTP_REFERER', reverse('laboratorio:coating_painel'))
                    return redirect(url_redirecionamento)
        
        # Encontra ambos os lados (CC e CX) deste lote
        registros_do_lote = RegistroCoating.objects.filter(
            lote=registro.lote,
            maquina=registro.maquina,
            turno_coating=registro.turno_coating
        )
        
        ManutencaoRealizadaCoating.objects.filter(registro__in=registros_do_lote).delete()
        
        for reg in registros_do_lote:
            for cid in ciclo_ids:
                ciclo = get_object_or_404(CicloManutencaoCoating, pk=cid)
                
                valor_aferido_str = request.POST.get(f'valor_aferido_{ciclo.id}')
                try:
                    valor_aferido = float(valor_aferido_str) if valor_aferido_str else None
                except ValueError:
                    valor_aferido = None
                
                manut = ManutencaoRealizadaCoating.objects.create(
                    registro=reg, 
                    ciclo=ciclo,
                    observacao=observacao if observacao else None,
                    valor_aferido=valor_aferido
                )
                
                for item in ciclo.itens_checklist.all():
                    chk_name = f'checklist_{ciclo.id}_{item.id}'
                    feito = request.POST.get(chk_name) == 'on'
                    RespostaChecklistManutencao.objects.create(
                        manutencao=manut,
                        item=item,
                        feito=feito
                    )
            
        messages.success(request, f"Manutenções atualizadas com sucesso para o Lote {registro.lote} (lados CC e CX).")
    except Exception as e:
        messages.error(request, f"Erro ao registrar manutenção: {str(e)}")
        
    return redirect("laboratorio:coating_painel")

@login_required
def run_migrate_view(request):
    if request.user.is_superuser:
        from django.core.management import call_command
        try:
            call_command('migrate')
            return HttpResponse("Migrações aplicadas com sucesso no banco de dados!")
        except Exception as e:
            return HttpResponse(f"Erro: {str(e)}")
        return HttpResponse("Migrações aplicadas com sucesso.")
    return HttpResponse("Acesso negado.", status=403)

@login_required
def obter_observacoes_lote(request):
    try:
        registro_id = request.GET.get('id')
        registro = get_object_or_404(RegistroCoating, pk=registro_id)
        
        # Busca ambos os registros do lote na mesma máquina e turno
        registros = RegistroCoating.objects.filter(
            turno_coating=registro.turno_coating,
            maquina=registro.maquina,
            lote=registro.lote
        )
        
        obs_cc = ""
        obs_cx = ""
        id_cc = None
        id_cx = None
        
        for reg in registros:
            if reg.lado == 'CC':
                obs_cc = reg.observacao or ""
                id_cc = reg.id
            elif reg.lado == 'CX':
                obs_cx = reg.observacao or ""
                id_cx = reg.id
                
        return JsonResponse({
            'success': True,
            'obs_cc': obs_cc,
            'obs_cx': obs_cx,
            'id_cc': id_cc,
            'id_cx': id_cx,
            'lote': registro.lote
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def configurar_checklist_ciclo(request, ciclo_id):
    ciclo = get_object_or_404(CicloManutencaoCoating, pk=ciclo_id)
    if request.method == "POST":
        action = request.POST.get('action')
        if action == 'add':
            texto = request.POST.get('texto')
            ordem = request.POST.get('ordem', '1')
            if texto:
                ItemChecklistCiclo.objects.create(
                    ciclo=ciclo,
                    texto=texto,
                    ordem=int(ordem) if ordem.isdigit() else 1
                )
                messages.success(request, "Item adicionado ao checklist.")
        elif action == 'delete':
            item_id = request.POST.get('item_id')
            ItemChecklistCiclo.objects.filter(id=item_id, ciclo=ciclo).delete()
            messages.success(request, "Item removido do checklist.")
        return redirect('laboratorio:configurar_checklist_ciclo', ciclo_id=ciclo.id)
        
    return render(request, "laboratorio/ciclo_checklist_config.html", {
        "ciclo": ciclo,
    })

@login_required
@require_POST
def ciclo_coating_delete(request, pk):
    try:
        ciclo = get_object_or_404(CicloManutencaoCoating, pk=pk)
        nome = ciclo.nome
        maq = ciclo.maquina.codigo
        ciclo.delete()
        messages.success(request, f"Ciclo '{nome}' removido da máquina {maq}.")
    except Exception as e:
        if type(e).__name__ == 'ProtectedError' or 'protected foreign keys' in str(e):
            messages.error(request, f"Não é possível excluir o ciclo '{nome}'. Ele já possui manutenções registradas no histórico de lotes e está protegido para fins de auditoria.")
        else:
            messages.error(request, f"Erro ao remover ciclo: {str(e)}")
        
    return redirect("laboratorio:ciclo_coating_list")


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
@require_POST
def salvar_observacoes_lote(request):
    try:
        data = json.loads(request.body)
        id_cc = data.get('id_cc')
        id_cx = data.get('id_cx')
        obs_cc = data.get('obs_cc', '')
        obs_cx = data.get('obs_cx', '')
        
        if id_cc:
            reg_cc = RegistroCoating.objects.get(pk=id_cc)
            reg_cc.observacao = obs_cc
            reg_cc.save()
            
        if id_cx:
            reg_cx = RegistroCoating.objects.get(pk=id_cx)
            reg_cx.observacao = obs_cx
            reg_cx.save()
            
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@permission_required('core.nav_laboratorio_coating_dashboard', raise_exception=True)
def dashboard_coating(request):
    from django.utils import timezone
    from datetime import timedelta, datetime
    from django.db.models import Count, Avg, F, ExpressionWrapper, DurationField
    import json
    
    periodo = request.GET.get('periodo', '15')
    maquina_id = request.GET.get('maquina', '')
    
    hoje = timezone.localtime().date()
    
    if periodo == '7':
        inicio = hoje - timedelta(days=7)
        dias_totais = 8
    elif periodo == '30':
        inicio = hoje - timedelta(days=30)
        dias_totais = 31
    elif periodo == 'mes':
        inicio = hoje.replace(day=1)
        dias_totais = (hoje - inicio).days + 1
    elif periodo == 'ano':
        inicio = hoje.replace(month=1, day=1)
        dias_totais = (hoje - inicio).days + 1
    else: # default 15
        inicio = hoje - timedelta(days=15)
        dias_totais = 16
        
    dias = [inicio + timedelta(days=i) for i in range(dias_totais)]
    
    qs_registros = RegistroCoating.objects.filter(turno_coating__data__gte=inicio, turno_coating__data__lte=hoje).select_related('maquina', 'turno_coating', 'tratamento')
    qs_manutencoes = ManutencaoRealizadaCoating.objects.filter(registro__turno_coating__data__gte=inicio, registro__turno_coating__data__lte=hoje).select_related('ciclo')
    
    if maquina_id:
        qs_registros = qs_registros.filter(maquina_id=maquina_id)
        qs_manutencoes = qs_manutencoes.filter(registro__maquina_id=maquina_id)
        
    maquinas = Maquina.objects.filter(setor__nome__iexact='COATING')
    maqs_to_iter = maquinas.filter(id=maquina_id) if maquina_id else maquinas
    
    # KPI 1: Total Lotes (distinct by lote, data, maquina)
    lotes_unicos = qs_registros.values('lote', 'turno_coating__data', 'maquina_id').distinct()
    total_lotes = lotes_unicos.count()
    
    # KPI 2: Maquina mais produtiva
    maquina_counts = lotes_unicos.values('maquina__codigo').annotate(total=Count('lote')).order_by('-total')
    maq_mais_produtiva = maquina_counts.first()['maquina__codigo'] if maquina_counts else 'N/A'
    
    # KPI 3 e 4: Tempos Médios
    tempos = qs_registros.filter(hora_entrada__isnull=False, hora_saida__isnull=False).aggregate(
        rodando=Avg(
            ExpressionWrapper(
                F('hora_saida') - F('hora_entrada'),
                output_field=DurationField()
            )
        )
    )
    avg_rodando = tempos['rodando']
    avg_rodando_str = str(avg_rodando).split('.')[0] if avg_rodando else '00:00'
    if avg_rodando_str.startswith('0:'): avg_rodando_str = '00' + avg_rodando_str[1:]
    
    registros_ord = qs_registros.order_by('maquina_id', 'turno_coating__data', 'hora_entrada')
    tempos_parados = []
    last_saida = {}
    for r in registros_ord:
        if not r.hora_entrada or not r.hora_saida:
            continue
        key = (r.maquina_id, r.turno_coating.data)
        if key in last_saida:
            dt_entrada = r.hora_entrada
            dt_saida_ant = last_saida[key]
            if dt_entrada > dt_saida_ant:
                tempos_parados.append((dt_entrada - dt_saida_ant).total_seconds())
        last_saida[key] = r.hora_saida
        
    if tempos_parados:
        avg_parado_sec = sum(tempos_parados) / len(tempos_parados)
        avg_parado_str = str(timedelta(seconds=int(avg_parado_sec)))
    else:
        avg_parado_str = '00:00:00'
        
    # Chart 1: Lotes Produzidos por Dia
    labels_dia = [d.strftime('%d/%m') for d in dias]
    datasets_dia = []
    cores = ['#0d6efd', '#198754', '#ffc107', '#dc3545', '#6f42c1', '#fd7e14']
    
    grid_data = { d: {} for d in dias }
    
    for i, maq in enumerate(maqs_to_iter):
        data_maq = []
        for d in dias:
            count = qs_registros.filter(maquina=maq, turno_coating__data=d).values('lote').distinct().count()
            data_maq.append(count)
            grid_data[d][maq.codigo] = count
            
        cor = cores[i % len(cores)]
        datasets_dia.append({
            'label': maq.codigo,
            'data': data_maq,
            'backgroundColor': cor,
            'borderColor': cor,
            'tension': 0.3,
            'borderWidth': 2
        })
        
    grid_rows = []
    for d in dias:
        row = {'data': d.strftime('%d/%m/%Y'), 'obj_data': d.strftime('%Y-%m-%d')}
        for maq in maqs_to_iter:
            row[maq.codigo] = grid_data[d][maq.codigo]
        row['Total'] = sum(grid_data[d].values())
        grid_rows.append(row)
        
    # Chart 2: Tratamentos
    tratamentos_count = qs_registros.values('tratamento__nome').annotate(total=Count('id')).order_by('-total')
    labels_trat = [t['tratamento__nome'] or 'Sem Tratamento' for t in tratamentos_count]
    data_trat = [t['total'] for t in tratamentos_count]
    
    # Chart 3: Manutenções Feitas
    manut_feitas = qs_manutencoes.values('ciclo__nome').annotate(total=Count('id')).order_by('-total')
    labels_manut = [m['ciclo__nome'] for m in manut_feitas]
    data_manut = [m['total'] for m in manut_feitas]
    
    return render(request, "laboratorio/dashboard_coating.html", {
        "maquinas": maquinas,
        "maquina_selecionada": int(maquina_id) if maquina_id else "",
        "periodo": periodo,
        "total_lotes": total_lotes,
        "maq_mais_produtiva": maq_mais_produtiva,
        "avg_rodando": avg_rodando_str,
        "avg_parado": avg_parado_str,
        "labels_json": json.dumps(labels_dia),
        "datasets_json": json.dumps(datasets_dia),
        "labels_trat": json.dumps(labels_trat),
        "data_trat": json.dumps(data_trat),
        "labels_manut": json.dumps(labels_manut),
        "data_manut": json.dumps(data_manut),
        "grid_rows": grid_rows,
        "maquinas_grid": maqs_to_iter,
    })

@login_required
@permission_required('core.nav_laboratorio_coating_importacao', raise_exception=True)
def baixar_modelo_importacao_coating(request):
    import pandas as pd
    import io
    
    df = pd.DataFrame(columns=[
        'Data (DD/MM/YYYY)', 'Turno', 'Maquina', 'Lote', 
        'Tratamento', 'Lado', 'Observacao'
    ])
    df.loc[0] = ['24/07/2026', 'TURNO 01', 'DLX1200', '1', 'BLUE CUT', 'CC', 'Atraso na liberação']
    df.loc[1] = ['24/07/2026', 'TURNO 01', 'DLX1200', '1', 'BLUE CUT', 'CX', '']
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Lotes')
    
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=Modelo_Importacao_Lotes.xlsx'
    return response

@login_required
@require_POST
@permission_required('core.nav_laboratorio_coating_importacao', raise_exception=True)
def importar_lotes_coating(request):
    import pandas as pd
    from django.db import transaction
    
    if 'arquivo' not in request.FILES:
        messages.error(request, 'Nenhum arquivo selecionado.')
        return redirect('laboratorio:coating_painel')
        
    arquivo = request.FILES['arquivo']
    try:
        if arquivo.name.endswith('.csv'):
            df = pd.read_csv(arquivo, sep=';', encoding='latin1')
        else:
            df = pd.read_excel(arquivo)
            
        lotes_criados = 0
        erros = []
        
        with transaction.atomic():
            for index, row in df.iterrows():
                try:
                    data_str = str(row.get('Data (DD/MM/YYYY)', '')).strip()
                    turno_nome = str(row.get('Turno', '')).strip()
                    maq_nome = str(row.get('Maquina', '')).strip()
                    lote_val = str(row.get('Lote', '')).strip()
                    trat_nome = str(row.get('Tratamento', '')).strip()
                    lado_val = str(row.get('Lado', '')).strip().upper()
                    obs_val = str(row.get('Observacao', '')).strip()
                    
                    if obs_val == 'nan' or obs_val.lower() == 'none':
                        obs_val = ''
                        
                    if not (data_str and turno_nome and maq_nome and lote_val and trat_nome and lado_val):
                        continue # Pula linha vazia
                        
                    # Conversões
                    data_obj = datetime.strptime(data_str.split(' ')[0], '%d/%m/%Y').date()
                    
                    # Buscar Turno (cria Registro de Turno se nao existir para a data)
                    regra_turno = RegraTurnoCoating.objects.filter(nome__iexact=turno_nome).first()
                    if not regra_turno:
                        raise ValueError(f"Turno '{turno_nome}' não encontrado.")
                        
                    turno_obj, _ = TurnoCoating.objects.get_or_create(
                        data=data_obj,
                        regra=regra_turno,
                        defaults={'aberto': False}
                    )
                    
                    # Máquina
                    maquina = Maquina.objects.filter(nome__iexact=maq_nome, setor__nome__iexact='COATING').first()
                    if not maquina:
                        raise ValueError(f"Máquina '{maq_nome}' não encontrada no setor Coating.")
                        
                    # Tratamento
                    tratamento = TratamentoAntiReflexo.objects.filter(nome__iexact=trat_nome).first()
                    if not tratamento:
                        raise ValueError(f"Tratamento '{trat_nome}' não encontrado.")
                        
                    # Cria ou atualiza
                    registro, created = RegistroCoating.objects.update_or_create(
                        turno_coating=turno_obj,
                        maquina=maquina,
                        lote=int(lote_val),
                        lado=lado_val,
                        defaults={
                            'tratamento': tratamento,
                            'observacao': obs_val if obs_val else None
                        }
                    )
                    if created:
                        lotes_criados += 1
                        
                except Exception as row_e:
                    erros.append(f"Linha {index + 2}: {str(row_e)}")
                    
        if erros:
            messages.warning(request, f"Importação concluída com {len(erros)} erros. Lotes criados: {lotes_criados}. Detalhes: {', '.join(erros[:5])}...")
        else:
            messages.success(request, f"Importação concluída com sucesso! {lotes_criados} registros criados.")
            
    except Exception as e:
        messages.error(request, f"Erro fatal ao processar o arquivo: {str(e)}")
        
    return redirect('laboratorio:coating_painel')
