import base64
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from auditoria.models import (
    AgendaAuditoriaIso,
    AuditoriaIso,
    BancoPergunta,
    EvidenciaPlanoAcaoIso,
    ImagemSolicitacaoIso,
    Norma,
    PlanoAcaoMagicLink,
    RespostaEntrevistaIso,
    SolicitacaoEvidenciaIso,
)

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


class ArquivosEvidenciaTests(TestCase):
    """Fotos e anexos saem por endpoint com cache, não mais embutidos em base64 na página."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="auditor_arq", password="senha-forte-123")
        norma = Norma.objects.create(codigo="TESTE-ARQUIVOS")  # ISO 13485 já vem da migração de dados
        self.auditoria = AuditoriaIso.objects.create(norma=norma, data_inicio=date(2026, 9, 1), data_fim=date(2026, 9, 2))
        pergunta = BancoPergunta.objects.create(texto_pergunta="Processos controlados?")
        resposta = RespostaEntrevistaIso.objects.create(auditoria=self.auditoria, pergunta=pergunta)
        self.solicitacao = SolicitacaoEvidenciaIso.objects.create(resposta=resposta, solicitacao="OP-001", conclusao="NC")
        self.imagem = ImagemSolicitacaoIso.objects.create(
            solicitacao=self.solicitacao,
            arquivo_base64="data:image/png;base64," + base64.b64encode(PNG_1PX).decode(),
            nome_arquivo="op.png",
        )
        self.link = PlanoAcaoMagicLink.objects.create(auditoria=self.auditoria)

    def test_imagem_servida_com_cache(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.imagem.url_servida)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, PNG_1PX)
        self.assertEqual(resp["Content-Type"], "image/png")
        self.assertIn("immutable", resp["Cache-Control"])
        self.assertIn("private", resp["Cache-Control"])

    def test_imagem_exige_login(self):
        resp = self.client.get(self.imagem.url_servida)
        self.assertEqual(resp.status_code, 302)

    def test_evidencia_html_vai_como_download(self):
        self.client.force_login(self.user)
        ev = EvidenciaPlanoAcaoIso.objects.create(
            solicitacao=self.solicitacao,
            arquivo_base64=base64.b64encode(b"<script>alert(1)</script>").decode(),
            nome_arquivo="x.html",
            tipo_arquivo="text/html",
        )
        resp = self.client.get(ev.url_servida)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/octet-stream")
        self.assertTrue(resp["Content-Disposition"].startswith("attachment"))

    def test_portal_publico_com_token_valido(self):
        resp = self.client.get(self.imagem.url_publica(self.link.token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, PNG_1PX)

    def test_portal_publico_recusa_link_revogado_ou_fora_do_escopo(self):
        self.link.ativo = False
        self.link.save()
        self.assertEqual(self.client.get(self.imagem.url_publica(self.link.token)).status_code, 404)

        outro_link = PlanoAcaoMagicLink.objects.create(auditoria=self.auditoria)
        self.solicitacao.conclusao = "C"  # item conforme não aparece no portal
        self.solicitacao.save()
        self.assertEqual(self.client.get(self.imagem.url_publica(outro_link.token)).status_code, 404)

        self.assertEqual(self.client.get(self.imagem.url_publica("token-inexistente")).status_code, 404)

    def test_telas_internas_nao_embutem_base64(self):
        self.client.force_login(self.user)
        ev = EvidenciaPlanoAcaoIso.objects.create(
            solicitacao=self.solicitacao, arquivo_base64=base64.b64encode(b"%PDF-1.4").decode(),
            nome_arquivo="acao.pdf", tipo_arquivo="application/pdf",
        )
        self.solicitacao.capa_causa_raiz = "Falha de treinamento"  # painel só lista anexos após resposta do gestor
        self.solicitacao.save()
        agenda = AgendaAuditoriaIso.objects.create(auditoria=self.auditoria, titulo="Produção")
        for nome, query, urls_esperadas in (
            ("iso_entrevista_view", f"?agenda_id={agenda.id}", []),  # a tela sempre é aberta por bloco
            ("iso_matriz_view", "", []),
            ("iso_auditoria_cronograma", "", [self.imagem.url_servida]),
            ("iso_auditoria_capa", "", [ev.url_servida]),
        ):
            with self.subTest(tela=nome):
                resp = self.client.get(reverse(f"auditoria:{nome}", args=[self.auditoria.id]) + query)
                self.assertEqual(resp.status_code, 200)
                html = resp.content.decode()
                self.assertNotIn("base64,", html)
                for url in urls_esperadas:
                    self.assertIn(url, html)

    def test_portal_publico_renderiza_urls_de_endpoint(self):
        resp = self.client.get(reverse("auditoria:capa_portal_publico", args=[self.link.token]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn(self.imagem.url_publica(self.link.token), html)
        self.assertNotIn("base64,", html)
