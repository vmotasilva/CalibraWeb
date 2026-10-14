# -*- coding: utf-8 -*-
import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from organization.models import Setor
from procedures.models import ColaboradorMatrizHabilidade, MatrizHabilidade
from rh.models import Colaborador


class DesassociarDesligadosTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='desl-tester', password='pass12345', is_staff=True)
        self.client.force_login(self.user)
        setor = Setor.objects.create(nome='Setor Desl')
        self.matriz = MatrizHabilidade.objects.create(nome='Matriz Desl')
        self.desligado = Colaborador.objects.create(
            matricula='D1', nome_completo='Desligado Um', setor=setor, turno='TURNO_1', is_active=False)
        ColaboradorMatrizHabilidade.objects.create(matriz=self.matriz, colaborador=self.desligado, ativo=True)

    def test_pagina_lista_e_remove_desligado(self):
        resp = self.client.get(reverse('procedures:matriz_avaliacoes'), {'matriz': self.matriz.id})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Desligado Um')

        resp = self.client.post(
            reverse('procedures:desassociar_colaboradores', args=[self.matriz.id]),
            data=json.dumps({'colaboradores': [self.desligado.id]}),
            content_type='application/json',
        )
        self.assertEqual(resp.json().get('sucesso'), True, resp.content)
        self.assertEqual(resp.json()['quantidade'], 1)
        self.assertFalse(ColaboradorMatrizHabilidade.objects.filter(matriz=self.matriz).exists())

