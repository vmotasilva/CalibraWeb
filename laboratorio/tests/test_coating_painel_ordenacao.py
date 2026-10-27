from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from laboratorio.models import RegistroCoating, RegraTurnoCoating, TratamentoAntiReflexo, TurnoCoating
from maquinas.models import CategoriaMaquina, Maquina
from organization.models import Setor


class CoatingPainelOrdenacaoTests(TestCase):
    """Painel ordena por lote decrescente por padrão e aceita ordenar pelas demais colunas."""

    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser(username="coating.ordem", password="x"))
        regra = RegraTurnoCoating.objects.create(nome="Turno 01", hora_inicio=time(0, 0), hora_fim=time(23, 59))
        turno = TurnoCoating.objects.create(data=timezone.localdate(), regra=regra)
        maquina = Maquina.objects.create(
            codigo="DLX1200",
            categoria=CategoriaMaquina.objects.create(nome="Evaporadora"),
            setor=Setor.objects.create(nome="Coating"),
        )
        base = timezone.make_aware(datetime.combine(timezone.localdate(), time(8, 0)))
        # lote -> (tratamento, minutos após as 08:00 da entrada, duração em minutos)
        dados = {101: ("CRIZAL", 60, 40), 102: ("AZUL", 0, 10), 103: ("BLUE CUT", 30, 90)}
        for lote, (trat, inicio, duracao) in dados.items():
            tratamento, _ = TratamentoAntiReflexo.objects.get_or_create(nome=trat)
            for lado in ("CC", "CX"):
                RegistroCoating.objects.create(
                    turno_coating=turno, maquina=maquina, lote=lote, tratamento=tratamento, lado=lado,
                    hora_entrada=base + timedelta(minutes=inicio),
                    hora_saida=base + timedelta(minutes=inicio + duracao),
                )

    def _lotes(self, **params):
        response = self.client.get(reverse("laboratorio:coating_painel"), params)
        self.assertEqual(response.status_code, 200)
        return [(r.lote, r.lado) for r in response.context["registros"]], response

    def test_padrao_lote_decrescente(self):
        lotes, response = self._lotes()
        self.assertEqual(lotes, [(103, "CC"), (103, "CX"), (102, "CC"), (102, "CX"), (101, "CC"), (101, "CX")])
        self.assertTrue(response.context["ordenacao_padrao"])
        self.assertEqual(response.context["qs_ordenacao"], "")

    def test_parametro_invalido_volta_ao_padrao(self):
        lotes, _ = self._lotes(ordem="hackeado", dir="asc")
        self.assertEqual(lotes[0], (103, "CC"))

    def test_ordena_por_colunas(self):
        casos = {
            ("lote", "asc"): [101, 102, 103],
            ("tratamento", "asc"): [102, 103, 101],
            ("entrada", "asc"): [102, 103, 101],
            ("entrada", "desc"): [101, 103, 102],
            ("rodando", "desc"): [103, 101, 102],
        }
        for (ordem, direcao), esperado in casos.items():
            lotes, _ = self._lotes(ordem=ordem, dir=direcao)
            self.assertEqual([l for l, _ in lotes[::2]], esperado, (ordem, direcao))
            # CC e CX do mesmo lote continuam juntos
            self.assertEqual([lado for _, lado in lotes], ["CC", "CX"] * 3, (ordem, direcao))

    def test_ciclo_do_cabecalho_e_links_preservam_ordenacao(self):
        _, response = self._lotes()
        links = response.context["links_ordenacao"]
        self.assertIn("ordem=lote&dir=asc", links["lote"]["url"])
        self.assertIn("ordem=saida&dir=asc", links["saida"]["url"])

        _, response = self._lotes(ordem="saida", dir="asc", lote_search="10")
        links = response.context["links_ordenacao"]
        self.assertIn("ordem=saida&dir=desc", links["saida"]["url"])
        self.assertIn("lote_search=10", links["saida"]["url"])
        self.assertEqual(response.context["qs_ordenacao"], "&ordem=saida&dir=asc")
        # Abas de máquina mantêm a ordenação escolhida
        self.assertContains(response, "&amp;ordem=saida&amp;dir=asc")

        _, response = self._lotes(ordem="saida", dir="desc")
        self.assertNotIn("ordem=", response.context["links_ordenacao"]["saida"]["url"])


class CoatingPainelFiltrosTests(CoatingPainelOrdenacaoTests):
    """Pop-up de filtros: competência, turno, tratamento, preparação e montagem."""

    def test_filtra_por_tratamento_e_turno(self):
        trat = TratamentoAntiReflexo.objects.get(nome="AZUL")
        lotes, response = self._lotes(tratamento=trat.id)
        self.assertEqual({l for l, _ in lotes}, {102})
        self.assertEqual(response.context["filtros_ativos"], 1)
        self.assertContains(response, f"&amp;tratamento={trat.id}")

        regra = RegraTurnoCoating.objects.get()
        lotes, _ = self._lotes(turno=regra.id)
        self.assertEqual(len(lotes), 6)
        lotes, _ = self._lotes(turno=regra.id + 999)
        self.assertEqual(lotes, [])

    def test_filtra_por_competencia(self):
        hoje = timezone.localdate()
        lotes, response = self._lotes(competencia=f"{hoje.year}-{hoje.month:02d}")
        self.assertEqual(len(lotes), 6)
        self.assertEqual(response.context["competencias_opcoes"][0]["valor"], f"{hoje.year}-{hoje.month:02d}")
        lotes, _ = self._lotes(competencia="2000-01")
        self.assertEqual(lotes, [])

    def test_valores_invalidos_sao_ignorados(self):
        lotes, response = self._lotes(competencia="abc", turno="x", tratamento="'; drop")
        self.assertEqual(len(lotes), 6)
        self.assertEqual(response.context["filtros_ativos"], 0)


class CoatingDashboardFiltrosTests(CoatingPainelOrdenacaoTests):
    """Dashboard aceita os mesmos filtros do Painel."""

    def _dash(self, **params):
        response = self.client.get(reverse("laboratorio:dashboard_coating"), params)
        self.assertEqual(response.status_code, 200)
        return response

    def test_competencia_define_periodo_e_filtra(self):
        hoje = timezone.localdate()
        response = self._dash(competencia=f"{hoje.year}-{hoje.month:02d}")
        self.assertEqual(response.context["total_lotes"], 3)
        self.assertEqual(response.context["data_de"], hoje.replace(day=1).strftime("%Y-%m-%d"))
        response = self._dash(competencia="2000-01")
        self.assertEqual(response.context["total_lotes"], 0)

    def test_filtra_por_tratamento(self):
        trat = TratamentoAntiReflexo.objects.get(nome="AZUL")
        response = self._dash(tratamento=trat.id, periodo="30")
        self.assertEqual(response.context["total_lotes"], 1)
        self.assertEqual(response.context["tratamento_selecionado"], trat.id)

    def test_competencia_invalida_e_ignorada(self):
        response = self._dash(competencia="abc", tratamento="x")
        self.assertEqual(response.context["competencia"], "")
        self.assertEqual(response.context["total_lotes"], 3)
