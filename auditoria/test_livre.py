import json
from datetime import date
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import AuditoriaLivre, SolicitacaoLivre


class AuditoriaLivreTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("aud", "aud@example.com", "x")
        self.client.force_login(self.user)
        self.aud = AuditoriaLivre.objects.create(
            titulo="Recebimento", objetivo="Verificar insumos", data_inicio=date(2026, 11, 20)
        )

    def _post_json(self, url, payload):
        return self.client.post(url, json.dumps(payload), content_type="application/json")

    def test_requires_login(self):
        self.client.logout()
        r = self.client.get(reverse("auditoria:livre_list"))
        self.assertEqual(r.status_code, 302)

    def test_create_validates_and_redirects_to_execution(self):
        url = reverse("auditoria:livre_create")
        r = self.client.post(url, {"titulo": "", "data_inicio": "2026-11-23"})
        self.assertEqual(r.status_code, 200)
        r = self.client.post(url, {"titulo": "X", "data_inicio": "2026-11-23", "data_fim": "2026-11-01"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(AuditoriaLivre.objects.count(), 1)
        r = self.client.post(url, {
            "titulo": "Nova", "data_inicio": "2026-11-23", "auditores": [str(self.user.pk)],
        })
        nova = AuditoriaLivre.objects.get(titulo="Nova")
        self.assertRedirects(r, reverse("auditoria:livre_execucao", args=[nova.pk]))
        self.assertEqual(list(nova.auditores.all()), [self.user])
        self.assertEqual(nova.criado_por, self.user)

    def test_execucao_starts_audit_and_renders(self):
        r = self.client.get(reverse("auditoria:livre_execucao", args=[self.aud.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Solicitar evidência")
        self.aud.refresh_from_db()
        self.assertEqual(self.aud.status, "EM_ANDAMENTO")

    def test_solicitacao_lifecycle(self):
        r = self._post_json(reverse("auditoria:api_livre_sol_create", args=[self.aud.pk]),
                            {"solicitacao": " Registro de calibração ", "topico": "Metrologia"})
        self.assertEqual(r.status_code, 200)
        sol = SolicitacaoLivre.objects.get()
        self.assertEqual(sol.solicitacao, "Registro de calibração")
        self.assertEqual(sol.conclusao, "P")
        self.assertEqual(r.json()["resumo"]["P"], 1)

        upd = reverse("auditoria:api_livre_sol_update", args=[sol.pk])
        r = self._post_json(upd, {"conclusao": "NC", "grau_nc": "MAIOR", "evidencia": "Vencido"})
        self.assertEqual(r.json()["solicitacao"]["grau_nc"], "MAIOR")
        self.assertEqual(r.json()["resumo"]["NC"], 1)

        # grau só vale para NC
        self._post_json(upd, {"conclusao": "OM"})
        sol.refresh_from_db()
        self.assertEqual(sol.conclusao, "OM")
        self.assertIsNone(sol.grau_nc)

        r = self._post_json(reverse("auditoria:api_livre_sol_delete", args=[sol.pk]), {})
        self.assertEqual(r.json()["resumo"]["total"], 0)

    def test_api_rejects_bad_input(self):
        create = reverse("auditoria:api_livre_sol_create", args=[self.aud.pk])
        self.assertEqual(self._post_json(create, {"solicitacao": "  "}).status_code, 400)
        self.assertEqual(self._post_json(create, {}).status_code, 400)
        sol = SolicitacaoLivre.objects.create(auditoria=self.aud, solicitacao="a")
        upd = reverse("auditoria:api_livre_sol_update", args=[sol.pk])
        self.assertEqual(self._post_json(upd, {"conclusao": "XX"}).status_code, 400)
        self.assertEqual(self._post_json(upd, {"solicitacao": ""}).status_code, 400)
        self.assertEqual(self.client.post(create, "[1]", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.get(create).status_code, 405)

    def test_conclude_reopen_archive_delete(self):
        SolicitacaoLivre.objects.create(auditoria=self.aud, solicitacao="a")
        self.client.post(reverse("auditoria:livre_toggle_conclusao", args=[self.aud.pk]))
        self.aud.refresh_from_db()
        self.assertEqual(self.aud.status, "CONCLUIDA")
        self.assertIsNotNone(self.aud.data_fim)
        self.client.post(reverse("auditoria:livre_toggle_conclusao", args=[self.aud.pk]))
        self.aud.refresh_from_db()
        self.assertEqual(self.aud.status, "EM_ANDAMENTO")

        # exclusão exige arquivada
        self.client.post(reverse("auditoria:livre_delete", args=[self.aud.pk]))
        self.assertTrue(AuditoriaLivre.objects.exists())
        self.client.post(reverse("auditoria:livre_arquivar", args=[self.aud.pk]),
                         {"next": "https://evil.example.com/"})
        self.aud.refresh_from_db()
        self.assertTrue(self.aud.arquivada)
        self.assertEqual(len(self.client.get(reverse("auditoria:livre_list")).context["auditorias"]), 0)
        self.assertEqual(len(self.client.get(reverse("auditoria:livre_list") + "?arquivadas=1").context["auditorias"]), 1)
        self.client.post(reverse("auditoria:livre_delete", args=[self.aud.pk]))
        self.assertFalse(AuditoriaLivre.objects.exists())
        self.assertFalse(SolicitacaoLivre.objects.exists())

    def test_save_conclusion_text(self):
        self._post_json(reverse("auditoria:api_livre_conclusao_salvar", args=[self.aud.pk]),
                        {"conclusao_texto": "Aprovado com ressalvas"})
        self.aud.refresh_from_db()
        self.assertEqual(self.aud.conclusao_texto, "Aprovado com ressalvas")

    def test_export_excel(self):
        from openpyxl import load_workbook
        SolicitacaoLivre.objects.create(auditoria=self.aud, solicitacao="Doc A", conclusao="C", topico="T1")
        SolicitacaoLivre.objects.create(auditoria=self.aud, solicitacao="Doc B", conclusao="NC", grau_nc="MENOR")
        r = self.client.get(reverse("auditoria:livre_export_excel", args=[self.aud.pk]))
        self.assertEqual(r.status_code, 200)
        wb = load_workbook(BytesIO(r.content))
        self.assertEqual(wb.sheetnames, ["Resumo", "Evidências"])
        linhas = list(wb["Evidências"].iter_rows(values_only=True))
        self.assertEqual(len(linhas), 3)
        self.assertEqual(linhas[2][5:7], ("Não Conformidade", "NC Menor"))

    def test_navigation_permission_mapping(self):
        from shared.permissions import VIEW_NAME_TO_PERMISSION
        for nome in ("livre_list", "livre_execucao", "api_livre_sol_update", "livre_export_excel"):
            self.assertTrue(VIEW_NAME_TO_PERMISSION[f"auditoria:{nome}"]["perm"].startswith("core.nav_auditoria_livre_"))


class AuditoriaLivreFotosTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("aud2", "aud2@example.com", "x")
        self.client.force_login(self.user)
        aud = AuditoriaLivre.objects.create(titulo="Fotos", data_inicio=date(2026, 11, 20))
        self.sol = SolicitacaoLivre.objects.create(auditoria=aud, solicitacao="Foto do local")
        self.url = reverse("auditoria:api_livre_imagem_upload", args=[self.sol.pk])

    def _img(self, nome="foto.png", size=(3000, 2000), fmt="PNG", mode="RGB"):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        buf = BytesIO()
        Image.new(mode, size, (200, 30, 30) + ((255,) if mode == "RGBA" else ())).save(buf, format=fmt)
        return SimpleUploadedFile(nome, buf.getvalue(), content_type=f"image/{fmt.lower()}")

    def test_upload_resizes_to_jpeg_and_serves(self):
        from PIL import Image
        r = self.client.post(self.url, {"imagem": [self._img(), self._img("b.png", mode="RGBA")], "legenda": "Entrada"})
        self.assertEqual(r.status_code, 200, r.content)
        imgs = r.json()["imagens"]
        self.assertEqual(len(imgs), 2)
        self.assertEqual(imgs[0]["nome"], "foto.jpg")
        self.assertEqual(self.sol.imagens.count(), 2)
        r = self.client.get(imgs[0]["url"])
        self.assertEqual(r["Content-Type"], "image/jpeg")
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        im = Image.open(BytesIO(r.content))
        self.assertEqual(max(im.size), 1920)

    def test_rejects_non_images_and_empty(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        falso = SimpleUploadedFile("x.png", b"<script>alert(1)</script>", content_type="image/png")
        self.assertEqual(self.client.post(self.url, {"imagem": falso}).status_code, 400)
        self.assertEqual(self.client.post(self.url, {}).status_code, 400)
        self.assertEqual(self.sol.imagens.count(), 0)

    def test_limit_per_evidence(self):
        from .views_livre import MAX_FOTOS_POR_SOLICITACAO
        r = self.client.post(self.url, {"imagem": [self._img(size=(50, 50)) for _ in range(MAX_FOTOS_POR_SOLICITACAO + 2)]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.sol.imagens.count(), MAX_FOTOS_POR_SOLICITACAO)
        self.assertTrue(r.json()["avisos"])
        self.assertEqual(self.client.post(self.url, {"imagem": self._img(size=(50, 50))}).status_code, 400)

    def test_caption_delete_and_page_payload(self):
        img_id = self.client.post(self.url, {"imagem": self._img(size=(50, 50))}).json()["imagens"][0]["id"]
        self._post = lambda u, d: self.client.post(u, json.dumps(d), content_type="application/json")
        self._post(reverse("auditoria:api_livre_imagem_legenda", args=[img_id]), {"legenda": "Piso"})
        r = self.client.get(reverse("auditoria:livre_execucao", args=[self.sol.auditoria_id]))
        self.assertEqual(r.context["grupos_json"][0]["itens"][0]["imagens"][0]["legenda"], "Piso")
        self.client.post(reverse("auditoria:api_livre_imagem_delete", args=[img_id]))
        self.assertEqual(self.sol.imagens.count(), 0)
        self.assertEqual(self.client.get(reverse("auditoria:livre_imagem_arquivo", args=[img_id])).status_code, 404)

    def test_requires_login_and_cascade(self):
        self.client.post(self.url, {"imagem": self._img(size=(50, 50))})
        self.client.logout()
        self.assertEqual(self.client.post(self.url, {"imagem": self._img(size=(50, 50))}).status_code, 302)
        self.sol.delete()
        from .models import ImagemSolicitacaoLivre
        self.assertEqual(ImagemSolicitacaoLivre.objects.count(), 0)

    def test_excel_has_photos_sheet(self):
        from openpyxl import load_workbook
        self.client.post(self.url, {"imagem": self._img(size=(400, 300)), "legenda": "Vista"})
        r = self.client.get(reverse("auditoria:livre_export_excel", args=[self.sol.auditoria_id]))
        wb = load_workbook(BytesIO(r.content))
        self.assertEqual(wb.sheetnames, ["Resumo", "Evidências", "Fotos"])
        self.assertEqual(wb["Evidências"]["I2"].value, 1)
        self.assertEqual(len(wb["Fotos"]._images), 1)


class AuditoriaLivreWordTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("aud3", "aud3@example.com", "x")
        self.client.force_login(self.user)
        self.aud = AuditoriaLivre.objects.create(
            titulo="Auditoria de Recebimento", objetivo="Verificar insumos", escopo="Doca 1",
            data_inicio=date(2026, 11, 20), conclusao_texto="Aprovado com ressalvas", auditor_lider="Maria",
        )
        self.aud.auditores.add(self.user)
        mk = lambda **kw: SolicitacaoLivre.objects.create(auditoria=self.aud, **kw)
        mk(solicitacao="Registro de temperatura", conclusao="C", evidencia="Planilha OK")
        self.nc = mk(solicitacao="Calibração do termômetro", conclusao="NC", grau_nc="MAIOR",
                     evidencia="Vencida", observacao="Abrir ação", topico="Metrologia")
        mk(solicitacao="Sinalização", conclusao="OM")
        mk(solicitacao="Sem classificar")

    def _doc(self):
        from docx import Document
        r = self.client.get(reverse("auditoria:livre_export_docx", args=[self.aud.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertIn("wordprocessingml", r["Content-Type"])
        self.assertIn(".docx", r["Content-Disposition"])
        return Document(BytesIO(r.content))

    def _texto(self, doc):
        partes = [p.text for p in doc.paragraphs]
        for t in doc.tables:
            for row in t.rows:
                partes += [c.text for c in row.cells]
        return "\n".join(partes)

    def test_report_content_and_grouping(self):
        t = self._texto(self._doc())
        for esperado in ("Auditoria de Recebimento", "Verificar insumos", "Aprovado com ressalvas",
                         "Não Conformidades (1)", "Oportunidades de Melhoria (1)", "Conformidades (1)",
                         "Pendentes de classificação (1)", "Não Conformidade (NC Maior)",
                         "#2  ·  Metrologia", "Abrir ação", "Índice de conformidade: 33%"):
            self.assertIn(esperado, t)
        # NC aparece antes das conformidades
        self.assertLess(t.index("Calibração do termômetro"), t.index("Registro de temperatura"))

    def test_report_embeds_photos(self):
        import base64
        from PIL import Image
        from .models import ImagemSolicitacaoLivre
        buf = BytesIO()
        Image.new("RGB", (300, 200), (10, 90, 200)).save(buf, format="JPEG")
        ImagemSolicitacaoLivre.objects.create(
            solicitacao=self.nc, nome_arquivo="a.jpg", legenda="Etiqueta vencida",
            arquivo_base64=base64.b64encode(buf.getvalue()).decode(),
        )
        r = self.client.get(reverse("auditoria:livre_export_docx", args=[self.aud.pk]))
        import zipfile
        midia = [n for n in zipfile.ZipFile(BytesIO(r.content)).namelist() if n.startswith("word/media/")]
        self.assertEqual(len(midia), 1)
        from docx import Document
        self.assertIn("Etiqueta vencida", self._texto(Document(BytesIO(r.content))))

    def test_empty_audit_and_login(self):
        from .models import AuditoriaLivre as A
        vazia = A.objects.create(titulo="Vazia", data_inicio=date(2026, 11, 1))
        r = self.client.get(reverse("auditoria:livre_export_docx", args=[vazia.pk]))
        self.assertEqual(r.status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("auditoria:livre_export_docx", args=[vazia.pk])).status_code, 302)


class AuditoriaLivreCapaTests(TestCase):
    def setUp(self):
        from django.test import Client
        self.user = get_user_model().objects.create_superuser("aud4", "aud4@example.com", "x")
        self.client.force_login(self.user)
        self.publico = Client()  # visitante sem login (o auditado)
        self.aud = AuditoriaLivre.objects.create(titulo="Auditoria CAPA", data_inicio=date(2026, 11, 20))
        mk = lambda **kw: SolicitacaoLivre.objects.create(auditoria=self.aud, **kw)
        self.nc = mk(solicitacao="Calibração vencida", conclusao="NC", grau_nc="MAIOR", topico="Metrologia", ordem=1)
        self.nc2 = mk(solicitacao="Sem registro", conclusao="NC", topico="Produção", ordem=2)
        self.om = mk(solicitacao="Sinalização", conclusao="OM", topico="Metrologia", ordem=3)
        self.ok = mk(solicitacao="Tudo certo", conclusao="C", ordem=4)
        self.link = self._link()
        outra = AuditoriaLivre.objects.create(titulo="Outra", data_inicio=date(2026, 11, 1))
        self.alheia = SolicitacaoLivre.objects.create(auditoria=outra, solicitacao="x", conclusao="NC")

    def _link(self, **kw):
        from .models import CapaLinkLivre
        return CapaLinkLivre.objects.create(auditoria=self.aud, **kw)

    def _resp(self, sol, token=None, **extra):
        dados = {"solicitacao_id": sol.pk, "causa_raiz": "Falta de rotina", "acao_corretiva": "Criar agenda",
                 "responsavel": "João", "prazo": "2026-12-31", "respondente": "João Silva", "enviar": "true"}
        dados.update(extra)
        return self.publico.post(
            reverse("auditoria:api_livre_capa_responder_publico", args=[token or self.link.token]), dados)

    # ---- auditor
    def test_panel_and_link_generation(self):
        r = self.client.get(reverse("auditoria:livre_capa", args=[self.aud.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["resumo"]["total"], 3)  # NC, NC e OM
        self.assertEqual([i["numero"] for i in r.context["itens"]], [1, 2, 3])
        url = reverse("auditoria:api_livre_capa_gerar_link", args=[self.aud.pk])
        j = self.client.post(url, json.dumps({"dias_validade": 9999, "incluir_om": True, "topico": "Metrologia"}),
                             content_type="application/json").json()
        self.assertTrue(j["success"])
        from .models import CapaLinkLivre
        novo = CapaLinkLivre.objects.exclude(pk=self.link.pk).get()
        self.assertEqual(novo.dias_validade, 90)
        self.assertTrue(novo.incluir_om and novo.topico == "Metrologia")
        self.assertIn(novo.token, j["url"])
        self.client.post(reverse("auditoria:api_livre_capa_revogar_link", args=[novo.pk]))
        novo.refresh_from_db()
        self.assertFalse(novo.ativo)

    def test_auditor_endpoints_require_login(self):
        self.client.logout()
        for nome, args in (("livre_capa", [self.aud.pk]), ("api_livre_capa_gerar_link", [self.aud.pk]),
                           ("api_livre_capa_salvar", [self.nc.pk]), ("api_livre_capa_revisar", [self.nc.pk])):
            self.assertEqual(self.client.post(reverse(f"auditoria:{nome}", args=args)).status_code, 302, nome)

    # ---- portal público: acesso e escopo
    def test_portal_access_rules(self):
        url = reverse("auditoria:livre_capa_portal", args=[self.link.token])
        r = self.publico.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual([i["id"] for i in r.context["itens"]], [self.nc.pk, self.nc2.pk])  # sem OM, sem C
        self.assertEqual(r["Cache-Control"], "no-store")
        self.assertEqual(r["Referrer-Policy"], "no-referrer")
        self.assertEqual(self.publico.get(reverse("auditoria:livre_capa_portal", args=["inexistente"])).status_code, 404)
        self.link.ativo = False
        self.link.save()
        self.assertEqual(self.publico.get(url).status_code, 404)
        from django.utils import timezone
        exp = self._link(expira_em=timezone.now() - timezone.timedelta(days=1))
        self.assertEqual(self.publico.get(reverse("auditoria:livre_capa_portal", args=[exp.token])).status_code, 403)

    def test_portal_scope_topic_and_om(self):
        l = self._link(topico="Metrologia", incluir_om=True)
        itens = self.publico.get(reverse("auditoria:livre_capa_portal", args=[l.token])).context["itens"]
        self.assertEqual({i["id"] for i in itens}, {self.nc.pk, self.om.pk})
        self.assertEqual(self._resp(self.nc2, token=l.token).status_code, 404)   # outro tópico
        self.assertEqual(self._resp(self.om, token=self.link.token).status_code, 404)  # OM fora do escopo
        self.assertEqual(self._resp(self.alheia).status_code, 404)  # outra auditoria
        self.assertEqual(self._resp(self.ok).status_code, 404)  # conforme
        self.assertEqual(self.publico.post(reverse("auditoria:api_livre_capa_responder_publico", args=[self.link.token]),
                                           {"solicitacao_id": "abc"}).status_code, 404)

    # ---- portal público: resposta
    def test_respond_flow(self):
        r = self._resp(self.nc, enviar="false", acao_corretiva="")
        self.assertEqual(r.json()["status"], "PENDENTE")  # rascunho
        self.assertEqual(self._resp(self.nc, causa_raiz="").status_code, 400)  # envio incompleto
        self.assertEqual(self._resp(self.nc, prazo="31/12").status_code, 400)  # prazo inválido
        r = self._resp(self.nc)
        self.assertEqual(r.json()["status"], "AGUARDANDO_REVISAO")
        self.nc.refresh_from_db()
        self.assertEqual((self.nc.capa_respondido_por_nome, self.nc.capa_prazo), ("João Silva", date(2026, 12, 31)))
        self.assertIsNotNone(self.nc.capa_respondido_em)
        self.assertEqual(self._resp(self.nc, causa_raiz="mudei").status_code, 400)  # travado em revisão
        self.nc.refresh_from_db()
        self.assertEqual(self.nc.capa_causa_raiz, "Falta de rotina")

    def test_attachments_validation_and_serving(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import EvidenciaPlanoAcaoLivre
        bom = SimpleUploadedFile("laudo.pdf", b"%PDF-1.4 x", content_type="application/pdf")
        txt = SimpleUploadedFile("nota.txt", b"<script>alert(1)</script>", content_type="text/plain")
        exe = SimpleUploadedFile("virus.exe", b"MZ", content_type="application/octet-stream")
        html = SimpleUploadedFile("x.html", b"<b>x</b>", content_type="text/html")
        r = self.publico.post(reverse("auditoria:api_livre_capa_responder_publico", args=[self.link.token]), {
            "solicitacao_id": self.nc.pk, "enviar": "false", "anexos": [bom, txt, exe, html]})
        j = r.json()
        self.assertEqual([a["nome"] for a in j["anexos"]], ["laudo.pdf", "nota.txt"])
        self.assertEqual(len(j["avisos"]), 2)
        self.assertEqual(EvidenciaPlanoAcaoLivre.objects.count(), 2)
        pdf, nota = EvidenciaPlanoAcaoLivre.objects.order_by("id")
        r = self.publico.get(reverse("auditoria:livre_capa_anexo_publico", args=[self.link.token, pdf.pk]))
        self.assertEqual((r["Content-Type"], r["X-Content-Type-Options"]), ("application/pdf", "nosniff"))
        r = self.publico.get(reverse("auditoria:livre_capa_anexo_publico", args=[self.link.token, nota.pk]))
        self.assertEqual(r["Content-Type"], "application/octet-stream")  # texto nunca é exibido inline
        self.assertIn("attachment", r["Content-Disposition"])
        # outro link (outro escopo) e visitante sem token válido não acessam
        l2 = self._link(topico="Produção")
        self.assertEqual(self.publico.get(reverse("auditoria:livre_capa_anexo_publico", args=[l2.token, pdf.pk])).status_code, 404)
        self.assertEqual(self.publico.get(reverse("auditoria:livre_capa_anexo_publico", args=["x", pdf.pk])).status_code, 404)
        self.assertEqual(self.publico.get(reverse("auditoria:livre_capa_anexo", args=[pdf.pk])).status_code, 302)
        self.assertEqual(self.client.get(reverse("auditoria:livre_capa_anexo", args=[pdf.pk])).status_code, 200)
        # remoção: só em plano editável e dentro do escopo
        rm = lambda tok, ev: self.publico.post(reverse("auditoria:api_livre_capa_remover_anexo_publico", args=[tok, ev.pk]))
        self.assertEqual(rm(l2.token, nota).status_code, 404)
        self.assertEqual(rm(self.link.token, nota).status_code, 200)
        self.nc.capa_status = "AGUARDANDO_REVISAO"
        self.nc.save()
        self.assertEqual(rm(self.link.token, pdf).status_code, 400)

    def test_attachment_limits(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .views_livre_capa import MAX_ANEXOS_POR_ITEM, MAX_BYTES_ANEXO
        grande = SimpleUploadedFile("g.pdf", b"0" * (MAX_BYTES_ANEXO + 1))
        pequenos = [SimpleUploadedFile(f"{n}.txt", b"a") for n in range(MAX_ANEXOS_POR_ITEM + 2)]
        r = self.publico.post(reverse("auditoria:api_livre_capa_responder_publico", args=[self.link.token]), {
            "solicitacao_id": self.nc.pk, "enviar": "false", "anexos": [grande] + pequenos})
        self.assertEqual(len(r.json()["anexos"]), MAX_ANEXOS_POR_ITEM)
        self.assertEqual(self.nc.evidencias_capa.count(), MAX_ANEXOS_POR_ITEM)

    # ---- revisão pelo auditor
    def test_review_flow(self):
        rev = lambda sol, **d: self.client.post(reverse("auditoria:api_livre_capa_revisar", args=[sol.pk]),
                                                json.dumps(d), content_type="application/json")
        self.assertEqual(rev(self.nc, status="APROVADO").status_code, 400)  # sem plano enviado
        self._resp(self.nc)
        self.assertEqual(rev(self.nc, status="REJEITADO").status_code, 400)  # exige parecer
        self.assertEqual(rev(self.nc, status="XX").status_code, 400)
        self.assertEqual(rev(self.nc, status="REJEITADO", parecer="Causa rasa").status_code, 200)
        self.nc.refresh_from_db()
        self.assertEqual((self.nc.capa_status, self.nc.capa_parecer_auditor), ("REJEITADO", "Causa rasa"))
        # o auditado edita depois da rejeição: rascunho volta a pendente; reenvio vai para revisão
        self.assertEqual(self._resp(self.nc, enviar="false").json()["status"], "PENDENTE")
        self.assertEqual(self._resp(self.nc).json()["status"], "AGUARDANDO_REVISAO")
        self.assertEqual(rev(self.nc, status="APROVADO", parecer="Ok").status_code, 200)
        self.nc.refresh_from_db()
        self.assertEqual(self.nc.capa_status, "APROVADO")
        self.assertEqual(self._resp(self.nc, causa_raiz="x").status_code, 400)  # aprovado não muda

    def test_auditor_registers_plan_directly(self):
        url = reverse("auditoria:api_livre_capa_salvar", args=[self.nc.pk])
        post = lambda d: self.client.post(url, json.dumps(d), content_type="application/json")
        self.assertEqual(post({"causa_raiz": "a", "enviar": True}).status_code, 400)
        j = post({"causa_raiz": "a", "acao_corretiva": "b", "responsavel": "c", "prazo": "2026-12-01", "enviar": True}).json()
        self.assertEqual(j["status"], "AGUARDANDO_REVISAO")
        self.assertEqual(self.client.post(reverse("auditoria:api_livre_capa_salvar", args=[self.ok.pk]),
                                          "{}", content_type="application/json").status_code, 404)

    # ---- integração com execução, Excel e Word
    def test_execution_page_exports_and_cascade(self):
        from io import BytesIO
        from docx import Document
        from openpyxl import load_workbook
        self._resp(self.nc)
        r = self.client.get(reverse("auditoria:livre_execucao", args=[self.aud.pk]))
        self.assertContains(r, reverse("auditoria:livre_capa", args=[self.aud.pk]))
        self.assertEqual(r.context["grupos_json"][0]["itens"][0]["capa_status"], "AGUARDANDO_REVISAO")
        wb = load_workbook(BytesIO(self.client.get(reverse("auditoria:livre_export_excel", args=[self.aud.pk])).content))
        linha = [c.value for c in wb["Evidências"][2]]
        self.assertEqual(linha[9:12], ["Aguardando Revisão", "João", "31/12/2026"])
        self.assertFalse(wb["Evidências"]["J5"].value)  # conforme não tem plano
        doc = Document(BytesIO(self.client.get(reverse("auditoria:livre_export_docx", args=[self.aud.pk])).content))
        texto = "\n".join(c.text for t in doc.tables for row in t.rows for c in row.cells)
        for esperado in ("Falta de rotina", "Criar agenda", "31/12/2026", "Plano de ação — situação"):
            self.assertIn(esperado, texto)
        self.link.delete()
        self.aud.delete()
        from .models import EvidenciaPlanoAcaoLivre
        self.assertEqual(EvidenciaPlanoAcaoLivre.objects.count(), 0)

    def test_permission_mapping_covers_auditor_views_only(self):
        from shared.permissions import VIEW_NAME_TO_PERMISSION as M
        for nome in ("livre_capa", "api_livre_capa_salvar", "api_livre_capa_revisar", "livre_capa_anexo"):
            self.assertTrue(M[f"auditoria:{nome}"]["perm"].startswith("core.nav_auditoria_livre_"))
        for nome in ("livre_capa_portal", "api_livre_capa_responder_publico", "livre_capa_anexo_publico"):
            self.assertNotIn(f"auditoria:{nome}", M)  # públicas: validadas pelo token


class AuditoriaLivreEmailTests(TestCase):
    def setUp(self):
        from django.core import mail
        self.mail = mail
        self.user = get_user_model().objects.create_superuser(
            "aud5", "auditor@example.com", "x", first_name="Maria", last_name="Auditora")
        self.client.force_login(self.user)
        self.aud = AuditoriaLivre.objects.create(titulo="Auditoria <b>Final</b>", data_inicio=date(2026, 11, 20))
        self.nc = SolicitacaoLivre.objects.create(
            auditoria=self.aud, solicitacao="Calibração vencida", conclusao="NC", topico="Metrologia", ordem=1)
        self.gerar = reverse("auditoria:api_livre_capa_gerar_link", args=[self.aud.pk])

    def _post(self, url, dados):
        return self.client.post(url, json.dumps(dados), content_type="application/json")

    def _link(self, emails="aud@empresa.com", **kw):
        from .models import CapaLinkLivre
        return CapaLinkLivre.objects.create(auditoria=self.aud, emails_destino=emails, **kw)

    def _revisar(self, status="REJEITADO", parecer="Causa rasa", notificar=True):
        self.nc.capa_status = "AGUARDANDO_REVISAO"
        self.nc.save()
        return self._post(reverse("auditoria:api_livre_capa_revisar", args=[self.nc.pk]),
                          {"status": status, "parecer": parecer, "notificar": notificar})

    def test_parse_emails(self):
        from .services.notificacao_livre import parse_emails
        validos, invalidos = parse_emails("A@x.com; b@x.com\nb@x.com, <c@x.com> semarroba, d@")
        self.assertEqual(validos, ["a@x.com", "b@x.com", "c@x.com"])
        self.assertEqual(invalidos, ["semarroba", "d@"])
        self.assertEqual(parse_emails(None), ([], []))

    def test_generate_link_sends_email(self):
        j = self._post(self.gerar, {"emails": "um@empresa.com, dois@empresa.com", "mensagem": "Prazo curto <i>!</i>"}).json()
        self.assertEqual(j["email"], {"enviados": 2, "falhas": 0})
        self.assertEqual(len(self.mail.outbox), 2)
        m = self.mail.outbox[0]
        self.assertEqual(m.to, ["um@empresa.com"])  # um e-mail por pessoa: ninguém vê os outros
        self.assertEqual(m.reply_to, ["auditor@example.com"])
        self.assertIn(j["url"], m.body)
        self.assertIn("Maria Auditora", m.body)
        self.assertIn("Prazo curto", m.body)
        html = m.alternatives[0][0]
        self.assertIn(j["url"], html)
        self.assertNotIn("<b>Final</b>", html)       # título escapado
        self.assertNotIn("<i>!</i>", html)           # mensagem escapada
        from .models import CapaLinkLivre
        self.assertEqual(CapaLinkLivre.objects.get().lista_emails, ["um@empresa.com", "dois@empresa.com"])

    def test_generate_link_without_emails_sends_nothing(self):
        j = self._post(self.gerar, {}).json()
        self.assertTrue(j["success"])
        self.assertIsNone(j["email"])
        self.assertEqual(len(self.mail.outbox), 0)

    def test_generate_link_rejects_bad_emails_without_creating_link(self):
        from .models import CapaLinkLivre
        self.assertEqual(self._post(self.gerar, {"emails": "ok@x.com, invalido"}).status_code, 400)
        many = ",".join(f"p{n}@x.com" for n in range(21))
        self.assertEqual(self._post(self.gerar, {"emails": many}).status_code, 400)
        self.assertEqual(CapaLinkLivre.objects.count(), 0)
        self.assertEqual(len(self.mail.outbox), 0)

    def test_smtp_failure_does_not_break_the_action(self):
        from unittest.mock import patch
        from django.core.mail import EmailMultiAlternatives
        with patch.object(EmailMultiAlternatives, "send", side_effect=OSError("smtp fora")):
            j = self._post(self.gerar, {"emails": "um@empresa.com"}).json()
        self.assertTrue(j["success"])
        self.assertEqual(j["email"], {"enviados": 0, "falhas": 1})
        from .models import CapaLinkLivre
        self.assertEqual(CapaLinkLivre.objects.count(), 1)
        with patch.object(EmailMultiAlternatives, "send", side_effect=OSError("smtp fora")):
            self.assertEqual(self._revisar(notificar=True).status_code, 200)  # revisão grava mesmo assim
        self.nc.refresh_from_db()
        self.assertEqual(self.nc.capa_status, "REJEITADO")

    def test_header_injection_in_title_is_neutralized(self):
        self.aud.titulo = "Normal\nBcc: vitima@x.com"
        self.aud.save()
        self._post(self.gerar, {"emails": "um@empresa.com"})
        m = self.mail.outbox[0]
        self.assertNotIn("\n", m.subject)
        self.assertEqual(m.bcc, [])

    def test_resend_link(self):
        link = self._link(emails="velho@empresa.com")
        url = reverse("auditoria:api_livre_capa_enviar_link", args=[link.pk])
        self.assertEqual(self._post(url, {}).json()["email"], {"enviados": 1, "falhas": 0})  # usa os salvos
        self.assertEqual(self.mail.outbox[-1].to, ["velho@empresa.com"])
        self._post(url, {"emails": "novo@empresa.com"})
        link.refresh_from_db()
        self.assertEqual(link.lista_emails, ["novo@empresa.com"])
        self.assertEqual(self._post(url, {"emails": "ruim"}).status_code, 400)
        link.emails_destino = ""
        link.save()
        self.assertEqual(self._post(url, {}).status_code, 400)  # sem e-mails
        link.ativo = False
        link.save()
        self.assertEqual(self._post(url, {"emails": "a@x.com"}).status_code, 400)  # revogado
        self.client.logout()
        self.assertEqual(self.client.post(url).status_code, 302)

    def test_review_notifies_auditee(self):
        self._link(emails="aud@empresa.com")
        j = self._revisar("REJEITADO", "Causa rasa").json()
        self.assertEqual(j["email"], {"enviados": 1, "falhas": 0, "destinatarios": 1})
        m = self.mail.outbox[0]
        self.assertEqual(m.to, ["aud@empresa.com"])
        self.assertIn("Causa rasa", m.body)
        self.assertIn("/livre/capa/responder/", m.body)  # link para corrigir
        self.assertIn("Ajuste necessário", m.subject)
        self.mail.outbox.clear()
        j = self._revisar("APROVADO", "Ótimo").json()
        m = self.mail.outbox[0]
        self.assertIn("aprovado", m.subject.lower())
        self.assertIn("Ótimo", m.body)
        self.assertNotIn("/livre/capa/responder/", m.body)  # aprovado: nada mais a fazer

    def test_review_notification_scope_and_opt_out(self):
        from django.utils import timezone
        self._link(emails="a@empresa.com")
        self.assertIsNone(self._revisar(notificar=False).json()["email"])
        self.assertEqual(len(self.mail.outbox), 0)
        # fora do escopo: tópico diferente, link revogado, expirado, sem e-mails, OM sem incluir_om
        self._link(emails="topico@x.com", topico="Produção")
        self._link(emails="revogado@x.com", ativo=False)
        self._link(emails="expirado@x.com", expira_em=timezone.now() - timezone.timedelta(days=1))
        self._link(emails="")
        r = self._revisar().json()["email"]
        self.assertEqual({m.to[0] for m in self.mail.outbox}, {"a@empresa.com"})
        self.assertEqual(r["destinatarios"], 1)
        # OM só notifica se o link incluir OM
        self.mail.outbox.clear()
        self.nc.conclusao = "OM"
        self.nc.save()
        self._revisar()
        self.assertEqual(len(self.mail.outbox), 0)
        self._link(emails="om@empresa.com", incluir_om=True)
        self._revisar()
        self.assertEqual({m.to[0] for m in self.mail.outbox}, {"om@empresa.com"})

    def test_review_dedupes_recipients_across_links(self):
        self._link(emails="mesmo@empresa.com")
        self._link(emails="mesmo@empresa.com\noutro@empresa.com")
        self.assertEqual(self._revisar().json()["email"]["destinatarios"], 2)
        self.assertEqual(len(self.mail.outbox), 2)

    def test_panel_shows_recipients_and_permission_mapping(self):
        link = self._link(emails="aud@empresa.com")
        r = self.client.get(reverse("auditoria:livre_capa", args=[self.aud.pk]))
        self.assertContains(r, "aud@empresa.com")
        self.assertContains(r, f'class="btn btn-sm btn-outline-secondary rounded-pill btn-enviar" data-id="{link.pk}"')
        from shared.permissions import VIEW_NAME_TO_PERMISSION as M
        self.assertTrue(M["auditoria:api_livre_capa_enviar_link"]["perm"].startswith("core.nav_auditoria_livre_"))


class AuditoriaLivreItensTests(TestCase):
    """Uma solicitação com vários itens, cada um com a sua evidência e classificação."""

    def setUp(self):
        self.user = get_user_model().objects.create_superuser("aud6", "aud6@example.com", "x")
        self.client.force_login(self.user)
        self.aud = AuditoriaLivre.objects.create(titulo="Itens", data_inicio=date(2026, 11, 20))
        self.sol = SolicitacaoLivre.objects.create(
            auditoria=self.aud, solicitacao="Quais máquinas estão sinalizadas?", topico="Máquinas", ordem=1,
            evidencia="PRA 03", conclusao="C")
        self.outra = SolicitacaoLivre.objects.create(auditoria=self.aud, solicitacao="Outra", ordem=2)

    def _post(self, nome, pk, dados=None):
        return self.client.post(reverse(f"auditoria:{nome}", args=[pk]), json.dumps(dados or {}),
                                content_type="application/json")

    def _add_item(self, pk=None):
        return self._post("api_livre_item_create", pk or self.sol.pk).json()["item"]

    def test_add_item_copies_request_and_keeps_group_together(self):
        item = self._add_item()
        novo = SolicitacaoLivre.objects.get(pk=item["id"])
        self.assertEqual((novo.pai_id, novo.solicitacao, novo.topico, novo.ordem),
                         (self.sol.pk, "Quais máquinas estão sinalizadas?", "Máquinas", 1))
        self.assertEqual((novo.conclusao, novo.evidencia), ("P", ""))
        # adicionar a partir de um item extra também liga à original
        self.assertEqual(SolicitacaoLivre.objects.get(pk=self._add_item(novo.pk)["id"]).pai_id, self.sol.pk)
        # a numeração dos relatórios mantém os itens junto da solicitação: #1,#2,#3 e só depois a outra
        ordem = list(self.aud.solicitacoes.order_by("ordem", "id").values_list("solicitacao", flat=True))
        self.assertEqual(ordem, ["Quais máquinas estão sinalizadas?"] * 3 + ["Outra"])

    def test_each_item_has_its_own_classification_and_counts_separately(self):
        a, b = self._add_item(), self._add_item()
        self._post("api_livre_sol_update", a["id"], {"evidencia": "VFTOrbit 03", "conclusao": "OM"})
        r = self._post("api_livre_sol_update", b["id"], {"evidencia": "DLP 04", "conclusao": "NC", "grau_nc": "MAIOR"})
        self.assertEqual(r.json()["resumo"], {"P": 1, "C": 1, "NC": 1, "OM": 1, "NA": 0, "total": 4})
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.conclusao, "C")  # o item original não muda

    def test_request_text_and_topic_are_shared_by_all_items(self):
        a = self._add_item()
        self._post("api_livre_sol_update", a["id"], {"solicitacao": "Texto novo", "topico": "Linha 2"})
        for s in SolicitacaoLivre.objects.filter(pk__in=[self.sol.pk, a["id"]]):
            self.assertEqual((s.solicitacao, s.topico), ("Texto novo", "Linha 2"))
        self.outra.refresh_from_db()
        self.assertEqual(self.outra.solicitacao, "Outra")  # outras solicitações não são afetadas
        # editar só a evidência de um item não mexe nos demais
        self._post("api_livre_sol_update", a["id"], {"evidencia": "só deste"})
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.evidencia, "PRA 03")

    def test_page_groups_items_by_request(self):
        a = self._add_item()
        grupos = self.client.get(reverse("auditoria:livre_execucao", args=[self.aud.pk])).context["grupos_json"]
        self.assertEqual(len(grupos), 2)
        self.assertEqual([i["id"] for i in grupos[0]["itens"]], [self.sol.pk, a["id"]])
        self.assertEqual(grupos[0]["solicitacao"], "Quais máquinas estão sinalizadas?")
        self.assertEqual(len(grupos[1]["itens"]), 1)

    def test_delete_original_item_promotes_next_one(self):
        a, b = self._add_item(), self._add_item()
        self._post("api_livre_sol_delete", self.sol.pk)
        self.assertFalse(SolicitacaoLivre.objects.filter(pk=self.sol.pk).exists())
        nova_raiz = SolicitacaoLivre.objects.get(pk=a["id"])
        self.assertIsNone(nova_raiz.pai_id)
        self.assertEqual(SolicitacaoLivre.objects.get(pk=b["id"]).pai_id, a["id"])
        grupos = self.client.get(reverse("auditoria:livre_execucao", args=[self.aud.pk])).context["grupos_json"]
        self.assertEqual([len(g["itens"]) for g in grupos], [2, 1])  # a solicitação continua com os outros itens

    def test_delete_extra_item_and_whole_request(self):
        a = self._add_item()
        self._post("api_livre_sol_delete", a["id"])
        self.assertEqual(SolicitacaoLivre.objects.filter(pai=self.sol).count(), 0)
        self.assertTrue(SolicitacaoLivre.objects.filter(pk=self.sol.pk).exists())
        b, c = self._add_item(), self._add_item()
        r = self._post("api_livre_grupo_delete", c["id"])  # a partir de qualquer item
        self.assertEqual(r.json()["resumo"]["total"], 1)  # sobrou só "Outra"
        self.assertFalse(SolicitacaoLivre.objects.filter(pk__in=[self.sol.pk, b["id"], c["id"]]).exists())

    def test_items_have_own_photos_and_capa_and_flow_into_reports(self):
        from io import BytesIO
        from docx import Document
        from openpyxl import load_workbook
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        a = self._add_item()
        self._post("api_livre_sol_update", a["id"], {"evidencia": "DLP 04", "conclusao": "NC"})
        buf = BytesIO()
        Image.new("RGB", (40, 40), (1, 2, 3)).save(buf, "PNG")
        self.client.post(reverse("auditoria:api_livre_imagem_upload", args=[a["id"]]),
                         {"imagem": SimpleUploadedFile("f.png", buf.getvalue(), content_type="image/png")})
        self.assertEqual(self.sol.imagens.count(), 0)  # foto só do item certo
        # CAPA: só o item NC aparece no painel
        r = self.client.get(reverse("auditoria:livre_capa", args=[self.aud.pk]))
        self.assertEqual([i["id"] for i in r.context["itens"]], [a["id"]])
        self.assertEqual(r.context["itens"][0]["numero"], 2)  # #2: logo depois do item original
        # relatórios: uma linha por item
        wb = load_workbook(BytesIO(self.client.get(reverse("auditoria:livre_export_excel", args=[self.aud.pk])).content))
        linhas = [[c.value for c in row] for row in wb["Evidências"].iter_rows(min_row=2)]
        self.assertEqual([(l[1], l[4], l[5]) for l in linhas[:2]],
                         [("Máquinas", "PRA 03", "Conforme"), ("Máquinas", "DLP 04", "Não Conformidade")])
        doc = Document(BytesIO(self.client.get(reverse("auditoria:livre_export_docx", args=[self.aud.pk])).content))
        texto = "\n".join(c.text for t in doc.tables for row in t.rows for c in row.cells)
        self.assertIn("DLP 04", texto)
        self.assertIn("PRA 03", texto)

    def test_endpoints_require_login_and_post(self):
        url = reverse("auditoria:api_livre_item_create", args=[self.sol.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(self.client.post(reverse("auditoria:api_livre_grupo_delete", args=[self.sol.pk])).status_code, 302)
        from shared.permissions import VIEW_NAME_TO_PERMISSION as M
        for nome in ("api_livre_item_create", "api_livre_grupo_delete"):
            self.assertTrue(M[f"auditoria:{nome}"]["perm"].startswith("core.nav_auditoria_livre_"))


class AuditoriaLivreAuditadoETopicoTests(TestCase):
    """Colaborador auditado junto ao tópico e relatório agrupado por tópico."""

    def setUp(self):
        self.user = get_user_model().objects.create_superuser("aud7", "aud7@example.com", "x")
        self.client.force_login(self.user)
        self.aud = AuditoriaLivre.objects.create(titulo="Por tópico", data_inicio=date(2026, 11, 20))
        mk = lambda **kw: SolicitacaoLivre.objects.create(auditoria=self.aud, **kw)
        self.s1 = mk(solicitacao="Calibração", topico="Metrologia", auditado="João Silva", conclusao="NC", grau_nc="MAIOR", ordem=1)
        self.s2 = mk(solicitacao="Treinamento", topico="RH", auditado="Maria Souza", conclusao="C", ordem=2)
        self.s3 = mk(solicitacao="Registros", topico="Metrologia", auditado="Pedro Lima", conclusao="OM", ordem=3)
        self.s4 = mk(solicitacao="Geral", conclusao="P", ordem=4)

    def _post(self, nome, pk, dados=None):
        return self.client.post(reverse(f"auditoria:{nome}", args=[pk]), json.dumps(dados or {}),
                                content_type="application/json")

    def test_auditado_saved_cleaned_and_copied_to_new_items(self):
        r = self._post("api_livre_sol_update", self.s1.pk, {"auditado": "  Ana   Paula  Costa "})
        self.assertEqual(r.json()["solicitacao"]["auditado"], "Ana Paula Costa")
        item = self._post("api_livre_item_create", self.s1.pk).json()["item"]
        self.assertEqual(item["auditado"], "Ana Paula Costa")
        self._post("api_livre_sol_update", item["id"], {"auditado": "Bruno"})  # vale para a solicitação inteira
        self.s1.refresh_from_db()
        self.assertEqual(self.s1.auditado, "Bruno")
        self.s3.refresh_from_db()
        self.assertEqual(self.s3.auditado, "Pedro Lima")  # outras solicitações do mesmo tópico não mudam
        self._post("api_livre_sol_update", self.s1.pk, {"auditado": "x" * 400})
        self.s1.refresh_from_db()
        self.assertEqual(len(self.s1.auditado), 255)

    def test_create_with_auditado_and_page_payload(self):
        r = self._post("api_livre_sol_create", self.aud.pk, {"solicitacao": "Nova", "topico": "TI", "auditado": "Carla"})
        self.assertEqual(r.json()["solicitacao"]["auditado"], "Carla")
        grupos = self.client.get(reverse("auditoria:livre_execucao", args=[self.aud.pk])).context["grupos_json"]
        self.assertEqual({g["solicitacao"]: g["auditado"] for g in grupos}["Nova"], "Carla")
        self.assertContains(self.client.get(reverse("auditoria:livre_execucao", args=[self.aud.pk])), 'id="agruparTopico"')

    def test_collaborator_suggestions(self):
        from rh.models import Colaborador
        Colaborador.objects.create(matricula="123", nome_completo="Fernanda Oliveira", grupo="G", is_active=True)
        Colaborador.objects.create(matricula="124", nome_completo="Fernando Lima", grupo="G", is_active=True)
        Colaborador.objects.create(matricula="125", nome_completo="Fernanda Inativa", grupo="G", is_active=False)
        url = reverse("auditoria:api_livre_colaboradores_buscar")
        nomes = [c["nome"] for c in self.client.get(url, {"q": "fernan"}).json()["results"]]
        self.assertEqual(nomes, ["Fernanda Oliveira", "Fernando Lima"])  # ativos, em ordem alfabética
        self.assertEqual(self.client.get(url, {"q": "fernanda oli"}).json()["results"], [{"nome": "Fernanda Oliveira"}])
        self.assertEqual(self.client.get(url, {"q": "123"}).json()["results"], [{"nome": "Fernanda Oliveira"}])  # matrícula
        self.assertEqual(self.client.get(url, {"q": "f"}).json()["results"], [])  # mínimo de 2 letras
        self.client.logout()
        self.assertEqual(self.client.get(url, {"q": "fernan"}).status_code, 302)

    def _docx_texto(self, agrupar=None):
        from io import BytesIO
        from docx import Document
        extra = {"agrupar": agrupar} if agrupar else {}
        r = self.client.get(reverse("auditoria:livre_export_docx", args=[self.aud.pk]), extra)
        self.assertEqual(r.status_code, 200)
        doc = Document(BytesIO(r.content))
        return [p.text for p in doc.paragraphs], "\n".join(c.text for t in doc.tables for row in t.rows for c in row.cells)

    def test_word_default_shows_auditado_in_each_finding(self):
        paragrafos, tabelas = self._docx_texto()
        self.assertIn("#1  ·  Metrologia  ·  Auditado: João Silva", tabelas)
        self.assertIn("Não Conformidades (1)", paragrafos)  # continua agrupado por classificação

    def test_word_grouped_by_topic(self):
        paragrafos, tabelas = self._docx_texto("topico")
        # tópicos em ordem alfabética, "sem tópico" por último
        ordem = [p for p in paragrafos if p in ("Metrologia", "RH", "Sem tópico")]
        self.assertEqual(ordem, ["Metrologia", "RH", "Sem tópico"])
        self.assertIn("2 itens: 1 NC, 1 OM  ·  Auditado(s): João Silva, Pedro Lima", paragrafos)
        self.assertIn("1 item: 1 conformes  ·  Auditado(s): Maria Souza", paragrafos)
        self.assertIn("1 item: 1 pendentes", paragrafos)
        self.assertNotIn("Não Conformidades (1)", paragrafos)
        # a numeração da auditoria é mantida dentro dos blocos
        self.assertLess(tabelas.index("#1  ·"), tabelas.index("#3  ·"))
        self.assertLess(tabelas.index("#3  ·"), tabelas.index("#2  ·"))

    def test_excel_has_auditado_column_and_capa_shows_it(self):
        from io import BytesIO
        from openpyxl import load_workbook
        wb = load_workbook(BytesIO(self.client.get(reverse("auditoria:livre_export_excel", args=[self.aud.pk])).content))
        cab = [c.value for c in wb["Evidências"][1]]
        self.assertEqual(cab[1:3], ["Tópico", "Auditado"])
        self.assertEqual([wb["Evidências"].cell(row=r, column=3).value for r in (2, 3)], ["João Silva", "Maria Souza"])
        r = self.client.get(reverse("auditoria:livre_capa", args=[self.aud.pk]))
        self.assertContains(r, "João Silva")
        from .models import CapaLinkLivre
        from django.test import Client
        link = CapaLinkLivre.objects.create(auditoria=self.aud)
        portal = Client().get(reverse("auditoria:livre_capa_portal", args=[link.token]))
        self.assertContains(portal, "João Silva")

    def test_permission_mapping(self):
        from shared.permissions import VIEW_NAME_TO_PERMISSION as M
        self.assertTrue(M["auditoria:api_livre_colaboradores_buscar"]["perm"].startswith("core.nav_auditoria_livre_"))


class AuditoriaLivreSecaoPropriaTests(TestCase):
    """A Auditoria Livre é uma seção própria do menu, com permissões próprias (independentes da ISO 13485)."""

    LIVRE = ["livre_list", "livre_create", "livre_edit", "livre_arquivar", "livre_delete", "livre_execucao",
             "livre_export_excel", "livre_export_docx", "livre_capa"]
    PUBLICAS = ["livre_capa_portal", "api_livre_capa_responder_publico", "api_livre_capa_remover_anexo_publico",
                "livre_capa_anexo_publico", "livre_capa_imagem_publico"]

    def test_every_auditor_route_is_mapped_and_public_ones_are_not(self):
        import re
        from django.urls import get_resolver
        from shared.permissions import VIEW_NAME_TO_PERMISSION as M
        nomes = set()

        def walk(patterns):
            for p in patterns:
                if hasattr(p, "url_patterns"):
                    walk(p.url_patterns)
                elif getattr(p, "name", None) and re.match(r"^(api_)?livre", p.name):
                    nomes.add(p.name)
        walk(get_resolver().url_patterns)
        auditor = nomes - set(self.PUBLICAS)
        self.assertGreater(len(auditor), 20)
        for nome in sorted(auditor):
            self.assertIn(f"auditoria:{nome}", M, f"rota {nome} da Auditoria Livre sem permissão mapeada")
            self.assertTrue(M[f"auditoria:{nome}"]["perm"].startswith("core.nav_auditoria_livre_"), nome)
        for nome in self.PUBLICAS:
            self.assertNotIn(f"auditoria:{nome}", M)

    def test_functions_split_by_permission(self):
        from shared.permissions import VIEW_NAME_TO_PERMISSION as M
        esperado = {
            "livre_list": "lista", "livre_create": "gerenciar", "livre_delete": "gerenciar",
            "livre_execucao": "conducao", "api_livre_sol_update": "conducao", "api_livre_imagem_upload": "conducao",
            "livre_capa": "capa", "api_livre_capa_revisar": "capa", "api_livre_capa_enviar_link": "capa",
            "livre_export_excel": "export", "livre_export_docx": "export",
        }
        for nome, fim in esperado.items():
            self.assertEqual(M[f"auditoria:{nome}"]["perm"], f"core.nav_auditoria_livre_{fim}", nome)
        # e a seção de grupo exigida é a própria, não a da ISO 13485
        grupos = M["auditoria:livre_list"].get("grupos")
        self.assertEqual(grupos, ["core.nav_auditoria_livre_grupo"])

    def _usuario(self, nome, perms):
        from django.contrib.auth.models import Permission
        u = get_user_model().objects.create_user(nome, password="x")
        for cod in perms:
            u.user_permissions.add(Permission.objects.get(content_type__app_label="core", codename=cod))
        return get_user_model().objects.get(pk=u.pk)

    def test_access_is_independent_from_iso_and_needs_the_new_permissions(self):
        from shared.permissions import has_view_access
        base = ["nav_mod_auditoria"]
        so_iso = self._usuario("soiso", base + ["nav_auditoria_iso_bloco", "nav_auditoria_iso_lista", "nav_auditoria_iso_grupo"])
        self.assertFalse(has_view_access(so_iso, "auditoria:livre_list"))   # ISO sozinha não abre a Livre
        livre = self._usuario("livre", base + ["nav_auditoria_livre_grupo", "nav_auditoria_livre_bloco", "nav_auditoria_livre_lista"])
        self.assertTrue(has_view_access(livre, "auditoria:livre_list"))
        self.assertFalse(has_view_access(livre, "auditoria:iso_auditoria_list"))  # e a Livre não abre a ISO
        self.assertFalse(has_view_access(livre, "auditoria:livre_execucao"))      # cada função é separada
        sem_secao = self._usuario("semsecao", base + ["nav_auditoria_livre_bloco", "nav_auditoria_livre_lista"])
        self.assertFalse(has_view_access(sem_secao, "auditoria:livre_list"))      # flag da seção desligada

    def test_menu_shows_own_section_only_to_those_with_access(self):
        url = reverse("auditoria:hub")
        com = self._usuario("comlivre", ["nav_mod_auditoria", "nav_auditoria_livre_grupo", "nav_auditoria_livre_bloco",
                                          "nav_auditoria_livre_lista", "nav_auditoria_livre_gerenciar"])
        self.client.force_login(com)
        html = self.client.get(url).content.decode()
        self.assertIn("AUDITORIA LIVRE", html)
        self.assertIn(reverse("auditoria:livre_list"), html)
        self.assertIn(reverse("auditoria:livre_create"), html)
        self.assertNotIn("Modo Entrevista", html)  # a seção ISO não aparece sem permissão da ISO
        sem = self._usuario("semlivre", ["nav_mod_auditoria", "nav_auditoria_iso_bloco", "nav_auditoria_iso_lista", "nav_auditoria_iso_grupo"])
        self.client.force_login(sem)
        html = self.client.get(url).content.decode()
        self.assertNotIn("AUDITORIA LIVRE", html)
        self.assertIn("Modo Entrevista", html)

    def test_admin_sees_everything_and_livre_is_not_inside_iso_section(self):
        admin = get_user_model().objects.create_superuser("adm", "adm@example.com", "x")
        self.client.force_login(admin)
        html = self.client.get(reverse("auditoria:hub")).content.decode()
        i, j = html.index("collapseISO"), html.index("collapseLIVRE")
        self.assertLess(i, j)
        secao_iso = html[i:j]
        self.assertNotIn(reverse("auditoria:livre_list"), secao_iso)  # o item saiu da seção da ISO

    def test_migration_keeps_access_of_current_users(self):
        from importlib import import_module
        from django.apps import apps as django_apps
        from django.contrib.auth.models import Group, Permission
        from shared.permissions import has_view_access
        antigas = ["nav_mod_auditoria", "nav_auditoria_iso_bloco", "nav_auditoria_iso_lista", "nav_auditoria_iso_grupo"]
        direto = self._usuario("direto", antigas)
        so_lista = self._usuario("solista", ["nav_mod_auditoria", "nav_auditoria_iso_lista"])  # sem a seção ISO: não acessava
        # permissões core.nav_* herdadas de grupo nunca valeram no sistema: não podem virar acesso novo
        grupo = Group.objects.create(name="Auditores")
        for cod in antigas:
            grupo.permissions.add(Permission.objects.get(content_type__app_label="core", codename=cod))
        por_grupo = self._usuario("porgrupo", [])
        por_grupo.groups.add(grupo)
        inativo = self._usuario("inativo", antigas)
        inativo.is_active = False
        inativo.save()
        antes = {n: has_view_access(get_user_model().objects.get(username=n), "auditoria:livre_list")
                 for n in ("direto", "solista", "porgrupo")}
        self.assertEqual(antes["porgrupo"], False)
        import_module("core.migrations.0069_nav_auditoria_livre_dados").forwards(django_apps, None)
        dir_ = get_user_model().objects.get(username="direto")
        self.assertTrue(has_view_access(dir_, "auditoria:livre_list"))
        self.assertTrue(has_view_access(dir_, "auditoria:livre_export_docx"))
        for nome in ("solista", "porgrupo", "inativo"):
            u = get_user_model().objects.get(username=nome)
            self.assertFalse(u.user_permissions.filter(codename__startswith="nav_auditoria_livre_").exists(), nome)
        self.assertFalse(has_view_access(get_user_model().objects.get(username="porgrupo"), "auditoria:livre_list"))
        self.assertEqual(grupo.permissions.filter(codename__startswith="nav_auditoria_livre_").count(), 0)  # grupos intactos
        # idempotente: rodar de novo não duplica nem quebra
        import_module("core.migrations.0069_nav_auditoria_livre_dados").forwards(django_apps, None)
        self.assertEqual(dir_.user_permissions.filter(codename__startswith="nav_auditoria_livre_").count(), 7)

    def test_hub_card_and_search_entries(self):
        from shared.views.views import MODULE_HUBS_CONFIG, SYSTEM_FEATURES_CATALOG
        titulos = [a["title"] for a in MODULE_HUBS_CONFIG["auditoria"]["activities"]]
        self.assertIn("Auditoria Livre", titulos)
        busca = {f["view_name"] for f in SYSTEM_FEATURES_CATALOG}
        self.assertTrue({"auditoria:livre_list", "auditoria:livre_create"} <= busca)


class AuditoriaLivreExecucoesTests(TestCase):
    """Nova execução a partir de uma auditoria concluída e comparação da evolução."""

    def setUp(self):
        self.user = get_user_model().objects.create_superuser("aud8", "aud8@example.com", "x")
        self.client.force_login(self.user)
        self.aud = AuditoriaLivre.objects.create(
            titulo="PCP - HMC", objetivo="Verificar PCP", escopo="HMC", criterio="PRO-1", local="HMC",
            auditor_lider="Maria", auditados="João", data_inicio=date(2026, 11, 20), data_fim=date(2026, 11, 21),
            status="CONCLUIDA", conclusao_texto="Parecer da 1ª execução")
        self.aud.auditores.add(self.user)
        mk = lambda **kw: SolicitacaoLivre.objects.create(auditoria=self.aud, **kw)
        # solicitação 1 com três itens: PRA 03 conforme, VFTOrbit 03 OM, DLP 04 NC
        self.r1 = mk(solicitacao="Quais máquinas?", topico="Máquinas", auditado="João", ordem=1, evidencia="PRA 03", conclusao="C")
        self.r1b = mk(solicitacao="Quais máquinas?", topico="Máquinas", auditado="João", ordem=1, pai=self.r1,
                      evidencia="VFTOrbit 03", conclusao="OM")
        self.r1c = mk(solicitacao="Quais máquinas?", topico="Máquinas", auditado="João", ordem=1, pai=self.r1,
                      evidencia="DLP 04", conclusao="NC", grau_nc="MAIOR", capa_status="APROVADO", capa_causa_raiz="x")
        self.r2 = mk(solicitacao="Registros", topico="Pessoas", auditado="Maria", ordem=2, evidencia="ok", conclusao="C")
        self.r3 = mk(solicitacao="Treinamento", topico="Pessoas", auditado="Maria", ordem=3, evidencia="falta", conclusao="NC")

    def _nova(self, aud=None, pendencias=False):
        aud = aud or self.aud
        r = self.client.post(reverse("auditoria:livre_nova_execucao", args=[aud.pk]),
                             {"somente_pendencias": "1"} if pendencias else {})
        return r, AuditoriaLivre.objects.filter(anterior=aud).order_by("-id").first()

    def _linha(self, nova, anterior):
        return SolicitacaoLivre.objects.get(auditoria=nova, anterior=anterior)

    def _set(self, nova, anterior, conclusao, **kw):
        SolicitacaoLivre.objects.filter(auditoria=nova, anterior=anterior).update(conclusao=conclusao, **kw)

    # ------------------------------------------------------------------ criar
    def test_new_execution_copies_structure_with_clean_data(self):
        r, nova = self._nova()
        self.assertRedirects(r, reverse("auditoria:livre_execucao", args=[nova.pk]))
        self.assertEqual((nova.execucao, nova.anterior_id, nova.status, nova.somente_pendencias), (2, self.aud.pk, "PLANEJADA", False))
        self.assertEqual((nova.titulo, nova.objetivo, nova.escopo, nova.criterio, nova.local, nova.auditor_lider, nova.auditados),
                         ("PCP - HMC", "Verificar PCP", "HMC", "PRO-1", "HMC", "Maria", "João"))
        self.assertEqual(list(nova.auditores.all()), [self.user])
        self.assertEqual((nova.data_inicio, nova.data_fim, nova.conclusao_texto), (date.today(), None, ""))
        linhas = list(nova.solicitacoes.order_by("ordem", "id"))
        self.assertEqual(len(linhas), 5)
        for l in linhas:
            self.assertEqual((l.evidencia, l.conclusao, l.grau_nc, l.observacao, l.capa_status, l.capa_causa_raiz),
                             ("", "P", None, "", "PENDENTE", ""))
            self.assertEqual(l.imagens.count(), 0)
        # estrutura: a solicitação com 3 itens continua com 3 itens ligados à mesma linha original
        p1 = self._linha(nova, self.r1)
        self.assertIsNone(p1.pai_id)
        self.assertEqual(self._linha(nova, self.r1b).pai_id, p1.pk)
        self.assertEqual(self._linha(nova, self.r1c).pai_id, p1.pk)
        self.assertEqual((p1.topico, p1.auditado, p1.solicitacao, p1.ordem), ("Máquinas", "João", "Quais máquinas?", 1))
        self.assertEqual([self._linha(nova, x).ordem for x in (self.r1, self.r2, self.r3)], [1, 2, 3])
        # a execução original não muda
        self.aud.refresh_from_db()
        self.assertEqual((self.aud.status, self.aud.conclusao_texto), ("CONCLUIDA", "Parecer da 1ª execução"))
        self.assertEqual(self.r1c.__class__.objects.get(pk=self.r1c.pk).conclusao, "NC")

    def test_only_concluded_and_only_one_successor(self):
        self.aud.status = "EM_ANDAMENTO"
        self.aud.save()
        r, nova = self._nova()
        self.assertIsNone(nova)
        self.assertEqual(AuditoriaLivre.objects.count(), 1)
        self.aud.status = "CONCLUIDA"
        self.aud.save()
        _, nova = self._nova()
        self.assertIsNotNone(nova)
        r, outra = self._nova()  # já existe a próxima
        self.assertEqual(AuditoriaLivre.objects.count(), 2)
        self.assertRedirects(r, reverse("auditoria:livre_execucao", args=[nova.pk]))
        self.assertEqual(self.client.get(reverse("auditoria:livre_nova_execucao", args=[self.aud.pk])).status_code, 405)

    def test_only_pendencias_keeps_open_items_and_promotes_a_root(self):
        r, nova = self._nova(pendencias=True)
        self.assertTrue(nova.somente_pendencias)
        anteriores = set(nova.solicitacoes.values_list("anterior_id", flat=True))
        self.assertEqual(anteriores, {self.r1b.pk, self.r1c.pk, self.r3.pk})  # conformes não entram
        # a linha original (conforme) ficou de fora: o primeiro item que entrou virou a original
        raiz = self._linha(nova, self.r1b)
        self.assertIsNone(raiz.pai_id)
        self.assertEqual(self._linha(nova, self.r1c).pai_id, raiz.pk)
        self.assertEqual([self._linha(nova, x).ordem for x in (self.r1b, self.r3)], [1, 2])

    def test_execution_page_shows_previous_result_per_item(self):
        _, nova = self._nova()
        r = self.client.get(reverse("auditoria:livre_execucao", args=[nova.pk]))
        self.assertContains(r, "Execução 2")
        itens = {i["id"]: i for g in r.context["grupos_json"] for i in g["itens"]}
        ant = itens[self._linha(nova, self.r1c).pk]["anterior"]
        self.assertEqual((ant["conclusao"], ant["rotulo"], ant["evidencia"]), ("NC", "Não Conformidade (NC Maior)", "DLP 04"))
        self.assertContains(self.client.get(reverse("auditoria:livre_list")), "Execução 2")
        # na lista: a execução 1 oferece ir para a 2; a 2 oferece a evolução
        html = self.client.get(reverse("auditoria:livre_list")).content.decode()
        self.assertIn(reverse("auditoria:livre_comparar", args=[nova.pk]), html)
        self.assertIn(reverse("auditoria:livre_execucao", args=[nova.pk]), html)

    def test_new_execution_button_only_for_concluded_without_next(self):
        html = self.client.get(reverse("auditoria:livre_list")).content.decode()
        self.assertIn(reverse("auditoria:livre_nova_execucao", args=[self.aud.pk]), html)
        self.assertIn("Nova execução", self.client.get(reverse("auditoria:livre_execucao", args=[self.aud.pk])).content.decode())
        self._nova()
        self.assertNotIn(reverse("auditoria:livre_nova_execucao", args=[self.aud.pk]),
                         self.client.get(reverse("auditoria:livre_list")).content.decode())

    # --------------------------------------------------------------- comparar
    def _segunda_execucao(self):
        """Resultados da 2ª execução cobrindo todas as categorias de evolução."""
        _, nova = self._nova()
        self._set(nova, self.r1, "C", evidencia="PRA 03 ok")            # C  -> C   Mantido
        self._set(nova, self.r1b, "C", evidencia="corrigido")           # OM -> C   Resolvido
        self._set(nova, self.r1c, "OM", evidencia="melhorou")           # NC -> OM  Melhorou
        self._set(nova, self.r2, "NC", evidencia="piorou")              # C  -> NC  Piorou
        self._set(nova, self.r3, "NC", evidencia="continua")            # NC -> NC  Persiste
        novo = SolicitacaoLivre.objects.create(auditoria=nova, solicitacao="Extra", ordem=9, conclusao="C")      # Novo
        pend = SolicitacaoLivre.objects.create(auditoria=nova, solicitacao="Falta", ordem=10, conclusao="P", anterior=None)
        return nova, novo, pend

    def test_service_classifies_every_category_and_counts(self):
        from .services.evolucao_livre import comparar
        nova, novo, _ = self._segunda_execucao()
        comp = comparar(nova, self.aud)
        cat = {(i["base"].pk if i["base"] else None, i["atual"].solicitacao if i["atual"] else None): i["categoria"] for i in comp["itens"]}
        self.assertEqual(cat[(self.r1.pk, "Quais máquinas?")], "MANTIDO")
        self.assertEqual(cat[(self.r1b.pk, "Quais máquinas?")], "RESOLVIDO")
        self.assertEqual(cat[(self.r1c.pk, "Quais máquinas?")], "MELHOROU")
        self.assertEqual(cat[(self.r2.pk, "Registros")], "PIOROU")
        self.assertEqual(cat[(self.r3.pk, "Treinamento")], "PERSISTE")
        self.assertEqual(cat[(None, "Extra")], "NOVO")
        self.assertEqual(cat[(None, "Falta")], "NOVO")
        self.assertEqual(comp["contagem"]["NOVO"], 2)
        # contagens e índice: antes C2 NC2 OM1 -> índice 40; depois C3 NC2 OM1 P1 -> 50
        self.assertEqual((comp["res_base"]["C"], comp["res_base"]["NC"], comp["res_base"]["OM"], comp["res_base"]["indice"]), (2, 2, 1, 40.0))
        self.assertEqual((comp["res_atual"]["C"], comp["res_atual"]["NC"], comp["res_atual"]["OM"], comp["res_atual"]["indice"]), (3, 2, 1, 50.0))
        self.assertEqual((comp["deltas"]["C"], comp["deltas"]["NC"], comp["deltas"]["total"], comp["deltas"]["indice"]), (1, 0, 2, 10.0))
        # piores primeiro; nomes de tópicos e auditados
        self.assertEqual(comp["itens"][0]["categoria"], "PIOROU")
        pessoas = next(t for t in comp["topicos"] if t["topico"] == "Pessoas")
        self.assertEqual((pessoas["antes"]["NC"], pessoas["depois"]["NC"], pessoas["auditados"]), (1, 2, ["Maria"]))
        self.assertEqual(comp["topicos"][-1]["topico"], "")  # "sem tópico" por último

    def test_pending_removed_and_not_reevaluated(self):
        from .services.evolucao_livre import comparar
        _, nova = self._nova()  # todos pendentes
        comp = comparar(nova, self.aud)
        self.assertEqual({i["categoria"] for i in comp["itens"]}, {"PENDENTE"})
        self.assertIsNone(comp["res_atual"]["indice"])
        self.assertIsNone(comp["deltas"]["indice"])
        SolicitacaoLivre.objects.filter(auditoria=nova, anterior=self.r3).delete()  # item removido da nova execução
        self.assertEqual(comparar(nova, self.aud)["contagem"]["REMOVIDO"], 1)
        # execução só pendências: o que estava conforme é "não reavaliado", não "removido"
        self.aud.proximas.all().delete()
        _, so = self._nova(pendencias=True)
        c = comparar(so, self.aud)["contagem"]
        self.assertEqual((c["NAO_REAVALIADO"], c["REMOVIDO"]), (2, 0))  # PRA 03 e "Registros"

    def test_comparing_non_adjacent_executions_follows_the_chain(self):
        from .services.evolucao_livre import comparar
        nova, _, _ = self._segunda_execucao()
        nova.status = "CONCLUIDA"
        nova.save()
        _, terceira = self._nova(nova)
        self.assertEqual(terceira.execucao, 3)
        self.assertEqual([a.execucao for a in terceira.cadeia()], [1, 2, 3])
        self.assertEqual([a.execucao for a in self.aud.cadeia()], [1, 2, 3])
        self._set(terceira, self._linha(nova, self.r3), "C", evidencia="resolvido")  # r3 ficou NC -> C na 3ª
        comp = comparar(terceira, self.aud)  # 3ª contra a 1ª, passando pela 2ª
        item = next(i for i in comp["itens"] if i["base"] and i["base"].pk == self.r3.pk)
        self.assertEqual((item["categoria"], item["atual"].conclusao), ("RESOLVIDO", "C"))
        from .services.evolucao_livre import ExecucaoInvalida
        with self.assertRaises(ExecucaoInvalida):
            comparar(self.aud, terceira)  # só se compara com uma execução anterior

    def test_compare_view_and_selector(self):
        nova, _, _ = self._segunda_execucao()
        r = self.client.get(reverse("auditoria:livre_comparar", args=[nova.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["base"], self.aud)
        self.assertContains(r, "Evolução item a item")
        self.assertContains(r, "Piorou")
        self.assertContains(r, "Resolvido")
        self.assertContains(r, 'id="grafico"')
        # primeira execução: mensagem + atalho para a próxima
        r = self.client.get(reverse("auditoria:livre_comparar", args=[self.aud.pk]))
        self.assertIsNone(r.context["comp"])
        self.assertContains(r, "primeira execução")
        self.assertContains(r, reverse("auditoria:livre_comparar", args=[nova.pk]))
        # ?com= de outra série/inválido é ignorado
        outra = AuditoriaLivre.objects.create(titulo="Outra", data_inicio=date(2026, 1, 1))
        for com in (outra.pk, "abc", nova.pk):
            r = self.client.get(reverse("auditoria:livre_comparar", args=[nova.pk]), {"com": com})
            self.assertEqual(r.context["base"], self.aud)

    def test_deleting_previous_execution_does_not_break_the_next(self):
        nova, _, _ = self._segunda_execucao()
        self.aud.arquivada = True
        self.aud.save()
        self.client.post(reverse("auditoria:livre_delete", args=[self.aud.pk]))
        nova.refresh_from_db()
        self.assertIsNone(nova.anterior_id)
        self.assertEqual(self.client.get(reverse("auditoria:livre_execucao", args=[nova.pk])).status_code, 200)
        self.assertIsNone(self.client.get(reverse("auditoria:livre_comparar", args=[nova.pk])).context["comp"])

    # ------------------------------------------------------------ relatórios
    def test_comparative_excel_and_word(self):
        from io import BytesIO
        from docx import Document
        from openpyxl import load_workbook
        nova, _, _ = self._segunda_execucao()
        nova.conclusao_texto = "Parecer da 2ª execução"
        nova.save()
        wb = load_workbook(BytesIO(self.client.get(reverse("auditoria:livre_comparar_excel", args=[nova.pk])).content))
        self.assertEqual(wb.sheetnames, ["Resumo", "Evolução da série", "Itens", "Tópicos"])
        resumo = {row[0].value: [c.value for c in row[1:4]] for row in wb["Resumo"].iter_rows(min_row=6, max_row=12)}
        self.assertEqual(resumo["Conforme"][:2], [2, 3])
        self.assertEqual(resumo["Índice de conformidade"][:2], ["40,0%", "50,0%"])
        evol = [[c.value for c in row] for row in wb["Evolução da série"].iter_rows(min_row=2)]
        self.assertEqual([e[0] for e in evol], [1, 2])
        itens = [[c.value for c in row] for row in wb["Itens"].iter_rows(min_row=2)]
        self.assertEqual(itens[0][7], "Piorou")  # piores primeiro
        self.assertIn(["Pessoas", "Maria", "Registros", "ok", "Conforme", "piorou", "Não Conformidade", "Piorou"], itens)
        r = self.client.get(reverse("auditoria:livre_comparar_docx", args=[nova.pk]))
        self.assertIn("wordprocessingml", r["Content-Type"])
        doc = Document(BytesIO(r.content))
        paragrafos = [p.text for p in doc.paragraphs]
        texto = "\n".join(c.text for t in doc.tables for row in t.rows for c in row.cells) + "\n".join(paragrafos)
        for esperado in ("RELATÓRIO COMPARATIVO DE AUDITORIA", "Execução 1 (20/11/2026)", "Piorou (1)", "Resolvido (1)",
                         "Persiste (1)", "Item novo (2)", "Parecer da 1ª execução", "Parecer da 2ª execução",
                         "40,0%", "50,0%", "+10,0 p.p.", "Registros", "piorou"):
            self.assertIn(esperado, texto)

    def test_summary_sentence_uses_singular_and_plural(self):
        from .services.comparativo_livre_export import frase_resumo
        base = {c: 0 for c in ("RESOLVIDO", "MELHOROU", "PERSISTE", "PIOROU", "NOVO", "PENDENTE")}
        self.assertEqual(frase_resumo({"contagem": {**base, "RESOLVIDO": 1, "PERSISTE": 2, "PIOROU": 1}}),
                         "1 resolvido, 2 persistem, 1 piorou.")
        self.assertEqual(frase_resumo({"contagem": base}), "Sem itens para comparar.")

    def test_exports_for_first_execution_redirect_with_message(self):
        for nome in ("livre_comparar_excel", "livre_comparar_docx"):
            r = self.client.get(reverse(f"auditoria:{nome}", args=[self.aud.pk]))
            self.assertRedirects(r, reverse("auditoria:livre_execucao", args=[self.aud.pk]))

    def test_single_audit_reports_show_execution_number(self):
        from io import BytesIO
        from docx import Document
        nova, _, _ = self._segunda_execucao()
        doc = Document(BytesIO(self.client.get(reverse("auditoria:livre_export_docx", args=[nova.pk])).content))
        celulas = [c.text for t in doc.tables for row in t.rows for c in row.cells]
        self.assertIn("Execução", celulas)
        self.assertIn("2", celulas)

    # ------------------------------------------------------------ permissões
    def test_login_required_and_permission_mapping(self):
        from shared.permissions import VIEW_NAME_TO_PERMISSION as M
        esperado = {"livre_nova_execucao": "gerenciar", "livre_comparar": "lista",
                    "livre_comparar_excel": "export", "livre_comparar_docx": "export"}
        for nome, fim in esperado.items():
            self.assertEqual(M[f"auditoria:{nome}"]["perm"], f"core.nav_auditoria_livre_{fim}", nome)
        self.client.logout()
        for nome in esperado:
            self.assertEqual(self.client.post(reverse(f"auditoria:{nome}", args=[self.aud.pk])).status_code, 302, nome)


class AuditoriaLivreDashboardTests(TestCase):
    """Gráficos de evolução da Auditoria Livre no Dashboard Auditoria."""

    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("dash", "dash@example.com", "x")
        self.client.force_login(self.admin)
        self.url = reverse("auditoria:dashboard")

    def _aud(self, titulo, data, status="CONCLUIDA", anterior=None, execucao=1, **itens):
        aud = AuditoriaLivre.objects.create(titulo=titulo, data_inicio=data, status=status,
                                            anterior=anterior, execucao=execucao)
        for cod, n in itens.items():
            for k in range(n):
                SolicitacaoLivre.objects.create(auditoria=aud, solicitacao=f"{cod}{k}", conclusao=cod, ordem=k + 1)
        return aud

    def _serie_pcp(self):
        e1 = self._aud("PCP - HMC", date(2026, 11, 1), C=1, NC=1, OM=2)            # índice 25,0
        e2 = self._aud("PCP - HMC", date(2026, 11, 15), anterior=e1, execucao=2, C=3, NC=1)  # 75,0
        e3 = self._aud("PCP - HMC", date(2026, 12, 1), anterior=e2, execucao=3, C=4, P=1)    # 100,0
        return e1, e2, e3

    def test_service_builds_one_series_per_audit_with_indexes(self):
        from .services.evolucao_livre import dados_dashboard
        e1, e2, e3 = self._serie_pcp()
        unica = self._aud("Recebimento", date(2026, 11, 5), C=2, NC=2)             # 50,0
        d = dados_dashboard()
        self.assertEqual([s["titulo"] for s in d["series"]], ["PCP - HMC", "Recebimento"])
        pcp = d["series"][0]
        self.assertEqual([e["execucao"] for e in pcp["execucoes"]], [1, 2, 3])
        self.assertEqual([e["indice"] for e in pcp["execucoes"]], [25.0, 75.0, 100.0])
        self.assertEqual([e["NC"] for e in pcp["execucoes"]], [1, 1, 0])
        self.assertEqual((pcp["execucoes"][0]["data"], pcp["ultima_id"], pcp["variacao"]), ("01/11/2026", e3.pk, 75.0))
        self.assertIsNone(d["series"][1]["variacao"])  # uma execução só: sem evolução
        self.assertEqual(d["kpis"], {"auditorias": 2, "execucoes": 4, "com_evolucao": 1,
                                     "indice_medio": 75.0, "variacao_media": 75.0, "nc_abertas": 2})

    def test_service_filters_by_date_ignores_invalid_and_excludes_archived(self):
        from .services.evolucao_livre import dados_dashboard
        e1, e2, e3 = self._serie_pcp()
        d = dados_dashboard("2026-11-10", "2026-11-30")  # só a 2ª execução cai no período
        self.assertEqual([e["execucao"] for e in d["series"][0]["execucoes"]], [2])
        self.assertIsNone(d["series"][0]["variacao"])
        self.assertEqual(dados_dashboard("2027-01-01")["series"], [])
        self.assertEqual(len(dados_dashboard("não é data", "")["series"][0]["execucoes"]), 3)  # inválido: sem filtro
        e1.arquivada = True  # a 1ª arquivada: a 2ª passa a abrir a série, sem quebrar nada
        e1.save()
        self.assertEqual([e["execucao"] for e in dados_dashboard()["series"][0]["execucoes"]], [2, 3])
        for e in (e2, e3):
            e.arquivada = True
            e.save()
        self.assertEqual(dados_dashboard()["series"], [])
        self.assertEqual(dados_dashboard()["kpis"]["indice_medio"], None)

    def test_dashboard_shows_charts_and_table(self):
        self._serie_pcp()
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Auditoria Livre — Evolução")
        self.assertContains(r, 'id="chartLivreIndice"')
        self.assertContains(r, 'id="chartLivreComposicao"')
        self.assertContains(r, 'id="livre-series"')
        self.assertContains(r, "PCP - HMC")
        self.assertContains(r, "▲ +75,0 p.p.")  # número em pt-BR
        self.assertContains(r, reverse("auditoria:livre_comparar", args=[r.context["livre"]["series"][0]["ultima_id"]]))
        self.assertEqual(r.context["livre"]["kpis"]["com_evolucao"], 1)

    def test_dashboard_date_filter_applies_to_livre_section(self):
        self._serie_pcp()
        r = self.client.get(self.url, {"inicio": "2026-12-01", "fim": "2026-12-31"})
        self.assertEqual([e["execucao"] for e in r.context["livre"]["series"][0]["execucoes"]], [3])
        self.assertEqual(self.client.get(self.url, {"inicio": "lixo"}).status_code, 200)

    def test_dashboard_without_livre_data_shows_empty_message(self):
        r = self.client.get(self.url)
        self.assertContains(r, "Auditoria Livre — Evolução")
        self.assertContains(r, "Nenhuma auditoria livre no período")
        self.assertNotContains(r, 'id="chartLivreIndice"')

    def test_section_only_for_users_with_livre_access(self):
        from django.contrib.auth.models import Permission
        self._serie_pcp()
        base = ["nav_mod_auditoria", "nav_auditoria_analise", "nav_auditoria_dashboard"]

        def usuario(nome, extras):
            u = get_user_model().objects.create_user(nome, password="x")
            for cod in base + extras:
                u.user_permissions.add(Permission.objects.get(content_type__app_label="core", codename=cod))
            return u

        sem = usuario("semlivre", [])
        self.client.force_login(sem)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Auditoria Livre — Evolução")  # dados da Livre não vazam sem permissão
        self.assertNotContains(r, "PCP - HMC")
        self.assertIsNone(r.context.get("livre"))
        com = usuario("comlivre", ["nav_auditoria_livre_grupo", "nav_auditoria_livre_bloco", "nav_auditoria_livre_lista"])
        self.client.force_login(com)
        self.assertContains(self.client.get(self.url), "Auditoria Livre — Evolução")
