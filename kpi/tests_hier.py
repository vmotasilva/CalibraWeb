from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from kpi.models import HierCategoria, HierConsumo, HierSetor, HierSubcategoria, KpiHierarquico


class KpiHierarquicoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('hier', 'h@x.com', 'x')
        self.client.force_login(self.user)
        self.kpi = KpiHierarquico.objects.get(nome='Insumos')  # semeado pela migração
        self.setor = self.kpi.setores.get(nome='Surfaçagem')
        self.cat = HierCategoria.objects.create(setor=self.setor, nome='Corte Orbit 2.0')
        self.diamante = HierSubcategoria.objects.create(categoria=self.cat, nome='Diamante', unidade='un', meta=Decimal('10'))
        self.fresa = HierSubcategoria.objects.create(categoria=self.cat, nome='Fresa', unidade='un', meta=Decimal('4'))

    def test_semente_tem_os_tres_setores(self):
        self.assertEqual(set(self.kpi.setores.values_list('nome', flat=True)), {'Surfaçagem', 'HMC', 'Montagem'})

    def test_cadastro_cria_toda_a_arvore(self):
        r = self.client.post(reverse('kpi:hier_cadastro_salvar'), {'tipo': 'categoria', 'pai': self.setor.pk, 'nome': 'Polimento DLP'})
        self.assertEqual(r.status_code, 302)
        cat = HierCategoria.objects.get(nome='Polimento DLP')
        self.client.post(reverse('kpi:hier_cadastro_salvar'),
                         {'tipo': 'sub', 'pai': cat.pk, 'nome': 'Líquido polidor', 'unidade': 'L', 'meta': '12,5'})
        sub = HierSubcategoria.objects.get(nome='Líquido polidor')
        self.assertEqual(sub.meta, Decimal('12.5'))
        self.assertEqual(sub.categoria.setor.kpi, self.kpi)

    def test_nome_duplicado_no_mesmo_nivel_nao_quebra(self):
        r = self.client.post(reverse('kpi:hier_cadastro_salvar'), {'tipo': 'categoria', 'pai': self.setor.pk, 'nome': 'Corte Orbit 2.0'}, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(HierCategoria.objects.filter(setor=self.setor, nome='Corte Orbit 2.0').count(), 1)

    def test_lancar_consumo_atualiza_o_mesmo_mes(self):
        url = reverse('kpi:hier_lancar')
        self.client.post(url, {'mes': '2026-10', f'valor_{self.diamante.pk}': '8', f'valor_{self.fresa.pk}': '5,5'})
        self.client.post(url, {'mes': '2026-10', f'valor_{self.diamante.pk}': '9', f'valor_{self.fresa.pk}': ''})
        self.assertEqual(HierConsumo.objects.count(), 2)
        self.assertEqual(HierConsumo.objects.get(subcategoria=self.diamante).valor, Decimal('9'))
        self.assertEqual(HierConsumo.objects.get(subcategoria=self.fresa).valor, Decimal('5.5'))  # em branco não altera
        self.assertEqual(HierConsumo.objects.get(subcategoria=self.diamante).periodo, date(2026, 10, 31))

    def test_painel_filtra_na_hierarquia_e_calcula_status(self):
        HierConsumo.objects.create(subcategoria=self.diamante, periodo=date(2026, 10, 31), valor=8)
        HierConsumo.objects.create(subcategoria=self.fresa, periodo=date(2026, 10, 31), valor=6)
        r = self.client.get(reverse('kpi:hier_painel'), {'kpi': self.kpi.pk, 'setor': self.setor.pk, 'categoria': self.cat.pk, 'mes': '2026-10'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.context['dentro'], r.context['fora']), (1, 1))
        self.assertEqual(r.context['serie']['modo'], 'percentual')
        r = self.client.get(reverse('kpi:hier_painel'), {'kpi': self.kpi.pk, 'setor': self.setor.pk, 'categoria': self.cat.pk, 'sub': self.fresa.pk, 'mes': '2026-10'})
        self.assertEqual(r.context['serie']['modo'], 'valor')
        self.assertEqual(r.context['serie']['valores'][-1], 6.0)
        self.assertEqual(r.context['serie']['meta'], 4.0)

    def test_excluir_consumo_e_cascata_do_cadastro(self):
        HierConsumo.objects.create(subcategoria=self.diamante, periodo=date(2026, 10, 31), valor=8)
        self.client.post(reverse('kpi:hier_consumo_excluir', args=[self.diamante.pk]), {'mes': '2026-10'})
        self.assertFalse(HierConsumo.objects.exists())
        self.client.post(reverse('kpi:hier_cadastro_excluir'), {'tipo': 'categoria', 'pk': self.cat.pk})
        self.assertFalse(HierSubcategoria.objects.exists())

    def test_telas_de_cadastro_e_painel_vazio_abrem(self):
        self.assertEqual(self.client.get(reverse('kpi:hier_cadastro')).status_code, 200)
        HierSetor.objects.all().delete()
        self.assertEqual(self.client.get(reverse('kpi:hier_painel')).status_code, 200)
