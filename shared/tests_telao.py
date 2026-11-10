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


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class TelaoProvedoresTests(TestCase):
    """Cada provedor roda direto (sem o amortecedor de erros) e devolve slides válidos, mesmo sem dados."""

    def setUp(self):
        cache.clear()
        self.admin = get_user_model().objects.create_user("adm2", password="x", is_superuser=True, is_staff=True)

    def test_provedores_sem_dados(self):
        for chave, fn in providers.PROVEDORES.items():
            with self.subTest(provedor=chave):
                slides = fn(self.admin)
                self.assertIsInstance(slides, list)
                for s in slides:
                    self.assertIn(s["kind"], {"tiles", "cards", "bars", "chart"})

    def test_todas_as_playlists_montam(self):
        for chave in providers.PLAYLISTS:
            with self.subTest(playlist=chave):
                self.assertTrue(providers.montar_playlist(self.admin, chave))

    def test_metrologia_mostra_totais_mesmo_vazio(self):
        slides = providers.slides_metrologia(self.admin)
        self.assertEqual(slides[0]["kind"], "tiles")

    def test_treinamentos_planejado_aparece(self):
        from datetime import timedelta

        from django.utils import timezone

        from procedures.models import PlanejamentoTreinamento

        PlanejamentoTreinamento.objects.create(titulo="Treino X", data_prevista=timezone.localdate() + timedelta(days=3))
        slides = providers.slides_treinamentos(self.admin)
        cards = [i for s in slides if s["kind"] == "cards" for i in s["itens"]]
        self.assertEqual(cards[0]["titulo"], "Treino X")

    def test_usuario_sem_acesso_nao_ve_modulo(self):
        comum = get_user_model().objects.create_user("comum", password="x")
        self.assertEqual(providers.slides_kpi(comum) + providers.slides_auditoria(comum), [])


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ModeloApresentacaoTests(TestCase):
    def setUp(self):
        cache.clear()
        U = get_user_model()
        self.dono = U.objects.create_user("dono", password="x", is_superuser=True, is_staff=True)
        self.outro = U.objects.create_user("outro2", password="x")
        self.admin2 = U.objects.create_user("adm3", password="x", is_superuser=True, is_staff=True)

    def _criar(self, client, **extra):
        dados = {"nome": "Chão de fábrica", "prov": ["kpi", "ocorrencias"], "dur_kpi": "30", "dur_ocorrencias": "",
                 "duracao_padrao": "10", "ativo": "on", **extra}
        return client.post(reverse("telao_modelo_novo"), dados)

    def test_criar_respeita_ordem_e_duracao(self):
        from shared.models import ModeloApresentacao

        self.client.force_login(self.dono)
        self.assertEqual(self._criar(self.client).status_code, 302)
        m = ModeloApresentacao.objects.get()
        self.assertEqual([i["provedor"] for i in m.itens], ["kpi", "ocorrencias"])
        self.assertEqual(m.itens[0]["duracao"], 30)
        self.assertIsNone(m.itens[1]["duracao"])

    def test_validacao(self):
        from shared.models import ModeloApresentacao

        self.client.force_login(self.dono)
        self.client.post(reverse("telao_modelo_novo"), {"nome": "", "prov": ["kpi"]})
        self.client.post(reverse("telao_modelo_novo"), {"nome": "X", "prov": ["inexistente"]})
        self.assertEqual(ModeloApresentacao.objects.count(), 0)

    def test_playlist_personalizada_usa_duracoes(self):
        from shared.models import ModeloApresentacao

        m = ModeloApresentacao.objects.create(
            nome="M", criado_por=self.dono, duracao_padrao=9,
            itens=[{"provedor": "kpi", "duracao": 30}, {"provedor": "ocorrencias", "duracao": None}, {"provedor": "nao_existe"}])
        slides = providers.montar_playlist(self.dono, m.chave)
        self.assertTrue(slides)
        for s in slides:
            self.assertEqual(s["duracao"], 30 if s["provedor"] == "kpi" else 9)
            self.assertIn(s["provedor"], {"kpi", "ocorrencias"})

    def test_visibilidade(self):
        from shared.models import ModeloApresentacao

        priv = ModeloApresentacao.objects.create(nome="Privada", criado_por=self.dono, itens=[{"provedor": "kpi"}])
        pub = ModeloApresentacao.objects.create(nome="Pública", criado_por=self.dono, compartilhada=True, itens=[{"provedor": "kpi"}])
        self.client.force_login(self.outro)
        nomes = [m.nome for m in providers.modelos_visiveis(self.outro)]
        self.assertEqual(nomes, ["Pública"])
        # chave de modelo invisível cai no padrão, sem erro
        self.assertEqual(self.client.get(reverse("telao") + f"?p={priv.chave}").status_code, 200)
        self.assertEqual(self.client.get(reverse("telao_modelo_editar", args=[pub.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("telao_modelo_excluir", args=[pub.pk])).status_code, 403)
        self.assertTrue(pub.editavel_por(self.admin2))

    def test_telas_e_menu(self):
        from shared.models import ModeloApresentacao

        ModeloApresentacao.objects.create(nome="Minha TV", criado_por=self.dono, itens=[{"provedor": "kpi"}])
        self.client.force_login(self.dono)
        self.assertContains(self.client.get(reverse("telao_modelos")), "Minha TV")
        self.assertEqual(self.client.get(reverse("telao_modelo_novo") + "?base=geral").status_code, 200)
        self.assertContains(self.client.get(reverse("telao") + "?p=m999"), "Calibra")
