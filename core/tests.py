import pytest
from django.test import TestCase


# NOTE: Core module models are currently in qms (legacy monolithic structure)
# See ARCHITECTURE_MIGRATION_NOTES.md for details on the modularization status
# For now, tests import from qms but validate core module functionality

class UnidadeMedidaTests(TestCase):
    """Test UnidadeMedida model (currently in qms, conceptually in core)"""
    
    def setUp(self):
        """Create test data"""
        self.unidade = self._create_unidade()
    
    def _create_unidade(self, nome="Milímetro", sigla="mm"):
        """Helper to create UnidadeMedida"""
        from qms.models import UnidadeMedida
        return UnidadeMedida.objects.create(nome=nome, sigla=sigla)
    
    def test_unidade_medida_creation(self):
        """Test UnidadeMedida can be created"""
        self.assertEqual(self.unidade.nome, "Milímetro")
        self.assertEqual(self.unidade.sigla, "mm")
    
    def test_unidade_medida_string_representation(self):
        """Test UnidadeMedida __str__ method"""
        expected = "Milímetro (mm)"
        self.assertEqual(str(self.unidade), expected)
    
    def test_unidade_medida_verbose_name(self):
        """Test UnidadeMedida verbose name"""
        from qms.models import UnidadeMedida
        self.assertEqual(UnidadeMedida._meta.verbose_name_plural, "Unidades de Medida")
    
    def test_multiple_unidades_creation(self):
        """Test creating multiple units"""
        from qms.models import UnidadeMedida
        units = [
            {"nome": "Volt", "sigla": "V"},
            {"nome": "Ampère", "sigla": "A"},
            {"nome": "Graus Celsius", "sigla": "°C"},
        ]
        for unit in units:
            u = UnidadeMedida.objects.create(**unit)
            self.assertIsNotNone(u.id)
        
        self.assertEqual(UnidadeMedida.objects.count(), 4)  # 3 + setUp


class CoreConstantsTests(TestCase):
    """Test constants defined in core module (currently in qms)"""
    
    def test_status_choices_defined(self):
        """Test STATUS_CHOICES is properly defined"""
        from qms.models import STATUS_CHOICES
        self.assertEqual(len(STATUS_CHOICES), 3)
        self.assertIn(("ATIVO", "Ativo"), STATUS_CHOICES)
        self.assertIn(("INATIVO", "Inativo"), STATUS_CHOICES)
    
    def test_turnos_choices_defined(self):
        """Test TURNOS_CHOICES is properly defined"""
        from qms.models import TURNOS_CHOICES
        self.assertEqual(len(TURNOS_CHOICES), 5)
        self.assertIn(("ADM", "Administrativo"), TURNOS_CHOICES)
        self.assertIn(("12X36", "12x36"), TURNOS_CHOICES)
