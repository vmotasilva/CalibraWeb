from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Avg, Case, When, IntegerField
from collections import defaultdict

from procedures.models import (
    ColaboradorPerfil,
    PerfilTreinamento,
    MatrizHabilidade,
    AvaliacaoHabilidade,
    Disciplina,
    GrupoTreinamento,
    SubGrupoTreinamento,
    RegistroTreinamento,
    Procedimento
)
from rh.models import Colaborador


# ==================== GAP ANALYSIS ====================

@login_required
def dashboard_gaps_view(request):
    """
    Dashboard principal de análise de gaps
    Mostra lacunas entre perfis requeridos e competências avaliadas
    """
    # Filtros
    setor = request.GET.get('setor', '')
    perfil_id = request.GET.get('perfil', '')
    colaborador_id = request.GET.get('colaborador', '')
    
    # Buscar colaboradores com perfis atribuídos
    colaboradores_perfis = ColaboradorPerfil.objects.filter(
        ativo=True
    ).select_related('colaborador', 'perfil')
    
    if setor:
        colaboradores_perfis = colaboradores_perfis.filter(colaborador__setor=setor)
    
    if perfil_id:
        colaboradores_perfis = colaboradores_perfis.filter(perfil_id=perfil_id)
    
    if colaborador_id:
        colaboradores_perfis = colaboradores_perfis.filter(colaborador_id=colaborador_id)
    
    # Preparar dados de gaps
    gaps_data = []
    for cp in colaboradores_perfis:
        colaborador = cp.colaborador
        perfil = cp.perfil
        
        # Buscar procedimentos requeridos pelo perfil (via grupos e subgrupos)
        procedimentos_requeridos = Procedimento.objects.filter(
            subgrupotreinamento__grupo__perfil=perfil
        ).distinct()
        
        # Buscar procedimentos já treinados
        procedimentos_treinados = RegistroTreinamento.objects.filter(
            colaborador=colaborador
        ).values_list('procedimento_id', flat=True).distinct()
        
        # Identificar gaps de treinamento
        total_requerido = procedimentos_requeridos.count()
        total_treinado = procedimentos_requeridos.filter(
            id__in=procedimentos_treinados
        ).count()
        gap_treinamento = total_requerido - total_treinado
        percentual_completude = (total_treinado / total_requerido * 100) if total_requerido > 0 else 0
        
        # Buscar avaliações de habilidade
        avaliacoes = AvaliacaoHabilidade.objects.filter(
            colaborador=colaborador
        ).select_related('disciplina', 'matriz')
        
        total_avaliacoes = avaliacoes.count()
        nivel_medio = avaliacoes.aggregate(Avg('nivel'))['nivel__avg'] or 0
        
        # Contar por nível
        niveis_count = {
            'nivel_0': avaliacoes.filter(nivel=0).count(),
            'nivel_1': avaliacoes.filter(nivel=1).count(),
            'nivel_2': avaliacoes.filter(nivel=2).count(),
            'nivel_3': avaliacoes.filter(nivel=3).count(),
        }
        
        gaps_data.append({
            'colaborador': colaborador,
            'perfil': perfil,
            'total_requerido': total_requerido,
            'total_treinado': total_treinado,
            'gap_treinamento': gap_treinamento,
            'percentual_completude': round(percentual_completude, 1),
            'total_avaliacoes': total_avaliacoes,
            'nivel_medio': round(nivel_medio, 2),
            'niveis_count': niveis_count,
        })
    
    # Ordenar por maior gap
    gaps_data.sort(key=lambda x: x['gap_treinamento'], reverse=True)
    
    # Estatísticas gerais
    total_colaboradores = len(gaps_data)
    total_gaps = sum(g['gap_treinamento'] for g in gaps_data)
    avg_completude = sum(g['percentual_completude'] for g in gaps_data) / total_colaboradores if total_colaboradores > 0 else 0
    
    # Buscar dados para filtros
    setores = Colaborador.objects.filter(is_active=True).values_list('setor', flat=True).distinct().order_by('setor')
    setores = [s for s in setores if s]
    perfis = PerfilTreinamento.objects.filter(ativo=True).order_by('nome')
    colaboradores = Colaborador.objects.filter(
        is_active=True,
        colaboradorperfil__ativo=True
    ).distinct().order_by('nome')
    
    context = {
        'gaps_data': gaps_data,
        'total_colaboradores': total_colaboradores,
        'total_gaps': total_gaps,
        'avg_completude': round(avg_completude, 1),
        'setores': setores,
        'perfis': perfis,
        'colaboradores': colaboradores,
        'setor': setor,
        'perfil_id': perfil_id,
        'colaborador_id': colaborador_id,
    }
    
    return render(request, 'procedures/dashboard_gaps.html', context)


@login_required
def gap_detalhado_view(request, colaborador_id):
    """
    Análise detalhada de gaps para um colaborador específico
    Mostra disciplinas, procedimentos e recomendações
    """
    colaborador = get_object_or_404(Colaborador, id=colaborador_id)
    
    # Buscar perfil do colaborador
    colaborador_perfil = ColaboradorPerfil.objects.filter(
        colaborador=colaborador,
        ativo=True
    ).select_related('perfil').first()
    
    if not colaborador_perfil:
        context = {
            'colaborador': colaborador,
            'tem_perfil': False
        }
        return render(request, 'procedures/gap_detalhado.html', context)
    
    perfil = colaborador_perfil.perfil
    
    # 1. GAPS DE HABILIDADES (Disciplinas)
    # Buscar todas as matrizes ativas
    matrizes = MatrizHabilidade.objects.filter(ativo=True)
    
    gaps_habilidades = []
    for matriz in matrizes:
        disciplinas_matriz = matriz.disciplinas.filter(ativo=True)
        
        for disciplina in disciplinas_matriz:
            # Buscar avaliação do colaborador nesta disciplina
            avaliacao = AvaliacaoHabilidade.objects.filter(
                colaborador=colaborador,
                disciplina=disciplina,
                matriz=matriz
            ).first()
            
            nivel_atual = avaliacao.nivel if avaliacao else None
            
            # Considerar gap se não foi avaliado ou nível < 2
            if nivel_atual is None or nivel_atual < 2:
                gaps_habilidades.append({
                    'matriz': matriz,
                    'disciplina': disciplina,
                    'nivel_atual': nivel_atual,
                    'nivel_desejado': 2,  # Nível mínimo desejado
                    'gap': 2 - (nivel_atual if nivel_atual is not None else 0),
                    'avaliacao': avaliacao
                })
    
    # Ordenar por maior gap
    gaps_habilidades.sort(key=lambda x: x['gap'], reverse=True)
    
    # 2. GAPS DE TREINAMENTOS (Procedimentos)
    # Buscar procedimentos requeridos pelo perfil
    grupos = GrupoTreinamento.objects.filter(perfil=perfil).prefetch_related(
        'subgrupotreinamento_set__procedimentos'
    ).order_by('ordem')
    
    gaps_treinamentos = []
    for grupo in grupos:
        for subgrupo in grupo.subgrupotreinamento_set.all().order_by('ordem'):
            for procedimento in subgrupo.procedimentos.all():
                # Verificar se colaborador já foi treinado
                registro = RegistroTreinamento.objects.filter(
                    colaborador=colaborador,
                    procedimento=procedimento
                ).order_by('-data_treinamento').first()
                
                if not registro:
                    gaps_treinamentos.append({
                        'grupo': grupo,
                        'subgrupo': subgrupo,
                        'procedimento': procedimento,
                        'treinado': False,
                        'registro': None
                    })
                else:
                    # Incluir também os treinados para visualização completa
                    gaps_treinamentos.append({
                        'grupo': grupo,
                        'subgrupo': subgrupo,
                        'procedimento': procedimento,
                        'treinado': True,
                        'registro': registro
                    })
    
    # Estatísticas
    total_habilidades_gap = len([g for g in gaps_habilidades if g['nivel_atual'] is None or g['nivel_atual'] < 2])
    total_treinamentos_pendentes = len([g for g in gaps_treinamentos if not g['treinado']])
    total_treinamentos_ok = len([g for g in gaps_treinamentos if g['treinado']])
    
    context = {
        'colaborador': colaborador,
        'perfil': perfil,
        'tem_perfil': True,
        'gaps_habilidades': gaps_habilidades[:20],  # Top 20
        'gaps_treinamentos': gaps_treinamentos,
        'total_habilidades_gap': total_habilidades_gap,
        'total_treinamentos_pendentes': total_treinamentos_pendentes,
        'total_treinamentos_ok': total_treinamentos_ok,
    }
    
    return render(request, 'procedures/gap_detalhado.html', context)


@login_required
def gaps_por_perfil_view(request, perfil_id):
    """
    Análise de gaps agregada por perfil
    Mostra quais competências faltam mais no time com este perfil
    """
    perfil = get_object_or_404(PerfilTreinamento, id=perfil_id)
    
    # Buscar todos colaboradores com este perfil
    colaboradores = Colaborador.objects.filter(
        colaboradorperfil__perfil=perfil,
        colaboradorperfil__ativo=True,
        is_active=True
    ).distinct()
    
    # Procedimentos requeridos pelo perfil
    procedimentos_requeridos = Procedimento.objects.filter(
        subgrupotreinamento__grupo__perfil=perfil
    ).distinct().order_by('codigo')
    
    # Para cada procedimento, contar quantos colaboradores já foram treinados
    procedimentos_stats = []
    for proc in procedimentos_requeridos:
        treinados = RegistroTreinamento.objects.filter(
            procedimento=proc,
            colaborador__in=colaboradores
        ).values_list('colaborador_id', flat=True).distinct().count()
        
        pendentes = colaboradores.count() - treinados
        percentual = (treinados / colaboradores.count() * 100) if colaboradores.count() > 0 else 0
        
        procedimentos_stats.append({
            'procedimento': proc,
            'total_colaboradores': colaboradores.count(),
            'treinados': treinados,
            'pendentes': pendentes,
            'percentual': round(percentual, 1)
        })
    
    # Ordenar por maior número de pendentes
    procedimentos_stats.sort(key=lambda x: x['pendentes'], reverse=True)
    
    context = {
        'perfil': perfil,
        'colaboradores': colaboradores,
        'procedimentos_stats': procedimentos_stats,
        'total_colaboradores': colaboradores.count(),
    }
    
    return render(request, 'procedures/gaps_por_perfil.html', context)
