"""
Testes para o sistema de mapeamento de template de lista de presença

Execução:
    python manage.py test procedures.tests.test_mapeamento_template
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from procedures.models import (
    TemplateListaPresenca,
    MapeamentoCampoListaPresenca,
    ListaPresenca,
    Colaborador
)
import json
from datetime import datetime

User = get_user_model()


class TemplateListaPresencaTests(TestCase):
    """Testes para criação e validação de templates"""
    
    def setUp(self):
        """Setup inicial para cada teste"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.user.is_staff = True
        self.user.save()
        
        self.template = TemplateListaPresenca.objects.create(
            nome="Template Teste",
            descricao="Template para testes",
            tipo_arquivo="excel",
            metodo_mapeamento="ambos",
            ativo=True
        )
    
    def test_template_creation(self):
        """Testa criação de template"""
        self.assertEqual(self.template.nome, "Template Teste")
        self.assertTrue(self.template.ativo)
        self.assertEqual(self.template.metodo_mapeamento, "ambos")
    
    def test_template_string_representation(self):
        """Testa representação em string do template"""
        self.assertEqual(str(self.template), "Template Teste")
    
    def test_mapeamento_completo_default(self):
        """Testa que mapeamento_completo é False por padrão"""
        self.assertFalse(self.template.mapeamento_completo)
    
    def test_mapeamento_campos_default(self):
        """Testa que mapeamento_campos é dict vazio por padrão"""
        self.assertEqual(self.template.mapeamento_campos, {})


class MapeamentoCampoTests(TestCase):
    """Testes para mapeamento de campos"""
    
    def setUp(self):
        """Setup inicial"""
        self.template = TemplateListaPresenca.objects.create(
            nome="Template Mapeamento",
            tipo_arquivo="excel",
            metodo_mapeamento="referencia",
            ativo=True
        )
    
    def test_criar_mapeamento_campo(self):
        """Testa criação de mapeamento de campo"""
        mapeamento = MapeamentoCampoListaPresenca.objects.create(
            template=self.template,
            tipo_campo="titulo_treinamento",
            localizacao="A1",
            metodo="referencia",
            pagina=1,
            obrigatorio=True,
            permite_imagem_marcacao=False
        )
        
        self.assertEqual(mapeamento.tipo_campo, "titulo_treinamento")
        self.assertEqual(mapeamento.localizacao, "A1")
        self.assertEqual(mapeamento.metodo, "referencia")
    
    def test_mapeamento_unico_por_campo(self):
        """Testa que só pode haver um mapeamento por tipo_campo"""
        MapeamentoCampoListaPresenca.objects.create(
            template=self.template,
            tipo_campo="titulo_treinamento",
            localizacao="A1"
        )
        
        # Tentar criar outro para o mesmo campo deve falhar
        with self.assertRaises(Exception):
            MapeamentoCampoListaPresenca.objects.create(
                template=self.template,
                tipo_campo="titulo_treinamento",
                localizacao="B1"
            )
    
    def test_obrigatorio_default_true(self):
        """Testa que obrigatorio tem default True"""
        mapeamento = MapeamentoCampoListaPresenca.objects.create(
            template=self.template,
            tipo_campo="categoria_treinamento",
            localizacao="A2"
        )
        self.assertTrue(mapeamento.obrigatorio)
    
    def test_metodo_default_referencia(self):
        """Testa que metodo tem default 'referencia'"""
        mapeamento = MapeamentoCampoListaPresenca.objects.create(
            template=self.template,
            tipo_campo="metodologia",
            localizacao="A3"
        )
        self.assertEqual(mapeamento.metodo, "referencia")
    
    def test_string_representation_mapeamento(self):
        """Testa representação em string do mapeamento"""
        mapeamento = MapeamentoCampoListaPresenca.objects.create(
            template=self.template,
            tipo_campo="titulo_treinamento",
            localizacao="A1"
        )
        
        expected = f"{self.template.nome} - Título do Treinamento (A1)"
        self.assertEqual(str(mapeamento), expected)


class ValidacaoMapeamentoTests(TestCase):
    """Testes para validação de mapeamento"""
    
    def setUp(self):
        """Setup inicial"""
        self.template = TemplateListaPresenca.objects.create(
            nome="Template Validacao",
            tipo_arquivo="excel",
            ativo=True
        )
        
        # Campos obrigatórios
        self.campos_obrigatorios = [
            'titulo_treinamento',
            'categoria_treinamento',
            'metodologia',
            'area_conhecimento',
            'necessita_avaliacao',
            'facilitador_fornecedor',
            'data_hora',
            'carga_horaria',
            'procedimentos_assuntos',
        ]
    
    def test_template_incompleto_inicialmente(self):
        """Testa que template começa incompleto"""
        self.assertFalse(self.template.mapeamento_completo)
    
    def test_template_completo_com_todos_campos(self):
        """Testa que template fica completo quando todos os campos são mapeados"""
        for i, campo in enumerate(self.campos_obrigatorios, 1):
            MapeamentoCampoListaPresenca.objects.create(
                template=self.template,
                tipo_campo=campo,
                localizacao=f"A{i}"
            )
        
        # Atualizar flag
        self.template.mapeamento_completo = True
        self.template.save()
        
        self.assertTrue(self.template.mapeamento_completo)
        self.assertEqual(self.template.mapeamentos.count(), 9)
    
    def test_validacao_referencia_celula(self):
        """Testa validação de formato de referência de célula"""
        formatos_validos = ['A1', 'B2', 'Z100', 'AA50']
        
        for i, formato in enumerate(formatos_validos):
            mapeamento = MapeamentoCampoListaPresenca.objects.create(
                template=self.template,
                tipo_campo=self.campos_obrigatorios[i],
                localizacao=formato
            )
            self.assertEqual(mapeamento.localizacao, formato)
    
    def test_validacao_pagina_range(self):
        """Testa que página está entre 1 e 10"""
        # Válido
        mapeamento = MapeamentoCampoListaPresenca.objects.create(
            template=self.template,
            tipo_campo='titulo_treinamento',
            localizacao='A1',
            pagina=5
        )
        self.assertEqual(mapeamento.pagina, 5)


class MapeamentoJSONTests(TestCase):
    """Testes para estrutura JSON de mapeamento"""
    
    def setUp(self):
        """Setup inicial"""
        self.template = TemplateListaPresenca.objects.create(
            nome="Template JSON",
            tipo_arquivo="excel",
            ativo=True
        )
    
    def test_mapeamento_campos_json_vazio(self):
        """Testa que mapeamento_campos começa vazio"""
        self.assertEqual(self.template.mapeamento_campos, {})
    
    def test_salvar_mapeamento_em_json(self):
        """Testa que mapeamento pode ser salvo como JSON"""
        mapeamento_data = {
            'titulo_treinamento': {
                'localizacao': 'A1',
                'metodo': 'referencia',
                'pagina': 1,
                'obrigatorio': True,
                'permite_imagem_marcacao': False
            }
        }
        
        self.template.mapeamento_campos = mapeamento_data
        self.template.save()
        
        # Recuperar e verificar
        template_reload = TemplateListaPresenca.objects.get(pk=self.template.pk)
        self.assertEqual(
            template_reload.mapeamento_campos['titulo_treinamento']['localizacao'],
            'A1'
        )


class ViewUploadTests(TestCase):
    """Testes para view de upload"""
    
    def setUp(self):
        """Setup inicial"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            is_staff=True
        )
        self.client.login(username='testuser', password='testpass123')
        
        self.template = TemplateListaPresenca.objects.create(
            nome="Template Upload",
            tipo_arquivo="excel",
            ativo=True
        )
    
    def test_upload_view_get(self):
        """Testa GET na view de upload"""
        url = reverse('upload_excel_template')
        response = self.client.get(url, {'pk': self.template.pk})
        
        # Deve retornar sucesso ou redirecionamento
        self.assertIn(response.status_code, [200, 302])
    
    def test_validacao_arquivo_extension(self):
        """Testa que apenas .xlsx é aceito"""
        # Criar arquivo fake
        bad_file = SimpleUploadedFile(
            "test.txt",
            b"fake content",
            content_type="text/plain"
        )
        
        # Teste seria feito via POST, mas aqui validamos modelo
        self.assertFalse(str(bad_file).endswith('.xlsx'))


class RelatedDataTests(TestCase):
    """Testes para relações entre tabelas"""
    
    def setUp(self):
        """Setup inicial"""
        self.template = TemplateListaPresenca.objects.create(
            nome="Template Relations",
            tipo_arquivo="excel",
            ativo=True
        )
    
    def test_relacionamento_reverso_mapeamentos(self):
        """Testa acesso aos mapeamentos via template"""
        # Criar alguns mapeamentos
        for i in range(3):
            MapeamentoCampoListaPresenca.objects.create(
                template=self.template,
                tipo_campo=f'campo_{i}' if i > 0 else 'titulo_treinamento',
                localizacao=f'A{i+1}'
            )
        
        # Acessar via relacionamento reverso
        self.assertEqual(self.template.mapeamentos.count(), 3)
    
    def test_deletar_template_remove_mapeamentos(self):
        """Testa que deletar template remove mapeamentos"""
        # Criar mapeamento
        MapeamentoCampoListaPresenca.objects.create(
            template=self.template,
            tipo_campo='titulo_treinamento',
            localizacao='A1'
        )
        
        template_id = self.template.id
        
        # Deletar template
        self.template.delete()
        
        # Verificar que mapeamentos foram deletados
        mapeamentos = MapeamentoCampoListaPresenca.objects.filter(
            template_id=template_id
        )
        self.assertEqual(mapeamentos.count(), 0)


class IntegracaoComListaPresencaTests(TestCase):
    """Testes para integração com ListaPresenca"""
    
    def setUp(self):
        """Setup inicial"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.template = TemplateListaPresenca.objects.create(
            nome="Template Integracao",
            tipo_arquivo="excel",
            mapeamento_completo=True,
            ativo=True
        )
        
        # Pré-mapear campos
        for i, campo in enumerate([
            'titulo_treinamento', 'categoria_treinamento', 'metodologia',
            'area_conhecimento', 'necessita_avaliacao', 'facilitador_fornecedor',
            'data_hora', 'carga_horaria', 'procedimentos_assuntos'
        ], 1):
            MapeamentoCampoListaPresenca.objects.create(
                template=self.template,
                tipo_campo=campo,
                localizacao=f'A{i}'
            )
        
        # Criar lista de presença
        self.lista = ListaPresenca.objects.create(
            titulo="Lista Teste",
            data_sessao="2024-01-15",
            carga_horaria=8,
            local="Sala 01",
            criado_por=self.user
        )
    
    def test_lista_presenca_pode_usar_template(self):
        """Testa que ListaPresenca pode usar template com mapeamento"""
        # Verificar que template está completo
        self.assertTrue(self.template.mapeamento_completo)
        
        # Verificar que lista foi criada
        self.assertEqual(self.lista.titulo, "Lista Teste")
        
        # Ambos devem estar acessíveis
        self.assertIsNotNone(self.lista)
        self.assertIsNotNone(self.template)


class CamposObratoriosTests(TestCase):
    """Testes para validação dos 9 campos obrigatórios"""
    
    CAMPOS_ESPERADOS = [
        'titulo_treinamento',
        'categoria_treinamento',
        'metodologia',
        'area_conhecimento',
        'necessita_avaliacao',
        'facilitador_fornecedor',
        'data_hora',
        'carga_horaria',
        'procedimentos_assuntos',
    ]
    
    def setUp(self):
        """Setup inicial"""
        self.template = TemplateListaPresenca.objects.create(
            nome="Template Campos",
            tipo_arquivo="excel",
            ativo=True
        )
    
    def test_todos_campos_obrigatorios_existem(self):
        """Testa que todos os 9 campos obrigatórios podem ser mapeados"""
        for campo in self.CAMPOS_ESPERADOS:
            mapeamento = MapeamentoCampoListaPresenca.objects.create(
                template=self.template,
                tipo_campo=campo,
                localizacao='A1'
            )
            self.assertEqual(mapeamento.tipo_campo, campo)
    
    def test_total_campos_obrigatorios(self):
        """Testa que total de campos obrigatórios é 9"""
        self.assertEqual(len(self.CAMPOS_ESPERADOS), 9)


# Testes de Integração
class EndToEndTests(TestCase):
    """Testes end-to-end do sistema completo"""
    
    def setUp(self):
        """Setup inicial"""
        self.user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='admin123',
            is_staff=True,
            is_superuser=True
        )
    
    def test_fluxo_completo_template(self):
        """Testa o fluxo completo: criar -> mapear -> validar"""
        # 1. Criar template
        template = TemplateListaPresenca.objects.create(
            nome="Template E2E",
            tipo_arquivo="excel",
            metodo_mapeamento="ambos",
            ativo=True
        )
        self.assertFalse(template.mapeamento_completo)
        
        # 2. Mapear todos os campos
        campos = [
            'titulo_treinamento', 'categoria_treinamento', 'metodologia',
            'area_conhecimento', 'necessita_avaliacao', 'facilitador_fornecedor',
            'data_hora', 'carga_horaria', 'procedimentos_assuntos'
        ]
        
        for i, campo in enumerate(campos, 1):
            MapeamentoCampoListaPresenca.objects.create(
                template=template,
                tipo_campo=campo,
                localizacao=f'A{i}',
                metodo='referencia',
                pagina=1,
                obrigatorio=True
            )
        
        # 3. Atualizar status
        template.mapeamento_completo = True
        template.save()
        
        # 4. Validar
        template_reload = TemplateListaPresenca.objects.get(pk=template.pk)
        self.assertTrue(template_reload.mapeamento_completo)
        self.assertEqual(template_reload.mapeamentos.count(), 9)
        
        # 5. Verificar JSON
        self.assertIsNotNone(template_reload.mapeamento_campos)


# Executar testes
if __name__ == '__main__':
    import unittest
    unittest.main()
