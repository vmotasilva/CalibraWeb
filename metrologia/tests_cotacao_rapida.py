from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from metrologia.models import Instrumento, SolicitacaoCotacao, ItemSolicitacaoCotacao
from metrologia.views.novo_fluxo_cotacao import instrumentos_em_cotacao


class CotacaoRapidaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u", password="p")
        self.client.force_login(self.user)
        self.a = Instrumento.objects.create(tag="A-01", descricao="A")
        self.b = Instrumento.objects.create(tag="B-01", descricao="B")

    def test_cria_cotacao_com_instrumentos_selecionados(self):
        r = self.client.post(reverse("metrologia:solicitacao_create"),
                             {"instrumentos_ids": f"{self.a.id},{self.b.id}"})
        sol = SolicitacaoCotacao.objects.get()
        self.assertRedirects(r, reverse("metrologia:solicitacao_detail", args=[sol.id]))
        self.assertEqual(sol.itens.count(), 2)
        self.assertEqual(set(instrumentos_em_cotacao()), {self.a.id, self.b.id})

    def test_ignora_instrumento_ja_em_cotacao(self):
        self.client.post(reverse("metrologia:solicitacao_create"), {"instrumentos_ids": str(self.a.id)})
        self.client.post(reverse("metrologia:solicitacao_create"),
                         {"instrumentos_ids": f"{self.a.id},{self.b.id}"})
        self.assertEqual(SolicitacaoCotacao.objects.count(), 2)
        self.assertEqual(ItemSolicitacaoCotacao.objects.filter(instrumento=self.a).count(), 1)

    def test_encerrada_libera_instrumento(self):
        self.client.post(reverse("metrologia:solicitacao_create"), {"instrumentos_ids": str(self.a.id)})
        SolicitacaoCotacao.objects.get().marcar_concluida()
        self.assertEqual(instrumentos_em_cotacao(), {})

    def test_sem_ids_volta_para_tela_de_instrumentos(self):
        r = self.client.post(reverse("metrologia:solicitacao_create"), {})
        self.assertRedirects(r, reverse("modulo_metrologia"), fetch_redirect_response=False)
        self.assertEqual(SolicitacaoCotacao.objects.count(), 0)

    def test_telas_renderizam_e_mostram_filtro(self):
        self.client.post(reverse("metrologia:solicitacao_create"), {"instrumentos_ids": str(self.a.id)})
        r = self.client.get(reverse("modulo_metrologia"))
        self.assertContains(r, 'data-category="cotacao"')
        self.assertContains(r, 'data-em-cotacao="SIM"')
        self.assertContains(self.client.get(reverse("metrologia:solicitacao_list")), "SOL-")
        r = self.client.get("/dashboard/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'data-cat="cotacao"')

    def test_detalhe_renderiza_enxuto(self):
        self.client.post(reverse("metrologia:solicitacao_create"), {"instrumentos_ids": str(self.a.id)})
        sol = SolicitacaoCotacao.objects.get()
        r = self.client.get(reverse("metrologia:solicitacao_detail", args=[sol.id]))
        self.assertContains(r, "Propostas dos fornecedores")
        self.assertContains(r, "btn-concluir")
        self.assertNotContains(r, "Planejamento de Atendimentos")
