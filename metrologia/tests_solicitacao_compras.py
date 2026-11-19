from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from fornecedores.models import Fornecedor
from metrologia.models import (
    CotacaoFornecedor, Instrumento, ItemSolicitacaoCotacao, SolicitacaoCotacao,
)
from metrologia.views.novo_fluxo_cotacao import acompanhamento_instrumentos


class EtapaComprasTests(TestCase):
    """Solicitação das cotações ao setor de compras: antes das cotações, encerra com elas."""

    def setUp(self):
        self.user = User.objects.create_user("u", password="p")
        self.client.force_login(self.user)
        self.inst = Instrumento.objects.create(tag="TH-01", descricao="Termohigrômetro")
        self.sol = SolicitacaoCotacao.objects.create()
        ItemSolicitacaoCotacao.objects.create(solicitacao=self.sol, instrumento=self.inst)
        self.sol.atualizar_status_automatico()      # como faz a tela ao incluir os instrumentos
        self.forn = Fornecedor.objects.create(empresa="Lab X", nome_fantasia="X", endereco="r", uf="SP")

    def _compras(self, acao, **dados):
        return self.client.post(reverse("metrologia:solicitacao_compras", args=[self.sol.id]),
                                {"acao": acao, **dados})

    def _cotacao(self, status="RASCUNHO"):
        return CotacaoFornecedor.objects.create(
            solicitacao=self.sol, fornecedor=self.forn, numero="COT-C-1", status=status)

    def test_estado_inicial_e_pagina(self):
        self.assertEqual(self.sol.status, "INSTRUMENTOS_SELECIONADOS")
        self.assertFalse(self.sol.compras_ativa)
        html = self.client.get(reverse("metrologia:solicitacao_detail", args=[self.sol.id])).content.decode()
        self.assertIn("Solicitar ao setor de compras", html)
        self.assertIn("2. Solicitação ao setor de compras", html)

    def test_solicitar_coloca_demanda_com_o_setor_de_compras(self):
        ontem = timezone.localdate() - timedelta(days=3)
        self._compras("solicitar", data_solicitada=ontem.isoformat(), responsavel="Maria", observacoes="urgente")
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.status, "COM_COMPRAS")
        self.assertEqual(self.sol.get_status_display(), "Com o Setor de Compras")
        self.assertTrue(self.sol.compras_ativa)
        self.assertEqual((self.sol.compras_responsavel, self.sol.compras_dias, self.sol.compras_solicitada_por),
                         ("Maria", 3, self.user))
        html = self.client.get(reverse("metrologia:solicitacao_detail", args=[self.sol.id])).content.decode()
        self.assertIn("Com o setor de compras", html)
        self.assertIn("Encerrar etapa", html)
        # instrumento aparece no acompanhamento (filtro) como "Com o setor de compras"
        info = acompanhamento_instrumentos()[self.inst.id]
        self.assertEqual(info["codigo"], "COM_COMPRAS")
        self.assertIn(self.sol.numero, info["label"])
        for url in (reverse("modulo_metrologia"), "/dashboard/"):
            r = self.client.get(url).content.decode()
            self.assertIn('value="COM_COMPRAS"', r)
            self.assertIn('data-acompanhamento="COM_COMPRAS"', r)

    def test_etapa_comeca_antes_das_cotacoes_e_continua_com_cotacao_em_rascunho(self):
        self._compras("solicitar")
        self._cotacao("RASCUNHO")
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.status, "COM_COMPRAS")

    def test_encerra_junto_com_a_primeira_proposta(self):
        self._compras("solicitar", data_solicitada=(timezone.localdate() - timedelta(days=2)).isoformat())
        cot = self._cotacao("ENVIADA")
        self.sol.refresh_from_db()
        self.assertTrue(self.sol.compras_ativa)
        cot.status = "RESPONDIDA"
        cot.save()
        self.sol.refresh_from_db()
        self.assertFalse(self.sol.compras_ativa)
        self.assertEqual(self.sol.compras_concluida_em, timezone.localdate())
        self.assertEqual(self.sol.status, "COTACAO_SOLICITADA")
        self.assertEqual(acompanhamento_instrumentos()[self.inst.id]["codigo"], "EM_COTACAO")

    def test_encerrar_manual_reabrir_e_desfazer(self):
        self._compras("solicitar")
        self._compras("encerrar")
        self.sol.refresh_from_db()
        self.assertFalse(self.sol.compras_ativa)
        self.assertEqual(self.sol.status, "INSTRUMENTOS_SELECIONADOS")
        self._compras("reabrir")
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.status, "COM_COMPRAS")
        self._compras("desfazer")
        self.sol.refresh_from_db()
        self.assertIsNone(self.sol.compras_solicitada_em)
        self.assertEqual(self.sol.status, "INSTRUMENTOS_SELECIONADOS")

    def test_validacoes(self):
        self._compras("encerrar")                                   # sem solicitar antes
        self._compras("solicitar", data_solicitada=(timezone.localdate() + timedelta(days=2)).isoformat())
        self._compras("solicitar", data_solicitada="31/12/2026")    # formato inválido
        self._compras("xyz")
        self.sol.refresh_from_db()
        self.assertIsNone(self.sol.compras_solicitada_em)
        self._compras("solicitar", data_solicitada=date(2026, 11, 1).isoformat())
        self._compras("encerrar", data_encerrada="2026-10-01")      # antes da solicitação
        self.sol.refresh_from_db()
        self.assertTrue(self.sol.compras_ativa)

    def test_cotacao_encerrada_nao_altera_a_etapa(self):
        self.sol.marcar_concluida()
        self._compras("solicitar")
        self.sol.refresh_from_db()
        self.assertIsNone(self.sol.compras_solicitada_em)


class LinksComprasTests(EtapaComprasTests):
    """Links das tratativas (um ou mais) na etapa de compras."""

    def _link(self, acao="adicionar", **dados):
        return self.client.post(reverse("metrologia:solicitacao_compras_link", args=[self.sol.id]),
                                {"acao": acao, **dados})

    def _links(self):
        from metrologia.models import LinkSolicitacaoCompras
        return list(LinkSolicitacaoCompras.objects.filter(solicitacao=self.sol).order_by("id"))

    # herda os testes da etapa só para reutilizar as fixtures; evita reexecutá-los
    for _nome in [n for n in dir(EtapaComprasTests) if n.startswith("test_")]:
        locals()[_nome] = None
    del _nome

    def test_adiciona_um_ou_varios_links_e_remove(self):
        self._compras("solicitar")
        self._link(urls="https://portal.exemplo.com/pedido/123", descricao="Pedido no portal")
        self._link(urls="https://drive.google.com/x\nwww.teams.microsoft.com/chat/abc\n")
        links = self._links()
        self.assertEqual([l.rotulo for l in links],
                         ["Pedido no portal", "drive.google.com", "www.teams.microsoft.com"])
        self.assertEqual(links[2].url, "https://www.teams.microsoft.com/chat/abc")   # assume https
        self.assertEqual(links[0].criado_por, self.user)
        html = self.client.get(reverse("metrologia:solicitacao_detail", args=[self.sol.id])).content.decode()
        self.assertIn('href="https://portal.exemplo.com/pedido/123"', html)
        self.assertIn('rel="noopener noreferrer"', html)
        self.assertIn("Pedido no portal", html)
        self._link("remover", link_id=links[0].id)
        self.assertEqual(len(self._links()), 2)

    def test_recusa_links_invalidos_e_duplicados(self):
        self._compras("solicitar")
        self._link(urls="javascript:alert(1)")
        self._link(urls="não é link")
        self._link(urls="ftp://servidor/arquivo")
        self.assertEqual(self._links(), [])
        self._link(urls="https://ok.com/a\nhttps://ok.com/a\njavascript:x")
        self.assertEqual(len(self._links()), 1)                      # duplicado ignorado, inválido recusado
        self._link(urls="")
        self.assertEqual(len(self._links()), 1)

    def test_remover_link_de_outra_solicitacao_nao_funciona(self):
        from metrologia.models import LinkSolicitacaoCompras
        outra = SolicitacaoCotacao.objects.create()
        alheio = LinkSolicitacaoCompras.objects.create(solicitacao=outra, url="https://outra.com")
        self._link("remover", link_id=alheio.id)
        self.assertTrue(LinkSolicitacaoCompras.objects.filter(pk=alheio.pk).exists())


class NumeroCotacaoFornecedorTests(EtapaComprasTests):
    """O número (único) da cotação do fornecedor é gerado: antes a 2ª cotação dava erro 500."""

    for _nome in [n for n in dir(EtapaComprasTests) if n.startswith("test_")]:
        locals()[_nome] = None
    del _nome

    def _criar(self, sol, forn):
        return self.client.post(reverse("metrologia:cotacao_fornecedor_create", args=[sol.id]),
                                {"fornecedor": forn.id})

    def test_varias_cotacoes_recebem_numeros_unicos(self):
        outra = SolicitacaoCotacao.objects.create()
        ItemSolicitacaoCotacao.objects.create(
            solicitacao=outra, instrumento=Instrumento.objects.create(tag="TH-02", descricao="x"))
        forn2 = Fornecedor.objects.create(empresa="Lab Y", nome_fantasia="Y", endereco="r", uf="SP")
        for sol, forn in ((self.sol, self.forn), (self.sol, forn2), (outra, self.forn)):
            r = self._criar(sol, forn)
            self.assertEqual(r.status_code, 302)
        numeros = list(CotacaoFornecedor.objects.order_by("id").values_list("numero", flat=True))
        self.assertEqual(len(set(numeros)), 3)
        ano = timezone.now().year
        self.assertEqual(numeros[0], f"COT-{ano}-0001-FOR{self.forn.id % 1000:03d}")
        self.assertEqual(numeros[1][:14], f"COT-{ano}-0002-")
        self.assertTrue(all(len(n) <= 20 for n in numeros))
        # a tela mostra o número (antes o título ficava só com "$")
        cot = CotacaoFornecedor.objects.first()
        self.assertContains(self.client.get(reverse("metrologia:cotacao_fornecedor_detail", args=[cot.id])), cot.numero)

    def test_numero_informado_e_mantido(self):
        cot = CotacaoFornecedor.objects.create(
            solicitacao=self.sol, fornecedor=self.forn, numero="COT-MANUAL")
        self.assertEqual(cot.numero, "COT-MANUAL")


class CustosAdicionaisCotacaoTests(EtapaComprasTests):
    """Custos adicionais da cotação do fornecedor: deslocamentos, passagens aéreas etc."""

    for _nome in [n for n in dir(EtapaComprasTests) if n.startswith("test_")]:
        locals()[_nome] = None
    del _nome

    def _cotacao_com_item(self):
        from metrologia.models import ItemCotacao
        cot = CotacaoFornecedor.objects.create(solicitacao=self.sol, fornecedor=self.forn)
        item_sol = self.sol.itens.first()
        ItemCotacao.objects.create(cotacao_fornecedor=cot, item_solicitacao=item_sol, instrumento=self.inst,
                                   valor_unitario=Decimal("1000.00"), pode_atender=True)
        return cot

    def _salvar(self, cot, **extra):
        dados = {"fornecedor": self.forn.id, "custos_enviados": "1"}
        dados.update(extra)
        return self.client.post(reverse("metrologia:cotacao_fornecedor_update", args=[cot.id]), dados)

    def test_adiciona_custos_e_soma_no_total(self):
        cot = self._cotacao_com_item()
        r = self._salvar(cot,
                         custo_tipo=["DESLOCAMENTO", "PASSAGEM_AEREA", "OUTRO"],
                         custo_descricao=["Táxi", "Salvador → SP", ""],
                         custo_quantidade=["1", "2", "1"],
                         custo_valor=["150,50", "800", ""])          # 3ª linha em branco é ignorada
        self.assertEqual(r.status_code, 302)
        custos = list(cot.custos_adicionais.all())
        self.assertEqual([(c.tipo, c.quantidade, c.valor_unitario, c.valor_total) for c in custos],
                         [("DESLOCAMENTO", 1, Decimal("150.50"), Decimal("150.50")),
                          ("PASSAGEM_AEREA", 2, Decimal("800.00"), Decimal("1600.00"))])
        self.assertEqual(cot.get_valor_servicos(), Decimal("1000.00"))
        self.assertEqual(cot.get_valor_custos_adicionais(), Decimal("1750.50"))
        self.assertEqual(cot.get_valor_total(), Decimal("2750.50"))
        self.assertEqual(cot.get_valor_a_pagar(), Decimal("2750.50"))
        html = self.client.get(reverse("metrologia:cotacao_fornecedor_detail", args=[cot.id])).content.decode()
        self.assertIn("Custos adicionais", html)
        self.assertIn("2750.50".replace(".", ","), html.replace(".", ","))
        self.assertIn("Passagem aérea", html)
        # a lista de cotações da solicitação mostra o total com os custos
        self.assertContains(self.client.get(reverse("metrologia:solicitacao_detail", args=[self.sol.id])), "2750")

    def test_editar_substitui_e_remove_custos(self):
        cot = self._cotacao_com_item()
        self._salvar(cot, custo_tipo=["FRETE"], custo_descricao=["Ida e volta"], custo_quantidade=["1"], custo_valor=["200"])
        self.assertEqual(cot.custos_adicionais.count(), 1)
        self._salvar(cot, custo_tipo=["TAXA"], custo_descricao=["Imposto"], custo_quantidade=["1"], custo_valor=["30"])
        self.assertEqual([c.tipo for c in cot.custos_adicionais.all()], ["TAXA"])
        self._salvar(cot)                                            # nenhuma linha: remove tudo
        self.assertEqual(cot.custos_adicionais.count(), 0)

    def test_sem_marcador_nao_apaga_custos(self):
        cot = self._cotacao_com_item()
        self._salvar(cot, custo_tipo=["FRETE"], custo_descricao=[""], custo_quantidade=["1"], custo_valor=["50"])
        self.client.post(reverse("metrologia:cotacao_fornecedor_update", args=[cot.id]), {"fornecedor": self.forn.id})
        self.assertEqual(cot.custos_adicionais.count(), 1)

    def test_valores_invalidos_sao_ignorados(self):
        cot = self._cotacao_com_item()
        self._salvar(cot, custo_tipo=["FRETE", "FRETE", "FRETE", "XYZ"], custo_descricao=["a", "b", "c", "d"],
                     custo_quantidade=["1", "0", "x", "1"], custo_valor=["abc", "10", "10", "5"])
        custos = list(cot.custos_adicionais.all())
        self.assertEqual([(c.tipo, c.valor_total) for c in custos], [("OUTRO", Decimal("5.00"))])

    def test_tela_de_edicao_tem_a_secao(self):
        cot = self._cotacao_com_item()
        html = self.client.get(reverse("metrologia:cotacao_fornecedor_update", args=[cot.id])).content.decode()
        self.assertIn("Custos adicionais", html)
        self.assertIn("adicionarCusto()", html)
        self.assertIn('name="custos_enviados"', html)

    def test_valor_a_pagar_inclui_custos_apos_execucao(self):
        cot = self._cotacao_com_item()
        self._salvar(cot, custo_tipo=["DESLOCAMENTO"], custo_descricao=[""], custo_quantidade=["1"], custo_valor=["100"])
        item = cot.itens.get()
        item.status_execucao = "NAO_ATENDIDO"
        item.save()
        self.assertEqual(cot.get_valor_a_pagar(), Decimal("100.00"))   # só o custo adicional
