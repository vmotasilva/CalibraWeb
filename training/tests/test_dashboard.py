from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from datetime import date

from procedures.models import (
    ColaboradorPerfil,
    GrupoTreinamento,
    MatrizProcedimento,
    PerfilTreinamento,
    Procedimento,
    RegistroTreinamento,
    ResponsavelTreinamentoMatriz,
    SubAreaProcedimento,
    SubGrupoTreinamento,
)
from rh.models import Colaborador

class TestDashboardFilters(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='tester', password='pass')
        # Criar colaborador e procedimento
        self.col = Colaborador.objects.create(matricula='2000', nome_completo='Colab Teste')
        self.proc = Procedimento.objects.create(codigo='PROCX', nome='Proc X', numero_revisao='01')

        # Registro vigente (data + revisao bate)
        RegistroTreinamento.objects.create(colaborador=self.col, procedimento=self.proc, data_treinamento=date.today(), revisao_treinada='01', tipo='PROCEDIMENTO')
        # Registro pendente (sem data)
        RegistroTreinamento.objects.create(colaborador=self.col, procedimento=self.proc, data_treinamento=None, revisao_treinada='00', tipo='PROCEDIMENTO')

    def test_filtered_status_vigente(self):
        client = self.client
        client.force_login(self.user)
        url = reverse('training:dashboard_filtered') + '?status=vigente'
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Should only count the vigente record
        self.assertEqual(data['status_distribuicao']['vigente'], 1)
        self.assertGreaterEqual(data['total_treinamentos'], 0)
        self.assertTrue(all(r['data'] != 'Pendente' for r in data['dados_tabela']))

    def test_filtered_status_pendente(self):
        client = self.client
        client.force_login(self.user)
        url = reverse('training:dashboard_filtered') + '?status=pendente'
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Should only count the pendente record
        self.assertEqual(data['status_distribuicao']['pendente'], 1)
        self.assertTrue(any(r['data'] == 'Pendente' for r in data['dados_tabela']))


class TestDashboardTreinamentosView(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='dashboard-user', password='pass')

        self.instrutor_responsavel = Colaborador.objects.create(
            matricula='3000',
            nome_completo='ELMO OLIVEIRA SILVA JUNIOR',
            grupo='Treinamento',
            turno='ADM',
        )
        self.outro_instrutor = Colaborador.objects.create(
            matricula='3001',
            nome_completo='GEORGE FERREIRA DA COSTA SILVA',
            grupo='Treinamento',
            turno='ADM',
        )
        self.colaborador = Colaborador.objects.create(
            matricula='4000',
            nome_completo='COLABORADOR TESTE',
            grupo='Produção',
            turno='ADM',
        )
        self.outro_colaborador = Colaborador.objects.create(
            matricula='4001',
            nome_completo='COLABORADOR EXTRA',
            grupo='Produção',
            turno='ADM',
        )
        self.colaborador_geral = Colaborador.objects.create(
            matricula='4002',
            nome_completo='COLABORADOR GERAL',
            grupo='Produção',
            turno='ADM',
        )
        self.colaborador_alpha = Colaborador.objects.create(
            matricula='4003',
            nome_completo='ALFA COLABORADOR',
            grupo='Produção',
            turno='ADM',
        )

        self.matriz = MatrizProcedimento.objects.create(nome='MATRIZ TESTE')
        self.outra_matriz = MatrizProcedimento.objects.create(nome='MATRIZ EXTRA')
        self.sub_area = SubAreaProcedimento.objects.create(matriz=self.matriz, nome='SUBAREA A')

        self.procedimento = Procedimento.objects.create(
            codigo='PROC-001',
            nome='Procedimento Pendente',
            numero_revisao='01',
            matriz='MATRIZ TESTE',
            sub_area='SUBAREA A',
        )
        self.outro_procedimento = Procedimento.objects.create(
            codigo='PROC-002',
            nome='Outro Procedimento',
            numero_revisao='01',
            matriz='MATRIZ EXTRA',
        )
        self.procedimento_geral = Procedimento.objects.create(
            codigo='PROC-003',
            nome='Procedimento Geral da Matriz',
            numero_revisao='01',
            matriz='MATRIZ TESTE',
            sub_area='',
        )

        perfil = PerfilTreinamento.objects.create(nome='Perfil Teste')
        grupo = GrupoTreinamento.objects.create(perfil=perfil, nome='Grupo Teste')
        subgrupo = SubGrupoTreinamento.objects.create(grupo=grupo, nome='Subgrupo Teste')
        subgrupo.procedimentos.add(self.procedimento)

        outro_perfil = PerfilTreinamento.objects.create(nome='Perfil Extra')
        outro_grupo = GrupoTreinamento.objects.create(perfil=outro_perfil, nome='Grupo Extra')
        outro_subgrupo = SubGrupoTreinamento.objects.create(grupo=outro_grupo, nome='Subgrupo Extra')
        outro_subgrupo.procedimentos.add(self.outro_procedimento)

        perfil_geral = PerfilTreinamento.objects.create(nome='Perfil Geral')
        grupo_geral = GrupoTreinamento.objects.create(perfil=perfil_geral, nome='Grupo Geral')
        subgrupo_geral = SubGrupoTreinamento.objects.create(grupo=grupo_geral, nome='Subgrupo Geral')
        subgrupo_geral.procedimentos.add(self.procedimento_geral)

        ColaboradorPerfil.objects.create(
            colaborador=self.colaborador,
            perfil=perfil,
            data_atribuicao=date.today(),
        )
        ColaboradorPerfil.objects.create(
            colaborador=self.outro_colaborador,
            perfil=outro_perfil,
            data_atribuicao=date.today(),
        )
        ColaboradorPerfil.objects.create(
            colaborador=self.colaborador_geral,
            perfil=perfil_geral,
            data_atribuicao=date.today(),
        )
        ColaboradorPerfil.objects.create(
            colaborador=self.colaborador_alpha,
            perfil=perfil,
            data_atribuicao=date.today(),
        )

        ResponsavelTreinamentoMatriz.objects.create(
            matriz=self.matriz,
            turno='ADM',
            colaborador=self.outro_instrutor,
        )
        ResponsavelTreinamentoMatriz.objects.create(
            matriz=self.matriz,
            sub_area=self.sub_area,
            turno='ADM',
            colaborador=self.instrutor_responsavel,
        )
        ResponsavelTreinamentoMatriz.objects.create(
            matriz=self.outra_matriz,
            turno='ADM',
            colaborador=self.outro_instrutor,
        )

        RegistroTreinamento.objects.create(
            colaborador=self.colaborador,
            procedimento=self.procedimento,
            data_treinamento=None,
            revisao_treinada='00',
            tipo='PROCEDIMENTO',
        )
        RegistroTreinamento.objects.create(
            colaborador=self.outro_colaborador,
            procedimento=self.outro_procedimento,
            data_treinamento=None,
            revisao_treinada='00',
            tipo='PROCEDIMENTO',
        )
        RegistroTreinamento.objects.create(
            colaborador=self.colaborador_geral,
            procedimento=self.procedimento_geral,
            data_treinamento=None,
            revisao_treinada='00',
            tipo='PROCEDIMENTO',
        )
        RegistroTreinamento.objects.create(
            colaborador=self.colaborador_alpha,
            procedimento=self.procedimento,
            data_treinamento=None,
            revisao_treinada='00',
            tipo='PROCEDIMENTO',
        )

    def test_dashboard_renderiza_filtro_tabela_pendencias_e_nome_abreviado(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('training:dashboard_treinamentos'),
            {'instrutor_responsavel': str(self.instrutor_responsavel.id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Instrutor Responsável')
        self.assertContains(response, 'Treinamentos Pendentes')
        self.assertContains(response, 'PROC-001')
        self.assertContains(response, 'Procedimento Pendente')
        self.assertContains(response, 'SUBAREA A')
        self.assertNotContains(response, 'PROC-002')
        self.assertNotContains(response, 'PROC-003')
        self.assertNotContains(response, 'Responsáveis por Matriz/Turno')
        self.assertNotContains(response, 'Dashboard custom classes para estilos migrados do inline')
        self.assertEqual(response.context['total_pendencias_dashboard'], 2)
        self.assertEqual(
            [(item['procedimento'], item['colaborador']) for item in response.context['pendencias_dashboard']],
            [
                ('PROC-001', 'ALFA COLABORADOR'),
                ('PROC-001', 'COLABORADOR TESTE'),
            ],
        )
        self.assertEqual(response.context['demanda_por_instrutor'][0]['nome'], 'ELMO JUNIOR')

    def test_dashboard_prioriza_responsavel_da_subarea_antes_do_geral(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('training:dashboard_treinamentos'))

        self.assertEqual(response.status_code, 200)
        demanda = {item['nome']: item for item in response.context['demanda_por_instrutor']}
        self.assertEqual(demanda['ELMO JUNIOR']['pendentes'], 2)
        self.assertEqual(demanda['GEORGE SILVA']['pendentes'], 2)

    def test_dashboard_ordena_pendencias_por_procedimento_e_colaborador(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('training:dashboard_treinamentos'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'table table-sm table-striped table-hover align-middle dashboard-pending-table mb-0', html=False)
        self.assertContains(response, 'Nome do Procedimento')
        self.assertContains(response, 'Sub-área')

        pendencias = response.context['pendencias_dashboard']
        self.assertEqual(
            [(item['procedimento'], item['procedimento_nome'], item['sub_area'], item['colaborador']) for item in pendencias],
            [
                ('PROC-001', 'Procedimento Pendente', 'SUBAREA A', 'ALFA COLABORADOR'),
                ('PROC-001', 'Procedimento Pendente', 'SUBAREA A', 'COLABORADOR TESTE'),
                ('PROC-002', 'Outro Procedimento', '-', 'COLABORADOR EXTRA'),
                ('PROC-003', 'Procedimento Geral da Matriz', '-', 'COLABORADOR GERAL'),
            ],
        )

    def test_dashboard_pagina_tabela_de_pendencias(self):
        self.client.force_login(self.user)

        perfil_paginacao = PerfilTreinamento.objects.create(nome='Perfil Paginação')
        grupo_paginacao = GrupoTreinamento.objects.create(perfil=perfil_paginacao, nome='Grupo Paginação')
        subgrupo_paginacao = SubGrupoTreinamento.objects.create(grupo=grupo_paginacao, nome='Subgrupo Paginação')
        ColaboradorPerfil.objects.create(
            colaborador=self.outro_colaborador,
            perfil=perfil_paginacao,
            data_atribuicao=date.today(),
        )

        for index in range(10):
            procedimento_extra = Procedimento.objects.create(
                codigo=f'PROC-10{index}',
                nome=f'Procedimento Paginação {index:02}',
                numero_revisao='01',
                matriz='MATRIZ EXTRA',
            )
            subgrupo_paginacao.procedimentos.add(procedimento_extra)
            RegistroTreinamento.objects.create(
                colaborador=self.outro_colaborador,
                procedimento=procedimento_extra,
                data_treinamento=None,
                revisao_treinada='00',
                tipo='PROCEDIMENTO',
            )

        filtros = {'matriz': ['MATRIZ TESTE', 'MATRIZ EXTRA']}
        response = self.client.get(reverse('training:dashboard_treinamentos'), filtros)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_pendencias_dashboard'], 14)
        self.assertEqual(response.context['pendencias_page_size'], 10)
        self.assertEqual(len(response.context['pendencias_dashboard']), 10)
        self.assertTrue(response.context['pendencias_page_obj'].has_next())
        self.assertContains(response, 'Mostrando 1-10 de 14 pendências')
        self.assertContains(response, 'Itens por página')

        second_page = self.client.get(
            reverse('training:dashboard_treinamentos'),
            {
                'matriz': ['MATRIZ TESTE', 'MATRIZ EXTRA'],
                'pendencias_page': '2',
            },
        )

        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(second_page.context['pendencias_page_start'], 11)
        self.assertEqual(second_page.context['pendencias_page_end'], 14)
        self.assertEqual(
            [item['procedimento'] for item in second_page.context['pendencias_dashboard']],
            ['PROC-106', 'PROC-107', 'PROC-108', 'PROC-109'],
        )
        self.assertContains(second_page, 'Mostrando 11-14 de 14 pendências')

    def test_export_csv_respeita_filtro_instrutor_responsavel(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('training:dashboard_exportar_csv'),
            {'instrutor_responsavel': str(self.instrutor_responsavel.id)},
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8-sig')
        self.assertIn('PROC-001', content)
        self.assertNotIn('PROC-002', content)
        self.assertNotIn('PROC-003', content)

    def test_dashboard_contem_apenas_colaboradores_ativos_nao_afastados_nao_em_ferias(self):
        self.client.force_login(self.user)
        
        # Criar colaboradores inativos/afastados/ferias para verificar se são excluídos
        colab_inativo = Colaborador.objects.create(
            matricula='9991', nome_completo='COLAB INATIVO', is_active=False
        )
        colab_afastado = Colaborador.objects.create(
            matricula='9992', nome_completo='COLAB AFASTADO', afastado=True
        )
        colab_ferias = Colaborador.objects.create(
            matricula='9993', nome_completo='COLAB FERIAS', em_ferias=True
        )
        
        response = self.client.get(reverse('training:dashboard_treinamentos'))
        self.assertEqual(response.status_code, 200)
        
        colaboradores_todos = response.context['colaboradores_todos']
        colab_ids = [c['id'] for c in colaboradores_todos]
        
        # Inativo, afastado e em ferias não devem estar na lista
        self.assertNotIn(colab_inativo.id, colab_ids)
        self.assertNotIn(colab_afastado.id, colab_ids)
        self.assertNotIn(colab_ferias.id, colab_ids)
        
        # Colaborador ativo comum deve estar na lista
        self.assertIn(self.colaborador.id, colab_ids)

