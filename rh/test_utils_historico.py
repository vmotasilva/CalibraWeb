"""Unit tests for rh.utils_historico.GerenciadorHistoricoColaborador."""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from organization.models import Setor
from rh.models import (
    Colaborador,
    HistoricoColaborador,
    HistoricoPosto,
    HistoricoSalario,
    HistoricoSetor,
)
from rh.utils_historico import GerenciadorHistoricoColaborador


class GerenciadorHistoricoColaboradorTests(TestCase):
    """Tests for the change-history manager helper."""

    def setUp(self):
        """Create a collaborator and reference sectors."""
        self.setor_antigo = Setor.objects.create(nome="Producao", responsavel="Chefe")
        self.setor_novo = Setor.objects.create(nome="Qualidade", responsavel="Chefe Q")
        self.usuario = User.objects.create_user(username="rh_admin", password="x")
        self.colaborador = Colaborador.objects.create(
            matricula="MAT-100",
            nome_completo="Maria Souza",
            grupo="Producao",
            cargo="Operadora",
            setor=self.setor_antigo,
            turno="ADM",
            salario=Decimal("2000.00"),
            is_active=True,
        )

    def test_registrar_mudanca_setor_cria_dois_registros(self):
        """A sector change creates both a sector record and a general log."""
        GerenciadorHistoricoColaborador.registrar_mudanca_setor(
            self.colaborador,
            self.setor_novo,
            motivo="Promocao",
            usuario=self.usuario,
        )

        historico_setor = HistoricoSetor.objects.get(colaborador=self.colaborador)
        self.assertEqual(historico_setor.setor_anterior, self.setor_antigo)
        self.assertEqual(historico_setor.setor_novo, self.setor_novo)
        self.assertEqual(historico_setor.registrado_por, self.usuario)

        geral = HistoricoColaborador.objects.get(
            colaborador=self.colaborador, tipo_mudanca="SETOR"
        )
        self.assertIn("Promocao", geral.descricao)
        self.assertEqual(geral.dados_novos, {"setor": str(self.setor_novo)})

    def test_registrar_mudanca_setor_usa_data_padrao(self):
        """Without an explicit date the change uses today's date."""
        GerenciadorHistoricoColaborador.registrar_mudanca_setor(
            self.colaborador, self.setor_novo
        )
        historico = HistoricoSetor.objects.get(colaborador=self.colaborador)
        self.assertEqual(historico.data_efetiva, date.today())

    def test_registrar_mudanca_cargo(self):
        """A role change records old and new role values."""
        GerenciadorHistoricoColaborador.registrar_mudanca_cargo(
            self.colaborador, "Supervisora", motivo="Merito"
        )
        posto = HistoricoPosto.objects.get(colaborador=self.colaborador)
        self.assertEqual(posto.cargo_anterior, "Operadora")
        self.assertEqual(posto.cargo_novo, "Supervisora")

        geral = HistoricoColaborador.objects.get(
            colaborador=self.colaborador, tipo_mudanca="CARGO"
        )
        self.assertEqual(geral.dados_anteriores, {"cargo": "Operadora"})
        self.assertEqual(geral.dados_novos, {"cargo": "Supervisora"})

    def test_registrar_mudanca_salario_calcula_diferenca(self):
        """A salary change stores the computed difference."""
        GerenciadorHistoricoColaborador.registrar_mudanca_salario(
            self.colaborador, Decimal("2500.00"), motivo="Reajuste"
        )
        salario = HistoricoSalario.objects.get(colaborador=self.colaborador)
        self.assertEqual(salario.salario_anterior, Decimal("2000.00"))
        self.assertEqual(salario.salario_novo, Decimal("2500.00"))
        self.assertEqual(salario.diferenca, Decimal("500.00"))

        geral = HistoricoColaborador.objects.get(
            colaborador=self.colaborador, tipo_mudanca="SALARIO"
        )
        self.assertEqual(geral.dados_anteriores, {"salario": 2000.0})
        self.assertEqual(geral.dados_novos, {"salario": 2500.0})

    def test_registrar_mudanca_salario_sem_salario_anterior(self):
        """When there is no previous salary the difference is None."""
        colaborador = Colaborador.objects.create(
            matricula="MAT-200",
            nome_completo="Sem Salario",
            grupo="Producao",
            salario=None,
        )
        GerenciadorHistoricoColaborador.registrar_mudanca_salario(
            colaborador, Decimal("1800.00")
        )
        salario = HistoricoSalario.objects.get(colaborador=colaborador)
        self.assertIsNone(salario.diferenca)
        self.assertEqual(salario.salario_novo, Decimal("1800.00"))

    def test_registrar_mudanca_turno(self):
        """A shift change records old and new shift values."""
        GerenciadorHistoricoColaborador.registrar_mudanca_turno(
            self.colaborador, "NOTURNO", motivo="Escala"
        )
        geral = HistoricoColaborador.objects.get(
            colaborador=self.colaborador, tipo_mudanca="TURNO"
        )
        self.assertEqual(geral.dados_anteriores, {"turno": "ADM"})
        self.assertEqual(geral.dados_novos, {"turno": "NOTURNO"})

    def test_registrar_mudanca_status(self):
        """A status change records the active/inactive transition."""
        GerenciadorHistoricoColaborador.registrar_mudanca_status(
            self.colaborador, ativo=False, motivo="Desligamento"
        )
        geral = HistoricoColaborador.objects.get(
            colaborador=self.colaborador, tipo_mudanca="STATUS"
        )
        self.assertEqual(geral.dados_anteriores, {"is_active": True})
        self.assertEqual(geral.dados_novos, {"is_active": False})
        self.assertIn("Ativo", geral.descricao)
        self.assertIn("Inativo", geral.descricao)

    def test_obter_historico_resumido(self):
        """The summary returns the latest change per category and a count."""
        GerenciadorHistoricoColaborador.registrar_mudanca_setor(
            self.colaborador, self.setor_novo
        )
        GerenciadorHistoricoColaborador.registrar_mudanca_cargo(
            self.colaborador, "Lider"
        )
        resumo = GerenciadorHistoricoColaborador.obter_historico_resumido(
            self.colaborador
        )
        self.assertIsInstance(resumo, dict)
        self.assertIsNotNone(resumo["ultima_mudanca_setor"])
        self.assertIsNotNone(resumo["ultima_mudanca_cargo"])
        self.assertIsNone(resumo["ultima_mudanca_salario"])
        self.assertEqual(resumo["historico_geral_count"], 2)
