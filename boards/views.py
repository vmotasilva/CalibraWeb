from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.db.models import Count, Q, Max
import json

from boards.models import Board, BoardColumn, Card, ChecklistItem, CardComment, BoardActivity
from boards.forms import BoardForm, CardForm
from rh.models import Colaborador

def get_user_colaborador(user):
    return user.colaborador if hasattr(user, 'colaborador') else None


@login_required
def dashboard_view(request):
    """Exibe todos os quadros que o usuário gerencia ou participa"""
    colab = get_user_colaborador(request.user)
    
    # Superusuários vêm todos os quadros, colaboradores comuns vêm apenas os seus ou onde são membros
    if request.user.is_superuser:
        quadros = Board.objects.all().distinct()
    else:
        quadros = Board.objects.filter(
            Q(criado_por=colab) | Q(membros=colab)
        ).distinct()

    if request.method == 'POST':
        form = BoardForm(request.POST)
        if form.is_valid():
            board = form.save(commit=False)
            board.criado_por = colab
            board.save()
            
            # M2M precisa salvar depois de salvar o objeto base
            form.save_m2m()
            
            # Criar colunas padrão
            colunas_padrao = ["A Fazer", "Em Andamento", "Concluído"]
            for idx, nome_col in enumerate(colunas_padrao):
                BoardColumn.objects.create(quadro=board, nome=nome_col, ordem=idx)
                
            # Registrar atividade
            BoardActivity.objects.create(
                quadro=board,
                colaborador=colab,
                descricao="criou o quadro de atividades."
            )
            
            messages.success(request, f"Quadro '{board.nome}' criado com sucesso com as colunas padrão!")
            return redirect('boards:board_detail', board_id=board.id)
    else:
        form = BoardForm()
        
    context = {
        'quadros': quadros,
        'form': form,
        'titulo': 'Quadros de Atividades'
    }
    return render(request, 'boards/dashboard.html', context)


@login_required
def board_detail_view(request, board_id):
    """Visualização Kanban do quadro"""
    colab = get_user_colaborador(request.user)
    
    # Permissão de acesso
    if request.user.is_superuser:
        board = get_object_or_404(Board, id=board_id)
    else:
        board = get_object_or_404(
            Board.objects.filter(Q(criado_por=colab) | Q(membros=colab)), 
            id=board_id
        )
        
    # Colunas e cartões pré-carregados
    colunas = board.colunas.prefetch_related('cartoes__responsavel', 'cartoes__checklist_itens').all()
    
    # Calcular Métricas de Carga de Trabalho da Equipe
    total_cartoes = Card.objects.filter(coluna__quadro=board).count()
    
    # Identificar coluna de conclusão (última coluna por ordem ou contendo "concluido/concluído/done" no nome)
    concluido_colunas_ids = []
    for col in colunas:
        nome_low = col.nome.lower()
        if "concluido" in nome_low or "concluído" in nome_low or "done" in nome_low or "terminado" in nome_low or "pronto" in nome_low:
            concluido_colunas_ids.append(col.id)
            
    # Se não achar nenhuma pelo nome, assume a última
    if not concluido_colunas_ids and colunas.exists():
        concluido_colunas_ids.append(colunas.last().id)
        
    cartoes_concluidos = Card.objects.filter(coluna_id__in=concluido_colunas_ids).count()
    
    porcentagem_concluida = 0
    if total_cartoes > 0:
        porcentagem_concluida = int((cartoes_concluidos / total_cartoes) * 100)
        
    hoje = timezone.now().date()
    cartoes_atrasados = Card.objects.filter(
        coluna__quadro=board,
        data_entrega__lt=hoje
    ).exclude(coluna_id__in=concluido_colunas_ids).count()
    
    # Carga de trabalho por colaborador (exclui concluídos para focar no trabalho pendente)
    carga_membros = Colaborador.objects.filter(
        Q(quadros_participa=board) | Q(quadros_criados=board)
    ).annotate(
        tarefas_ativas=Count(
            'cartoes_atribuidos',
            filter=Q(cartoes_atribuidos__coluna__quadro=board) & ~Q(cartoes_atribuidos__coluna_id__in=concluido_colunas_ids)
        )
    ).filter(tarefas_ativas__gt=0).order_by('-tarefas_ativas')
    
    # Preparar dados para o Chart.js
    chart_membros_nomes = [m.nome_completo for m in carga_membros]
    chart_membros_valores = [m.tarefas_ativas for m in carga_membros]
    
    # Distribuição por colunas
    distribuicao_colunas = []
    for col in colunas:
        distribuicao_colunas.append({
            'nome': col.nome,
            'quantidade': col.cartoes.count()
        })
        
    # Atividades recentes do quadro (limita a 20)
    atividades = board.atividades.select_related('colaborador')[:20]
    
    # Formulários para criação rápida
    card_form = CardForm(board=board)
    
    # Lista de colaboradores para o dropdown de transferência de responsável
    todos_colaboradores = Colaborador.objects.filter(is_active=True).order_by('nome_completo')
    
    context = {
        'board': board,
        'colunas': colunas,
        'card_form': card_form,
        'total_cartoes': total_cartoes,
        'cartoes_concluidos': cartoes_concluidos,
        'porcentagem_concluida': porcentagem_concluida,
        'cartoes_atrasados': cartoes_atrasados,
        'atividades': atividades,
        'todos_colaboradores': todos_colaboradores,
        'chart_membros_nomes': json.dumps(chart_membros_nomes),
        'chart_membros_valores': json.dumps(chart_membros_valores),
        'distribuicao_colunas': json.dumps(distribuicao_colunas),
        'titulo': f"Quadro - {board.nome}"
    }
    return render(request, 'boards/board_detail.html', context)


@login_required
@require_POST
def create_column_view(request, board_id):
    """Cria uma nova coluna no quadro"""
    colab = get_user_colaborador(request.user)
    board = get_object_or_404(Board, id=board_id)
    nome = request.POST.get('nome', '').strip()
    
    if nome:
        # Pega a maior ordem e soma 1
        maior_ordem = board.colunas.aggregate(Max('ordem'))['ordem__max']
        ordem = (maior_ordem + 1) if maior_ordem is not None else 0
        
        coluna = BoardColumn.objects.create(quadro=board, nome=nome, ordem=ordem)
        
        BoardActivity.objects.create(
            quadro=board,
            colaborador=colab,
            descricao=f"criou a coluna '{nome}'."
        )
        messages.success(request, f"Coluna '{nome}' criada!")
    else:
        messages.error(request, "O nome da coluna é obrigatório!")
        
    return redirect('boards:board_detail', board_id=board.id)


@login_required
@require_POST
def delete_column_view(request, column_id):
    """Remove uma coluna do quadro e seus cartões"""
    colab = get_user_colaborador(request.user)
    coluna = get_object_or_404(BoardColumn, id=column_id)
    board = coluna.quadro
    
    nome_coluna = coluna.nome
    coluna.delete()
    
    BoardActivity.objects.create(
        quadro=board,
        colaborador=colab,
        descricao=f"excluiu a coluna '{nome_coluna}'."
    )
    messages.success(request, f"Coluna '{nome_coluna}' excluída.")
    return redirect('boards:board_detail', board_id=board.id)


@login_required
@require_POST
def create_card_view(request, column_id):
    """Cria um novo cartão em uma coluna"""
    colab = get_user_colaborador(request.user)
    coluna = get_object_or_404(BoardColumn, id=column_id)
    board = coluna.quadro
    
    form = CardForm(request.POST, board=board)
    if form.is_valid():
        card = form.save(commit=False)
        card.coluna = coluna
        card.criado_por = colab
        
        # Pega a maior ordem na coluna
        maior_ordem = coluna.cartoes.aggregate(Max('ordem'))['ordem__max']
        card.ordem = (maior_ordem + 1) if maior_ordem is not None else 0
        
        card.save()
        
        BoardActivity.objects.create(
            quadro=board,
            colaborador=colab,
            descricao=f"criou o cartão '{card.titulo}' na coluna '{coluna.nome}'."
        )
        messages.success(request, f"Tarefa '{card.titulo}' criada com sucesso!")
    else:
        messages.error(request, "Erro ao criar a tarefa. Verifique os dados inseridos.")
        
    return redirect('boards:board_detail', board_id=board.id)


@login_required
@require_POST
def api_move_card_view(request):
    """Endpoint API para mover cartão de coluna/posição via Drag and Drop"""
    try:
        colab = get_user_colaborador(request.user)
        data = json.loads(request.body)
        card_id = data.get('card_id')
        to_column_id = data.get('to_column_id')
        card_order_ids = data.get('card_order_ids', []) # Array de IDs na nova ordem
        
        card = get_object_or_404(Card, id=card_id)
        old_col_nome = card.coluna.nome
        nova_coluna = get_object_or_404(BoardColumn, id=to_column_id)
        
        # Atualizar a coluna do cartão movido
        card.coluna = nova_coluna
        card.save()
        
        # Atualizar a ordem de todos os cartões na coluna destino
        with transaction.atomic():
            for idx, c_id in enumerate(card_order_ids):
                Card.objects.filter(id=c_id).update(ordem=idx)
                
        # Registrar atividade se mudou de coluna
        if old_col_nome != nova_coluna.nome:
            BoardActivity.objects.create(
                quadro=nova_coluna.quadro,
                colaborador=colab,
                descricao=f"moveu o cartão '{card.titulo}' de '{old_col_nome}' para '{nova_coluna.nome}'."
            )
            
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def api_card_detail_view(request, card_id):
    """Endpoint API para buscar detalhes e atualizar informações de um cartão"""
    colab = get_user_colaborador(request.user)
    card = get_object_or_404(Card, id=card_id)
    board = card.coluna.quadro
    
    if request.method == 'GET':
        checklist = list(card.checklist_itens.values('id', 'descricao', 'concluido'))
        comentarios = []
        for c in card.comentarios.select_related('autor').all():
            comentarios.append({
                'id': c.id,
                'autor': c.autor.nome_completo,
                'texto': c.texto,
                'data': c.criado_em.strftime('%d/%m/%Y %H:%M')
            })
            
        data = {
            'id': card.id,
            'titulo': card.titulo,
            'descricao': card.descricao or '',
            'responsavel_id': card.responsavel.id if card.responsavel else '',
            'responsavel_nome': card.responsavel.nome_completo if card.responsavel else 'Não atribuído',
            'prioridade': card.prioridade,
            'prioridade_label': card.get_prioridade_display(),
            'data_entrega': card.data_entrega.strftime('%Y-%m-%d') if card.data_entrega else '',
            'checklist': checklist,
            'comentarios': comentarios
        }
        return JsonResponse(data)
        
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            # Atualizar os dados do cartão
            card.titulo = data.get('titulo', card.titulo).strip()
            card.descricao = data.get('descricao', card.descricao)
            
            resp_id = data.get('responsavel_id')
            if resp_id:
                card.responsavel = get_object_or_404(Colaborador, id=resp_id)
            else:
                card.responsavel = None
                
            prioridade = data.get('prioridade')
            if prioridade in dict(Card.PRIORIDADE_CHOICES):
                card.prioridade = prioridade
                
            data_entrega_raw = data.get('data_entrega')
            if data_entrega_raw:
                card.data_entrega = data_entrega_raw
            else:
                card.data_entrega = None
                
            card.save()
            
            BoardActivity.objects.create(
                quadro=board,
                colaborador=colab,
                descricao=f"editou o cartão '{card.titulo}'."
            )
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def api_add_checklist_item_view(request, card_id):
    """Cria um item de checklist no cartão"""
    colab = get_user_colaborador(request.user)
    card = get_object_or_404(Card, id=card_id)
    
    data = json.loads(request.body)
    descricao = data.get('descricao', '').strip()
    
    if descricao:
        item = ChecklistItem.objects.create(cartao=card, descricao=descricao)
        BoardActivity.objects.create(
            quadro=card.coluna.quadro,
            colaborador=colab,
            descricao=f"adicionou o item '{descricao}' no checklist de '{card.titulo}'."
        )
        return JsonResponse({
            'success': True, 
            'item': {'id': item.id, 'descricao': item.descricao, 'concluido': item.concluido}
        })
    return JsonResponse({'success': False, 'error': 'Descrição é obrigatória'}, status=400)


@login_required
@require_POST
def api_toggle_checklist_item_view(request, item_id):
    """Inverte o status de concluído do item do checklist"""
    colab = get_user_colaborador(request.user)
    item = get_object_or_404(ChecklistItem, id=item_id)
    card = item.cartao
    
    item.concluido = not item.concluido
    item.save()
    
    status_str = "concluiu" if item.concluido else "desmarcou"
    BoardActivity.objects.create(
        quadro=card.coluna.quadro,
        colaborador=colab,
        descricao=f"{status_str} o item '{item.descricao}' em '{card.titulo}'."
    )
    return JsonResponse({'success': True, 'concluido': item.concluido})


@login_required
@require_POST
def api_delete_checklist_item_view(request, item_id):
    """Exclui item de checklist"""
    colab = get_user_colaborador(request.user)
    item = get_object_or_404(ChecklistItem, id=item_id)
    card = item.cartao
    
    item_desc = item.descricao
    item.delete()
    
    BoardActivity.objects.create(
        quadro=card.coluna.quadro,
        colaborador=colab,
        descricao=f"removeu o item '{item_desc}' do checklist de '{card.titulo}'."
    )
    return JsonResponse({'success': True})


@login_required
@require_POST
def api_add_comment_view(request, card_id):
    """Adiciona comentário no cartão"""
    colab = get_user_colaborador(request.user)
    card = get_object_or_404(Card, id=card_id)
    
    data = json.loads(request.body)
    texto = data.get('texto', '').strip()
    
    if texto:
        comment = CardComment.objects.create(cartao=card, autor=colab, texto=texto)
        BoardActivity.objects.create(
            quadro=card.coluna.quadro,
            colaborador=colab,
            descricao=f"comentou no cartão '{card.titulo}'."
        )
        return JsonResponse({
            'success': True, 
            'comentario': {
                'id': comment.id,
                'autor': comment.autor.nome_completo,
                'texto': comment.texto,
                'data': comment.criado_em.strftime('%d/%m/%Y %H:%M')
            }
        })
    return JsonResponse({'success': False, 'error': 'Texto é obrigatório'}, status=400)


@login_required
@require_POST
def api_delete_comment_view(request, comment_id):
    """Exclui um comentário do cartão"""
    colab = get_user_colaborador(request.user)
    comment = get_object_or_404(CardComment, id=comment_id)
    
    # Permissão: apenas o autor ou administrador pode deletar o comentário
    if comment.autor != colab and not (request.user.is_superuser or request.user.is_staff):
        return JsonResponse({'success': False, 'error': 'Acesso negado'}, status=403)
        
    comment.delete()
    return JsonResponse({'success': True})


@login_required
@require_POST
def delete_card_view(request, card_id):
    """Exclui um cartão"""
    colab = get_user_colaborador(request.user)
    card = get_object_or_404(Card, id=card_id)
    board = card.coluna.quadro
    
    titulo_card = card.titulo
    card.delete()
    
    BoardActivity.objects.create(
        quadro=board,
        colaborador=colab,
        descricao=f"excluiu o cartão '{titulo_card}'."
    )
    messages.success(request, f"Tarefa '{titulo_card}' excluída.")
    return redirect('boards:board_detail', board_id=board.id)


@login_required
@require_POST
def edit_board_view(request, board_id):
    """Edita dados e membros do quadro"""
    colab = get_user_colaborador(request.user)
    board = get_object_or_404(Board, id=board_id)
    
    form = BoardForm(request.POST, instance=board)
    if form.is_valid():
        form.save()
        BoardActivity.objects.create(
            quadro=board,
            colaborador=colab,
            descricao="atualizou as configurações do quadro."
        )
        messages.success(request, "Configurações do quadro atualizadas!")
    else:
        messages.error(request, "Erro ao atualizar o quadro. Verifique os campos.")
        
    return redirect('boards:board_detail', board_id=board.id)


@login_required
@require_POST
def delete_board_view(request, board_id):
    """Remove um quadro completo"""
    colab = get_user_colaborador(request.user)
    board = get_object_or_404(Board, id=board_id)
    
    # Apenas o criador ou superuser pode excluir
    if board.criado_por != colab and not request.user.is_superuser:
        messages.error(request, "Apenas o criador do quadro pode excluí-lo.")
        return redirect('boards:board_detail', board_id=board.id)
        
    nome_board = board.nome
    board.delete()
    
    messages.success(request, f"Quadro '{nome_board}' excluído permanentemente.")
    return redirect('boards:dashboard')
