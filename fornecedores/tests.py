from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import FornecedorForm, cnpj_valido
from .forms_documento import DocumentoFornecedorForm
from .models import (
    AvaliacaoFornecedor, CategoriaDocumento, DocumentoFornecedor, Fornecedor,
    PerguntaAvaliacao, RespostaAvaliacao, RespostaMatrizAvaliacao,
)
from . import services

CNPJ_OK = "46.123.323/0001-73"
CNPJ_OK_2 = "11.222.333/0001-81"


def dados_fornecedor(**extra):
    d = {"empresa": "ACME", "nome_fantasia": "Acme", "endereco": "Rua A", "cnpj": CNPJ_OK, "uf": "BA",
         "tipo": "NAO_CRITICO", "ativo": "on"}
    d.update(extra)
    return d


class BaseTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser("admin", "a@a.com", "x")
        cls.f = Fornecedor.objects.create(empresa="MSMI", nome_fantasia="MSMI", endereco="x", uf="BA")

    def setUp(self):
        self.client.force_login(self.user)

    def url(self, name, *args):
        return reverse(f"fornecedores:{name}", args=args)


class FornecedorFormTests(TestCase):
    def test_cnpj_digitos_verificadores(self):
        self.assertTrue(cnpj_valido("46123323000173"))
        self.assertFalse(cnpj_valido("46123323000174"))
        self.assertFalse(cnpj_valido("11111111111111"))

    def test_cnpj_invalido_e_normalizado(self):
        self.assertIn("cnpj", FornecedorForm(dados_fornecedor(cnpj="123")).errors)
        form = FornecedorForm(dados_fornecedor(cnpj="46123323000173"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["cnpj"], CNPJ_OK)

    def test_cnpj_duplicado_bloqueado(self):
        Fornecedor.objects.create(empresa="X", nome_fantasia="X", endereco="x", uf="BA", cnpj=CNPJ_OK)
        self.assertIn("cnpj", FornecedorForm(dados_fornecedor(cnpj="46123323000173")).errors)

    def test_cnpj_opcional_e_edicao_do_proprio(self):
        self.assertTrue(FornecedorForm(dados_fornecedor(cnpj="")).is_valid())
        f = Fornecedor.objects.create(empresa="X", nome_fantasia="X", endereco="x", uf="BA", cnpj=CNPJ_OK)
        self.assertTrue(FornecedorForm(dados_fornecedor(), instance=f).is_valid())

    def test_uf_invalida(self):
        self.assertIn("uf", FornecedorForm(dados_fornecedor(uf="ZZ")).errors)
        self.assertTrue(FornecedorForm(dados_fornecedor(uf="EX", cnpj="")).is_valid())


class DocumentoFormTests(TestCase):
    def form(self, nome, conteudo=b"x"):
        cat = CategoriaDocumento.objects.create(nome="c")
        return DocumentoFornecedorForm({"categoria": cat.pk}, {"arquivo": SimpleUploadedFile(nome, conteudo)})

    def test_extensao_bloqueada(self):
        self.assertIn("arquivo", self.form("virus.exe").errors)
        self.assertIn("arquivo", self.form("pagina.html").errors)

    def test_pdf_aceito(self):
        self.assertTrue(self.form("a.PDF").is_valid())


class ListaEDetalheTests(BaseTest):
    def test_lista_filtra_e_pagina(self):
        for i in range(30):
            Fornecedor.objects.create(empresa=f"Emp {i:02d}", nome_fantasia="n", endereco="x", uf="SP")
        r = self.client.get(self.url("fornecedor_list"))
        self.assertEqual(len(r.context["fornecedores"]), 25)
        r = self.client.get(self.url("fornecedor_list"), {"uf": "SP", "page": 2})
        self.assertEqual(len(r.context["fornecedores"]), 5)
        r = self.client.get(self.url("fornecedor_list"), {"tipo": "INVALIDO", "ativo": "x"})
        self.assertEqual(r.status_code, 200)

    def test_lista_sem_n_mais_1(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        def consultas():
            with CaptureQueriesContext(connection) as ctx:
                self.client.get(self.url("fornecedor_list"))
            return len(ctx)

        antes = consultas()
        for i in range(20):
            Fornecedor.objects.create(empresa=f"E{i}", nome_fantasia="n", endereco="x", uf="SP")
        self.assertEqual(consultas(), antes)  # nº de consultas independe da quantidade de fornecedores

    def test_detalhe_nao_mostra_none(self):
        r = self.client.get(self.url("fornecedor_detail", self.f.pk))
        self.assertNotContains(r, ">None<")

    def test_detalhe_documento_vencido(self):
        cat = CategoriaDocumento.objects.create(nome="AFE")
        DocumentoFornecedor.objects.create(
            fornecedor=self.f, categoria=cat, arquivo="x.pdf", data_validade=timezone.localdate() - timedelta(days=1)
        )
        r = self.client.get(self.url("fornecedor_detail", self.f.pk))
        self.assertContains(r, "Vencido")

    def test_hub(self):
        self.assertEqual(self.client.get(self.url("modulo")).status_code, 200)


class PerguntasTests(BaseTest):
    def test_excluir_pergunta_respondida_apenas_desativa(self):
        p = PerguntaAvaliacao.objects.create(texto="q", tipo="SELECAO")
        av = AvaliacaoFornecedor.objects.create(fornecedor=self.f, data=timezone.localdate(), tipo="SELECAO")
        RespostaAvaliacao.objects.create(avaliacao=av, pergunta=p, resposta=True)
        self.client.post(self.url("pergunta_delete", p.pk))
        p.refresh_from_db()
        self.assertFalse(p.ativo)
        self.assertEqual(av.respostas.count(), 1)

    def test_excluir_pergunta_sem_respostas(self):
        p = PerguntaAvaliacao.objects.create(texto="q", tipo="SELECAO")
        self.client.post(self.url("pergunta_delete", p.pk))
        self.assertFalse(PerguntaAvaliacao.objects.filter(pk=p.pk).exists())

    def test_perguntas_filtradas_tipo_invalido(self):
        r = self.client.get(self.url("perguntas_filtradas"), {"tipo": "XX"})
        self.assertEqual(r.json(), {"perguntas": []})


class SelecaoReavaliacaoTests(BaseTest):
    def setUp(self):
        super().setUp()
        self.ps = [PerguntaAvaliacao.objects.create(texto=f"s{i}", tipo="SELECAO", ordem=i) for i in range(4)]
        self.pr = [PerguntaAvaliacao.objects.create(texto=f"r{i}", tipo="REAVALIACAO", ordem=i) for i in range(2)]

    def post(self, name, perguntas, marcadas, data=None, obs=""):
        dados = {"data": (data or timezone.localdate()).isoformat(), "observacao": obs}
        for p in perguntas[:marcadas]:
            dados[f"resposta_{p.id}"] = "on"
        return self.client.post(self.url(name, self.f.pk), dados)

    def test_selecao_pontuacao_e_atualizacao_mesma_data(self):
        self.post("avaliacao_selecao_create", self.ps, 3, obs="ok")
        av = AvaliacaoFornecedor.objects.get(tipo="SELECAO")
        self.assertEqual((av.pontuacao_ano, av.resultado, av.observacao), (75.0, "Bom", "ok"))
        self.post("avaliacao_selecao_create", self.ps, 4)
        self.assertEqual(AvaliacaoFornecedor.objects.filter(tipo="SELECAO").count(), 1)
        av.refresh_from_db()
        self.assertEqual((av.pontuacao_ano, av.resultado), (100.0, "Excelente"))
        self.assertEqual(av.respostas.count(), 4)

    def test_data_invalida_ou_futura_rejeitada(self):
        r = self.client.post(self.url("avaliacao_selecao_create", self.f.pk), {"data": "lixo"})
        self.assertEqual(r.status_code, 200)
        self.post("avaliacao_selecao_create", self.ps, 1, data=timezone.localdate() + timedelta(days=3))
        self.assertFalse(AvaliacaoFornecedor.objects.exists())

    def test_formulario_traz_observacao_anterior(self):
        self.post("avaliacao_selecao_create", self.ps, 1, obs="nota importante")
        r = self.client.get(self.url("avaliacao_selecao_create", self.f.pk))
        self.assertContains(r, "nota importante")

    def test_reavaliacao_uma_por_ano(self):
        hoje = timezone.localdate()
        self.post("avaliacao_reavaliacao_create", self.pr, 2, data=hoje.replace(month=1, day=1))
        self.assertEqual(AvaliacaoFornecedor.objects.filter(tipo="REAVALIACAO").count(), 1)
        # outra data no mesmo ano: bloqueada (antes passava quando era a mais recente)
        self.post("avaliacao_reavaliacao_create", self.pr, 0, data=hoje)
        if hoje != hoje.replace(month=1, day=1):
            self.assertEqual(AvaliacaoFornecedor.objects.filter(tipo="REAVALIACAO").count(), 1)
        # mesma data: atualiza
        self.post("avaliacao_reavaliacao_create", self.pr, 0, data=hoje.replace(month=1, day=1))
        av = AvaliacaoFornecedor.objects.get(tipo="REAVALIACAO")
        self.assertEqual((av.pontuacao_ano, av.resultado), (0.0, "Reprovado"))

    def test_rota_legada_redireciona(self):
        r = self.client.post(self.url("reavaliacao_create", self.f.pk), {"data": "2025-01-01"})
        self.assertRedirects(r, self.url("avaliacao_reavaliacao_create", self.f.pk))

    def test_reavaliacao_delete(self):
        self.post("avaliacao_reavaliacao_create", self.pr, 2)
        self.client.post(self.url("reavaliacao_delete", self.f.pk))
        self.assertFalse(AvaliacaoFornecedor.objects.filter(tipo="REAVALIACAO").exists())


class MonitoramentoTests(BaseTest):
    def setUp(self):
        super().setUp()
        self.pp = PerguntaAvaliacao.objects.create(texto="prazo", tipo="MONITORAMENTO", produto_servico="PRODUTO", ordem=1)
        self.pa = PerguntaAvaliacao.objects.create(texto="geral", tipo="MONITORAMENTO", produto_servico="AMBOS", ordem=2)
        self.ps = PerguntaAvaliacao.objects.create(texto="serv", tipo="MONITORAMENTO", produto_servico="SERVICO", ordem=3)

    def post_nova(self, marcadas=(), **extra):
        dados = {"data": timezone.localdate().isoformat(), "nota_fiscal": "NF1", "tipo_nota": "PRODUTO", "observacao": ""}
        dados.update(extra)
        for p in marcadas:
            dados[f"resposta_{p.id}"] = "on"
        return self.client.post(self.url("avaliacao_create", self.f.pk), dados)

    def test_tipo_nota_obrigatorio(self):
        r = self.post_nova(tipo_nota="")
        self.assertEqual(r.status_code, 200)  # antes: 500 (NameError) ou tudo "NÃO"
        self.assertFalse(AvaliacaoFornecedor.objects.exists())

    def test_pontuacao_so_perguntas_do_tipo(self):
        self.post_nova(marcadas=[self.pa])  # PRODUTO + AMBOS; "prazo" desmarcada = 1 ocorrência
        av = AvaliacaoFornecedor.objects.get()
        self.assertEqual(av.respostas.count(), 2)
        self.assertEqual((av.pontuacao_ano, av.resultado), (99.5, "Excelente"))

    def test_mesma_data_e_nota_atualiza_incluindo_campos(self):
        self.post_nova(marcadas=[self.pp, self.pa])
        self.post_nova(marcadas=[], observacao="revisado")
        self.assertEqual(AvaliacaoFornecedor.objects.count(), 1)
        av = AvaliacaoFornecedor.objects.get()
        self.assertEqual(av.observacao, "revisado")
        self.assertEqual(av.pontuacao_ano, 99.0)

    def test_notas_diferentes_no_mesmo_dia_sao_registros_distintos(self):
        self.post_nova(nota_fiscal="NF1")
        self.post_nova(nota_fiscal="NF2")
        self.assertEqual(AvaliacaoFornecedor.objects.count(), 2)

    def test_edicao_nao_converte_selecao(self):
        av = AvaliacaoFornecedor.objects.create(fornecedor=self.f, data=timezone.localdate(), tipo="SELECAO")
        r = self.client.get(self.url("avaliacao_edit", self.f.pk, av.pk))
        self.assertEqual(r.status_code, 404)

    def test_edicao_invalida_nao_quebra(self):
        self.post_nova()
        av = AvaliacaoFornecedor.objects.get()
        r = self.client.post(self.url("avaliacao_edit", self.f.pk, av.pk), {"data": "", "tipo_nota": "PRODUTO"})
        self.assertEqual(r.status_code, 200)

    def test_edicao_mantem_avaliador_original(self):
        outro = get_user_model().objects.create_superuser("outro", "o@o.com", "x")
        self.post_nova()
        av = AvaliacaoFornecedor.objects.get()
        self.client.force_login(outro)
        self.client.post(self.url("avaliacao_edit", self.f.pk, av.pk), {
            "data": av.data.isoformat(), "tipo_nota": "PRODUTO", "nota_fiscal": "NF1", "observacao": "",
        })
        av.refresh_from_db()
        self.assertEqual(av.avaliador, self.user)

    def test_lista_apenas_monitoramento(self):
        self.post_nova()
        AvaliacaoFornecedor.objects.create(fornecedor=self.f, data=timezone.localdate(), tipo="SELECAO")
        r = self.client.get(self.url("avaliacao_list", self.f.pk))
        self.assertEqual(len(r.context["avaliacoes_info"]), 1)

    def test_remocao_exige_permissao_de_edicao(self):
        from django.contrib.auth.models import Permission
        self.post_nova()
        av = AvaliacaoFornecedor.objects.get()
        leitor = get_user_model().objects.create_user("leitor", password="x")
        leitor.user_permissions.add(Permission.objects.get(codename="nav_fornecedores_avaliacoes", content_type__app_label="core"))
        self.client.force_login(leitor)
        self.client.post(self.url("avaliacao_list", self.f.pk), {"delete_id": av.pk})
        self.assertTrue(AvaliacaoFornecedor.objects.filter(pk=av.pk).exists())

        editor = get_user_model().objects.create_user("editor", password="x")
        for c in ("nav_fornecedores_avaliacoes", "nav_fornecedores_avaliacao_edit"):
            editor.user_permissions.add(Permission.objects.get(codename=c, content_type__app_label="core"))
        self.client.force_login(editor)
        self.client.post(self.url("avaliacao_list", self.f.pk), {"delete_id": av.pk})
        self.assertFalse(AvaliacaoFornecedor.objects.filter(pk=av.pk).exists())

    def test_pontuacao_anual_unica_na_lista_e_detalhe(self):
        # 2 ocorrências neste ano + 1 em ano anterior (não conta)
        self.post_nova()
        antigo = AvaliacaoFornecedor.objects.create(
            fornecedor=self.f, data=timezone.localdate().replace(year=timezone.localdate().year - 1), tipo="MONITORAMENTO"
        )
        RespostaAvaliacao.objects.create(avaliacao=antigo, pergunta=self.pp, resposta=False)
        ano = timezone.localdate().year
        self.assertEqual(services.pontuacoes_monitoramento_por_fornecedor(ano), {self.f.pk: 99.0})
        r = self.client.get(self.url("fornecedor_detail", self.f.pk))
        self.assertEqual(r.context["pontuacao_geral"], 99.0)
        lista = self.client.get(self.url("fornecedor_list")).context["fornecedores"]
        self.assertEqual(lista[0].pontuacao_monitoramento, 99.0)

    def test_pontuacao_nunca_negativa(self):
        self.assertEqual(services.pontuacao_monitoramento(1000), 0.0)

    def test_xss_escapado_no_template(self):
        r = self.client.get(self.url("avaliacao_create", self.f.pk))
        self.assertContains(r, "function esc(")

    def test_matriz_nao_polui_monitoramento(self):
        r = self.client.post(self.url("avaliacao_matriz_create", self.f.pk), {
            "data": timezone.localdate().isoformat(), "produtos": "P1\nP2", "servicos": "S1",
            "matriz_PRODUTO_A": "on", "observacao": "geral",
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(RespostaMatrizAvaliacao.objects.count(), 8)
        self.assertEqual(len(self.client.get(self.url("avaliacao_list", self.f.pk)).context["avaliacoes_info"]), 0)
        self.assertEqual(services.pontuacoes_monitoramento_por_fornecedor(timezone.localdate().year), {})
        det = self.client.get(self.url("fornecedor_detail", self.f.pk))
        self.assertEqual(det.context["matriz_produtos"], ["P1", "P2"])
        self.assertTrue(det.context["matriz_respostas"]["PRODUTO_A"])

    def test_matriz_data_invalida(self):
        r = self.client.post(self.url("avaliacao_matriz_create", self.f.pk), {"data": "31/02/2025"})
        self.assertEqual(r.status_code, 200)


class ExportTests(BaseTest):
    def test_export_sem_registros_e_nome_seguro(self):
        f = Fornecedor.objects.create(empresa='Ação "Ltda"\r\nX', nome_fantasia="n", endereco="x", uf="BA")
        r = self.client.get(self.url("export_avaliacoes_excel", f.pk))
        self.assertEqual(r.status_code, 200)
        self.assertIn("avaliacoes_acao-ltda-x.xlsx", r["Content-Disposition"])

    def test_export_com_avaliacao_sem_avaliador(self):
        p = PerguntaAvaliacao.objects.create(texto="q", tipo="SELECAO")
        av = AvaliacaoFornecedor.objects.create(fornecedor=self.f, data=timezone.localdate(), tipo="SELECAO")
        RespostaAvaliacao.objects.create(avaliacao=av, pergunta=p, resposta=True)
        self.assertEqual(self.client.get(self.url("export_avaliacoes_excel", self.f.pk)).status_code, 200)


class DocumentoViewTests(BaseTest):
    def test_remover_documento_apaga_arquivo(self):
        cat = CategoriaDocumento.objects.create(nome="c")
        doc = DocumentoFornecedor.objects.create(
            fornecedor=self.f, categoria=cat, arquivo=SimpleUploadedFile("t.pdf", b"x")
        )
        caminho = doc.arquivo.path
        import os
        self.assertTrue(os.path.exists(caminho))
        self.client.post(self.url("documento_delete", self.f.pk, doc.pk))
        self.assertFalse(os.path.exists(caminho))


class BotoesPorPermissaoTests(BaseTest):
    """As tags can_nav_view ficavam fora do {% block %} (ignoradas pelo Django): nenhum botão protegido aparecia."""

    def test_botoes_de_acao_aparecem_para_administrador(self):
        cat = CategoriaDocumento.objects.create(nome="AFE")
        DocumentoFornecedor.objects.create(fornecedor=self.f, categoria=cat, arquivo="x.pdf")
        PerguntaAvaliacao.objects.create(texto="q", tipo="SELECAO")
        casos = [
            ("fornecedor_list", [], ["Novo Fornecedor", "Editar"]),
            ("fornecedor_detail", [self.f.pk], ["Editar", "Novo Documento", "Remover", "Responder Avaliação", "Matriz"]),
            ("pergunta_list", [], ["Nova Pergunta", "Editar", "Remover"]),
        ]
        for nome, args, esperados in casos:
            html = self.client.get(self.url(nome, *args)).content.decode()
            for texto in esperados:
                self.assertIn(texto, html, f"'{texto}' ausente em {nome}")

    def test_usuario_sem_permissao_nao_ve_botoes_de_edicao(self):
        from django.contrib.auth.models import Permission
        leitor = get_user_model().objects.create_user("leitor2", password="x")
        leitor.user_permissions.add(Permission.objects.get(codename="nav_fornecedores_lista", content_type__app_label="core"))
        self.client.force_login(leitor)
        html = self.client.get(self.url("fornecedor_detail", self.f.pk)).content.decode()
        self.assertNotIn("Novo Documento", html)
        self.assertNotIn(">Editar<", html)
