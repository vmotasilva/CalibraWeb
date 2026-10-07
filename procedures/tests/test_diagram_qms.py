# -*- coding: utf-8 -*-
"""
Testes unitários e de integração para o módulo de Diagramas (DOC.071)
Valida integridade QMS, imutabilidade, auto-save e exportação PDF.
"""

import json
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from procedures.models_diagram import Diagrama, DiagramaVersao, StatusDiagrama
from procedures.services.diagram_qms_service import DiagramaQMSService
from procedures.services.pdf_doc071_generator import gerar_pdf_diagrama_doc071

User = get_user_model()


class DiagramaQMSTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='auditor.qualidade', password='password123', email='auditor@calibraweb.com')
        self.client = Client()
        self.client.force_login(self.user)

        self.diagrama = Diagrama.objects.create(
            codigo='DOC.071-FLX-001',
            titulo='Fluxo de Calibração Dimensional',
            departamento='Metrologia',
            criado_por=self.user
        )
        self.versao_r00 = DiagramaVersao.objects.create(
            diagrama=self.diagrama,
            revisao=0,
            status=StatusDiagrama.RASCUNHO,
            dados_topologia={
                "nodes": [
                    {"id": "1", "type": "start", "position": {"x": 100, "y": 100}, "data": {"label": "Início"}},
                    {"id": "2", "type": "process", "position": {"x": 300, "y": 100}, "data": {"label": "Receber Instrumento"}}
                ],
                "edges": [
                    {"id": "e-1-2", "source": "1", "target": "2"}
                ],
                "grid_data": []
            }
        )

    def test_auto_save_atualiza_apenas_topologia(self):
        """Valida se o endpoint de auto-save persiste as alterações com sucesso."""
        nova_topologia = {
            "nodes": [
                {"id": "1", "type": "start", "position": {"x": 150, "y": 150}, "data": {"label": "Início"}},
                {"id": "2", "type": "process", "position": {"x": 400, "y": 150}, "data": {"label": "Receber Instrumento"}},
                {"id": "3", "type": "critical_process", "position": {"x": 650, "y": 150}, "data": {"label": "Calibração Padrão"}}
            ],
            "edges": [
                {"id": "e-1-2", "source": "1", "target": "2"},
                {"id": "e-2-3", "source": "2", "target": "3"}
            ],
            "grid_data": []
        }

        response = self.client.patch(
            f'/procedures/api/diagramas-versoes/{self.versao_r00.id}/auto-save/',
            data=json.dumps({"dados_topologia": nova_topologia}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        self.versao_r00.refresh_from_db()
        self.assertEqual(len(self.versao_r00.dados_topologia['nodes']), 3)

    def test_bloqueio_de_edicao_quando_aprovado(self):
        """Valida que versões aprovadas rejeitam edições (HTTP 423 Locked)."""
        # Aprova a versão
        DiagramaQMSService.aprovar_versao(self.versao_r00, self.user)
        self.versao_r00.refresh_from_db()
        self.assertEqual(self.versao_r00.status, StatusDiagrama.APROVADO)

        # Tentativa de auto-save deve retornar 423
        response = self.client.patch(
            f'/procedures/api/diagramas-versoes/{self.versao_r00.id}/auto-save/',
            data=json.dumps({"dados_topologia": {"nodes": [], "edges": []}}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 423)

    def test_fluxo_de_revisao_qms(self):
        """Valida ciclo R00 -> Aprovado -> R01 (Rascunho) com herança de topologia."""
        DiagramaQMSService.aprovar_versao(self.versao_r00, self.user)

        # Cria nova revisão R01
        nova_versao = DiagramaQMSService.criar_nova_revisao(
            self.versao_r00,
            self.user,
            motivo="Inclusão de etapa de conferência de rastreabilidade ISO 13485."
        )

        self.assertEqual(nova_versao.revisao, 1)
        self.assertEqual(nova_versao.status, StatusDiagrama.RASCUNHO)
        self.assertEqual(len(nova_versao.dados_topologia['nodes']), 2)

    def test_gerador_pdf_doc071(self):
        """Valida que o serviço ReportLab gera bytes de PDF válidos com cabeçalho DOC.071."""
        pdf_bytes = gerar_pdf_diagrama_doc071(self.versao_r00)
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'))
        self.assertGreater(len(pdf_bytes), 1000)

    def test_numeracao_sequencial_e_identificacao(self):
        """Valida geração automática de numeração sequencial (#001, #002) sem exigência de código documental."""
        d1 = Diagrama.objects.create(
            titulo='Fluxograma Sem Código',
            departamento='Qualidade',
            criado_por=self.user
        )
        self.assertIsNotNone(d1.numero)
        self.assertEqual(d1.identificador, f"#{d1.numero:03d}")
        self.assertEqual(d1.codigo_exibicao, f"#{d1.numero:03d}")

        d2 = Diagrama.objects.create(
            titulo='Segundo Fluxograma Sem Código',
            departamento='Engenharia',
            criado_por=self.user
        )
        self.assertEqual(d2.numero, d1.numero + 1)
        self.assertEqual(d2.identificador, f"#{d2.numero:03d}")

    def test_catalogo_templates_e_aplicacao(self):
        """Valida que o catálogo de modelos (Organograma, Mind Map, Ishikawa) gera nós e conexões corretamente."""
        from procedures.services.diagram_templates import obter_catalogo_templates, obter_topologia_por_template_id

        catalogo = obter_catalogo_templates()
        self.assertGreaterEqual(len(catalogo), 5)
        ids = [t['id'] for t in catalogo]
        self.assertIn('organograma', ids)
        self.assertIn('mapa_mental', ids)
        self.assertIn('ishikawa', ids)

        topologia_org = obter_topologia_por_template_id('organograma', 'Metrologia')
        self.assertIn('nodes', topologia_org)
        self.assertIn('edges', topologia_org)
        self.assertGreater(len(topologia_org['nodes']), 3)

        # Testa aplicação de template via API
        response = self.client.post(
            f'/procedures/api/diagramas-versoes/{self.versao_r00.id}/aplicar-template/',
            data=json.dumps({"template_id": "organograma"}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.versao_r00.refresh_from_db()
        self.assertEqual(len(self.versao_r00.dados_topologia['nodes']), len(topologia_org['nodes']))



class DiagramaAutoSaveValidacaoTestCase(TestCase):
    """Validação de schema e controle de concorrência do auto-save."""

    def setUp(self):
        self.user = User.objects.create_user(username='editor.fluxo', password='password123')
        self.client = Client()
        self.client.force_login(self.user)
        self.diagrama = Diagrama.objects.create(titulo='Fluxo X', criado_por=self.user)
        self.versao = DiagramaVersao.objects.create(
            diagrama=self.diagrama, revisao=0, status=StatusDiagrama.RASCUNHO,
            dados_topologia={"nodes": [], "edges": [], "grid_data": []},
        )
        self.url = f"/procedures/api/diagramas-versoes/{self.versao.id}/auto-save/"

    def _patch(self, body):
        return self.client.patch(self.url, data=json.dumps(body), content_type='application/json')

    def _no(self, nid):
        return {"id": nid, "type": "process", "position": {"x": 1, "y": 2}, "data": {"label": nid}}

    def test_rejeita_ids_de_no_duplicados(self):
        resp = self._patch({"dados_topologia": {"nodes": [self._no("1"), self._no("1")], "edges": []}})
        self.assertEqual(resp.status_code, 400)

    def test_rejeita_no_sem_posicao_valida(self):
        resp = self._patch({"dados_topologia": {"nodes": [{"id": "1", "position": None}], "edges": []}})
        self.assertEqual(resp.status_code, 400)

    def test_preserva_chaves_extras_do_editor(self):
        resp = self._patch({"dados_topologia": {"nodes": [self._no("1")], "edges": [], "estilo_linha": "curva"}})
        self.assertEqual(resp.status_code, 200)
        self.versao.refresh_from_db()
        self.assertEqual(self.versao.dados_topologia["estilo_linha"], "curva")

    def test_conflito_de_concorrencia_retorna_409(self):
        resp = self._patch({"dados_topologia": {"nodes": [self._no("1")], "edges": []},
                            "base_atualizado_em": "2000-01-01T00:00:00+00:00"})
        self.assertEqual(resp.status_code, 409)
        self.versao.refresh_from_db()
        self.assertEqual(self.versao.dados_topologia["nodes"], [])

    def test_salvamento_com_base_correta_funciona_em_sequencia(self):
        base = self.versao.atualizado_em.isoformat()
        r1 = self._patch({"dados_topologia": {"nodes": [self._no("1")], "edges": []}, "base_atualizado_em": base})
        self.assertEqual(r1.status_code, 200)
        r2 = self._patch({"dados_topologia": {"nodes": [self._no("1"), self._no("2")], "edges": []},
                          "base_atualizado_em": r1.json()["atualizado_em"]})
        self.assertEqual(r2.status_code, 200)
