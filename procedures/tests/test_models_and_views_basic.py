# -*- coding: utf-8 -*-
"""Tests básicos do app Procedures.

Mantidos aqui (pacote `procedures/tests/`) para evitar conflito com discovery
quando existe um diretório `tests/`.
"""

from datetime import date

from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from rh.models import Colaborador

from procedures.models import (
    Fornecedor,
    PlanejamentoTreinamento,
    ProcessoCotacao,
    Procedimento,
)

from procedures.views.planejamento_views import editar_planejamento_view


class ProcedimentoModelTest(TestCase):
    """Testes do modelo Procedimento."""

    def setUp(self):
        self.proc = Procedimento.objects.create(
            codigo='POP.001',
            nome='Procedimento Teste',
            numero_revisao='01',
        )

    def test_procedimento_creation(self):
        self.assertEqual(self.proc.codigo, 'POP.001')
        self.assertTrue(str(self.proc).startswith('POP.001'))


class FornecedorModelTest(TestCase):
    """Testes do modelo Fornecedor."""

    def setUp(self):
        self.fornecedor = Fornecedor.objects.create(
            nome_fantasia='Empresa Teste',
            cnpj='12345678000190',
            contato='João Silva',
            email='joao@empresa.com',
            telefone='11999999999',
            escopo_servico='Serviço Teste',
        )

    def test_fornecedor_creation(self):
        self.assertEqual(self.fornecedor.nome_fantasia, 'Empresa Teste')
        self.assertEqual(self.fornecedor.status, 'EM_ANALISE')


class ProcessoCotacaoModelTest(TestCase):
    """Testes do modelo ProcessoCotacao."""

    def setUp(self):
        self.cotacao = ProcessoCotacao.objects.create(
            titulo='Cotação Teste',
            prazo_limite='2025-12-31',
        )

    def test_cotacao_creation(self):
        self.assertEqual(self.cotacao.titulo, 'Cotação Teste')
        self.assertEqual(self.cotacao.status, 'ABERTO')


class PlanejamentoTreinamentoEditViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pass12345')
        self.rf = RequestFactory()

        self.instrutor = Colaborador.objects.create(
            matricula='I1',
            nome_completo='Instrutor Teste',
            grupo='GRUPO',
            setor=None,
        )
        self.colab1 = Colaborador.objects.create(
            matricula='C1',
            nome_completo='Colab 1',
            grupo='GRUPO',
            setor=None,
        )
        self.colab2 = Colaborador.objects.create(
            matricula='C2',
            nome_completo='Colab 2',
            grupo='GRUPO',
            setor=None,
        )

        self.planejamento = PlanejamentoTreinamento.objects.create(
            titulo='Treinamento X',
            origem='LIVRE',
            instrutor=self.instrutor,
            data_prevista=date.today(),
            status='PLANEJADO',
        )
        self.planejamento.colaboradores.set([self.colab1, self.colab2])

    def test_editar_nao_desassocia_colaboradores_quando_post_sem_colaboradores(self):
        request = self.rf.post(
            reverse('procedures:editar_planejamento', args=[self.planejamento.id]),
            data={
                'titulo': 'Treinamento X (edit)',
                'data_prevista': self.planejamento.data_prevista.isoformat(),
                'status': 'PLANEJADO',
                # Intencionalmente sem 'colaboradores'
            },
        )
        request.user = self.user

        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, '_messages', FallbackStorage(request))

        response = editar_planejamento_view(request, planejamento_id=self.planejamento.id)

        self.assertEqual(response.status_code, 200)
        self.planejamento.refresh_from_db()
        self.assertEqual(self.planejamento.colaboradores.count(), 2)

    def test_editar_atualiza_quando_post_com_colaboradores(self):
        request = self.rf.post(
            reverse('procedures:editar_planejamento', args=[self.planejamento.id]),
            data={
                'titulo': 'Treinamento X (edit ok)',
                'data_prevista': self.planejamento.data_prevista.isoformat(),
                'status': 'PLANEJADO',
                'colaboradores': [str(self.colab1.id), str(self.colab2.id)],
            },
        )
        request.user = self.user

        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, '_messages', FallbackStorage(request))

        response = editar_planejamento_view(request, planejamento_id=self.planejamento.id)

        self.assertEqual(response.status_code, 302)
        self.planejamento.refresh_from_db()
        self.assertEqual(self.planejamento.titulo, 'Treinamento X (edit ok)')
        self.assertEqual(self.planejamento.colaboradores.count(), 2)
