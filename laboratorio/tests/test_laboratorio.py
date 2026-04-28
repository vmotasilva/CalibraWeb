from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from laboratorio.models import CategoriaLaboratorio, OcorrenciaLaboratorio


class LaboratorioModuleTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="lab.admin",
            password="senha-forte-123",
            is_staff=True,
        )
        self.client.force_login(self.user)

    def test_modelo_calcula_duracao_e_assunto_pela_categoria(self):
        categoria = CategoriaLaboratorio.objects.create(
            nome="Falha de equipamento",
            impacto=CategoriaLaboratorio.IMPACTO_ALTO,
        )
        abertura = timezone.now()
        encerramento = abertura + timedelta(hours=2, minutes=30)

        ocorrencia = OcorrenciaLaboratorio.objects.create(
            categoria=categoria,
            assunto="",
            detalhamento="Parada inesperada na bancada principal.",
            consequencias="Atraso na liberacao das analises.",
            impacto="",
            responsavel=self.user,
            data_abertura=abertura,
            data_encerramento=encerramento,
        )

        self.assertEqual(ocorrencia.assunto, categoria.nome)
        self.assertEqual(ocorrencia.impacto, categoria.impacto)
        self.assertEqual(ocorrencia.duracao, timedelta(hours=2, minutes=30))

    def test_create_view_registra_ocorrencia(self):
        categoria = CategoriaLaboratorio.objects.create(
            nome="Contaminacao cruzada",
            impacto=CategoriaLaboratorio.IMPACTO_CRITICO,
        )
        abertura = timezone.localtime(timezone.now()).replace(second=0, microsecond=0)
        encerramento = abertura + timedelta(hours=1)

        response = self.client.post(
            reverse("laboratorio:ocorrencia_create"),
            {
                "data_abertura": abertura.strftime("%Y-%m-%dT%H:%M"),
                "data_encerramento": encerramento.strftime("%Y-%m-%dT%H:%M"),
                "responsavel": self.user.pk,
                "categoria": categoria.pk,
                "assunto": "",
                "impacto": "",
                "detalhamento": "Material reprovado na etapa de preparo.",
                "consequencias": "Necessidade de descarte do lote.",
            },
        )

        self.assertRedirects(response, reverse("laboratorio:ocorrencias_list"))
        ocorrencia = OcorrenciaLaboratorio.objects.get()
        self.assertEqual(ocorrencia.assunto, categoria.nome)
        self.assertEqual(ocorrencia.impacto, categoria.impacto)
        self.assertEqual(ocorrencia.responsavel, self.user)

    def test_dashboard_exibe_ocorrencias_filtradas(self):
        abertura = timezone.now()
        OcorrenciaLaboratorio.objects.create(
            assunto="Oscilacao de temperatura",
            detalhamento="Registro fora da faixa esperada por 20 minutos.",
            consequencias="Analise interrompida para ajuste.",
            impacto=CategoriaLaboratorio.IMPACTO_MEDIO,
            responsavel=self.user,
            data_abertura=abertura,
            data_encerramento=abertura + timedelta(minutes=20),
        )

        response = self.client.get(
            reverse("laboratorio:dashboard"),
            {
                "inicio": abertura.date().strftime("%Y-%m-%d"),
                "fim": abertura.date().strftime("%Y-%m-%d"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard de ocorrencias")
        self.assertEqual(response.context["total"], 1)
        self.assertEqual(response.context["encerradas"], 1)

    def test_detail_view_exibe_ocorrencia_e_link_na_listagem(self):
        abertura = timezone.now().replace(second=0, microsecond=0)
        ocorrencia = OcorrenciaLaboratorio.objects.create(
            assunto="Falha de incubadora",
            detalhamento="Equipamento ficou inoperante por oscilacao eletrica.",
            consequencias="Reagendamento das leituras do turno.",
            impacto=CategoriaLaboratorio.IMPACTO_ALTO,
            responsavel=self.user,
            data_abertura=abertura,
            data_encerramento=abertura + timedelta(hours=3, minutes=15),
        )

        list_response = self.client.get(reverse("laboratorio:ocorrencias_list"))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk]))

        detail_response = self.client.get(reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Falha de incubadora")
        self.assertContains(detail_response, "3h 15min")

    def test_encerramento_rapido_define_data_e_duracao(self):
        abertura = timezone.now().replace(second=0, microsecond=0) - timedelta(hours=2, minutes=10)
        ocorrencia = OcorrenciaLaboratorio.objects.create(
            assunto="Interrupcao temporaria de leitura",
            detalhamento="Parada para ajuste de configuracao.",
            consequencias="Fila de processamento reorganizada.",
            impacto=CategoriaLaboratorio.IMPACTO_MEDIO,
            responsavel=self.user,
            data_abertura=abertura,
        )

        response = self.client.post(
            reverse("laboratorio:ocorrencia_close", args=[ocorrencia.pk]),
            {"next": reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk])},
        )

        self.assertRedirects(response, reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk]))
        ocorrencia.refresh_from_db()
        self.assertIsNotNone(ocorrencia.data_encerramento)
        self.assertIsNotNone(ocorrencia.duracao)
        self.assertGreaterEqual(ocorrencia.duracao, timedelta(hours=2, minutes=10))
