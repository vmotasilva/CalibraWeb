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

from boards.models import Board, BoardColumn, Card, ChecklistItem, CardComment, BoardActivity, BoardSubSection, BoardLabel, CardPlanningDate
from boards.forms import BoardForm, CardForm
from rh.models import Colaborador

def get_user_colaborador(user):
    return user.colaborador if hasattr(user, 'colaborador') else None


@login_required
def dashboard_view(request):
    """Exibe todos os quadros que o usuário gerencia ou participa"""
    colab = get_user_colaborador(request.user)
    # Garante que o quadro fixado de Planos de Ação existe

    board_fixed, created = Board.objects.get_or_create(
        tipo='PLANOS_ACAO',
        defaults={
            'nome': 'Ações Corretivas e Preventivas',
            'descricao': 'Quadro fixado contendo as ações corretivas e preventivas dos Planos de Ações.',
            'arquivado': False
        }
    )
    if created:
        # Criar as 5 colunas vinculadas aos status das ações
        colunas_padrao = [
            ("Planejada", "planejada"),
            ("Em Curso/Andamento", "em_curso"),
            ("Retardo/Atrasada", "retardo"),
            ("Completa/Concluído", "completa"),
            ("Cancelada", "cancelada"),
        ]
        for idx, (nome_col, status_val) in enumerate(colunas_padrao):
            BoardColumn.objects.create(
                quadro=board_fixed, 
                nome=nome_col, 
                ordem=idx,
                status_linha_acao=status_val
            )
            
    # Superusuários vêm todos os quadros, colaboradores comuns vêm apenas os seus, onde são membros, ou o quadro fixo
    if request.user.is_superuser:
        quadros_base = Board.objects.all().distinct()
    else:
        quadros_base = Board.objects.filter(
            Q(criado_por=colab) | Q(membros=colab) | Q(tipo='PLANOS_ACAO')
        ).distinct()

    quadros = quadros_base.filter(arquivado=False)
    quadros_arquivados = quadros_base.filter(arquivado=True)


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
        
    # Coletar todas as tarefas/ações de todos os quadros acessíveis
    from boards.models import Card
    cartoes_qs = Card.objects.filter(coluna__quadro__in=quadros).select_related('coluna__quadro', 'subsecao', 'criado_por').prefetch_related('responsaveis', 'etiquetas')
    
    todas_acoes = []
    
    # 1. Obter ações corretivas/preventivas virtuais se houver quadro PLANOS_ACAO
    board_planos = quadros.filter(tipo='PLANOS_ACAO').first()
    if board_planos:
        from acoes.models import LinhaAcao
        linhas = LinhaAcao.objects.filter(
            classificacao__in=['corretiva', 'preventiva']
        ).select_related('plano_acao__solucao', 'responsavel_acao').prefetch_related('responsaveis_multiplos').all()
        
        for l in linhas:
            resps = []
            if l.responsavel_acao:
                resps.append(l.responsavel_acao)
            for r in l.responsaveis_multiplos.all():
                if r not in resps:
                    resps.append(r)
            
            plan_ref = l.plano_acao.numero_registro or l.plano_acao.solucao.titulo or "Plano de Ação"
            card_title = f"Ação #{l.numero_acao} - {plan_ref}"
            
            todas_acoes.append({
                'id': l.id,
                'titulo': card_title,
                'descricao': l.descricao,
                'prioridade': 'ALTA' if l.prioridade else 'BAIXA',
                'data_entrega': l.data_deadline,
                'data_conclusao': l.data_conclusao,
                'status_exibicao': l.get_status_display() if hasattr(l, 'get_status_display') else l.status.capitalize(),
                'quadro_nome': board_planos.nome,
                'quadro_id': board_planos.id,
                'responsaveis': resps,
                'plano_acao_id': l.plano_acao.id,
                'is_virtual': True
            })
            
    # 2. Obter tarefas dos quadros normais
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
def board_detail_view(request, board_id):
    """Visualização Kanban do quadro"""
    colab = get_user_colaborador(request.user)
    
    # Permissão de acesso
    if request.user.is_superuser:
        board = get_object_or_404(Board, id=board_id)
    else:
        board = get_object_or_404(
            Board.objects.filter(Q(criado_por=colab) | Q(membros=colab) | Q(tipo='PLANOS_ACAO')), 
            id=board_id
        )
        
    # Colunas, sub-sessões e cartões pré-carregados
    colunas = list(board.colunas.prefetch_related('subsecoes', 'cartoes__responsaveis', 'cartoes__checklist_itens', 'cartoes__planejamentos').all())
    
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

    if board.tipo == 'PLANOS_ACAO':
        from acoes.models import LinhaAcao
        
        # Obter todas as linhas de ação corretiva e preventiva
        linhas = LinhaAcao.objects.filter(
            classificacao__in=['corretiva', 'preventiva']
        ).select_related('plano_acao__solucao', 'responsavel_acao').prefetch_related('responsaveis_multiplos').all()
        
        # Filtrar por período se aplicável
        if start_date:
            linhas_filtradas = []
            for l in linhas:
                is_completed = l.status in ['completa', 'cancelada']
                if is_completed:
                    if l.data_conclusao and start_date <= l.data_conclusao <= end_date:
                        linhas_filtradas.append(l)
                else:
                    if l.data_deadline and start_date <= l.data_deadline <= end_date:
                        linhas_filtradas.append(l)
            linhas = linhas_filtradas

        total_cartoes = len(linhas)
        
        # Identificar colunas concluídas
        concluido_colunas_ids = [col.id for col in colunas if col.status_linha_acao in ['completa', 'cancelada']]
        
        cartoes_concluidos = sum(1 for l in linhas if l.status in ['completa', 'cancelada'])
        
        porcentagem_concluida = 0
        if total_cartoes > 0:
            porcentagem_concluida = int((cartoes_concluidos / total_cartoes) * 100)
            
        cartoes_atrasados = sum(1 for l in linhas if l.data_deadline and l.data_deadline < today and l.status not in ['completa', 'cancelada'])
        
        # Carga de trabalho por colaborador (linhas de ação pendentes)
        carga_membros_dict = {}
        for l in linhas:
            if l.status in ['completa', 'cancelada']:
                continue
            # responsavel principal
            if l.responsavel_acao:
                carga_membros_dict[l.responsavel_acao] = carga_membros_dict.get(l.responsavel_acao, 0) + 1
            # responsaveis multiplos
            for r in l.responsaveis_multiplos.all():
                if r != l.responsavel_acao:
                    carga_membros_dict[r] = carga_membros_dict.get(r, 0) + 1
                    
        # Ordenar carga de trabalho por quantidade de tarefas decrescente
        carga_membros_sorted = sorted(carga_membros_dict.items(), key=lambda x: x[1], reverse=True)
        chart_membros_nomes = [m.nome_completo for m, _ in carga_membros_sorted]
        chart_membros_valores = [v for _, v in carga_membros_sorted]
        
        # Distribuição por colunas e associar cartões virtuais a colunas
        distribuicao_colunas = []
        for col in colunas:
            col_linhas = [l for l in linhas if l.status == col.status_linha_acao]
            distribuicao_colunas.append({
                'nome': col.nome,
                'quantidade': len(col_linhas)
            })
            
            # Construir cartões virtuais
            col.cartoes_list = []
            for l in col_linhas:
                resps = []
                if l.responsavel_acao:
                    resps.append(l.responsavel_acao)
                for r in l.responsaveis_multiplos.all():
                    if r not in resps:
                        resps.append(r)
                        
                plan_ref = l.plano_acao.numero_registro or l.plano_acao.solucao.titulo or "Plano de Ação"
                card_title = f"Ação #{l.numero_acao} - {plan_ref}"
                
                col.cartoes_list.append({
                    'id': l.id,
                    'titulo': card_title,
                    'descricao': l.descricao,
                    'prioridade': 'ALTA' if l.prioridade else 'BAIXA',
                    'data_entrega': l.data_deadline,
                    'data_conclusao': l.data_conclusao,
                    'hora_inicio': None,
                    'hora_fim': None,
                    'responsaveis': {
                        'all': resps
                    },
                    'periodicidade': 'AVULSA',
                    'checklist_itens': {
                        'exists': False
                    },
                    'plano_acao_id': l.plano_acao.id,
                    'is_virtual': True,
                    'etiquetas': {
                        'all': []
                    },
                    'antecessora': None,
                    'historia': []
                })
            
            if col.status_linha_acao in ['completa', 'cancelada']:
                col.cartoes_list_andamento = []
                col.cartoes_list_concluido = col.cartoes_list
            else:
                col.cartoes_list_andamento = col.cartoes_list
                col.cartoes_list_concluido = []
            
            col.subsecoes_list = []
            col.cartoes_sem_subsecao_andamento = col.cartoes_list_andamento
            col.cartoes_sem_subsecao_concluido = col.cartoes_list_concluido
    else:
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
    
    # Lista de colaboradores para o dropdown de transferência de responsável (membros do quadro + criador)
    if board.tipo == 'PLANOS_ACAO':
        todos_colaboradores = Colaborador.objects.filter(is_active=True).order_by('nome_completo')
    else:
        membros_ids = list(board.membros.values_list('id', flat=True))
        if board.criado_por:
            membros_ids.append(board.criado_por.id)
        todos_colaboradores = Colaborador.objects.filter(id__in=membros_ids, is_active=True).distinct().order_by('nome_completo')
        
    colunas_andamento = [col for col in colunas if col.id not in concluido_colunas_ids]
    if board.tipo == 'PLANOS_ACAO':
        colunas_concluidas = colunas
    else:
        colunas_concluidas = colunas_andamento

    context = {
        'board': board,
        'colunas': colunas,
        'colunas_andamento': colunas_andamento,
        'colunas_concluidas': colunas_concluidas,
        'card_form': card_form,
        'total_cartoes': total_cartoes,
        'cartoes_concluidos': cartoes_concluidos,
        'porcentagem_concluida': porcentagem_concluida,
        'cartoes_atrasados': cartoes_atrasados,
        'atividades': atividades,
        'todos_colaboradores': todos_colaboradores,
        'colaboradores_sistema': Colaborador.objects.filter(is_active=True).order_by('nome_completo'),
        'chart_membros_nomes': json.dumps(chart_membros_nomes),
        'chart_membros_valores': json.dumps(chart_membros_valores),
        'distribuicao_colunas': json.dumps(distribuicao_colunas),
        'titulo': f"Quadro - {board.nome}",
        'periodo': periodo,
        'hoje': today
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


from django.urls import reverse

@login_required
@require_POST
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
def api_move_card_view(request):
    """Endpoint API para mover cartão de coluna/posição via Drag and Drop"""
    try:
        colab = get_user_colaborador(request.user)
        data = json.loads(request.body)
        card_id = data.get('card_id')
        to_column_id = data.get('to_column_id')
        card_order_ids = data.get('card_order_ids', []) # Array de IDs na nova ordem
        
        nova_coluna = get_object_or_404(BoardColumn, id=to_column_id)
        
        if nova_coluna.quadro.tipo == 'PLANOS_ACAO':
            from acoes.models import LinhaAcao
            linha = get_object_or_404(LinhaAcao, id=card_id)
            old_status = linha.status
            new_status = nova_coluna.status_linha_acao
            
            linha.status = new_status
            if new_status == 'completa':
                linha.data_conclusao = timezone.now().date()
            else:
                linha.data_conclusao = None
            linha.save()
            
            if old_status != new_status:
                BoardActivity.objects.create(
                    quadro=nova_coluna.quadro,
                    colaborador=colab,
                    descricao=f"alterou o status da ação #{linha.numero_acao} de '{old_status}' para '{new_status}'."
                )
            return JsonResponse({'success': True})
            
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
    
    # Quadros não podem mais ser excluídos, apenas arquivados
    messages.error(request, "Quadros não podem ser excluídos, apenas arquivados.")
    return redirect('boards:board_detail', board_id=board.id)


@login_required
@require_POST
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
def delete_subsection_view(request, subsection_id):
    subsecao = get_object_or_404(BoardSubSection, id=subsection_id)
    board_id = subsecao.coluna.quadro.id
    nome = subsecao.nome
    subsecao.delete()
    messages.success(request, f"Sub-sessão '{nome}' excluída com sucesso!")
    return redirect('boards:board_detail', board_id=board_id)


@login_required
@require_POST
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
    from .models import BoardMention
    from django.urls import reverse
    colab = get_user_colaborador(request.user)
    mention = get_object_or_404(BoardMention, id=mention_id, mencionado=colab)
    mention.visualizada = True
    mention.save()
    
    board_id = mention.comentario.cartao.coluna.quadro.id
    card_id = mention.comentario.cartao.id
    return redirect(reverse('boards:board_detail', kwargs={'board_id': board_id}) + f"?card_id={card_id}")
