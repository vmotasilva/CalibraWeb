from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Prefetch
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json

from procedures.models import (
    MatrizHabilidade,
    AvaliacaoHabilidade,
    Disciplina,
    HistoricoAvaliacaoHabilidade
)
from procedures.forms.forms import AvaliacaoHabilidadeForm
from rh.models import Colaborador


# ==================== AVALIAÇÕES DE HABILIDADE ====================

@login_required
def matriz_avaliacoes_view(request):
    """
    Exibe uma matriz de avaliações: colaboradores x disciplinas
    com os níveis de competência (0-3)
    """
    # Filtros
    matriz_id = request.GET.get('matriz', '')
    setor = request.GET.get('setor', '')
    termo_colab = request.GET.get('colaborador', '').strip()
    
    # Buscar matrizes disponíveis
    matrizes = MatrizHabilidade.objects.filter(ativo=True).order_by('nome')
    
    # Selecionar matriz
    matriz_selecionada = None
    disciplinas = []
    colaboradores = []
    avaliacoes_dict = {}
    
    if matriz_id:
        matriz_selecionada = get_object_or_404(MatrizHabilidade, id=matriz_id)
        disciplinas = matriz_selecionada.disciplinas_matriz.filter(ativo=True).order_by('codigo')
        
        # Buscar APENAS colaboradores associados à matriz
        from procedures.models import ColaboradorMatrizHabilidade
        colaboradores_assoc = ColaboradorMatrizHabilidade.objects.filter(
            matriz=matriz_selecionada,
            ativo=True
        ).select_related('colaborador').order_by('colaborador__nome_completo')
        
        # Extrair lista de colaboradores
        colaboradores = [assoc.colaborador for assoc in colaboradores_assoc]
        
        if setor:
            colaboradores = [c for c in colaboradores if c.setor == setor]
        
        if termo_colab:
            colaboradores = [
                c for c in colaboradores 
                if termo_colab.lower() in c.nome_completo.lower() or 
                   termo_colab.lower() in (c.matricula or '').lower()
            ]
        
        colaboradores = colaboradores[:50]  # Limitar para performance
        
        # Buscar avaliações existentes
        avaliacoes = AvaliacaoHabilidade.objects.filter(
            matriz=matriz_selecionada,
            colaborador__in=colaboradores,
            disciplina__in=disciplinas
        ).select_related('colaborador', 'disciplina', 'avaliador')
        
        # Criar estrutura de dados para o template
        # Lista de listas: cada colaborador tem uma lista de células (uma por disciplina)
        matriz_dados = []
        for colaborador in colaboradores:
            linha = {
                'colaborador': colaborador,
                'avaliacoes': []
            }
            for disciplina in disciplinas:
                # Buscar avaliação específica
                avaliacao = next(
                    (av for av in avaliacoes if av.colaborador_id == colaborador.id and av.disciplina_id == disciplina.id),
                    None
                )
                linha['avaliacoes'].append({
                    'disciplina': disciplina,
                    'avaliacao': avaliacao
                })
            matriz_dados.append(linha)
    
    # Buscar setores disponíveis
    setores = Colaborador.objects.filter(is_active=True).values_list('setor', flat=True).distinct().order_by('setor')
    setores = [s for s in setores if s]
    
    context = {
        'matrizes': matrizes,
        'matriz_selecionada': matriz_selecionada,
        'disciplinas': disciplinas,
        'matriz_dados': matriz_dados if matriz_selecionada else [],
        'setores': setores,
        'matriz_id': matriz_id,
        'setor': setor,
        'termo_colab': termo_colab,
    }
    
    return render(request, 'procedures/matriz_avaliacao.html', context)


@login_required
def editar_avaliacao_view(request, matriz_id, colaborador_id, disciplina_id):
    """
    Edita ou cria uma avaliação individual
    """
    matriz = get_object_or_404(MatrizHabilidade, id=matriz_id)
    colaborador = get_object_or_404(Colaborador, id=colaborador_id)
    disciplina = get_object_or_404(Disciplina, id=disciplina_id)
    
    # Verificar se disciplina pertence à matriz
    if not matriz.disciplinas_matriz.filter(id=disciplina_id).exists():
        messages.error(request, 'Disciplina não pertence a esta matriz!')
        return redirect('procedures:matriz_avaliacoes')
    
    # Buscar avaliação existente
    avaliacao = AvaliacaoHabilidade.objects.filter(
        matriz=matriz,
        colaborador=colaborador,
        disciplina=disciplina
    ).first()
    
    if request.method == 'POST':
        try:
            # Extrair dados do POST
            nivel = request.POST.get('nivel')
            data_avaliacao = request.POST.get('data_avaliacao')
            observacoes = request.POST.get('observacoes', '')
            
            # Validações
            if not nivel:
                messages.error(request, 'Por favor, selecione um nível de competência!')
                return render(request, 'procedures/avaliacao_form.html', {
                    'matriz': matriz,
                    'colaborador': colaborador,
                    'disciplina': disciplina,
                    'avaliacao': avaliacao,
                    'today': timezone.now().date(),
                    'error': 'Nível é obrigatório'
                })
            
            if not data_avaliacao:
                messages.error(request, 'Por favor, informe a data da avaliação!')
                return render(request, 'procedures/avaliacao_form.html', {
                    'matriz': matriz,
                    'colaborador': colaborador,
                    'disciplina': disciplina,
                    'avaliacao': avaliacao,
                    'today': timezone.now().date(),
                    'error': 'Data é obrigatória'
                })
            
            # Converter nível para inteiro
            try:
                nivel = int(nivel)
            except ValueError:
                messages.error(request, 'Nível inválido!')
                return render(request, 'procedures/avaliacao_form.html', {
                    'matriz': matriz,
                    'colaborador': colaborador,
                    'disciplina': disciplina,
                    'avaliacao': avaliacao,
                    'today': timezone.now().date(),
                    'error': 'Nível inválido'
                })
            
            # Criar ou atualizar avaliação
            if avaliacao:
                # Guardar valores antigos para o histórico
                nivel_anterior = avaliacao.nivel
                data_anterior = avaliacao.data_avaliacao
                observacoes_anterior = avaliacao.observacoes
                
                # Atualizar avaliação
                avaliacao.nivel = nivel
                avaliacao.data_avaliacao = data_avaliacao
                avaliacao.observacoes = observacoes
                avaliacao.avaliador = request.user.colaborador if hasattr(request.user, 'colaborador') else None
                avaliacao.save()
                
                # Salvar no histórico
                from procedures.models import HistoricoAvaliacaoHabilidade
                HistoricoAvaliacaoHabilidade.objects.create(
                    avaliacao=avaliacao,
                    nivel_anterior=nivel_anterior,
                    nivel_novo=int(nivel),
                    avaliador=request.user.colaborador if hasattr(request.user, 'colaborador') else None,
                    data_avaliacao=data_anterior,
                    data_avaliacao_nova=data_avaliacao,
                    observacoes_anterior=observacoes_anterior,
                    observacoes_nova=observacoes,
                    tipo_alteracao='atualizacao'
                )
                tipo_msg = 'Avaliação atualizada'
            else:
                avaliacao = AvaliacaoHabilidade.objects.create(
                    matriz=matriz,
                    colaborador=colaborador,
                    disciplina=disciplina,
                    nivel=int(nivel),
                    data_avaliacao=data_avaliacao,
                    observacoes=observacoes,
                    avaliador=request.user.colaborador if hasattr(request.user, 'colaborador') else None,
                )
                
                # Salvar no histórico
                from procedures.models import HistoricoAvaliacaoHabilidade
                HistoricoAvaliacaoHabilidade.objects.create(
                    avaliacao=avaliacao,
                    nivel_anterior=None,
                    nivel_novo=int(nivel),
                    avaliador=request.user.colaborador if hasattr(request.user, 'colaborador') else None,
                    data_avaliacao=None,
                    data_avaliacao_nova=data_avaliacao,
                    observacoes_anterior=None,
                    observacoes_nova=observacoes,
                    tipo_alteracao='criacao'
                )
                tipo_msg = 'Avaliação criada'
            
            messages.success(request, f'{tipo_msg} com sucesso!')
            
            # Redirecionar de volta para a matriz
            return redirect(f"{request.META.get('HTTP_REFERER', '/procedures/avaliacoes/')}")
        
        except Exception as e:
            messages.error(request, f'Erro ao salvar avaliação: {str(e)}')
            return render(request, 'procedures/avaliacao_form.html', {
                'matriz': matriz,
                'colaborador': colaborador,
                'disciplina': disciplina,
                'avaliacao': avaliacao,
                'today': timezone.now().date(),
                'error': str(e)
            })
    else:
        if avaliacao:
            form = AvaliacaoHabilidadeForm(instance=avaliacao)
        else:
            form = AvaliacaoHabilidadeForm()
    
    # Buscar histórico se houver avaliação
    historico = []
    if avaliacao:
        from procedures.models import HistoricoAvaliacaoHabilidade
        historico = HistoricoAvaliacaoHabilidade.objects.filter(avaliacao=avaliacao).order_by('-alterado_em')
    
    context = {
        'form': form,
        'matriz': matriz,
        'colaborador': colaborador,
        'disciplina': disciplina,
        'avaliacao': avaliacao,
        'historico': historico,
        'today': timezone.now().date(),
    }
    
    return render(request, 'procedures/avaliacao_form.html', context)


@login_required
def avaliacoes_colaborador_view(request, colaborador_id):
    """
    Exibe todas as avaliações de um colaborador específico
    agrupadas por matriz
    """
    colaborador = get_object_or_404(Colaborador, id=colaborador_id)
    
    # Buscar avaliações do colaborador
    avaliacoes = AvaliacaoHabilidade.objects.filter(
        colaborador=colaborador
    ).select_related('matriz', 'disciplina', 'avaliador').order_by('matriz__nome', 'disciplina__codigo')
    
    # Agrupar por matriz
    avaliacoes_por_matriz = {}
    for av in avaliacoes:
        matriz_nome = av.matriz.nome
        if matriz_nome not in avaliacoes_por_matriz:
            avaliacoes_por_matriz[matriz_nome] = {
                'matriz': av.matriz,
                'avaliacoes': []
            }
        avaliacoes_por_matriz[matriz_nome]['avaliacoes'].append(av)
    
    context = {
        'colaborador': colaborador,
        'avaliacoes_por_matriz': avaliacoes_por_matriz,
    }
    
    return render(request, 'procedures/avaliacoes_colaborador.html', context)


@login_required
def avaliacao_rapida_view(request):
    """
    Interface para avaliação rápida via AJAX/POST
    Permite atualizar nivel diretamente da matriz
    """
    if request.method == 'POST':
        matriz_id = request.POST.get('matriz_id')
        colaborador_id = request.POST.get('colaborador_id')
        disciplina_id = request.POST.get('disciplina_id')
        nivel = request.POST.get('nivel')
        
        try:
            matriz = MatrizHabilidade.objects.get(id=matriz_id)
            colaborador = Colaborador.objects.get(id=colaborador_id)
            disciplina = Disciplina.objects.get(id=disciplina_id)
            
            # Verificar se disciplina pertence à matriz
            if not matriz.disciplinas_matriz.filter(id=disciplina_id).exists():
                return JsonResponse({'success': False, 'error': 'Disciplina não pertence a esta matriz'})
            
            # Buscar ou criar avaliação
            avaliacao, created = AvaliacaoHabilidade.objects.get_or_create(
                matriz=matriz,
                colaborador=colaborador,
                disciplina=disciplina,
                defaults={
                    'nivel': nivel,
                    'avaliador': request.user.colaborador if hasattr(request.user, 'colaborador') else None,
                    'data_avaliacao': timezone.now()
                }
            )
            
            if not created:
                avaliacao.nivel = nivel
                avaliacao.avaliador = request.user.colaborador if hasattr(request.user, 'colaborador') else None
                avaliacao.data_avaliacao = timezone.now()
                avaliacao.save()
            
            from django.http import JsonResponse
            return JsonResponse({
                'success': True,
                'nivel': avaliacao.nivel,
                'data': avaliacao.data_avaliacao.strftime('%d/%m/%Y %H:%M')
            })
        
        except Exception as e:
            from django.http import JsonResponse
            return JsonResponse({'success': False, 'error': str(e)})
    
    from django.http import JsonResponse
    return JsonResponse({'success': False, 'error': 'Método não permitido'})


# ==================== GERENCIAMENTO DE COLABORADORES ====================

@login_required
def desassociar_colaboradores_view(request, matriz_id):
    """
    Desassocia um ou mais colaboradores da matriz
    """
    import json
    from django.http import JsonResponse
    
    if request.method != 'POST':
        return JsonResponse({'sucesso': False, 'erro': 'Apenas POST permitido'})
    
    try:
        matriz = get_object_or_404(MatrizHabilidade, id=matriz_id)
        dados = json.loads(request.body)
        colaboradores_ids = dados.get('colaboradores', [])
        
        if not colaboradores_ids:
            return JsonResponse({'sucesso': False, 'erro': 'Nenhum colaborador informado'})
        
        # Importar modelo
        from procedures.models import ColaboradorMatrizHabilidade
        
        # Desassociar
        quantidade = ColaboradorMatrizHabilidade.objects.filter(
            matriz=matriz,
            colaborador_id__in=colaboradores_ids
        ).delete()[0]
        
        return JsonResponse({
            'sucesso': True,
            'quantidade': quantidade,
            'mensagem': f'{quantidade} colaborador(es) desassociado(s)'
        })
    
    except Exception as e:
        return JsonResponse({'sucesso': False, 'erro': str(e)})


@login_required
def colaboradores_disponiveis_view(request, matriz_id):
    """
    Retorna lista de colaboradores não associados à matriz
    """
    from django.http import JsonResponse
    
    try:
        matriz = get_object_or_404(MatrizHabilidade, id=matriz_id)
        
        # Importar modelo
        from procedures.models import ColaboradorMatrizHabilidade
        
        # Buscar IDs dos colaboradores já associados
        associados = ColaboradorMatrizHabilidade.objects.filter(
            matriz=matriz
        ).values_list('colaborador_id', flat=True)
        
        # Buscar colaboradores disponíveis (SEM limite)
        disponiveis = Colaborador.objects.filter(
            is_active=True
        ).exclude(
            id__in=associados
        ).values('id', 'nome_completo', 'matricula').order_by('nome_completo')
        
        return JsonResponse({
            'colaboradores': list(disponiveis)
        })
    
    except Exception as e:
        from django.http import JsonResponse
        return JsonResponse({'erro': str(e)})


@login_required
def associar_colaborador_view(request, matriz_id):
    """
    Associa um novo colaborador à matriz
    """
    import json
    from django.http import JsonResponse
    
    if request.method != 'POST':
        return JsonResponse({'sucesso': False, 'erro': 'Apenas POST permitido'})
    
    try:
        matriz = get_object_or_404(MatrizHabilidade, id=matriz_id)
        dados = json.loads(request.body)
        colaborador_id = dados.get('colaborador_id')
        
        if not colaborador_id:
            return JsonResponse({'sucesso': False, 'erro': 'Colaborador não informado'})
        
        # Verificar se colaborador existe
        colaborador = get_object_or_404(Colaborador, id=colaborador_id)
        
        # Importar modelo
        from procedures.models import ColaboradorMatrizHabilidade
        
        # Criar associação
        assoc, created = ColaboradorMatrizHabilidade.objects.get_or_create(
            matriz=matriz,
            colaborador=colaborador,
            defaults={'ativo': True}
        )
        
        if created:
            return JsonResponse({
                'sucesso': True,
                'mensagem': f'{colaborador.nome_completo} associado com sucesso!'
            })
        else:
            return JsonResponse({
                'sucesso': False,
                'erro': f'{colaborador.nome_completo} já está associado a esta matriz'
            })
    
    except Exception as e:
        from django.http import JsonResponse
        return JsonResponse({'sucesso': False, 'erro': str(e)})


@login_required
def obter_avaliacao_api(request, matriz_id, colaborador_id, disciplina_id):
    """
    API para obter dados de uma avaliação para o modal popup
    """
    try:
        matriz = get_object_or_404(MatrizHabilidade, id=matriz_id)
        colaborador = get_object_or_404(Colaborador, id=colaborador_id)
        disciplina = get_object_or_404(Disciplina, id=disciplina_id)
        
        # Buscar avaliação existente
        avaliacao = AvaliacaoHabilidade.objects.filter(
            matriz=matriz,
            colaborador=colaborador,
            disciplina=disciplina
        ).first()
        
        # Buscar histórico
        historico = []
        if avaliacao:
            historico_qs = HistoricoAvaliacaoHabilidade.objects.filter(
                avaliacao=avaliacao
            ).order_by('-alterado_em')[:5]
            
            for h in historico_qs:
                historico.append({
                    'tipo': h.tipo_alteracao,
                    'nivel_anterior': h.nivel_anterior,
                    'nivel_novo': h.nivel_novo,
                    'data_avaliacao': h.data_avaliacao_nova.strftime('%d/%m/%Y') if h.data_avaliacao_nova else None,
                    'alterado_em': h.alterado_em.strftime('%d/%m/%Y %H:%M'),
                    'avaliador': h.avaliador.nome_completo if h.avaliador else None,
                    'observacoes': h.observacoes_nova
                })
        
        return JsonResponse({
            'sucesso': True,
            'colaborador': {
                'id': colaborador.id,
                'nome': colaborador.nome_completo,
                'matricula': colaborador.matricula,
                'setor': str(colaborador.setor) if colaborador.setor else None
            },
            'disciplina': {
                'id': disciplina.id,
                'codigo': disciplina.codigo,
                'nome': disciplina.nome
            },
            'avaliacao': {
                'existe': avaliacao is not None,
                'nivel': avaliacao.nivel if avaliacao else None,
                'data_avaliacao': avaliacao.data_avaliacao.strftime('%Y-%m-%d') if avaliacao and avaliacao.data_avaliacao else None,
                'observacoes': avaliacao.observacoes if avaliacao else '',
                'avaliador': avaliacao.avaliador.nome_completo if avaliacao and avaliacao.avaliador else None
            },
            'historico': historico
        })
    except Exception as e:
        return JsonResponse({'sucesso': False, 'erro': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def salvar_avaliacao_api(request, matriz_id, colaborador_id, disciplina_id):
    """
    API para salvar avaliação via AJAX (modal popup)
    """
    try:
        data = json.loads(request.body)
        
        matriz = get_object_or_404(MatrizHabilidade, id=matriz_id)
        colaborador = get_object_or_404(Colaborador, id=colaborador_id)
        disciplina = get_object_or_404(Disciplina, id=disciplina_id)
        
        nivel = data.get('nivel')
        data_avaliacao_str = data.get('data_avaliacao')
        observacoes = data.get('observacoes', '')
        
        # Validações
        if nivel is None or nivel == '':
            return JsonResponse({'sucesso': False, 'erro': 'Nível é obrigatório'}, status=400)
        
        if not data_avaliacao_str:
            return JsonResponse({'sucesso': False, 'erro': 'Data é obrigatória'}, status=400)
        
        # Converter nível para inteiro
        try:
            nivel = int(nivel)
        except ValueError:
            return JsonResponse({'sucesso': False, 'erro': 'Nível inválido'}, status=400)
        
        # Converter data para objeto date
        from datetime import datetime
        try:
            data_avaliacao = datetime.strptime(data_avaliacao_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'sucesso': False, 'erro': 'Formato de data inválido'}, status=400)
        
        # Buscar avaliação existente
        avaliacao = AvaliacaoHabilidade.objects.filter(
            matriz=matriz,
            colaborador=colaborador,
            disciplina=disciplina
        ).first()
        
        # Criar ou atualizar avaliação
        if avaliacao:
            # Guardar valores antigos para o histórico
            nivel_anterior = avaliacao.nivel
            data_anterior = avaliacao.data_avaliacao
            observacoes_anterior = avaliacao.observacoes
            
            # Atualizar avaliação
            avaliacao.nivel = nivel
            avaliacao.data_avaliacao = data_avaliacao
            avaliacao.observacoes = observacoes
            avaliacao.avaliador = request.user.colaborador if hasattr(request.user, 'colaborador') else None
            avaliacao.save()
            
            # Salvar no histórico
            HistoricoAvaliacaoHabilidade.objects.create(
                avaliacao=avaliacao,
                nivel_anterior=nivel_anterior,
                nivel_novo=nivel,
                avaliador=request.user.colaborador if hasattr(request.user, 'colaborador') else None,
                data_avaliacao=data_anterior,
                data_avaliacao_nova=data_avaliacao,
                observacoes_anterior=observacoes_anterior,
                observacoes_nova=observacoes,
                tipo_alteracao='atualizacao'
            )
            tipo_msg = 'Avaliação atualizada'
        else:
            avaliacao = AvaliacaoHabilidade.objects.create(
                matriz=matriz,
                colaborador=colaborador,
                disciplina=disciplina,
                nivel=nivel,
                data_avaliacao=data_avaliacao,
                observacoes=observacoes,
                avaliador=request.user.colaborador if hasattr(request.user, 'colaborador') else None,
            )
            
            # Salvar no histórico
            HistoricoAvaliacaoHabilidade.objects.create(
                avaliacao=avaliacao,
                nivel_anterior=None,
                nivel_novo=nivel,
                avaliador=request.user.colaborador if hasattr(request.user, 'colaborador') else None,
                data_avaliacao=None,
                data_avaliacao_nova=data_avaliacao,
                observacoes_anterior=None,
                observacoes_nova=observacoes,
                tipo_alteracao='criacao'
            )
            tipo_msg = 'Avaliação criada'
        
        return JsonResponse({
            'sucesso': True,
            'mensagem': f'{tipo_msg} com sucesso!',
            'nivel': nivel
        })
        
    except Exception as e:
        import traceback
        print(f"Erro ao salvar avaliação: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'sucesso': False, 'erro': str(e)}, status=500)
