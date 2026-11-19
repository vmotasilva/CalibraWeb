import json
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from fornecedores.models import Fornecedor
from metrologia.models import (
    AtendimentoSolicitacao, CotacaoFornecedor, Instrumento, ItemCotacao,
    ItemSolicitacaoCotacao, SolicitacaoCotacao,
)


class PlanejamentoAtendimentosTests(TestCase):
    """Planejamento: campos únicos por agrupamento, desconsiderar com justificativa e ocorrência."""

    def setUp(self):
        self.user = User.objects.create_superuser("adm_m", "m@example.com", "x")
        self.client.force_login(self.user)
        self.fornecedor = Fornecedor.objects.create(empresa="Trescal", nome_fantasia="Trescal", endereco="x", uf="SP")
        self.sol = SolicitacaoCotacao.objects.create(solicitante=self.user) if "solicitante" in {
            f.name for f in SolicitacaoCotacao._meta.get_fields()} else SolicitacaoCotacao.objects.create()
        self.cot = CotacaoFornecedor.objects.create(solicitacao=self.sol, fornecedor=self.fornecedor, numero="COT-T-0001")
        self.atends = {}
        for tag, local in (("RC-01", "NO_LOCAL"), ("RC-02", "NO_LOCAL"), ("ES-01", "NO_LABORATORIO")):
            inst = Instrumento.objects.create(tag=tag, descricao=tag)
            item = ItemSolicitacaoCotacao.objects.create(solicitacao=self.sol, instrumento=inst)
            ic = ItemCotacao.objects.create(
                cotacao_fornecedor=self.cot, item_solicitacao=item, instrumento=inst,
                pode_atender=True, local_atendimento=local, valor_unitario=10,
            )
            self.atends[tag] = AtendimentoSolicitacao.objects.create(
                solicitacao=self.sol, item_solicitacao=item, item_cotacao=ic,
                data_prevista_atendimento=date(2026, 11, 17),
            )

    def _salvar(self, tipo, tags, grupo):
        return self.client.post(
            reverse("metrologia:atendimento_atualizar_dados"),
            data=json.dumps({"tipo": tipo, "cotacao_id": self.cot.id,
                             "atendimentos": [self.atends[t].id for t in tags], "grupo": grupo}),
            content_type="application/json",
        )

    def test_pagina_renderiza_com_campos_unicos_por_agrupamento(self):
        r = self.client.get(reverse("metrologia:solicitacao_detail", args=[self.sol.id]))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertEqual(html.count('data-grupo-campo="data_realizada"'), 1)   # 1 data para todos os itens
        self.assertEqual(html.count('data-grupo-campo="tecnico_telefone"'), 1)
        self.assertEqual(html.count('data-grupo-campo="data_envio"'), 1)
        self.assertEqual(html.count('data-grupo-campo="data_retorno_previsto"'), 1)
        self.assertEqual(html.count("Desconsiderar</label>"), 3)               # flag em todos
        self.assertEqual(html.count("abrirOcorrenciaAtendimento("), 3 + 1)     # botão em todos (+ definição JS)

    def test_salva_grupo_no_local_em_todos_os_itens(self):
        r = self._salvar("NO_LOCAL", ["RC-01", "RC-02"], {
            "data_realizada": "2026-11-17", "tecnico": "Maria", "tecnico_telefone": "(11) 99999-0000"})
        self.assertEqual(r.json()["atualizados"], 2)
        for tag in ("RC-01", "RC-02"):
            a = AtendimentoSolicitacao.objects.get(pk=self.atends[tag].pk)
            self.assertEqual((a.data_realizada, a.tecnico_responsavel, a.tecnico_telefone),
                             (date(2026, 11, 17), "Maria", "(11) 99999-0000"))

    def test_salva_grupo_laboratorio_e_rejeita_data_invalida(self):
        self._salvar("NO_LABORATORIO", ["ES-01"], {"data_envio": "2026-11-18", "data_retorno_previsto": "2026-12-01"})
        a = AtendimentoSolicitacao.objects.get(pk=self.atends["ES-01"].pk)
        self.assertEqual((a.data_envio, a.data_retorno_previsto), (date(2026, 11, 18), date(2026, 12, 1)))
        r = self._salvar("NO_LABORATORIO", ["ES-01"], {"data_envio": "18/11/2026"})
        self.assertEqual(r.status_code, 400)

    def test_desconsiderar_exige_justificativa_e_sai_do_andamento(self):
        url = reverse("metrologia:atendimento_desconsiderar", args=[self.atends["RC-02"].id])
        self.client.post(url, {"desconsiderado": "1", "justificativa": "  "})
        self.assertFalse(AtendimentoSolicitacao.objects.get(pk=self.atends["RC-02"].pk).desconsiderado)

        self.client.post(url, {"desconsiderado": "1", "justificativa": "Instrumento inutilizado"})
        a = AtendimentoSolicitacao.objects.get(pk=self.atends["RC-02"].pk)
        self.assertTrue(a.desconsiderado)
        self.assertEqual((a.justificativa_desconsiderar, a.desconsiderado_por), ("Instrumento inutilizado", self.user))

        # salvar o grupo não altera o item desconsiderado
        self._salvar("NO_LOCAL", ["RC-01", "RC-02"], {"data_realizada": "2026-11-17"})
        self.assertIsNone(AtendimentoSolicitacao.objects.get(pk=self.atends["RC-02"].pk).data_realizada)

        # com os demais concluídos, a solicitação considera só os ativos
        self._salvar("NO_LABORATORIO", ["ES-01"], {"data_retorno": "2026-11-20"})
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.status, "REALIZADO")

        self.client.post(url, {"desconsiderado": "0"})
        self.assertFalse(AtendimentoSolicitacao.objects.get(pk=self.atends["RC-02"].pk).desconsiderado)

    def test_botao_de_ocorrencia_usa_o_fluxo_existente(self):
        from qms.models import OcorrenciaInstrumento
        inst = self.atends["RC-01"].item_solicitacao.instrumento
        pagina = reverse("metrologia:solicitacao_detail", args=[self.sol.id])
        dados = {"instrumento_id": inst.id, "tipo": "AVARIA", "descricao": "Caiu", "data_ocorrencia": "2026-11-17"}
        r = self.client.post(reverse("metrologia:registrar_ocorrencia"), dados, HTTP_REFERER=pagina)
        self.assertRedirects(r, pagina)                       # volta para a tela do planejamento
        self.assertEqual(OcorrenciaInstrumento.objects.get().instrumento, inst)
        r = self.client.post(reverse("metrologia:registrar_ocorrencia"), dados)  # sem Referer: não quebra
        self.assertEqual(r.status_code, 302)
