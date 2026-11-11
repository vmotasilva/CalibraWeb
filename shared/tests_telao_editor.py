import json
from datetime import date

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from kpi.models import Indicador, Medicao
from shared.models import ModeloApresentacao
from shared.telao import cards, layout


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class EditorTests(TestCase):
    def setUp(self):
        cache.clear()
        U = get_user_model()
        self.dono = U.objects.create_user("dono_ed", password="x", is_staff=False)
        self.outro = U.objects.create_user("outro_ed", password="x")
        self.admin = U.objects.create_user("adm_ed", password="x", is_superuser=True, is_staff=True)
        for nome in ("Perda", "Retrabalho"):
            ind = Indicador.objects.create(nome=nome, meta=5, sentido="menor", unidade="%")
            Medicao.objects.create(indicador=ind, periodo=date(2026, 1, 31), valor=8, granularidade="mensal")
        self.client.force_login(self.admin)

    def _post(self, nome, corpo):
        return self.client.post(reverse(nome), json.dumps(corpo), content_type="application/json")

    # ---- página
    def test_exige_login(self):
        self.client.logout()
        for nome in ("telao_editor_novo", "telao_editor_instancias"):
            self.assertEqual(self.client.get(reverse(nome)).status_code, 302)
        for nome in ("telao_editor_salvar", "telao_editor_previa", "telao_editor_personalizar"):
            self.assertEqual(self.client.post(reverse(nome), "{}", content_type="application/json").status_code, 302)

    def test_pagina_novo_traz_catalogo_e_slides_da_geral(self):
        r = self.client.get(reverse("telao_editor_novo"))
        self.assertEqual(r.status_code, 200)
        dados = r.context["dados"]
        self.assertEqual(len(dados["catalogo"]), 7)
        self.assertEqual([s["provedor"] for s in dados["slides"]][:2], ["ocorrencias", "kpi"])
        self.assertEqual(dados["grade"], {"colunas": cards.COLUNAS, "linhas": cards.LINHAS})
        self.assertIn("layout", [c["nome"] for c in dados["campos"]["kpi"]])
        self.assertContains(r, 'id="edDados"')

    def test_campos_separam_configuracao_de_filtro(self):
        campos = {c["nome"]: c for c in self.client.get(reverse("telao_editor_novo")).context["dados"]["campos"]["kpi"]}
        self.assertFalse(campos["indicadores"]["config"])
        self.assertFalse(campos["setores"]["config"])
        self.assertEqual((campos["tipo_grafico"]["config"], campos["tipo_grafico"]["cards"]), (True, ["kpi.graficos"]))
        self.assertEqual(campos["ocultar_fora"]["cards"], ["kpi.situacao"])
        self.assertEqual(campos["comentarios"]["cards"], ["kpi.ocorrencias"])

    def test_pagina_de_modelo_antigo_converte_para_slides_automaticos(self):
        m = ModeloApresentacao.objects.create(nome="Antigo", criado_por=self.admin, itens=[
            {"provedor": "kpi", "duracao": 20, "filtros": {"cards": ["situacao"]}},
            {"tipo": "assunto", "titulo": "A", "blocos": [{"provedor": "pcp", "filtros": {}}]}])
        dados = self.client.get(reverse("telao_editor", args=[m.pk])).context["dados"]
        self.assertEqual([(s["origem"], s.get("provedor") or s.get("tipo")) for s in dados["slides"]], [("auto", "kpi"), ("auto", "assunto")])
        self.assertEqual(dados["slides"][0]["duracao"], 20)

    def test_copia_de_modelo(self):
        m = ModeloApresentacao.objects.create(nome="Base", criado_por=self.admin, compartilhada=True, slides=[
            {"origem": "manual", "titulo": "X", "itens": []}])
        dados = self.client.get(reverse("telao_editor_novo") + f"?base={m.chave}").context["dados"]
        self.assertEqual(dados["modelo"]["nome"], "Base (cópia)")
        self.assertEqual(dados["slides"][0]["titulo"], "X")
        self.assertIsNone(dados["modelo"]["id"])

    def test_so_o_dono_ou_admin_edita(self):
        m = ModeloApresentacao.objects.create(nome="D", criado_por=self.dono, compartilhada=True, slides=[{"origem": "manual", "titulo": "X"}])
        self.client.force_login(self.outro)
        self.assertEqual(self.client.get(reverse("telao_editor", args=[m.pk])).status_code, 403)
        r = self._post("telao_editor_salvar", {"id": m.pk, "nome": "Hack", "slides": [{"origem": "manual"}]})
        self.assertEqual(r.status_code, 403)
        m.refresh_from_db()
        self.assertEqual(m.nome, "D")
        self.client.force_login(self.dono)
        self.assertEqual(self.client.get(reverse("telao_editor", args=[m.pk])).status_code, 200)

    def test_formulario_antigo_redireciona_para_o_editor_quando_ha_slides(self):
        m = ModeloApresentacao.objects.create(nome="N", criado_por=self.admin, slides=[{"origem": "manual", "titulo": "X"}])
        r = self.client.get(reverse("telao_modelo_editar", args=[m.pk]))
        self.assertRedirects(r, reverse("telao_editor", args=[m.pk]))
        legado = ModeloApresentacao.objects.create(nome="L", criado_por=self.admin, itens=[{"provedor": "kpi"}])
        self.assertEqual(self.client.get(reverse("telao_modelo_editar", args=[legado.pk])).status_code, 200)

    # ---- salvar
    def test_salvar_cria_e_edita(self):
        corpo = {"id": None, "nome": "  Minha  ", "descricao": "d", "icone": "bi-star", "duracao_padrao": 999, "resumo": True, "compartilhada": True,
                 "slides": [{"origem": "auto", "provedor": "kpi", "filtros": {"layout": "2"}},
                            {"origem": "manual", "titulo": "M", "itens": [{"card_id": "kpi.situacao", "pos": {"x": 0, "y": 0, "w": 12, "h": 2}}, {"card_id": "x.y"}]}]}
        r = self._post("telao_editor_salvar", corpo)
        self.assertEqual(r.status_code, 200, r.content)
        m = ModeloApresentacao.objects.get(pk=r.json()["id"])
        self.assertEqual((m.nome, m.icone, m.duracao_padrao, m.resumo, m.compartilhada, m.criado_por), ("Minha", "bi-star", 120, True, True, self.admin))
        self.assertEqual([s["origem"] for s in m.slides], ["auto", "manual"])
        self.assertEqual(len(m.slides[1]["itens"]), 1, "card inexistente descartado")
        self.assertEqual(m.itens, [])
        corpo.update(id=m.pk, nome="Outro", slides=[m.slides[1]])
        self.assertEqual(self._post("telao_editor_salvar", corpo).status_code, 200)
        m.refresh_from_db()
        self.assertEqual((m.nome, len(m.slides)), ("Outro", 1))
        self.assertEqual(ModeloApresentacao.objects.count(), 1)

    def test_salvar_posicao_livre_mantem_percentuais_e_ordem(self):
        slide = {"origem": "manual", "titulo": "L", "layout": {"modo": "livre"}, "itens": [
            {"card_id": "kpi.situacao", "pos": {"x": 10.5, "y": 30, "w": 47, "h": 43}},
            {"card_id": "kpi.graficos", "pos": {"x": 90, "y": 90, "w": 50, "h": 50}}]}
        r = self._post("telao_editor_salvar", {"nome": "Livre", "slides": [slide]})
        self.assertEqual(r.status_code, 200, r.content)
        s = ModeloApresentacao.objects.get(pk=r.json()["id"]).slides[0]
        self.assertEqual(s["layout"]["modo"], "livre")
        self.assertEqual([i["card_id"] for i in s["itens"]], ["kpi.situacao", "kpi.graficos"], "a ordem define quem fica por cima")
        self.assertEqual(s["itens"][0]["pos"], {"x": 10.5, "y": 30.0, "w": 47.0, "h": 43.0})
        self.assertEqual(s["itens"][1]["pos"], {"x": 90.0, "y": 90.0, "w": 10.0, "h": 10.0}, "limitado à borda do slide")

    def test_salvar_grade_com_colunas_e_linhas_escolhidas(self):
        slide = {"origem": "manual", "titulo": "G", "layout": {"modo": "grade", "colunas": 6, "linhas": 3}, "itens": [
            {"card_id": "kpi.situacao", "pos": {"x": 4, "y": 2, "w": 9, "h": 9}}]}
        r = self._post("telao_editor_salvar", {"nome": "G", "slides": [slide, {"origem": "manual", "layout": {"colunas": 99, "linhas": 0}}]})
        s = ModeloApresentacao.objects.get(pk=r.json()["id"]).slides
        self.assertEqual(s[0]["layout"], {"modo": "grade", "colunas": 6, "linhas": 3})
        self.assertEqual(s[0]["itens"][0]["pos"], {"x": 4, "y": 2, "w": 2, "h": 1}, "cabe na grade escolhida")
        self.assertEqual((s[1]["layout"]["colunas"], s[1]["layout"]["linhas"]), (24, 1), "limites 1-24 e 1-16")

    def test_tema_do_slide_e_salvo_e_chega_ao_player(self):
        r = self._post("telao_editor_salvar", {"nome": "Claro", "tema": "claro", "slides": [{"origem": "auto", "provedor": "kpi"}]})
        m = ModeloApresentacao.objects.get(pk=r.json()["id"])
        self.assertEqual(m.tema, "claro")
        self.assertEqual(self.client.get(reverse("telao_editor", args=[m.pk])).context["dados"]["modelo"]["tema"], "claro")
        self.assertContains(self.client.get(reverse("telao") + f"?p={m.chave}"), 'class="tl claro"')
        self.assertNotContains(self.client.get(reverse("telao") + f"?p={m.chave}&tema=escuro"), 'class="tl claro"')
        self.assertContains(self.client.get(reverse("telao") + "?p=geral&tema=claro"), 'class="tl claro"')
        r = self._post("telao_editor_salvar", {"id": m.pk, "nome": "Claro", "tema": "xyz", "slides": [{"origem": "auto", "provedor": "kpi"}]})
        m.refresh_from_db()
        self.assertEqual(m.tema, "escuro")

    def test_salvar_moldura_do_card(self):
        itens = [{"card_id": "kpi.situacao", "visual": {"moldura": "sem"}}, {"card_id": "kpi.graficos", "visual": {"moldura": "qualquer"}}]
        r = self._post("telao_editor_salvar", {"nome": "M", "slides": [{"origem": "manual", "itens": itens}]})
        s = ModeloApresentacao.objects.get(pk=r.json()["id"]).slides[0]["itens"]
        self.assertEqual(s[0]["visual"].get("moldura"), "sem")
        self.assertNotIn("moldura", s[1]["visual"])

    def test_elementos_soltos_titulo_texto_imagem(self):
        png = "data:image/png;base64,iVBORw0KGgo="
        itens = [
            {"card_id": "", "el": {"tipo": "titulo", "texto": "Resultado do mês", "tam": 99, "alinhar": "centro", "cor": "xx"}, "pos": {"x": 0, "y": 0, "w": 12, "h": 1}},
            {"card_id": "", "el": {"tipo": "texto", "texto": "x" * 3000, "negrito": True}, "pos": {"x": 0, "y": 1, "w": 6, "h": 2}, "visual": {"moldura": "com"}},
            {"card_id": "", "el": {"tipo": "imagem", "url": png, "ajuste": "cobre"}, "pos": {"x": 6, "y": 1, "w": 6, "h": 2}},
            {"card_id": "", "el": {"tipo": "imagem", "url": "javascript:alert(1)"}, "pos": {"x": 0, "y": 3, "w": 2, "h": 1}},
            {"card_id": "", "el": {"tipo": "imagem", "url": "http://inseguro/x.png"}, "pos": {"x": 2, "y": 3, "w": 2, "h": 1}},
            {"card_id": "", "el": {"tipo": "imagem", "url": "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4="}, "pos": {"x": 4, "y": 3, "w": 2, "h": 1}},
            {"card_id": "", "el": {"tipo": "qualquer", "texto": "?"}, "pos": {"x": 6, "y": 3, "w": 2, "h": 1}},
        ]
        r = self._post("telao_editor_salvar", {"nome": "E", "slides": [{"origem": "manual", "itens": itens}]})
        salvo = ModeloApresentacao.objects.get(pk=r.json()["id"]).slides[0]["itens"]
        self.assertEqual(len(salvo), 6)  # o tipo desconhecido cai
        titulo, texto, img, ruim_js, ruim_http, ruim_svg = salvo
        self.assertEqual((titulo["el"]["tam"], titulo["el"]["alinhar"], titulo["el"]["cor"], titulo["el"]["negrito"]), (15, "centro", "padrao", True))
        self.assertEqual(len(texto["el"]["texto"]), 2000)
        self.assertEqual(texto["visual"].get("moldura"), "com")
        self.assertEqual((img["el"]["url"], img["el"]["ajuste"]), (png, "cobre"))
        self.assertEqual([x["el"]["url"] for x in (ruim_js, ruim_http, ruim_svg)], ["", "", ""])
        conteudo = layout.montar_manual(self.admin, {"origem": "manual", "titulo": "E", "itens": salvo}, False, [], {})[0]["itens"]
        self.assertEqual([c["conteudo"]["kind"] for c in conteudo], ["elemento"] * 6)
        self.assertEqual(conteudo[0]["conteudo"]["texto"], "Resultado do mês")
        self.assertTrue(conteudo[1]["conteudo"]["moldura"])
        self.assertFalse(conteudo[0]["conteudo"]["moldura"])

    def test_previa_alinha_elementos_e_cards(self):
        slide = {"origem": "manual", "itens": [{"card_id": "", "el": {"tipo": "subtitulo", "texto": "Olá"}, "pos": {"x": 0, "y": 0, "w": 4, "h": 1}},
                                                {"card_id": "kpi.situacao", "pos": {"x": 4, "y": 0, "w": 4, "h": 2}}]}
        r = self._post("telao_editor_previa", {"slide": slide}).json()
        self.assertEqual(r["itens"][0]["texto"], "Olá")
        self.assertIsNotNone(r["itens"][1])

    def test_salvar_assunto_com_blocos_editados(self):
        slide = {"origem": "auto", "tipo": "assunto", "titulo": "A", "blocos": [{"provedor": "kpi", "filtros": {}}, {"provedor": "zzz"}, {"provedor": "pcp", "filtros": {}}]}
        r = self._post("telao_editor_salvar", {"nome": "A", "slides": [slide]})
        s = ModeloApresentacao.objects.get(pk=r.json()["id"]).slides[0]
        self.assertEqual([b["provedor"] for b in s["blocos"]], ["kpi", "pcp"])

    def test_salvar_substitui_o_formato_antigo(self):
        m = ModeloApresentacao.objects.create(nome="L", criado_por=self.admin, itens=[{"provedor": "kpi"}])
        slides = layout.slides_do_modelo(m)
        self.assertEqual(self._post("telao_editor_salvar", {"id": m.pk, "nome": "L", "slides": slides}).status_code, 200)
        m.refresh_from_db()
        self.assertEqual((m.itens, [s["provedor"] for s in m.slides]), ([], ["kpi"]))

    def test_salvar_valida(self):
        r = self._post("telao_editor_salvar", {"nome": "", "slides": []})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(len(r.json()["erros"]), 2)
        self.assertEqual(self.client.post(reverse("telao_editor_salvar"), "não é json", content_type="application/json").status_code, 400)
        self.assertEqual(ModeloApresentacao.objects.count(), 0)

    # ---- apoio
    def test_previa_manual_alinhada_aos_itens(self):
        slide = {"origem": "manual", "itens": [
            {"card_id": "kpi.situacao", "pos": {}}, {"card_id": "nao.existe"}, {"card_id": "kpi.graficos", "params": {"ref": "Perda"}},
            {"card_id": "pcp.paginas"}]}
        itens = self._post("telao_editor_previa", {"slide": slide}).json()["itens"]
        self.assertEqual(len(itens), 4)
        self.assertEqual(itens[0]["kind"], "tiles")
        self.assertIsNone(itens[1])
        self.assertEqual(itens[2]["titulo"], "Perda")
        self.assertIsNone(itens[3], "sem dado")

    def test_previa_automatica(self):
        r = self._post("telao_editor_previa", {"slide": {"origem": "auto", "provedor": "kpi", "filtros": {"cards": ["graficos"], "layout": "2"}}}).json()
        self.assertEqual([s["kind"] for s in r["slides"]], ["layout"])
        self.assertEqual(self._post("telao_editor_previa", {"slide": {"origem": "auto", "provedor": "zzz"}}).json(), {"slides": []})
        self.assertEqual(self._post("telao_editor_previa", {}).json(), {"slides": []})

    def test_instancias(self):
        r = self.client.get(reverse("telao_editor_instancias") + "?card_id=kpi.graficos").json()
        self.assertEqual(sorted(r["instancias"]), ["Perda", "Retrabalho"])
        self.assertEqual(self.client.get(reverse("telao_editor_instancias") + "?card_id=x").json(), {"instancias": []})

    def test_personalizar(self):
        r = self._post("telao_editor_personalizar", {"slide": {"origem": "auto", "provedor": "kpi", "filtros": {"cards": ["situacao", "graficos"]}}})
        self.assertEqual(r.status_code, 200)
        manual = r.json()["slides"][0]
        self.assertEqual(manual["origem"], "manual")
        self.assertEqual([i["card_id"] for i in manual["itens"]], ["kpi.situacao", "kpi.graficos", "kpi.graficos"])
        self.assertEqual(self._post("telao_editor_personalizar", {"slide": {"origem": "auto", "provedor": "pcp"}}).status_code, 409)
        self.assertEqual(self._post("telao_editor_personalizar", {"slide": {"origem": "auto", "provedor": "zzz"}}).status_code, 400)

    # ---- lista
    def test_lista_resume_slides(self):
        ModeloApresentacao.objects.create(nome="S", criado_por=self.admin, slides=[
            {"origem": "auto", "provedor": "kpi"}, {"origem": "manual", "titulo": "Fechamento"}, {"origem": "auto", "tipo": "assunto", "titulo": "A", "blocos": []}])
        r = self.client.get(reverse("telao_modelos"))
        self.assertContains(r, "Indicadores (KPI)")
        self.assertContains(r, "Slide: Fechamento")
        self.assertContains(r, "Assunto: A")
        self.assertContains(r, reverse("telao_editor_novo"))
