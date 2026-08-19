"""Unit tests for qms.forms_historico (PDF validation and history form)."""
from datetime import date

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from qms.forms_historico import (
    HistoricoCalibracaoForm,
    MultipleFileInput,
    validate_pdf_file,
)


def _pdf(
    name="cert.pdf", content=b"%PDF-1.4 data", content_type="application/pdf", size=None
):
    """Build a SimpleUploadedFile, optionally overriding its reported size."""
    f = SimpleUploadedFile(name, content, content_type=content_type)
    if size is not None:
        f.size = size
    return f


class MultipleFileInputTests(TestCase):
    """Tests for the multi-upload file widget."""

    def test_allows_multiple_selected(self):
        """The widget advertises support for multiple files."""
        self.assertTrue(MultipleFileInput.allow_multiple_selected)


class ValidatePdfFileTests(TestCase):
    """Tests for the validate_pdf_file helper."""

    def test_valid_pdf_returns_file(self):
        """A valid PDF is returned unchanged."""
        f = _pdf()
        self.assertIs(validate_pdf_file(f), f)

    def test_case_insensitive_extension(self):
        """An uppercase .PDF extension is accepted."""
        f = _pdf(name="CERT.PDF")
        self.assertIs(validate_pdf_file(f), f)

    def test_rejects_non_pdf_extension(self):
        """A non-PDF extension raises ValidationError."""
        with self.assertRaises(ValidationError):
            validate_pdf_file(_pdf(name="doc.txt", content_type="text/plain"))

    def test_rejects_invalid_content_type(self):
        """An unrelated content type raises ValidationError."""
        f = _pdf(name="cert.pdf", content_type="image/png")
        with self.assertRaises(ValidationError):
            validate_pdf_file(f)

    def test_accepts_content_type_containing_pdf(self):
        """A content type containing 'pdf' is accepted."""
        f = _pdf(name="cert.pdf", content_type="application/x-pdf")
        self.assertIs(validate_pdf_file(f), f)

    def test_rejects_oversized_file(self):
        """A file larger than the 50MB limit raises ValidationError."""
        f = _pdf(size=51 * 1024 * 1024)
        with self.assertRaises(ValidationError):
            validate_pdf_file(f)


class HistoricoCalibracaoFormTests(TestCase):
    """Tests for the calibration-history form."""

    def _base_data(self):
        """Return the minimal valid form payload."""
        return {
            "data_calibracao": date(2024, 1, 10),
            "numero_certificado": "CERT-001",
            "tipo_calibracao": "EXTERNA",
        }

    def test_valid_without_certificate(self):
        """The form is valid without an attached certificate."""
        form = HistoricoCalibracaoForm(data=self._base_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_optional_resultado_and_data_aprovacao(self):
        """Result and approval date fields are optional."""
        form = HistoricoCalibracaoForm(data=self._base_data())
        self.assertFalse(form.fields["resultado"].required)
        self.assertFalse(form.fields["data_aprovacao"].required)

    def test_clean_certificado_rejects_non_pdf(self):
        """A non-PDF certificate upload is rejected."""
        files = {"certificado": _pdf(name="bad.txt", content_type="text/plain")}
        form = HistoricoCalibracaoForm(data=self._base_data(), files=files)
        self.assertFalse(form.is_valid())
        self.assertIn("certificado", form.errors)

    def test_clean_certificado_accepts_pdf(self):
        """A valid PDF certificate upload is accepted."""
        files = {"certificado": _pdf()}
        form = HistoricoCalibracaoForm(data=self._base_data(), files=files)
        self.assertTrue(form.is_valid(), form.errors)
