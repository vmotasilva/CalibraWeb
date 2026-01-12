# -*- coding: utf-8 -*-
"""
Views para o módulo RH (Recursos Humanos)
"""

from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_page
from django.db.models import Q, Prefetch
from django.http import HttpResponseRedirect
from django.core.paginator import Paginator
from django.core.cache import cache
import logging
import json

logger = logging.getLogger(__name__)

# Imports dos models
from rh.models import Colaborador, Ocorrencia, Ferias
from organization.models import Setor, CentroCusto, HierarquiaSetor
from procedures.models import ColaboradorPerfil, PerfilTreinamento

# Imports dos forms
from rh.forms import ColaboradorForm, OcorrenciaForm, FeriasForm

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


def get_colaboradores_acessiveis(request_user):
    """
    Retorna queryset de colaboradores que o usuário tem permissão de acesso.
    """
    if request_user.is_superuser:
        return Colaborador.objects.all()
    
    usuario_logado = get_colaborador_for_user(request_user)
    if not usuario_logado:
        return Colaborador.objects.none()
    
    # Se é staff (RH/DP/Qualidade), pode ver todos
    setor_nome = (usuario_logado.setor.nome.upper() if usuario_logado.setor else "")
    if any(k in setor_nome for k in ["RH", "DP", "QUALIDADE"]):
        return Colaborador.objects.all()
    
    # Se é gerente ou diretor, pode ver seus subordinados
    if HierarquiaSetor.objects.filter(gerente=usuario_logado).exists() or \
       HierarquiaSetor.objects.filter(diretor=usuario_logado).exists():
        subordinados_ids = get_all_subordinates(usuario_logado)
        subordinados_ids.add(usuario_logado.id)
        return Colaborador.objects.filter(id__in=subordinados_ids)
    
    # Caso contrário, pode ver apenas a si mesmo
    return Colaborador.objects.filter(id=usuario_logado.id)


@login_required
def modulo_rh_view(request):
    """Dashboard principal do módulo de RH com filtros avançados."""
    from django.db.models import Prefetch
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    from procedures.models import ColaboradorPerfil
    
    colab = None
    try:
        colab = get_colaborador_for_user(request.user)
    except Exception:
        pass

    # 1. VISIBILIDADE - Quem pode ver todos vs sua árvore (otimizado com cache)
    ids_permitidos = set()
    can_see_salary = False
    can_view_all = False

    # Verificar se é superusuário (mesmo sem Colaborador associado)
    # SUPERUSERS SEMPRE VÊM TODOS SEM LIMITAÇÕES
    if request.user.is_superuser:
        can_view_all = True
        can_see_salary = True  # Também ver salários
    elif colab:
        # Verificar se está em setor administrativo (RH, DP, QUALIDADE)
        setor_nome = (colab.setor.nome.upper() if colab.setor else "")
        if any(k in setor_nome for k in ["RH", "DP", "QUALIDADE"]):
            can_view_all = True
        # Verificar se é gerente - fazer uma única query
        elif (
            "GERENTE" in str(colab.cargo).upper()
            or HierarquiaSetor.objects.filter(Q(gerente=colab) | Q(diretor=colab)).exists()
        ):
            can_view_all = True
        
        # Permissão para ver salário - verificar uma única vez
        if ("GERENTE" in str(colab.cargo).upper() or
            "DIRETOR" in str(colab.cargo).upper() or
            HierarquiaSetor.objects.filter(Q(gerente=colab) | Q(diretor=colab)).exists()):
            can_see_salary = True

    # Definir IDs permitidos baseado em permissão
    if can_view_all:
        # Ver TODOS os colaboradores - sem filtro de is_active
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

    # Pré-carregar férias ativas usando Prefetch
    prefetch_ferias = Prefetch(
        'ferias_set',
        queryset=Ferias.objects.filter(
            aprovada=True,
            data_inicio__lte=date.today(),
            data_fim__gte=date.today()
        ).order_by('-data_inicio')
    )

    # Pré-carregar perfis ativos com procedimentos em batch
    prefetch_perfis = Prefetch(
        'perfis_treinamento',
        queryset=ColaboradorPerfil.objects.filter(ativo=True).select_related('perfil')
    )

    # QuerySet base com filtros de visibilidade - otimizado
    funcionarios_base = Colaborador.objects.filter(
        id__in=list(ids_permitidos)
    ).select_related(
        'setor', 'centro_custo', 'lider', 'supervisor', 'gerente'
    ).prefetch_related(
        'treinamentos__procedimento',
        prefetch_ferias,
        prefetch_perfis
    ).order_by("nome_completo")

    # Extrair opções de filtro em queries paralelas (sem repetir funcionarios_base.count())
    # Usar valores já em memória para criar opções de filtro
    setores_ids = set(funcionarios_base.exclude(setor__isnull=True).values_list("setor", flat=True))
    lideres_ids = set(funcionarios_base.exclude(lider__isnull=True).values_list("lider", flat=True))
    supervisores_ids = set(funcionarios_base.exclude(supervisor__isnull=True).values_list("supervisor", flat=True))
    gerentes_ids = set(funcionarios_base.exclude(gerente__isnull=True).values_list("gerente", flat=True))
    
    # Fazer queries apenas uma vez com todos os IDs
    setores_filtro = Setor.objects.filter(id__in=setores_ids).order_by("nome") if setores_ids else []
    lideres_filtro = Colaborador.objects.filter(id__in=lideres_ids).order_by("nome_completo") if lideres_ids else []
    supervisores_filtro = Colaborador.objects.filter(id__in=supervisores_ids).order_by("nome_completo") if supervisores_ids else []
    gerentes_filtro = Colaborador.objects.filter(id__in=gerentes_ids).order_by("nome_completo") if gerentes_ids else []

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

    # Aplicar paginação ANTES de calcular estatísticas (lazy evaluation)
    total_colaboradores = funcionarios_visiveis.count()
    paginator = Paginator(funcionarios_visiveis, total_colaboradores if total_colaboradores > 0 else 1)
    page = request.GET.get('page')
    try:
        funcionarios_page = paginator.page(page)
    except PageNotAnInteger:
        funcionarios_page = paginator.page(1)
    except EmptyPage:
        funcionarios_page = paginator.page(paginator.num_pages)
    
    # Calcular estatísticas APENAS para a página atual usando dados pré-carregados
    for f in funcionarios_page.object_list:
        vig = 0
        pend = 0
        last = None
        
        # Usar dados já carregados em memória (via prefetch)
        perfis_ativos = f.perfis_treinamento.all()
        
        if not perfis_ativos:
            f.trein_vigentes = 0
            f.trein_pendentes = 0
            f.trein_ultima_data = None
            continue
        
        # Coletar procedimentos apenas dos grupos/subgrupos selecionados
        procedimentos_ids = set()
        
        for cp in perfis_ativos:
            # Se não tem seleção específica, pegar todos do perfil
            if not cp.grupos_selecionados:
                # Todos os procedimentos do perfil
                procs = cp.perfil.grupos.all().prefetch_related(
                    'subgrupos__procedimentos'
                )
                for grupo in procs:
                    for subgrupo in grupo.subgrupos.all():
                        for proc in subgrupo.procedimentos.all():
                            procedimentos_ids.add(proc.id)
            else:
                # Filtrar por grupos/subgrupos selecionados
                grupos_selecionados = cp.grupos_selecionados.get('grupos', [])
                subgrupos_selecionados = cp.grupos_selecionados.get('subgrupos', [])
                
                # Se há subgrupos selecionados, usar apenas eles
                if subgrupos_selecionados:
                    procs = cp.perfil.grupos.all().prefetch_related(
                        'subgrupos__procedimentos'
                    )
                    for grupo in procs:
                        for subgrupo in grupo.subgrupos.all():
                            if subgrupo.id in subgrupos_selecionados:
                                for proc in subgrupo.procedimentos.all():
                                    procedimentos_ids.add(proc.id)
                # Se há grupos selecionados, usar todos os subgrupos desses grupos
                elif grupos_selecionados:
                    procs = cp.perfil.grupos.all().prefetch_related(
                        'subgrupos__procedimentos'
                    )
                    for grupo in procs:
                        if grupo.id in grupos_selecionados:
                            for subgrupo in grupo.subgrupos.all():
                                for proc in subgrupo.procedimentos.all():
                                    procedimentos_ids.add(proc.id)
        
        # Buscar apenas os treinamentos dos procedimentos dos perfis/grupos/subgrupos associados
        # Usando dados já pré-carregados
        treinamentos_dos_perfis = [
            rt for rt in f.treinamentos.all()
            if rt.procedimento_id in procedimentos_ids
        ]
        
        # Contar status dos treinamentos dos perfis
        for rt in treinamentos_dos_perfis:
            status = rt.status_treinamento
            if status in ("VIGENTE", "OK"):
                vig += 1
            else:
                pend += 1
            if rt.data_treinamento and (last is None or rt.data_treinamento > last):
                last = rt.data_treinamento
        
        f.trein_vigentes = vig
        f.trein_pendentes = pend
        f.trein_ultima_data = last

    # Pré-carregar CentroCusto uma única vez
    centros = CentroCusto.objects.all().order_by("codigo")

    ctx = {
        "funcionarios": funcionarios_page,
        "lideres_filtro": lideres_filtro,
        "setores_filtro": setores_filtro,
        "supervisores_filtro": supervisores_filtro,
        "gerentes_filtro": gerentes_filtro,
        "turnos_filtro": turnos_filtro,
        "centros": centros,
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
        # Gerentes e supervisores podem ver/registrar ocorrências
        if HierarquiaSetor.objects.filter(gerente=usuario_logado).exists() or \
           HierarquiaSetor.objects.filter(supervisor=usuario_logado).exists():
            can_register_occ = True
            can_view_occ = True
        # Colaboradores com cargo de gerente ou supervisor também podem ver/registrar
        if ("GERENTE" in str(usuario_logado.cargo).upper() or
            "SUPERVISOR" in str(usuario_logado.cargo).upper() or
            "DIRETOR" in str(usuario_logado.cargo).upper()):
            can_view_occ = True
        # Apenas a própria pessoa NÃO pode ver suas próprias ocorrências (se não for admin)
        if usuario_logado.id == alvo.id and not (request.user.is_superuser or request.user.is_staff):
            # Pessoa pode ver suas próprias ocorrências apenas se for gerente/supervisor
            if not ("GERENTE" in str(usuario_logado.cargo).upper() or
                    "SUPERVISOR" in str(usuario_logado.cargo).upper() or
                    "DIRETOR" in str(usuario_logado.cargo).upper() or
                    HierarquiaSetor.objects.filter(gerente=usuario_logado).exists() or
                    HierarquiaSetor.objects.filter(supervisor=usuario_logado).exists()):
                can_view_occ = False

    ocorrencias = alvo.ocorrencias.all().order_by("-data_ocorrencia") if can_view_occ else []
    
    # Organizar treinamentos em cascata: Perfil > Grupo > Subgrupo > Procedimento
    matriz_treinamentos = {}
    total_pendentes = 0
    total_treinamentos = 0
    
    # Buscar perfis atribuídos ao colaborador
    perfis_colab = ColaboradorPerfil.objects.filter(
        colaborador=alvo, ativo=True
    ).select_related('perfil').prefetch_related(
        'perfil__grupos__subgrupos__procedimentos'
    )
    
    for cp in perfis_colab:
        perfil = cp.perfil
        grupos_selecionados_ids = cp.grupos_selecionados.get('grupos', []) if cp.grupos_selecionados else []
        subgrupos_selecionados_ids = cp.grupos_selecionados.get('subgrupos', []) if cp.grupos_selecionados else []
        
        if perfil.codigo not in matriz_treinamentos:
            matriz_treinamentos[perfil.codigo] = {
                'perfil': perfil,
                'grupos': {},
                'pendentes': 0,
                'total': 0
            }
        
        for grupo in perfil.grupos.all().order_by('ordem', 'nome'):
            # Filtrar grupos selecionados se houver filtro
            if grupos_selecionados_ids and grupo.id not in grupos_selecionados_ids:
                continue
                
            if grupo.id not in matriz_treinamentos[perfil.codigo]['grupos']:
                matriz_treinamentos[perfil.codigo]['grupos'][grupo.id] = {
                    'grupo': grupo,
                    'subgrupos': {},
                    'pendentes': 0,
                    'total': 0
                }
            
            for subgrupo in grupo.subgrupos.all().order_by('ordem', 'nome'):
                # Filtrar subgrupos selecionados se houver filtro
                if subgrupos_selecionados_ids and subgrupo.id not in subgrupos_selecionados_ids:
                    continue
                    
                if subgrupo.id not in matriz_treinamentos[perfil.codigo]['grupos'][grupo.id]['subgrupos']:
                    matriz_treinamentos[perfil.codigo]['grupos'][grupo.id]['subgrupos'][subgrupo.id] = {
                        'subgrupo': subgrupo,
                        'procedimentos': [],
                        'pendentes': 0,
                        'total': 0
                    }
                
                # Para cada procedimento do subgrupo, buscar o registro de treinamento
                for proc in subgrupo.procedimentos.all().order_by('codigo'):
                    treinamento = alvo.treinamentos.filter(procedimento=proc).first()
                    
                    # Contabilizar
                    total_treinamentos += 1
                    matriz_treinamentos[perfil.codigo]['total'] += 1
                    matriz_treinamentos[perfil.codigo]['grupos'][grupo.id]['total'] += 1
                    matriz_treinamentos[perfil.codigo]['grupos'][grupo.id]['subgrupos'][subgrupo.id]['total'] += 1
                    
                    # Verificar se está pendente
                    if not treinamento or treinamento.status_treinamento not in ('OK', 'VIGENTE'):
                        total_pendentes += 1
                        matriz_treinamentos[perfil.codigo]['pendentes'] += 1
                        matriz_treinamentos[perfil.codigo]['grupos'][grupo.id]['pendentes'] += 1
                        matriz_treinamentos[perfil.codigo]['grupos'][grupo.id]['subgrupos'][subgrupo.id]['pendentes'] += 1
                    
                    matriz_treinamentos[perfil.codigo]['grupos'][grupo.id]['subgrupos'][subgrupo.id]['procedimentos'].append({
                        'procedimento': proc,
                        'treinamento': treinamento
                    })
    
    documentos = alvo.documentos.all().order_by("-arquivo")
    
    # Perfis disponíveis para associação (que ainda não estão associados)
    from procedures.models import PerfilTreinamento
    perfis_ja_associados = ColaboradorPerfil.objects.filter(
        colaborador=alvo, ativo=True
    ).values_list('perfil_id', flat=True)
    
    perfis_disponiveis = PerfilTreinamento.objects.filter(ativo=True).exclude(
        id__in=perfis_ja_associados
    ).prefetch_related('grupos__subgrupos').order_by('codigo')
    
    # Estruturar dados dos perfis para JavaScript (grupos e subgrupos)
    perfis_data = {}
    for perfil in perfis_disponiveis:
        perfis_data[perfil.id] = {
            'codigo': perfil.codigo,
            'nome': perfil.nome,
            'grupos': []
        }
        for grupo in perfil.grupos.all().order_by('ordem', 'nome'):
            grupo_data = {
                'id': grupo.id,
                'nome': grupo.nome,
                'subgrupos': []
            }
            for subgrupo in grupo.subgrupos.all().order_by('ordem', 'nome'):
                grupo_data['subgrupos'].append({
                    'id': subgrupo.id,
                    'nome': subgrupo.nome
                })
            perfis_data[perfil.id]['grupos'].append(grupo_data)

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
        "matriz_treinamentos": matriz_treinamentos,
        "total_treinamentos": total_treinamentos,
        "total_pendentes": total_pendentes,
        "documentos": documentos,
        "ferias": ferias_qs,
        "kpi_ferias_vencidas": ferias_vencidas,
        "kpi_ferias_programadas": ferias_programadas,
        "can_edit": True,
        "supervisor_rh": supervisor_rh,
        "gerente_rh": gerente_rh,
        "perfis_disponiveis": perfis_disponiveis,
        "perfis_data": json.dumps(perfis_data),
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


@login_required
def listar_ocorrencias_view(request):
    """Lista todas as ocorrências registradas, ordenadas por mais recentes primeiro."""
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
        messages.error(request, "Você não tem permissão para acessar a listagem de ocorrências.")
        return redirect("modulo_rh")
    
    # Obter todas as ocorrências ou filtradas por acesso
    if request.user.is_superuser or request.user.is_staff:
        ocorrencias = Ocorrencia.objects.all().select_related('colaborador', 'condutor').order_by('-data_ocorrencia')
    else:
        # Filtrar apenas colaboradores que o usuário tem acesso
        colaboradores_acessiveis = get_colaboradores_acessiveis(request.user)
        ocorrencias = Ocorrencia.objects.filter(colaborador__in=colaboradores_acessiveis).select_related('colaborador', 'condutor').order_by('-data_ocorrencia')
    
    # Filtros opcionais
    colaborador_id = request.GET.get('colaborador_id')
    tipo = request.GET.get('tipo')
    natureza = request.GET.get('natureza')
    
    if colaborador_id:
        ocorrencias = ocorrencias.filter(colaborador_id=colaborador_id)
    
    if tipo:
        ocorrencias = ocorrencias.filter(tipo=tipo)
    
    if natureza:
        ocorrencias = ocorrencias.filter(natureza=natureza)
    
    # Paginação
    paginator = Paginator(ocorrencias, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'ocorrencias': page_obj.object_list,
        'tipos': Ocorrencia.TIPO_CHOICES,
        'naturezas': Ocorrencia.NATUREZA_CHOICES,
        'colaboradores': Colaborador.objects.all().order_by('nome_completo') if (request.user.is_superuser or request.user.is_staff) else None,
        'total_ocorrencias': paginator.count,
    }
    
    return render(request, 'rh/ocorrencias_lista.html', context)


# ==============================================================================
# VIEWS DE FÉRIAS
# ==============================================================================

@login_required
@require_http_methods(["GET", "POST"])
def registrar_ferias_view(request, colab_id):
    """Registra novo período de férias para um colaborador."""
    colaborador = get_object_or_404(Colaborador, id=colab_id)
    
    # Verificar permissão de acesso ao colaborador
    if not can_user_access_colaborador(request.user, colaborador):
        messages.error(request, "Acesso Negado. Você não tem permissão para registrar férias para este colaborador.")
        return redirect("modulo_rh")
    
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
    
    return render(request, 'rh/ferias_form.html', {
        "form": form, 
        "colaborador": colaborador,
        "titulo": "Registrar Férias"
    })


@login_required
@require_http_methods(["GET", "POST"])
def editar_ferias_view(request, colab_id, ferias_id):
    """Edita um período de férias existente."""
    ferias = get_object_or_404(Ferias, id=ferias_id, colaborador_id=colab_id)
    colaborador = ferias.colaborador
    
    # Verificar permissão de acesso ao colaborador
    if not can_user_access_colaborador(request.user, colaborador):
        messages.error(request, "Acesso Negado. Você não tem permissão para editar férias deste colaborador.")
        return redirect("modulo_rh")
    
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
    
    return render(request, 'rh/ferias_form.html', {
        "form": form, 
        "colaborador": colaborador,
        "edicao": True,
        "titulo": "Editar Férias"
    })


@login_required
@require_http_methods(["POST"])
def excluir_ferias_view(request, colab_id, ferias_id):
    """Exclui um período de férias."""
    ferias = get_object_or_404(Ferias, id=ferias_id, colaborador_id=colab_id)
    colaborador = ferias.colaborador
    
    # Verificar permissão de acesso ao colaborador
    if not can_user_access_colaborador(request.user, colaborador):
        messages.error(request, "Acesso Negado. Você não tem permissão para excluir férias deste colaborador.")
        return redirect("modulo_rh")
    
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


@login_required
def gestao_ferias_view(request):
    """Dashboard de gestão de férias com listagem completa."""
    usuario_logado = None
    try:
        usuario_logado = get_colaborador_for_user(request.user)
    except Exception:
        pass
    
    # Verificar permissão de acesso ao módulo
    permitido = False
    if request.user.is_superuser or request.user.is_staff:
        permitido = True
    elif usuario_logado:
        setor_nome = (usuario_logado.setor.nome.upper() if usuario_logado.setor else "")
        if any(k in setor_nome for k in ["RH", "DP", "QUALIDADE"]):
            permitido = True
        if HierarquiaSetor.objects.filter(gerente=usuario_logado).exists() or \
           HierarquiaSetor.objects.filter(diretor=usuario_logado).exists():
            permitido = True
    
    if not permitido:
        messages.error(request, "Você não tem permissão para acessar a gestão de férias.")
        return redirect("modulo_rh")
    
    try:
        # Obter todas as férias ou apenas das que o usuário pode acessar
        if request.user.is_superuser or request.user.is_staff:
            ferias_qs = Ferias.objects.all().select_related('colaborador').order_by('-data_inicio')
        else:
            try:
                colaboradores_acessiveis = get_colaboradores_acessiveis(request.user)
                ferias_qs = Ferias.objects.filter(
                    colaborador__in=colaboradores_acessiveis
                ).select_related('colaborador').order_by('-data_inicio')
            except Exception as e:
                logger.error(f"Erro ao obter colaboradores acessíveis: {e}")
                ferias_qs = Ferias.objects.none()
        
        # Filtros
        status = request.GET.get('status', '').strip()
        aprovada = request.GET.get('aprovada', '').strip()
        colaborador_id = request.GET.get('colaborador_id', '').strip()
        
        if status:
            ferias_qs = ferias_qs.filter(status=status)
        
        if aprovada:
            if aprovada == '1':
                ferias_qs = ferias_qs.filter(aprovada=True)
            elif aprovada == '0':
                ferias_qs = ferias_qs.filter(aprovada=False)
        
        if colaborador_id:
            try:
                ferias_qs = ferias_qs.filter(colaborador_id=int(colaborador_id))
            except (ValueError, TypeError):
                pass
        
        # Paginação
        paginator = Paginator(ferias_qs, 25)
        page = request.GET.get('page', '1').strip()
        try:
            page_num = int(page) if page else 1
            ferias_page = paginator.page(page_num)
        except Exception as e:
            logger.error(f"Erro ao paginar férias: {e}")
            ferias_page = paginator.page(1)
        
        # Estatísticas
        hoje = date.today()
        total_ferias = paginator.count
        
        # KPIs
        ferias_em_andamento = Ferias.objects.filter(
            aprovada=True,
            data_inicio__lte=hoje,
            data_fim__gte=hoje
        ).count()
        
        ferias_vencidas = Ferias.objects.filter(
            aprovada=True,
            data_fim__lt=hoje,
            status__in=['PLANEJADO', 'EM_ANDAMENTO']
        ).count()
        
        ferias_pendentes_aprovacao = Ferias.objects.filter(
            aprovada=False
        ).count()
        
        # Colaboradores para filtro
        if request.user.is_superuser or request.user.is_staff:
            colaboradores = Colaborador.objects.all().order_by('nome_completo')
        else:
            try:
                colaboradores_acessiveis = get_colaboradores_acessiveis(request.user)
                colaboradores = colaboradores_acessiveis.order_by('nome_completo')
            except Exception:
                colaboradores = Colaborador.objects.none()
        
        ctx = {
            "ferias_page": ferias_page,
            "ferias": ferias_page.object_list,
            "status_choices": Ferias.STATUS_CHOICES,
            "colaboradores": colaboradores,
            "total_ferias": total_ferias,
            "ferias_em_andamento": ferias_em_andamento,
            "ferias_vencidas": ferias_vencidas,
            "ferias_pendentes_aprovacao": ferias_pendentes_aprovacao,
            "colaborador_logado": usuario_logado,
            "status_filtro": status,
            "aprovada_filtro": aprovada,
            "colaborador_filtro": colaborador_id,
        }
        
        return render(request, "rh/gestao_ferias.html", ctx)
        
    except Exception as e:
        logger.error(f"Erro fatal na gestão de férias: {e}", exc_info=True)
        messages.error(request, f"Erro ao carregar gestão de férias: {str(e)}")
        return redirect("modulo_rh")


# ==================== API ENDPOINTS ====================

from django.http import JsonResponse


def api_colaboradores(request):
    """API para buscar colaboradores com filtros"""
    colaboradores = Colaborador.objects.select_related('setor', 'lider', 'supervisor').all()
    
    # Aplicar filtros
    q = request.GET.get('q', '').strip()
    if q:
        colaboradores = colaboradores.filter(
            Q(nome_completo__icontains=q) |
            Q(matricula__icontains=q)
        )
    
    setor_id = request.GET.get('setor', '').strip()
    if setor_id:
        colaboradores = colaboradores.filter(setor_id=setor_id)
    
    cargo = request.GET.get('cargo', '').strip()
    if cargo:
        colaboradores = colaboradores.filter(cargo__icontains=cargo)
    
    grupo = request.GET.get('grupo', '').strip()
    if grupo:
        colaboradores = colaboradores.filter(grupo__icontains=grupo)
    
    turno = request.GET.get('turno', '').strip()
    if turno:
        colaboradores = colaboradores.filter(turno=turno)
    
    lider_id = request.GET.get('lider', '').strip()
    if lider_id:
        colaboradores = colaboradores.filter(lider_id=lider_id)
    
    supervisor_id = request.GET.get('supervisor', '').strip()
    if supervisor_id:
        colaboradores = colaboradores.filter(supervisor_id=supervisor_id)
    
    # Limitar resultado
    colaboradores = colaboradores.order_by('nome_completo')[:200]
    
    # Formatar resposta
    data = {
        'colaboradores': [
            {
                'id': c.id,
                'nome': c.nome_completo,
                'matricula': c.matricula,
                'cargo': c.cargo or '',
                'setor': c.setor.nome if c.setor else '',
                'grupo': c.grupo or '',
                'turno': c.get_turno_display() if c.turno else '',
            }
            for c in colaboradores
        ]
    }
    
    return JsonResponse(data)


def api_setores(request):
    """API para listar setores"""
    setores = Setor.objects.all().order_by('nome')
    
    data = {
        'setores': [
            {
                'id': s.id,
                'nome': s.nome
            }
            for s in setores
        ]
    }
    
    return JsonResponse(data)


def api_cargos(request):
    """API para listar cargos únicos"""
    cargos = Colaborador.objects.exclude(
        cargo__isnull=True
    ).exclude(
        cargo=''
    ).values_list('cargo', flat=True).distinct().order_by('cargo')
    
    data = {
        'cargos': list(cargos)
    }
    
    return JsonResponse(data)


def api_grupos(request):
    """API para listar grupos únicos"""
    grupos = Colaborador.objects.exclude(
        grupo__isnull=True
    ).exclude(
        grupo=''
    ).values_list('grupo', flat=True).distinct().order_by('grupo')
    
    data = {
        'grupos': list(grupos)
    }
    
    return JsonResponse(data)


def api_lideres(request):
    """API para listar líderes (colaboradores que são líderes de alguém)"""
    lideres = Colaborador.objects.filter(
        liderados__isnull=False
    ).distinct().order_by('nome_completo')
    
    data = {
        'lideres': [
            {
                'id': l.id,
                'nome': l.nome_completo
            }
            for l in lideres
        ]
    }
    
    return JsonResponse(data)


def api_supervisores(request):
    """API para listar supervisores (colaboradores que são supervisores de alguém)"""
    supervisores = Colaborador.objects.filter(
        supervisionados__isnull=False
    ).distinct().order_by('nome_completo')
    
    data = {
        'supervisores': [
            {
                'id': s.id,
                'nome': s.nome_completo
            }
            for s in supervisores
        ]
    }
    
    return JsonResponse(data)


@login_required
def criar_ferias_view(request, colab_id=None):
    """Criar um novo período de férias para um colaborador."""
    # Se colab_id foi fornecido, usar esse colaborador
    if colab_id:
        colaborador = get_object_or_404(Colaborador, id=colab_id)
        
        # Verificar permissão de acesso ao colaborador
        if not can_user_access_colaborador(request.user, colaborador):
            messages.error(request, "Acesso Negado. Você não tem permissão para registrar férias deste colaborador.")
            return redirect("modulo_rh")
    else:
        # Se não fornecido, usar o colaborador logado (se houver)
        try:
            colaborador = get_colaborador_for_user(request.user)
            if not colaborador:
                messages.error(request, "Você não está associado a um colaborador.")
                return redirect("modulo_rh")
        except Exception:
            messages.error(request, "Erro ao obter seu perfil.")
            return redirect("modulo_rh")
    
    if request.method == "POST":
        form = FeriasForm(request.POST)
        if form.is_valid():
            ferias = form.save(commit=False)
            ferias.colaborador = colaborador
            ferias.save()
            messages.success(request, "Registro de férias criado com sucesso!")
            return redirect('rh:gestao_ferias')
        else:
            messages.error(request, "Verifique os dados do formulário.")
    else:
        form = FeriasForm()
    
    return render(request, 'rh/ferias_form.html', {
        "form": form,
        "colaborador": colaborador,
        "edicao": False,
        "titulo": "Registrar Novas Férias"
    })


@login_required
def atualizar_status_ferias_view(request):
    """View para atualizar status de férias em massa."""
    # Verificar permissão - apenas staff/superuser/RH
    permitido = False
    if request.user.is_superuser or request.user.is_staff:
        permitido = True
    else:
        try:
            usuario_logado = get_colaborador_for_user(request.user)
            if usuario_logado:
                setor_nome = (usuario_logado.setor.nome.upper() if usuario_logado.setor else "")
                if any(k in setor_nome for k in ["RH", "DP", "QUALIDADE"]):
                    permitido = True
        except Exception:
            pass
    
    if not permitido:
        messages.error(request, "Você não tem permissão para executar essa ação.")
        return redirect("rh:gestao_ferias")
    
    try:
        # Importar a lógica da task do módulo correto e executar de forma síncrona
        from rh.tasks.ferias_tasks import atualizar_status_ferias_logic
        
        logger.info("🔄 Iniciando atualização de status de férias...")
        result = atualizar_status_ferias_logic()
        logger.info(f"📊 Resultado da atualização: {result}")
        
        if result.get("success"):
            em_andamento = result.get("em_andamento", 0)
            concluidas = result.get("concluidas", 0)
            desatualizar = result.get("desatualizar", 0)
            total = result.get("total", 0)
            
            message = "✅ Atualização concluída!"
            details = []
            if em_andamento > 0:
                details.append(f"{em_andamento} para EM_ANDAMENTO")
            if concluidas > 0:
                details.append(f"{concluidas} para CONCLUIDO")
            if desatualizar > 0:
                details.append(f"{desatualizar} colaboradores desatualizados")
            
            if details:
                message += " " + ", ".join(details)
            else:
                message += " (Nenhum registro necessitava de atualização)"
            
            messages.success(request, message)
            logger.info(f"✅ Mensagem enviada ao usuário: {message}")
        else:
            error = result.get("error", "Erro desconhecido na atualização")
            logger.error(f"❌ Erro na atualização: {error}")
            messages.error(request, f"Erro ao atualizar: {error}")
            
    except Exception as e:
        logger.error(f"❌ Exceção ao atualizar status de férias: {e}", exc_info=True)
        messages.error(request, f"Erro ao executar atualização: {str(e)}")
    
    return redirect("rh:gestao_ferias")


def importar_ferias_view(request):
    """
    View para importação em massa de férias via arquivo CSV/Excel
    """
    if not request.user.is_authenticated:
        messages.error(request, "Você deve estar autenticado para acessar esta página.")
        return redirect("login")
    
    # Verificar permissão
    permitido = False
    if request.user.is_superuser or request.user.is_staff:
        permitido = True
    else:
        try:
            usuario_logado = get_colaborador_for_user(request.user)
            if usuario_logado:
                setor_nome = (usuario_logado.setor.nome.upper() if usuario_logado.setor else "")
                if any(k in setor_nome for k in ["RH", "DP", "QUALIDADE"]):
                    permitido = True
        except Exception:
            pass
    
    if not permitido:
        messages.error(request, "Você não tem permissão para executar essa ação.")
        return redirect("rh:gestao_ferias")
    
    if request.method == "POST":
        arquivo = request.FILES.get("arquivo_importacao")
        
        if not arquivo:
            messages.error(request, "Nenhum arquivo foi enviado.")
            return redirect("rh:importar_ferias")
        
        try:
            import csv
            from io import StringIO
            import pandas as pd
            from rh.models import Ferias, Colaborador
            from datetime import datetime
            
            logger.info(f"🔄 Iniciando importação de férias do arquivo: {arquivo.name}")
            
            # Detectar tipo de arquivo
            arquivo_nome = arquivo.name.lower()
            registros_criados = 0
            registros_atualizados = 0
            registros_erro = 0
            erros_detalhes = []
            
            try:
                # Tentar ler como Excel ou CSV
                if arquivo_nome.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(arquivo)
                else:
                    # Ler como CSV
                    conteudo = arquivo.read().decode('utf-8')
                    df = pd.read_csv(StringIO(conteudo))
                
                # Remover espaços em branco das colunas
                df.columns = df.columns.str.strip()
                
                logger.info(f"📊 Arquivo contém {len(df)} linhas")
                
                # Processar cada linha
                for idx, row in df.iterrows():
                    try:
                        # Obter dados obrigatórios
                        matricula = str(row.get("Matrícula", "") or row.get("matricula", "") or "").strip()
                        data_inicio = row.get("Data Início", "") or row.get("data_inicio", "")
                        data_fim = row.get("Data Fim", "") or row.get("data_fim", "")
                        dias_solicitados = row.get("Dias Solicitados", "") or row.get("dias_solicitados", "")
                        
                        if not matricula or not data_inicio or not data_fim:
                            registros_erro += 1
                            erros_detalhes.append(f"Linha {idx + 2}: Matrícula, Data Início e Data Fim são obrigatórios")
                            continue
                        
                        # Buscar colaborador
                        try:
                            colaborador = Colaborador.objects.get(matricula=matricula)
                        except Colaborador.DoesNotExist:
                            registros_erro += 1
                            erros_detalhes.append(f"Linha {idx + 2}: Colaborador com matrícula '{matricula}' não encontrado")
                            continue
                        
                        # Converter datas
                        try:
                            if isinstance(data_inicio, str):
                                data_inicio = datetime.strptime(data_inicio, "%d/%m/%Y").date()
                            elif hasattr(data_inicio, 'date'):
                                data_inicio = data_inicio.date()
                            
                            if isinstance(data_fim, str):
                                data_fim = datetime.strptime(data_fim, "%d/%m/%Y").date()
                            elif hasattr(data_fim, 'date'):
                                data_fim = data_fim.date()
                        except ValueError as e:
                            registros_erro += 1
                            erros_detalhes.append(f"Linha {idx + 2}: Erro ao converter datas - {str(e)}")
                            continue
                        
                        # Converter dias solicitados
                        try:
                            dias_solicitados = int(dias_solicitados) if dias_solicitados else (data_fim - data_inicio).days + 1
                        except (ValueError, TypeError):
                            dias_solicitados = (data_fim - data_inicio).days + 1
                        
                        # Dados opcionais
                        aprovada = row.get("Aprovada", "") or row.get("aprovada", "")
                        if isinstance(aprovada, str):
                            aprovada = aprovada.lower() in ["sim", "yes", "true", "1", "s"]
                        else:
                            aprovada = bool(aprovada)
                        
                        descricao = row.get("Descrição", "") or row.get("descricao", "")
                        descricao = str(descricao) if descricao else ""
                        
                        # Buscar ou criar registro de férias
                        ferias, criado = Ferias.objects.get_or_create(
                            colaborador=colaborador,
                            data_inicio=data_inicio,
                            data_fim=data_fim,
                            defaults={
                                "dias_solicitados": dias_solicitados,
                                "aprovada": aprovada,
                                "descricao": descricao,
                                "status": "PLANEJADO"
                            }
                        )
                        
                        if criado:
                            registros_criados += 1
                            logger.info(f"✅ Férias criadas: {colaborador.nome_completo} ({data_inicio} a {data_fim})")
                        else:
                            # Atualizar registro existente
                            ferias.dias_solicitados = dias_solicitados
                            ferias.aprovada = aprovada
                            ferias.descricao = descricao
                            ferias.save()
                            registros_atualizados += 1
                            logger.info(f"🔄 Férias atualizadas: {colaborador.nome_completo} ({data_inicio} a {data_fim})")
                        
                    except Exception as e:
                        registros_erro += 1
                        erros_detalhes.append(f"Linha {idx + 2}: {str(e)}")
                        logger.error(f"❌ Erro ao processar linha {idx + 2}: {str(e)}", exc_info=True)
                
                # Exibir resultado
                mensagem = f"✅ Importação concluída! {registros_criados} criados, {registros_atualizados} atualizados"
                if registros_erro > 0:
                    mensagem += f", {registros_erro} erros"
                    messages.warning(request, mensagem)
                    for erro in erros_detalhes[:5]:  # Mostrar apenas os 5 primeiros erros
                        messages.info(request, erro)
                    if len(erros_detalhes) > 5:
                        messages.info(request, f"... e mais {len(erros_detalhes) - 5} erros")
                else:
                    messages.success(request, mensagem)
                
                logger.info(f"📊 Importação finalizada: {registros_criados} criados, {registros_atualizados} atualizados, {registros_erro} erros")
                
            except Exception as e:
                logger.error(f"❌ Erro ao processar arquivo: {str(e)}", exc_info=True)
                messages.error(request, f"Erro ao processar arquivo: {str(e)}")
        
        except Exception as e:
            logger.error(f"❌ Erro geral na importação: {str(e)}", exc_info=True)
            messages.error(request, f"Erro na importação: {str(e)}")
        
        return redirect("rh:gestao_ferias")
    
    # GET - Mostrar formulário de importação
    context = {
        "titulo": "Importar Férias em Massa",
        "descricao": "Importe férias dos colaboradores a partir de um arquivo CSV ou Excel"
    }
    return render(request, "rh/importar_ferias.html", context)
