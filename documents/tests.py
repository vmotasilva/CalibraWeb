import pytest
from django.test import TestCase


# NOTE: Documents module models are currently in qms (legacy monolithic structure)
# See ARCHITECTURE_MIGRATION_NOTES.md for details on the modularization status

class DocumentsProcedimentoTests(TestCase):
    """Test Procedimento model"""
    
    def setUp(self):
        """Create test data"""
        self.procedimento = self._create_procedimento()
    
    def _create_procedimento(
        self,
        codigo="PROC.001",
        nome="Teste Procedimento",
        classificacao="POP"
    ):
        """Helper to create Procedimento"""
        from qms.models import Procedimento
        return Procedimento.objects.create(
            codigo=codigo,
            nome=nome,
            classificacao=classificacao
        )
    
    def test_procedimento_creation(self):
        """Test Procedimento can be created"""
        self.assertEqual(self.procedimento.codigo, "PROC.001")
        self.assertEqual(self.procedimento.nome, "Teste Procedimento")
        self.assertIsNotNone(self.procedimento.id)
    
    def test_procedimento_string_representation(self):
        """Test Procedimento __str__ method"""
        self.assertIn("PROC.001", str(self.procedimento))
    
    def test_procedimento_classificacao_assignment(self):
        """Test Procedimento classificacao"""
        self.assertEqual(self.procedimento.classificacao, "POP")
    
    def test_multiple_procedimentos_creation(self):
        """Test creating multiple procedures"""
        from qms.models import Procedimento
        procs = [
            {"codigo": "DOC.001", "nome": "Documento 1", "classificacao": "DOC"},
            {"codigo": "FOR.001", "nome": "Formulário 1", "classificacao": "FOR"},
        ]
        for proc_data in procs:
            p = Procedimento.objects.create(**proc_data)
            self.assertIsNotNone(p.id)
        
        self.assertEqual(Procedimento.objects.count(), 3)  # 2 + setUp


class DocumentsProcedimentoRevisaoTests(TestCase):
    """Test ProcedimentoRevisao model"""
    
    def setUp(self):
        """Create test data"""
        self.procedimento = self._create_procedimento()
    
    def _create_procedimento(self):
        """Helper to create Procedimento"""
        from qms.models import Procedimento
        return Procedimento.objects.create(
            codigo="REV.001",
            nome="Revisable Procedure"
        )
    
    def test_procedimento_revisao_creation(self):
        """Test ProcedimentoRevisao can be created"""
        from qms.models import ProcedimentoRevisao
        revisao = ProcedimentoRevisao.objects.create(
            procedimento=self.procedimento,
            numero_revisao="01"
        )
        self.assertEqual(revisao.numero_revisao, "01")
        self.assertIsNotNone(revisao.id)
    
    def test_procedimento_revisao_relationship(self):
        """Test ProcedimentoRevisao relationships"""
        from qms.models import ProcedimentoRevisao
        revisao = ProcedimentoRevisao.objects.create(
            procedimento=self.procedimento,
            numero_revisao="02"
        )
        self.assertEqual(revisao.procedimento, self.procedimento)


class DocumentsAreaTests(TestCase):
    """Test Area model for procedure areas"""
    
    def test_area_creation(self):
        """Test Area can be created"""
        from qms.models import Area
        area = Area.objects.create(
            nome="Qualidade",
            descricao="Área de Qualidade e Processos"
        )
        self.assertEqual(area.nome, "Qualidade")
        self.assertIsNotNone(area.id)
    
    def test_area_string_representation(self):
        """Test Area __str__ method"""
        from qms.models import Area
        area = Area.objects.create(nome="RH", descricao="Recursos Humanos")
        self.assertEqual(str(area), "RH")
    
    def test_multiple_areas_creation(self):
        """Test creating multiple areas"""
        from qms.models import Area
        areas = [
            {"nome": "Operações", "descricao": "Área de Operações"},
            {"nome": "Logística", "descricao": "Área de Logística"},
        ]
        for area_data in areas:
            a = Area.objects.create(**area_data)
            self.assertIsNotNone(a.id)
        
        self.assertEqual(Area.objects.count(), 2)


class DocumentsRegistroTreinamentoTests(TestCase):
    """Test RegistroTreinamento model"""
    
    def setUp(self):
        """Create test data"""
        self.colaborador = self._create_colaborador()
        self.procedimento = self._create_procedimento()
    
    def _create_colaborador(self):
        """Helper to create Colaborador"""
        from qms.models import Colaborador, Setor
        setor = Setor.objects.create(nome="TEST", turno="ADM")
        return Colaborador.objects.create(
            matricula="999",
            nome_completo="Test User",
            setor=setor
        )
    
    def _create_procedimento(self):
        """Helper to create Procedimento"""
        from qms.models import Procedimento
        return Procedimento.objects.create(
            codigo="TRAIN.001",
            nome="Treinamento"
        )
    
    def test_registro_treinamento_creation(self):
        """Test RegistroTreinamento can be created"""
        from qms.models import RegistroTreinamento
        from datetime import date
        
        registro = RegistroTreinamento.objects.create(
            colaborador=self.colaborador,
            procedimento=self.procedimento,
            data_treinamento=date.today()
        )
        self.assertIsNotNone(registro.id)
    
    def test_registro_treinamento_relationships(self):
        """Test RegistroTreinamento relationships"""
        from qms.models import RegistroTreinamento
        from datetime import date
        
        registro = RegistroTreinamento.objects.create(
            colaborador=self.colaborador,
            procedimento=self.procedimento,
            data_treinamento=date.today()
        )
        self.assertEqual(registro.colaborador, self.colaborador)
        self.assertEqual(registro.procedimento, self.procedimento)


class DocumentsPacoteTreinamentoTests(TestCase):
    """Test PacoteTreinamento model"""
    
    def test_pacote_treinamento_creation(self):
        """Test PacoteTreinamento can be created"""
        from qms.models import PacoteTreinamento
        pacote = PacoteTreinamento.objects.create(
            nome="Pacote Inicial",
            descricao="Treinamentos obrigatórios para todos"
        )
        self.assertEqual(pacote.nome, "Pacote Inicial")
        self.assertIsNotNone(pacote.id)
    
    def test_pacote_treinamento_string_representation(self):
        """Test PacoteTreinamento __str__ method"""
        from qms.models import PacoteTreinamento
        pacote = PacoteTreinamento.objects.create(
            nome="Pacote Avançado"
        )
        self.assertEqual(str(pacote), "Pacote Avançado")
    
    def test_pacote_treinamento_procedures_relationship(self):
        """Test PacoteTreinamento procedures relationship"""
        from qms.models import PacoteTreinamento, Procedimento
        
        pacote = PacoteTreinamento.objects.create(nome="Test Package")
        proc1 = Procedimento.objects.create(codigo="P1", nome="Proc 1")
        proc2 = Procedimento.objects.create(codigo="P2", nome="Proc 2")
        
        pacote.procedimentos.add(proc1, proc2)
        self.assertEqual(pacote.procedimentos.count(), 2)
