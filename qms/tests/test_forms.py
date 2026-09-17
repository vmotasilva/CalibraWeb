"""Unit tests for qms.forms (metrologia instrument/range ModelForms)."""
from decimal import Decimal

from django.test import TestCase

from core.models import UnidadeMedida
from qms.forms import FaixaMedicaoForm, InstrumentoForm, ResultadoFaixaCalibracaoForm


class InstrumentoFormTests(TestCase):
    """Tests for the instrument creation/edit form."""

    def test_valid_with_minimal_fields(self):
        """Only tag and description are required for validity."""
        form = InstrumentoForm(data={"tag": "LE-02", "descricao": "Paquimetro"})
        self.assertTrue(form.is_valid(), form.errors)

    def test_tag_is_required(self):
        """Missing tag makes the form invalid."""
        form = InstrumentoForm(data={"descricao": "Sem tag"})
        self.assertFalse(form.is_valid())
        self.assertIn("tag", form.errors)

    def test_descricao_is_required(self):
        """Missing description makes the form invalid."""
        form = InstrumentoForm(data={"tag": "LE-99"})
        self.assertFalse(form.is_valid())
        self.assertIn("descricao", form.errors)

    def test_tag_widget_has_bootstrap_class(self):
        """The tag widget is styled with a Bootstrap class."""
        form = InstrumentoForm()
        self.assertIn("form-control", form.fields["tag"].widget.attrs.get("class", ""))


class FaixaMedicaoFormTests(TestCase):
    """Tests for the measurement range form."""

    def setUp(self):
        """Create a measurement unit used by the range."""
        self.unidade = UnidadeMedida.objects.create(nome="mm")

    def test_valid_form(self):
        """A range with unit and min/max values is valid."""
        form = FaixaMedicaoForm(
            data={
                "unidade": self.unidade.pk,
                "valor_minimo": "0.0000",
                "valor_maximo": "150.0000",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_missing_required_fields(self):
        """Unit and both range bounds are required."""
        form = FaixaMedicaoForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn("unidade", form.errors)
        self.assertIn("valor_minimo", form.errors)
        self.assertIn("valor_maximo", form.errors)

    def test_optional_fields_allowed_blank(self):
        """Resolution, nominal and tolerance may be left blank."""
        form = FaixaMedicaoForm(
            data={
                "unidade": self.unidade.pk,
                "valor_minimo": "0",
                "valor_maximo": "10",
                "resolucao": "",
                "nominal": "",
                "tolerancia_mais_menos": "",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)


class ResultadoFaixaCalibracaoFormTests(TestCase):
    """Tests for the per-range calibration result form."""

    def test_resultado_not_required(self):
        """The result field is optional so it can be auto-computed."""
        form = ResultadoFaixaCalibracaoForm()
        self.assertFalse(form.fields["resultado"].required)

    def test_valid_when_all_blank(self):
        """All fields are optional, so an empty form is valid."""
        form = ResultadoFaixaCalibracaoForm(data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_with_values(self):
        """A form with numeric values cleans them into Decimals."""
        form = ResultadoFaixaCalibracaoForm(
            data={
                "tolerancia": "0.5000",
                "erro": "0.1000",
                "incerteza": "0.0500",
                "resultado": "APROVADO_SEM_CORRECAO",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["erro"], Decimal("0.1000"))
