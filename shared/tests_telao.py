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

    def test_ocorrencias_agrupadas_por_sessao(self):
        slides = [s for s in providers.slides_ocorrencias(self.admin) if s.get("grupo")]
        self.assertEqual(len(slides), 1)
        self.assertEqual(slides[0]["titulo"], "Laboratório")
        self.assertEqual(slides[0]["itens"][0]["comentarios"], [])
        self.assertIn("1 em aberto", slides[0]["subtitulo"])

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

    def test_treinamentos_com_todos_os_filtros_compila(self):
        filtros = {"setores": ["1"], "turnos": ["A"], "lideres": ["1"], "supervisores": ["1"], "gerentes": ["1"],
                   "criticidade": ["CRITICO"], "matrizes": ["M"], "sub_areas": ["S"], "janela": "15", "apenas_atrasados": True}
        self.assertIsInstance(providers.slides_treinamentos(self.admin, filtros=filtros), list)
        self.assertIsInstance(providers.slides_treinamentos(self.admin, resumo=True, filtros={}), list)

    def test_treinamentos_filtros_do_editor_tem_opcoes(self):
        campos = {c["nome"]: c for c in providers.campos_filtro("treinamentos", self.admin)}
        for nome in ("setores", "turnos", "lideres", "supervisores", "gerentes", "criticidade", "matrizes", "sub_areas"):
            self.assertIn(nome, campos)

    def test_laboratorio_filtra_turno_periodo_e_cards(self):
        from laboratorio.models import HCCadastro, RendimentoHCItem, RendimentoHCRegistro

        motivo = HCCadastro.objects.create(tipo=HCCadastro.TIPO_MOTIVO, nome="Bolha")
        mat = HCCadastro.objects.create(tipo=HCCadastro.TIPO_MATERIAL, nome="Policarbonato")
        for dia, turno, ret in ((1, "T1", 5), (2, "T1", 0), (3, "T2", 20)):
            r = RendimentoHCRegistro.objects.create(data=date(2026, 3, dia), turno_nome=turno, qtd_lentes=100, qtd_retrabalho=ret)
            RendimentoHCItem.objects.create(registro=r, tipo=RendimentoHCItem.RET_MOTIVO, cadastro=motivo, quantidade=ret)
            RendimentoHCItem.objects.create(registro=r, tipo=RendimentoHCItem.PROD_MATERIAL, cadastro=mat, quantidade=100)
            RendimentoHCItem.objects.create(registro=r, tipo=RendimentoHCItem.RET_MATERIAL, cadastro=mat, quantidade=ret)
        todos = providers.slides_laboratorio(self.admin)
        titulos = {s["titulo"] for s in todos}
        self.assertIn("Laboratório — rendimento por turno", titulos)
        self.assertIn("Laboratório — retrabalho por motivo", titulos)
        t1 = providers.slides_laboratorio(self.admin, filtros={"turnos": ["T1"]})
        tiles = {i["rotulo"]: i["valor"] for s in t1 if s["kind"] == "tiles" for i in s["itens"]}
        self.assertEqual(tiles["Lentes produzidas"], "200")
        self.assertEqual(providers.slides_laboratorio(self.admin, filtros={"periodo": "ano"})[0]["kind"], "tiles")

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


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class TelaoAuditoriasInativasTests(TestCase):
    """Auditorias inativadas ou arquivadas não entram no telão (nem os slides, nem as ocorrências)."""

    def setUp(self):
        cache.clear()
        self.admin = get_user_model().objects.create_user("adm4", password="x", is_superuser=True, is_staff=True)

    def _modelo(self, nome, **extra):
        from auditoria.models import ModeloAuditoria, RegistroAuditoria

        m = ModeloAuditoria.objects.create(nome=nome, objeto_auditoria="o", periodicidade="MENSAL", **extra)
        hoje = date.today()
        RegistroAuditoria.objects.create(modelo=m, data_auditoria=hoje, periodo_inicio=hoje, periodo_fim=hoje, status="CONCLUIDO")
        return m

    def test_slides_ignoram_inativas_e_arquivadas(self):
        self._modelo("Ativa")
        self._modelo("Inativa", ativo=False)
        self._modelo("Arquivada", arquivado=True)
        slides = providers.slides_auditoria(self.admin)
        texto = str(slides)
        self.assertIn("Ativa", texto)
        self.assertNotIn("Inativa", texto)
        self.assertNotIn("Arquivada", texto)

    def test_ocorrencias_de_modelo_inativo_ou_arquivado_ficam_de_fora(self):
        from auditoria.models import ComentarioRespostaAuditoria, PerguntaAuditoria

        for nome, extra in (("Ok", {}), ("Inativa", {"ativo": False}), ("Arquivada", {"arquivado": True})):
            m = self._modelo(nome, **extra)
            p = PerguntaAuditoria.objects.create(modelo=m, pergunta=f"Pergunta {nome}")
            ComentarioRespostaAuditoria.objects.create(pergunta=p, texto=f"texto {nome}", requer_tratativa=True, autor=self.admin)
        itens = providers._sem_auditorias_inativas(__import__("shared.ocorrencias", fromlist=["x"]).listar_ocorrencias(self.admin, "abertas"))
        titulos = " ".join(i.titulo for i in itens)
        self.assertIn("Pergunta Ok", titulos)
        self.assertNotIn("Pergunta Inativa", titulos)
        self.assertNotIn("Pergunta Arquivada", titulos)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class TelaoFiltrosTests(TestCase):
    """Cada conteúdo do modelo aceita filtros (como nos dashboards) e a seleção dos cards que vão para a apresentação."""

    def setUp(self):
        cache.clear()
        self.admin = get_user_model().objects.create_user("adm5", password="x", is_superuser=True, is_staff=True)
        from kpi.models import SetorIndicador

        self.ind = Indicador.objects.create(nome="Perda", meta=5, sentido="menor", unidade="%")
        self.outro = Indicador.objects.create(nome="Entrega", meta=95, sentido="maior", unidade="%")
        self.mont = SetorIndicador.objects.create(indicador=self.ind, nome="Montagem", meta=3)
        self.surf = SetorIndicador.objects.create(indicador=self.ind, nome="Surfaçagem", meta=8)
        for n, v in enumerate([4, 6]):
            Medicao.objects.create(indicador=self.ind, periodo=date(2026, n + 1, 28), valor=v, granularidade="mensal")
            Medicao.objects.create(indicador=self.ind, setor=self.mont, periodo=date(2026, n + 1, 28), valor=v - 1, granularidade="mensal")
            Medicao.objects.create(indicador=self.ind, setor=self.surf, periodo=date(2026, n + 1, 28), valor=v + 1, granularidade="mensal")
            Medicao.objects.create(indicador=self.outro, periodo=date(2026, n + 1, 28), valor=96, granularidade="mensal")

    def _tiles(self, slides):
        return {i["rotulo"]: i for s in slides if s["kind"] == "tiles" for i in s["itens"]}

    def test_kpi_por_setor_usa_meta_e_medicao_do_setor(self):
        slides = providers.slides_kpi(self.admin, filtros={"setores": ["Montagem"]})
        t = self._tiles(slides)
        self.assertIn("Perda · Montagem", t)
        self.assertNotIn("Perda · Surfaçagem", t)
        self.assertNotIn("Entrega", t)  # indicador sem setor Montagem fica de fora
        self.assertEqual(t["Perda · Montagem"]["tom"], "critico")  # 5 > meta 3 do setor
        self.assertIn("Montagem", slides[0]["titulo"])

    def test_kpi_filtro_de_indicador_e_fora_da_meta(self):
        t = self._tiles(providers.slides_kpi(self.admin, filtros={"indicadores": [str(self.outro.pk)]}))
        self.assertEqual(set(k for k in t if k not in ("Na meta", "Fora da meta", "Sem dado")), {"Entrega"})
        t = self._tiles(providers.slides_kpi(self.admin, filtros={"apenas_fora": True}))
        self.assertNotIn("Entrega", t)

    def test_selecao_de_cards(self):
        from shared.models import ModeloApresentacao

        m = ModeloApresentacao.objects.create(nome="So graficos", criado_por=self.admin, itens=[
            {"provedor": "kpi", "duracao": None, "filtros": {"cards": ["graficos"], "graficos": "todos"}}])
        slides = providers.montar_playlist(self.admin, m.chave)
        self.assertTrue(slides)
        self.assertTrue(all(s["kind"] == "chart" and s["card"] == "graficos" for s in slides))

    def test_alteracao_do_modelo_vale_na_proxima_chamada(self):
        from shared.models import ModeloApresentacao

        m = ModeloApresentacao.objects.create(nome="Dinamico", criado_por=self.admin, itens=[
            {"provedor": "kpi", "duracao": None, "filtros": {"setores": ["Montagem"]}}])
        self.assertIn("Montagem", providers.montar_playlist(self.admin, m.chave)[0]["titulo"])
        m.itens = [{"provedor": "kpi", "duracao": None, "filtros": {"setores": ["Surfaçagem"]}}]
        m.save()
        self.assertIn("Surfaçagem", providers.montar_playlist(self.admin, m.chave)[0]["titulo"])

    def test_formulario_salva_filtros_validos(self):
        from shared.models import ModeloApresentacao

        self.client.force_login(self.admin)
        self.client.post(reverse("telao_modelo_novo"), {
            "nome": "Montagem TV", "prov": ["kpi"], "duracao_padrao": "10", "ativo": "on",
            "f_kpi_setores": ["Montagem", "Inexistente"], "f_kpi_apenas_fora": "on", "f_kpi_graficos": "todos",
            "f_kpi_cards": ["situacao", "invalido"]})
        item = ModeloApresentacao.objects.get(nome="Montagem TV").itens[0]
        self.assertEqual(item["filtros"], {"cards": ["situacao"], "setores": ["Montagem"], "apenas_fora": True, "graficos": "todos"})
        r = self.client.get(reverse("telao_modelo_editar", args=[ModeloApresentacao.objects.get().pk]))
        self.assertContains(r, 'value="Montagem" id="f_kpi_setores_1" checked')

    def test_auditoria_filtra_relatorio(self):
        from auditoria.models import ModeloAuditoria, RegistroAuditoria

        hoje = date.today()
        ids = {}
        for nome in ("Relatorio A", "Relatorio B"):
            m = ModeloAuditoria.objects.create(nome=nome, objeto_auditoria="o", periodicidade="MENSAL")
            RegistroAuditoria.objects.create(modelo=m, data_auditoria=hoje, periodo_inicio=hoje, periodo_fim=hoje, status="CONCLUIDO")
            ids[nome] = str(m.pk)
        texto = str(providers.slides_auditoria(self.admin, filtros={"modelos": [ids["Relatorio B"]]}))
        self.assertIn("Relatorio B", texto)
        self.assertNotIn("Relatorio A", texto)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class TelaoOcorrenciasAbordagemTests(TestCase):
    def setUp(self):
        cache.clear()
        U = get_user_model()
        self.admin = U.objects.create_user("adm6", password="x", is_superuser=True, is_staff=True)
        ana = U.objects.create_user("ana", password="x", first_name="Ana", last_name="Souza")
        bia = U.objects.create_user("bia", password="x", first_name="Bia", last_name="Lima")
        for assunto, resp in (("A1", ana), ("A2", ana), ("B1", bia), ("S1", None)):
            OcorrenciaLaboratorio.objects.create(assunto=assunto, detalhamento="d", criado_por=self.admin, responsavel=resp)

    def _barras(self, slides):
        return {i["rotulo"]: i for s in slides if s["kind"] == "bars" and "responsável" in s["titulo"] for i in s["itens"]}

    def test_global_lista_responsaveis_e_conta_por_pessoa(self):
        slides = providers.slides_ocorrencias(self.admin)
        barras = self._barras(slides)
        self.assertEqual(barras["Ana Souza"]["txt"], "2")
        self.assertEqual(barras["Bia Lima"]["txt"], "1")
        self.assertEqual(barras["Sem responsável"]["txt"], "1")
        rotulos = {i["rotulo"] for s in slides if s["kind"] == "tiles" for i in s["itens"]}
        self.assertNotIn("Envolvem você", rotulos)
        self.assertIn("Sem responsável", rotulos)

    def test_pessoal_destaca_o_usuario_e_sem_grafico_por_pessoa(self):
        slides = providers.slides_ocorrencias(self.admin, filtros={"abordagem": "pessoal"})
        rotulos = {i["rotulo"] for s in slides if s["kind"] == "tiles" for i in s["itens"]}
        self.assertIn("Envolvem você", rotulos)
        self.assertEqual(self._barras(slides), {})

    def test_resumo_nao_expoe_nomes(self):
        self.assertEqual(self._barras(providers.slides_ocorrencias(self.admin, resumo=True)), {})

    def test_card_do_grafico_pode_ser_escolhido_sozinho(self):
        from shared.models import ModeloApresentacao

        m = ModeloApresentacao.objects.create(nome="Por pessoa", criado_por=self.admin, itens=[
            {"provedor": "ocorrencias", "duracao": None, "filtros": {"cards": ["por_responsavel"]}}])
        slides = providers.montar_playlist(self.admin, m.chave)
        self.assertEqual([s["card"] for s in slides], ["por_responsavel"])
