# -*- coding: utf-8 -*-

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from procedures.models import MatrizHabilidade, SolicitacaoValidacaoMatriz
from rh.models import Colaborador


class ValidacoesPendentesViewTest(TestCase):
    def setUp(self):
        # Colaboradores/usuários que serão validadores
        self.user_validador_1 = User.objects.create_user(username='validador1', password='pass12345')
        self.colab_validador_1 = Colaborador.objects.create(
            user_django=self.user_validador_1,
            matricula='V1',
            nome_completo='Validador 1',
            grupo='GRUPO',
            setor=None,
        )

        self.user_validador_2 = User.objects.create_user(username='validador2', password='pass12345')
        self.colab_validador_2 = Colaborador.objects.create(
            user_django=self.user_validador_2,
            matricula='V2',
            nome_completo='Validador 2',
            grupo='GRUPO',
            setor=None,
        )

        self.solicitante = Colaborador.objects.create(
            matricula='S1',
            nome_completo='Solicitante',
            grupo='GRUPO',
            setor=None,
        )

        self.matriz_1 = MatrizHabilidade.objects.create(nome='Matriz 1')
        self.matriz_2 = MatrizHabilidade.objects.create(nome='Matriz 2')

        self.sol_1 = SolicitacaoValidacaoMatriz.objects.create(
            matriz=self.matriz_1,
            solicitante=self.solicitante,
            validador=self.colab_validador_1,
            status='pendente',
            motivo_solicitacao='Motivo 1',
        )
        self.sol_2 = SolicitacaoValidacaoMatriz.objects.create(
            matriz=self.matriz_2,
            solicitante=self.solicitante,
            validador=self.colab_validador_2,
            status='pendente',
            motivo_solicitacao='Motivo 2',
        )

        # Superuser sem perfil de colaborador (cenário que antes retornava lista vazia)
        self.superuser = User.objects.create_superuser(username='admin2', password='pass12345', email='admin2@test.com')

    def test_superuser_sees_all_pending(self):
        self.client.force_login(self.superuser)
        url = reverse('procedures:validacoes_pendentes')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('validacoes', response.context)
        self.assertEqual(response.context['validacoes'].count(), 2)

    def test_normal_user_sees_only_assigned_pending(self):
        self.client.force_login(self.user_validador_1)
        url = reverse('procedures:validacoes_pendentes')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('validacoes', response.context)
        validacoes = list(response.context['validacoes'])
        self.assertEqual(len(validacoes), 1)
        self.assertEqual(validacoes[0].id, self.sol_1.id)
