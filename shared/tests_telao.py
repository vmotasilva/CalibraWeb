from datetime import date

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from kpi.models import Indicador, Medicao
from laboratorio.models import OcorrenciaLaboratorio
from shared.telao import providers


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class TelaoTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = get_user_model().objects.create_user("admin", password="x", is_superuser=True, is_staff=True)
        OcorrenciaLaboratorio.objects.create(assunto="Falha na estufa", detalhamento="detalhe", criado_por=self.admin)
        ind = Indicador.objects.create(nome="Perda", meta=5, sentido="menor", unidade="%")
        Medicao.objects.create(indicador=ind, periodo=date(2026, 1, 31), valor=8, granularidade="mensal")
        Medicao.objects.create(indicador=ind, periodo=date(2026, 2, 28), valor=9, granularidade="mensal")

    def test_exige_login(self):
        r = self.client.get(reverse("telao_api"))
        self.assertEqual(r.status_code, 302)

    def test_playlist_geral(self):
        self.client.force_login(self.admin)
        slides = self.client.get(reverse("telao_api") + "?p=geral").json()["slides"]
        provs = {s["provedor"] for s in slides}
        self.assertIn("ocorrencias", provs)
        self.assertIn("kpi", provs)
        self.assertTrue(any(s["kind"] == "chart" and s["titulo"] == "Perda" for s in slides))

    def test_resumo_oculta_texto(self):
        slides = providers.slides_ocorrencias(self.admin, resumo=True)
        cards = [i for s in slides if s["kind"] == "cards" for i in s["itens"]]
        self.assertTrue(cards)
        self.assertTrue(all(c["texto"] == "" for c in cards))

    def test_playlist_invalida_cai_no_padrao(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("telao_api") + "?p=xyz").status_code, 200)
        self.assertEqual(self.client.get(reverse("telao") + "?p=xyz").status_code, 200)

    def test_provedor_com_falha_nao_derruba(self):
        original = providers.PROVEDORES["kpi"]
        providers.PROVEDORES["kpi"] = lambda u, resumo=False: 1 / 0
        try:
            slides = providers.montar_playlist(self.admin, "kpi")
        finally:
            providers.PROVEDORES["kpi"] = original
        self.assertEqual(slides[0]["kind"], "vazio")
