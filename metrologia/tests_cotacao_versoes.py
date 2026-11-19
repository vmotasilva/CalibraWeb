from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from fornecedores.models import Fornecedor
from metrologia.models import (
    AtendimentoSolicitacao, CotacaoFornecedor, CustoAdicionalCotacao, Instrumento, ItemCotacao,
    ItemSolicitacaoCotacao, SolicitacaoCotacao,
)
from metrologia.services.comparativo_cotacoes import comparar_fornecedores, comparar_versoes


class BaseVersoes(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u", password="p")
        self.client.force_login(self.user)
        self.sol = SolicitacaoCotacao.objects.create()
        self.insts, self.itens_sol = [], []
        for tag in ("LE-01", "LE-02", "LE-03"):
            inst = Instrumento.objects.create(tag=tag, descricao="LENSÔMETRO")
            self.insts.append(inst)
            self.itens_sol.append(ItemSolicitacaoCotacao.objects.create(solicitacao=self.sol, instrumento=inst))
        self.sol.atualizar_status_automatico()
        self.f1 = Fornecedor.objects.create(empresa="Alfa Lab", nome_fantasia="Alfa", endereco="r", uf="SP")
        self.f2 = Fornecedor.objects.create(empresa="Beta Cal", nome_fantasia="Beta", endereco="r", uf="SP")

    def cotacao(self, forn, valores, status="RESPONDIDA", prazo=None, custos=(), **extra):
        cot = CotacaoFornecedor.objects.create(solicitacao=self.sol, fornecedor=forn, status=status, **extra)
        for inst, item_sol, v in zip(self.insts, self.itens_sol, valores):
            if v is None:
                continue
            ItemCotacao.objects.create(cotacao_fornecedor=cot, item_solicitacao=item_sol, instrumento=inst,
                                       valor_unitario=Decimal(str(v)), pode_atender=bool(v), prazo_dias=prazo)
        for tipo, qtd, val in custos:
            CustoAdicionalCotacao.objects.create(cotacao_fornecedor=cot, tipo=tipo, quantidade=qtd,
                                                 valor_unitario=Decimal(str(val)))
        return cot

    def ativacao(self, cot, acao, **dados):
        return self.client.post(reverse("metrologia:cotacao_fornecedor_ativacao", args=[cot.id]),
                                {"acao": acao, **dados})


class InativarENovaVersaoTests(BaseVersoes):
    def test_inativar_exige_motivo_e_marca_obsoleta(self):
        cot = self.cotacao(self.f1, [1000, 1000, 1000], aprovada=True, status="ACEITA")
        self.ativacao(cot, "inativar", motivo="")
        cot.refresh_from_db()
        self.assertTrue(cot.ativa)
        self.ativacao(cot, "inativar", motivo="valores desatualizados")
        cot.refresh_from_db()
        self.assertFalse(cot.ativa)
        self.assertFalse(cot.aprovada)
        self.assertEqual((cot.motivo_inativacao, cot.inativada_por), ("valores desatualizados", self.user))
        self.assertIsNotNone(cot.inativada_em)
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.status, "INSTRUMENTOS_SELECIONADOS")     # sem cotação ativa

    def test_inativar_e_criar_nova_versao_copia_itens_e_custos(self):
        cot = self.cotacao(self.f1, [1000, 1100, 1200], prazo=15, custos=[("PASSAGEM_AEREA", 2, 800)])
        r = self.ativacao(cot, "inativar_nova", motivo="reajuste")
        nova = CotacaoFornecedor.objects.get(versao_anterior=cot)
        self.assertRedirects(r, reverse("metrologia:cotacao_fornecedor_update", args=[nova.id]))
        self.assertTrue(nova.ativa)
        self.assertNotEqual(nova.numero, cot.numero)
        self.assertEqual((nova.fornecedor, nova.status, nova.aprovada), (self.f1, "RASCUNHO", False))
        self.assertEqual(sorted(nova.itens.values_list("valor_unitario", flat=True)),
                         [Decimal("1000.00"), Decimal("1100.00"), Decimal("1200.00")])
        self.assertEqual(nova.get_valor_custos_adicionais(), Decimal("1600.00"))
        self.assertEqual(nova.itens.first().prazo_dias, 15)

    def test_nao_inativa_com_atendimento_planejado(self):
        cot = self.cotacao(self.f1, [1000, 1000, 1000], aprovada=True, status="ACEITA")
        item = cot.itens.first()
        AtendimentoSolicitacao.objects.create(
            solicitacao=self.sol, item_solicitacao=item.item_solicitacao, item_cotacao=item,
            data_prevista_atendimento="2026-12-01")
        self.ativacao(cot, "inativar", motivo="x")
        cot.refresh_from_db()
        self.assertTrue(cot.ativa)

    def test_so_uma_cotacao_ativa_por_fornecedor(self):
        cot = self.cotacao(self.f1, [1000, 1000, 1000])
        # criar outra ativa do mesmo fornecedor pela tela: erro de formulário, não 500
        r = self.client.post(reverse("metrologia:cotacao_fornecedor_create", args=[self.sol.id]),
                             {"fornecedor": self.f1.id})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Já existe uma cotação ativa deste fornecedor")
        self.assertEqual(CotacaoFornecedor.objects.filter(fornecedor=self.f1).count(), 1)
        # depois de inativar, pode criar a nova
        self.ativacao(cot, "inativar", motivo="obsoleta")
        r = self.client.post(reverse("metrologia:cotacao_fornecedor_create", args=[self.sol.id]),
                             {"fornecedor": self.f1.id})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(CotacaoFornecedor.objects.filter(fornecedor=self.f1).count(), 2)

    def test_reativar_bloqueado_se_ha_outra_ativa(self):
        cot = self.cotacao(self.f1, [1000, 1000, 1000])
        self.ativacao(cot, "inativar", motivo="obsoleta")
        nova = self.cotacao(self.f1, [1100, 1100, 1100])
        self.ativacao(cot, "reativar")
        cot.refresh_from_db()
        self.assertFalse(cot.ativa)
        self.ativacao(nova, "inativar", motivo="voltar")
        self.ativacao(cot, "reativar")
        cot.refresh_from_db()
        self.assertTrue(cot.ativa)
        self.assertEqual(cot.motivo_inativacao, "")

    def test_obsoleta_sai_dos_totais_e_do_programado(self):
        from metrologia.views.novo_fluxo_cotacao import acompanhamento_instrumentos
        cot = self.cotacao(self.f1, [1000, 1000, 1000], aprovada=True, status="ACEITA",
                           )
        for item in cot.itens.all():
            item.tipo_servico = "CALIBRACAO"
            item.save()
        self.assertEqual(acompanhamento_instrumentos()[self.insts[0].id]["codigo"], "CALIBRACAO_PROGRAMADA")
        self.ativacao(cot, "inativar", motivo="obsoleta")
        self.assertNotEqual(acompanhamento_instrumentos().get(self.insts[0].id, {}).get("codigo"), "CALIBRACAO_PROGRAMADA")
        html = self.client.get(reverse("metrologia:solicitacao_detail", args=[self.sol.id])).content.decode()
        self.assertIn("Cotações obsoletas (1)", html)
        self.assertIn("Cotações (0)", html)


class ComparativosTests(BaseVersoes):
    def _textos(self, resultado):
        return " | ".join(a["texto"] for a in resultado["alertas"])

    def test_versao_total_sobe_e_item_acima_do_limite(self):
        antiga = self.cotacao(self.f1, [1000, 1000, 1000], prazo=10, custos=[("DESLOCAMENTO", 1, 100)], ativa=False)
        nova = self.cotacao(self.f1, [1000, 1000, 1300], prazo=20, custos=[("DESLOCAMENTO", 1, 400)],
                            versao_anterior=antiga)
        r = comparar_versoes(nova, antiga)
        self.assertEqual(r["totais"]["total_ant"], Decimal("3100.00"))
        self.assertEqual(r["totais"]["total_nov"], Decimal("3700.00"))
        textos = self._textos(r)
        self.assertIn("O valor total subiu +19.4%".replace(".", ","), textos)
        self.assertIn("LE-03: +30,0%", textos)
        self.assertIn("reajustes não são uniformes", textos)
        self.assertIn("Custo adicional de deslocamento", textos)
        self.assertIn("O prazo aumentou de 10 para 20 dias", textos)
        self.assertTrue(any(a["pergunta"] for a in r["alertas"]))
        linha = {l["tag"]: l for l in r["linhas"]}
        self.assertTrue(linha["LE-03"]["destaque"])
        self.assertFalse(linha["LE-01"]["destaque"])

    def test_versao_item_removido_e_preco_inconsistente(self):
        antiga = self.cotacao(self.f1, [1000, 1000, 1000], ativa=False)
        nova = self.cotacao(self.f1, [1000, 1200, None], versao_anterior=antiga)
        r = comparar_versoes(nova, antiga)
        textos = self._textos(r)
        self.assertIn("Deixaram de ser cotados/atendidos: LE-03", textos)
        self.assertIn("Instrumentos iguais (LENSÔMETRO) com valores diferentes", textos)
        self.assertEqual([a["nivel"] for a in r["alertas"] if "LE-03" in a["texto"]], ["danger"])

    def test_versao_mesmo_valor_pergunta_o_que_mudou(self):
        antiga = self.cotacao(self.f1, [1000, 1000, 1000], ativa=False)
        nova = self.cotacao(self.f1, [1000, 1000, 1000], versao_anterior=antiga)
        self.assertIn("mesmo valor total", self._textos(comparar_versoes(nova, antiga)))

    def test_fornecedores_matriz_menor_preco_e_alertas(self):
        self.cotacao(self.f1, [1000, 1000, 1000])
        self.cotacao(self.f2, [900, 1300, None], custos=[("PASSAGEM_AEREA", 2, 800)])
        r = comparar_fornecedores(self.sol)
        self.assertEqual([c.fornecedor.empresa for c in r["cotacoes"]], ["Beta Cal", "Alfa Lab"]
                         if r["cotacoes"][0].fornecedor == self.f2 else ["Alfa Lab", "Beta Cal"])
        linhas = {l["tag"]: l for l in r["linhas"]}
        menores = {l: [c["cotacao"].fornecedor.empresa for c in linhas[l]["celulas"] if c["menor"]] for l in linhas}
        self.assertEqual(menores["LE-01"], ["Beta Cal"])
        self.assertEqual(menores["LE-02"], ["Alfa Lab"])
        self.assertEqual(menores["LE-03"], [])                # só um fornecedor cotou
        textos = self._textos(r)
        self.assertIn("Beta Cal não cotou/atende: LE-03", textos)
        self.assertIn("custos adicionais são", textos)
        self.assertIn("dividido entre fornecedores", textos)
        totais = {t["cotacao"].fornecedor.empresa: t for t in r["totais"]}
        self.assertFalse(totais["Beta Cal"]["completa"])
        self.assertTrue(totais["Alfa Lab"]["completa"])
        # a incompleta não é destacada como "menor total", mesmo sendo mais barata no papel
        self.assertFalse(totais["Beta Cal"]["menor"])

    def test_fornecedores_diferenca_grande_entre_totais(self):
        self.cotacao(self.f1, [1000, 1000, 1000])
        self.cotacao(self.f2, [1500, 1500, 1500])
        textos = self._textos(comparar_fornecedores(self.sol))
        self.assertIn("Beta Cal está +50,0% acima de Alfa Lab", textos)

    def test_comparativo_so_com_duas_cotacoes_ativas_com_valores(self):
        cot = self.cotacao(self.f1, [1000, 1000, 1000])
        self.assertIsNone(comparar_fornecedores(self.sol))
        outra = self.cotacao(self.f2, [1100, 1100, 1100])
        self.assertIsNotNone(comparar_fornecedores(self.sol))
        outra.ativa = False
        outra.save()
        self.assertIsNone(comparar_fornecedores(self.sol))

    def test_telas_mostram_comparativos(self):
        antiga = self.cotacao(self.f1, [1000, 1000, 1000])
        self.ativacao(antiga, "inativar_nova", motivo="reajuste")
        nova = CotacaoFornecedor.objects.get(versao_anterior=antiga)
        ItemCotacao.objects.filter(cotacao_fornecedor=nova, instrumento=self.insts[0]).update(valor_unitario=Decimal("1500"))
        for it in nova.itens.all():
            it.save()
        html = self.client.get(reverse("metrologia:cotacao_fornecedor_detail", args=[nova.id])).content.decode()
        self.assertIn("Comparação com a versão anterior", html)
        self.assertIn("Questionamentos sugeridos", html)
        self.assertIn(antiga.numero, html)
        html = self.client.get(reverse("metrologia:cotacao_fornecedor_detail", args=[antiga.id])).content.decode()
        self.assertIn("Cotação obsoleta", html)
        self.assertIn(nova.numero, html)
        # comparativo entre fornecedores na solicitação
        self.cotacao(self.f2, [900, 900, 900])
        html = self.client.get(reverse("metrologia:solicitacao_detail", args=[self.sol.id])).content.decode()
        self.assertIn("Comparativo de cotações (2 fornecedores)", html)
        self.assertIn("Cotações obsoletas (1)", html)


class ModalENovaVersaoRetroativaTests(BaseVersoes):
    def test_enter_no_motivo_nao_deixa_de_criar_a_nova_versao(self):
        """O envio por Enter usa o 1º botão: agora só há um botão e a caixa 'nova versão' vem marcada."""
        html = self.client.get(reverse("metrologia:solicitacao_detail", args=[self.sol.id])).content.decode()
        modal = html[html.index('id="modalInativarCotacao"'):]
        modal = modal[:modal.index("</form>")]
        self.assertEqual(modal.count('type="submit"'), 1)
        self.assertIn('name="nova_versao"', modal)
        self.assertIn('id="inativarNovaVersao" checked', modal)

    def test_inativar_com_caixa_marcada_cria_a_nova_versao(self):
        cot = self.cotacao(self.f1, [1000, 1000, 1000])
        r = self.ativacao(cot, "inativar", motivo="valores desatualizados", nova_versao="1")
        nova = CotacaoFornecedor.objects.get(versao_anterior=cot)
        self.assertRedirects(r, reverse("metrologia:cotacao_fornecedor_update", args=[nova.id]))

    def test_inativar_com_caixa_desmarcada_so_inativa(self):
        cot = self.cotacao(self.f1, [1000, 1000, 1000])
        self.ativacao(cot, "inativar", motivo="x")
        self.assertFalse(CotacaoFornecedor.objects.filter(versao_anterior=cot).exists())

    def test_cria_nova_versao_de_cotacao_que_ja_esta_obsoleta(self):
        cot = self.cotacao(self.f1, [1000, 1100, 1200], custos=[("DESLOCAMENTO", 1, 100)])
        self.ativacao(cot, "inativar", motivo="Valores Desatualizados")        # ficou sem cópia
        pagina = self.client.get(reverse("metrologia:solicitacao_detail", args=[self.sol.id])).content.decode()
        self.assertIn('value="nova_versao"', pagina)                            # botão aparece
        r = self.ativacao(cot, "nova_versao")
        nova = CotacaoFornecedor.objects.get(versao_anterior=cot)
        self.assertRedirects(r, reverse("metrologia:cotacao_fornecedor_update", args=[nova.id]))
        self.assertTrue(nova.ativa)
        self.assertEqual(nova.get_valor_servicos(), Decimal("3300.00"))
        self.assertEqual(nova.get_valor_custos_adicionais(), Decimal("100.00"))
        # com uma ativa do fornecedor, não oferece nem cria outra
        pagina = self.client.get(reverse("metrologia:solicitacao_detail", args=[self.sol.id])).content.decode()
        self.assertNotIn('value="nova_versao"', pagina)
        self.ativacao(cot, "nova_versao")
        self.assertEqual(CotacaoFornecedor.objects.filter(versao_anterior=cot).count(), 1)

    def test_nova_versao_so_para_obsoleta(self):
        cot = self.cotacao(self.f1, [1000, 1000, 1000])
        self.ativacao(cot, "nova_versao")                                         # ativa: não cria
        self.assertFalse(CotacaoFornecedor.objects.filter(versao_anterior=cot).exists())


class EdicaoDaNovaVersaoTests(BaseVersoes):
    def _nova_versao(self):
        antiga = self.cotacao(self.f1, [1125, 1125, 1125], data_solicitacao="2026-10-05",
                              data_retorno_fornecedor="2026-10-05")
        self.ativacao(antiga, "inativar", motivo="reajuste", nova_versao="1")
        return antiga, CotacaoFornecedor.objects.get(versao_anterior=antiga)

    def test_tela_de_edicao_da_nova_versao_mostra_os_instrumentos_copiados(self):
        _antiga, nova = self._nova_versao()
        self.assertIsNone(nova.data_retorno_fornecedor)             # ainda sem retorno do fornecedor
        html = self.client.get(reverse("metrologia:cotacao_fornecedor_update", args=[nova.id])).content.decode()
        self.assertIn("Instrumentos da Solicitação", html)
        for tag in ("LE-01", "LE-02", "LE-03"):
            self.assertIn(f"<strong>{tag}</strong>", html)
        self.assertEqual(html.count('value="1125.00"'), 3)           # valores copiados, com ponto decimal
        self.assertIn('name="itens_enviados"', html)

    def test_datas_da_cotacao_vao_em_formato_iso(self):
        _antiga, nova = self._nova_versao()
        html = self.client.get(reverse("metrologia:cotacao_fornecedor_update", args=[nova.id])).content.decode()
        import re
        campo = re.search(r'<input[^>]*name="data_solicitacao"[^>]*>', html).group(0)
        self.assertIn(f'value="{nova.data_solicitacao.isoformat()}"', campo)   # AAAA-MM-DD, aceito pelo type=date

    def test_atualizar_valores_da_nova_versao(self):
        antiga, nova = self._nova_versao()
        dados = {"fornecedor": self.f1.id, "itens_enviados": "1"}
        for item in nova.itens.all():
            dados[f"item_{item.item_solicitacao_id}_pode_atender"] = "on"
            dados[f"item_{item.item_solicitacao_id}_valor"] = "1400.00"
        r = self.client.post(reverse("metrologia:cotacao_fornecedor_update", args=[nova.id]), dados)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(set(nova.itens.values_list("valor_unitario", flat=True)), {Decimal("1400.00")})
        self.assertEqual(antiga.get_valor_servicos(), Decimal("3375.00"))   # a obsoleta não muda
        html = self.client.get(reverse("metrologia:cotacao_fornecedor_detail", args=[nova.id])).content.decode()
        self.assertIn("Comparação com a versão anterior", html)

    def test_salvar_dados_gerais_sem_a_tabela_nao_zera_pode_atender(self):
        _antiga, nova = self._nova_versao()
        self.assertTrue(all(nova.itens.values_list("pode_atender", flat=True)))
        self.client.post(reverse("metrologia:cotacao_fornecedor_update", args=[nova.id]), {"fornecedor": self.f1.id})
        self.assertTrue(all(nova.itens.values_list("pode_atender", flat=True)))


class DesfazerNovaVersaoTests(BaseVersoes):
    def _par(self, **extra):
        antiga = self.cotacao(self.f1, [1000, 1100, 1200], **extra)
        self.ativacao(antiga, "inativar", motivo="reajuste", nova_versao="1")
        antiga.refresh_from_db()
        return antiga, CotacaoFornecedor.objects.get(versao_anterior=antiga)

    def test_desfazer_descarta_a_nova_e_reativa_a_anterior(self):
        antiga, nova = self._par()
        ItemCotacao.objects.filter(cotacao_fornecedor=nova).update(valor_unitario=Decimal("2000"))
        numero_nova = nova.numero
        r = self.ativacao(nova, "desfazer_versao")
        self.assertRedirects(r, reverse("metrologia:solicitacao_detail", args=[self.sol.id]))
        self.assertFalse(CotacaoFornecedor.objects.filter(pk=nova.pk).exists())
        self.assertFalse(ItemCotacao.objects.filter(cotacao_fornecedor_id=nova.pk).exists())
        antiga.refresh_from_db()
        self.assertTrue(antiga.ativa)
        self.assertEqual((antiga.motivo_inativacao, antiga.inativada_em, antiga.inativada_por), ("", None, None))
        self.assertEqual(antiga.get_valor_servicos(), Decimal("3300.00"))         # valores originais intactos
        html = self.client.get(reverse("metrologia:solicitacao_detail", args=[self.sol.id])).content.decode()
        self.assertNotIn(numero_nova, html)
        self.assertNotIn("Cotações obsoletas", html)

    def test_aceita_volta_aprovada_e_status_recalculado(self):
        antiga, nova = self._par(status="ACEITA", aprovada=True)
        self.assertFalse(antiga.aprovada)                                           # inativada tira a aprovação
        self.ativacao(nova, "desfazer_versao")
        antiga.refresh_from_db()
        self.assertTrue(antiga.aprovada)
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.status, "AGUARDANDO_PLANEJAMENTO")

    def test_botoes_aparecem_na_nova_versao(self):
        antiga, nova = self._par()
        html = self.client.get(reverse("metrologia:solicitacao_detail", args=[self.sol.id])).content.decode()
        self.assertIn('value="desfazer_versao"', html)
        self.assertIn(f"Voltar p/ anterior", html)
        det = self.client.get(reverse("metrologia:cotacao_fornecedor_detail", args=[nova.id])).content.decode()
        self.assertIn(f"Desfazer e voltar para {antiga.numero}", det)

    def test_bloqueado_com_atendimento_mesmo_desconsiderado(self):
        antiga, nova = self._par()
        item = nova.itens.first()
        AtendimentoSolicitacao.objects.create(
            solicitacao=self.sol, item_solicitacao=item.item_solicitacao, item_cotacao=item,
            data_prevista_atendimento="2026-12-01", desconsiderado=True, justificativa_desconsiderar="x")
        self.ativacao(nova, "desfazer_versao")                                      # sem erro 500
        self.assertTrue(CotacaoFornecedor.objects.filter(pk=nova.pk).exists())
        antiga.refresh_from_db()
        self.assertFalse(antiga.ativa)

    def test_so_vale_para_nova_versao_ativa(self):
        cot = self.cotacao(self.f2, [1000, 1000, 1000])                              # sem versão anterior
        self.ativacao(cot, "desfazer_versao")
        self.assertTrue(CotacaoFornecedor.objects.filter(pk=cot.pk).exists())
        antiga, nova = self._par()
        self.ativacao(antiga, "desfazer_versao")                                     # a obsoleta não tem anterior
        self.assertTrue(CotacaoFornecedor.objects.filter(pk=antiga.pk).exists())
