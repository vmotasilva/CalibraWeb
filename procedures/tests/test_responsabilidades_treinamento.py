from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from procedures.models import (
    MatrizProcedimento,
    Procedimento,
    ResponsavelTreinamentoMatriz,
    SubAreaProcedimento,
)
from rh.models import Colaborador


class ResponsabilidadesTreinamentoViewTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='pass123',
        )

        self.matriz = MatrizProcedimento.objects.create(nome='MATRIZ A')
        self.sub_area = SubAreaProcedimento.objects.create(matriz=self.matriz, nome='Bloco A')

        Procedimento.objects.create(
            codigo='POP-100',
            nome='Procedimento Sub-area',
            numero_revisao='01',
            matriz='MATRIZ A',
            sub_area='Bloco A',
        )
        Procedimento.objects.create(
            codigo='POP-101',
            nome='Procedimento Geral',
            numero_revisao='01',
            matriz='MATRIZ A',
            sub_area='',
        )

        self.responsavel_subarea = Colaborador.objects.create(
            matricula='9000',
            nome_completo='Responsavel Subarea',
            grupo='Treinamento',
            turno='ADM',
        )
        self.responsavel_geral = Colaborador.objects.create(
            matricula='9001',
            nome_completo='Responsavel Geral',
            grupo='Treinamento',
            turno='ADM',
        )

    def test_renderiza_faixa_da_matriz_com_subarea_e_secao_geral(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('procedures:procedimento_responsabilidades_treinamento'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Responsaveis por Matriz, Sub-area e Turno')
        self.assertContains(response, 'MATRIZ A')
        self.assertContains(response, 'Bloco A')
        self.assertContains(response, 'Sem sub-área')

    def test_salva_responsabilidades_por_subarea_e_escopo_geral(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('procedures:procedimento_responsabilidades_treinamento'),
            {
                f'resp_{self.matriz.id}_sa{self.sub_area.id}_ADM': str(self.responsavel_subarea.id),
                f'resp_{self.matriz.id}_geral_ADM': str(self.responsavel_geral.id),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ResponsavelTreinamentoMatriz.objects.filter(
                matriz=self.matriz,
                sub_area=self.sub_area,
                turno='ADM',
                colaborador=self.responsavel_subarea,
            ).exists()
        )
        self.assertTrue(
            ResponsavelTreinamentoMatriz.objects.filter(
                matriz=self.matriz,
                sub_area__isnull=True,
                turno='ADM',
                colaborador=self.responsavel_geral,
            ).exists()
        )
