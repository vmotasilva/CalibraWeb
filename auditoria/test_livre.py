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
