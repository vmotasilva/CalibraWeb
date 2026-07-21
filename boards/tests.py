from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from boards.models import Board, BoardColumn, Card, ChecklistItem, CardComment, BoardActivity, BoardLabel, CardPlanningDate
from rh.models import Colaborador
from django.utils import timezone
import datetime
import json

class BoardsTestCase(TestCase):
    def setUp(self):
        # Cria usuário Django
        self.user = User.objects.create_user(username='testuser', password='password123')
        
        # Cria Colaborador vinculado
        self.colaborador = Colaborador.objects.create(
            user_django=self.user,
            matricula='MAT-TEST-99',
            nome_completo='Colaborador Teste',
            cargo='Desenvolvedor',
            grupo='TI',
            is_active=True
        )
        
        # Cria Quadro
        self.board = Board.objects.create(
            nome='Quadro de Teste',
            descricao='Quadro para testes automatizados',
            criado_por=self.colaborador
        )
        self.board.membros.add(self.colaborador)
        
        # Cria Colunas
        self.coluna_todo = BoardColumn.objects.create(quadro=self.board, nome='A Fazer', ordem=0)
        self.coluna_done = BoardColumn.objects.create(quadro=self.board, nome='Concluído', ordem=1)
        
        # Cria Cartão
        self.card = Card.objects.create(
            coluna=self.coluna_todo,
            titulo='Tarefa de Teste',
            descricao='Descrição da tarefa de teste',
            prioridade='BAIXA',
            criado_por=self.colaborador,
            ordem=0
        )
        self.card.responsaveis.add(self.colaborador)
        
        self.client = Client()
        self.client.login(username='testuser', password='password123')

    def test_model_relations(self):
        """Verifica a integridade dos relacionamentos dos modelos"""
        self.assertEqual(self.board.colunas.count(), 2)
        self.assertEqual(self.coluna_todo.cartoes.count(), 1)
        self.assertIn(self.colaborador, self.card.responsaveis.all())

    def test_dashboard_view(self):
        """Testa o acesso à view do dashboard"""
        response = self.client.get(reverse('boards:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Quadro de Teste')

    def test_board_detail_view(self):
        """Testa a visualização de detalhes do quadro"""
        response = self.client.get(reverse('boards:board_detail', args=[self.board.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tarefa de Teste')

    def test_create_board(self):
        """Testa a criação de um novo quadro"""
        post_data = {
            'nome': 'Novo Quadro Criado',
            'descricao': 'Descrição do novo quadro',
            'membros': [self.colaborador.id]
        }
        response = self.client.post(reverse('boards:dashboard'), post_data)
        self.assertEqual(response.status_code, 302) # Redireciona após sucesso
        
        # Verifica se o quadro foi criado
        self.assertTrue(Board.objects.filter(nome='Novo Quadro Criado').exists())
        novo_board = Board.objects.get(nome='Novo Quadro Criado')
        # Verifica se as colunas padrão foram criadas
        self.assertEqual(novo_board.colunas.count(), 3)

    def test_create_column(self):
        """Testa a criação de uma nova coluna no quadro"""
        response = self.client.post(reverse('boards:create_column', args=[self.board.id]), {'nome': 'Nova Coluna'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(BoardColumn.objects.filter(quadro=self.board, nome='Nova Coluna').exists())

    def test_create_card(self):
        """Testa a criação de uma nova tarefa em uma coluna"""
        post_data = {
            'titulo': 'Nova Tarefa no Quadro',
            'descricao': 'Breve detalhe',
            'responsaveis': [self.colaborador.id],
            'prioridade': 'ALTA'
        }
        response = self.client.post(reverse('boards:create_card', args=[self.coluna_todo.id]), post_data)
        self.assertEqual(response.status_code, 302)
        card = Card.objects.get(coluna=self.coluna_todo, titulo='Nova Tarefa no Quadro')
        self.assertIn(self.colaborador, card.responsaveis.all())

    def test_api_move_card(self):
        """Testa a movimentação de um cartão via API AJAX (Drag and Drop)"""
        url = reverse('boards:api_move_card')
        post_json = {
            'card_id': self.card.id,
            'to_column_id': self.coluna_done.id,
            'card_order_ids': [self.card.id]
        }
        response = self.client.post(
            url, 
            data=json.dumps(post_json), 
            content_type='application/json',
            HTTP_X_CSRFTOKEN='dummy_token' # Client ignora CSRF por padrão em testes
        )
        self.assertEqual(response.status_code, 200)
        
        # Verifica se o cartão mudou de coluna
        self.card.refresh_from_db()
        self.assertEqual(self.card.coluna, self.coluna_done)
        
        # Verifica se registrou a atividade correspondente
        self.assertTrue(BoardActivity.objects.filter(quadro=self.board, colaborador=self.colaborador).exists())

    def test_api_checklist_and_comments(self):
        """Testa as APIs de checklist e comentários"""
        # 1. Adicionar item no checklist
        response = self.client.post(
            reverse('boards:api_add_checklist_item', args=[self.card.id]),
            data=json.dumps({'descricao': 'Item 1 do Checklist'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ChecklistItem.objects.filter(cartao=self.card, descricao='Item 1 do Checklist').exists())
        item = ChecklistItem.objects.get(descricao='Item 1 do Checklist')
        
        # 2. Toggle status do checklist item
        response = self.client.post(
            reverse('boards:api_toggle_checklist_item', args=[item.id]),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertTrue(item.concluido)

        # 3. Adicionar comentário
        response = self.client.post(
            reverse('boards:api_add_comment', args=[self.card.id]),
            data=json.dumps({'texto': 'Excelente trabalho!'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(CardComment.objects.filter(cartao=self.card, texto='Excelente trabalho!').exists())

    def test_recurring_task_spawning(self):
        """Testa o nascimento de uma nova tarefa recorrente ao concluir a tarefa atual"""
        import datetime
        from django.utils import timezone
        hoje = timezone.now().date()
        self.card.data_entrega = hoje
        self.card.periodicidade = 'MENSAL'
        self.card.save()
        
        # Cria um item no checklist para verificar se ele será copiado
        ChecklistItem.objects.create(cartao=self.card, descricao='Subtarefa a copiar', concluido=True)
        
        # Move o cartão para a coluna "Concluído" via API com confirmação de recriação
        url = reverse('boards:api_move_card')
        post_json = {
            'card_id': self.card.id,
            'to_column_id': self.coluna_done.id,
            'card_order_ids': [self.card.id],
            'recreate': True
        }
        response = self.client.post(
            url, 
            data=json.dumps(post_json), 
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        # O cartão original deve ter mudado para a coluna concluído
        self.card.refresh_from_db()
        self.assertEqual(self.card.coluna, self.coluna_done)
        # O cartão original deixa de ser recorrente para evitar ciclos infinitos
        self.assertEqual(self.card.periodicidade, 'AVULSA')
        
        # Deve ter nascido um novo cartão na coluna de origem ("A Fazer")
        new_cards = Card.objects.filter(coluna=self.coluna_todo, titulo=self.card.titulo).exclude(id=self.card.id)
        self.assertEqual(new_cards.count(), 1)
        new_card = new_cards.first()
        
        # O novo cartão herda os dados corretos
        self.assertEqual(new_card.periodicidade, 'MENSAL')
        self.assertIn(self.colaborador, new_card.responsaveis.all())
        
        # O prazo do novo cartão deve ser exatamente 1 mês à frente
        months_to_add = 1
        month = hoje.month + months_to_add
        year = hoje.year
        if month > 12:
            month -= 12
            year += 1
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        day = min(hoje.day, last_day)
        expected_date = datetime.date(year, month, day)
        self.assertEqual(new_card.data_entrega, expected_date)
        
        # O checklist deve ter sido copiado como desmarcado
        self.assertEqual(new_card.checklist_itens.count(), 1)
        self.assertFalse(new_card.checklist_itens.first().concluido)

    def test_recurring_task_no_spawning(self):
        """Testa que se o usuário não confirmar a recriação, ela não é criada e o cartão original mantém a periodicidade"""
        import datetime
        from django.utils import timezone
        hoje = timezone.now().date()
        self.card.data_entrega = hoje
        self.card.periodicidade = 'MENSAL'
        self.card.save()
        
        url = reverse('boards:api_move_card')
        post_json = {
            'card_id': self.card.id,
            'to_column_id': self.coluna_done.id,
            'card_order_ids': [self.card.id],
            'recreate': False
        }
        response = self.client.post(
            url, 
            data=json.dumps(post_json), 
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        self.card.refresh_from_db()
        self.assertEqual(self.card.coluna, self.coluna_done)
        # Como recreate foi False, o cartão original mantém sua periodicidade
        self.assertEqual(self.card.periodicidade, 'MENSAL')
        
        # Não deve ter nascido nenhum cartão novo
        new_cards = Card.objects.filter(coluna=self.coluna_todo, titulo=self.card.titulo)
        self.assertEqual(new_cards.count(), 0)

    def test_subsection_crud_and_card_association(self):
        """Testa a criação, exclusão de sub-sessões e movimentação/criação de cartões associados"""
        from boards.models import BoardSubSection
        
        # 1. Criar sub-sessão
        create_url = reverse('boards:create_subsection', args=[self.coluna_todo.id])
        response = self.client.post(create_url, {'nome': 'Subsection 1'})
        self.assertEqual(response.status_code, 302)
        
        sub = BoardSubSection.objects.get(coluna=self.coluna_todo, nome='Subsection 1')
        self.assertEqual(sub.nome, 'Subsection 1')
        
        # 2. Criar cartão associado a sub-sessão
        card_create_url = reverse('boards:create_card', args=[self.coluna_todo.id])
        response = self.client.post(card_create_url, {
            'titulo': 'Task in subsection',
            'descricao': 'Desc',
            'subsecao': sub.id,
            'prioridade': 'BAIXA',
            'periodicidade': 'AVULSA'
        })
        self.assertEqual(response.status_code, 302)
        
        new_card = Card.objects.get(titulo='Task in subsection')
        self.assertEqual(new_card.subsecao, sub)
        
        # 3. Mover cartão para outra sub-sessão ou coluna (API)
        move_url = reverse('boards:api_move_card')
        post_json = {
            'card_id': new_card.id,
            'to_column_id': self.coluna_done.id,
            'to_subsection_id': None,
            'card_order_ids': [new_card.id]
        }
        response = self.client.post(
            move_url,
            data=json.dumps(post_json),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        new_card.refresh_from_db()
        self.assertEqual(new_card.coluna, self.coluna_done)
        self.assertIsNone(new_card.subsecao)

        # 4. Excluir sub-sessão
        delete_url = reverse('boards:delete_subsection', args=[sub.id])
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(BoardSubSection.objects.filter(id=sub.id).exists())

    def test_column_reordering_api(self):
        """Testa o endpoint de reordenar colunas do quadro"""
        url = reverse('boards:api_move_column')
        post_json = {
            'column_order_ids': [self.coluna_done.id, self.coluna_todo.id]
        }
        response = self.client.post(
            url,
            data=json.dumps(post_json),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        self.coluna_done.refresh_from_db()
        self.coluna_todo.refresh_from_db()
        self.assertEqual(self.coluna_done.ordem, 0)
        self.assertEqual(self.coluna_todo.ordem, 1)

    def test_labels_and_recurrence_history(self):
        """Testa o gerenciamento de etiquetas e o vínculo de histórico de tarefas recorrentes"""
        # 1. Criar etiqueta
        create_label_url = reverse('boards:create_label', args=[self.board.id])
        response = self.client.post(create_label_url, {'nome': 'Label Test', 'cor': '#ff0000'})
        self.assertEqual(response.status_code, 302)
        
        self.assertTrue(BoardLabel.objects.filter(quadro=self.board, nome='Label Test').exists())
        label = BoardLabel.objects.get(quadro=self.board, nome='Label Test')
        self.assertEqual(label.cor, '#ff0000')
        
        # 2. Associar etiqueta ao cartão e testar api_card_detail_view POST e GET
        detail_url = reverse('boards:api_card_detail', args=[self.card.id])
        
        post_json = {
            'titulo': self.card.titulo,
            'descricao': self.card.descricao,
            'responsaveis_ids': [self.colaborador.id],
            'prioridade': 'BAIXA',
            'periodicidade': 'DIARIA',
            'data_entrega': '2026-06-17',
            'etiquetas_ids': [label.id]
        }
        response = self.client.post(
            detail_url,
            data=json.dumps(post_json),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.card.refresh_from_db()
        self.assertIn(label, self.card.etiquetas.all())
        self.assertEqual(self.card.periodicidade, 'DIARIA')
        
        # GET para verificar dados de etiquetas e histórico
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data['etiquetas']), 1)
        self.assertEqual(data['etiquetas'][0]['nome'], 'Label Test')
        
        # 3. Completar cartão (remover para coluna concluída com recriação)
        move_url = reverse('boards:api_move_card')
        move_json = {
            'card_id': self.card.id,
            'to_column_id': self.coluna_done.id,
            'card_order_ids': [self.card.id],
            'recreate': True
        }
        response = self.client.post(
            move_url,
            data=json.dumps(move_json),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        self.card.refresh_from_db()
        self.assertEqual(self.card.periodicidade, 'AVULSA')
        
        # Uma nova tarefa sucessora deve ter sido gerada na primeira coluna (coluna_todo)
        self.assertTrue(Card.objects.filter(coluna=self.coluna_todo, antecessora=self.card).exists())
        new_card = Card.objects.get(coluna=self.coluna_todo, antecessora=self.card)
        self.assertEqual(new_card.titulo, self.card.titulo)
        self.assertIn(label, new_card.etiquetas.all())
        
        # 4. Verificar o histórico completo na API GET de ambas as tarefas
        # Na tarefa original
        response = self.client.get(reverse('boards:api_card_detail', args=[self.card.id]))
        data = json.loads(response.content)
        self.assertEqual(len(data['historia']), 2)
        self.assertEqual(data['historia'][0]['id'], self.card.id)
        self.assertEqual(data['historia'][1]['id'], new_card.id)
        
        # Na nova tarefa
        response = self.client.get(reverse('boards:api_card_detail', args=[new_card.id]))
        data = json.loads(response.content)
        self.assertEqual(len(data['historia']), 2)
        
        # 5. Excluir etiqueta
        delete_label_url = reverse('boards:delete_label', args=[label.id])
        response = self.client.post(delete_label_url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(BoardLabel.objects.filter(id=label.id).exists())

    def test_card_completion_date_and_execution_times(self):
        # Login
        self.client.force_login(self.user)
        
        detail_url = reverse('boards:api_card_detail', args=[self.card.id])
        
        # 1. Atualizar campos via API POST
        post_json = {
            'titulo': self.card.titulo,
            'descricao': self.card.descricao,
            'data_conclusao': '2026-06-17',
            'datetime_inicio': '2026-06-17T08:30',
            'datetime_fim': '2026-06-17T17:45',
            'prioridade': 'MEDIA',
            'periodicidade': 'AVULSA'
        }
        
        response = self.client.post(
            detail_url,
            data=json.dumps(post_json),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        # Verificar no banco de dados
        self.card.refresh_from_db()
        self.assertEqual(self.card.data_conclusao.strftime('%Y-%m-%d'), '2026-06-17')
        self.assertEqual(self.card.datetime_inicio.strftime('%Y-%m-%dT%H:%M'), '2026-06-17T08:30')
        self.assertEqual(self.card.datetime_fim.strftime('%Y-%m-%dT%H:%M'), '2026-06-17T17:45')
        
        # 2. Verificar retorno via API GET
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['data_conclusao'], '2026-06-17')
        self.assertEqual(data['datetime_inicio'], '2026-06-17T08:30')
        self.assertEqual(data['datetime_fim'], '2026-06-17T17:45')
        
        # 3. Mover para coluna concluída (deve atualizar data_conclusao automaticamente se não estivesse preenchida)
        # Primeiro, vamos limpar os campos
        self.card.data_conclusao = None
        self.card.hora_inicio = None
        self.card.hora_fim = None
        self.card.save()
        
        move_url = reverse('boards:api_move_card')
        move_json = {
            'card_id': self.card.id,
            'to_column_id': self.coluna_done.id,
            'card_order_ids': [self.card.id],
            'recreate': False
        }
        response = self.client.post(
            move_url,
            data=json.dumps(move_json),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        self.card.refresh_from_db()
        self.assertIsNotNone(self.card.data_conclusao)
        self.assertEqual(self.card.data_conclusao, timezone.now().date())
        
        # 4. Mover de volta para coluna não concluída (deve limpar os campos)
        # Vamos definir horários também para testar se limpa
        self.card.datetime_inicio = timezone.make_aware(datetime.datetime(2026, 6, 17, 9, 0))
        self.card.datetime_fim = timezone.make_aware(datetime.datetime(2026, 6, 17, 10, 0))
        self.card.save()
        
        reopen_json = {
            'card_id': self.card.id,
            'to_column_id': self.coluna_todo.id,
            'card_order_ids': [self.card.id],
            'recreate': False
        }
        response = self.client.post(
            move_url,
            data=json.dumps(reopen_json),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        self.card.refresh_from_db()
        self.assertIsNone(self.card.data_conclusao)
        self.assertIsNone(self.card.datetime_inicio)
        self.assertIsNone(self.card.datetime_fim)

    def test_completed_tasks_column_mirroring_and_modal_column_movement(self):
        # Login
        self.client.force_login(self.user)
        
        move_url = reverse('boards:api_move_card')
        detail_url = reverse('boards:api_card_detail', args=[self.card.id])
        
        # 1. Concluir tarefa na mesma coluna (coluna_todo) usando drag & drop concluido: True
        move_json = {
            'card_id': self.card.id,
            'to_column_id': self.coluna_todo.id,
            'concluido': True,
            'recreate': False
        }
        response = self.client.post(
            move_url,
            data=json.dumps(move_json),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        self.card.refresh_from_db()
        self.assertEqual(self.card.coluna, self.coluna_todo)
        self.assertIsNotNone(self.card.data_conclusao)
        
        # 2. Reabrir tarefa na mesma coluna usando concluido: False
        reopen_json = {
            'card_id': self.card.id,
            'to_column_id': self.coluna_todo.id,
            'concluido': False,
            'recreate': False
        }
        response = self.client.post(
            move_url,
            data=json.dumps(reopen_json),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        self.card.refresh_from_db()
        self.assertEqual(self.card.coluna, self.coluna_todo)
        self.assertIsNone(self.card.data_conclusao)
        
        # 3. Mudar de coluna pelo modal de detalhes via API POST
        detail_post_json = {
            'titulo': self.card.titulo,
            'descricao': self.card.descricao,
            'coluna_id': self.coluna_done.id,
            'prioridade': 'ALTA',
            'periodicidade': 'AVULSA'
        }
        response = self.client.post(
            detail_url,
            data=json.dumps(detail_post_json),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        self.card.refresh_from_db()
        self.assertEqual(self.card.coluna, self.coluna_done)
        # Como coluna_done é concluída, deve ter completado automaticamente
        self.assertIsNotNone(self.card.data_conclusao)
        
        # 4. Reabrir alterando a coluna de volta pelo modal para coluna_todo
        detail_reopen_json = {
            'titulo': self.card.titulo,
            'descricao': self.card.descricao,
            'coluna_id': self.coluna_todo.id,
            'prioridade': 'ALTA',
            'periodicidade': 'AVULSA'
        }
        response = self.client.post(
            detail_url,
            data=json.dumps(detail_reopen_json),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        self.card.refresh_from_db()
        self.assertEqual(self.card.coluna, self.coluna_todo)
        self.assertIsNone(self.card.data_conclusao)

    def test_card_date_time_validation(self):
        """Testa a validação cronológica de data e hora de início e fim"""
        self.client.force_login(self.user)
        detail_url = reverse('boards:api_card_detail', args=[self.card.id])
        
        # 1. Caso Válido: Fim após início
        valid_json = {
            'titulo': self.card.titulo,
            'datetime_inicio': '2026-06-17T08:00',
            'data_conclusao': '2026-06-17',
            'datetime_fim': '2026-06-17T10:00',
            'prioridade': 'MEDIA',
            'periodicidade': 'AVULSA'
        }
        response = self.client.post(
            detail_url,
            data=json.dumps(valid_json),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        # 2. Caso Inválido: Fim antes de início (mesmo dia, hora anterior)
        invalid_json_1 = {
            'titulo': self.card.titulo,
            'datetime_inicio': '2026-06-17T10:00',
            'data_conclusao': '2026-06-17',
            'datetime_fim': '2026-06-17T08:00',
            'prioridade': 'MEDIA',
            'periodicidade': 'AVULSA'
        }
        response = self.client.post(
            detail_url,
            data=json.dumps(invalid_json_1),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('A data/hora de fim deve ser posterior à data/hora de início', data['error'])
        
        # 3. Caso Inválido: Fim antes de início (dia anterior)
        invalid_json_2 = {
            'titulo': self.card.titulo,
            'datetime_inicio': '2026-06-17T08:00',
            'data_conclusao': '2026-06-16',
            'datetime_fim': '2026-06-16T08:00',
            'prioridade': 'MEDIA',
            'periodicidade': 'AVULSA'
        }
        response = self.client.post(
            detail_url,
            data=json.dumps(invalid_json_2),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_multiple_planning_dates(self):
        """Testa o salvamento e a sincronização de múltiplos planejamentos de data/hora"""
        self.client.force_login(self.user)
        detail_url = reverse('boards:api_card_detail', args=[self.card.id])
        
        # 1. Enviar múltiplos planejamentos válidos
        planning_json = {
            'titulo': self.card.titulo,
            'prioridade': 'MEDIA',
            'periodicidade': 'AVULSA',
            'planejamentos': [
                {'datetime_inicio': '2026-06-20T09:00', 'datetime_fim': '2026-06-20T10:00'},
                {'datetime_inicio': '2026-06-21T14:00', 'datetime_fim': '2026-06-21T16:00'},
                {'datetime_inicio': '2026-06-19T08:00', 'datetime_fim': '2026-06-19T12:00'} # Enviado fora de ordem para testar ordenação e sinc
            ]
        }
        response = self.client.post(
            detail_url,
            data=json.dumps(planning_json),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        # Verifica se os objetos CardPlanningDate foram criados
        self.assertEqual(self.card.planejamentos.count(), 3)
        
        # Verifica a sincronização com os campos legados baseando-se no planejamento mais antigo (2026-06-19 08:00)
        self.card.refresh_from_db()
        self.assertEqual(self.card.datetime_inicio.strftime('%Y-%m-%dT%H:%M'), '2026-06-19T08:00')
        self.assertEqual(self.card.datetime_fim.strftime('%Y-%m-%dT%H:%M'), '2026-06-19T12:00')
        
        # 2. Caso inválido: Hora fim antes da hora início em um dos planejamentos
        invalid_planning_json = {
            'titulo': self.card.titulo,
            'prioridade': 'MEDIA',
            'periodicidade': 'AVULSA',
            'planejamentos': [
                {'datetime_inicio': '2026-06-20T10:00', 'datetime_fim': '2026-06-20T09:00'}
            ]
        }
        response = self.client.post(
            detail_url,
            data=json.dumps(invalid_planning_json),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('Data/Hora de fim deve ser posterior', data['error'])
        
        # 3. Remover todos os planejamentos enviando array vazio
        clear_planning_json = {
            'titulo': self.card.titulo,
            'prioridade': 'MEDIA',
            'periodicidade': 'AVULSA',
            'planejamentos': []
        }
        response = self.client.post(
            detail_url,
            data=json.dumps(clear_planning_json),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.card.planejamentos.count(), 0)
        
        # Verifica se os campos legados foram limpos
        self.card.refresh_from_db()
        self.assertIsNone(self.card.datetime_inicio)
        self.assertIsNone(self.card.datetime_fim)






