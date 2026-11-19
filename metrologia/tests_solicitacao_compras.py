from datetime import date, timedelta

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
