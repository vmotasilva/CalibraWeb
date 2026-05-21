from decimal import Decimal
from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from laboratorio.models import CategoriaLaboratorio, OcorrenciaLaboratorio, OcorrenciaLaboratorioAnotacao
from maquinas.models import CategoriaMaquina, Maquina
from organization.models import Setor
from rh.models import Colaborador


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
        self.assertEqual(ocorrencia.criado_por, self.user)

    def test_formulario_exibe_modais_para_selecao_de_maquina_e_colaborador(self):
        setor = Setor.objects.create(nome="Laboratorio")
        colaborador = Colaborador.objects.create(
            matricula="1001",
            nome_completo="Ana Paula Teste",
            grupo="Laboratorio",
            setor=setor,
        )
        categoria_maquina = CategoriaMaquina.objects.create(nome="Polidora")
        maquina = Maquina.objects.create(
            codigo="POL-01",
            categoria=categoria_maquina,
            setor=setor,
        )

        response = self.client.get(reverse("laboratorio:ocorrencia_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-bs-target="#maquinaModal"', html=False)
        self.assertContains(response, 'data-bs-target="#colaboradorModal"', html=False)
        self.assertContains(response, 'id="maquina-categoria-filtro"', html=False)
        self.assertContains(response, 'id="colaborador-setor-filtro"', html=False)
        self.assertContains(response, 'Deseja alterar o assunto para', html=False)
        self.assertContains(response, 'O assunto parece coerente com a categoria', html=False)
        self.assertContains(response, categoria_maquina.nome)
        self.assertContains(response, maquina.display_name)
        self.assertContains(response, setor.nome)
        self.assertContains(response, colaborador.nome_completo)

    def test_formulario_preseleciona_maquina_via_query_string(self):
        setor = Setor.objects.create(nome="Laboratorio")
        categoria_maquina = CategoriaMaquina.objects.create(nome="Misturador")
        maquina = Maquina.objects.create(
            codigo="MIX-01",
            fabricante="IKA",
            categoria=categoria_maquina,
            setor=setor,
        )

        response = self.client.get(reverse("laboratorio:ocorrencia_create"), {"maquina_id": maquina.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="maquina-resumo"', html=False)
        self.assertContains(response, maquina.display_name)
        self.assertContains(response, categoria_maquina.nome)

    def test_create_view_exige_colaborador_para_categoria_de_falta(self):
        categoria = CategoriaLaboratorio.objects.create(
            nome="Falta de Colaborador",
            impacto=CategoriaLaboratorio.IMPACTO_ALTO,
        )

        response = self.client.post(
            reverse("laboratorio:ocorrencia_create"),
            {
                "data_abertura": timezone.localtime(timezone.now()).replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M"),
                "responsavel": self.user.pk,
                "categoria": categoria.pk,
                "assunto": "Ausencia no turno A",
                "impacto": categoria.impacto,
                "detalhamento": "Nao houve substituicao imediata.",
                "consequencias": "Atraso no fluxo.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Selecione o colaborador vinculado a esta ocorrencia.")
        self.assertFalse(OcorrenciaLaboratorio.objects.filter(assunto="Ausencia no turno A").exists())

    def test_create_view_exige_maquina_para_categoria_de_parada(self):
        categoria = CategoriaLaboratorio.objects.create(
            nome="Parada de Maquina",
            impacto=CategoriaLaboratorio.IMPACTO_ALTO,
        )

        response = self.client.post(
            reverse("laboratorio:ocorrencia_create"),
            {
                "data_abertura": timezone.localtime(timezone.now()).replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M"),
                "responsavel": self.user.pk,
                "categoria": categoria.pk,
                "assunto": "Parada da prensa 02",
                "impacto": categoria.impacto,
                "detalhamento": "Sem equipamento alternativo.",
                "consequencias": "Aguardando manutencao.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Selecione a maquina vinculada a esta ocorrencia.")
        self.assertFalse(OcorrenciaLaboratorio.objects.filter(assunto="Parada da prensa 02").exists())

    def test_dashboard_exibe_ocorrencias_filtradas(self):
        categoria = CategoriaLaboratorio.objects.create(
            nome="Controle ambiental",
            impacto=CategoriaLaboratorio.IMPACTO_MEDIO,
        )
        abertura = timezone.now()
        ocorrencia_encerrada = OcorrenciaLaboratorio.objects.create(
            categoria=categoria,
            assunto="Oscilacao de temperatura",
            detalhamento="Registro fora da faixa esperada por 20 minutos.",
            consequencias="Analise interrompida para ajuste.",
            impacto=CategoriaLaboratorio.IMPACTO_MEDIO,
            responsavel=self.user,
            data_abertura=abertura,
            data_encerramento=abertura + timedelta(minutes=20),
            perda_producao=Decimal("15.50"),
            unidade_perda_producao="analises",
            horas_indisponibilidade=Decimal("1.50"),
            impacto_financeiro=Decimal("1200.00"),
            observacoes_encerramento="Amostras repriorizadas para recompor o fluxo.",
        )
        ocorrencia_aberta = OcorrenciaLaboratorio.objects.create(
            assunto="Revisao de reagente em andamento",
            detalhamento="Lote em conferencia antes da liberacao.",
            consequencias="Aguardando validacao final.",
            impacto=CategoriaLaboratorio.IMPACTO_BAIXO,
            responsavel=self.user,
            data_abertura=abertura,
        )

        response = self.client.get(
            reverse("laboratorio:dashboard"),
            {
                "inicio": abertura.date().strftime("%Y-%m-%d"),
                "fim": abertura.date().strftime("%Y-%m-%d"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Painel gerencial de ocorrencias")
        self.assertContains(response, "Resumo executivo")
        self.assertEqual(response.context["total"], 2)
        self.assertEqual(response.context["abertas"], 1)
        self.assertEqual(response.context["encerradas"], 1)
        self.assertEqual(response.context["por_categoria"][0]["nome"], categoria.nome)
        self.assertIn(
            ocorrencia_encerrada,
            [item["obj"] for g in response.context["ocorrencias_recentes_por_categoria"] for item in g["ocorrencias"]]
        )
        self.assertEqual(response.context["total_absenteismo_horas"], Decimal("0"))
        self.assertContains(response, "Ocorrencias recentes por categoria no periodo filtrado")
        self.assertContains(response, "<th>Informacao</th>", html=True)
        self.assertContains(response, "<th>Detalhamento</th>", html=True)
        self.assertNotContains(response, "<th>Responsavel</th>", html=True)
        self.assertContains(response, reverse("laboratorio:ocorrencia_detail", args=[ocorrencia_encerrada.pk]))
        self.assertContains(response, "modal=encerramento")

    def test_dashboard_calcula_absenteismo_a_partir_de_faltas_de_colaborador(self):
        categoria_falta = CategoriaLaboratorio.objects.create(
            nome="Falta de colaborador",
            impacto=CategoriaLaboratorio.IMPACTO_MEDIO,
        )
        categoria_outros = CategoriaLaboratorio.objects.create(
            nome="Parada de maquina",
            impacto=CategoriaLaboratorio.IMPACTO_ALTO,
        )
        abertura = timezone.now().replace(second=0, microsecond=0)

        OcorrenciaLaboratorio.objects.create(
            categoria=categoria_falta,
            assunto="Falta de colaborador no turno A",
            detalhamento="Ausencia durante o primeiro turno.",
            consequencias="Redistribuicao da equipe.",
            impacto=categoria_falta.impacto,
            responsavel=self.user,
            data_abertura=abertura,
            data_encerramento=abertura + timedelta(hours=8),
            horas_indisponibilidade=Decimal("1.50"),
        )
        OcorrenciaLaboratorio.objects.create(
            categoria=categoria_outros,
            assunto="Parada de equipamento",
            detalhamento="Falha mecanica no equipamento.",
            consequencias="Interrupcao parcial da bancada.",
            impacto=categoria_outros.impacto,
            responsavel=self.user,
            data_abertura=abertura,
            data_encerramento=abertura + timedelta(hours=4),
            horas_indisponibilidade=Decimal("10.00"),
        )

        response = self.client.get(
            reverse("laboratorio:dashboard"),
            {
                "inicio": abertura.date().strftime("%Y-%m-%d"),
                "fim": abertura.date().strftime("%Y-%m-%d"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_absenteismo_horas"], Decimal("8"))
        self.assertContains(response, "Absenteismo (h)")
        self.assertNotContains(response, "Colaborador ausente:")

    def test_dashboard_filtra_por_semana_com_sobreposicao_de_encerramento(self):
        categoria = CategoriaLaboratorio.objects.create(
            nome="Controle ambiental",
            impacto=CategoriaLaboratorio.IMPACTO_MEDIO,
        )

        OcorrenciaLaboratorio.objects.create(
            categoria=categoria,
            assunto="Encerrada na semana",
            detalhamento="Abriu antes e encerrou na semana.",
            consequencias="Deve entrar no dashboard semanal.",
            impacto=CategoriaLaboratorio.IMPACTO_MEDIO,
            responsavel=self.user,
            data_abertura=datetime(2026, 4, 26, 9, 0, tzinfo=timezone.get_current_timezone()),
            data_encerramento=datetime(2026, 4, 29, 12, 0, tzinfo=timezone.get_current_timezone()),
        )
        OcorrenciaLaboratorio.objects.create(
            categoria=categoria,
            assunto="Aberta na semana",
            detalhamento="Registrada dentro da semana selecionada.",
            consequencias="Tambem deve entrar.",
            impacto=CategoriaLaboratorio.IMPACTO_BAIXO,
            responsavel=self.user,
            data_abertura=datetime(2026, 5, 1, 14, 0, tzinfo=timezone.get_current_timezone()),
        )
        OcorrenciaLaboratorio.objects.create(
            categoria=categoria,
            assunto="Fora do recorte semanal",
            detalhamento="Nao cruza a semana solicitada.",
            consequencias="Nao deve aparecer.",
            impacto=CategoriaLaboratorio.IMPACTO_ALTO,
            responsavel=self.user,
            data_abertura=datetime(2026, 5, 8, 10, 0, tzinfo=timezone.get_current_timezone()),
        )

        response = self.client.get(
            reverse("laboratorio:dashboard"),
            {"semana": "2026-W18"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total"], 2)
        self.assertEqual(response.context["inicio"], "2026-04-27")
        self.assertEqual(response.context["fim"], "2026-05-03")
        self.assertContains(response, "Abriu antes e encerrou na semana.")
        self.assertContains(response, "Registrada dentro da semana selecionada.")
        self.assertNotContains(response, "Nao cruza a semana solicitada.")
        self.assertContains(response, 'id="dashboard-semana-picker"')
        self.assertContains(response, "Semana 18/2026 (27/04/2026 a 03/05/2026)")
        self.assertContains(response, "Limpar filtros")

    def test_dashboard_exporta_pdf_com_filtros(self):
        categoria = CategoriaLaboratorio.objects.create(
            nome="Controle ambiental",
            impacto=CategoriaLaboratorio.IMPACTO_MEDIO,
        )
        abertura = timezone.now().replace(second=0, microsecond=0)

        OcorrenciaLaboratorio.objects.create(
            categoria=categoria,
            assunto="Registro para PDF",
            detalhamento="Ocorrencia usada para validar exportacao em PDF.",
            consequencias="Sem consequencias criticas.",
            impacto=categoria.impacto,
            responsavel=self.user,
            data_abertura=abertura,
        )

        response = self.client.get(
            reverse("laboratorio:dashboard_pdf"),
            {
                "inicio": abertura.date().strftime("%Y-%m-%d"),
                "fim": abertura.date().strftime("%Y-%m-%d"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))

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
        self.assertContains(detail_response, reverse("laboratorio:ocorrencia_notes", args=[ocorrencia.pk]))

    def test_listagem_filtra_por_categoria(self):
        categoria_parada = CategoriaLaboratorio.objects.create(
            nome="Parada de maquina",
            impacto=CategoriaLaboratorio.IMPACTO_ALTO,
        )
        categoria_colaborador = CategoriaLaboratorio.objects.create(
            nome="Falta de colaborador",
            impacto=CategoriaLaboratorio.IMPACTO_MEDIO,
        )
        abertura = timezone.now().replace(second=0, microsecond=0)

        OcorrenciaLaboratorio.objects.create(
            categoria=categoria_parada,
            assunto="Ocorrencia da categoria parada",
            detalhamento="Linha interrompida por falha mecanica.",
            consequencias="Producao impactada.",
            impacto=categoria_parada.impacto,
            responsavel=self.user,
            data_abertura=abertura,
        )
        OcorrenciaLaboratorio.objects.create(
            categoria=categoria_colaborador,
            assunto="Ocorrencia da categoria colaborador",
            detalhamento="Ausencia no turno da noite.",
            consequencias="Redistribuicao da equipe.",
            impacto=categoria_colaborador.impacto,
            responsavel=self.user,
            data_abertura=abertura - timedelta(hours=1),
        )

        response = self.client.get(
            reverse("laboratorio:ocorrencias_list"),
            {"categoria": categoria_parada.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ocorrencia da categoria parada")
        self.assertNotContains(response, "Ocorrencia da categoria colaborador")
        self.assertEqual(response.context["filtros"]["categoria"], str(categoria_parada.pk))
        self.assertEqual(response.context["total_filtrados"], 1)
        self.assertEqual(response.context["total_registros"], 2)

    def test_listagem_filtra_por_semana_considerando_abertura_ou_encerramento_na_semana(self):
        semana_referencia = date.fromisocalendar(2026, 18, 1)
        categoria = CategoriaLaboratorio.objects.create(
            nome="Parada de maquina",
            impacto=CategoriaLaboratorio.IMPACTO_ALTO,
        )

        OcorrenciaLaboratorio.objects.create(
            categoria=categoria,
            assunto="Encerrada dentro da semana",
            detalhamento="Iniciou antes da semana e encerrou dentro dela.",
            consequencias="Entrou no consolidado semanal.",
            impacto=categoria.impacto,
            responsavel=self.user,
            data_abertura=datetime(2026, 4, 26, 8, 0, tzinfo=timezone.get_current_timezone()),
            data_encerramento=datetime(2026, 4, 29, 17, 0, tzinfo=timezone.get_current_timezone()),
        )
        OcorrenciaLaboratorio.objects.create(
            categoria=categoria,
            assunto="Aberta durante a semana",
            detalhamento="Registrada no meio da semana filtrada.",
            consequencias="Tambem precisa aparecer.",
            impacto=categoria.impacto,
            responsavel=self.user,
            data_abertura=datetime(2026, 4, 30, 9, 30, tzinfo=timezone.get_current_timezone()),
        )
        OcorrenciaLaboratorio.objects.create(
            categoria=categoria,
            assunto="Fora da semana",
            detalhamento="Nao cruza a semana informada.",
            consequencias="Nao deve aparecer.",
            impacto=categoria.impacto,
            responsavel=self.user,
            data_abertura=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.get_current_timezone()),
        )

        response = self.client.get(
            reverse("laboratorio:ocorrencias_list"),
            {"semana": semana_referencia.strftime("%G-W%V")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Encerrada dentro da semana")
        self.assertContains(response, "Aberta durante a semana")
        self.assertNotContains(response, "Fora da semana")
        self.assertEqual(response.context["filtros"]["semana"], "2026-W18")
        self.assertContains(response, 'id="semana-picker"')
        self.assertContains(response, "Semana 18/2026 (27/04/2026 a 03/05/2026)")

    def test_detail_view_registra_anotacoes_por_modal_com_autor_e_historico(self):
        ocorrencia = OcorrenciaLaboratorio.objects.create(
            assunto="Acompanhamento de analise",
            detalhamento="Necessidade de observacao adicional na bancada.",
            consequencias="Sem impacto imediato.",
            impacto=CategoriaLaboratorio.IMPACTO_BAIXO,
            responsavel=self.user,
            data_abertura=timezone.now().replace(second=0, microsecond=0),
        )
        outro_usuario = get_user_model().objects.create_user(
            username="lab.coordenador",
            password="senha-forte-456",
            first_name="Laura",
            last_name="Coordenadora",
        )

        response = self.client.post(
            reverse("laboratorio:ocorrencia_notes", args=[ocorrencia.pk]),
            {"texto": "Primeira anotacao gerencial registrada."},
        )

        self.assertRedirects(response, reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk]))

        self.client.force_login(outro_usuario)
        segundo_response = self.client.post(
            reverse("laboratorio:ocorrencia_notes", args=[ocorrencia.pk]),
            {"texto": "Segunda anotacao com novo responsavel."},
        )

        self.assertRedirects(segundo_response, reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk]))
        anotacoes = list(OcorrenciaLaboratorioAnotacao.objects.filter(ocorrencia=ocorrencia))
        self.assertEqual(len(anotacoes), 2)
        self.assertEqual(anotacoes[0].texto, "Segunda anotacao com novo responsavel.")
        self.assertEqual(anotacoes[0].usuario, outro_usuario)
        self.assertIsNotNone(anotacoes[0].criado_em)
        self.assertEqual(anotacoes[1].texto, "Primeira anotacao gerencial registrada.")
        self.assertEqual(anotacoes[1].usuario, self.user)

        detail_response = self.client.get(reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk]))
        self.assertContains(detail_response, "Primeira anotacao gerencial registrada.")
        self.assertContains(detail_response, "Segunda anotacao com novo responsavel.")
        self.assertContains(detail_response, outro_usuario.get_full_name())
        self.assertContains(detail_response, anotacoes[0].criado_em.strftime("%d/%m/%Y"))

    def test_encerramento_rapido_define_data_e_duracao(self):
        abertura = timezone.now().replace(second=0, microsecond=0) - timedelta(hours=2, minutes=10)
        ocorrencia = OcorrenciaLaboratorio.objects.create(
            assunto="Interrupcao temporaria de leitura",
            detalhamento="Parada para ajuste de configuracao.",
            consequencias="Fila de processamento reorganizada.",
            impacto=CategoriaLaboratorio.IMPACTO_MEDIO,
            criado_por=self.user,
            responsavel=self.user,
            data_abertura=abertura,
        )

        response = self.client.post(
            reverse("laboratorio:ocorrencia_close", args=[ocorrencia.pk]),
            {
                "next": reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk]),
                "data_encerramento": timezone.localtime(timezone.now()).replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M"),
                "registrar_medidas": "on",
                "perda_producao": "8.00",
                "unidade_perda_producao": "analises",
                "horas_indisponibilidade": "2.17",
                "impacto_financeiro": "850.00",
                "observacoes_encerramento": "Plano de contingencia acionado e fila regularizada.",
            },
        )

        self.assertRedirects(response, reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk]))
        ocorrencia.refresh_from_db()
        self.assertIsNotNone(ocorrencia.data_encerramento)
        self.assertIsNotNone(ocorrencia.duracao)
        self.assertGreaterEqual(ocorrencia.duracao, timedelta(hours=2, minutes=10))
        self.assertEqual(ocorrencia.perda_producao, Decimal("8.00"))
        self.assertEqual(ocorrencia.unidade_perda_producao, "analises")
        self.assertEqual(ocorrencia.impacto_financeiro, Decimal("850.00"))

    def test_encerramento_aceita_apenas_data_e_observacoes(self):
        abertura = timezone.now().replace(second=0, microsecond=0) - timedelta(minutes=45)
        ocorrencia = OcorrenciaLaboratorio.objects.create(
            assunto="Ajuste simples",
            detalhamento="Ocorrencia para validar fechamento minimo.",
            consequencias="Sem perdas numericas.",
            impacto=CategoriaLaboratorio.IMPACTO_BAIXO,
            criado_por=self.user,
            responsavel=self.user,
            data_abertura=abertura,
        )

        response = self.client.post(
            reverse("laboratorio:ocorrencia_close", args=[ocorrencia.pk]),
            {
                "next": reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk]),
                "data_encerramento": timezone.localtime(timezone.now()).replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M"),
                "observacoes_encerramento": "Encerramento sem necessidade de registrar medidas.",
            },
        )

        self.assertRedirects(response, reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk]))
        ocorrencia.refresh_from_db()
        self.assertIsNotNone(ocorrencia.data_encerramento)
        self.assertEqual(ocorrencia.observacoes_encerramento, "Encerramento sem necessidade de registrar medidas.")
        self.assertIsNone(ocorrencia.perda_producao)
        self.assertEqual(ocorrencia.unidade_perda_producao, "")
        self.assertIsNone(ocorrencia.horas_indisponibilidade)
        self.assertIsNone(ocorrencia.impacto_financeiro)

    def test_encerramento_exige_data_posterior_a_abertura(self):
        abertura = timezone.now().replace(second=0, microsecond=0)
        ocorrencia = OcorrenciaLaboratorio.objects.create(
            assunto="Validacao de data",
            detalhamento="Ocorrencia para validar encerramento posterior.",
            consequencias="Sem consequencias.",
            impacto=CategoriaLaboratorio.IMPACTO_MEDIO,
            criado_por=self.user,
            responsavel=self.user,
            data_abertura=abertura,
        )

        response = self.client.post(
            reverse("laboratorio:ocorrencia_close", args=[ocorrencia.pk]),
            {
                "next": reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk]),
                "data_encerramento": timezone.localtime(abertura).strftime("%Y-%m-%dT%H:%M"),
                "observacoes_encerramento": "Tentativa invalida.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "O encerramento deve ser posterior a abertura.")
        ocorrencia.refresh_from_db()
        self.assertIsNone(ocorrencia.data_encerramento)

    def test_encerramento_so_aparece_para_criador_ou_staff(self):
        criador = get_user_model().objects.create_user(
            username="lab.criador",
            password="senha-forte-456",
        )
        intruso = get_user_model().objects.create_user(
            username="lab.intruso",
            password="senha-forte-789",
        )
        ocorrencia = OcorrenciaLaboratorio.objects.create(
            assunto="Bloqueio de encerramento",
            detalhamento="Ocorrencia aberta para validar permissao de encerramento.",
            consequencias="Sem consequencias.",
            impacto=CategoriaLaboratorio.IMPACTO_MEDIO,
            criado_por=criador,
            responsavel=criador,
            data_abertura=timezone.now().replace(second=0, microsecond=0),
        )

        self.client.force_login(intruso)
        detail_response = self.client.get(reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk]))
        self.assertNotContains(detail_response, "Encerrar agora")

        response = self.client.post(
            reverse("laboratorio:ocorrencia_close", args=[ocorrencia.pk]),
            {
                "next": reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk]),
                "data_encerramento": (timezone.localtime(timezone.now()) + timedelta(minutes=10)).replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M"),
                "observacoes_encerramento": "Tentativa sem permissao.",
            },
        )

        self.assertRedirects(response, reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk]))
        ocorrencia.refresh_from_db()
        self.assertIsNone(ocorrencia.data_encerramento)

    def test_criador_regular_pode_encerrar_e_staff_pode_sobrescrever(self):
        criador = get_user_model().objects.create_user(
            username="lab.autor",
            password="senha-forte-456",
        )
        ocorrencia = OcorrenciaLaboratorio.objects.create(
            assunto="Encerramento pelo criador",
            detalhamento="Ocorrencia aberta para validar criador.",
            consequencias="Sem consequencias.",
            impacto=CategoriaLaboratorio.IMPACTO_BAIXO,
            criado_por=criador,
            responsavel=criador,
            data_abertura=timezone.now().replace(second=0, microsecond=0) - timedelta(minutes=30),
        )

        self.client.force_login(criador)
        response = self.client.post(
            reverse("laboratorio:ocorrencia_close", args=[ocorrencia.pk]),
            {
                "next": reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk]),
                "data_encerramento": timezone.localtime(timezone.now()).replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M"),
                "observacoes_encerramento": "Fechamento pelo proprio criador.",
            },
        )

        self.assertRedirects(response, reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk]))
        ocorrencia.refresh_from_db()
        self.assertIsNotNone(ocorrencia.data_encerramento)

        ocorrencia.data_encerramento = None
        ocorrencia.observacoes_encerramento = ""
        ocorrencia.save(update_fields=["data_encerramento", "observacoes_encerramento", "duracao", "atualizado_em"])

        self.client.force_login(self.user)
        staff_response = self.client.post(
            reverse("laboratorio:ocorrencia_close", args=[ocorrencia.pk]),
            {
                "next": reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk]),
                "data_encerramento": timezone.localtime(timezone.now()).replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M"),
                "observacoes_encerramento": "Fechamento por staff.",
            },
        )

        self.assertRedirects(staff_response, reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk]))
        ocorrencia.refresh_from_db()
        self.assertIsNotNone(ocorrencia.data_encerramento)

    def test_detail_view_exibe_botao_excluir_e_remove_ocorrencia(self):
        ocorrencia = OcorrenciaLaboratorio.objects.create(
            assunto="Teste de exclusao",
            detalhamento="Ocorrencia criada para validar exclusao.",
            consequencias="Sem consequencias adicionais.",
            impacto=CategoriaLaboratorio.IMPACTO_BAIXO,
            responsavel=self.user,
            data_abertura=timezone.now().replace(second=0, microsecond=0),
        )

        detail_response = self.client.get(reverse("laboratorio:ocorrencia_detail", args=[ocorrencia.pk]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, reverse("laboratorio:ocorrencia_delete", args=[ocorrencia.pk]))

        delete_response = self.client.post(reverse("laboratorio:ocorrencia_delete", args=[ocorrencia.pk]))
        self.assertRedirects(delete_response, reverse("laboratorio:ocorrencias_list"))
        self.assertFalse(OcorrenciaLaboratorio.objects.filter(pk=ocorrencia.pk).exists())

    def test_update_view_exibe_botao_excluir(self):
        ocorrencia = OcorrenciaLaboratorio.objects.create(
            assunto="Teste botao excluir na edicao",
            detalhamento="Ocorrencia criada para validar o botao de exclusao na tela de edicao.",
            consequencias="Sem consequencias adicionais.",
            impacto=CategoriaLaboratorio.IMPACTO_BAIXO,
            responsavel=self.user,
            data_abertura=timezone.now().replace(second=0, microsecond=0),
        )

        response = self.client.get(reverse("laboratorio:ocorrencia_update", args=[ocorrencia.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("laboratorio:ocorrencia_delete", args=[ocorrencia.pk]), count=2)
        self.assertContains(response, "Excluir ocorrencia", count=2)
