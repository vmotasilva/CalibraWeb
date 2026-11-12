from datetime import date

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from kpi.models import Indicador, Medicao
from shared.models import ModeloApresentacao
from shared.telao import cards, layout, providers


def _celulas(pos):
    return {(x, y) for x in range(pos["x"], pos["x"] + pos["w"]) for y in range(pos["y"], pos["y"] + pos["h"])}


class DisposicoesTests(SimpleTestCase):
    def test_posicoes_cabem_na_grade_sem_sobrepor(self):
        for chave, (_r, cap, posicoes) in layout.LAYOUTS.items():
            with self.subTest(layout=chave):
                self.assertEqual(len(posicoes), cap)
                usadas = set()
                for x, y, w, h in posicoes:
                    self.assertTrue(x + w <= cards.COLUNAS and y + h <= cards.LINHAS)
                    c = _celulas(dict(zip("xywh", (x, y, w, h))))
                    self.assertFalse(usadas & c, "cards sobrepostos")
                    usadas |= c
                self.assertEqual(len(usadas), cards.COLUNAS * cards.LINHAS, "a disposição deve preencher o slide")

    def test_juntar_partes_une_listas_divididas_em_lotes(self):
        a = {"kind": "cards", "card_id": "metrologia.criticos", "titulo": "Instrumentos críticos", "subtitulo": "parte 1", "itens": [1, 2, 3, 4]}
        b = {**a, "subtitulo": "parte 2", "itens": [5, 6]}
        outro = {"kind": "tiles", "card_id": "metrologia.totais", "titulo": "Totais", "subtitulo": "x", "itens": [9]}
        juntos = layout.juntar_partes([a, b, outro])
        self.assertEqual([j["card_id"] for j in juntos], ["metrologia.criticos", "metrologia.totais"])
        self.assertEqual(juntos[0]["itens"], [1, 2, 3, 4, 5, 6])
        self.assertEqual(juntos[0]["subtitulo"], "")
        self.assertEqual(a["itens"], [1, 2, 3, 4], "não altera o original")

    def test_compor_automatico_escolhe_disposicao_pela_quantidade(self):
        def sl(n):
            return {"kind": "bars", "card_id": "pcp.frequencias", "titulo": f"B{n}", "subtitulo": "", "itens": []}
        for qtd, esperado in ((1, 1), (2, 2), (3, 3), (4, 4)):
            r = layout.compor([sl(n) for n in range(qtd)], "pcp", layout.AUTO)
            self.assertEqual(len(r), 1)
            self.assertEqual(len(r[0]["itens"]), esperado)
        r = layout.compor([sl(n) for n in range(6)], "pcp", layout.AUTO)
        self.assertEqual([len(s["itens"]) for s in r], [4, 2])
        self.assertIn("(1/2)", r[0]["titulo"])
        self.assertEqual(layout.compor([], "pcp", "2"), [])


class LimparTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user("adm_lay", password="x", is_superuser=True, is_staff=True)

    def test_limpa_slide_manual(self):
        bruto = {"origem": "manual", "titulo": "  Fechamento  ", "duracao": "500", "icone": "x-1", "layout": {"modo": "livre"}, "itens": [
            {"card_id": "kpi.situacao", "pos": {"x": "-5", "y": 10.456, "w": 500, "h": "abc"}, "visual": {"titulo": False, "max_itens": "7"}},
            {"card_id": "nao.existe", "pos": {}},
            "lixo",
            {"card_id": "kpi.graficos", "params": {"ref": "Perda"}, "filtros": {"dias": "999", "graficos": "todos", "layout": "2", "x": 1}},
        ]}
        s = layout.limpar_slide(bruto, self.admin)
        self.assertEqual((s["titulo"], s["duracao"], s["icone"]), ("Fechamento", 120, ""))
        self.assertEqual(s["layout"]["modo"], "livre")
        self.assertEqual(len(s["itens"]), 2)
        p = s["itens"][0]["pos"]
        self.assertEqual((p["x"], p["y"]), (0, 10.46))
        self.assertTrue(p["x"] + p["w"] <= 100 and p["y"] + p["h"] <= 100)
        self.assertEqual(s["itens"][0]["visual"], {"titulo": False, "max_itens": 7})
        self.assertEqual(s["itens"][1]["params"], {"ref": "Perda"})
        self.assertEqual(s["itens"][1]["filtros"], {"graficos": "todos"}, "descarta opção inválida, 'layout' e campo desconhecido")

    def test_capa_e_preservada(self):
        el = {"card_id": "", "el": {"tipo": "titulo", "texto": "Olá"}, "pos": {"x": 0, "y": 0, "w": 12, "h": 2}}
        s = layout.limpar_slide({"origem": "manual", "capa": True, "titulo": "Capa", "itens": [el]}, self.admin)
        self.assertTrue(s["capa"])
        self.assertNotIn("capa", layout.limpar_slide({"origem": "manual", "capa": "sim", "itens": [el]}, self.admin))

    def test_grade_prende_ao_tamanho_da_grade(self):
        s = layout.limpar_slide({"origem": "manual", "itens": [{"card_id": "kpi.situacao", "pos": {"x": 11, "y": 7, "w": 9, "h": 9}}]}, self.admin)
        p = s["itens"][0]["pos"]
        self.assertEqual(p, {"x": 11, "y": 7, "w": 1, "h": 1})

    def test_limpa_slide_automatico_e_assunto(self):
        a = layout.limpar_slide({"origem": "auto", "provedor": "kpi", "filtros": {"layout": "2x2", "graficos": "nenhum", "meses": "7"}}, self.admin)
        self.assertEqual(a["filtros"], {"layout": "2x2", "graficos": "nenhum"})
        self.assertIsNone(layout.limpar_slide({"origem": "auto", "provedor": "xyz"}, self.admin))
        s = layout.limpar_slide({"origem": "auto", "tipo": "assunto", "titulo": "T", "blocos": [{"provedor": "kpi"}, {"provedor": "zzz"}]}, self.admin)
        self.assertEqual([b["provedor"] for b in s["blocos"]], ["kpi"])
        self.assertIsNone(layout.limpar_slide({"origem": "auto", "tipo": "assunto", "blocos": []}, self.admin))
        self.assertEqual(layout.limpar_slides("não é lista", self.admin), [])
        self.assertEqual(len(layout.limpar_slides([{"origem": "manual"}] * 100, self.admin)), layout.MAX_SLIDES)

    def test_editor_oferece_o_campo_de_disposicao_e_valida(self):
        nomes = [c["nome"] for c in providers.campos_filtro("kpi", self.admin)]
        self.assertIn("layout", nomes)
        filtros = providers.limpar_filtros("kpi", lambda k: [], {"f_kpi_layout": "2x2"}.get, self.admin)
        self.assertEqual(filtros["layout"], "2x2")
        self.assertNotIn("layout", providers.limpar_filtros("kpi", lambda k: [], {"f_kpi_layout": "9"}.get, self.admin))


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SlidesComDadosTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = get_user_model().objects.create_user("adm_lay2", password="x", is_superuser=True, is_staff=True)
        for nome in ("Perda", "Retrabalho"):  # dois indicadores fora da meta: 2 gráficos + situação
            ind = Indicador.objects.create(nome=nome, meta=5, sentido="menor", unidade="%")
            Medicao.objects.create(indicador=ind, periodo=date(2026, 1, 31), valor=8, granularidade="mensal")
            Medicao.objects.create(indicador=ind, periodo=date(2026, 2, 28), valor=9, granularidade="mensal")

    def _modelo(self, **kw):
        m = ModeloApresentacao.objects.create(nome="M", criado_por=self.admin, compartilhada=True, **kw)
        return m, providers.montar_playlist(self.admin, m.chave)

    def test_modo_automatico_compoe_cards_em_slides_de_layout(self):
        _m, slides = self._modelo(itens=[{"provedor": "kpi", "duracao": 20, "filtros": {"layout": "auto", "cards": ["situacao", "graficos"], "com_ocorrencias": "nao"}}])
        self.assertEqual([s["kind"] for s in slides], ["layout"])
        s = slides[0]
        self.assertEqual(s["duracao"], 20)
        self.assertEqual([i["card_id"] for i in s["itens"]], ["kpi.situacao", "kpi.graficos", "kpi.graficos"])
        self.assertEqual([i["conteudo"]["kind"] for i in s["itens"]], ["tiles", "chart", "chart"])
        self.assertEqual(s["layout"], {"modo": "grade", "colunas": cards.COLUNAS, "linhas": cards.LINHAS})

    def test_sem_disposicao_continua_um_card_por_slide(self):
        _m, slides = self._modelo(itens=[{"provedor": "kpi", "filtros": {"cards": ["situacao", "graficos"]}}])
        self.assertEqual([s["kind"] for s in slides], ["tiles", "chart", "chart"])

    def test_disposicao_2x2_com_um_card_por_slide_usa_tela_cheia(self):
        _m, slides = self._modelo(itens=[{"provedor": "kpi", "filtros": {"layout": "1", "cards": ["graficos"]}}])
        self.assertEqual(len(slides), 2)
        self.assertEqual(slides[0]["itens"][0]["pos"], {"x": 0, "y": 0, "w": 12, "h": 8})

    def test_assunto_ignora_a_disposicao_dos_blocos(self):
        _m, slides = self._modelo(itens=[{"tipo": "assunto", "titulo": "A", "blocos": [
            {"provedor": "kpi", "filtros": {"layout": "2x2", "cards": ["situacao"]}}]}])
        self.assertEqual(slides[0]["kind"], "pagina")
        self.assertEqual(slides[0]["paineis"][0]["kind"], "tiles")

    def test_slide_manual_resolve_cards_e_instancias_com_dados_ao_vivo(self):
        cfg = {"origem": "manual", "titulo": "Meu slide", "duracao": 30, "layout": {"modo": "grade"}, "itens": [
            {"card_id": "kpi.situacao", "pos": {"x": 0, "y": 0, "w": 12, "h": 2}, "visual": {"titulo": True, "max_itens": 2}},
            {"card_id": "kpi.graficos", "params": {"ref": "Retrabalho"}, "pos": {"x": 0, "y": 2, "w": 12, "h": 6}},
            {"card_id": "pcp.paginas", "pos": {"x": 0, "y": 0, "w": 1, "h": 1}},   # sem dado: some
        ]}
        m, slides = self._modelo(slides=[cfg])
        self.assertEqual(len(slides), 1)
        s = slides[0]
        self.assertEqual((s["kind"], s["titulo"], s["duracao"]), ("layout", "Meu slide", 30))
        self.assertEqual([i["card_id"] for i in s["itens"]], ["kpi.situacao", "kpi.graficos"])
        self.assertEqual(len(s["itens"][0]["conteudo"]["itens"]), 2, "max_itens")
        self.assertEqual(s["itens"][1]["conteudo"]["titulo"], "Retrabalho")
        Medicao.objects.create(indicador=Indicador.objects.get(nome="Retrabalho"), periodo=date(2026, 3, 31), valor=2, granularidade="mensal")
        novo = providers.montar_playlist(self.admin, m.chave)[0]["itens"][1]["conteudo"]
        self.assertEqual(novo["valores"][-1], 2.0, "o slide manual guarda só a posição: o dado é sempre o atual")

    def test_slides_tem_precedencia_sobre_itens_e_slide_sem_dado_vira_vazio(self):
        _m, slides = self._modelo(itens=[{"provedor": "kpi"}], slides=[{"origem": "manual", "titulo": "x", "itens": [
            {"card_id": "pcp.paginas", "pos": {"x": 0, "y": 0, "w": 4, "h": 4}}]}])
        self.assertEqual([s["kind"] for s in slides], ["vazio"])

    def test_slide_automatico_na_configuracao_de_slides(self):
        _m, slides = self._modelo(slides=[
            {"origem": "auto", "provedor": "kpi", "filtros": {"cards": ["graficos"], "layout": "2"}},
            {"origem": "auto", "provedor": "kpi", "filtros": {"cards": ["situacao"]}, "duracao": 40}])
        self.assertEqual([s["kind"] for s in slides], ["layout", "tiles"])
        self.assertEqual(slides[1]["duracao"], 40)

    def test_instancias_do_card(self):
        self.assertEqual(sorted(layout.instancias(self.admin, "kpi.graficos")), ["Perda", "Retrabalho"])
        self.assertEqual(layout.instancias(self.admin, "nao.existe"), [])

    def test_personalizar_congela_o_automatico_em_manual_e_gera_o_mesmo_visual(self):
        auto = {"origem": "auto", "provedor": "kpi", "duracao": 25, "filtros": {"cards": ["situacao", "graficos"], "com_ocorrencias": "nao"}}
        manuais = layout.materializar(self.admin, auto)
        self.assertEqual(len(manuais), 1)
        m = manuais[0]
        self.assertEqual((m["origem"], m["duracao"], m["layout"]["modo"]), ("manual", 25, "grade"))
        self.assertEqual([i["card_id"] for i in m["itens"]], ["kpi.situacao", "kpi.graficos", "kpi.graficos"])
        self.assertEqual({i["params"]["ref"] for i in m["itens"][1:]}, {"Perda", "Retrabalho"})
        self.assertEqual(layout.limpar_slide(m, self.admin)["itens"][0]["pos"], m["itens"][0]["pos"], "já sai válido para salvar")
        _modelo, slides = self._modelo(slides=manuais)
        self.assertEqual([i["conteudo"]["titulo"] for i in slides[0]["itens"][1:]], [i["params"]["ref"] for i in m["itens"][1:]])

    def test_personalizar_assunto(self):
        a = {"origem": "auto", "tipo": "assunto", "titulo": "Resumo", "blocos": [{"provedor": "kpi", "filtros": {"cards": ["situacao", "graficos"]}}]}
        m = layout.materializar(self.admin, a)[0]
        self.assertEqual((m["titulo"], len(m["itens"])), ("Resumo", 3))

    def test_api_devolve_slide_de_layout(self):
        m = ModeloApresentacao.objects.create(nome="API", criado_por=self.admin, slides=[
            {"origem": "auto", "provedor": "kpi", "filtros": {"layout": "auto", "cards": ["situacao", "graficos"]}}])
        self.client.force_login(self.admin)
        slides = self.client.get(reverse("telao_api") + f"?p={m.chave}").json()["slides"]
        self.assertEqual(slides[0]["kind"], "layout")
        self.assertEqual(slides[0]["itens"][0]["conteudo"]["kind"], "tiles")
        self.assertEqual(self.client.get(reverse("telao") + f"?p={m.chave}").status_code, 200)
