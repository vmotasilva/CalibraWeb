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
    Disciplina,
    DisciplinaProcedimento,
    Fornecedor,
    ListaPresenca,
    PlanejamentoTreinamento,
    ProcessoCotacao,
    Procedimento,
    RegistroTreinamento,
)

from procedures.views.planejamento_views import editar_planejamento_view
from procedures.views.habilidades_views import deletar_disciplina_view


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

        self.proc1 = Procedimento.objects.create(
            codigo='POP.101',
            nome='Procedimento 101',
            numero_revisao='01',
        )
        self.proc2 = Procedimento.objects.create(
            codigo='POP.102',
            nome='Procedimento 102',
            numero_revisao='01',
        )
        self.planejamento.procedimentos.set([self.proc1, self.proc2])

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

        self.assertEqual(response.status_code, 302)
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

    def test_editar_nao_limpa_procedimentos_quando_post_com_valor_em_branco(self):
        request = self.rf.post(
            reverse('procedures:editar_planejamento', args=[self.planejamento.id]),
            data={
                'titulo': 'Treinamento X (edit proc blank)',
                'data_prevista': self.planejamento.data_prevista.isoformat(),
                'status': 'PLANEJADO',
                'colaboradores': [str(self.colab1.id), str(self.colab2.id)],
                # Simula hidden input quebrado/sem valor
                'procedimentos': [''],
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
        self.assertEqual(self.planejamento.procedimentos.count(), 2)

    def test_editar_nao_limpa_colaboradores_quando_post_com_valor_em_branco(self):
        request = self.rf.post(
            reverse('procedures:editar_planejamento', args=[self.planejamento.id]),
            data={
                'titulo': 'Treinamento X (edit colab blank)',
                'data_prevista': self.planejamento.data_prevista.isoformat(),
                'status': 'PLANEJADO',
                # Simula hidden input quebrado/sem valor
                'colaboradores': [''],
                'procedimentos': [str(self.proc1.id), str(self.proc2.id)],
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


class CalendarioTreinamentosViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cal-tester', password='pass12345')

        self.instrutor = Colaborador.objects.create(
            matricula='I2',
            nome_completo='Instrutor Calendário',
            grupo='GRUPO',
            setor=None,
        )
        self.colab = Colaborador.objects.create(
            matricula='C3',
            nome_completo='Colab Calendário',
            grupo='GRUPO',
            setor=None,
        )

        self.ref_date = date(2026, 3, 9)

        self.planejamento = PlanejamentoTreinamento.objects.create(
            titulo='Planejado Calendário',
            origem='LIVRE',
            instrutor=self.instrutor,
            data_prevista=self.ref_date,
            status='CONFIRMADO',
        )
        self.planejamento.colaboradores.set([self.colab])

        self.lista = ListaPresenca.objects.create(
            titulo='Registrado Calendário',
            instrutor=self.instrutor,
            data_sessao=self.ref_date,
        )

    def test_calendario_mes_mostra_planejado_e_registrado(self):
        self.client.force_login(self.user)
        url = reverse('procedures:treinamentos_calendario')
        resp = self.client.get(url, {'view': 'month', 'year': 2026, 'month': 3})
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('Planejado Calendário', content)
        self.assertIn('Registrado Calendário', content)

    def test_calendario_semana_nao_quebra(self):
        self.client.force_login(self.user)
        url = reverse('procedures:treinamentos_calendario')
        resp = self.client.get(url, {'view': 'week', 'date': self.ref_date.isoformat()})
        self.assertEqual(resp.status_code, 200)

    def test_calendario_dia_nao_quebra(self):
        self.client.force_login(self.user)
        url = reverse('procedures:treinamentos_calendario')
        resp = self.client.get(url, {'view': 'day', 'date': self.ref_date.isoformat()})
        self.assertEqual(resp.status_code, 200)


class DisciplinaDeleteRuleTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='disc-del', password='pass12345')
        self.rf = RequestFactory()
        self.disciplina = Disciplina.objects.create(nome='Disciplina Teste')

    def test_deletar_disciplina_sem_associacao(self):
        request = self.rf.post(f'/procedures/disciplinas/{self.disciplina.id}/deletar/')
        request.user = self.user

        resp = deletar_disciplina_view(request, self.disciplina.id)

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Disciplina.objects.filter(id=self.disciplina.id).exists())

    def test_nao_deleta_disciplina_com_procedimento_associado(self):
        proc = Procedimento.objects.create(codigo='POP.DEL.001', nome='Proc associado', numero_revisao='01')
        DisciplinaProcedimento.objects.create(
            disciplina=self.disciplina,
            procedimento=proc,
            ordem=1,
            obrigatorio=True,
        )
        request = self.rf.post(f'/procedures/disciplinas/{self.disciplina.id}/deletar/')
        request.user = self.user

        resp = deletar_disciplina_view(request, self.disciplina.id)

        self.assertEqual(resp.status_code, 400)
        self.assertTrue(Disciplina.objects.filter(id=self.disciplina.id).exists())


class PlanejamentoConclusaoFlowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='flow-tester', password='pass12345')
        self.client.force_login(self.user)

        self.instrutor = Colaborador.objects.create(
            matricula='IFLOW',
            nome_completo='Instrutor Flow',
            grupo='GRUPO',
            setor=None,
        )
        self.colab1 = Colaborador.objects.create(
            matricula='CF1',
            nome_completo='Colaborador 1',
            grupo='GRUPO',
            setor=None,
        )
        self.colab2 = Colaborador.objects.create(
            matricula='CF2',
            nome_completo='Colaborador 2',
            grupo='GRUPO',
            setor=None,
        )
        self.colab3 = Colaborador.objects.create(
            matricula='CF3',
            nome_completo='Colaborador 3',
            grupo='GRUPO',
            setor=None,
        )

        self.procedimento = Procedimento.objects.create(
            codigo='POP.FLOW.001',
            nome='Procedimento Flow',
            numero_revisao='01',
        )

        self.planejamento = PlanejamentoTreinamento.objects.create(
            titulo='Planejamento Flow',
            origem='LIVRE',
            instrutor=self.instrutor,
            data_prevista=date(2026, 3, 20),
            status='CONFIRMADO',
        )
        self.planejamento.procedimentos.set([self.procedimento])
        self.planejamento.colaboradores.set([self.colab1, self.colab2])

    def test_alterar_status_realizado_redireciona_para_confirmacao(self):
        url = reverse('procedures:alterar_status_planejamento', args=[self.planejamento.id])
        resp = self.client.post(url, {'status': 'REALIZADO'})

        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse('procedures:criar_registros_planejamento', args=[self.planejamento.id]))

        self.planejamento.refresh_from_db()
        self.assertEqual(self.planejamento.status, 'CONFIRMADO')

    def test_conclusao_confirma_participantes_data_horario_duracao(self):
        url = reverse('procedures:criar_registros_planejamento', args=[self.planejamento.id])
        resp = self.client.post(
            url,
            {
                'data_treinamento': '2026-03-21',
                'horario_realizado': '14:30',
                'duracao_minutos': '90',
                'participantes_planejados': [str(self.colab1.id)],
                'participantes_adicionais': [str(self.colab3.id)],
            },
        )

        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse('procedures:detalhe_planejamento', args=[self.planejamento.id]))

        self.planejamento.refresh_from_db()
        self.assertEqual(self.planejamento.status, 'REALIZADO')
        self.assertEqual(self.planejamento.data_realizada.isoformat(), '2026-03-21')
        self.assertEqual(self.planejamento.horario_previsto.strftime('%H:%M'), '14:30')
        self.assertEqual(self.planejamento.carga_horaria, 90)

        participantes_ids = set(self.planejamento.colaboradores.values_list('id', flat=True))
        self.assertEqual(participantes_ids, {self.colab1.id, self.colab3.id})

        registros = RegistroTreinamento.objects.filter(
            procedimento=self.procedimento,
            data_treinamento=date(2026, 3, 21),
        )
        self.assertEqual(registros.count(), 2)
