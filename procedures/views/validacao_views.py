from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse

from procedures.models import (
    MatrizHabilidade,
    SolicitacaoValidacaoMatriz,
    HistoricoValidacaoMassa,
    AvaliacaoHabilidade,
    HistoricoAvaliacaoHabilidade,
    ColaboradorMatrizHabilidade
)
from rh.models import Colaborador


@login_required
def solicitar_validacao_view(request, matriz_id):
    """
    Solicita validação de uma matriz para um usuário específico
    """
    matriz = get_object_or_404(MatrizHabilidade, id=matriz_id)
    
    if request.method == 'POST':
        validador_id = request.POST.get('validador_id')
        motivo = request.POST.get('motivo', '')
        
        if not validador_id:
            messages.error(request, 'Por favor, selecione um validador!')
            return redirect('procedures:matriz_avaliacoes')
        
        try:
            validador = get_object_or_404(Colaborador, id=validador_id)
            
            # Criar solicitação
            solicitacao = SolicitacaoValidacaoMatriz.objects.create(
                matriz=matriz,
                solicitante=request.user.colaborador if hasattr(request.user, 'colaborador') else None,
                validador=validador,
                motivo_solicitacao=motivo,
                status='pendente'
            )
            
            messages.success(request, f'Solicitação de validação enviada para {validador.nome_completo}!')
            return redirect('procedures:matriz_avaliacoes')
        
        except Exception as e:
            messages.error(request, f'Erro ao solicitar validação: {str(e)}')
            return redirect('procedures:matriz_avaliacoes')
    
    # GET - Mostrar formulário
    # Buscar possíveis validadores (líderes/supervisores)
    validadores = Colaborador.objects.filter(
        is_active=True
    ).order_by('nome_completo')
    
    context = {
        'matriz': matriz,
        'validadores': validadores,
    }
    
    return render(request, 'procedures/solicitar_validacao.html', context)


@login_required
def validacoes_pendentes_view(request):
    """
    Mostra validações pendentes para o usuário atual
    """
    # Superuser pode acessar mesmo sem perfil de colaborador.
    # Nesse caso, deve enxergar todas as pendências (não apenas as sem validador).
    if request.user.is_superuser:
        validacoes = SolicitacaoValidacaoMatriz.objects.filter(
            status='pendente'
        ).select_related('matriz', 'solicitante', 'validador').order_by('-criado_em')
    else:
        try:
            colaborador = request.user.colaborador
        except Exception:
            messages.error(request, 'Usuário não tem perfil de colaborador!')
            return redirect('home')

        validacoes = SolicitacaoValidacaoMatriz.objects.filter(
            validador=colaborador,
            status='pendente'
        ).select_related('matriz', 'solicitante', 'validador').order_by('-criado_em')
    
    context = {
        'validacoes': validacoes,
    }
    
    return render(request, 'procedures/validacoes_pendentes.html', context)


@login_required
def validar_matriz_view(request, solicitacao_id):
    """
    Valida uma matriz específica em massa
    """
    solicitacao = get_object_or_404(SolicitacaoValidacaoMatriz, id=solicitacao_id)
    matriz = solicitacao.matriz
    
    # Verificar permissão (superusers pode validar qualquer coisa)
    if not request.user.is_superuser:
        try:
            if request.user.colaborador != solicitacao.validador:
                messages.error(request, 'Você não tem permissão para validar esta matriz!')
                return redirect('procedures:validacoes_pendentes')
        except Colaborador.DoesNotExist:
            messages.error(request, 'Usuário não tem perfil de colaborador!')
            return redirect('home')
    
    if request.method == 'POST':
        acao = request.POST.get('acao')
        motivo = request.POST.get('motivo', '')
        
        try:
            if acao == 'validar':
                # Marcar solicitação como validada
                solicitacao.status = 'validada'
                solicitacao.validado_em = timezone.now()
                solicitacao.save()
                
                # Criar histórico de validação em massa
                avaliacoes = AvaliacaoHabilidade.objects.filter(matriz=matriz)
                total = avaliacoes.count()
                
                HistoricoValidacaoMassa.objects.create(
                    matriz=matriz,
                    validador=request.user.colaborador,
                    total_avaliacoes=total,
                    avaliacoes_atualizadas=total,
                    motivo=motivo
                )
                
                messages.success(request, f'Matriz {matriz.nome} validada com sucesso!')
                return redirect('procedures:validacoes_pendentes')
            
            elif acao == 'rejeitar':
                # Marcar solicitação como rejeitada
                solicitacao.status = 'rejeitada'
                solicitacao.motivo_rejeicao = motivo
                solicitacao.validado_em = timezone.now()
                solicitacao.save()
                
                messages.warning(request, f'Matriz {matriz.nome} rejeitada.')
                return redirect('procedures:validacoes_pendentes')
        
        except Exception as e:
            messages.error(request, f'Erro ao processar validação: {str(e)}')
    
    # GET - Mostrar tela de revisão
    avaliacoes = AvaliacaoHabilidade.objects.filter(matriz=matriz).select_related(
        'colaborador', 'disciplina', 'avaliador'
    ).order_by('colaborador__nome_completo', 'disciplina__codigo')
    
    # Agrupar por colaborador
    colaboradores_map = {}
    for av in avaliacoes:
        if av.colaborador.id not in colaboradores_map:
            colaboradores_map[av.colaborador.id] = {
                'colaborador': av.colaborador,
                'avaliacoes': []
            }
        colaboradores_map[av.colaborador.id]['avaliacoes'].append(av)
    
    colaboradores_data = list(colaboradores_map.values())
    
    context = {
        'solicitacao': solicitacao,
        'matriz': matriz,
        'colaboradores_data': colaboradores_data,
        'total_avaliacoes': avaliacoes.count(),
    }
    
    return render(request, 'procedures/validar_matriz.html', context)


@login_required
def validacao_rapida_view(request, matriz_id):
    """
    Validação rápida em massa sem solicitação prévia (para quando há poucas mudanças)
    """
    matriz = get_object_or_404(MatrizHabilidade, id=matriz_id)
    
    # Permitir superusers mesmo sem perfil de colaborador
    if not request.user.is_superuser:
        try:
            validador = request.user.colaborador
        except Colaborador.DoesNotExist:
            messages.error(request, 'Usuário não tem perfil de colaborador!')
            return redirect('home')
    else:
        validador = None
    
    if request.method == 'POST':
        motivo = request.POST.get('motivo', 'Validação rápida')
        
        try:
            # Buscar todas as avaliações da matriz
            avaliacoes = AvaliacaoHabilidade.objects.filter(matriz=matriz)
            total = avaliacoes.count()
            
            # Criar histórico de validação em massa
            HistoricoValidacaoMassa.objects.create(
                matriz=matriz,
                validador=validador,
                total_avaliacoes=total,
                avaliacoes_atualizadas=total,
                motivo=motivo
            )
            
            messages.success(request, f'Matriz {matriz.nome} validada rapidamente! {total} avaliações registradas.')
            return redirect('procedures:matriz_avaliacoes')
        
        except Exception as e:
            messages.error(request, f'Erro ao validar: {str(e)}')
            return redirect('procedures:matriz_avaliacoes')
    
    # GET - Mostrar confirmação
    avaliacoes_count = AvaliacaoHabilidade.objects.filter(matriz=matriz).count()
    
    context = {
        'matriz': matriz,
        'total_avaliacoes': avaliacoes_count,
    }
    
    return render(request, 'procedures/validacao_rapida.html', context)
