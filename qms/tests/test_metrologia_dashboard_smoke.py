# -*- coding: utf-8 -*-

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from metrologia.models import Instrumento, CategoriaInstrumento
from organization.models import Setor


class MetrologiaDashboardSmokeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pass12345')
        self.client.force_login(self.user)

        self.setor = Setor.objects.create(nome='Setor 1')
        self.categoria = CategoriaInstrumento.objects.create(nome='Categoria 1')

        Instrumento.objects.create(
            tag='TAG-001',
            descricao='Instrumento teste',
            fabricante='Fab',
            modelo='Mod',
            setor=self.setor,
            categoria=self.categoria,
            ativo=True,
        )

    def test_dashboard_renders_and_shows_instrument(self):
        url = reverse('modulo_metrologia')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TAG-001')
