from datetime import date

from django.test import TestCase
from django.urls import reverse

from .models import HistoricoCalibracao, Instrumento


class HistoricoCalibracaoLogicTests(TestCase):
    def setUp(self):
        self.inst = Instrumento.objects.create(
            tag="TST-001", descricao="Instrumento Teste"
        )

    def test_result_aprovado_when_eme_leq_ema(self):
        # erro + incerteza = 2, tolerancia -> ema = tol/2 = 2 -> APROVADO
        hist = HistoricoCalibracao(
            instrumento=self.inst,
            data_calibracao=date.today(),
            erro_encontrado=1,
            incerteza=1,
            tolerancia_usada=4,
        )
        hist.save()
        self.assertEqual(hist.resultado, "APROVADO")

    def test_result_reprovado_when_eme_gt_3x_ema(self):
        # erro + incerteza = 10, tolerancia -> ema = 1 -> 10 > 3 -> REPROVADO
        hist = HistoricoCalibracao(
            instrumento=self.inst,
            data_calibracao=date.today(),
            erro_encontrado=9,
            incerteza=1,
            tolerancia_usada=2,
        )
        hist.save()
        self.assertEqual(hist.resultado, "REPROVADO")

    def test_result_condicional_when_between(self):
        # erro + incerteza = 3, ema = 2 -> between -> CONDICIONAL
        hist = HistoricoCalibracao(
            instrumento=self.inst,
            data_calibracao=date.today(),
            erro_encontrado=2,
            incerteza=1,
            tolerancia_usada=4,
        )
        hist.save()
        self.assertEqual(hist.resultado, "CONDICIONAL")


class CeleryTasksTests(TestCase):
    def test_ping_task(self):
        # call apply (synchronous execution) so this passes in regular test runner
        try:
            from .tasks import ping_task
        except ModuleNotFoundError:
            # Celery not installed in this environment — skip test gracefully
            self.skipTest("celery not installed")

        res = ping_task.apply().get()
        self.assertEqual(res, "pong")

class ImportInstrumentsTaskTests(TestCase):
    def setUp(self):
        self.user = None

    def test_import_instruments_task_creates_instrumentos(self):
        import tempfile
        from .models import ImportJob, Instrumento
        from .tasks import import_instruments_task

        # Create a small CSV file with one instrument
        csv_content = 'TAG,EQUIPAMENTO\nTST-01,Instrumento Teste\n'
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='w', encoding='utf-8')
        tmp.write(csv_content)
        tmp.flush()
        tmp.close()

        job = ImportJob.objects.create(filename='test.csv', filepath=tmp.name, status='PENDING')

        res = import_instruments_task(job.id, tmp.name)

        job.refresh_from_db()
        self.assertEqual(job.status, 'SUCCESS')
        self.assertIn('Imported', job.result)

        # Check that the instrumento was created
        inst = Instrumento.objects.filter(tag='TST-01').first()
        self.assertIsNotNone(inst)
        self.assertEqual(inst.descricao, 'Instrumento Teste')

    def test_imp_instr_view_enqueues_and_processes(self):
        from django.contrib.auth.models import User
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import ImportJob, Instrumento

        # create and login user
        u = User.objects.create_user(username='tester', password='pass')
        self.client.login(username='tester', password='pass')

        csv_content = b'TAG,EQUIPAMENTO\nTST-03,Instrumento View Test\n'
        uploaded = SimpleUploadedFile('insts.csv', csv_content, content_type='text/csv')

        resp = self.client.post('/imp-inst/', {'arquivo_excel': uploaded})
        # Should redirect to modulo_metrologia
        self.assertIn(resp.status_code, (302, 303))

        job = ImportJob.objects.filter(filename='insts.csv').first()
        self.assertIsNotNone(job)
        # task fallback runs synchronously in tests environment, so should be SUCCESS
        job.refresh_from_db()
        self.assertEqual(job.status, 'SUCCESS')

        inst = Instrumento.objects.filter(tag='TST-03').first()
        self.assertIsNotNone(inst)
        self.assertEqual(inst.descricao, 'Instrumento View Test')


class BasicViewsTests(TestCase):
    def test_healthz_returns_200(self):
        resp = self.client.get("/healthz/")
        self.assertEqual(resp.status_code, 200)

    def test_carimbar_creates_historico_and_returns_pdf(self):
        import io as _io
        from reportlab.pdfgen import canvas as _canvas
        from django.contrib.auth.models import User
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import Instrumento, HistoricoCalibracao

        # Create an instrument so the view can link the certificado
        inst = Instrumento.objects.create(tag="CAR-001", descricao="Inst Carimbo")

        # Create a small PDF in-memory
        buf = _io.BytesIO()
        c = _canvas.Canvas(buf, pagesize=(200, 200))
        c.drawString(10, 100, "Sample")
        c.save()
        buf.seek(0)
        pdf_bytes = buf.getvalue()

        u = User.objects.create_user(username="car_user", password="pw")
        self.client.login(username="car_user", password="pw")

        uploaded = SimpleUploadedFile("cert.pdf", pdf_bytes, content_type="application/pdf")

        data = {
            "data_validacao": "2025-11-24",
            "status_validacao": "Aprovado sem correções",
            "page_width": "200",
            "page_height": "200",
            "instrument_id_0": str(inst.id),
            "calib_date_0": "2025-11-01",
            "cert_num_0": "CERT123",
            "x_0": "0",
            "y_0": "0",
            "w_0": "0",
            "h_0": "0",
        }

        resp = self.client.post("/carimbar/", {**data, "arquivo_pdf": uploaded})
        # Response should be a generated PDF for a single uploaded file
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp["Content-Type"].startswith("application/pdf"))

        # DB should have a new HistoricoCalibracao for this instrument
        hist = HistoricoCalibracao.objects.filter(instrumento=inst, numero_certificado="CERT123").first()
        self.assertIsNotNone(hist)


class ProcedimentosListViewTests(TestCase):
    def setUp(self):
        # Criar 120 procedimentos variados e autenticar usuário (view exige login)
        from .models import Procedimento
        from django.contrib.auth.models import User
        tipos = ["POP", "DOC", "FOR", "TAB", "DEX"]
        count = 0
        for t in tipos:
            for i in range(1, 25):  # 24 de cada tipo = 120 total
                Procedimento.objects.create(
                    codigo=f"{t}.{1000+i}",
                    titulo=f"{t} TITULO {i}",
                    revisao_atual="01",
                    aplica_treinamento=True,
                )
                count += 1
        self.total = count
        # Autentica para evitar redirects (302)
        self.user = User.objects.create_user(username='procuser', password='pw')
        self.client.force_login(self.user)

    def test_paginacao_primeira_pagina(self):
        url = reverse("procedimentos_list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        # Deve haver page_obj e máximo 50 registros
        self.assertIn("page_obj", resp.context)
        self.assertLessEqual(len(resp.context["procedimentos"]), 50)
        self.assertEqual(resp.context["page_obj"].number, 1)

    def test_paginacao_segunda_pagina(self):
        url = reverse("procedimentos_list") + "?page=2"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["page_obj"].number, 2)

    def test_filtro_tipo(self):
        url = reverse("procedimentos_list") + "?tipo=POP"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        for p in resp.context["procedimentos"]:
            self.assertTrue(p.codigo.startswith("POP."))

    def test_busca_termo(self):
        # Busca por um título específico
        url = reverse("procedimentos_list") + "?q=TITULO 5&tipo=DOC"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(any("TITULO 5" in p.titulo for p in resp.context["procedimentos"]))

    def test_limite_total(self):
        # Total criado deve ser 120
        from .models import Procedimento
        self.assertEqual(Procedimento.objects.count(), 120)
