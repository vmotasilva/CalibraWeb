# -*- coding: utf-8 -*-
"""
Testes para o sistema de mapeamento de template de lista de presença (PDF)

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
    ListaPresenca
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
            tipo_arquivo="pdf",
            tem_pagina_assinatura=True,
            num_linhas_assinatura=20,
            placeholders_mapeados={"titulo": "Título do Treinamento"},
            ativo=True
        )
    
    def test_template_creation(self):
        """Testa criação de template"""
        self.assertEqual(self.template.nome, "Template Teste")
        self.assertTrue(self.template.ativo)
        self.assertEqual(self.template.tipo_arquivo, "pdf")
        self.assertTrue(self.template.tem_pagina_assinatura)
        self.assertEqual(self.template.num_linhas_assinatura, 20)
    
    def test_template_string_representation(self):
        """Testa representação em string do template"""
        self.assertEqual(str(self.template), "Template Teste")
    
    def test_mapeamento_completo_default(self):
        """Testa que mapeamento_completo é False por padrão"""
        self.assertFalse(self.template.mapeamento_completo)
    
    def test_placeholders_mapeados_default(self):
        """Testa que placeholders_mapeados é dict por padrão"""
        template_novo = TemplateListaPresenca.objects.create(
            nome="Template Novo",
            tipo_arquivo="pdf"
        )
        self.assertEqual(template_novo.placeholders_mapeados, {})


class MapeamentoCampoTests(TestCase):
    """Testes para mapeamento de campos"""
    
    def setUp(self):
        """Setup inicial"""
        self.template = TemplateListaPresenca.objects.create(
            nome="Template Mapeamento",
            tipo_arquivo="pdf",
            ativo=True
        )
    
    def test_criar_mapeamento_campo(self):
        """Testa criação de mapeamento de campo"""
        mapeamento = MapeamentoCampoListaPresenca.objects.create(
            template=self.template,
            placeholder="{{titulo}}",
            campo_dados="titulo",
            formato="dd/mm/yyyy",
            obrigatorio=True
        )
        
        self.assertEqual(mapeamento.placeholder, "{{titulo}}")
        self.assertEqual(mapeamento.campo_dados, "titulo")
        self.assertEqual(mapeamento.formato, "dd/mm/yyyy")
        self.assertTrue(mapeamento.obrigatorio)
    
    def test_mapeamento_unico_por_placeholder(self):
        """Testa que só pode haver um mapeamento por placeholder no mesmo template"""
        MapeamentoCampoListaPresenca.objects.create(
            template=self.template,
            placeholder="{{titulo}}",
            campo_dados="titulo"
        )
        
        # Tentar criar outro mapeamento com o mesmo placeholder deve falhar por conta do unique_together
        with self.assertRaises(Exception):
            MapeamentoCampoListaPresenca.objects.create(
                template=self.template,
                placeholder="{{titulo}}",
                campo_dados="local"
            )
    
    def test_obrigatorio_default_true(self):
        """Testa que obrigatorio tem default True"""
        mapeamento = MapeamentoCampoListaPresenca.objects.create(
            template=self.template,
            placeholder="{{facilitador}}",
            campo_dados="facilitador"
        )
        self.assertTrue(mapeamento.obrigatorio)
    
    def test_string_representation_mapeamento(self):
        """Testa representação em string do mapeamento"""
        mapeamento = MapeamentoCampoListaPresenca.objects.create(
            template=self.template,
            placeholder="{{titulo}}",
            campo_dados="titulo"
        )
        
        expected = f"{self.template.nome} - {mapeamento.placeholder} → Título do Treinamento"
        self.assertEqual(str(mapeamento), expected)


class RelatedDataTests(TestCase):
    """Testes para relações entre tabelas"""
    
    def setUp(self):
        """Setup inicial"""
        self.template = TemplateListaPresenca.objects.create(
            nome="Template Relations",
            tipo_arquivo="pdf",
            ativo=True
        )
    
    def test_relacionamento_reverso_mapeamentos(self):
        """Testa acesso aos mapeamentos via template"""
        for i in range(3):
            MapeamentoCampoListaPresenca.objects.create(
                template=self.template,
                placeholder=f"{{{{campo_{i}}}}}" if i > 0 else "{{titulo}}",
                campo_dados="titulo"
            )
        
        self.assertEqual(self.template.mapeamentos.count(), 3)
    
    def test_deletar_template_remove_mapeamentos(self):
        """Testa que deletar template remove mapeamentos"""
        MapeamentoCampoListaPresenca.objects.create(
            template=self.template,
            placeholder="{{titulo}}",
            campo_dados="titulo"
        )
        
        template_id = self.template.id
        self.template.delete()
        
        mapeamentos = MapeamentoCampoListaPresenca.objects.filter(
            template_id=template_id
        )
        self.assertEqual(mapeamentos.count(), 0)


class ViewUploadTests(TestCase):
    """Testes para views de upload e mapeamento"""
    
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
            tipo_arquivo="pdf",
            ativo=True
        )
    
    def test_upload_view_get(self):
        """Testa GET na view de upload"""
        url = reverse('procedures:upload_template_lista_presenca')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
    
    def test_upload_view_post_valido(self):
        """Testa criação de template via POST"""
        url = reverse('procedures:upload_template_lista_presenca')
        fake_pdf = SimpleUploadedFile(
            "template.pdf",
            b"fake pdf content",
            content_type="application/pdf"
        )
        
        data = {
            'nome': 'Template Enviado',
            'descricao': 'Descrição do template enviado',
            'arquivo_pdf_template': fake_pdf,
            'tem_pagina_assinatura': 'on',
            'num_linhas_assinatura': '25'
        }
        
        response = self.client.post(url, data)
        # Deve redirecionar para a view de mapeamento
        self.assertEqual(response.status_code, 302)
        
        # Verifica se foi criado no BD
        tpl = TemplateListaPresenca.objects.get(nome='Template Enviado')
        self.assertEqual(tpl.descricao, 'Descrição do template enviado')
        self.assertEqual(tpl.num_linhas_assinatura, 25)
    
    def test_mapear_fields_view_post(self):
        """Testa salvar mapeamentos via POST"""
        url = reverse('procedures:mapear_template_fields', kwargs={'template_id': self.template.id})
        
        # Placeholders que serão mapeados
        data = {
            'campo_dados[titulo]': 'titulo',
            'campo_dados[facilitador]': 'facilitador',
            'campo_dados[data]': 'data',
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        
        # Verifica se mapeamentos foram salvos no BD
        self.template.refresh_from_db()
        self.assertTrue(self.template.mapeamento_completo)
        self.assertEqual(self.template.mapeamentos.count(), 3)
        
        m_titulo = self.template.mapeamentos.get(placeholder='titulo')
        self.assertEqual(m_titulo.campo_dados, 'titulo')
