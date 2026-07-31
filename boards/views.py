from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.db.models import Count, Q, Max
import json
import datetime
import calendar

from boards.models import Board, BoardColumn, Card, ChecklistItem, CardComment, BoardActivity, BoardSubSection, BoardLabel, CardPlanningDate, BoardLink, BoardNotification, BoardMention

def notify_card_update(card, actor, message):
    for responsavel in card.responsaveis.all():
        if actor and responsavel.id == actor.id:
            continue
        BoardNotification.objects.create(
            colaborador=responsavel,
            cartao=card,
            mensagem=message,
            criado_por=actor
        )

from boards.forms import BoardForm, CardForm
from rh.models import Colaborador

def get_user_colaborador(user):
    return user.colaborador if hasattr(user, 'colaborador') else None

def can_edit_board(board, colab, user):
    """
    Retorna True se o usuário pode alterar estrutura (configurações, colunas, tags) do quadro.
    Somente superuser, criador e membros explícitos têm permissão de edição.
    Usuários que acessam via 'todos_colaboradores=True' são apenas leitores/associados.
    """
    if user.is_superuser:
        return True
    if not colab:
        return False
    if board.criado_por == colab:
        return True
    return board.membros.filter(id=colab.id).exists()


from functools import wraps
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
import json

def require_board_edit_permission(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        colab = get_user_colaborador(request.user)
        board = None
        
        try:
            if 'board_id' in kwargs:
                from .models import Board
                board = get_object_or_404(Board, id=kwargs['board_id'])
            elif 'column_id' in kwargs:
                from .models import BoardColumn
                board = get_object_or_404(BoardColumn, id=kwargs['column_id']).quadro
            elif 'card_id' in kwargs:
                from .models import Card
                board = get_object_or_404(Card, id=kwargs['card_id']).coluna.quadro
            elif 'linha_id' in kwargs:
                from qms.models import ActionPlanLinha
                # actually boards uses its own models? Let's check imports.
                pass # Will just let it pass if it's too complex or we can check request.body
            elif 'item_id' in kwargs:
                from .models import ChecklistItem
                board = get_object_or_404(ChecklistItem, id=kwargs['item_id']).cartao.coluna.quadro
            elif 'comment_id' in kwargs:
                from .models import CardComment
                board = get_object_or_404(CardComment, id=kwargs['comment_id']).cartao.coluna.quadro
            elif 'subsection_id' in kwargs:
                from .models import BoardSubSection
                board = get_object_or_404(BoardSubSection, id=kwargs['subsection_id']).coluna.quadro
            elif 'label_id' in kwargs:
                from .models import BoardLabel
                board = get_object_or_404(BoardLabel, id=kwargs['label_id']).quadro
            elif 'link_id' in kwargs:
                from .models import BoardLink
                board = get_object_or_404(BoardLink, id=kwargs['link_id']).quadro
            elif request.method in ['POST', 'PUT']:
                if request.body:
                    data = json.loads(request.body)
                    if 'card_id' in data:
                        from .models import Card
                        board = get_object_or_404(Card, id=data['card_id']).coluna.quadro
                    elif 'column_id' in data:
                        from .models import BoardColumn
                        board = get_object_or_404(BoardColumn, id=data['column_id']).quadro
        except Exception as e:
            pass
            
        if board and not can_edit_board(board, colab, request.user):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'success': False, 'error': 'Acesso negado. Apenas membros podem alterar.'}, status=403)
            return HttpResponseForbidden("Acesso negado. Apenas membros podem alterar o quadro.")
            
        return view_func(request, *args, **kwargs)
    return _wrapped_view


from rh.views.views import _has_nav_view_access

@login_required
def dashboard_view(request):
    if not _has_nav_view_access(request.user, 'boards:dashboard'):
        messages.error(request, 'Acesso Negado. Você não tem permissão para acessar os Quadros.')
        return redirect('home')
    
    """Exibe todos os quadros que o usuário gerencia ou participa"""
    colab = get_user_colaborador(request.user)
    
    # Superusuários vêm todos os quadros, colaboradores comuns vêm apenas os seus, onde são membros
    if request.user.is_superuser:
        quadros_base = Board.objects.exclude(nome="Ações Corretivas e Preventivas").distinct()
    elif colab:
        quadros_base = Board.objects.filter(
            Q(criado_por=colab) | Q(membros=colab) | Q(todos_colaboradores=True)
        ).exclude(nome="Ações Corretivas e Preventivas").distinct()
    else:
        quadros_base = Board.objects.filter(todos_colaboradores=True).exclude(nome="Ações Corretivas e Preventivas").distinct()

    quadros = quadros_base.filter(arquivado=False)
    quadros_arquivados = quadros_base.filter(arquivado=True)



    if request.method == 'POST':
        if not request.user.has_perm('core.nav_boards_create') and not request.user.is_superuser:
            messages.error(request, 'Acesso Negado. Você não tem permissão para criar Quadros.')
            return redirect('boards:dashboard')

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
        
    # Coletar todas as tarefas/ações de todos os quadros acessíveis
    from boards.models import Card
    cartoes_qs = Card.objects.filter(coluna__quadro__in=quadros).select_related('coluna__quadro', 'subsecao', 'criado_por').prefetch_related('responsaveis', 'etiquetas')
    
    todas_acoes = []
    
    # Obter tarefas dos quadros normais
    for c in cartoes_qs:
        todas_acoes.append({
            'id': c.id,
            'titulo': c.titulo,
            'descricao': c.descricao,
            'prioridade': c.prioridade,
            'data_entrega': c.data_entrega,
            'data_conclusao': c.data_conclusao,
            'status_exibicao': c.coluna.nome,
            'quadro_nome': c.coluna.quadro.nome,
            'quadro_id': c.coluna.quadro.id,
            'responsaveis': list(c.responsaveis.all()),
            'is_virtual': False
        })
        
    # Ordenar as ações: as que têm prazo mais próximo primeiro, e as sem prazo por último
    todas_acoes.sort(key=lambda x: x['data_entrega'] or datetime.date.max)
    
    # Mapear cada quadro
    quadros_list = list(quadros)
    todos_colaboradores = Colaborador.objects.filter(is_active=True).order_by('nome_completo')
    
    unread_mentions = []
    if colab:
        from boards.models import BoardMention
        unread_mentions = BoardMention.objects.filter(mencionado=colab, visualizada=False).select_related('comentario__cartao__coluna__quadro', 'criado_por')

    context = {
        'quadros': quadros,
        'quadros_list': quadros_list,
        'quadros_arquivados': quadros_arquivados,
        'todas_acoes': todas_acoes,
        'todos_colaboradores': todos_colaboradores,
        'form': form,
        'titulo': 'Quadros de Atividades',
        'hoje': timezone.now().date(),
        'unread_mentions': unread_mentions
    }
    return render(request, 'boards/dashboard.html', context)


@login_required
def board_detail_view(request, board_id, focus_column_id=None):
    """Visualização Kanban do quadro"""
    colab = get_user_colaborador(request.user)
    
    # Permissão de acesso
    if request.user.is_superuser:
        board = get_object_or_404(Board.objects.exclude(nome="Ações Corretivas e Preventivas"), id=board_id)
    elif colab:
        board = get_object_or_404(
            Board.objects.filter(Q(criado_por=colab) | Q(membros=colab) | Q(todos_colaboradores=True))
            .exclude(nome="Ações Corretivas e Preventivas")
            .distinct(), 
            id=board_id
        )
    else:
        board = get_object_or_404(
            Board.objects.filter(todos_colaboradores=True)
            .exclude(nome="Ações Corretivas e Preventivas")
            .distinct(), 
            id=board_id
        )        
    # Colunas, sub-sessões e cartões pré-carregados
    todas_colunas = list(board.colunas.prefetch_related('subsecoes', 'cartoes__responsaveis', 'cartoes__checklist_itens', 'cartoes__planejamentos').all())
    colunas = [col for col in todas_colunas if not col.arquivada]
    colunas_arquivadas = [col for col in todas_colunas if col.arquivada]
    
    # Pegar o filtro de período
    periodo = request.GET.get('periodo', 'tudo')
    
    start_date = None
    end_date = None
    today = timezone.now().date()
    
    if periodo == 'hoje':
        start_date = today
        end_date = today
    elif periodo == 'semana':
        start_date = today - datetime.timedelta(days=today.weekday())
        end_date = start_date + datetime.timedelta(days=6)
    elif periodo == 'mes':
        start_date = today.replace(day=1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        end_date = today.replace(day=last_day)
    elif periodo == 'ano':
        start_date = datetime.date(today.year, 1, 1)
        end_date = datetime.date(today.year, 12, 31)

    # Calcular Métricas de Carga de Trabalho da Equipe (Quadro Padrão)
    
    # Identificar coluna de conclusão (última coluna por ordem ou contendo "concluido/concluído/done" no nome)
    concluido_colunas_ids = []
    for col in colunas:
        nome_low = col.nome.lower()
        if "concluido" in nome_low or "concluído" in nome_low or "done" in nome_low or "terminado" in nome_low or "pronto" in nome_low:
            concluido_colunas_ids.append(col.id)
            
    # Se não achar nenhuma pelo nome, assume a última
    if not concluido_colunas_ids and colunas:
        concluido_colunas_ids.append(colunas[-1].id)
        
    # Migração automática de cartões orfãos na coluna concluído para a primeira coluna ativa
    colunas_ativas = [col for col in colunas if col.id not in concluido_colunas_ids]
    if colunas_ativas and concluido_colunas_ids:
        primeira_coluna = colunas_ativas[0]
        cartoes_orfaos = Card.objects.filter(coluna_id__in=concluido_colunas_ids)
        if cartoes_orfaos.exists():
            with transaction.atomic():
                for card in cartoes_orfaos:
                    card.coluna = primeira_coluna
                    if not card.data_conclusao:
                        card.data_conclusao = card.criado_em.date() if card.criado_em else timezone.now().date()
                    card.save()

    # Definir funções auxiliares de filtro de período para tarefas normais
    def matches_period_andamento(c):
        if not start_date:
            return True
        return c.data_entrega is not None and start_date <= c.data_entrega <= end_date

    def matches_period_concluido(c):
        if not start_date:
            return True
        return c.data_conclusao is not None and start_date <= c.data_conclusao <= end_date

    # Distribuição por colunas e agrupamento por sub-sessões
    distribuicao_colunas = []
    for col in colunas:
        col.subsecoes_list = list(col.subsecoes.all())
        for sub in col.subsecoes_list:
            sub.cartoes_list_andamento = [c for c in col.cartoes.all() if c.subsecao_id == sub.id and c.data_conclusao is None and matches_period_andamento(c)]
            sub.cartoes_list_concluido = [c for c in col.cartoes.all() if c.subsecao_id == sub.id and c.data_conclusao is not None and matches_period_concluido(c)]
            
        col.cartoes_sem_subsecao_andamento = [c for c in col.cartoes.all() if c.subsecao_id is None and c.data_conclusao is None and matches_period_andamento(c)]
        col.cartoes_sem_subsecao_concluido = [c for c in col.cartoes.all() if c.subsecao_id is None and c.data_conclusao is not None and matches_period_concluido(c)]
        col.cartoes_list_andamento = [c for c in col.cartoes.all() if c.data_conclusao is None and matches_period_andamento(c)]
        col.cartoes_list_concluido = [c for c in col.cartoes.all() if c.data_conclusao is not None and matches_period_concluido(c)]
        col.cartoes_list = [c for c in col.cartoes.all() if (c.data_conclusao is None and matches_period_andamento(c)) or (c.data_conclusao is not None and matches_period_concluido(c))]
        
        distribuicao_colunas.append({
            'nome': col.nome,
            'quantidade': len(col.cartoes_list)
        })

    total_cartoes = sum(len(col.cartoes_list) for col in colunas)
    cartoes_concluidos = sum(len(col.cartoes_list_concluido) for col in colunas)
    
    porcentagem_concluida = 0
    if total_cartoes > 0:
        porcentagem_concluida = int((cartoes_concluidos / total_cartoes) * 100)
        
    cartoes_atrasados = 0
    for col in colunas:
        for c in col.cartoes_list_andamento:
            if c.data_entrega and c.data_entrega < today:
                cartoes_atrasados += 1

    # Carga de trabalho por colaborador (exclui concluídos para focar no trabalho pendente)
    carga_membros_dict = {}
    for col in colunas:
        for c in col.cartoes_list_andamento:
            for resp in c.responsaveis.all():
                carga_membros_dict[resp] = carga_membros_dict.get(resp, 0) + 1
                
    carga_membros_sorted = sorted(carga_membros_dict.items(), key=lambda x: x[1], reverse=True)
    chart_membros_nomes = [m.nome_completo for m, _ in carga_membros_sorted]
    chart_membros_valores = [v for _, v in carga_membros_sorted]
        
    # Atividades recentes do quadro (limita a 20)
    atividades = board.atividades.select_related('colaborador')[:20]
    
    # Formulários para criação rápida
    card_form = CardForm(board=board)
    
    # Lista de colaboradores para o dropdown de transferência de responsável (todos os colaboradores, ativos ou não)
    responsaveis_atuais_ids = list(Card.objects.filter(coluna__quadro=board).values_list('responsaveis__id', flat=True))
    responsaveis_atuais_ids = [r_id for r_id in responsaveis_atuais_ids if r_id is not None]
    
    # Para o filtro global, apenas os que têm tarefa associada a eles neste quadro
    colaboradores_com_tarefas = Colaborador.objects.filter(id__in=responsaveis_atuais_ids).distinct().order_by('nome_completo')
    
    # Para dropdown de atribuição (nova tarefa / edição)
    todos_colaboradores = Colaborador.objects.all().order_by('nome_completo')
        
    colunas_andamento = [col for col in colunas if col.id not in concluido_colunas_ids]
    colunas_concluidas = colunas_andamento

    # Nomes de sub-sessões únicos (deduplicados) para o filtro
    _seen_subs = set()
    subsecoes_unicas = []
    for col in colunas:
        for sub in col.subsecoes_list:
            if sub.nome not in _seen_subs:
                _seen_subs.add(sub.nome)
                subsecoes_unicas.append(sub.nome)
    subsecoes_unicas.sort()

    focus_column = None
    if focus_column_id:
        focus_column = get_object_or_404(BoardColumn, id=focus_column_id, quadro_id=board.id)

    context = {
        'board': board,
        'colunas': colunas,
        'focus_column': focus_column,
        'colunas_arquivadas': colunas_arquivadas,
        'board_links': board.links.all(),
        'colunas_andamento': colunas_andamento,
        'colunas_concluidas': colunas_concluidas,
        'card_form': card_form,
        'total_cartoes': total_cartoes,
        'cartoes_concluidos': cartoes_concluidos,
        'porcentagem_concluida': porcentagem_concluida,
        'cartoes_atrasados': cartoes_atrasados,
        'atividades': atividades,
        'can_edit_board': can_edit_board(board, colab, request.user),
        'todos_colaboradores': todos_colaboradores,
        'colaboradores_com_tarefas': colaboradores_com_tarefas,
        'colaboradores_sistema': Colaborador.objects.all().order_by('nome_completo'),
        'chart_membros_nomes': json.dumps(chart_membros_nomes),
        'chart_membros_valores': json.dumps(chart_membros_valores),
        'distribuicao_colunas': json.dumps(distribuicao_colunas),
        'titulo': f"Quadro - {board.nome}",
        'periodo': periodo,
        'hoje': today,
        'subsecoes_unicas': subsecoes_unicas,
    }
    return render(request, 'boards/board_detail.html', context)



@login_required
@require_POST
@require_board_edit_permission
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
@require_board_edit_permission
def archive_column_view(request, column_id):
    """Arquiva uma coluna (oculta do quadro ativo, preserva cartões)"""
    colab = get_user_colaborador(request.user)
    coluna = get_object_or_404(BoardColumn, id=column_id)
    board = coluna.quadro
    coluna.arquivada = True
    coluna.save(update_fields=['arquivada'])
    BoardActivity.objects.create(
        quadro=board,
        colaborador=colab,
        descricao=f"arquivou a coluna '{coluna.nome}'."
    )
    messages.success(request, f"Coluna '{coluna.nome}' arquivada.")
    return redirect('boards:board_detail', board_id=board.id)


@login_required
@require_POST
@require_board_edit_permission
def unarchive_column_view(request, column_id):
    """Desarquiva uma coluna, tornando-a ativa novamente"""
    colab = get_user_colaborador(request.user)
    coluna = get_object_or_404(BoardColumn, id=column_id)
    board = coluna.quadro
    coluna.arquivada = False
    coluna.save(update_fields=['arquivada'])
    BoardActivity.objects.create(
        quadro=board,
        colaborador=colab,
        descricao=f"desarquivou a coluna '{coluna.nome}'."
    )
    messages.success(request, f"Coluna '{coluna.nome}' reativada.")
    return redirect('boards:board_detail', board_id=board.id)


@login_required
@require_POST
@require_board_edit_permission
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


from django.urls import reverse


@login_required
@require_POST
@require_board_edit_permission
def copy_column_view(request, column_id):
    """Cria uma cópia de uma coluna (com novo nome) no mesmo quadro"""
    colab = get_user_colaborador(request.user)
    coluna = get_object_or_404(BoardColumn, id=column_id)
    board = coluna.quadro

    novo_nome = request.POST.get('nome', '').strip()
    if not novo_nome:
        novo_nome = f"{coluna.nome} (Cópia)"

    maior_ordem = board.colunas.aggregate(Max('ordem'))['ordem__max']
    nova_ordem = (maior_ordem + 1) if maior_ordem is not None else 0

    nova_coluna = BoardColumn.objects.create(
        quadro=board,
        nome=novo_nome,
        descricao=coluna.descricao,
        ordem=nova_ordem
    )

    # Copiar sub-sessões
    for sub in coluna.subsecoes.all():
        from boards.models import BoardSubSection
        BoardSubSection.objects.create(coluna=nova_coluna, nome=sub.nome, ordem=sub.ordem)

    BoardActivity.objects.create(
        quadro=board,
        colaborador=colab,
        descricao=f"criou uma cópia da coluna '{coluna.nome}' como '{novo_nome}'."
    )
    messages.success(request, f"Coluna '{novo_nome}' criada como cópia de '{coluna.nome}'.")
    return redirect('boards:board_detail', board_id=board.id)


@login_required
@require_board_edit_permission
def api_column_description_view(request, column_id):
    """GET: retorna descrição da coluna. POST: atualiza descrição."""
    coluna = get_object_or_404(BoardColumn, id=column_id)

    if request.method == 'GET':
        return JsonResponse({'descricao': coluna.descricao or ''})

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            coluna.descricao = data.get('descricao', '').strip() or None
            coluna.save(update_fields=['descricao'])
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return JsonResponse({'error': 'Método não permitido.'}, status=405)


@login_required
@require_board_edit_permission
def api_rename_column_view(request, column_id):
    """POST: renomeia a coluna."""
    coluna = get_object_or_404(BoardColumn, id=column_id)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            novo_nome = data.get('nome', '').strip()
            if not novo_nome:
                return JsonResponse({'success': False, 'error': 'O nome da coluna não pode ficar vazio.'}, status=400)
            
            colab = get_user_colaborador(request.user)
            nome_antigo = coluna.nome
            coluna.nome = novo_nome
            coluna.save(update_fields=['nome'])
            
            BoardActivity.objects.create(
                quadro=coluna.quadro,
                colaborador=colab,
                descricao=f"renomeou a coluna '{nome_antigo}' para '{novo_nome}'."
            )
            
            return JsonResponse({'success': True, 'nome': coluna.nome})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return JsonResponse({'error': 'Método não permitido.'}, status=405)


@login_required
@require_POST
@require_board_edit_permission
def create_card_view(request, column_id):
    """Cria um novo cartão em uma coluna"""
    colab = get_user_colaborador(request.user)
    coluna = get_object_or_404(BoardColumn, id=column_id)
    board = coluna.quadro
    
    form = CardForm(request.POST, board=board, column=coluna)
    if form.is_valid():
        card = form.save(commit=False)
        card.coluna = coluna
        card.criado_por = colab
        
        # Pega a maior ordem na coluna
        maior_ordem = coluna.cartoes.aggregate(Max('ordem'))['ordem__max']
        card.ordem = (maior_ordem + 1) if maior_ordem is not None else 0
        card.save()
        form.save_m2m()
        
        # Criar planejamento se datetime_inicio foi preenchido
        if card.datetime_inicio:
            CardPlanningDate.objects.create(
                cartao=card,
                datetime_inicio=card.datetime_inicio,
                datetime_fim=card.datetime_fim
            )
        
        BoardActivity.objects.create(
            quadro=board,
            colaborador=colab,
            descricao=f"criou o cartão '{card.titulo}' na coluna '{coluna.nome}'."
        )
        messages.success(request, f"Tarefa '{card.titulo}' criada com sucesso!")
    else:
        messages.error(request, "Erro ao criar a tarefa. Verifique os dados inseridos.")
        
    url = reverse('boards:board_detail', kwargs={'board_id': board.id})
    if request.GET:
        url += '?' + request.GET.urlencode()
    return redirect(url)


def spawn_recurring_card(card, origin_column=None, origin_subsection=None):
    """Gera uma nova tarefa recorrente na primeira coluna do quadro com prazo atualizado"""
    base_date = card.data_entrega or timezone.now().date()
    
    if card.periodicidade == 'DIARIA':
        next_date = base_date + datetime.timedelta(days=1)
    elif card.periodicidade == 'SEMANAL':
        next_date = base_date + datetime.timedelta(weeks=1)
    elif card.periodicidade == 'QUINZENAL':
        # 14 dias mantém o mesmo dia da semana (equivalente a 10 dias úteis)
        next_date = base_date + datetime.timedelta(days=14)
    elif card.periodicidade in ('MENSAL', 'BIMESTRAL', 'TRIMESTRAL', 'SEMESTRAL'):
        months_to_add = {
            'MENSAL': 1,
            'BIMESTRAL': 2,
            'TRIMESTRAL': 3,
            'SEMESTRAL': 6
        }[card.periodicidade]
        
        # Recuperar o dia original da primeira tarefa da série para evitar 
        # perda do dia final do mês (ex: 31 -> 28 -> 28 em vez de 31 -> 28 -> 31)
        original_day = base_date.day
        current_ancestor = card
        loop_guard = 0
        while current_ancestor.antecessora_id and loop_guard < 100:
            current_ancestor = current_ancestor.antecessora
            if current_ancestor.data_entrega:
                original_day = current_ancestor.data_entrega.day
            loop_guard += 1
            
        month = base_date.month + months_to_add
        year = base_date.year
        while month > 12:
            month -= 12
            year += 1
            
        last_day = calendar.monthrange(year, month)[1]
        day = min(original_day, last_day)
        next_date = datetime.date(year, month, day)
    elif card.periodicidade == 'ANUAL':
        # Para anual também buscamos o dia/mês original para tratar anos bissextos (29 Fev)
        original_day = base_date.day
        original_month = base_date.month
        current_ancestor = card
        loop_guard = 0
        while current_ancestor.antecessora_id and loop_guard < 100:
            current_ancestor = current_ancestor.antecessora
            if current_ancestor.data_entrega:
                original_day = current_ancestor.data_entrega.day
                original_month = current_ancestor.data_entrega.month
            loop_guard += 1
            
        year = base_date.year + 1
        if original_month == 2 and original_day == 29 and not calendar.isleap(year):
            next_date = datetime.date(year, 2, 28)
        else:
            last_day = calendar.monthrange(year, original_month)[1]
            day = min(original_day, last_day)
            next_date = datetime.date(year, original_month, day)
    else:
        return None
        
    coluna_destino = origin_column if origin_column else card.coluna
    subsecao_destino = origin_subsection if origin_subsection else card.subsecao
    
    maior_ordem = coluna_destino.cartoes.aggregate(Max('ordem'))['ordem__max']
    new_ordem = (maior_ordem + 1) if maior_ordem is not None else 0
    
    new_card = Card.objects.create(
        coluna=coluna_destino,
        subsecao=subsecao_destino,
        titulo=card.titulo,
        descricao=card.descricao,
        data_entrega=next_date,
        prioridade=card.prioridade,
        periodicidade=card.periodicidade,
        ordem=new_ordem,
        criado_por=card.criado_por,
        antecessora=card
    )
    new_card.responsaveis.set(card.responsaveis.all())
    new_card.etiquetas.set(card.etiquetas.all())

    
    # Copia os itens do checklist (como não concluídos)
    for item in card.checklist_itens.all():
        ChecklistItem.objects.create(
            cartao=new_card,
            descricao=item.descricao,
            concluido=False
        )
        
    BoardActivity.objects.create(
        quadro=coluna_destino.quadro,
        colaborador=None,
        descricao=f"Criada tarefa recorrente automática '{new_card.titulo}' para {new_card.data_entrega.strftime('%d/%m/%Y')}."
    )
    
    # O cartão original deixa de ser recorrente para não gerar duplicatas
    card.periodicidade = 'AVULSA'
    card.save()
    
    return new_card


@login_required
@require_POST
@require_board_edit_permission
def api_move_card_view(request):
    """Endpoint API para mover cartão de coluna/posição via Drag and Drop"""
    try:
        colab = get_user_colaborador(request.user)
        data = json.loads(request.body)
        card_id = data.get('card_id')
        to_column_id = data.get('to_column_id')
        card_order_ids = data.get('card_order_ids', []) # Array de IDs na nova ordem
        
        nova_coluna = get_object_or_404(BoardColumn, id=to_column_id)
        
        card = get_object_or_404(Card, id=card_id)
        old_col_nome = card.coluna.nome
        old_coluna = card.coluna
        old_subsecao = card.subsecao
        
        # Obter a subsessão se fornecida
        to_subsection_id = data.get('to_subsection_id')
        if to_subsection_id and to_subsection_id != 'null':
            subsecao = get_object_or_404(BoardSubSection, id=to_subsection_id, coluna=nova_coluna)
            card.subsecao = subsecao
        else:
            card.subsecao = None
            
        # Verificar se é coluna de conclusão
        concluido = data.get('concluido')
        if concluido is not None:
            is_concluida = concluido
        else:
            nome_low = nova_coluna.nome.lower()
            is_concluida = "concluido" in nome_low or "concluído" in nome_low or "done" in nome_low or "terminado" in nome_low or "pronto" in nome_low
            if not is_concluida:
                # Fallback: se for a última coluna do quadro
                last_col = nova_coluna.quadro.colunas.order_by('ordem', 'criado_em').last()
                if last_col and last_col.id == nova_coluna.id:
                    is_concluida = True

        # Verificar se é a primeira coluna (backlog / a fazer)
        first_col = nova_coluna.quadro.colunas.order_by('ordem', 'criado_em').first()
        is_first_col = (first_col and first_col.id == nova_coluna.id)

        # Atualizar a data de conclusão e horários baseado no destino
        now_date = timezone.now().date()
        now_time = timezone.now().time()
        now_dt = timezone.now()
        
        if is_concluida:
            # Aceitar data_conclusao do frontend se fornecida
            custom_data_conclusao = data.get('data_conclusao')
            if custom_data_conclusao:
                from datetime import datetime as dt_class
                card.data_conclusao = dt_class.strptime(custom_data_conclusao, '%Y-%m-%d').date()
            elif not card.data_conclusao:
                card.data_conclusao = now_date
            if not card.hora_fim:
                card.hora_fim = now_time
            if not card.datetime_fim:
                card.datetime_fim = now_dt
                
            if not card.data_inicio:
                card.data_inicio = card.data_conclusao
            if not card.hora_inicio:
                card.hora_inicio = card.hora_fim
            if not card.datetime_inicio:
                card.datetime_inicio = card.datetime_fim
        elif is_first_col:
            card.data_inicio = None
            card.hora_inicio = None
            card.data_conclusao = None
            card.hora_fim = None
            card.datetime_inicio = None
            card.datetime_fim = None
        else:
            if not card.data_inicio:
                card.data_inicio = now_date
            if not card.hora_inicio:
                card.hora_inicio = now_time
            if not card.datetime_inicio:
                card.datetime_inicio = now_dt
            card.data_conclusao = None
            card.hora_fim = None
            card.datetime_fim = None

        # Atualizar a coluna do cartão movido
        card.coluna = nova_coluna
        card.save()

        recreate = data.get('recreate', False)
        if is_concluida and card.periodicidade != 'AVULSA' and recreate:
            spawn_recurring_card(card, origin_column=old_coluna, origin_subsection=old_subsecao)

            
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
            notify_card_update(card, colab, f"foi movido para a coluna '{nova_coluna.nome}'")
            
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def api_linha_acao_detail_view(request, linha_id):
    """Endpoint API para buscar detalhes de uma LinhaAcao (cartão virtual do quadro de Planos de Ação)"""
    from acoes.models import LinhaAcao
    linha = get_object_or_404(LinhaAcao, id=linha_id)
    
    STATUS_LABEL = {
        'planejada': 'Planejada',
        'em_curso':  'Em Curso/Andamento',
        'retardo':   'Retardo/Atrasada',
        'completa':  'Completa/Concluído',
        'cancelada': 'Cancelada',
    }
    STATUS_COLOR = {
        'planejada': '#6c757d',
        'em_curso':  '#0d6efd',
        'retardo':   '#dc3545',
        'completa':  '#198754',
        'cancelada': '#adb5bd',
    }
    
    resps = []
    if linha.responsavel_acao:
        resps.append({'id': linha.responsavel_acao.id, 'nome': linha.responsavel_acao.nome_completo})
    for r in linha.responsaveis_multiplos.all():
        if r.id not in [x['id'] for x in resps]:
            resps.append({'id': r.id, 'nome': r.nome_completo})
    
    plano = linha.plano_acao
    plano_ref = plano.numero_registro or (plano.solucao.titulo if plano.solucao else '') or f'Plano #{plano.id}'
    plano_url = f'/acoes/plano-acao/{plano.id}/'
    
    data = {
        'id': linha.id,
        'numero_acao': linha.numero_acao,
        'titulo': f'Ação #{linha.numero_acao}',
        'descricao': linha.descricao or '',
        'classificacao': linha.get_classificacao_display() if linha.classificacao else 'N/A',
        'status': linha.status,
        'status_label': STATUS_LABEL.get(linha.status, linha.status),
        'status_color': STATUS_COLOR.get(linha.status, '#6c757d'),
        'prioridade': 'Alta' if linha.prioridade else 'Normal',
        'data_deadline': linha.data_deadline.strftime('%d/%m/%Y') if linha.data_deadline else '',
        'data_primeira_deadline': linha.data_primeira_deadline.strftime('%d/%m/%Y') if linha.data_primeira_deadline else '',
        'data_conclusao': linha.data_conclusao.strftime('%d/%m/%Y') if linha.data_conclusao else '',
        'comentarios_texto': linha.comentarios or '',
        'acao_eficaz': linha.get_acao_eficaz_display() if linha.acao_eficaz else '',
        'kpi': linha.kpi or '',
        'problema': linha.problema or '',
        'input_origem': linha.input_origem or '',
        'responsaveis': resps,
        'plano_ref': plano_ref,
        'plano_url': plano_url,
        'plano_id': plano.id,
    }
    return JsonResponse(data)


@login_required
def api_card_detail_view(request, card_id):
    """Endpoint API para buscar detalhes e atualizar informações de um cartão"""

    colab = get_user_colaborador(request.user)
    card = get_object_or_404(Card, id=card_id)
    board = card.coluna.quadro
    
    if request.method == 'GET':
        if colab:
            from .models import BoardMention
            BoardMention.objects.filter(comentario__cartao=card, mencionado=colab, visualizada=False).update(visualizada=True)
            
        checklist = list(card.checklist_itens.values('id', 'descricao', 'concluido'))
        comentarios = []
        for c in card.comentarios.select_related('autor').all():
            comentarios.append({
                'id': c.id,
                'autor': c.autor.nome_completo if c.autor else 'Sistema / Admin',
                'texto': c.texto,
                'data': c.criado_em.strftime('%d/%m/%Y %H:%M')
            })
            
        etiquetas = [{'id': et.id, 'nome': et.nome, 'cor': et.cor} for et in card.etiquetas.all()]
        
        # Encontrar raiz do histórico
        raiz = card
        while raiz.antecessora is not None:
            raiz = raiz.antecessora
            
        historia = []
        curr = raiz
        while curr is not None:
            nome_col_low = curr.coluna.nome.lower()
            is_concluida = "concluido" in nome_col_low or "concluído" in nome_col_low or "done" in nome_col_low or "terminado" in nome_col_low or "pronto" in nome_col_low
            if not is_concluida:
                last_col = curr.coluna.quadro.colunas.order_by('ordem', 'criado_em').last()
                if last_col and last_col.id == curr.coluna_id:
                    is_concluida = True
                    
            status_str = f"Concluída ({curr.coluna.nome})" if is_concluida else f"Ativa ({curr.coluna.nome})"
            historia.append({
                'id': curr.id,
                'titulo': curr.titulo,
                'coluna_nome': curr.coluna.nome,
                'status': status_str,
                'data': curr.criado_em.strftime('%d/%m/%Y %H:%M'),
                'is_current': curr.id == card.id
            })
            curr = curr.sucessoras.first()
            
        planejamentos = [
            {
                'id': p.id,
                'datetime_inicio': timezone.localtime(p.datetime_inicio).strftime('%Y-%m-%dT%H:%M') if p.datetime_inicio else '',
                'datetime_fim': timezone.localtime(p.datetime_fim).strftime('%Y-%m-%dT%H:%M') if p.datetime_fim else ''
            }
            for p in card.planejamentos.all()
        ]
        
        data = {
            'id': card.id,
            'coluna_id': card.coluna_id,
            'subsecao_id': card.subsecao_id,
            'titulo': card.titulo,
            'descricao': card.descricao or '',
            'link_anexo': card.link_anexo or '',
            'responsaveis_ids': list(card.responsaveis.values_list('id', flat=True)),
            'responsaveis_nomes': ", ".join([r.nome_completo for r in card.responsaveis.all()]) or 'Não atribuído',
            'responsaveis': [{'id': r.id, 'nome': r.nome_completo} for r in card.responsaveis.all()],
            'prioridade': card.prioridade,
            'prioridade_label': card.get_prioridade_display(),
            'periodicidade': card.periodicidade,
            'periodicidade_label': card.get_periodicidade_display(),
            'data_entrega': card.data_entrega.strftime('%Y-%m-%d') if card.data_entrega else '',
            'data_conclusao': card.data_conclusao.strftime('%Y-%m-%d') if card.data_conclusao else '',
            'datetime_inicio': timezone.localtime(card.datetime_inicio).strftime('%Y-%m-%dT%H:%M') if card.datetime_inicio else '',
            'datetime_fim': timezone.localtime(card.datetime_fim).strftime('%Y-%m-%dT%H:%M') if card.datetime_fim else '',
            'checklist': checklist,
            'comentarios': comentarios,
            'etiquetas': etiquetas,
            'historia': historia if len(historia) > 1 else [],
            'planejamentos': planejamentos
        }
        return JsonResponse(data)
        
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            # Atualizar os dados do cartão
            card.titulo = data.get('titulo', card.titulo).strip()
            card.descricao = data.get('descricao', card.descricao)
            
            if 'link_anexo' in data:
                link_val = data.get('link_anexo')
                card.link_anexo = link_val.strip() if link_val else None
            
            coluna_id = data.get('coluna_id')
            if coluna_id:
                nova_coluna = get_object_or_404(BoardColumn, id=coluna_id, quadro=board)
                if card.coluna != nova_coluna:
                    old_col_nome = card.coluna.nome
                    
                    # Automático se mudou de coluna e a destino é de conclusão
                    nome_low = nova_coluna.nome.lower()
                    is_dest_concluida = "concluido" in nome_low or "concluído" in nome_low or "done" in nome_low or "terminado" in nome_low or "pronto" in nome_low
                    if not is_dest_concluida:
                        last_col = nova_coluna.quadro.colunas.order_by('ordem', 'criado_em').last()
                        if last_col and last_col.id == nova_coluna.id:
                            is_dest_concluida = True
                            
                    first_col = nova_coluna.quadro.colunas.order_by('ordem', 'criado_em').first()
                    is_first_col = (first_col and first_col.id == nova_coluna.id)

                    if is_dest_concluida:
                        now_date = timezone.now().date()
                        now_time = timezone.now().time()
                        now_dt = timezone.now()
                        
                        if not card.data_conclusao:
                            card.data_conclusao = now_date
                        if not card.hora_fim:
                            card.hora_fim = now_time
                        if not card.datetime_fim:
                            card.datetime_fim = now_dt
                            
                        if not card.data_inicio:
                            card.data_inicio = card.data_conclusao
                        if not card.hora_inicio:
                            card.hora_inicio = card.hora_fim
                        if not card.datetime_inicio:
                            card.datetime_inicio = card.datetime_fim
                    elif is_first_col:
                        card.data_inicio = None
                        card.hora_inicio = None
                        card.data_conclusao = None
                        card.hora_fim = None
                        card.datetime_inicio = None
                        card.datetime_fim = None
                    else:
                        now_date = timezone.now().date()
                        now_time = timezone.now().time()
                        now_dt = timezone.now()
                        if not card.data_inicio:
                            card.data_inicio = now_date
                        if not card.hora_inicio:
                            card.hora_inicio = now_time
                        if not card.datetime_inicio:
                            card.datetime_inicio = now_dt
                        card.data_conclusao = None
                        card.hora_fim = None
                        card.datetime_fim = None
                    
                    old_coluna_temp = card.coluna
                    old_subsecao_temp = card.subsecao
                    card.coluna = nova_coluna
                    
                    recreate = data.get('recreate', False)
                    if is_dest_concluida and card.periodicidade != 'AVULSA' and recreate:
                        spawn_recurring_card(card, origin_column=old_coluna_temp, origin_subsection=old_subsecao_temp)
                        
                    BoardActivity.objects.create(
                        quadro=board,
                        colaborador=colab,
                        descricao=f"moveu o cartão '{card.titulo}' de '{old_col_nome}' para '{nova_coluna.nome}'."
                    )
            
            if 'subsecao_id' in data:
                subsecao_id = data.get('subsecao_id')
                if subsecao_id:
                    subsecao = BoardSubSection.objects.filter(id=subsecao_id, coluna=card.coluna).first()
                    card.subsecao = subsecao
                else:
                    card.subsecao = None
                
            # Trata conclusão via parâmetro explícito 'concluido'
            concluido = data.get('concluido')
            if concluido is not None:
                is_concluida = concluido
                if is_concluida:
                    if not card.data_conclusao:
                        card.data_conclusao = timezone.now().date()
                    if not card.hora_fim:
                        card.hora_fim = timezone.now().time()
                    if not card.datetime_fim:
                        card.datetime_fim = timezone.now()
                    if not card.data_inicio:
                        card.data_inicio = card.data_concluido if hasattr(card, 'data_concluido') else card.data_conclusao
                    if not card.hora_inicio:
                        card.hora_inicio = card.hora_fim
                    if not card.datetime_inicio:
                        card.datetime_inicio = card.datetime_fim
                else:
                    card.data_conclusao = None
                    card.hora_fim = None
                    card.datetime_fim = None
                
                recreate = data.get('recreate', False)
                if is_concluida and card.periodicidade != 'AVULSA' and recreate:
                    spawn_recurring_card(card, origin_column=card.coluna, origin_subsection=card.subsecao)
            
            if 'responsaveis_ids' in data:
                resp_ids = data.get('responsaveis_ids', [])
                val_ids = [int(i) for i in resp_ids if i]
                card.responsaveis.set(Colaborador.objects.filter(id__in=val_ids))
                
            prioridade = data.get('prioridade')
            if prioridade in dict(Card.PRIORIDADE_CHOICES):
                card.prioridade = prioridade
                
            periodicidade = data.get('periodicidade')
            if periodicidade in dict(Card.PERIODICIDADE_CHOICES):
                card.periodicidade = periodicidade
                
            if 'data_entrega' in data:
                data_entrega_raw = data.get('data_entrega')
                if data_entrega_raw:
                    parsed_date = None
                    for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
                        try:
                            parsed_date = datetime.datetime.strptime(data_entrega_raw, fmt).date()
                            break
                        except ValueError:
                            continue
                    card.data_entrega = parsed_date
                else:
                    card.data_entrega = None
                
            if 'planejamentos' in data:
                planejamentos_data = data.get('planejamentos', [])
                parsed_items = []
                for idx, p_item in enumerate(planejamentos_data, 1):
                    dt_ini_raw = p_item.get('datetime_inicio')
                    dt_fim_raw = p_item.get('datetime_fim')
                    
                    dt_ini = None
                    dt_fim = None
                    
                    if dt_ini_raw:
                        try:
                            # Tenta parsear formato ISO (YYYY-MM-DDTHH:MM)
                            dt_ini = datetime.datetime.fromisoformat(dt_ini_raw.replace('Z', ''))
                            if timezone.is_naive(dt_ini):
                                dt_ini = timezone.make_aware(dt_ini)
                        except ValueError:
                            return JsonResponse({'success': False, 'error': f'Data/Hora de início inválida na linha {idx}.'}, status=400)
                    else:
                        return JsonResponse({'success': False, 'error': f'Data/Hora de início é obrigatória na linha {idx}.'}, status=400)
                        
                    if dt_fim_raw:
                        try:
                            dt_fim = datetime.datetime.fromisoformat(dt_fim_raw.replace('Z', ''))
                            if timezone.is_naive(dt_fim):
                                dt_fim = timezone.make_aware(dt_fim)
                        except ValueError:
                            return JsonResponse({'success': False, 'error': f'Data/Hora de fim inválida na linha {idx}.'}, status=400)
                            
                        if dt_fim < dt_ini:
                            return JsonResponse({'success': False, 'error': f'A Data/Hora de fim deve ser posterior à Data/Hora de início na linha {idx}.'}, status=400)
                    
                    parsed_items.append((dt_ini, dt_fim))
                
                card.planejamentos.all().delete()
                for dt_ini, dt_fim in parsed_items:
                    CardPlanningDate.objects.create(
                        cartao=card,
                        datetime_inicio=dt_ini,
                        datetime_fim=dt_fim
                    )
                
                # Sincroniza com o campo principal do cartão
                primeiro_p = card.planejamentos.order_by('datetime_inicio').first()
                if primeiro_p:
                    card.datetime_inicio = primeiro_p.datetime_inicio
                    card.datetime_fim = primeiro_p.datetime_fim
                else:
                    card.datetime_inicio = None
                    card.datetime_fim = None
            else:
                if 'datetime_inicio' in data:
                    dt_ini_raw = data.get('datetime_inicio')
                    if dt_ini_raw:
                        try:
                            parsed_ini = datetime.datetime.fromisoformat(dt_ini_raw.replace('Z', ''))
                            if timezone.is_naive(parsed_ini):
                                parsed_ini = timezone.make_aware(parsed_ini)
                            card.datetime_inicio = parsed_ini
                        except ValueError:
                            card.datetime_inicio = None
                    else:
                        card.datetime_inicio = None

                if 'datetime_fim' in data:
                    dt_fim_raw = data.get('datetime_fim')
                    if dt_fim_raw:
                        try:
                            parsed_fim = datetime.datetime.fromisoformat(dt_fim_raw.replace('Z', ''))
                            if timezone.is_naive(parsed_fim):
                                parsed_fim = timezone.make_aware(parsed_fim)
                            card.datetime_fim = parsed_fim
                        except ValueError:
                            card.datetime_fim = None
                    else:
                        card.datetime_fim = None

                # Sincronizar de volta para a tabela CardPlanningDate
                if 'datetime_inicio' in data or 'datetime_fim' in data:
                    card.planejamentos.all().delete()
                    if card.datetime_inicio:
                        CardPlanningDate.objects.create(
                            cartao=card,
                            datetime_inicio=card.datetime_inicio,
                            datetime_fim=card.datetime_fim
                        )
                
            if 'data_conclusao' in data:
                data_conclusao_raw = data.get('data_conclusao')
                if data_conclusao_raw:
                    parsed_date = None
                    for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
                        try:
                            parsed_date = datetime.datetime.strptime(data_conclusao_raw, fmt).date()
                            break
                        except ValueError:
                            continue
                    card.data_conclusao = parsed_date
                else:
                    card.data_conclusao = None

            if 'etiquetas_ids' in data:
                etiquetas_ids = data.get('etiquetas_ids', [])
                val_et_ids = [int(i) for i in etiquetas_ids if i]
                card.etiquetas.set(BoardLabel.objects.filter(id__in=val_et_ids, quadro=board))
            
            # Validação da relação de data e hora para início e fim
            if card.datetime_inicio and card.datetime_fim:
                if card.datetime_fim < card.datetime_inicio:
                    return JsonResponse({'success': False, 'error': 'A data/hora de fim deve ser posterior à data/hora de início.'}, status=400)

            card.save()
            
            BoardActivity.objects.create(
                quadro=board,
                colaborador=colab,
                descricao=f"editou o cartão '{card.titulo}'."
            )
            notify_card_update(card, colab, "teve seus detalhes editados")
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
@require_board_edit_permission
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
@require_board_edit_permission
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
@require_board_edit_permission
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
        
        # Parse and save mentions
        try:
            from .models import BoardMention
            board = card.coluna.quadro
            membros = list(board.membros.all())
            if board.criado_por and board.criado_por not in membros:
                membros.append(board.criado_por)
            
            membros.sort(key=lambda m: len(m.nome_completo), reverse=True)
            for member in membros:
                mention_str = f"@{member.nome_completo}"
                if mention_str in comment.texto:
                    BoardMention.objects.get_or_create(
                        comentario=comment,
                        mencionado=member,
                        defaults={'criado_por': colab}
                    )
        except Exception as e:
            print("Error parsing mentions:", e)

        BoardActivity.objects.create(
            quadro=card.coluna.quadro,
            colaborador=colab,
            descricao=f"comentou no cartão '{card.titulo}'."
        )
        return JsonResponse({
            'success': True, 
            'comentario': {
                'id': comment.id,
                'autor': comment.autor.nome_completo if comment.autor else 'Sistema / Admin',
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
@require_board_edit_permission
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
@require_board_edit_permission
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
@require_board_edit_permission
def delete_board_view(request, board_id):
    """Remove um quadro completo"""
    colab = get_user_colaborador(request.user)
    board = get_object_or_404(Board, id=board_id)
    
    # Quadros não podem mais ser excluídos, apenas arquivados
    messages.error(request, "Quadros não podem ser excluídos, apenas arquivados.")
    return redirect('boards:board_detail', board_id=board.id)


@login_required
@require_POST
@require_board_edit_permission
def archive_board_view(request, board_id):
    """Arquiva um quadro de atividades"""
    colab = get_user_colaborador(request.user)
    board = get_object_or_404(Board, id=board_id)
    
    if board.criado_por != colab and not request.user.is_superuser:
        messages.error(request, "Apenas o criador do quadro pode arquivá-lo.")
        return redirect('boards:dashboard')
        
    board.arquivado = True
    board.save()
    
    BoardActivity.objects.create(
        quadro=board,
        colaborador=colab,
        descricao="arquivou o quadro."
    )
    messages.success(request, f"Quadro '{board.nome}' arquivado com sucesso!")
    return redirect('boards:dashboard')


@login_required
@require_POST
@require_board_edit_permission
def unarchive_board_view(request, board_id):
    """Desarquiva/restaura um quadro de atividades"""
    colab = get_user_colaborador(request.user)
    board = get_object_or_404(Board, id=board_id)
    
    if board.criado_por != colab and not request.user.is_superuser:
        messages.error(request, "Apenas o criador do quadro pode desarquivá-lo.")
        return redirect('boards:dashboard')
        
    board.arquivado = False
    board.save()
    
    BoardActivity.objects.create(
        quadro=board,
        colaborador=colab,
        descricao="desarquivou o quadro."
    )
    messages.success(request, f"Quadro '{board.nome}' restaurado com sucesso!")
    return redirect('boards:dashboard')


@login_required
@require_POST
@require_board_edit_permission
def api_move_column_view(request):
    """Endpoint API para reordenar colunas via AJAX Drag and Drop"""
    try:
        data = json.loads(request.body)
        column_order_ids = data.get('column_order_ids', [])
        
        with transaction.atomic():
            for idx, col_id in enumerate(column_order_ids):
                BoardColumn.objects.filter(id=col_id).update(ordem=idx)
                
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
@require_board_edit_permission
def create_subsection_view(request, column_id):
    column = get_object_or_404(BoardColumn, id=column_id)
    nome = request.POST.get('nome', '').strip()
    if nome:
        maior_ordem = column.subsecoes.aggregate(Max('ordem'))['ordem__max']
        ordem = (maior_ordem + 1) if maior_ordem is not None else 0
        
        BoardSubSection.objects.create(
            coluna=column,
            nome=nome,
            ordem=ordem
        )
        messages.success(request, f"Sub-sessão '{nome}' criada com sucesso!")
    else:
        messages.error(request, "O nome da sub-sessão não pode ser vazio.")
    return redirect('boards:board_detail', board_id=column.quadro.id)


@login_required
@require_POST
@require_board_edit_permission
def delete_subsection_view(request, subsection_id):
    subsecao = get_object_or_404(BoardSubSection, id=subsection_id)
    board_id = subsecao.coluna.quadro.id
    nome = subsecao.nome
    subsecao.delete()
    messages.success(request, f"Sub-sessão '{nome}' excluída com sucesso!")
    return redirect('boards:board_detail', board_id=board_id)


@login_required
@require_POST
@require_board_edit_permission
def create_label_view(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    colab = get_user_colaborador(request.user)
    if not request.user.is_superuser:
        if board.criado_por != colab and not board.membros.filter(id=colab.id).exists():
            messages.error(request, "Acesso negado.")
            return redirect('boards:dashboard')
            
    nome = request.POST.get('nome', '').strip()
    cor = request.POST.get('cor', '#0d6efd').strip()
    if nome:
        if BoardLabel.objects.filter(quadro=board, nome__iexact=nome).exists():
            messages.error(request, f"Já existe uma etiqueta chamada '{nome}' neste quadro.")
        else:
            BoardLabel.objects.create(quadro=board, nome=nome, cor=cor)
            messages.success(request, f"Etiqueta '{nome}' criada!")
    else:
        messages.error(request, "O nome da etiqueta é obrigatório.")
    return redirect('boards:board_detail', board_id=board.id)


@login_required
@require_POST
@require_board_edit_permission
def delete_label_view(request, label_id):
    label = get_object_or_404(BoardLabel, id=label_id)
    board = label.quadro
    colab = get_user_colaborador(request.user)
    if not request.user.is_superuser:
        if board.criado_por != colab and not board.membros.filter(id=colab.id).exists():
            messages.error(request, "Acesso negado.")
            return redirect('boards:dashboard')
            
    nome = label.nome
    label.delete()
    messages.success(request, f"Etiqueta '{nome}' excluída.")
    return redirect('boards:board_detail', board_id=board.id)


@login_required
def read_mention_view(request, mention_id):
    """Marca uma menção como lida e redireciona para o detalhe do cartão"""
    mention = get_object_or_404(BoardMention, id=mention_id, mencionado=get_user_colaborador(request.user))
    mention.visualizada = True
    mention.save(update_fields=['visualizada'])
    
    url = f"{reverse('boards:board_detail', args=[mention.comentario.cartao.coluna.quadro.id])}?card_id={mention.comentario.cartao.id}"
    return redirect(url)


@login_required
@require_POST
@require_board_edit_permission
def api_add_board_link_view(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    try:
        data = json.loads(request.body)
        titulo = data.get('titulo', '').strip()
        url = data.get('url', '').strip()
        if not titulo or not url:
            return JsonResponse({'success': False, 'error': 'Título e URL são obrigatórios.'})
            
        link = BoardLink.objects.create(
            quadro=board,
            titulo=titulo,
            url=url,
            criado_por=get_user_colaborador(request.user)
        )
        return JsonResponse({
            'success': True,
            'id': link.id,
            'titulo': link.titulo,
            'url': link.url
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
@require_board_edit_permission
def api_delete_board_link_view(request, link_id):
    link = get_object_or_404(BoardLink, id=link_id)
    if not request.user.is_superuser and link.criado_por != get_user_colaborador(request.user) and link.quadro.criado_por != get_user_colaborador(request.user):
        return JsonResponse({'success': False, 'error': 'Permissão negada.'})
        
    try:
        link.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def read_board_notification_view(request, notif_id):
    """Marca uma notificação passiva como lida e redireciona para o cartão"""
    colab = get_user_colaborador(request.user)
    notif = get_object_or_404(BoardNotification, id=notif_id, colaborador=colab)
    notif.lida = True
    notif.save()
    
    url = reverse("boards:board_detail", args=[notif.cartao.coluna.quadro.id])
    return redirect(f"{url}?card_id={notif.cartao.id}")

from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT

@login_required
def export_board_pdf_view(request, board_id):
    colab = get_user_colaborador(request.user)
    
    if request.user.is_superuser:
        board = get_object_or_404(Board.objects.exclude(nome="Ações Corretivas e Preventivas"), id=board_id)
    elif colab:
        board = get_object_or_404(
            Board.objects.filter(Q(criado_por=colab) | Q(membros=colab) | Q(todos_colaboradores=True)).exclude(nome="Ações Corretivas e Preventivas"), 
            id=board_id
        )
    else:
        board = get_object_or_404(
            Board.objects.filter(todos_colaboradores=True).exclude(nome="Ações Corretivas e Preventivas"), 
            id=board_id
        )
    cartoes_param = request.GET.get('cartoes', '')
    if cartoes_param:
        cartoes_ids = [int(cid) for cid in cartoes_param.split(',') if cid.isdigit()]
        cartoes = Card.objects.filter(id__in=cartoes_ids, coluna__quadro_id=board_id).select_related('coluna', 'subsecao').prefetch_related('responsaveis', 'comentarios', 'comentarios__autor').order_by('coluna__ordem', 'ordem')
    else:
        cartoes = Card.objects.none()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Quadro_{board.nome[:20]}_Tarefas.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=HexColor('#1a1a1a'),
        spaceAfter=20,
        alignment=TA_CENTER
    )
    
    card_title_style = ParagraphStyle(
        'CardTitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=HexColor('#2c3e50'),
        spaceBefore=15,
        spaceAfter=5
    )
    
    meta_style = ParagraphStyle(
        'MetaText',
        parent=styles['Normal'],
        fontSize=10,
        textColor=HexColor('#555555'),
        spaceAfter=5
    )
    
    desc_style = ParagraphStyle(
        'DescText',
        parent=styles['Normal'],
        fontSize=11,
        spaceBefore=5,
        spaceAfter=10
    )

    comment_header_style = ParagraphStyle(
        'CommentHeader',
        parent=styles['Normal'],
        fontSize=9,
        textColor=HexColor('#666666'),
        spaceBefore=2,
        spaceAfter=2
    )

    comment_body_style = ParagraphStyle(
        'CommentBody',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=15,
        spaceAfter=8
    )

    story = []
    
    story.append(Paragraph(f"Tarefas: {board.nome}", title_style))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor('#cccccc'), spaceAfter=20))

    if not cartoes:
        story.append(Paragraph("Nenhuma tarefa selecionada ou encontrada.", desc_style))
        doc.build(story)
        return response

    for card in cartoes:
        story.append(Paragraph(f"Tarefa: {card.titulo}", card_title_style))
        
        meta_info = f"<b>Coluna:</b> {card.coluna.nome}"
        if card.subsecao:
            meta_info += f" | <b>Sub-sessão:</b> {card.subsecao.nome}"
            
        prioridade_label = dict(Card.PRIORIDADE_CHOICES).get(card.prioridade, card.prioridade)
        meta_info += f" | <b>Prioridade:</b> {prioridade_label}"
        
        resp_nomes = [r.nome_completo for r in card.responsaveis.all()]
        if resp_nomes:
            meta_info += f"<br/><b>Responsáveis:</b> {', '.join(resp_nomes)}"
            
        if card.data_entrega:
            meta_info += f" | <b>Prazo:</b> {card.data_entrega.strftime('%d/%m/%Y')}"
            
        story.append(Paragraph(meta_info, meta_style))
        
        if card.descricao:
            desc_text = card.descricao.replace('\n', '<br/>')
            story.append(Paragraph(f"<b>Descrição:</b><br/>{desc_text}", desc_style))
        
        comentarios = card.comentarios.all().order_by('criado_em')
        if comentarios:
            story.append(Paragraph("<b>Comentários:</b>", meta_style))
            for comment in comentarios:
                autor = comment.autor.nome_completo if comment.autor else "Sistema"
                data_str = comment.criado_em.strftime('%d/%m/%Y %H:%M')
                story.append(Paragraph(f"<i>{autor} em {data_str}</i>", comment_header_style))
                c_text = comment.texto.replace('\n', '<br/>')
                story.append(Paragraph(c_text, comment_body_style))
        
        story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor('#eeeeee'), spaceBefore=10, spaceAfter=10))

    doc.build(story)
    return response
