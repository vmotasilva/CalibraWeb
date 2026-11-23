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
        self.assertEqual(linhas[2][4:6], ("Não Conformidade", "NC Menor"))

    def test_navigation_permission_mapping(self):
        from shared.permissions import VIEW_NAME_TO_PERMISSION
        for nome in ("livre_list", "livre_execucao", "api_livre_sol_update", "livre_export_excel"):
            self.assertEqual(
                VIEW_NAME_TO_PERMISSION[f"auditoria:{nome}"]["perm"], "core.nav_auditoria_iso_lista"
            )


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
        self.assertEqual(r.context["solicitacoes_json"][0]["imagens"][0]["legenda"], "Piso")
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
        self.assertEqual(wb["Evidências"]["H2"].value, 1)
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
        self.assertEqual(r.context["solicitacoes_json"][0]["capa_status"], "AGUARDANDO_REVISAO")
        wb = load_workbook(BytesIO(self.client.get(reverse("auditoria:livre_export_excel", args=[self.aud.pk])).content))
        linha = [c.value for c in wb["Evidências"][2]]
        self.assertEqual(linha[8:11], ["Aguardando Revisão", "João", "31/12/2026"])
        self.assertFalse(wb["Evidências"]["I5"].value)  # conforme não tem plano
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
            self.assertEqual(M[f"auditoria:{nome}"]["perm"], "core.nav_auditoria_iso_lista")
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
        self.assertEqual(M["auditoria:api_livre_capa_enviar_link"]["perm"], "core.nav_auditoria_iso_lista")
