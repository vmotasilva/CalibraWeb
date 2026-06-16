from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from boards.models import Board, BoardColumn, Card, ChecklistItem, CardComment, BoardActivity
from rh.models import Colaborador
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
            responsavel=self.colaborador,
            prioridade='BAIXA',
            criado_por=self.colaborador,
            ordem=0
        )
        
        self.client = Client()
        self.client.login(username='testuser', password='password123')

    def test_model_relations(self):
        """Verifica a integridade dos relacionamentos dos modelos"""
        self.assertEqual(self.board.colunas.count(), 2)
        self.assertEqual(self.coluna_todo.cartoes.count(), 1)
        self.assertEqual(self.card.responsavel, self.colaborador)

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
            'responsavel': self.colaborador.id,
            'prioridade': 'MEDIA'
        }
        response = self.client.post(reverse('boards:create_card', args=[self.coluna_todo.id]), post_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Card.objects.filter(coluna=self.coluna_todo, titulo='Nova Tarefa no Quadro').exists())

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
        
        # Move o cartão para a coluna "Concluído" via API
        url = reverse('boards:api_move_card')
        post_json = {
            'card_id': self.card.id,
            'to_column_id': self.coluna_done.id,
            'card_order_ids': [self.card.id]
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
        new_cards = Card.objects.filter(coluna=self.coluna_todo, titulo=self.card.titulo)
        self.assertEqual(new_cards.count(), 1)
        new_card = new_cards.first()
        
        # O novo cartão herda os dados corretos
        self.assertEqual(new_card.periodicidade, 'MENSAL')
        self.assertEqual(new_card.responsavel, self.colaborador)
        
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
