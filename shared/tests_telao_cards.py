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


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class KpiSituacaoEMotivosTests(TestCase):
    def setUp(self):
        cache.clear()
        from kpi.models import Motivo

        self.admin = get_user_model().objects.create_user("adm_kpi_cards", password="x", is_superuser=True, is_staff=True)
        self.ind = Indicador.objects.create(nome="Quebras", meta=5, sentido="menor", unidade="%")
        Medicao.objects.create(indicador=self.ind, periodo=date(2026, 1, 31), valor=8, granularidade="mensal")
        for dia, desc, q in ((1, "Risco de garra", 9), (1, "Laser trincado", 3), (2, "risco de garra", 2), (2, "Batida", 1)):
            Motivo.objects.create(indicador=self.ind, granularidade="diaria", data=date(2026, 3, dia), descricao=desc, quantidade=q)

    def _tiles(self, filtros):
        return [s for s in providers.slides_kpi(self.admin, filtros=filtros) if s["kind"] == "tiles"][0]["itens"]

    def test_tiles_separam_situacao_geral_dos_indicadores(self):
        itens = self._tiles({})
        self.assertEqual([i["grupo"] for i in itens], ["situacao"] * 3 + ["indicador"])
        self.assertEqual([i["rotulo"] for i in itens][:3], ["Na meta", "Fora da meta", "Sem dado"])

    def test_cada_item_da_situacao_geral_pode_ser_ocultado(self):
        self.assertEqual([i["rotulo"] for i in self._tiles({"ocultar_na_meta": True, "ocultar_sem_dado": True})], ["Fora da meta", "Quebras"])
        todos = self._tiles({"ocultar_na_meta": True, "ocultar_fora": True, "ocultar_sem_dado": True})
        self.assertEqual([i["rotulo"] for i in todos], ["Quebras"])

    def test_card_de_motivos_so_aparece_quando_pedido(self):
        self.assertFalse([s for s in providers.slides_kpi(self.admin, filtros={}) if s["kind"] == "bars"])
        s = [s for s in providers._slides_provedor(self.admin, "kpi", {"cards": ["motivos"]}, False, [])][0]
        self.assertEqual((s["card_id"], s["kind"], s["titulo"]), ("kpi.motivos", "bars", "Quebras"))
        self.assertEqual([i["rotulo"] for i in s["itens"]], ["1. risco de garra", "2. Laser trincado", "3. Batida"])
        self.assertEqual(s["itens"][0]["txt"], "11 · 73%")  # soma de "Risco de garra" nos dois dias / total de 15
        self.assertEqual(s["itens"][0]["pct"], 100)  # barra proporcional ao maior

    def test_periodo_dos_motivos(self):
        s = providers._slides_provedor(self.admin, "kpi", {"cards": ["motivos"], "motivos_periodo": "dia"}, False, [])[0]
        self.assertEqual([i["rotulo"] for i in s["itens"]], ["1. risco de garra", "2. Batida"])  # só o último dia lançado

    def test_card_de_motivos_no_slide_manual(self):
        from shared.telao import layout

        item = layout.limpar_item({"card_id": "kpi.motivos", "params": {"ref": "Quebras"}}, "grade", self.admin)
        conteudo = layout.resolver_item(self.admin, item, False, [], {})
        self.assertEqual(conteudo["kind"], "bars")
        self.assertEqual(layout.instancias(self.admin, "kpi.motivos"), ["Quebras"])


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class KpiGraficoConfiguravelTests(TestCase):
    def setUp(self):
        cache.clear()
        from kpi.models import SetorIndicador

        self.admin = get_user_model().objects.create_user("adm_kpi_graf", password="x", is_superuser=True, is_staff=True)
        self.ind = Indicador.objects.create(nome="Quebras", meta=5, sentido="menor", unidade="%")
        self.setores = [SetorIndicador.objects.create(indicador=self.ind, nome=n, meta=5) for n in ("HMC", "Montagem")]
        for k in range(1, 5):  # 4 meses
            Medicao.objects.create(indicador=self.ind, periodo=date(2026, k, 28), valor=4 + k, granularidade="mensal")
        for d in range(1, 11):  # 10 dias de março e 5 de abril
            Medicao.objects.create(indicador=self.ind, periodo=date(2026, 3, d), valor=d, granularidade="diaria")
        for d in range(1, 6):
            Medicao.objects.create(indicador=self.ind, periodo=date(2026, 4, d), valor=10 + d, granularidade="diaria")
        for s in self.setores:
            for k in (1, 2, 3):
                Medicao.objects.create(indicador=self.ind, setor=s, periodo=date(2026, k, 28), valor=2, granularidade="mensal")

    def _grafico(self, **filtros):
        s = providers._slides_provedor(self.admin, "kpi", {"cards": ["graficos"], "graficos": "todos", **filtros}, False, [])
        return [x for x in s if x["titulo"] == "Quebras"][0]

    def test_padrao_continua_sendo_linha_mensal(self):
        g = self._grafico()
        self.assertEqual((g["tipo"], g["labels"][-1]), ("linha", "04/2026"))

    def test_periodo_diario_ultimos_n(self):
        g = self._grafico(serie="diaria", ultimos="3")
        self.assertEqual(g["labels"], ["03/04", "04/04", "05/04"])
        self.assertIn("diário", g["subtitulo"])

    def test_dentro_da_ultima_competencia(self):
        g = self._grafico(serie="diaria", janela="competencia")
        self.assertEqual(g["labels"], ["01/04", "02/04", "03/04", "04/04", "05/04"])  # só abril, o último mês com dado
        self.assertIn("última competência", g["subtitulo"])

    def test_tipo_barras(self):
        g = self._grafico(tipo_grafico="barras", serie="mensal", ultimos="2")
        self.assertEqual((g["tipo"], len(g["labels"]), len(g["atingiu"])), ("barras", 2, 2))

    def test_barras_empilhadas_por_setor(self):
        g = self._grafico(tipo_grafico="empilhadas", serie="mensal")
        self.assertEqual(g["tipo"], "empilhadas")
        self.assertEqual(sorted(s["nome"] for s in g["series"]), ["HMC", "Montagem"])
        self.assertEqual(g["valores"], [4.0, 4.0, 4.0])  # 2 + 2 por mês

    def test_empilhado_sem_setores_vira_barras(self):
        Medicao.objects.filter(setor__isnull=False).delete()
        self.assertEqual(self._grafico(tipo_grafico="empilhadas")["tipo"], "barras")


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class MotivosConfiguraveisTests(TestCase):
    def setUp(self):
        cache.clear()
        from kpi.models import Motivo

        self.admin = get_user_model().objects.create_user("adm_mot_cfg", password="x", is_superuser=True, is_staff=True)
        ind = Indicador.objects.create(nome="Quebras", meta=5, sentido="menor", unidade="%")
        Medicao.objects.create(indicador=ind, periodo=date(2026, 1, 31), valor=8, granularidade="mensal")
        for desc, q in (("Risco de garra", 9), ("Laser trincado", 3)):
            Motivo.objects.create(indicador=ind, granularidade="diaria", data=date(2026, 3, 1), descricao=desc, quantidade=q)

    def _slide(self, **f):
        return providers._slides_provedor(self.admin, "kpi", {"cards": ["motivos"], **f}, False, [])[0]

    def test_informacao_exibida(self):
        self.assertEqual(self._slide()["itens"][0]["txt"], "9 · 75%")
        self.assertEqual(self._slide(motivos_exibir="quantidade")["itens"][0]["txt"], "9")
        self.assertEqual(self._slide(motivos_exibir="percentual")["itens"][0]["txt"], "75,0%")

    def test_barra_e_prioridade_do_texto(self):
        s = self._slide()
        self.assertEqual((s["sem_barra"], s["texto_prioritario"]), (False, False))
        s = self._slide(motivos_sem_barra=True, motivos_texto=True)
        self.assertEqual((s["sem_barra"], s["texto_prioritario"]), (True, True))

    def test_subtitulo_do_card_oculta_separado_do_titulo(self):
        from shared.telao import layout

        v = layout.limpar_item({"card_id": "kpi.motivos", "visual": {"titulo": True, "subtitulo": False}}, "grade", self.admin)["visual"]
        self.assertEqual((v["titulo"], v["subtitulo"]), (True, False))
        v = layout.limpar_item({"card_id": "kpi.motivos", "visual": {}}, "grade", self.admin)["visual"]
        self.assertNotIn("subtitulo", v)
