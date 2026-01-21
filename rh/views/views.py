# -*- coding: utf-8 -*-
"""
Views para o módulo RH (Recursos Humanos)
"""

from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Prefetch
from django.http import HttpResponseRedirect, JsonResponse
from django.core.paginator import Paginator
from django.core.cache import cache
import logging
import json

logger = logging.getLogger(__name__)

# Imports dos models
from rh.models import Colaborador, Ocorrencia, Ferias
from organization.models import Setor, CentroCusto, HierarquiaSetor
from procedures.models import ColaboradorPerfil, PerfilTreinamento, RegistroTreinamento

# Imports dos forms
from rh.forms import ColaboradorForm, OcorrenciaForm, FeriasForm

# Imports dos helpers
from qms.views_helpers import get_all_subordinates, get_colaborador_for_user


def _get_status_colaborador(colab):
    """
    Determina o status de um colaborador baseado em seus campos.
    Prioridade: Desligado > Afastado > Em Férias > Ativo
    """
    if not colab.is_active:
        return 'Desligado'
    elif colab.afastado:
        return 'Afastado'
    elif colab.em_ferias:
        return 'Em Férias'
    else:
        return 'ATIVO'
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
    
    # Verificar se é gerente ou diretor (hierarquia)
    if HierarquiaSetor.objects.filter(Q(gerente=usuario_logado) | Q(diretor=usuario_logado)).exists():
        return True
    
    # Verificar se é o próprio colaborador
    if usuario_logado.id == target_colaborador.id:
        return True
    
    # ✅ NOVO: Verificar se é subordinado direto (lider, supervisor, gerente)
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
    
    # ✅ NOVO: Se é gerente, diretor, LÍDER ou SUPERVISOR, pode ver seus subordinados
    if HierarquiaSetor.objects.filter(Q(gerente=usuario_logado) | Q(diretor=usuario_logado)).exists():
        subordinados_ids = get_all_subordinates(usuario_logado)
        subordinados_ids.add(usuario_logado.id)
        return Colaborador.objects.filter(id__in=subordinados_ids)
    
    # Verificar se é líder ou supervisor - que também têm subordinados
    subordinados_como_lider = Colaborador.objects.filter(
        Q(lider=usuario_logado) | Q(supervisor=usuario_logado) | Q(gerente=usuario_logado)
    ).exists()
    
    if subordinados_como_lider:
        subordinados_ids = get_all_subordinates(usuario_logado)
        subordinados_ids.add(usuario_logado.id)
        return Colaborador.objects.filter(id__in=subordinados_ids)
    
    # Caso contrário, pode ver apenas a si mesmo
    return Colaborador.objects.filter(id=usuario_logado.id)


@login_required
def modulo_rh_view(request):
    """Dashboard principal do módulo de RH com filtros avançados."""
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    
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
        
        # Permissão para ver salário - gerentes, diretores e RH
        if ("GERENTE" in str(colab.cargo).upper() or
            "DIRETOR" in str(colab.cargo).upper() or
            HierarquiaSetor.objects.filter(Q(gerente=colab) | Q(diretor=colab)).exists() or
            any(k in setor_nome for k in ["RH", "DP"])):
            can_see_salary = True

    # Definir IDs permitidos baseado em permissão
    if can_view_all:
        # Ver TODOS os colaboradores - sem filtro de is_active
        ids_permitidos = set(Colaborador.objects.all().values_list("id", flat=True))
    elif colab:
        # Ver apenas subordinados diretos e a si mesmo
        # Sempre pode ver a si mesmo
        ids_permitidos.add(colab.id)
        
        # Subordinados diretos (como lider, supervisor, gerente)
        diretos = Colaborador.objects.filter(
            Q(lider=colab) | Q(supervisor=colab) | Q(gerente=colab)
        ).values_list('id', flat=True)
        ids_permitidos.update(diretos)
        
        # Subordinados indiretos (função auxiliar para líderes/supervisores)
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

    # QuerySet base com filtros de visibilidade - otimizado
    funcionarios_base = Colaborador.objects.filter(
        id__in=list(ids_permitidos)
    ).select_related(
        'setor', 'centro_custo', 'lider', 'supervisor', 'gerente'
    ).prefetch_related(
        'treinamentos__procedimento',
        prefetch_ferias
    ).order_by("nome_completo")

    # Extrair opções de filtro usando dados já carregados em memória
    # EVITAR: .exclude().values_list() - reavalia o queryset inteiro!
    
    # ⚡ OTIMIZAÇÃO: Buscar líderes, supervisores e gerentes únicos dos colaboradores visíveis
    # Usar queries separadas e eficientes para popular os filtros
    
    # Setores únicos dos colaboradores visíveis
    setor_ids = funcionarios_base.values_list('setor_id', flat=True).distinct()
    setores_filtro = Setor.objects.filter(id__in=setor_ids).order_by('nome')
    
    # Líderes únicos (excluindo nulos)
    lider_ids = funcionarios_base.exclude(lider__isnull=True).values_list('lider_id', flat=True).distinct()
    lideres_filtro = Colaborador.objects.filter(id__in=lider_ids).order_by('nome_completo')
    
    # Supervisores únicos (excluindo nulos)
    supervisor_ids = funcionarios_base.exclude(supervisor__isnull=True).values_list('supervisor_id', flat=True).distinct()
    supervisores_filtro = Colaborador.objects.filter(id__in=supervisor_ids).order_by('nome_completo')
    
    # Gerentes únicos (excluindo nulos)
    gerente_ids = funcionarios_base.exclude(gerente__isnull=True).values_list('gerente_id', flat=True).distinct()
    gerentes_filtro = Colaborador.objects.filter(id__in=gerente_ids).order_by('nome_completo')
    
    # Turnos únicos dos colaboradores visíveis - como tuplas (codigo, nome) para o template
    from core.models import TURNOS_CHOICES
    turnos_dict = dict(TURNOS_CHOICES)
    # Usar set() para garantir unicidade e depois ordenar
    turnos_usados = set(funcionarios_base.exclude(turno__isnull=True).exclude(turno='').values_list('turno', flat=True))
    # Criar lista ordenada de tuplas (codigo, nome) apenas para turnos válidos
    turnos_filtro = sorted(
        [(codigo, turnos_dict.get(codigo, codigo)) for codigo in turnos_usados if codigo in turnos_dict],
        key=lambda x: x[1]  # Ordenar pelo nome do turno
    )
    
    # ⚡ OTIMIZAÇÃO: Contar TODOS os colaboradores acessíveis ANTES do filtro
    total_all_colaboradores = funcionarios_base.count()
    
    # Usar todos os colaboradores visíveis (sem filtros de busca ainda)
    funcionarios_visiveis = funcionarios_base
    
    # ⚡ OTIMIZAÇÃO: Aplicar busca por nome ANTES de paginar
    # Isso reduz drasticamente o resultado se o usuário está buscando alguém
    busca = request.GET.get('q', '').strip()
    if busca:
        funcionarios_visiveis = funcionarios_visiveis.filter(
            Q(nome_completo__icontains=busca) | 
            Q(matriculaains=busca) |
            Q(id__icontains=busca)  # Buscar por ID também
        )
    
    # Contar colaboradores após aplicar busca (para exibir "X/200")
    total_colaboradores_filtrados = funcionarios_visiveis.count()
    
    # Aplicar paginação ANTES de calcular estatísticas (lazy evaluation)
    # ⚡ OTIMIZAÇÃO: Mostrar 50 por página
    paginator = Paginator(funcionarios_visiveis, 50)
    page = request.GET.get('page')
    try:
        funcionarios_page = paginator.page(page)
    except PageNotAnInteger:
        funcionarios_page = paginator.page(1)
    except EmptyPage:
        funcionarios_page = paginator.page(paginator.num_pages)
    
    # ⚡ OTIMIZAÇÃO RADICAL: Usar SQL para calcular estatísticas ao invés de Python
    # Isto é 100x mais rápido que loops em Python
    from django.db.models import Count, Max
    
    # Buscar IDs dos colaboradores da página atual
    colaboradores_ids = list(funcionarios_page.object_list.values_list('id', flat=True))
    
    # Query ÚNICA para pegar stats de treinamento por colaborador
    # {colaborador_id: {'vigentes': X, 'pendentes': Y, 'ultima_data': Z}}
    trein_stats = {}
    
    if colaboradores_ids:
        # ⚠️ IMPORTANTE: status_treinamento é uma PROPERTY em Python, não um campo do BD
        # Logo, não podemos usar em .filter() SQL. Usamos data_treinamento como proxy:
        # - data_treinamento NOT NULL + revisao_treinada = OK
        # - data_treinamento NULL = PENDENTE
        
        # Pegar TODOS os treinamentos ativos destes colaboradores
        treinamentos_ativos = RegistroTreinamento.objects.filter(
            colaborador_id__in=colaboradores_ids,
            ativo=True
        ).values_list('colaborador_id', 'data_treinamento', 'revisao_treinada')
        
        # Contar em Python usando a lógica da property
        for colab_id in colaboradores_ids:
            registros = [
                (data, rev) for cid, data, rev in treinamentos_ativos 
                if cid == colab_id
            ]
            
            vigentes = 0
            pendentes = 0
            ultima_vig = None
            
            for data_trein, revisao in registros:
                # Simular a lógica da property status_treinamento
                if revisao and data_trein:  # OK
                    vigentes += 1
                    if ultima_vig is None or data_trein > ultima_vig:
                        ultima_vig = data_trein
                else:  # PENDENTE
                    pendentes += 1
            
            trein_stats[colab_id] = {
                'vigentes': vigentes,
                'pendentes': pendentes,
                'ultima_data': ultima_vig
            }
    
    # Atribuir dados aos colaboradores da página
    for f in funcionarios_page.object_list:
        stats = trein_stats.get(f.id, {'vigentes': 0, 'pendentes': 0, 'ultima_data': None})
        f.trein_vigentes = stats['vigentes']
        f.trein_pendentes = stats['pendentes']
        f.trein_ultima_data = stats['ultima_data']

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
        "total_colaboradores_filtrados": total_colaboradores_filtrados,  # Colaboradores após busca
        "total_colaboradores": total_all_colaboradores,  # Total de colaboradores acessíveis
        "busca": busca,  # Manter valor na busca
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
    procedimentos_contabilizados = set()  # Rastrear procedimentos já contados globalmente
    
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
                    
                    # Verificar se este procedimento já foi contabilizado (em outro perfil)
                    eh_duplicada = proc.id in procedimentos_contabilizados
                    
                    # Contabilizar apenas na primeira vez que aparecer
                    if not eh_duplicada:
                        total_treinamentos += 1
                        procedimentos_contabilizados.add(proc.id)
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
    # Permitir se tem permissão Django de adicionar ocorrências
    permitido = False
    if request.user.is_superuser or request.user.is_staff:
        permitido = True
    elif request.user.has_perm('rh.add_ocorrencia'):
        # Usuário tem permissão Django para adicionar ocorrências
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
    
    # Verificar permissão geral para editar ocorrências (superuser, staff, RH ou permissão Django)
    usuario_logado = None
    try:
        usuario_logado = get_colaborador_for_user(request.user)
    except Exception:
        pass
    
    permitido = False
    if request.user.is_superuser or request.user.is_staff:
        permitido = True
    elif request.user.has_perm('rh.change_ocorrencia'):
        # Usuário tem permissão Django para editar ocorrências
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
    
    # Verificar permissão geral para deletar ocorrências (superuser, staff, RH ou permissão Django)
    usuario_logado = None
    try:
        usuario_logado = get_colaborador_for_user(request.user)
    except Exception:
        pass
    
    permitido = False
    if request.user.is_superuser or request.user.is_staff:
        permitido = True
    elif request.user.has_perm('rh.delete_ocorrencia'):
        # Usuário tem permissão Django para deletar ocorrências
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
    # Permitir se tem permissão Django de visualizar ocorrências
    permitido = False
    if request.user.is_superuser or request.user.is_staff:
        permitido = True
    elif request.user.has_perm('rh.view_ocorrencia'):
        # Usuário tem permissão Django para ver ocorrências
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


@login_required
def exportar_ferias_view(request):
    """
    Exporta registros de férias para Excel no mesmo formato do template de importação.
    Colunas: Matrícula | Data Início | Data Fim | Dias Solicitados | Aprovada | Descrição | Status | Colaborador
    """
    import io
    from django.http import HttpResponse
    
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
        messages.error(request, "Você não tem permissão para exportar férias.")
        return redirect("rh:gestao_ferias")
    
    try:
        import pandas as pd
        
        # Buscar todas as férias
        ferias_qs = Ferias.objects.select_related('colaborador').order_by(
            'colaborador__nome_completo', '-data_inicio'
        )
        
        # Aplicar filtros se existirem (mesmos filtros da tela)
        status = request.GET.get('status', '')
        aprovada = request.GET.get('aprovada', '')
        colaborador_id = request.GET.get('colaborador', '')
        
        if status:
            ferias_qs = ferias_qs.filter(status=status)
        if aprovada:
            if aprovada == 'sim':
                ferias_qs = ferias_qs.filter(aprovada=True)
            elif aprovada == 'nao':
                ferias_qs = ferias_qs.filter(aprovada=False)
        if colaborador_id:
            ferias_qs = ferias_qs.filter(colaborador_id=colaborador_id)
        
        # Preparar dados para o DataFrame
        dados = []
        for f in ferias_qs:
            dados.append({
                'Matrícula': f.colaborador.matricula,
                'Colaborador': f.colaborador.nome_completo,
                'Data Início': f.data_inicio.strftime('%d/%m/%Y') if f.data_inicio else '',
                'Data Fim': f.data_fim.strftime('%d/%m/%Y') if f.data_fim else '',
                'Dias Solicitados': f.dias_solicitados or '',
                'Aprovada': 'Sim' if f.aprovada else 'Não',
                'Status': f.get_status_display() if hasattr(f, 'get_status_display') else f.status,
                'Descrição': f.descricao or '',
            })
        
        # Criar DataFrame
        df = pd.DataFrame(dados)
        
        # Se não houver dados, criar DataFrame vazio com cabeçalhos
        if df.empty:
            df = pd.DataFrame(columns=[
                'Matrícula', 'Colaborador', 'Data Início', 'Data Fim', 
                'Dias Solicitados', 'Aprovada', 'Status', 'Descrição'
            ])
        
        # Criar arquivo Excel em memória
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Férias')
            
            # Ajustar largura das colunas
            worksheet = writer.sheets['Férias']
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).map(len).max() if not df.empty else 0,
                    len(col)
                ) + 2
                worksheet.column_dimensions[chr(65 + idx)].width = min(max_length, 50)
        
        output.seek(0)
        
        # Criar response
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        from datetime import datetime
        filename = f"ferias_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        logger.info(f"📊 Exportação de férias realizada por {request.user.username}: {len(dados)} registros")
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Erro ao exportar férias: {str(e)}", exc_info=True)
        messages.error(request, f"Erro ao exportar férias: {str(e)}")
        return redirect("rh:gestao_ferias")


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


@login_required
@require_http_methods(["GET"])
def api_colaboradores_filtrados(request):
    """
    API para retornar colaboradores com filtros em tempo real (AJAX).
    Suporta filtros: status, lider, supervisor, gerente, setor, turno, busca
    """
    from django.db.models import Count, Max
    
    # Obter colaborador do usuário logado
    colab = None
    try:
        colab = get_colaborador_for_user(request.user)
    except Exception:
        pass

    # 1. VISIBILIDADE - Quem pode ver todos vs sua árvore
    ids_permitidos = set()
    
    if request.user.is_superuser:
        ids_permitidos = set(Colaborador.objects.all().values_list("id", flat=True))
    elif colab:
        # Ver apenas subordinados diretos e a si mesmo
        ids_permitidos.add(colab.id)
        diretos = Colaborador.objects.filter(
            Q(lider=colab) | Q(supervisor=colab) | Q(gerente=colab)
        ).values_list('id', flat=True)
        ids_permitidos.update(diretos)
        subordinados_indiretos = get_all_subordinates(colab)
        ids_permitidos.update(subordinados_indiretos)
    else:
        ids_permitidos = set()

    # 2. Aplicar filtros
    funcionarios = Colaborador.objects.filter(
        id__in=list(ids_permitidos)
    ).select_related(
        'setor', 'centro_custo', 'lider', 'supervisor', 'gerente'
    ).prefetch_related(
        'treinamentos__procedimento'
    ).order_by("nome_completo")

    # Busca por nome/matrícula/ID
    busca = request.GET.get('q', '').strip()
    if busca:
        funcionarios = funcionarios.filter(
            Q(nome_completo__icontains=busca) | 
            Q(matricula__icontains=busca) |
            Q(id__icontains=busca)
        )

    # Filtro por Status
    status_filtros = request.GET.getlist('status')
    if status_filtros:
        status_query = Q()
        for status in status_filtros:
            if status == 'ATIVO':
                status_query |= Q(is_active=True, afastado=False, em_ferias=False)
            elif status == 'FERIAS':
                status_query |= Q(em_ferias=True)
            elif status == 'AFASTADO':
                status_query |= Q(afastado=True)
            elif status == 'INATIVO':
                status_query |= Q(is_active=False)
        if status_query:
            funcionarios = funcionarios.filter(status_query)

    # Filtro por Lider - Incluir o próprio líder nos resultados
    lider_ids = request.GET.getlist('lider')
    if lider_ids:
        # Mostrar colaboradores com esse líder E o próprio líder
        funcionarios = funcionarios.filter(
            Q(lider_id__in=lider_ids) | Q(id__in=lider_ids)
        )

    # Filtro por Supervisor - Incluir o próprio supervisor nos resultados
    supervisor_ids = request.GET.getlist('supervisor')
    if supervisor_ids:
        # Mostrar colaboradores com esse supervisor E o próprio supervisor
        funcionarios = funcionarios.filter(
            Q(supervisor_id__in=supervisor_ids) | Q(id__in=supervisor_ids)
        )

    # Filtro por Gerente - Incluir o próprio gerente nos resultados
    gerente_ids = request.GET.getlist('gerente')
    if gerente_ids:
        # Mostrar colaboradores com esse gerente E o próprio gerente
        funcionarios = funcionarios.filter(
            Q(gerente_id__in=gerente_ids) | Q(id__in=gerente_ids)
        )

    # Filtro por Setor
    setor_ids = request.GET.getlist('setor')
    if setor_ids:
        funcionarios = funcionarios.filter(setor_id__in=setor_ids)

    # Filtro por Turno
    turnos = request.GET.getlist('turno')
    if turnos:
        funcionarios = funcionarios.filter(turno__in=turnos)

    # Filtro por Treinamentos (PENDENTE ou EM_DIA)
    # Este filtro será aplicado após calcular as estatísticas de treinamento
    treino_filtros = request.GET.getlist('treino')

    # Construir resposta JSON
    dados = []
    for colab in funcionarios:
        # Contar treinamentos vigentes e pendentes
        vigentes = 0
        pendentes = 0
        
        for trein in colab.treinamentos.all():
            if trein.ativo:
                if trein.revisao_treinada and trein.data_treinamento:
                    vigentes += 1
                else:
                    pendentes += 1
        
        # Aplicar filtro de treinamentos se selecionado
        if treino_filtros:
            tem_pendentes = pendentes > 0
            em_dia = pendentes == 0
            
            # Verificar se o colaborador atende ao filtro
            passa_filtro = False
            if 'PENDENTE' in treino_filtros and tem_pendentes:
                passa_filtro = True
            if 'EM_DIA' in treino_filtros and em_dia:
                passa_filtro = True
            
            if not passa_filtro:
                continue  # Pular este colaborador
        
        dados.append({
            'id': colab.id,
            'nome': colab.nome_completo,
            'matricula': colab.matricula or '',
            'cargo': str(colab.cargo) if colab.cargo else '',
            'setor': colab.setor.nome if colab.setor else '',
            'centro_custo': colab.centro_custo.codigo if colab.centro_custo else '',
            'turno': colab.turno or '',
            'lider': colab.lider.nome_completo if colab.lider else '',
            'supervisor': colab.supervisor.nome_completo if colab.supervisor else '',
            'gerente': colab.gerente.nome_completo if colab.gerente else '',
            'vigentes': vigentes,
            'pendentes': pendentes,
            'status': _get_status_colaborador(colab),
        })

    return JsonResponse({
        'total': len(dados),
        'colaboradores': dados
    })


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_delete_colaborador(request, colab_id):
    """
    API para deletar um colaborador específico
    """
    try:
        colaborador = get_object_or_404(Colaborador, id=colab_id)
        nome = colaborador.nome_completo
        
        # Deletar usuário Django associado
        if colaborador.user_django:
            colaborador.user_django.delete()
        
        # Deletar colaborador
        colaborador.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Colaborador {nome} deletado com sucesso.'
        })
    except Exception as e:
        logger.error(f'Erro ao deletar colaborador {colab_id}: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_delete_colaboradores_multiple(request):
    """
    API para deletar múltiplos colaboradores
    """
    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])
        
        if not ids:
            return JsonResponse({
                'success': False,
                'error': 'Nenhum ID fornecido'
            }, status=400)
        
        deleted_count = 0
        for colab_id in ids:
            try:
                colaborador = Colaborador.objects.get(id=colab_id)
                
                # Deletar usuário Django associado
                if colaborador.user_django:
                    colaborador.user_django.delete()
                
                # Deletar colaborador
                colaborador.delete()
                deleted_count += 1
            except Colaborador.DoesNotExist:
                continue
            except Exception as e:
                logger.error(f'Erro ao deletar colaborador {colab_id}: {str(e)}')
                continue
        
        return JsonResponse({
            'success': True,
            'deleted': deleted_count,
            'message': f'{deleted_count} colaborador(es) deletado(s) com sucesso.'
        })
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'JSON inválido'
        }, status=400)
    except Exception as e:
        logger.error(f'Erro ao deletar colaboradores: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


# ==============================================================================
# GERENCIAMENTO DE PERMISSÕES
# ==============================================================================

from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType


@login_required
def gerenciar_permissoes_view(request):
    """
    View para gerenciar permissões de usuários via interface customizada.
    Apenas superusuários ou staff podem acessar.
    """
    if not request.user.is_superuser and not request.user.is_staff:
        messages.error(request, 'Você não tem permissão para acessar esta página.')
        return redirect('modulo_rh')
    
    # Buscar todos os usuários ativos (exceto o próprio superusuário se não for admin)
    usuarios = User.objects.filter(is_active=True).select_related().order_by('username')
    
    # Definir as permissões do módulo RH que queremos gerenciar
    # Formato: (codename, nome_amigavel, model_name)
    permissoes_rh = [
        # Colaborador
        ('view_colaborador', 'Visualizar Colaborador', 'colaborador'),
        ('add_colaborador', 'Adicionar Colaborador', 'colaborador'),
        ('change_colaborador', 'Editar Colaborador', 'colaborador'),
        ('delete_colaborador', 'Excluir Colaborador', 'colaborador'),
        # Documento Pessoal
        ('view_documentopessoal', 'Visualizar Documento Pessoal', 'documentopessoal'),
        ('add_documentopessoal', 'Adicionar Documento Pessoal', 'documentopessoal'),
        ('change_documentopessoal', 'Editar Documento Pessoal', 'documentopessoal'),
        ('delete_documentopessoal', 'Excluir Documento Pessoal', 'documentopessoal'),
        # Férias
        ('view_ferias', 'Visualizar Férias', 'ferias'),
        ('add_ferias', 'Adicionar Férias', 'ferias'),
        ('change_ferias', 'Editar Férias', 'ferias'),
        ('delete_ferias', 'Excluir Férias', 'ferias'),
        # Ocorrência
        ('view_ocorrencia', 'Visualizar Ocorrência', 'ocorrencia'),
        ('add_ocorrencia', 'Adicionar Ocorrência', 'ocorrencia'),
        ('change_ocorrencia', 'Editar Ocorrência', 'ocorrencia'),
        ('delete_ocorrencia', 'Excluir Ocorrência', 'ocorrencia'),
    ]
    
    # Buscar as permissões do banco de dados
    permissoes_db = {}
    for codename, nome, model in permissoes_rh:
        try:
            perm = Permission.objects.get(codename=codename, content_type__app_label='rh')
            permissoes_db[codename] = perm
        except Permission.DoesNotExist:
            logger.warning(f'Permissão {codename} não encontrada no banco.')
    
    # Montar dados dos usuários com suas permissões
    usuarios_data = []
    for user in usuarios:
        user_perms = user.user_permissions.filter(content_type__app_label='rh').values_list('codename', flat=True)
        user_perms_set = set(user_perms)
        
        # Verificar se tem o colaborador vinculado
        try:
            colaborador = Colaborador.objects.get(user_django=user)
            colaborador_nome = colaborador.nome_completo
            colaborador_setor = colaborador.setor.nome if colaborador.setor else '-'
        except Colaborador.DoesNotExist:
            colaborador_nome = None
            colaborador_setor = '-'
        
        usuarios_data.append({
            'user': user,
            'colaborador_nome': colaborador_nome,
            'colaborador_setor': colaborador_setor,
            'permissoes': user_perms_set,
            'is_superuser': user.is_superuser,
            'is_staff': user.is_staff,
        })
    
    context = {
        'usuarios': usuarios_data,
        'permissoes_rh': permissoes_rh,
        'total_usuarios': len(usuarios_data),
    }
    
    return render(request, 'rh/gerenciar_permissoes.html', context)


@login_required
@require_http_methods(["POST"])
def api_atualizar_permissao(request):
    """
    API para atualizar uma permissão específica de um usuário.
    Recebe: user_id, codename, acao ('add' ou 'remove'), app_label (opcional, padrão 'rh')
    """
    if not request.user.is_superuser and not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Sem permissão'}, status=403)
    
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        codename = data.get('codename')
        acao = data.get('acao')  # 'add' ou 'remove'
        app_label = data.get('app_label', 'rh')  # Suporte a múltiplos apps
        
        logger.info(f'API atualizar_permissao - user_id: {user_id}, codename: {codename}, acao: {acao}, app_label: {app_label}')
        
        if not all([user_id, codename, acao]):
            return JsonResponse({'success': False, 'error': 'Dados incompletos'}, status=400)
        
        user = User.objects.get(id=user_id)
        
        # Buscar a permissão
        try:
            permission = Permission.objects.get(codename=codename, content_type__app_label=app_label)
        except Permission.DoesNotExist:
            logger.error(f'Permissão não encontrada: codename={codename}, app_label={app_label}')
            return JsonResponse({
                'success': False, 
                'error': f'Permissão "{codename}" não encontrada no app "{app_label}"'
            }, status=404)
        
        if acao == 'add':
            user.user_permissions.add(permission)
            msg = f'Permissão "{permission.name}" adicionada'
            logger.info(f'{request.user.username} adicionou permissão {codename} para {user.username}')
        elif acao == 'remove':
            user.user_permissions.remove(permission)
            msg = f'Permissão "{permission.name}" removida'
            logger.info(f'{request.user.username} removeu permissão {codename} de {user.username}')
        else:
            return JsonResponse({'success': False, 'error': 'Ação inválida'}, status=400)
        
        return JsonResponse({'success': True, 'message': msg})
    
    except User.DoesNotExist:
        logger.error(f'Usuário não encontrado: id={user_id}')
        return JsonResponse({'success': False, 'error': 'Usuário não encontrado'}, status=404)
    except json.JSONDecodeError as e:
        logger.error(f'Erro ao decodificar JSON: {str(e)}')
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    except Exception as e:
        logger.error(f'Erro ao atualizar permissão: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def api_atualizar_permissoes_lote(request):
    """
    API para atualizar múltiplas permissões de um usuário de uma vez.
    Recebe: user_id, permissoes (lista de codenames a adicionar)
    """
    if not request.user.is_superuser and not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Sem permissão'}, status=403)
    
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        permissoes = data.get('permissoes', [])  # Lista de codenames
        
        if not user_id:
            return JsonResponse({'success': False, 'error': 'user_id é obrigatório'}, status=400)
        
        user = User.objects.get(id=user_id)
        
        # Remover todas as permissões RH atuais
        perms_rh = Permission.objects.filter(content_type__app_label='rh')
        user.user_permissions.remove(*perms_rh)
        
        # Adicionar as permissões selecionadas
        if permissoes:
            perms_to_add = Permission.objects.filter(
                codename__in=permissoes,
                content_type__app_label='rh'
            )
            user.user_permissions.add(*perms_to_add)
        
        logger.info(f'{request.user.username} atualizou permissões de {user.username}: {permissoes}')
        return JsonResponse({
            'success': True,
            'message': f'Permissões de {user.username} atualizadas com sucesso.'
        })
    
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Usuário não encontrado'}, status=404)
    except Exception as e:
        logger.error(f'Erro ao atualizar permissões em lote: {str(e)}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def api_toggle_staff(request):
    """
    API para alternar o status de staff de um usuário.
    """
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Apenas superusuários podem alterar status de staff'}, status=403)
    
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        if not user_id:
            return JsonResponse({'success': False, 'error': 'user_id é obrigatório'}, status=400)
        
        user = User.objects.get(id=user_id)
        
        # Não permitir alterar o próprio status
        if user.id == request.user.id:
            return JsonResponse({'success': False, 'error': 'Você não pode alterar seu próprio status'}, status=400)
        
        user.is_staff = not user.is_staff
        user.save()
        
        status_str = 'Staff' if user.is_staff else 'Usuário comum'
        logger.info(f'{request.user.username} alterou {user.username} para {status_str}')
        
        return JsonResponse({
            'success': True,
            'is_staff': user.is_staff,
            'message': f'{user.username} agora é {status_str}'
        })
    
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Usuário não encontrado'}, status=404)
    except Exception as e:
        logger.error(f'Erro ao alternar staff: {str(e)}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def api_toggle_superuser(request):
    """
    API para alternar o status de superusuário de um usuário.
    """
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Apenas superusuários podem alterar status de superusuário'}, status=403)
    
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        if not user_id:
            return JsonResponse({'success': False, 'error': 'user_id é obrigatório'}, status=400)
        
        user = User.objects.get(id=user_id)
        
        # Não permitir alterar o próprio status
        if user.id == request.user.id:
            return JsonResponse({'success': False, 'error': 'Você não pode alterar seu próprio status de superusuário'}, status=400)
        
        user.is_superuser = not user.is_superuser
        user.save()
        
        status_str = 'Superusuário' if user.is_superuser else 'Usuário comum'
        logger.info(f'{request.user.username} alterou {user.username} para {status_str}')
        
        return JsonResponse({
            'success': True,
            'is_superuser': user.is_superuser,
            'message': f'{user.username} agora é {status_str}'
        })
    
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Usuário não encontrado'}, status=404)
    except Exception as e:
        logger.error(f'Erro ao alternar superusuário: {str(e)}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ==============================================================================
# SEÇÃO USUÁRIOS - GESTÃO DE USUÁRIOS E PERMISSÕES
# ==============================================================================

@login_required
def listar_usuarios_view(request):
    """
    View para listar todos os usuários do sistema.
    Acessível apenas por superusuários ou staff.
    """
    if not request.user.is_superuser and not request.user.is_staff:
        messages.error(request, 'Você não tem permissão para acessar esta página.')
        return redirect('home')
    
    # Buscar todos os usuários ativos
    usuarios = User.objects.filter(is_active=True).select_related().order_by('username')
    
    # Montar dados dos usuários
    usuarios_data = []
    for user in usuarios:
        # Verificar se tem o colaborador vinculado
        try:
            colaborador = Colaborador.objects.get(user_django=user)
            colaborador_nome = colaborador.nome_completo
            colaborador_setor = colaborador.setor.nome if colaborador.setor else '-'
            colaborador_cargo = colaborador.cargo or '-'
        except Colaborador.DoesNotExist:
            colaborador_nome = None
            colaborador_setor = '-'
            colaborador_cargo = '-'
        
        # Contar permissões
        perms_count = user.user_permissions.filter(content_type__app_label='rh').count()
        
        usuarios_data.append({
            'user': user,
            'colaborador_nome': colaborador_nome,
            'colaborador_setor': colaborador_setor,
            'colaborador_cargo': colaborador_cargo,
            'perms_count': perms_count,
            'is_superuser': user.is_superuser,
            'is_staff': user.is_staff,
        })
    
    context = {
        'usuarios': usuarios_data,
        'total_usuarios': len(usuarios_data),
    }
    
    return render(request, 'rh/usuarios_lista.html', context)


@login_required
def detalhe_usuario_view(request, user_id):
    """
    View para exibir detalhes e permissões de um usuário específico.
    """
    if not request.user.is_superuser and not request.user.is_staff:
        messages.error(request, 'Você não tem permissão para acessar esta página.')
        return redirect('home')
    
    user = get_object_or_404(User, id=user_id)
    
    # Buscar colaborador vinculado
    try:
        colaborador = Colaborador.objects.get(user_django=user)
    except Colaborador.DoesNotExist:
        colaborador = None
    
    # Permissões do usuário - separar por app
    user_perms_rh = set(user.user_permissions.filter(content_type__app_label='rh').values_list('codename', flat=True))
    user_perms_qms = set(user.user_permissions.filter(content_type__app_label='qms').values_list('codename', flat=True))
    user_perms_procedures = set(user.user_permissions.filter(content_type__app_label='procedures').values_list('codename', flat=True))
    user_perms_fornecedores = set(user.user_permissions.filter(content_type__app_label='fornecedores').values_list('codename', flat=True))
    
    # Definir módulos com seus grupos de permissões
    modulos = [
        {
            'nome': 'Metrologia',
            'cor': 'success',
            'icone': 'bi-rulers',
            'app_label': 'qms',
            'grupos': [
                {
                    'nome': 'Instrumento',
                    'icone': 'bi-tools',
                    'permissoes': [
                        ('view_instrumento', 'Visualizar'),
                        ('add_instrumento', 'Adicionar'),
                        ('change_instrumento', 'Editar'),
                        ('delete_instrumento', 'Excluir'),
                    ]
                },
                {
                    'nome': 'Calibração',
                    'icone': 'bi-speedometer2',
                    'permissoes': [
                        ('view_calibracao', 'Visualizar'),
                        ('add_calibracao', 'Adicionar'),
                        ('change_calibracao', 'Editar'),
                        ('delete_calibracao', 'Excluir'),
                    ]
                },
                {
                    'nome': 'Certificado',
                    'icone': 'bi-award',
                    'permissoes': [
                        ('view_certificado', 'Visualizar'),
                        ('add_certificado', 'Adicionar'),
                        ('change_certificado', 'Editar'),
                        ('delete_certificado', 'Excluir'),
                    ]
                },
            ]
        },
        {
            'nome': 'Procedimentos',
            'cor': 'info',
            'icone': 'bi-file-earmark-text',
            'app_label': 'procedures',
            'grupos': [
                {
                    'nome': 'Procedimento',
                    'icone': 'bi-file-earmark-ruled',
                    'permissoes': [
                        ('view_procedimento', 'Visualizar'),
                        ('add_procedimento', 'Adicionar'),
                        ('change_procedimento', 'Editar'),
                        ('delete_procedimento', 'Excluir'),
                    ]
                },
                {
                    'nome': 'Revisão',
                    'icone': 'bi-clock-history',
                    'permissoes': [
                        ('view_procedimentorevisao', 'Visualizar'),
                        ('add_procedimentorevisao', 'Adicionar'),
                        ('change_procedimentorevisao', 'Editar'),
                        ('delete_procedimentorevisao', 'Excluir'),
                    ]
                },
                {
                    'nome': 'Disciplina',
                    'icone': 'bi-book',
                    'permissoes': [
                        ('view_disciplina', 'Visualizar'),
                        ('add_disciplina', 'Adicionar'),
                        ('change_disciplina', 'Editar'),
                        ('delete_disciplina', 'Excluir'),
                    ]
                },
            ]
        },
        {
            'nome': 'Treinamentos',
            'cor': 'warning',
            'icone': 'bi-mortarboard-fill',
            'app_label': 'procedures',
            'grupos': [
                {
                    'nome': 'Planejamento',
                    'icone': 'bi-calendar-event',
                    'permissoes': [
                        ('view_planejamentotreinamento', 'Visualizar'),
                        ('add_planejamentotreinamento', 'Adicionar'),
                        ('change_planejamentotreinamento', 'Editar'),
                        ('delete_planejamentotreinamento', 'Excluir'),
                    ]
                },
                {
                    'nome': 'Registro',
                    'icone': 'bi-journal-check',
                    'permissoes': [
                        ('view_registrotreinamento', 'Visualizar'),
                        ('add_registrotreinamento', 'Adicionar'),
                        ('change_registrotreinamento', 'Editar'),
                        ('delete_registrotreinamento', 'Excluir'),
                    ]
                },
                {
                    'nome': 'Lista de Presença',
                    'icone': 'bi-list-check',
                    'permissoes': [
                        ('view_listapresenca', 'Visualizar'),
                        ('add_listapresenca', 'Adicionar'),
                        ('change_listapresenca', 'Editar'),
                        ('delete_listapresenca', 'Excluir'),
                    ]
                },
                {
                    'nome': 'Matriz de Habilidades',
                    'icone': 'bi-grid-3x3',
                    'permissoes': [
                        ('view_matrizhabilidade', 'Visualizar'),
                        ('add_matrizhabilidade', 'Adicionar'),
                        ('change_matrizhabilidade', 'Editar'),
                        ('delete_matrizhabilidade', 'Excluir'),
                    ]
                },
            ]
        },
        {
            'nome': 'Avaliação de Colaboradores',
            'cor': 'danger',
            'icone': 'bi-clipboard-check',
            'app_label': 'procedures',
            'grupos': [
                {
                    'nome': 'Avaliação de Habilidade',
                    'icone': 'bi-star-fill',
                    'permissoes': [
                        ('view_avaliacaohabilidade', 'Visualizar'),
                        ('add_avaliacaohabilidade', 'Adicionar'),
                        ('change_avaliacaohabilidade', 'Editar'),
                        ('delete_avaliacaohabilidade', 'Excluir'),
                    ]
                },
                {
                    'nome': 'Histórico de Avaliação',
                    'icone': 'bi-clock-history',
                    'permissoes': [
                        ('view_historicoavaliacaohabilidade', 'Visualizar'),
                        ('add_historicoavaliacaohabilidade', 'Adicionar'),
                        ('change_historicoavaliacaohabilidade', 'Editar'),
                        ('delete_historicoavaliacaohabilidade', 'Excluir'),
                    ]
                },
                {
                    'nome': 'Validação de Matriz',
                    'icone': 'bi-check-circle',
                    'permissoes': [
                        ('view_solicitacaovalidacaomatriz', 'Visualizar'),
                        ('add_solicitacaovalidacaomatriz', 'Adicionar'),
                        ('change_solicitacaovalidacaomatriz', 'Editar'),
                        ('delete_solicitacaovalidacaomatriz', 'Excluir'),
                    ]
                },
            ]
        },
        {
            'nome': 'RH',
            'cor': 'primary',
            'icone': 'bi-people-fill',
            'app_label': 'rh',
            'grupos': [
                {
                    'nome': 'Colaborador',
                    'icone': 'bi-person',
                    'permissoes': [
                        ('view_colaborador', 'Visualizar'),
                        ('add_colaborador', 'Adicionar'),
                        ('change_colaborador', 'Editar'),
                        ('delete_colaborador', 'Excluir'),
                    ]
                },
                {
                    'nome': 'Documento Pessoal',
                    'icone': 'bi-file-earmark-text',
                    'permissoes': [
                        ('view_documentopessoal', 'Visualizar'),
                        ('add_documentopessoal', 'Adicionar'),
                        ('change_documentopessoal', 'Editar'),
                        ('delete_documentopessoal', 'Excluir'),
                    ]
                },
                {
                    'nome': 'Férias',
                    'icone': 'bi-calendar-check',
                    'permissoes': [
                        ('view_ferias', 'Visualizar'),
                        ('add_ferias', 'Adicionar'),
                        ('change_ferias', 'Editar'),
                        ('delete_ferias', 'Excluir'),
                    ]
                },
                {
                    'nome': 'Ocorrência',
                    'icone': 'bi-exclamation-triangle',
                    'permissoes': [
                        ('view_ocorrencia', 'Visualizar'),
                        ('add_ocorrencia', 'Adicionar'),
                        ('change_ocorrencia', 'Editar'),
                        ('delete_ocorrencia', 'Excluir'),
                    ]
                },
            ]
        },
        {
            'nome': 'Fornecedores',
            'cor': 'secondary',
            'icone': 'bi-truck',
            'app_label': 'fornecedores',
            'grupos': [
                {
                    'nome': 'Fornecedor',
                    'icone': 'bi-building',
                    'permissoes': [
                        ('view_fornecedor', 'Visualizar'),
                        ('add_fornecedor', 'Adicionar'),
                        ('change_fornecedor', 'Editar'),
                        ('delete_fornecedor', 'Excluir'),
                    ]
                },
                {
                    'nome': 'Avaliação',
                    'icone': 'bi-star',
                    'permissoes': [
                        ('view_avaliacaofornecedor', 'Visualizar'),
                        ('add_avaliacaofornecedor', 'Adicionar'),
                        ('change_avaliacaofornecedor', 'Editar'),
                        ('delete_avaliacaofornecedor', 'Excluir'),
                    ]
                },
                {
                    'nome': 'Documento',
                    'icone': 'bi-file-earmark',
                    'permissoes': [
                        ('view_documentofornecedor', 'Visualizar'),
                        ('add_documentofornecedor', 'Adicionar'),
                        ('change_documentofornecedor', 'Editar'),
                        ('delete_documentofornecedor', 'Excluir'),
                    ]
                },
            ]
        },
    ]
    
    # Combinar todas as permissões do usuário
    all_user_perms = user_perms_rh | user_perms_qms | user_perms_procedures | user_perms_fornecedores
    
    context = {
        'usuario': user,
        'colaborador': colaborador,
        'user_perms': all_user_perms,
        'modulos': modulos,
    }
    
    return render(request, 'rh/usuario_detalhe.html', context)


@login_required
@require_http_methods(["POST"])
def api_toggle_user_active(request):
    """
    API para ativar/desativar (bloquear) um usuário.
    """
    if not request.user.is_superuser and not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Permissão negada'}, status=403)
    
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        if not user_id:
            return JsonResponse({'success': False, 'error': 'user_id é obrigatório'}, status=400)
        
        user = User.objects.get(id=user_id)
        
        # Não permitir desativar o próprio usuário
        if user.id == request.user.id:
            return JsonResponse({'success': False, 'error': 'Você não pode desativar sua própria conta'}, status=400)
        
        user.is_active = not user.is_active
        user.save()
        
        status_str = 'ativado' if user.is_active else 'bloqueado'
        logger.info(f'{request.user.username} {status_str} o usuário {user.username}')
        
        return JsonResponse({
            'success': True,
            'is_active': user.is_active,
            'message': f'Usuário {user.username} foi {status_str}'
        })
    
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Usuário não encontrado'}, status=404)
    except Exception as e:
        logger.error(f'Erro ao alternar status de usuário: {str(e)}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def api_reset_password(request):
    """
    API para resetar a senha de um usuário para uma senha temporária.
    """
    if not request.user.is_superuser and not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Permissão negada'}, status=403)
    
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        if not user_id:
            return JsonResponse({'success': False, 'error': 'user_id é obrigatório'}, status=400)
        
        user = User.objects.get(id=user_id)
        
        # Gerar senha temporária
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))
        
        user.set_password(temp_password)
        user.save()
        
        logger.info(f'{request.user.username} resetou a senha do usuário {user.username}')
        
        return JsonResponse({
            'success': True,
            'temp_password': temp_password,
            'message': f'Senha de {user.username} foi resetada'
        })
    
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Usuário não encontrado'}, status=404)
    except Exception as e:
        logger.error(f'Erro ao resetar senha: {str(e)}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def api_vincular_colaborador(request):
    """
    API para vincular um colaborador a um usuário Django.
    Permite transferir vínculo de outro usuário.
    """
    if not request.user.is_superuser and not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Permissão negada'}, status=403)
    
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        colaborador_id = data.get('colaborador_id')
        
        if not user_id:
            return JsonResponse({'success': False, 'error': 'user_id é obrigatório'}, status=400)
        
        user = User.objects.get(id=user_id)
        
        # Se colaborador_id é null/None, desvincular
        if not colaborador_id:
            # Desvincular colaborador atual se existir
            Colaborador.objects.filter(user_django=user).update(user_django=None)
            logger.info(f'{request.user.username} desvinculou colaborador do usuário {user.username}')
            return JsonResponse({
                'success': True,
                'message': f'Colaborador desvinculado de {user.username}'
            })
        
        colaborador = Colaborador.objects.get(id=colaborador_id)
        
        # Guardar usuário anterior para log (se houver)
        usuario_anterior = colaborador.user_django.username if colaborador.user_django else None
        
        # Desvincular colaborador anterior do usuário (se houver)
        Colaborador.objects.filter(user_django=user).update(user_django=None)
        
        # Vincular novo colaborador (transferindo de outro usuário se necessário)
        colaborador.user_django = user
        colaborador.save()
        
        if usuario_anterior and usuario_anterior != user.username:
            logger.info(f'{request.user.username} transferiu {colaborador.nome_completo} de {usuario_anterior} para {user.username}')
            message = f'{colaborador.nome_completo} transferido de {usuario_anterior} para {user.username}'
        else:
            logger.info(f'{request.user.username} vinculou {colaborador.nome_completo} ao usuário {user.username}')
            message = f'{colaborador.nome_completo} vinculado a {user.username}'
        
        return JsonResponse({
            'success': True,
            'colaborador_nome': colaborador.nome_completo,
            'colaborador_setor': colaborador.setor.nome if colaborador.setor else '-',
            'message': message
        })
    
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Usuário não encontrado'}, status=404)
    except Colaborador.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Colaborador não encontrado'}, status=404)
    except Exception as e:
        logger.error(f'Erro ao vincular colaborador: {str(e)}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def api_colaboradores_sem_vinculo(request):
    """
    API para listar colaboradores para vinculação.
    Retorna todos colaboradores ativos, marcando os que já têm vínculo.
    """
    if not request.user.is_superuser and not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Permissão negada'}, status=403)
    
    try:
        user_id = request.GET.get('user_id')
        search = request.GET.get('search', '').strip()
        
        # Buscar TODOS os colaboradores ativos
        colaboradores = Colaborador.objects.filter(
            is_active=True
        ).select_related('setor', 'user_django').order_by('nome_completo')
        
        # Filtrar por busca se fornecido
        if search:
            colaboradores = colaboradores.filter(nome_completo__icontains=search)
        
        data = []
        for colab in colaboradores:
            # Verificar se está vinculado ao usuário atual
            is_vinculado_usuario_atual = colab.user_django_id == int(user_id) if user_id and colab.user_django_id else False
            # Verificar se está vinculado a outro usuário
            vinculado_outro = colab.user_django_id and not is_vinculado_usuario_atual
            
            data.append({
                'id': colab.id,
                'nome': colab.nome_completo,
                'setor': colab.setor.nome if colab.setor else '-',
                'cargo': colab.cargo or '-',
                'vinculado': is_vinculado_usuario_atual,
                'vinculado_outro': vinculado_outro,
                'usuario_vinculado': colab.user_django.username if colab.user_django else None
            })
        
        return JsonResponse({'success': True, 'colaboradores': data})
    
    except Exception as e:
        logger.error(f'Erro ao listar colaboradores: {str(e)}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def api_criar_usuario(request):
    """
    API para criar um novo usuário no sistema.
    Gera uma senha temporária aleatória.
    """
    if not request.user.is_superuser and not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Permissão negada'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método não permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        is_staff = data.get('is_staff', False)
        colaborador_id = data.get('colaborador_id')
        
        # Validações
        if not username:
            return JsonResponse({'success': False, 'error': 'Nome de usuário é obrigatório'})
        
        if len(username) < 3:
            return JsonResponse({'success': False, 'error': 'Nome de usuário deve ter pelo menos 3 caracteres'})
        
        # Verificar se usuário já existe
        if User.objects.filter(username__iexact=username).exists():
            return JsonResponse({'success': False, 'error': 'Este nome de usuário já está em uso'})
        
        # Verificar email duplicado (se fornecido)
        if email and User.objects.filter(email__iexact=email).exists():
            return JsonResponse({'success': False, 'error': 'Este e-mail já está em uso'})
        
        # Gerar senha temporária segura
        temp_password = secrets.token_urlsafe(12)
        
        # Criar o usuário
        user = User.objects.create_user(
            username=username,
            email=email or None,
            password=temp_password,
            first_name=first_name,
            last_name=last_name,
            is_staff=is_staff,
            is_active=True
        )
        
        # Vincular colaborador se fornecido
        colaborador_nome = None
        if colaborador_id:
            try:
                colaborador = Colaborador.objects.get(id=colaborador_id, user_django__isnull=True)
                colaborador.user_django = user
                colaborador.save()
                colaborador_nome = colaborador.nome_completo
            except Colaborador.DoesNotExist:
                pass  # Ignorar se colaborador não existe ou já está vinculado
        
        logger.info(f'Novo usuário criado: {username} por {request.user.username}')
        
        return JsonResponse({
            'success': True,
            'message': f'Usuário {username} criado com sucesso!',
            'user_id': user.id,
            'temp_password': temp_password,
            'colaborador_nome': colaborador_nome
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Dados inválidos'}, status=400)
    except Exception as e:
        logger.error(f'Erro ao criar usuário: {str(e)}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def criar_usuario_view(request):
    """
    View para criar um novo usuário no sistema com formulário dedicado.
    O admin define username e senha.
    """
    if not request.user.is_superuser and not request.user.is_staff:
        messages.error(request, 'Você não tem permissão para acessar esta página.')
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        password_confirm = request.POST.get('password_confirm', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        is_staff = request.POST.get('is_staff') == 'on'
        colaborador_id = request.POST.get('colaborador_id')
        
        errors = []
        
        # Validações
        if not username:
            errors.append('Nome de usuário é obrigatório.')
        elif len(username) < 3:
            errors.append('Nome de usuário deve ter pelo menos 3 caracteres.')
        elif ' ' in username:
            errors.append('Nome de usuário não pode conter espaços.')
        elif User.objects.filter(username__iexact=username).exists():
            errors.append('Este nome de usuário já está em uso.')
        
        if not password:
            errors.append('Senha é obrigatória.')
        elif len(password) < 6:
            errors.append('Senha deve ter pelo menos 6 caracteres.')
        elif password != password_confirm:
            errors.append('As senhas não conferem.')
        
        if email and User.objects.filter(email__iexact=email).exists():
            errors.append('Este e-mail já está em uso.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'rh/usuario_criar.html', {
                'form_data': {
                    'username': username,
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'is_staff': is_staff,
                    'colaborador_id': colaborador_id,
                },
                'colaboradores': Colaborador.objects.filter(user_django__isnull=True, is_active=True).select_related('setor').order_by('nome_completo')
            })
        
        # Criar o usuário
        user = User.objects.create_user(
            username=username,
            email=email or None,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_staff=is_staff,
            is_active=True
        )
        
        # Vincular colaborador se fornecido
        if colaborador_id:
            try:
                colaborador = Colaborador.objects.get(id=colaborador_id, user_django__isnull=True)
                colaborador.user_django = user
                colaborador.save()
            except Colaborador.DoesNotExist:
                pass
        
        logger.info(f'Novo usuário criado: {username} por {request.user.username}')
        messages.success(request, f'Usuário "{username}" criado com sucesso!')
        return redirect('rh:detalhe_usuario', user_id=user.id)
    
    # GET - exibir formulário
    colaboradores = Colaborador.objects.filter(
        user_django__isnull=True, 
        is_active=True
    ).select_related('setor').order_by('nome_completo')
    
    return render(request, 'rh/usuario_criar.html', {
        'colaboradores': colaboradores
    })

