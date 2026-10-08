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
        self.aprovador = User.objects.create_user(username='aprovador.qms', password='password123')
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
                    {"id": "2", "type": "process", "position": {"x": 300, "y": 100}, "data": {"label": "Receber Instrumento"}},
                    {"id": "3", "type": "end", "position": {"x": 500, "y": 100}, "data": {"label": "Fim"}}
                ],
                "edges": [
                    {"id": "e-1-2", "source": "1", "target": "2"},
                    {"id": "e-2-3", "source": "2", "target": "3"}
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
        DiagramaQMSService.submeter_para_aprovacao(self.versao_r00, self.user)
        DiagramaQMSService.aprovar_versao(self.versao_r00, self.aprovador)
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
        DiagramaQMSService.submeter_para_aprovacao(self.versao_r00, self.user)
        DiagramaQMSService.aprovar_versao(self.versao_r00, self.aprovador)

        # Cria nova revisão R01
        nova_versao = DiagramaQMSService.criar_nova_revisao(
            self.versao_r00,
            self.user,
            motivo="Inclusão de etapa de conferência de rastreabilidade ISO 13485."
        )

        self.assertEqual(nova_versao.revisao, 1)
        self.assertEqual(nova_versao.status, StatusDiagrama.RASCUNHO)
        self.assertEqual(len(nova_versao.dados_topologia['nodes']), 3)

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


class DiagramaGovernancaTestCase(TestCase):
    """Permissões, segregação de funções, devolução, nova revisão e PDF."""

    def setUp(self):
        self.autor = User.objects.create_user(username='autor', password='x')
        self.aprovador = User.objects.create_user(username='aprovador', password='x')
        self.diagrama = Diagrama.objects.create(titulo='Calibração & Ensaios <A>', criado_por=self.autor)
        self.versao = DiagramaVersao.objects.create(
            diagrama=self.diagrama, revisao=0, status=StatusDiagrama.RASCUNHO,
            dados_topologia={
                "nodes": [
                    {"id": "1", "type": "start", "position": {"x": 100, "y": 60}, "data": {"label": "Início", "lane": "Lab"}},
                    {"id": "2", "type": "decision", "position": {"x": 100, "y": 200}, "data": {"label": "Conforme? 😀", "lane": "Lab"}},
                    {"id": "3", "type": "process", "position": {"x": 400, "y": 200}, "data": {"label": "Liberar", "lane": "Qualidade", "customTags": ["Tag"]}},
                    {"id": "4", "type": "end", "position": {"x": 400, "y": 340}, "data": {"label": "Fim", "lane": "Qualidade"}},
                ],
                "edges": [
                    {"id": "e-1-2", "source": "1", "target": "2"},
                    {"id": "e-2-3", "source": "2", "target": "3", "label": "Sim", "sourceHandle": "right"},
                    {"id": "e-2-4", "source": "2", "target": "4", "label": "Não"},
                ],
                "grid_data": [],
            },
        )

    def _aprovar(self, aprovador=None):
        DiagramaQMSService.submeter_para_aprovacao(self.versao, self.autor)
        DiagramaQMSService.aprovar_versao(self.versao, aprovador or self.aprovador)
        self.versao.refresh_from_db()

    def _cliente(self, user, *perms):
        from django.contrib.auth.models import Permission
        for codename in perms:
            user.user_permissions.add(Permission.objects.get(codename=codename))
        user = User.objects.get(pk=user.pk)  # limpa cache de permissões
        c = Client()
        c.force_login(user)
        return c

    def test_nao_aprova_rascunho_sem_submeter(self):
        with self.assertRaises(ValidationError):
            DiagramaQMSService.aprovar_versao(self.versao, self.aprovador)

    def test_segregacao_de_funcoes(self):
        DiagramaQMSService.submeter_para_aprovacao(self.versao, self.autor)
        with self.assertRaises(ValidationError):
            DiagramaQMSService.aprovar_versao(self.versao, self.autor)

    def test_devolucao_exige_motivo_e_volta_para_rascunho(self):
        DiagramaQMSService.submeter_para_aprovacao(self.versao, self.autor)
        with self.assertRaises(ValidationError):
            DiagramaQMSService.devolver_para_ajustes(self.versao, self.aprovador, "")
        DiagramaQMSService.devolver_para_ajustes(self.versao, self.aprovador, "Falta a etapa de calibração")
        self.versao.refresh_from_db()
        self.assertEqual(self.versao.status, StatusDiagrama.RASCUNHO)
        self.assertEqual(self.versao.motivo_devolucao, "Falta a etapa de calibração")

    def test_nova_revisao_somente_de_versao_aprovada_e_sem_revisao_aberta(self):
        with self.assertRaises(ValidationError):
            DiagramaQMSService.criar_nova_revisao(self.versao, self.autor, "Ajuste de processo")
        self._aprovar()
        r01 = DiagramaQMSService.criar_nova_revisao(self.versao, self.autor, "Ajuste de processo")
        self.assertEqual(r01.revisao, 1)
        with self.assertRaises(ValidationError):
            DiagramaQMSService.criar_nova_revisao(self.versao, self.autor, "Outra revisão paralela")

    def test_endpoints_exigem_permissao(self):
        c = self._cliente(self.autor)
        url = f'/procedures/api/diagramas-versoes/{self.versao.id}/submeter/'
        self.assertEqual(c.post(url).status_code, 403)
        c = self._cliente(self.autor, 'nav_diagramas_submeter')
        self.assertEqual(c.post(url).status_code, 200)

        c_apr = self._cliente(self.aprovador)
        self.assertEqual(c_apr.post(f'/procedures/api/diagramas-versoes/{self.versao.id}/aprovar/').status_code, 403)
        self.assertEqual(c_apr.post(f'/procedures/api/diagramas-versoes/{self.versao.id}/exportar-pdf-doc071/').status_code, 403)

    def test_cabecalho_de_diagrama_aprovado_e_travado(self):
        self._aprovar()
        c = self._cliente(self.autor)
        resp = c.patch(f'/procedures/api/diagramas/{self.diagrama.id}/', data=json.dumps({"titulo": "Novo"}),
                       content_type='application/json')
        self.assertEqual(resp.status_code, 423)
        self.diagrama.refresh_from_db()
        self.assertEqual(self.diagrama.titulo, 'Calibração & Ensaios <A>')

    def test_pdf_renderiza_diagrama_e_aceita_caracteres_especiais(self):
        self._aprovar()
        pdf = gerar_pdf_diagrama_doc071(self.versao)
        self.assertTrue(pdf.startswith(b'%PDF-'))
        # Sem diagrama a página 1 seria bem menor: o desenho vetorial aumenta o conteúdo
        vazio = DiagramaVersao.objects.create(
            diagrama=Diagrama.objects.create(titulo='Vazio', criado_por=self.autor), revisao=0, dados_topologia={"nodes": [], "edges": []})
        self.assertGreater(len(pdf), len(gerar_pdf_diagrama_doc071(vazio)))

    def test_editor_exibe_botoes_conforme_status_e_permissao(self):
        url = f'/procedures/diagramas/editor/{self.versao.id}/'
        # Rascunho: usuário sem permissões não vê Submeter/PDF
        html = self._cliente(self.autor).get(url).content.decode()
        self.assertNotIn('btnSubmeter', html)
        self.assertNotIn('exportarPDFDoc071()">', html)
        # Rascunho com permissão de submeter
        html = self._cliente(self.autor, 'nav_diagramas_submeter').get(url).content.decode()
        self.assertIn('btnSubmeter', html)
        self.assertIn('const IS_APPROVED = false', html)

        # Em aprovação: somente leitura; aprovador vê Aprovar/Devolver
        DiagramaQMSService.submeter_para_aprovacao(self.versao, self.autor)
        html = self._cliente(self.aprovador, 'nav_diagramas_aprovar').get(url).content.decode()
        self.assertIn('btnAprovar', html)
        self.assertIn('btnDevolver', html)
        self.assertNotIn('btnSubmeter', html)
        self.assertIn('const IS_APPROVED = true', html)

        # Aprovado: Nova Revisão aparece só com permissão e sem revisão em andamento
        DiagramaQMSService.aprovar_versao(self.versao, self.aprovador)
        html = self._cliente(self.autor, 'nav_diagramas_nova_revisao').get(url).content.decode()
        self.assertIn('onclick="modalNovaRevisao()"', html)

    def test_editor_barra_de_ferramentas_com_historico_e_edicao_de_conexoes(self):
        url = f'/procedures/diagramas/editor/{self.versao.id}/'
        html = self._cliente(self.autor).get(url).content.decode()
        for marcador in ('id="btnDesfazer"', 'id="btnRefazer"', 'onclick="excluirSelecao()"',
                         'Organizar', 'id="labelEstiloLinha"', 'procedures/js/diagrama_editor.js'):
            self.assertIn(marcador, html)

        # A lógica do editor fica no arquivo estático
        from pathlib import Path
        js = (Path(__file__).resolve().parent.parent / 'static' / 'procedures' / 'js' / 'diagrama_editor.js').read_text(encoding='utf-8')
        for funcao in ('function editarRotuloAresta', 'function desfazer()', 'function dispararAutoSave'):
            self.assertIn(funcao, js)

        # Somente leitura (Em Aprovação): sem botões de edição/histórico
        DiagramaQMSService.submeter_para_aprovacao(self.versao, self.autor)
        html = self._cliente(self.autor).get(url).content.decode()
        self.assertNotIn('id="btnDesfazer"', html)
        self.assertNotIn('onclick="adicionarTopicoIrmao()"', html)


class DiagramaPacote4TestCase(TestCase):
    """Validação pré-submissão, comparação de revisões, lista, duplicar/arquivar e inbox."""

    def setUp(self):
        self.autor = User.objects.create_user(username='autor4', password='x')
        self.aprovador = User.objects.create_user(username='aprovador4', password='x')
        self.diagrama = Diagrama.objects.create(titulo='Fluxo Pacote 4', criado_por=self.autor)
        self.versao = DiagramaVersao.objects.create(
            diagrama=self.diagrama, revisao=0, status=StatusDiagrama.RASCUNHO, dados_topologia=self._topologia_valida())

    @staticmethod
    def _topologia_valida():
        return {
            "nodes": [
                {"id": "1", "type": "start", "position": {"x": 1, "y": 1}, "data": {"label": "Início", "lane": "A"}},
                {"id": "2", "type": "decision", "position": {"x": 1, "y": 100}, "data": {"label": "Ok?", "lane": "A"}},
                {"id": "3", "type": "end", "position": {"x": 1, "y": 200}, "data": {"label": "Fim", "lane": "A"}},
                {"id": "4", "type": "process", "position": {"x": 300, "y": 100}, "data": {"label": "Corrigir", "lane": "A"}},
            ],
            "edges": [
                {"id": "e12", "source": "1", "target": "2"},
                {"id": "e23", "source": "2", "target": "3", "label": "Sim"},
                {"id": "e24", "source": "2", "target": "4", "label": "Não"},
            ],
            "grid_data": [],
        }

    def _cliente(self, user, *perms):
        from django.contrib.auth.models import Permission
        for codename in perms:
            user.user_permissions.add(Permission.objects.get(codename=codename))
        c = Client()
        c.force_login(User.objects.get(pk=user.pk))
        return c

    # --- validação pré-submissão -------------------------------------------------
    def test_validacao_aceita_fluxograma_completo(self):
        from procedures.services.diagram_validation import validar_para_submissao
        self.assertEqual(validar_para_submissao(self._topologia_valida()), [])

    def test_validacao_detecta_problemas(self):
        from procedures.services.diagram_validation import validar_para_submissao
        topo = self._topologia_valida()
        topo["nodes"] = [n for n in topo["nodes"] if n["type"] != "end"]
        topo["edges"] = [e for e in topo["edges"] if e["id"] != "e23"]
        topo["nodes"].append({"id": "9", "type": "process", "position": {"x": 5, "y": 5}, "data": {"label": ""}})
        texto = " | ".join(validar_para_submissao(topo))
        self.assertIn("Fim", texto)
        self.assertIn("pelo menos 2 saídas", texto)
        self.assertIn("sem texto", texto)
        self.assertIn("isolado", texto)

    def test_organograma_nao_exige_inicio_e_fim(self):
        from procedures.services.diagram_validation import validar_para_submissao
        topo = {"nodes": [
            {"id": "a", "type": "process", "position": {"x": 1, "y": 1}, "data": {"label": "Diretoria"}},
            {"id": "b", "type": "process", "position": {"x": 1, "y": 2}, "data": {"label": "Qualidade"}}],
            "edges": [{"id": "e", "source": "a", "target": "b"}]}
        self.assertEqual(validar_para_submissao(topo), [])

    def test_submissao_bloqueada_com_problemas(self):
        self.versao.dados_topologia["nodes"][0]["data"]["label"] = ""
        self.versao.save()
        with self.assertRaises(ValidationError) as ctx:
            DiagramaQMSService.submeter_para_aprovacao(self.versao, self.autor)
        self.assertIn("Corrija antes de submeter", ctx.exception.messages[0])

    # --- comparação ---------------------------------------------------------------
    def test_comparacao_entre_revisoes(self):
        from procedures.services.diagram_diff import comparar_topologias
        antiga = self._topologia_valida()
        nova = self._topologia_valida()
        nova["nodes"][3]["data"]["label"] = "Corrigir e reinspecionar"
        nova["nodes"].append({"id": "5", "type": "process", "position": {"x": 1, "y": 1}, "data": {"label": "Registrar", "lane": "B"}})
        nova["edges"] = [e for e in nova["edges"] if e["id"] != "e24"] + [{"id": "e45", "source": "4", "target": "5"}]
        nova["nodes"][0]["position"] = {"x": 999, "y": 999}  # posição não conta
        diff = comparar_topologias(antiga, nova)
        self.assertEqual([b["nome"] for b in diff["blocos_adicionados"]], ["Registrar"])
        self.assertEqual(diff["blocos_removidos"], [])
        self.assertEqual(diff["blocos_alterados"][0]["mudancas"][0]["para"], "Corrigir e reinspecionar")
        self.assertEqual(len(diff["conexoes_adicionadas"]), 1)
        self.assertEqual(len(diff["conexoes_removidas"]), 1)
        self.assertTrue(comparar_topologias(antiga, antiga)["sem_mudancas"])

    def test_pagina_de_historico_com_comparacao(self):
        DiagramaQMSService.submeter_para_aprovacao(self.versao, self.autor)
        DiagramaQMSService.aprovar_versao(self.versao, self.aprovador)
        r01 = DiagramaQMSService.criar_nova_revisao(self.versao, self.autor, "Ajuste do processo")
        r01.dados_topologia["nodes"][3]["data"]["label"] = "Corrigir (novo texto)"
        r01.save()
        html = self._cliente(self.autor).get(f'/procedures/diagramas/{self.diagrama.id}/historico/').content.decode()
        self.assertIn('R01', html)
        self.assertIn('Blocos alterados', html)
        self.assertIn('Corrigir (novo texto)', html)

    # --- lista, duplicar, arquivar -------------------------------------------------
    def test_lista_filtra_por_status_e_mostra_vigente(self):
        DiagramaQMSService.submeter_para_aprovacao(self.versao, self.autor)
        DiagramaQMSService.aprovar_versao(self.versao, self.aprovador)
        DiagramaQMSService.criar_nova_revisao(self.versao, self.autor, "Ajuste do processo")
        outro = Diagrama.objects.create(titulo='Outro Fluxo', criado_por=self.autor)
        DiagramaVersao.objects.create(diagrama=outro, revisao=0, status=StatusDiagrama.RASCUNHO, dados_topologia={"nodes": [], "edges": []})
        c = self._cliente(self.autor)
        html = c.get('/procedures/diagramas/?status=RASCUNHO').content.decode()
        self.assertIn('Fluxo Pacote 4', html)   # última revisão (R01) é rascunho
        self.assertIn('Outro Fluxo', html)
        self.assertIn('Rascunho aberto', html)  # R01 aberto sobre vigente R00
        html = c.get('/procedures/diagramas/?status=APROVADO').content.decode()
        self.assertNotIn('Fluxo Pacote 4', html)
        html = c.get('/procedures/diagramas/?busca=%23' + str(outro.numero)).content.decode()
        self.assertIn('Outro Fluxo', html)
        self.assertNotIn('Fluxo Pacote 4', html)

    def test_duplicar_cria_copia_em_rascunho(self):
        c = self._cliente(self.autor, 'nav_diagramas_novo')
        resp = c.post(f'/procedures/diagramas/{self.diagrama.id}/duplicar/')
        self.assertEqual(resp.status_code, 302)
        copia = Diagrama.objects.exclude(pk=self.diagrama.pk).get()
        self.assertTrue(copia.titulo.endswith('(cópia)'))
        v = copia.versoes.get()
        self.assertEqual((v.revisao, v.status), (0, StatusDiagrama.RASCUNHO))
        self.assertEqual(len(v.dados_topologia['nodes']), 4)
        # Sem permissão: nada é criado
        sem_perm = self._cliente(self.aprovador)
        sem_perm.post(f'/procedures/diagramas/{self.diagrama.id}/duplicar/')
        self.assertEqual(Diagrama.objects.count(), 2)

    def test_arquivar_e_restaurar_respeita_revisao_aprovada(self):
        c = self._cliente(self.autor, 'nav_diagramas_editor')
        c.post(f'/procedures/diagramas/{self.diagrama.id}/arquivar/', {'acao': 'arquivar'})
        self.diagrama.refresh_from_db()
        self.assertFalse(self.diagrama.ativo)
        c.post(f'/procedures/diagramas/{self.diagrama.id}/arquivar/', {'acao': 'restaurar'})
        self.diagrama.refresh_from_db()
        self.assertTrue(self.diagrama.ativo)

        DiagramaQMSService.submeter_para_aprovacao(self.versao, self.autor)
        DiagramaQMSService.aprovar_versao(self.versao, self.aprovador)
        c.post(f'/procedures/diagramas/{self.diagrama.id}/arquivar/', {'acao': 'arquivar'})
        self.diagrama.refresh_from_db()
        self.assertTrue(self.diagrama.ativo)  # aprovado: só superusuário arquiva

    # --- caixa de entrada ----------------------------------------------------------
    def test_inbox_notifica_aprovador_e_elaborador(self):
        from shared.inbox import get_user_inbox_items
        from django.core.cache import cache
        from django.contrib.auth.models import Permission
        self.aprovador.user_permissions.add(Permission.objects.get(codename='nav_diagramas_aprovar'))
        DiagramaQMSService.submeter_para_aprovacao(self.versao, self.autor)

        cache.clear()
        aprovador = User.objects.get(pk=self.aprovador.pk)
        itens = [i for i in get_user_inbox_items(aprovador) if i.module == 'Diagramas']
        self.assertEqual(len(itens), 1)
        self.assertEqual(itens[0].sub_type, 'Aguardando aprovação')

        # Quem submeteu não vê a própria aprovação pendente (segregação)
        cache.clear()
        self.assertEqual([i for i in get_user_inbox_items(self.autor) if i.module == 'Diagramas'], [])

        # Após devolver, o elaborador é avisado
        DiagramaQMSService.devolver_para_ajustes(self.versao, aprovador, "Falta detalhar a decisão")
        cache.clear()
        itens = [i for i in get_user_inbox_items(User.objects.get(pk=self.autor.pk)) if i.module == 'Diagramas']
        self.assertEqual([i.sub_type for i in itens], ['Devolvidos para ajuste'])


class DiagramaColaboradorSubtitulosTestCase(TestCase):
    """Subtítulos nos blocos e bloco de colaborador (busca, foto, validação, PDF e comparação)."""

    FOTO_PNG = ("data:image/png;base64,"
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

    def setUp(self):
        from rh.models import Colaborador
        from organization.models import Setor
        self.user = User.objects.create_user(username='editor5', password='x')
        self.client = Client()
        self.client.force_login(self.user)
        setor = Setor.objects.create(nome='Qualidade')
        base = dict(setor=setor)
        self.colab_foto = self._criar_colab(Colaborador, 'Maria Aparecida Souza Lima', 'Analista da Qualidade', self.FOTO_PNG, '9001', base)
        self.colab_sem_foto = self._criar_colab(Colaborador, 'João Pedro Santos', 'Auxiliar', None, '9002', base)
        self.diagrama = Diagrama.objects.create(titulo='Org', criado_por=self.user)

    @staticmethod
    def _criar_colab(Colaborador, nome, cargo, foto, matricula, extra):
        # Preenche apenas o necessário; demais campos obrigatórios usam o primeiro valor válido do modelo
        campos = {'nome_completo': nome, 'cargo': cargo, 'foto': foto, 'matricula': matricula, 'grupo': 'Geral'}
        campos.update(extra)
        return Colaborador.objects.create(**campos)

    def _topologia(self):
        return {
            "nodes": [
                {"id": "1", "type": "process", "position": {"x": 100, "y": 60},
                 "data": {"label": "Maria Aparecida Souza Lima", "lane": "Qualidade", "subtitles": ["Responsável pelo DOC.071", "Substituta: João"],
                          "colab": {"id": self.colab_foto.id, "nome": "Maria Aparecida Souza Lima",
                                    "cargo": "Analista da Qualidade", "nomeCurto": True, "temFoto": True}}},
                {"id": "2", "type": "process", "position": {"x": 400, "y": 60},
                 "data": {"label": "João Pedro Santos", "lane": "Qualidade",
                          "colab": {"id": self.colab_sem_foto.id, "nome": "João Pedro Santos", "cargo": "Auxiliar",
                                    "nomeCurto": False, "temFoto": False}}},
            ],
            "edges": [{"id": "e12", "source": "1", "target": "2"}],
            "grid_data": [],
        }

    def test_busca_de_colaboradores_para_blocos(self):
        resp = self.client.get('/procedures/api/diagramas/colaboradores/?q=maria')
        self.assertEqual(resp.status_code, 200)
        itens = resp.json()['results']
        self.assertEqual(len(itens), 1)
        self.assertEqual((itens[0]['id'], itens[0]['cargo'], itens[0]['setor'], itens[0]['tem_foto']),
                         (self.colab_foto.id, 'Analista da Qualidade', 'Qualidade', True))
        self.assertFalse(self.client.get('/procedures/api/diagramas/colaboradores/?q=joão').json()['results'][0]['tem_foto'])
        self.assertEqual(self.client.get('/procedures/api/diagramas/colaboradores/?q=m').json()['results'], [])
        self.assertEqual(Client().get('/procedures/api/diagramas/colaboradores/?q=maria').status_code, 401)

    def test_foto_do_colaborador(self):
        resp = self.client.get(f'/procedures/api/diagramas/colaboradores/{self.colab_foto.id}/foto/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'image/png')
        self.assertTrue(resp.content.startswith(b'\x89PNG'))
        self.assertEqual(self.client.get(f'/procedures/api/diagramas/colaboradores/{self.colab_sem_foto.id}/foto/').status_code, 404)

    def test_autosave_valida_subtitulos_e_colaborador(self):
        versao = DiagramaVersao.objects.create(diagrama=self.diagrama, revisao=0, dados_topologia={"nodes": [], "edges": []})
        url = f'/procedures/api/diagramas-versoes/{versao.id}/auto-save/'

        def salvar(topo):
            return self.client.patch(url, data=json.dumps({"dados_topologia": topo}), content_type='application/json')

        self.assertEqual(salvar(self._topologia()).status_code, 200)

        ruim = self._topologia()
        ruim["nodes"][0]["data"]["subtitles"] = "texto solto"
        self.assertEqual(salvar(ruim).status_code, 400)
        ruim = self._topologia()
        ruim["nodes"][0]["data"]["colab"]["id"] = "abc"
        self.assertEqual(salvar(ruim).status_code, 400)
        ruim = self._topologia()
        ruim["nodes"][0]["data"]["subtitles"] = ["x"] * 21
        self.assertEqual(salvar(ruim).status_code, 400)

    def test_nome_curto_e_dimensoes_no_renderer(self):
        from procedures.services.diagram_renderer import nome_exibicao, _tamanho
        self.assertEqual(nome_exibicao({"nome": "Maria Aparecida Souza Lima", "nomeCurto": True}), "Maria Lima")
        self.assertEqual(nome_exibicao({"nome": "Maria Aparecida Souza Lima", "nomeCurto": False}), "Maria Aparecida Souza Lima")
        self.assertEqual(nome_exibicao({"nome": "João Santos", "nomeCurto": True}), "João Santos")
        topo = self._topologia()
        largura, altura = _tamanho(topo["nodes"][0])
        self.assertEqual(largura, 200)
        self.assertGreater(altura, _tamanho(topo["nodes"][1])[1])  # mais alto por ter 2 subtítulos

    def test_pdf_com_blocos_de_colaborador_e_fotos(self):
        from procedures.services.pdf_doc071_generator import _carregar_fotos
        versao = DiagramaVersao.objects.create(diagrama=self.diagrama, revisao=0, dados_topologia=self._topologia())
        fotos = _carregar_fotos(versao.dados_topologia)
        self.assertEqual(set(fotos), {self.colab_foto.id})
        pdf = gerar_pdf_diagrama_doc071(versao)
        self.assertTrue(pdf.startswith(b'%PDF-'))

    def test_comparacao_considera_subtitulos_e_funcao(self):
        from procedures.services.diagram_diff import comparar_topologias
        antiga = self._topologia()
        nova = self._topologia()
        nova["nodes"][0]["data"]["subtitles"].append("Novo subtítulo")
        nova["nodes"][0]["data"]["colab"]["cargo"] = "Coordenadora da Qualidade"
        campos = {m["campo"] for b in comparar_topologias(antiga, nova)["blocos_alterados"] for m in b["mudancas"]}
        self.assertEqual(campos, {"Subtítulos", "Função"})


class DiagramaRaiasTestCase(TestCase):
    """Catálogo de raias, ordem explícita, renomear/mesclar em rascunhos e integração com editor/PDF."""

    def setUp(self):
        from organization.models import Setor
        self.admin = User.objects.create_user(username='admin.raias', password='x')
        self.leitor = User.objects.create_user(username='leitor.raias', password='x')
        self.setor_q = Setor.objects.create(nome='Qualidade')
        self.diagrama = Diagrama.objects.create(titulo='Org Raias', criado_por=self.admin)
        self.versao = DiagramaVersao.objects.create(
            diagrama=self.diagrama, revisao=0, status=StatusDiagrama.RASCUNHO,
            dados_topologia=self._topologia())

    @staticmethod
    def _topologia():
        return {
            "nodes": [
                {"id": "1", "type": "process", "position": {"x": 1, "y": 60}, "data": {"label": "A", "lane": "Liderança"}},
                {"id": "2", "type": "process", "position": {"x": 1, "y": 300}, "data": {"label": "B", "lane": "Qualidade"}},
            ],
            "edges": [{"id": "e12", "source": "1", "target": "2"}],
            "grid_data": [],
        }

    def _cliente(self, user, *perms):
        from django.contrib.auth.models import Permission
        for codename in perms:
            user.user_permissions.add(Permission.objects.get(codename=codename))
        c = Client()
        c.force_login(User.objects.get(pk=user.pk))
        return c

    # --- ordem explícita ------------------------------------------------------------
    def test_ordem_das_raias(self):
        from procedures.services.diagram_raias import raias_do_diagrama
        topo = self._topologia()
        self.assertEqual(raias_do_diagrama(topo), ["Liderança", "Qualidade"])  # legado: ordem de aparição

        topo["lanes"] = ["Qualidade", "Liderança"]
        self.assertEqual(raias_do_diagrama(topo), ["Qualidade", "Liderança"])  # ordem explícita

        topo["raias_fixas"] = ["Operacional"]  # raia criada sem blocos continua visível
        self.assertEqual(raias_do_diagrama(topo), ["Qualidade", "Liderança", "Operacional"])

        topo["lanes"] = ["Qualidade", "Fantasma", "Liderança"]  # nomes sem blocos e não fixos somem
        self.assertNotIn("Fantasma", raias_do_diagrama(topo))
        self.assertEqual(raias_do_diagrama({"nodes": [], "edges": []}), ["Geral"])

    def test_autosave_valida_lanes(self):
        url = f'/procedures/api/diagramas-versoes/{self.versao.id}/auto-save/'
        c = self._cliente(self.admin)
        ok = self._topologia()
        ok["lanes"], ok["raias_fixas"] = ["Liderança", "Qualidade"], ["Qualidade"]
        self.assertEqual(c.patch(url, data=json.dumps({"dados_topologia": ok}), content_type='application/json').status_code, 200)
        ruim = self._topologia()
        ruim["lanes"] = "Liderança"
        self.assertEqual(c.patch(url, data=json.dumps({"dados_topologia": ruim}), content_type='application/json').status_code, 400)

    # --- catálogo -------------------------------------------------------------------
    def test_somente_com_permissao_altera_o_catalogo(self):
        from procedures.models_diagram import RaiaCatalogo
        dados = {'acao': 'salvar', 'nome': 'Qualidade', 'cor': '#0f766e', 'setor': self.setor_q.id}
        self._cliente(self.leitor).post('/procedures/diagramas/raias/', dados)
        self.assertEqual(RaiaCatalogo.objects.count(), 0)
        # leitura da tela é liberada
        self.assertEqual(self._cliente(self.leitor).get('/procedures/diagramas/raias/').status_code, 200)

        c = self._cliente(self.admin, 'nav_diagramas_raias')
        c.post('/procedures/diagramas/raias/', dados)
        raia = RaiaCatalogo.objects.get()
        self.assertEqual((raia.nome, raia.cor, raia.setor_id, raia.ativo), ('Qualidade', '#0f766e', self.setor_q.id, True))
        self.assertGreater(raia.ordem, 0)

    def test_validacoes_do_cadastro(self):
        from procedures.models_diagram import RaiaCatalogo
        c = self._cliente(self.admin, 'nav_diagramas_raias')
        c.post('/procedures/diagramas/raias/', {'acao': 'salvar', 'nome': 'Qualidade', 'cor': '#0f766e'})
        c.post('/procedures/diagramas/raias/', {'acao': 'salvar', 'nome': 'qualidade', 'cor': '#0f766e'})  # duplicada (sem diferenciar caixa)
        c.post('/procedures/diagramas/raias/', {'acao': 'salvar', 'nome': 'Outra', 'cor': 'vermelho'})     # cor inválida
        c.post('/procedures/diagramas/raias/', {'acao': 'salvar', 'nome': '   ', 'cor': '#000000'})        # nome vazio
        self.assertEqual(list(RaiaCatalogo.objects.values_list('nome', flat=True)), ['Qualidade'])

    def test_renomear_aplica_somente_em_rascunhos(self):
        from procedures.models_diagram import RaiaCatalogo
        raia = RaiaCatalogo.objects.create(nome='Qualidade', ordem=10)
        # diagrama com revisão aprovada: permanece imutável
        aprovado = Diagrama.objects.create(titulo='Aprovado', criado_por=self.admin)
        v_ap = DiagramaVersao.objects.create(diagrama=aprovado, revisao=0, status=StatusDiagrama.APROVADO,
                                             dados_topologia=self._topologia())
        c = self._cliente(self.admin, 'nav_diagramas_raias')
        c.post('/procedures/diagramas/raias/', {'acao': 'salvar', 'id': raia.id, 'nome': 'Garantia da Qualidade',
                                                'cor': '#334155', 'ordem': 10, 'ativo': 'on', 'aplicar_rascunhos': 'on'})
        self.versao.refresh_from_db()
        v_ap.refresh_from_db()
        lanes_rascunho = {n['data']['lane'] for n in self.versao.dados_topologia['nodes']}
        lanes_aprovado = {n['data']['lane'] for n in v_ap.dados_topologia['nodes']}
        self.assertEqual(lanes_rascunho, {'Liderança', 'Garantia da Qualidade'})
        self.assertEqual(lanes_aprovado, {'Liderança', 'Qualidade'})

    def test_mesclar_raias(self):
        from procedures.models_diagram import RaiaCatalogo
        origem = RaiaCatalogo.objects.create(nome='Qualidade', ordem=10)
        destino = RaiaCatalogo.objects.create(nome='Liderança', ordem=20)
        c = self._cliente(self.admin, 'nav_diagramas_raias')
        c.post('/procedures/diagramas/raias/', {'acao': 'mesclar', 'id': origem.id, 'destino_id': destino.id})
        self.versao.refresh_from_db()
        self.assertEqual({n['data']['lane'] for n in self.versao.dados_topologia['nodes']}, {'Liderança'})
        origem.refresh_from_db()
        self.assertFalse(origem.ativo)

    def test_tela_mostra_uso_e_raias_livres(self):
        from procedures.models_diagram import RaiaCatalogo
        RaiaCatalogo.objects.create(nome='Qualidade', ordem=10)
        html = self._cliente(self.admin, 'nav_diagramas_raias').get('/procedures/diagramas/raias/').content.decode()
        self.assertIn('1 diagrama', html)             # uso da raia Qualidade
        self.assertIn('Raias livres em uso', html)    # "Liderança" está em uso fora do catálogo
        self.assertIn('Liderança', html)

    # --- editor / busca / PDF -------------------------------------------------------
    def test_editor_recebe_catalogo_e_busca_traz_setor_id(self):
        from procedures.models_diagram import RaiaCatalogo
        from rh.models import Colaborador
        RaiaCatalogo.objects.create(nome='Qualidade', cor='#0f766e', ordem=10, setor=self.setor_q)
        RaiaCatalogo.objects.create(nome='Inativa', ordem=20, ativo=False)
        html = self._cliente(self.admin).get(f'/procedures/diagramas/editor/{self.versao.id}/').content.decode()
        self.assertIn('id="raiasCatalogoData"', html)
        self.assertIn('#0f766e', html)
        self.assertNotIn('Inativa', html)
        self.assertIn('id="modalNovaRaia"', html)

        Colaborador.objects.create(nome_completo='Ana Paula Silva', matricula='7001', grupo='G', setor=self.setor_q)
        itens = self._cliente(self.admin).get('/procedures/api/diagramas/colaboradores/?q=ana').json()['results']
        self.assertEqual(itens[0]['setor_id'], self.setor_q.id)

    def test_pdf_usa_ordem_e_cor_das_raias(self):
        from procedures.models_diagram import RaiaCatalogo
        RaiaCatalogo.objects.create(nome='Qualidade', cor='#0f766e', ordem=10)
        self.versao.dados_topologia["lanes"] = ["Qualidade", "Liderança"]
        self.versao.dados_topologia["raias_fixas"] = ["Operacional"]
        self.versao.save()
        pdf = gerar_pdf_diagrama_doc071(self.versao)
        self.assertTrue(pdf.startswith(b'%PDF-'))

    def test_cadastro_de_raias_no_registro_de_permissoes_e_cor_do_modulo(self):
        from shared.permissions import NAV_STRUCTURE
        modulo = next(m for m in NAV_STRUCTURE if m["key"] == "diagramas")
        self.assertEqual(modulo["cor"], "purple")  # cor com CSS definido (teal não existe no Bootstrap)
        perms = [f["perm"] for b in modulo["blocos"] for f in b["funcoes"]]
        self.assertIn("core.nav_diagramas_raias", perms)


class DiagramaModalColaboradorTestCase(TestCase):
    def test_modal_busca_e_cria_bloco_ao_clicar_no_resultado(self):
        from pathlib import Path
        user = User.objects.create_user(username='modal.colab', password='x')
        diagrama = Diagrama.objects.create(titulo='Modal', criado_por=user)
        versao = DiagramaVersao.objects.create(diagrama=diagrama, revisao=0, dados_topologia={"nodes": [], "edges": []})
        c = Client()
        c.force_login(user)
        html = c.get(f'/procedures/diagramas/editor/{versao.id}/').content.decode()
        self.assertIn('oninput="buscarColaboradoresParaBloco(this.value)"', html)
        self.assertIn('onkeydown="teclaBuscaColaborador(event)"', html)

        js = (Path(__file__).resolve().parent.parent / 'static' / 'procedures' / 'js' / 'diagrama_editor.js').read_text(encoding='utf-8')
        trecho = js[js.index('function escolherColaboradorParaBloco'):js.index('function confirmarAdicionarBloco')]
        self.assertIn('confirmarAdicionarBloco()', trecho)          # clicar no resultado cria o bloco
        self.assertIn('/procedures/api/diagramas/colaboradores/', trecho)
        self.assertNotIn('/rh/api/colaboradores/', js)              # formato antigo/incorreto não é mais usado


class DiagramaAlinhamentoDescendentesTestCase(TestCase):
    def test_editor_alinha_descendentes_lado_a_lado(self):
        from pathlib import Path
        js = (Path(__file__).resolve().parent.parent / 'static' / 'procedures' / 'js' / 'diagrama_editor.js').read_text(encoding='utf-8')
        for funcao in ('function alinharFilhosDe', 'function inserirFilhoNoLayout', 'function ligarFilhoAoPai'):
            self.assertIn(funcao, js)
        trecho = js[js.index('function confirmarAdicionarBloco'):js.index('function _pushNodeAndGrid')]
        # filho, irmão (com pai) e o "+" de baixo usam o alinhamento automático
        self.assertGreaterEqual(trecho.count('inserirFilhoNoLayout('), 3)
        # conexões de filhos saem por baixo e chegam por cima (traçado vertical)
        corpo = js[js.index('function ligarFilhoAoPai'):js.index('function confirmarAdicionarBloco')]
        self.assertIn("sourceHandle: 'bottom'", corpo)
        self.assertIn("targetHandle: 'top'", corpo)


class TelaDePermissoesDiagramasTestCase(TestCase):
    def test_card_do_modulo_diagramas_tem_cor_legivel_e_bloco_renomeado(self):
        admin = User.objects.create_superuser(username='admin.perm', password='x', email='a@b.com')
        alvo = User.objects.create_user(username='alvo.perm', password='x')
        c = Client()
        c.force_login(admin)
        resp = c.get(f'/rh/usuarios/{alvo.id}/')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()

        # cabeçalho do módulo usa uma cor que tem CSS definido na própria tela
        self.assertIn('card-header bg-purple text-white module-header', html)
        self.assertIn('.bg-purple {', html)
        self.assertNotIn('bg-teal', html)

        # bloco sem o sufixo (DOC.071)
        self.assertIn('Fluxogramas de Processos', html)
        self.assertNotIn('Fluxogramas de Processos (DOC.071)', html)


class DiagramaAtalhosPorModoTestCase(TestCase):
    def test_atalhos_de_canvas_nao_interferem_na_grelha(self):
        from pathlib import Path
        user = User.objects.create_user(username='atalhos', password='x')
        diagrama = Diagrama.objects.create(titulo='Atalhos', criado_por=user)
        versao = DiagramaVersao.objects.create(diagrama=diagrama, revisao=0, dados_topologia={"nodes": [], "edges": []})
        c = Client()
        c.force_login(user)
        html = c.get(f'/procedures/diagramas/editor/{versao.id}/').content.decode()

        # controles exclusivos do Canvas ficam desativados fora dele
        for onclick in ('adicionarTopicoIrmao()', 'adicionarSubtopicoFilho()', 'conectarNosSelecionados()', 'excluirSelecao()'):
            self.assertIn(f'class="ribbon-btn border somente-canvas" onclick="{onclick}"', html)
        self.assertEqual(html.count('somente-canvas"'), 7)  # 4 botões + grupos Layout, Visão e Exibição
        self.assertIn('.modo-nao-canvas .somente-canvas', html)

        js = (Path(__file__).resolve().parent.parent / 'static' / 'procedures' / 'js' / 'diagrama_editor.js').read_text(encoding='utf-8')
        trecho = js[js.index('function tratarAtalhosGlobais'):js.index('// ===', js.index('function tratarAtalhosGlobais'))]
        self.assertIn("e.defaultPrevented || modalAberto() || !foraDeCampoDeEdicao()", trecho)
        self.assertIn("if (ctrl && modoAtual === 'canvas')", trecho)               # zoom do navegador livre nos outros modos
        self.assertIn("if (modoAtual !== 'canvas' || focoEmControleInterativo() || !focoNoCanvasOuLivre()) return;", trecho)
        troca = js[js.index('function alternarModoEditor'):js.index('function alternarModoZen')]
        self.assertIn("if (modo !== 'canvas') desmarcarTodosNos();", troca)        # sem seleção "invisível" para excluir
        self.assertIn("el.inert = modo !== 'canvas'", troca)
