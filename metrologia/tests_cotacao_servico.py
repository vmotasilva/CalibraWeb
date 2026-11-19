from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from fornecedores.models import Fornecedor
from metrologia.models import (
    CotacaoFornecedor, Instrumento, ItemCotacao, ItemSolicitacaoCotacao, SolicitacaoCotacao,
)
from qms.models import OcorrenciaInstrumento


class BaseCotacaoServico(TestCase):

    def setUp(self):
        self.user = User.objects.create_user("u", password="p")
        self.client.force_login(self.user)
        self.a = Instrumento.objects.create(tag="A-01", descricao="A")
        self.b = Instrumento.objects.create(tag="B-01", descricao="B")
        self.sol = SolicitacaoCotacao.objects.create()
        forn = Fornecedor.objects.create(empresa="Lab X", nome_fantasia="X", endereco="r", uf="SP")
        self.cot = CotacaoFornecedor.objects.create(
            solicitacao=self.sol, fornecedor=forn, numero="COT-1", aprovada=True, status="ACEITA")
        self.itens = []
        for inst, valor in ((self.a, "100.00"), (self.b, "50.00")):
            isol = ItemSolicitacaoCotacao.objects.create(solicitacao=self.sol, instrumento=inst)
            self.itens.append(ItemCotacao.objects.create(
                cotacao_fornecedor=self.cot, item_solicitacao=isol, instrumento=inst,
                valor_unitario=Decimal(valor), pode_atender=True))

    def _post(self, name, data):
        return self.client.post(reverse(f"metrologia:{name}", args=[self.cot.id]), data)

    def _iniciar(self):
        self._post("cotacao_servico_agendar", {"data_visita": "2026-12-01T09:30", "acao": "iniciar"})
        self.cot.refresh_from_db()



class CotacaoServicoTests(BaseCotacaoServico):
    """Planejamento -> Execução -> Conclusão do serviço de uma cotação aceita."""

    def test_detalhe_renderiza_em_cada_etapa(self):
        url = reverse("metrologia:cotacao_fornecedor_detail", args=[self.cot.id])
        self.assertContains(self.client.get(url), "Data e hora da visita")
        self._iniciar()
        self.assertContains(self.client.get(url), "Salvar execução")

    def test_agendar_e_iniciar(self):
        self._post("cotacao_servico_agendar", {"data_visita": "2026-12-01T09:30", "acao": "agendar"})
        self.cot.refresh_from_db()
        self.assertIsNotNone(self.cot.data_visita)
        self.assertEqual(self.cot.etapa_servico, "AGENDAMENTO")
        self._post("cotacao_servico_agendar", {"acao": "iniciar"})
        self.cot.refresh_from_db()
        self.assertEqual(self.cot.etapa_servico, "EXECUCAO")

    def test_nao_inicia_sem_visita(self):
        self._post("cotacao_servico_agendar", {"acao": "iniciar"})
        self.cot.refresh_from_db()
        self.assertEqual(self.cot.etapa_servico, "AGENDAMENTO")

    def test_cotacao_nao_aprovada_nao_agenda(self):
        self.cot.aprovada = False
        self.cot.save()
        self._post("cotacao_servico_agendar", {"data_visita": "2026-12-01T09:30"})
        self.cot.refresh_from_db()
        self.assertIsNone(self.cot.data_visita)

    def test_execucao_atualiza_valor_a_pagar_e_abre_ocorrencia(self):
        self._iniciar()
        ia, ib = self.itens
        self.assertEqual(self.cot.get_valor_a_pagar(), Decimal("150.00"))
        self._post("cotacao_servico_executar", {
            f"status_{ia.id}": "ATENDIDO", f"valor_{ia.id}": "90,00",
            f"status_{ib.id}": "NAO_ATENDIDO",
            f"ocorrencia_{ib.id}": "on", f"ocorrencia_tipo_{ib.id}": "AVARIA",
            f"ocorrencia_desc_{ib.id}": "Veio danificado",
        })
        ia.refresh_from_db(); ib.refresh_from_db()
        self.assertEqual(ia.valor_cobrado, Decimal("90.00"))
        self.assertEqual(ib.valor_cobrado, Decimal("0.00"))
        self.assertEqual(self.cot.get_valor_a_pagar(), Decimal("90.00"))
        oc = OcorrenciaInstrumento.objects.get()
        self.assertEqual((oc.instrumento_id, oc.tipo, oc.status), (self.b.id, "AVARIA", "ABERTA"))
        self.assertEqual(ib.ocorrencia_id, oc.id)
        # salvar de novo não duplica a ocorrência
        self._post("cotacao_servico_executar", {
            f"status_{ia.id}": "ATENDIDO", f"status_{ib.id}": "NAO_ATENDIDO",
            f"ocorrencia_{ib.id}": "on", f"ocorrencia_desc_{ib.id}": "outra"})
        self.assertEqual(OcorrenciaInstrumento.objects.count(), 1)

    def test_ocorrencia_sem_descricao_nao_e_criada(self):
        self._iniciar()
        ia = self.itens[0]
        self._post("cotacao_servico_executar", {f"status_{ia.id}": "ATENDIDO", f"ocorrencia_{ia.id}": "on"})
        self.assertEqual(OcorrenciaInstrumento.objects.count(), 0)

    def test_conclusao_exige_todos_confirmados(self):
        self._iniciar()
        self._post("cotacao_servico_concluir", {})
        self.cot.refresh_from_db()
        self.assertEqual(self.cot.etapa_servico, "EXECUCAO")

    def test_conclusao_gera_relatorio_e_pode_reabrir(self):
        self._iniciar()
        ia, ib = self.itens
        self._post("cotacao_servico_executar", {
            f"status_{ia.id}": "ATENDIDO", f"valor_{ia.id}": "90",
            f"status_{ib.id}": "NAO_ATENDIDO", f"obs_{ib.id}": "Sem condições"})
        self._post("cotacao_servico_concluir", {"observacoes_conclusao": "ok"})
        self.cot.refresh_from_db()
        self.assertEqual(self.cot.etapa_servico, "CONCLUIDO")
        self.assertEqual(self.cot.concluido_por, self.user)
        rel = self.cot.relatorio_conclusao
        for trecho in ("COT-1", "01/12/2026 09:30", "A-01: R$ 90,00 (cotado R$ 100,00)",
                       "B-01: Sem condições", "R$ 90,00"):
            self.assertIn(trecho, rel)
        self.assertContains(
            self.client.get(reverse("metrologia:cotacao_fornecedor_detail", args=[self.cot.id])),
            "Relatório de conclusão")

    def test_reabrir_sem_historico_gerado(self):
        self._iniciar()
        ia, ib = self.itens
        self._post("cotacao_servico_executar", {
            f"status_{ia.id}": "NAO_ATENDIDO", f"status_{ib.id}": "NAO_ATENDIDO"})
        self._post("cotacao_servico_concluir", {})
        self.cot.refresh_from_db()
        self.assertEqual(self.cot.etapa_servico, "CONCLUIDO")
        self._post("cotacao_servico_concluir", {"acao": "reabrir"})
        self.cot.refresh_from_db()
        self.assertEqual(self.cot.etapa_servico, "EXECUCAO")


class HistoricoEAcompanhamentoTests(BaseCotacaoServico):
    """Geração de histórico na conclusão e status de acompanhamento nos filtros."""

    def _executar_e_concluir(self, atendido_b=False):
        self._iniciar()
        ia, ib = self.itens
        self._post("cotacao_servico_executar", {
            f"status_{ia.id}": "ATENDIDO",
            f"status_{ib.id}": "ATENDIDO" if atendido_b else "NAO_ATENDIDO"})
        self._post("cotacao_servico_concluir", {})

    def test_conclusao_gera_historico_aguardando_certificado(self):
        from metrologia.models import HistoricoCalibracao
        self._executar_e_concluir()
        h = HistoricoCalibracao.objects.get()
        self.assertEqual((h.instrumento_id, h.item_cotacao_id), (self.a.id, self.itens[0].id))
        self.assertTrue(h.aguardando_certificado)
        self.assertEqual(h.numero_certificado, "S/N")
        self.assertEqual(h.fornecedor, "Lab X")
        self.assertIn("PENDENTE", h.observacoes)
        self.assertIn("PENDENTE: dados do certificado", self.cot.__class__.objects.get().relatorio_conclusao)
        r = self.client.get(reverse("metrologia:cotacao_fornecedor_detail", args=[self.cot.id]))
        self.assertContains(r, "Dados do certificado de calibração pendentes")
        # reabrir fica bloqueado depois de gerar histórico
        self._post("cotacao_servico_concluir", {"acao": "reabrir"})
        self.cot.refresh_from_db()
        self.assertEqual(self.cot.etapa_servico, "CONCLUIDO")

    def test_flag_limpa_ao_preencher_certificado(self):
        from metrologia.models import HistoricoCalibracao
        self._executar_e_concluir()
        h = HistoricoCalibracao.objects.get()
        h.numero_certificado = "CERT-1"
        h.save()
        h.refresh_from_db()
        self.assertTrue(h.aguardando_certificado)  # falta arquivo/link
        h.link_certificado = "https://exemplo.com/c.pdf"
        h.save()
        h.refresh_from_db()
        self.assertFalse(h.aguardando_certificado)

    def test_acompanhamento_por_status(self):
        from metrologia.views.novo_fluxo_cotacao import acompanhamento_instrumentos
        # orçamento ainda não aprovado: em cotação
        CotacaoFornecedor.objects.filter(pk=self.cot.pk).update(aprovada=False, status="RESPONDIDA")
        self.assertEqual(acompanhamento_instrumentos()[self.a.id]["codigo"], "EM_COTACAO")
        # aprovado: já fica programado, mesmo sem visita agendada
        CotacaoFornecedor.objects.filter(pk=self.cot.pk).update(aprovada=True, status="ACEITA")
        self.assertEqual(acompanhamento_instrumentos()[self.a.id]["codigo"], "CALIBRACAO_PROGRAMADA")
        self._post("cotacao_servico_agendar", {"data_visita": "2026-12-01T09:30", "acao": "agendar"})
        self.assertIn("01/12/2026", acompanhamento_instrumentos()[self.a.id]["label"])
        self._executar_e_concluir(atendido_b=True)
        mapa = acompanhamento_instrumentos()
        self.assertEqual(mapa[self.a.id]["codigo"], "AGUARDANDO_CERTIFICADO")
        self.assertEqual(mapa[self.b.id]["codigo"], "AGUARDANDO_CERTIFICADO")

    def test_telas_exibem_filtro_e_atributo(self):
        self._post("cotacao_servico_agendar", {"data_visita": "2026-12-01T09:30", "acao": "agendar"})
        r = self.client.get(reverse("modulo_metrologia"))
        self.assertContains(r, 'value="AGUARDANDO_CERTIFICADO" data-category="acompanhamento"')
        self.assertContains(r, 'data-acompanhamento="CALIBRACAO_PROGRAMADA"')
        r = self.client.get("/dashboard/")
        self.assertContains(r, 'data-acompanhamento="CALIBRACAO_PROGRAMADA"')
        self.assertContains(r, "Calibração programada")


class PlanejamentoGeraRegistroTests(BaseCotacaoServico):
    """Atendimentos salvos como realizados já viram registro 'aguardando certificado'."""

    def setUp(self):
        super().setUp()
        from datetime import date
        from metrologia.models import AtendimentoSolicitacao
        self.atends = []
        for item in self.itens:
            item.local_atendimento = "NO_LOCAL"
            item.save()
            self.atends.append(AtendimentoSolicitacao.objects.create(
                solicitacao=self.sol, item_solicitacao=item.item_solicitacao, item_cotacao=item,
                data_prevista_atendimento=date(2026, 11, 17)))

    def _salvar(self, atends, grupo, tipo="NO_LOCAL"):
        import json
        return self.client.post(
            reverse("metrologia:atendimento_atualizar_dados"),
            data=json.dumps({"tipo": tipo, "cotacao_id": self.cot.id,
                             "atendimentos": [a.id for a in atends], "grupo": grupo}),
            content_type="application/json")

    def test_aprovado_sem_planejamento_ja_e_programado(self):
        from metrologia.views.novo_fluxo_cotacao import acompanhamento_instrumentos
        mapa = acompanhamento_instrumentos()
        self.assertEqual({mapa[self.a.id]["codigo"], mapa[self.b.id]["codigo"]}, {"CALIBRACAO_PROGRAMADA"})

    def test_salvar_realizado_cria_registro_aguardando_certificado(self):
        from metrologia.models import HistoricoCalibracao
        from metrologia.views.novo_fluxo_cotacao import acompanhamento_instrumentos
        r = self._salvar(self.atends, {"data_realizada": "2026-11-17", "tecnico": "Vitor",
                                       "tecnico_telefone": "(71) 9 8142-1115"})
        self.assertEqual(r.json()["historicos_criados"], 2)
        hs = HistoricoCalibracao.objects.all()
        self.assertEqual(hs.count(), 2)
        for h in hs:
            self.assertTrue(h.aguardando_certificado)
            self.assertEqual(str(h.data_calibracao), "2026-11-17")
            self.assertIsNotNone(h.atendimento_id)
            self.assertIsNotNone(h.item_cotacao_id)
        self.assertEqual({v["codigo"] for v in acompanhamento_instrumentos().values()}, {"AGUARDANDO_CERTIFICADO"})
        # salvar de novo não duplica
        self._salvar(self.atends, {"data_realizada": "2026-11-17"})
        self.assertEqual(HistoricoCalibracao.objects.count(), 2)
        # a tela mostra o status com link para preencher o certificado
        r = self.client.get(reverse("metrologia:solicitacao_detail", args=[self.sol.id]))
        self.assertContains(r, "Calibrado: aguardando certificado")

    def test_sem_data_realizada_nao_cria(self):
        from metrologia.models import HistoricoCalibracao
        self._salvar(self.atends, {"tecnico": "Vitor"})
        self.assertEqual(HistoricoCalibracao.objects.count(), 0)

    def test_desconsiderado_nao_gera_nem_fica_programado(self):
        from metrologia.models import HistoricoCalibracao
        from metrologia.views.novo_fluxo_cotacao import acompanhamento_instrumentos
        a0 = self.atends[0]
        a0.desconsiderado = True
        a0.save()
        self._salvar(self.atends, {"data_realizada": "2026-11-17"})
        self.assertEqual(HistoricoCalibracao.objects.count(), 1)
        self.assertNotIn(self.a.id, {i for i, v in acompanhamento_instrumentos().items()
                                     if v["codigo"] == "CALIBRACAO_PROGRAMADA"})

    def test_laboratorio_gera_no_retorno(self):
        from metrologia.models import HistoricoCalibracao
        for it in self.itens:
            it.local_atendimento = "NO_LABORATORIO"
            it.save()
        self._salvar(self.atends, {"data_envio": "2026-11-10"}, tipo="NO_LABORATORIO")
        self.assertEqual(HistoricoCalibracao.objects.count(), 0)
        self._salvar(self.atends, {"data_retorno": "2026-11-18"}, tipo="NO_LABORATORIO")
        self.assertEqual(HistoricoCalibracao.objects.count(), 2)

    def test_conclusao_do_servico_nao_duplica_registro_do_planejamento(self):
        from metrologia.models import HistoricoCalibracao
        self._salvar(self.atends, {"data_realizada": "2026-11-17"})
        self._post("cotacao_servico_agendar", {"data_visita": "2026-12-01T09:30", "acao": "iniciar"})
        ia, ib = self.itens
        self._post("cotacao_servico_executar", {f"status_{ia.id}": "ATENDIDO", f"status_{ib.id}": "ATENDIDO"})
        self._post("cotacao_servico_concluir", {})
        self.assertEqual(HistoricoCalibracao.objects.count(), 2)
