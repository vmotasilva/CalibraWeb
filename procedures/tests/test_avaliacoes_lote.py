# -*- coding: utf-8 -*-
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from rh.models import Colaborador
from organization.models import Setor
from procedures.models import MatrizHabilidade, Disciplina, ColaboradorMatrizHabilidade, AvaliacaoHabilidade, HistoricoAvaliacaoHabilidade
from datetime import date

class BatchApplyEvaluationsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='batch-tester', password='pass12345')
        
        # Criar Setores
        self.setor1 = Setor.objects.create(nome='Setor Teste 1')
        self.setor2 = Setor.objects.create(nome='Setor Teste 2')
        
        # Criar MatrizHabilidade
        self.matriz = MatrizHabilidade.objects.create(nome='Matriz Lote')
        
        # Criar Disciplina
        self.disc = Disciplina.objects.create(
            matriz=self.matriz,
            nome='Disciplina Lote',
            ativo=True
        )
        
        # Criar Colaboradores
        self.colab1 = Colaborador.objects.create(
            matricula='C1',
            nome_completo='Colaborador Um',
            setor=self.setor1,
            turno='TURNO_1',
            is_active=True
        )
        self.colab2 = Colaborador.objects.create(
            matricula='C2',
            nome_completo='Colaborador Dois',
            setor=self.setor1,
            turno='TURNO_2',
            is_active=True
        )
        self.colab3 = Colaborador.objects.create(
            matricula='C3',
            nome_completo='Colaborador Tres',
            setor=self.setor2,
            turno='TURNO_1',
            is_active=True
        )
        
        # Associar à Matriz
        for colab in [self.colab1, self.colab2, self.colab3]:
            ColaboradorMatrizHabilidade.objects.create(
                colaborador=colab,
                matriz=self.matriz,
                ativo=True
            )
            
        # Adicionar uma avaliação pré-existente para colab1
        self.eval1 = AvaliacaoHabilidade.objects.create(
            colaborador=self.colab1,
            disciplina=self.disc,
            matriz=self.matriz,
            nivel=1,
            data_avaliacao=date(2026, 1, 1),
            observacoes='Nota inicial'
        )

    def test_batch_apply_all_overwriting(self):
        self.client.force_login(self.user)
        url = reverse('procedures:salvar_avaliacao_lote_api', kwargs={'matriz_id': self.matriz.id, 'disciplina_id': self.disc.id})
        
        payload = {
            'nivel': 2,
            'data_avaliacao': '2026-06-08',
            'observacoes': 'Treinamento em lote',
            'somente_sem_avaliacao': False
        }
        
        response = self.client.post(url, payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['sucesso'])
        self.assertEqual(data['count'], 3) # Todos os 3 devem ser atualizados/criados
        
        # Verificar que colab1 foi atualizado para nivel 2
        eval1_updated = AvaliacaoHabilidade.objects.get(colaborador=self.colab1, disciplina=self.disc, matriz=self.matriz)
        self.assertEqual(eval1_updated.nivel, 2)
        self.assertEqual(eval1_updated.observacoes, 'Treinamento em lote')
        
        # Verificar que colab2 e colab3 ganharam avaliação com nivel 2
        self.assertTrue(AvaliacaoHabilidade.objects.filter(colaborador=self.colab2, nivel=2).exists())
        self.assertTrue(AvaliacaoHabilidade.objects.filter(colaborador=self.colab3, nivel=2).exists())
        
        # Verificar que historicos foram gerados
        self.assertEqual(HistoricoAvaliacaoHabilidade.objects.filter(avaliacao__disciplina=self.disc).count(), 3)

    def test_batch_apply_only_empty_cells(self):
        self.client.force_login(self.user)
        url = reverse('procedures:salvar_avaliacao_lote_api', kwargs={'matriz_id': self.matriz.id, 'disciplina_id': self.disc.id})
        
        payload = {
            'nivel': 3,
            'data_avaliacao': '2026-06-08',
            'observacoes': 'Apenas vazios',
            'somente_sem_avaliacao': True
        }
        
        response = self.client.post(url, payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['sucesso'])
        self.assertEqual(data['count'], 2) # Apenas colab2 e colab3 devem ser criados
        
        # Verificar que colab1 continua no nível 1 (não foi alterado)
        eval1_check = AvaliacaoHabilidade.objects.get(colaborador=self.colab1, disciplina=self.disc, matriz=self.matriz)
        self.assertEqual(eval1_check.nivel, 1)
        
        # Verificar que colab2 e colab3 foram definidos para o nível 3
        eval2_check = AvaliacaoHabilidade.objects.get(colaborador=self.colab2, disciplina=self.disc, matriz=self.matriz)
        self.assertEqual(eval2_check.nivel, 3)
        eval3_check = AvaliacaoHabilidade.objects.get(colaborador=self.colab3, disciplina=self.disc, matriz=self.matriz)
        self.assertEqual(eval3_check.nivel, 3)

    def test_batch_apply_specific_collaborator_ids(self):
        self.client.force_login(self.user)
        url = reverse('procedures:salvar_avaliacao_lote_api', kwargs={'matriz_id': self.matriz.id, 'disciplina_id': self.disc.id})
        
        # Aplicar somente para colab1 e colab2
        payload = {
            'nivel': 2,
            'data_avaliacao': '2026-06-08',
            'somente_sem_avaliacao': False,
            'colaborador_ids': [self.colab1.id, self.colab2.id]
        }
        
        response = self.client.post(url, payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 2)
        
        # colab3 não deve ter ganho avaliação
        self.assertFalse(AvaliacaoHabilidade.objects.filter(colaborador=self.colab3, disciplina=self.disc).exists())

    def test_batch_apply_with_filters(self):
        self.client.force_login(self.user)
        url = reverse('procedures:salvar_avaliacao_lote_api', kwargs={'matriz_id': self.matriz.id, 'disciplina_id': self.disc.id})
        
        # Filtrar por setor 1 (contém colab1 e colab2, mas não colab3)
        payload = {
            'nivel': 3,
            'data_avaliacao': '2026-06-08',
            'somente_sem_avaliacao': False,
            'setor_id': self.setor1.id
        }
        
        response = self.client.post(url, payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 2)
        
        # Verificar que colab1 e colab2 foram atualizados/criados com nivel 3
        self.assertEqual(AvaliacaoHabilidade.objects.get(colaborador=self.colab1, disciplina=self.disc).nivel, 3)
        self.assertEqual(AvaliacaoHabilidade.objects.get(colaborador=self.colab2, disciplina=self.disc).nivel, 3)
        
        # colab3 continua sem avaliação
        self.assertFalse(AvaliacaoHabilidade.objects.filter(colaborador=self.colab3, disciplina=self.disc).exists())
