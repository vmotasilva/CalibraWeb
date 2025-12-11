# -*- coding: utf-8 -*-
"""
Views para o módulo RH (Recursos Humanos)
"""

from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)

# Imports dos models
from rh.models import Colaborador, Ocorrencia
from organization.models import Setor, CentroCusto, HierarquiaSetor

# Imports dos forms
from rh.forms import ColaboradorForm, OcorrenciaForm

# Imports dos helpers
from qms.views_helpers import get_all_subordinates


@login_required
def modulo_rh_view(request):
    """Dashboard principal do módulo de RH com filtros avançados."""
    colab = None
    try:
        colab = Colaborador.objects.filter(user_django=request.user).first()
    except Exception:
        pass

    # 1. VISIBILIDADE - Quem pode ver todos vs sua árvore
    ids_permitidos = set()
    can_see_salary = False

    can_view_all = False
    if request.user.is_superuser:
        can_view_all = True
    elif colab:
        setor_nome = (colab.setor.nome.upper() if colab.setor else "")
        if any(k in setor_nome for k in ["RH", "DP", "QUALIDADE"]):
            can_view_all = True
        elif (
            "GERENTE" in str(colab.cargo).upper()
            or HierarquiaSetor.objects.filter(gerente=colab).exists()
        ):
            can_view_all = True

    if can_view_all:
        ids_permitidos = set(Colaborador.objects.all().values_list("id", flat=True))
    elif colab:
        # Inclui subordinados diretos e a própria pessoa
        ids_permitidos = get_all_subordinates(colab)
        ids_permitidos.add(colab.id)
        # Também inclui relacionamentos diretos
        diretos = Colaborador.objects.filter(
            Q(lider=colab) | Q(supervisor=colab) | Q(gerente=colab)
        ).values_list('id', flat=True)
        ids_permitidos.update(diretos)
    else:
        ids_permitidos = set()

    # Permissão para ver salário
    if request.user.is_superuser:
        can_see_salary = True
    elif colab:
        if "GERENTE" in str(colab.cargo).upper() or \
           HierarquiaSetor.objects.filter(gerente=colab).exists() or \
           ("DIRETOR" in str(colab.cargo).upper()) or \
           HierarquiaSetor.objects.filter(diretor=colab).exists():
            can_see_salary = True

    # QuerySet base
    funcionarios_base = Colaborador.objects.filter(
        id__in=list(ids_permitidos)
    ).select_related('setor', 'centro_custo', 'lider', 'supervisor', 'gerente').prefetch_related(
        'treinamentos', 'treinamentos__procedimento'
    ).order_by("nome_completo")

    # Opções de filtro baseadas na base de dados
    setores_ids = funcionarios_base.exclude(setor__isnull=True).values_list("setor", flat=True).distinct()
    setores_filtro = Setor.objects.filter(id__in=setores_ids).order_by("nome")

    lideres_ids = funcionarios_base.exclude(lider__isnull=True).values_list("lider", flat=True).distinct()
    lideres_filtro = Colaborador.objects.filter(id__in=lideres_ids).order_by("nome_completo")

    supervisores_ids = funcionarios_base.exclude(supervisor__isnull=True).values_list("supervisor", flat=True).distinct()
    supervisores_filtro = Colaborador.objects.filter(id__in=supervisores_ids).order_by("nome_completo")

    gerentes_ids = funcionarios_base.exclude(gerente__isnull=True).values_list("gerente", flat=True).distinct()
    gerentes_filtro = Colaborador.objects.filter(id__in=gerentes_ids).order_by("nome_completo")

    # Turnos únicos - sem repetições
    turnos_unicos = sorted(set(funcionarios_base.values_list("turno", flat=True).distinct()))
    turnos_map = dict(Colaborador._meta.get_field('turno').choices)
    turnos_filtro = [(turno, turnos_map.get(turno, turno)) for turno in turnos_unicos if turno]

    funcionarios_visiveis = funcionarios_base

    # Estatísticas de Treinamento por colaborador
    for f in funcionarios_visiveis:
        vig = 0
        pend = 0
        last = None
        for rt in getattr(f, 'treinamentos').all():
            if rt.status_treinamento == "VIGENTE":
                vig += 1
            else:
                pend += 1
            if rt.data_treinamento and (last is None or rt.data_treinamento > last):
                last = rt.data_treinamento
        f.trein_vigentes = vig
        f.trein_pendentes = pend
        f.trein_ultima_data = last

    ctx = {
        "funcionarios": funcionarios_visiveis,
        "lideres_filtro": lideres_filtro,
        "setores_filtro": setores_filtro,
        "supervisores_filtro": supervisores_filtro,
        "gerentes_filtro": gerentes_filtro,
        "turnos_filtro": turnos_filtro,
        "centros": CentroCusto.objects.all().order_by("codigo"),
        "can_see_salary": can_see_salary,
        "can_edit": True,
    }
    return render(request, "rh/dashboard.html", ctx)


@login_required
def detalhe_colaborador_view(request, colab_id):
    """Visualiza detalhes completos do colaborador com permissões granulares."""
    usuario_logado = None
    try:
        usuario_logado = Colaborador.objects.filter(user_django=request.user).first()
    except Exception:
        pass
    
    alvo = get_object_or_404(Colaborador, id=colab_id)

    # Busca hierarquia por setor/turno
    supervisor_rh = None
    gerente_rh = None

    if alvo.setor and alvo.turno:
        hierarquia = HierarquiaSetor.objects.filter(
            setor=alvo.setor, turno=alvo.turno
        ).first()

        if not hierarquia:
            hierarquia = HierarquiaSetor.objects.filter(
                setor=alvo.setor, turno="ADM"
            ).first()

        if hierarquia:
            supervisor_rh = hierarquia.supervisor
            gerente_rh = hierarquia.gerente

    # Segurança: pode ver todos se for superuser, gerente, RH/DP/Qualidade
    if not request.user.is_superuser:
        permitido = False
        if usuario_logado:
            setor_nome = (usuario_logado.setor.nome.upper() if usuario_logado.setor else "")
            pode_ver_todos = False
            if any(k in setor_nome for k in ["RH", "DP", "QUALIDADE"]):
                pode_ver_todos = True
            if ("GERENTE" in str(usuario_logado.cargo).upper() or
                HierarquiaSetor.objects.filter(gerente=usuario_logado).exists()):
                pode_ver_todos = True
            if pode_ver_todos:
                permitido = True
            elif usuario_logado.id == alvo.id:
                permitido = True
            else:
                meus_subordinados = get_all_subordinates(usuario_logado)
                if alvo.id in meus_subordinados:
                    permitido = True
        if not permitido:
            messages.error(request, "Acesso Negado.")
            return redirect("modulo_rh")

    # Permissão para ver salário
    can_see_salary = False
    if request.user.is_superuser:
        can_see_salary = True
    elif usuario_logado:
        if (
            "GERENTE" in str(usuario_logado.cargo).upper()
            or HierarquiaSetor.objects.filter(gerente=usuario_logado).exists()
            or "DIRETOR" in str(usuario_logado.cargo).upper()
            or HierarquiaSetor.objects.filter(diretor=usuario_logado).exists()
        ):
            can_see_salary = True

    # Permissões para ocorrências
    can_register_occ = False
    can_view_occ = False
    if request.user.is_superuser or request.user.is_staff:
        can_register_occ = True
        can_view_occ = True
    elif usuario_logado:
        if usuario_logado.setor and "RH" in usuario_logado.setor.nome.upper():
            can_register_occ = True
            can_view_occ = True
        if HierarquiaSetor.objects.filter(gerente=usuario_logado).exists() or \
           HierarquiaSetor.objects.filter(supervisor=usuario_logado).exists():
            can_register_occ = True
            can_view_occ = True
        if usuario_logado.id == alvo.id and not (request.user.is_superuser or request.user.is_staff):
            can_view_occ = False

    ocorrencias = alvo.ocorrencias.all().order_by("-data_ocorrencia") if can_view_occ else []
    treinamentos = alvo.treinamentos.all().order_by("-data_treinamento")
    documentos = alvo.documentos.all().order_by("-arquivo")

    # Férias
    try:
        ferias_qs = alvo.ferias_set.all().order_by("-data_fim")
    except AttributeError:
        ferias_qs = []

    ferias_vencidas = 0
    ferias_programadas = 0
    hoje = date.today()

    for f in ferias_qs:
        dt_limite = (
            f.data_limite
            if f.data_limite
            else (
                f.periodo_aquisitivo_fim + timedelta(days=365)
                if f.periodo_aquisitivo_fim
                else None
            )
        )

        if dt_limite and dt_limite < hoje:
            if f.status != "GOZADAS" and (not f.data_inicio or f.data_inicio < hoje):
                ferias_vencidas += 1

        if f.data_inicio and f.data_inicio > hoje:
            ferias_programadas += 1

    ctx = {
        "colaborador": usuario_logado,
        "alvo": alvo,
        "can_see_salary": can_see_salary,
        "can_register_occ": can_register_occ,
        "can_view_occ": can_view_occ,
        "ocorrencias": ocorrencias,
        "treinamentos": treinamentos,
        "documentos": documentos,
        "ferias": ferias_qs,
        "kpi_ferias_vencidas": ferias_vencidas,
        "kpi_ferias_programadas": ferias_programadas,
        "can_edit": True,
        "supervisor_rh": supervisor_rh,
        "gerente_rh": gerente_rh,
    }
    return render(request, "rh/colaborador_detalhe.html", ctx)


@login_required
def editar_colaborador_view(request, colab_id):
    """Edita dados de um colaborador com permissões de RH."""
    usuario_logado = None
    try:
        usuario_logado = Colaborador.objects.filter(user_django=request.user).first()
    except Exception:
        pass
    
    alvo = get_object_or_404(Colaborador, id=colab_id)

    if not (request.user.is_superuser or request.user.is_staff):
        permitido = False
        if usuario_logado:
            if usuario_logado.setor and "RH" in usuario_logado.setor.nome.upper():
                permitido = True
            else:
                meus_subordinados = get_all_subordinates(usuario_logado)
                if alvo.id in meus_subordinados:
                    permitido = True
        if not permitido:
            messages.error(request, "Acesso Negado.")
            return redirect("modulo_rh")

    if request.method == "POST":
        form = ColaboradorForm(request.POST, instance=alvo)
        if form.is_valid():
            form.save()
            messages.success(request, "Colaborador atualizado com sucesso!")
            return redirect("detalhe_colaborador", colab_id=alvo.id)
        else:
            messages.error(request, "Erro ao salvar.")
    else:
        form = ColaboradorForm(instance=alvo)
    
    return render(
        request,
        "editar_colaborador.html",
        {"form": form, "alvo": alvo, "colaborador": usuario_logado},
    )


@login_required
def registrar_ocorrencia_view(request):
    """Registra nova ocorrência de RH para um colaborador."""
    usuario_logado = None
    try:
        usuario_logado = Colaborador.objects.filter(user_django=request.user).first()
    except Exception:
        pass
    
    permitido = False
    if request.user.is_superuser or request.user.is_staff:
        permitido = True
    elif usuario_logado:
        if usuario_logado.setor and "RH" in usuario_logado.setor.nome.upper():
            permitido = True
        if HierarquiaSetor.objects.filter(gerente=usuario_logado).exists() or \
           HierarquiaSetor.objects.filter(supervisor=usuario_logado).exists():
            permitido = True
    
    if not permitido:
        messages.error(request, "Você não tem permissão para registrar ocorrências.")
        return redirect("modulo_rh")

    preselect_id = request.GET.get("colab_id")
    if request.method == "POST":
        form = OcorrenciaForm(request.POST, request.FILES)
        if form.is_valid():
            oc = form.save(commit=False)
            if not oc.condutor:
                oc.condutor = request.user
            oc.save()
            messages.success(request, "Ocorrência registrada com sucesso!")
            if oc.colaborador_id:
                return redirect("detalhe_colaborador", colab_id=oc.colaborador_id)
            return redirect("modulo_rh")
        else:
            messages.error(request, "Verifique os dados da ocorrência.")
    else:
        initial = {}
        if preselect_id:
            initial["colaborador"] = preselect_id
        initial["condutor"] = request.user.id
        form = OcorrenciaForm(initial=initial)
    
    return render(
        request,
        "rh/ocorrencia_form.html",
        {"form": form},
    )


@login_required
@require_http_methods(["GET", "POST"])
def editar_ocorrencia_view(request, occ_id):
    """Edita uma ocorrência existente."""
    from django.shortcuts import get_object_or_404
    
    ocorrencia = get_object_or_404(Ocorrencia, id=occ_id)
    
    # Verificar permissão (superuser, staff ou RH)
    usuario_logado = None
    try:
        usuario_logado = Colaborador.objects.filter(user_django=request.user).first()
    except Exception:
        pass
    
    permitido = False
    if request.user.is_superuser or request.user.is_staff:
        permitido = True
    elif usuario_logado:
        if usuario_logado.setor and "RH" in usuario_logado.setor.nome.upper():
            permitido = True
    
    if not permitido:
        messages.error(request, "Você não tem permissão para editar ocorrências.")
        return redirect("modulo_rh")
    
    if request.method == "POST":
        form = OcorrenciaForm(request.POST, request.FILES, instance=ocorrencia)
        if form.is_valid():
            form.save()
            messages.success(request, "Ocorrência atualizada com sucesso!")
            return redirect("detalhe_colaborador", colab_id=ocorrencia.colaborador_id)
        else:
            messages.error(request, "Verifique os dados da ocorrência.")
    else:
        form = OcorrenciaForm(instance=ocorrencia)
    
    return render(
        request,
        "rh/ocorrencia_form.html",
        {
            "form": form,
            "edicao": True,
            "ocorrencia": ocorrencia,
        },
    )


@login_required
@require_http_methods(["POST"])
def deletar_ocorrencia_view(request, occ_id):
    """Exclui uma ocorrência."""
    ocorrencia = get_object_or_404(Ocorrencia, id=occ_id)
    
    # Verificar permissão (superuser, staff ou RH)
    usuario_logado = None
    try:
        usuario_logado = Colaborador.objects.filter(user_django=request.user).first()
    except Exception:
        pass
    
    permitido = False
    if request.user.is_superuser or request.user.is_staff:
        permitido = True
    elif usuario_logado:
        if usuario_logado.setor and "RH" in usuario_logado.setor.nome.upper():
            permitido = True
    
    if not permitido:
        messages.error(request, "Você não tem permissão para excluir ocorrências.")
        return redirect("modulo_rh")
    
    colaborador_id = ocorrencia.colaborador_id
    ocorrencia.delete()
    messages.success(request, "Ocorrência excluída com sucesso!")
    return redirect("detalhe_colaborador", colab_id=colaborador_id)
