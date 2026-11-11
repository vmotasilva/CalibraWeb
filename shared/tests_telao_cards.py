from datetime import date

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from kpi.models import Indicador, Medicao
from laboratorio.models import OcorrenciaLaboratorio
from shared.telao import cards, providers


class CatalogoDeCardsTests(SimpleTestCase):
    def test_todo_card_do_codigo_tem_metadados_e_vice_versa(self):
        esperados = {cards.card_id(m, c[0]) for m, lista in providers.PROVEDOR_CARDS.items() for c in lista}
        self.assertEqual(esperados, set(cards.CARDS))

    def test_formas_e_secoes_validas(self):
        secoes = {k for k, _ in cards.SECOES}
        for cid, (secao, forma, _inst) in cards.CARDS.items():
            with self.subTest(card=cid):
                self.assertIn(secao, secoes)
                self.assertIn(forma, cards.TAMANHOS)

    def test_tamanhos_cabem_na_grade_e_padrao_nao_menor_que_minimo(self):
        for forma, (minimo, padrao) in cards.TAMANHOS.items():
            with self.subTest(forma=forma):
                self.assertTrue(minimo[0] <= padrao[0] <= cards.COLUNAS)
                self.assertTrue(minimo[1] <= padrao[1] <= cards.LINHAS)

    def test_catalogo_hierarquia_modulo_secao_card(self):
        cat = cards.catalogo()
        self.assertEqual([m["id"] for m in cat], list(providers.ROTULOS_PROVEDORES))
        ids = [c["id"] for m in cat for s in m["secoes"] for c in s["cards"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), set(cards.CARDS))
        self.assertTrue(all(s["cards"] for m in cat for s in m["secoes"]))  # sem seção vazia


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class CardIdNosSlidesTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = get_user_model().objects.create_user("adm_cards", password="x", is_superuser=True, is_staff=True)
        OcorrenciaLaboratorio.objects.create(assunto="Falha na estufa", detalhamento="d", criado_por=self.admin)
        ind = Indicador.objects.create(nome="Perda", meta=5, sentido="menor", unidade="%")
        Medicao.objects.create(indicador=ind, periodo=date(2026, 1, 31), valor=8, granularidade="mensal")

    def test_slides_trazem_card_id_do_catalogo(self):
        self.client.force_login(self.admin)
        slides = self.client.get(reverse("telao_api") + "?p=geral").json()["slides"]
        with_card = [s for s in slides if s["kind"] != "vazio"]
        self.assertTrue(with_card)
        for s in with_card:
            with self.subTest(slide=s["titulo"]):
                self.assertIn(s["card_id"], cards.CARDS)
                self.assertEqual(cards.card_do_slide(s)["forma"], s["kind"])

    def test_forma_do_catalogo_bate_com_o_slide_gerado(self):
        """Evita o catálogo e o gerador divergirem (ex.: card declarado 'bars' que o gerador entrega como 'chart')."""
        for chave, fn in providers.PROVEDORES.items():
            for s in providers._slides_provedor(self.admin, chave, {}, False, []):
                if s["card_id"]:
                    with self.subTest(card=s["card_id"], titulo=s["titulo"]):
                        self.assertEqual(cards.CARDS[s["card_id"]][1], s["kind"])
