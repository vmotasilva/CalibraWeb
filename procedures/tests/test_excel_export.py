# -*- coding: utf-8 -*-
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from rh.models import Colaborador
from procedures.models import MatrizHabilidade, Disciplina, ColaboradorMatrizHabilidade, AvaliacaoHabilidade
from datetime import date

class ExcelExportTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='export-tester', password='pass12345')
        
        # Criar MatrizHabilidade
        self.matriz = MatrizHabilidade.objects.create(
            nome='Matriz de Teste'
        )
        
        # Criar Disciplinas
        self.disc1 = Disciplina.objects.create(
            matriz=self.matriz,
            nome='Disciplina A',
            ativo=True
        )
        self.disc2 = Disciplina.objects.create(
            matriz=self.matriz,
            nome='Disciplina B',
            ativo=True
        )
        
        # Criar Colaboradores
        self.colab1 = Colaborador.objects.create(
            matricula='M1',
            nome_completo='Colaborador A',
            turno='Turno A'
        )
        self.colab2 = Colaborador.objects.create(
            matricula='M2',
            nome_completo='Colaborador B',
            turno='Turno B'
        )
        
        # Associar à Matriz
        ColaboradorMatrizHabilidade.objects.create(
            colaborador=self.colab1,
            matriz=self.matriz,
            ativo=True
        )
        ColaboradorMatrizHabilidade.objects.create(
            colaborador=self.colab2,
            matriz=self.matriz,
            ativo=True
        )
        
        # Adicionar Avaliação
        AvaliacaoHabilidade.objects.create(
            colaborador=self.colab1,
            disciplina=self.disc1,
            matriz=self.matriz,
            nivel=2,
            data_avaliacao=date.today()
        )
        
    def test_export_excel_success(self):
        self.client.force_login(self.user)
        url = reverse('procedures:exportar_matriz_excel')
        response = self.client.get(url, {'matriz': self.matriz.id})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertTrue(response['Content-Disposition'].startswith('attachment; filename="Matriz_Habilidades_'))

    def test_export_excel_requires_login(self):
        url = reverse('procedures:exportar_matriz_excel')
        response = self.client.get(url, {'matriz': self.matriz.id})
        self.assertEqual(response.status_code, 302)

    def test_bulk_export_csv_success(self):
        self.client.force_login(self.user)
        url = reverse('procedures:exportar_matrizes', kwargs={'formato': 'csv'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        content = response.content.decode('utf-8')
        # Check if the headers and delimiters are correct
        self.assertIn('Matriz|Disciplina|Colaborador|Turno|Nota|Data', content)
        # Check that both collaborators are exported (active in the matrix)
        self.assertIn('Colaborador A', content)
        self.assertIn('Colaborador B', content)

    def test_bulk_export_excel_success(self):
        self.client.force_login(self.user)
        url = reverse('procedures:exportar_matrizes', kwargs={'formato': 'excel'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

