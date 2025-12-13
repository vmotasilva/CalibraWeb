
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import HttpResponseRedirect

# Edição de férias
@login_required
@require_http_methods(["GET", "POST"])
def editar_ferias_view(request, colab_id, ferias_id):
    ferias = get_object_or_404(Ferias, id=ferias_id, colaborador_id=colab_id)
    colaborador = ferias.colaborador
    if request.method == "POST":
        form = FeriasForm(request.POST, instance=ferias)
        if form.is_valid():
            form.save()
            messages.success(request, "Registro de férias atualizado com sucesso!")
            return redirect('detalhe_colaborador', colab_id=colaborador.id)
        else:
            messages.error(request, "Verifique os dados do formulário.")
    else:
        form = FeriasForm(instance=ferias)
    return render(request, 'rh/ferias_form.html', {"form": form, "colaborador": colaborador, "edicao": True})

# Exclusão de férias
@login_required
@require_http_methods(["POST"])
def excluir_ferias_view(request, colab_id, ferias_id):
    ferias = get_object_or_404(Ferias, id=ferias_id, colaborador_id=colab_id)
    colaborador = ferias.colaborador
    ferias.delete()
    # Atualiza o campo em_ferias do colaborador após exclusão
    hoje = date.today()
    ferias_ativas = Ferias.objects.filter(
        colaborador=colaborador,
        aprovada=True,
        data_inicio__lte=hoje,
        data_fim__gte=hoje
    ).exists()
    colaborador.em_ferias = ferias_ativas
    colaborador.save(update_fields=["em_ferias"])
    messages.success(request, "Registro de férias excluído com sucesso!")
    return redirect('detalhe_colaborador', colab_id=colaborador.id)

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from rh.models import Colaborador, Ocorrencia, Ferias
from rh.forms import ColaboradorForm, OcorrenciaForm, FeriasForm

@login_required
@require_http_methods(["GET", "POST"])
def registrar_ferias_view(request, colab_id):
    colaborador = get_object_or_404(Colaborador, id=colab_id)
    if request.method == "POST":
        form = FeriasForm(request.POST)
        if form.is_valid():
            ferias = form.save(commit=False)
            ferias.colaborador = colaborador
            ferias.save()
            messages.success(request, "Férias registradas com sucesso!")
            return redirect('detalhe_colaborador', colab_id=colaborador.id)
        else:
            messages.error(request, "Verifique os dados do formulário.")
    else:
        form = FeriasForm()
    return render(request, 'rh/ferias_form.html', {"form": form, "colaborador": colaborador})
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
from qms.views_helpers import get_all_subordinates, get_colaborador_for_user


def can_user_access_colaborador(request_user, target_colaborador):
    """
    Verifica se o usuário logado pode acessar as informações de um colaborador.
    Retorna True se:
    - É superusuário
    - É staff (RH/DP/Qualidade)
    - É o próprio colaborador
    - É lider/supervisor/gerente do colaborador (direto ou indireto)
    """
    if request_user.is_superuser:
        return True
    
    usuario_logado = get_colaborador_for_user(request_user)
    if not usuario_logado:
        return False
    
    # Verificar se está em setor administrativo
    setor_nome = (usuario_logado.setor.nome.upper() if usuario_logado.setor else "")
    if any(k in setor_nome for k in ["RH", "DP", "QUALIDADE"]):
        return True
    
    # Verificar se é gerente ou diretor
    if HierarquiaSetor.objects.filter(gerente=usuario_logado).exists() or \
       HierarquiaSetor.objects.filter(diretor=usuario_logado).exists():
        return True
    
    # Verificar se é o próprio colaborador
    if usuario_logado.id == target_colaborador.id:
        return True
    
    # Verificar se é subordinado direto (lider, supervisor, gerente)
    if Colaborador.objects.filter(
        Q(lider=usuario_logado) | Q(supervisor=usuario_logado) | Q(gerente=usuario_logado),
        id=target_colaborador.id
    ).exists():
        return True
    
    # Verificar se é subordinado indireto
    subordinados = get_all_subordinates(usuario_logado)
    if target_colaborador.id in subordinados:
        return True
    
    return False


@login_required
def modulo_rh_view(request):
    """Dashboard principal do módulo de RH com filtros avançados."""
    colab = None
    try:
        colab = get_colaborador_for_user(request.user)
    except Exception:
        pass

    # 1. VISIBILIDADE - Quem pode ver todos vs sua árvore
    ids_permitidos = set()
    can_see_salary = False
    can_view_all = False

    # Verificar se é superusuário (mesmo sem Colaborador associado)
    if request.user.is_superuser:
        can_view_all = True
    elif colab:
        # Verificar se está em setor administrativo (RH, DP, QUALIDADE)
        setor_nome = (colab.setor.nome.upper() if colab.setor else "")
        if any(k in setor_nome for k in ["RH", "DP", "QUALIDADE"]):
            can_view_all = True
        # Verificar se é gerente
        elif (
            "GERENTE" in str(colab.cargo).upper()
            or HierarquiaSetor.objects.filter(gerente=colab).exists()
        ):
            can_view_all = True

    # Definir IDs permitidos baseado em permissão
    if can_view_all:
        # Ver todos os colaboradores
        ids_permitidos = set(Colaborador.objects.all().values_list("id", flat=True))
    elif colab:
        # Ver apenas subordinados diretos e a si mesmo
        # Subordinados por liderança
        ids_permitidos.add(colab.id)
        
        # Subordinados diretos (lider, supervisor, gerente)
        diretos = Colaborador.objects.filter(
            Q(lider=colab) | Q(supervisor=colab) | Q(gerente=colab)
        ).values_list('id', flat=True)
        ids_permitidos.update(diretos)
        
        # Subordinados indiretos (função auxiliar)
        subordinados_indiretos = get_all_subordinates(colab)
        ids_permitidos.update(subordinados_indiretos)
    else:
        # Usuário não tem colaborador associado
        ids_permitidos = set()

    # Permissão para ver salário
    if request.user.is_superuser:
        can_see_salary = True
    elif colab:
        if ("GERENTE" in str(colab.cargo).upper() or
            HierarquiaSetor.objects.filter(gerente=colab).exists() or
            "DIRETOR" in str(colab.cargo).upper() or
            HierarquiaSetor.objects.filter(diretor=colab).exists()):
            can_see_salary = True

    # QuerySet base com filtros de visibilidade
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


    # Filtro de férias (checkbox ou query param 'em_ferias')
    em_ferias_param = request.GET.get('em_ferias')
    if em_ferias_param == '1':
        funcionarios_visiveis = funcionarios_base.filter(em_ferias=True)
    else:
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
    alvo = get_object_or_404(Colaborador, id=colab_id)
    
    # Verificar permissão de acesso
    if not can_user_access_colaborador(request.user, alvo):
        messages.error(request, "Acesso Negado. Você não tem permissão para ver este colaborador.")
        return redirect("modulo_rh")
    
    usuario_logado = None
    try:
        usuario_logado = get_colaborador_for_user(request.user)
    except Exception:
        pass

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
        dt_vencimento = getattr(f, 'vencimento', None)
        # Só conta como vencida se não for GOZADAS
        if dt_vencimento and dt_vencimento < hoje and f.status != 'GOZADAS':
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
    alvo = get_object_or_404(Colaborador, id=colab_id)

    # Verificação de acesso usando função auxiliar
    if not can_user_access_colaborador(request.user, alvo):
        messages.error(request, "Acesso Negado. Você não tem permissão para editar este colaborador.")
        return redirect("modulo_rh")
    
    usuario_logado = None
    try:
        usuario_logado = get_colaborador_for_user(request.user)
    except Exception:
        pass

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
        "rh/editar_colaborador_novo.html",
        {"form": form, "alvo": alvo, "colaborador": usuario_logado},
    )


@login_required
def registrar_ocorrencia_view(request):
    """Registra nova ocorrência de RH para um colaborador."""
    usuario_logado = None
    try:
        usuario_logado = get_colaborador_for_user(request.user)
    except Exception:
        pass
    
    # Verificar permissão geral de acesso ao módulo
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
    
    # Se há um colaborador pré-selecionado, verificar acesso
    if preselect_id:
        try:
            colab_pré = Colaborador.objects.get(id=preselect_id)
            if not can_user_access_colaborador(request.user, colab_pré):
                messages.error(request, "Acesso Negado. Você não tem permissão para registrar ocorrências para este colaborador.")
                return redirect("modulo_rh")
        except Colaborador.DoesNotExist:
            pass
    
    if request.method == "POST":
        form = OcorrenciaForm(request.POST, request.FILES)
        if form.is_valid():
            oc = form.save(commit=False)
            
            # Verificar acesso ao colaborador selecionado no formulário
            if oc.colaborador and not can_user_access_colaborador(request.user, oc.colaborador):
                messages.error(request, "Acesso Negado. Você não tem permissão para registrar ocorrências para este colaborador.")
                return redirect("modulo_rh")
            
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
    
    # Verificar permissão ao colaborador da ocorrência
    if not can_user_access_colaborador(request.user, ocorrencia.colaborador):
        messages.error(request, "Acesso Negado. Você não tem permissão para editar ocorrências deste colaborador.")
        return redirect("modulo_rh")
    
    # Verificar permissão geral para editar ocorrências (superuser, staff ou RH)
    usuario_logado = None
    try:
        usuario_logado = get_colaborador_for_user(request.user)
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
    
    # Verificar permissão ao colaborador da ocorrência
    if not can_user_access_colaborador(request.user, ocorrencia.colaborador):
        messages.error(request, "Acesso Negado. Você não tem permissão para deletar ocorrências deste colaborador.")
        return redirect("modulo_rh")
    
    # Verificar permissão geral para deletar ocorrências (superuser, staff ou RH)
    usuario_logado = None
    try:
        usuario_logado = get_colaborador_for_user(request.user)
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
