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
from organization.models import Setor


# ==================== AVALIAÇÕES DE HABILIDADE ====================

@login_required
def matriz_avaliacoes_view(request):
    """
    Exibe uma matriz de avaliações: colaboradores x disciplinas
    com os níveis de competência (0-3)
    """
    # Filtros
    matriz_id = request.GET.get('matriz', '')
    disciplina_filtro = request.GET.get('disciplina', '')
    setor = request.GET.get('setor', '')
    turno = request.GET.get('turno', '')
    termo_colab = request.GET.get('colaborador', '').strip()
    nivel_filtro = request.GET.get('nivel_filtro', '')

    setor_id = None
    if setor and str(setor).isdigit():
        setor_id = int(setor)

    disciplina_filtro_id = None
    if disciplina_filtro and str(disciplina_filtro).isdigit():
        disciplina_filtro_id = int(disciplina_filtro)
    
    # Buscar matrizes disponíveis
    matrizes = MatrizHabilidade.objects.filter(ativo=True).order_by('nome')
    
    # Selecionar matriz
    matriz_selecionada = None
    disciplinas = []
    disciplinas_exibidas = []
    colaboradores = []
    avaliacoes_dict = {}
    turnos_disponiveis = []
    pagination = None
    query_params = None
    colaboradores_desligados_ids = []
    desligados_ids_json = '[]'
    
    if matriz_id:
        matriz_selecionada = get_object_or_404(MatrizHabilidade, id=matriz_id)
        # Colunas (disciplinas) em ordem alfabética crescente
        from django.db.models.functions import Lower
        disciplinas = matriz_selecionada.disciplinas_matriz.filter(ativo=True).order_by(Lower('nome'))
        
        # Buscar APENAS colaboradores associados à matriz
        from procedures.models import ColaboradorMatrizHabilidade
        colaboradores_assoc = ColaboradorMatrizHabilidade.objects.filter(
            matriz=matriz_selecionada,
            ativo=True
        ).select_related('colaborador')

        # Setores disponíveis para esta matriz (antes de aplicar filtros/limites)
        setores_ids_matriz = list(
            colaboradores_assoc.values_list('colaborador__setor_id', flat=True)
            .exclude(colaborador__setor_id__isnull=True)
            .distinct()
        )
        
        # Obter turnos únicos disponíveis nesta matriz (antes de aplicar filtros)
        turnos_disponiveis = sorted(list(set(
            colaboradores_assoc.values_list('colaborador__turno', flat=True)
            .exclude(colaborador__turno__isnull=True)
            .exclude(colaborador__turno='')
            .distinct()
        )))
        
        # Filtrar o queryset de Colaboradores associados à matriz
        colaboradores_qs = Colaborador.objects.filter(
            id__in=colaboradores_assoc.values_list('colaborador_id', flat=True)
        ).select_related('setor').order_by('nome_completo')
        
        if setor_id is not None:
            colaboradores_qs = colaboradores_qs.filter(setor_id=setor_id)
        
        if turno:
            colaboradores_qs = colaboradores_qs.filter(turno=turno)
        
        if termo_colab:
            colaboradores_qs = colaboradores_qs.filter(
                Q(nome_completo__icontains=termo_colab) |
                Q(matricula__icontains=termo_colab)
            )
        
        if nivel_filtro in ['-1', '0', '1', '2', '3']:
            nivel_val = int(nivel_filtro)
            colaboradores_qs = colaboradores_qs.filter(
                avaliacoes_habilidade__matriz=matriz_selecionada,
                avaliacoes_habilidade__disciplina__in=disciplinas,
                avaliacoes_habilidade__nivel=nivel_val
            ).distinct()
        elif nivel_filtro == 'pendente' and disciplinas.exists():
            from django.db.models import Count
            colaboradores_qs = colaboradores_qs.annotate(
                num_avaliacoes=Count(
                    'avaliacoes_habilidade',
                    filter=Q(
                        avaliacoes_habilidade__matriz=matriz_selecionada,
                        avaliacoes_habilidade__disciplina__in=disciplinas
                    )
                )
            ).filter(num_avaliacoes__lt=disciplinas.count())
        
        # Obter IDs dos colaboradores desligados associados à matriz
        colaboradores_desligados_ids = list(Colaborador.objects.filter(
            id__in=ColaboradorMatrizHabilidade.objects.filter(matriz=matriz_selecionada, ativo=True).values_list('colaborador_id', flat=True),
            is_active=False
        ).values_list('id', flat=True))
        import json
        desligados_ids_json = json.dumps(colaboradores_desligados_ids)
        
        # Paginar colaboradores usando o OffsetPaginator padrão
        from qms.pagination import OffsetPaginator, PaginationHelper
        page = PaginationHelper.get_page_from_request(request)
        paginator = OffsetPaginator(page_size=50)
        
        colaboradores, pagination_metadata = paginator.paginate_queryset(
            colaboradores_qs,
            page=page
        )
        pagination = pagination_metadata.to_dict()
        
        query_params = request.GET.copy()
        if 'page' in query_params:
            query_params.pop('page')
        
        # Disciplinas a serem renderizadas nos cards
        disciplinas_exibidas = disciplinas
        if disciplina_filtro_id:
            disciplinas_exibidas = disciplinas.filter(id=disciplina_filtro_id)

        # Buscar avaliações existentes
        avaliacoes = AvaliacaoHabilidade.objects.filter(
            matriz=matriz_selecionada,
            colaborador__in=colaboradores,
            disciplina__in=disciplinas_exibidas
        ).select_related('colaborador', 'disciplina', 'avaliador')
        
        # Criar estrutura de dados para o template
        # Lista de listas: cada colaborador tem uma lista de células (uma por disciplina)
        matriz_dados = []
        for colaborador in colaboradores:
            linha = {
                'colaborador': colaborador,
                'avaliacoes': []
            }
            for disciplina in disciplinas_exibidas:
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

        # Obter estatísticas das colunas (disciplinas) para toda a matriz (respeitando filtros atuais)
        colaboradores_ids_filtrados = list(colaboradores_qs.values_list('id', flat=True))
        total_colab_filtrados = len(colaboradores_ids_filtrados)
        
        todas_avaliacoes = AvaliacaoHabilidade.objects.filter(
            matriz=matriz_selecionada,
            disciplina__in=disciplinas,
            colaborador_id__in=colaboradores_ids_filtrados
        ).values('disciplina_id', 'nivel')
        
        resumos_disciplinas = {d.id: {-1: 0, 0: 0, 1: 0, 2: 0, 3: 0, 'total_avaliados': 0} for d in disciplinas}
        for av in todas_avaliacoes:
            d_id = av['disciplina_id']
            nivel = av['nivel']
            if d_id in resumos_disciplinas:
                if nivel in resumos_disciplinas[d_id]:
                    resumos_disciplinas[d_id][nivel] += 1
                resumos_disciplinas[d_id]['total_avaliados'] += 1
                
        for disc in disciplinas:
            resumo = resumos_disciplinas.get(disc.id, {-1: 0, 0: 0, 1: 0, 2: 0, 3: 0, 'total_avaliados': 0})
            disc.resumo_lote = {
                'na': resumo.get(-1, 0),
                'nivel_0': resumo.get(0, 0),
                'nivel_1': resumo.get(1, 0),
                'nivel_2': resumo.get(2, 0),
                'nivel_3': resumo.get(3, 0),
                'pendentes': max(0, total_colab_filtrados - resumo.get('total_avaliados', 0))
            }
    
    # Buscar setores disponíveis (com nome) para o filtro
    if matriz_id and matriz_selecionada:
        setores = Setor.objects.filter(id__in=setores_ids_matriz).order_by('nome')
    else:
        setores_ids = (
            Colaborador.objects.filter(is_active=True, setor__isnull=False)
            .values_list('setor_id', flat=True)
            .distinct()
        )
        setores = Setor.objects.filter(id__in=setores_ids).order_by('nome')
    
    # Busca Global de Colaboradores (Quando não há matriz, mas há termo)
    colaboradores_globais = None
    if not matriz_id and termo_colab:
        colaboradores_qs = Colaborador.objects.filter(
            Q(nome_completo__icontains=termo_colab) |
            Q(matricula__icontains=termo_colab),
            is_active=True
        ).select_related('setor').order_by('nome_completo')
        
        from qms.pagination import OffsetPaginator, PaginationHelper
        page = PaginationHelper.get_page_from_request(request)
        paginator = OffsetPaginator(page_size=20)
        colabs_page, pagination_metadata = paginator.paginate_queryset(
            colaboradores_qs,
            page=page
        )
        pagination = pagination_metadata.to_dict()
        
        query_params = request.GET.copy()
        if 'page' in query_params:
            query_params.pop('page')

        # Buscar matrizes vinculadas de cada colaborador da página
        from procedures.models import ColaboradorMatrizHabilidade
        colab_ids = [c.id for c in colabs_page]
        vinculos = ColaboradorMatrizHabilidade.objects.filter(
            colaborador_id__in=colab_ids,
            ativo=True,
            matriz__ativo=True
        ).select_related('matriz').order_by('matriz__nome')
        
        matrizes_map = {}
        for v in vinculos:
            if v.colaborador_id not in matrizes_map:
                matrizes_map[v.colaborador_id] = []
            matrizes_map[v.colaborador_id].append(v.matriz)
            
        colaboradores_globais = []
        for c in colabs_page:
            c.matrizes_vinculadas = matrizes_map.get(c.id, [])
            colaboradores_globais.append(c)

    context = {
        'matrizes': matrizes,
        'matriz_selecionada': matriz_selecionada,
        'disciplinas': disciplinas,
        'disciplinas_exibidas': disciplinas_exibidas,
        'disciplina_filtro': disciplina_filtro,
        'matriz_dados': matriz_dados if matriz_selecionada else [],
        'colaboradores_globais': colaboradores_globais,
        'setores': setores,
        'turnos_disponiveis': turnos_disponiveis,
        'matriz_id': matriz_id,
        'setor': setor,
        'turno': turno,
        'termo_colab': termo_colab,
        'nivel_filtro': nivel_filtro,
        'pagination': pagination,
        'query_params': query_params,
        'colaboradores_desligados_ids': colaboradores_desligados_ids,
        'desligados_ids_json': desligados_ids_json,
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
    Exibe todas as matrizes e avaliações de um colaborador específico,
    renderizando cada matriz no formato visual de cards/faróis (uma abaixo da outra).
    """
    colaborador = get_object_or_404(
        Colaborador.objects.select_related('setor'), 
        id=colaborador_id
    )
    
    from procedures.models import ColaboradorMatrizHabilidade, MatrizHabilidade
    from django.db.models.functions import Lower

    # Matrizes vinculadas ativas
    matrizes_assoc_ids = list(
        ColaboradorMatrizHabilidade.objects.filter(
            colaborador=colaborador,
            ativo=True
        ).values_list('matriz_id', flat=True)
    )
    
    # Matrizes onde o colaborador tem alguma avaliação
    matrizes_com_avaliacao_ids = list(
        AvaliacaoHabilidade.objects.filter(
            colaborador=colaborador
        ).values_list('matriz_id', flat=True)
    )
    
    todas_matrizes_ids = list(set(matrizes_assoc_ids + matrizes_com_avaliacao_ids))
    
    matrizes = MatrizHabilidade.objects.filter(
        id__in=todas_matrizes_ids,
        ativo=True
    ).order_by(Lower('nome'))
    
    # Buscar todas as avaliações deste colaborador nestas matrizes
    avaliacoes = AvaliacaoHabilidade.objects.filter(
        colaborador=colaborador,
        matriz__in=matrizes
    ).select_related('matriz', 'disciplina', 'avaliador')
    
    avaliacoes_map = {(av.matriz_id, av.disciplina_id): av for av in avaliacoes}
    
    matrizes_dados = []
    for matriz in matrizes:
        disciplinas = list(matriz.disciplinas_matriz.filter(ativo=True).order_by(Lower('nome')))
        celulas = []
        for disc in disciplinas:
            av = avaliacoes_map.get((matriz.id, disc.id))
            celulas.append({
                'disciplina': disc,
                'avaliacao': av
            })
        
        matrizes_dados.append({
            'matriz': matriz,
            'disciplinas': disciplinas,
            'total_disciplinas': len(disciplinas),
            'celulas': celulas,
        })
    
    context = {
        'colaborador': colaborador,
        'matrizes_dados': matrizes_dados,
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
        ).select_related('setor', 'lider').values(
            'id', 'nome_completo', 'matricula', 'setor_id', 'setor__nome', 'lider_id', 'lider__nome_completo', 'turno'
        ).order_by('nome_completo')
        
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


@login_required
@require_http_methods(["POST"])
def salvar_avaliacao_lote_api(request, matriz_id, disciplina_id):
    """
    API para salvar avaliações em lote para uma coluna (disciplina) inteira.
    """
    try:
        data = json.loads(request.body)
        
        matriz = get_object_or_404(MatrizHabilidade, id=matriz_id)
        disciplina = get_object_or_404(Disciplina, id=disciplina_id)
        
        nivel = data.get('nivel')
        data_avaliacao_str = data.get('data_avaliacao')
        observacoes = data.get('observacoes', '')
        somente_sem_avaliacao = data.get('somente_sem_avaliacao', False)
        
        # Filtros e targets
        colaborador_ids = data.get('colaborador_ids', [])
        setor_id = data.get('setor_id')
        turno = data.get('turno')
        termo_colab = data.get('termo_colab', '').strip()
        
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
            
        # Determinar os colaboradores alvo
        from procedures.models import ColaboradorMatrizHabilidade
        colaboradores_assoc = ColaboradorMatrizHabilidade.objects.filter(
            matriz=matriz,
            ativo=True
        ).select_related('colaborador')
        
        colaboradores_qs = Colaborador.objects.filter(
            id__in=colaboradores_assoc.values_list('colaborador_id', flat=True)
        )
        
        if colaborador_ids:
            colaboradores_qs = colaboradores_qs.filter(id__in=colaborador_ids)
        else:
            # Se não passou ID específico, aplicar filtros da tela atual (se houver)
            if setor_id:
                try:
                    colaboradores_qs = colaboradores_qs.filter(setor_id=int(setor_id))
                except ValueError:
                    pass
            if turno:
                colaboradores_qs = colaboradores_qs.filter(turno=turno)
            if termo_colab:
                colaboradores_qs = colaboradores_qs.filter(
                    Q(nome_completo__icontains=termo_colab) |
                    Q(matricula__icontains=termo_colab)
                )
        
        target_colaboradores = list(colaboradores_qs)
        if not target_colaboradores:
            return JsonResponse({'sucesso': True, 'mensagem': 'Nenhum colaborador elegível encontrado.', 'count': 0})
            
        # Loop para salvar/atualizar
        count_updated = 0
        from django.db import transaction
        with transaction.atomic():
            for colab in target_colaboradores:
                # Buscar se já existe avaliação
                avaliacao = AvaliacaoHabilidade.objects.filter(
                    matriz=matriz,
                    colaborador=colab,
                    disciplina=disciplina
                ).first()
                
                if avaliacao:
                    # Se for pra aplicar somente em células vazias, pular esta
                    if somente_sem_avaliacao:
                        continue
                        
                    # Guardar valores antigos
                    nivel_anterior = avaliacao.nivel
                    data_anterior = avaliacao.data_avaliacao
                    observacoes_anterior = avaliacao.observacoes
                    
                    # Atualizar
                    avaliacao.nivel = nivel
                    avaliacao.data_avaliacao = data_avaliacao
                    avaliacao.observacoes = observacoes
                    avaliacao.avaliador = request.user.colaborador if hasattr(request.user, 'colaborador') else None
                    avaliacao.save()
                    
                    # Gravar no histórico
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
                else:
                    # Criar nova
                    avaliacao = AvaliacaoHabilidade.objects.create(
                        matriz=matriz,
                        colaborador=colab,
                        disciplina=disciplina,
                        nivel=nivel,
                        data_avaliacao=data_avaliacao,
                        observacoes=observacoes,
                        avaliador=request.user.colaborador if hasattr(request.user, 'colaborador') else None,
                    )
                    
                    # Gravar histórico
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
                
                count_updated += 1
                
        return JsonResponse({
            'sucesso': True,
            'mensagem': f'{count_updated} avaliação(ões) salva(s) com sucesso!',
            'count': count_updated
        })
        
    except Exception as e:
        import traceback
        print(f"Erro ao salvar avaliações em lote: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'sucesso': False, 'erro': str(e)}, status=500)


@login_required
def exportar_matriz_excel_view(request):
    """
    Exporta a matriz de avaliações (filtrada) para Excel
    """
    matriz_id = request.GET.get('matriz', '')
    setor = request.GET.get('setor', '')
    turno = request.GET.get('turno', '')
    termo_colab = request.GET.get('colaborador', '').strip()

    if not matriz_id:
        messages.error(request, 'Selecione uma matriz para exportar!')
        return redirect('procedures:matriz_avaliacoes')

    matriz_selecionada = get_object_or_404(MatrizHabilidade, id=matriz_id)
    
    from django.db.models.functions import Lower
    disciplinas = matriz_selecionada.disciplinas_matriz.filter(ativo=True).order_by(Lower('nome'))
    
    from procedures.models import ColaboradorMatrizHabilidade
    colaboradores_assoc = ColaboradorMatrizHabilidade.objects.filter(
        matriz=matriz_selecionada,
        ativo=True
    ).select_related('colaborador')

    nivel_filtro = request.GET.get('nivel_filtro', '')

    colaboradores_qs = Colaborador.objects.filter(
        id__in=colaboradores_assoc.values_list('colaborador_id', flat=True)
    ).select_related('setor').order_by('nome_completo')

    if setor and str(setor).isdigit():
        colaboradores_qs = colaboradores_qs.filter(setor_id=int(setor))
    
    if turno:
        colaboradores_qs = colaboradores_qs.filter(turno=turno)
    
    if termo_colab:
        colaboradores_qs = colaboradores_qs.filter(
            Q(nome_completo__icontains=termo_colab) |
            Q(matricula__icontains=termo_colab)
        )

    if nivel_filtro in ['-1', '0', '1', '2', '3']:
        nivel_val = int(nivel_filtro)
        colaboradores_qs = colaboradores_qs.filter(
            avaliacoes_habilidade__matriz=matriz_selecionada,
            avaliacoes_habilidade__disciplina__in=disciplinas,
            avaliacoes_habilidade__nivel=nivel_val
        ).distinct()
    elif nivel_filtro == 'pendente' and disciplinas.exists():
        from django.db.models import Count
        colaboradores_qs = colaboradores_qs.annotate(
            num_avaliacoes=Count(
                'avaliacoes_habilidade',
                filter=Q(
                    avaliacoes_habilidade__matriz=matriz_selecionada,
                    avaliacoes_habilidade__disciplina__in=disciplinas
                )
            )
        ).filter(num_avaliacoes__lt=disciplinas.count())

    colaboradores = list(colaboradores_qs)
    
    avaliacoes = AvaliacaoHabilidade.objects.filter(
        matriz=matriz_selecionada,
        colaborador__in=colaboradores,
        disciplina__in=disciplinas
    ).select_related('colaborador', 'disciplina')
    
    avaliacoes_map = {
        (av.colaborador_id, av.disciplina_id): av.nivel
        for av in avaliacoes
    }
    
    rows = []
    for col in colaboradores:
        row = {
            'Matrícula': col.matricula or '',
            'Colaborador': col.nome_completo or '',
            'Setor': str(col.setor) if col.setor else '',
            'Turno': col.turno or '',
        }
        for disc in disciplinas:
            nivel = avaliacoes_map.get((col.id, disc.id))
            if nivel is None:
                row[disc.nome] = ''
            elif nivel == -1:
                row[disc.nome] = 'N/A'
            else:
                row[disc.nome] = nivel
        rows.append(row)

    import io
    import pandas as pd
    from django.http import HttpResponse
    
    df = pd.DataFrame(rows)
    
    cols = ['Matrícula', 'Colaborador', 'Setor', 'Turno'] + [disc.nome for disc in disciplinas]
    for col_name in cols:
        if col_name not in df.columns:
            df[col_name] = ''
    df = df[cols]
    
    b = io.BytesIO()
    with pd.ExcelWriter(b, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Matriz de Habilidades')
        
        workbook = writer.book
        worksheet = writer.sheets['Matriz de Habilidades']
        
        from openpyxl.utils import get_column_letter
        for col_idx, col_name in enumerate(df.columns, 1):
            max_len = max(
                df[col_name].astype(str).map(len).max(),
                len(str(col_name))
            ) + 3
            max_len = min(max_len, 50)
            worksheet.column_dimensions[get_column_letter(col_idx)].width = max_len

    b.seek(0)
    
    nome_matriz = matriz_selecionada.nome.replace(' ', '_').replace('/', '_')
    filename = f"Matriz_Habilidades_{nome_matriz}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    response = HttpResponse(b, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

