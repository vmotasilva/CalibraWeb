from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
import json

from laboratorio.models import FluxoProcessoTMS, EtapaProcessoTMS

User = get_user_model()


class TMSCalculosTestCase(TestCase):
    def setUp(self):
        self.fluxo = FluxoProcessoTMS.objects.create(
            nome="Linha Teste Lentes",
            codigo="LT-01",
            horas_trabalho_dia=8.8,
            dias_trabalho_mes=22,
            unidade_medida="PECAS",
            fator_conversao_par=2.0,
            tamanho_padrao_lote=50,
        )

        # Etapa 1: Triagem (TC=30s, 1 posto, OEE=100%, refugo=0%) -> TC ef = 30s -> Cap = 120 pçs/h
        self.etapa1 = EtapaProcessoTMS.objects.create(
            fluxo=self.fluxo,
            ordem=1,
            nome="Triagem",
            tipo_posto="MANUAL",
            tempo_ciclo_segundos=30.0,
            postos_paralelos=1,
            eficiencia_oee=100.0,
            perda_refugo_pct=0.0,
        )

        # Etapa 2: Surfaçagem (TC=120s, 2 postos, OEE=100%, refugo=0%) -> TC ef = 60s -> Cap = 60 pçs/h (GARGALO)
        self.etapa2 = EtapaProcessoTMS.objects.create(
            fluxo=self.fluxo,
            ordem=2,
            nome="Surfaçagem",
            tipo_posto="MAQUINA",
            tempo_ciclo_segundos=120.0,
            postos_paralelos=2,
            eficiencia_oee=100.0,
            perda_refugo_pct=0.0,
        )

        # Etapa 3: Montagem (TC=40s, 1 posto, OEE=100%, refugo=0%) -> TC ef = 40s -> Cap = 90 pçs/h
        self.etapa3 = EtapaProcessoTMS.objects.create(
            fluxo=self.fluxo,
            ordem=3,
            nome="Montagem",
            tipo_posto="MANUAL",
            tempo_ciclo_segundos=40.0,
            postos_paralelos=1,
            eficiencia_oee=100.0,
            perda_refugo_pct=0.0,
        )

    def test_identificacao_correta_do_gargalo(self):
        metricas = self.fluxo.calcular_metricas()
        
        # O gargalo deve ser a Etapa 2 (Surfaçagem) com TC efetivo de 60s (menor vazão: 60 pçs/h)
        self.assertIsNotNone(metricas["gargalo"])
        self.assertEqual(metricas["gargalo"]["id"], self.etapa2.id)
        self.assertEqual(metricas["gargalo"]["nome"], "Surfaçagem")
        self.assertEqual(metricas["capacidade_maxima_hora_pecas"], 60.0)
        
        # Capacidade diária = 60 * 8.8 = 528 peças/dia
        self.assertEqual(metricas["capacidade_maxima_dia_pecas"], 528)
        # Capacidade em pares = 528 / 2 = 264 pares/dia
        self.assertEqual(metricas["capacidade_maxima_dia_pares"], 264)

    def test_balanceamento_de_linha(self):
        metricas = self.fluxo.calcular_metricas()
        # TC efetivos: 30s + 60s + 40s = 130s
        # 3 etapas * 60s (gargalo) = 180s
        # Eficiência = (130 / 180) * 100 = 72.2%
        self.assertEqual(metricas["eficiencia_balanceamento_pct"], 72.2)
        # Lead time teórico = (30 + 120 + 40) / 60 = 190s / 60 = 3.17 min
        self.assertEqual(metricas["lead_time_teorico_unitario_min"], 3.17)

    def test_previsao_producao(self):
        # Demanda de 600 peças
        # Gargalo produz 60 pçs/h
        # Tempo total aprox: (190s + 599 * 60s) / 3600 = (190 + 35940) / 3600 = 36130 / 3600 = 10.04 horas
        previsao = self.fluxo.simular_previsao(demanda_unidades=600, tipo_unidade="PECAS")
        self.assertEqual(previsao["pecas_totais"], 600)
        self.assertAlmostEqual(previsao["tempo_total_horas"], 10.04, places=1)
        # Dias úteis = 10.04 / 8.8 = 1.14 dias
        self.assertAlmostEqual(previsao["dias_uteis_estimados"], 1.14, places=1)

    def test_simulacao_what_if_resolvendo_gargalo(self):
        # Se adicionarmos +2 postos na Etapa 2 (total 4 postos):
        # Novo TC efetivo da Etapa 2: 120s / 4 = 30s -> Cap = 120 pçs/h
        # Novo gargalo passa a ser a Etapa 3 (Montagem) com 40s (90 pçs/h)
        overrides = {
            str(self.etapa2.id): {"postos_paralelos": 4}
        }
        metricas = self.fluxo.calcular_metricas(etapas_override=overrides)
        self.assertEqual(metricas["gargalo"]["id"], self.etapa3.id)
        self.assertEqual(metricas["capacidade_maxima_hora_pecas"], 90.0)
        self.assertEqual(metricas["capacidade_maxima_dia_pecas"], 792)


class TMSViewsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.client = Client()
        self.client.login(username="testuser", password="password123")

        self.fluxo = FluxoProcessoTMS.objects.create(
            nome="Linha Coating AR",
            codigo="COAT-01",
            horas_trabalho_dia=8.8,
            dias_trabalho_mes=22,
        )

        self.etapa = EtapaProcessoTMS.objects.create(
            fluxo=self.fluxo,
            ordem=1,
            nome="Câmara de Vácuo",
            tipo_posto="MAQUINA",
            tempo_ciclo_segundos=90.0,
            postos_paralelos=2,
            eficiencia_oee=85.0,
        )

    def test_dashboard_view(self):
        url = reverse("laboratorio:tms_dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Linha Coating AR")
        self.assertContains(response, "Câmara de Vácuo")

    def test_api_simular(self):
        url = reverse("laboratorio:api_tms_simular")
        payload = {
            "fluxo_id": self.fluxo.id,
            "demanda": 300,
            "tipo_unidade": "PECAS",
            "horas_dia": 8.8,
        }
        response = self.client.post(url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["resultado"]["pecas_totais"], 300)
        self.assertGreater(data["resultado"]["tempo_total_horas"], 0)

    def test_fluxos_list_and_crud(self):
        # List
        url = reverse("laboratorio:tms_fluxos_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Create
        create_url = reverse("laboratorio:tms_fluxo_create")
        post_data = {
            "nome": "Novo Fluxo Montagem",
            "codigo": "MONT-01",
            "horas_trabalho_dia": "8.8",
            "dias_trabalho_mes": 22,
            "unidade_medida": "PECAS",
            "fator_conversao_par": "2.0",
            "tamanho_padrao_lote": 1,
            "ativo": True,
        }
        resp_post = self.client.post(create_url, data=post_data)
        self.assertEqual(resp_post.status_code, 302)
        self.assertTrue(FluxoProcessoTMS.objects.filter(nome="Novo Fluxo Montagem").exists())

    def test_duplicar_fluxo(self):
        url = reverse("laboratorio:tms_fluxo_duplicar", kwargs={"pk": self.fluxo.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        copias = FluxoProcessoTMS.objects.filter(nome__startswith="Linha Coating AR (Cópia")
        self.assertTrue(copias.exists())
        self.assertEqual(copias.first().etapas.count(), 1)

    def test_carregar_exemplo(self):
        url = reverse("laboratorio:tms_carregar_exemplo")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        exemplo = FluxoProcessoTMS.objects.filter(nome="Linha de Produção - Lentes & Coating AR")
        self.assertTrue(exemplo.exists())
        self.assertEqual(exemplo.first().etapas.count(), 8)
