"""
Agregação de dados de Ações Registradas de todos os 6 tipos de soluções
Permite visualizar/filtrar ações em uma única tela
"""

from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q, F, Value as V, CharField, Count, Case, When
from django.views import View
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import PlanoAcao, SolucaoA3, Solucao8D, SolucaoRNC, SolucaoGestaoDeMudanca, RevisaoGerencial


class AcoesRegistradasView(LoginRequiredMixin, View):
    """
    View que agrega ações de todos os 6 tipos de soluções
    Permite filtrar por tipo, status, responsável, prioridade, etc.
    """
    login_url = 'login'
    template_name = 'acoes/acoes_registradas.html'
    paginate_by = 50
    
    def get(self, request, *args, **kwargs):
        """Renderiza página de Ações Registradas com filtros"""
        
        # Parâmetros de filtro
        tipo_solucao = request.GET.get('tipo', 'todas')  # todas, plano_acao, a3, 8d, rnc, mudanca, rg
        status = request.GET.get('status', '')
        prioridade = request.GET.get('prioridade', '')
        responsavel = request.GET.get('responsavel', '')
        busca = request.GET.get('busca', '')
        
        # Agregação: Obter ações de cada modelo
        acoes = self._agregar_acoes(tipo_solucao, status, prioridade, responsavel, busca)
        
        # Paginação
        paginator = Paginator(acoes, self.paginate_by)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        # Opções de filtro
        status_choices = [
            ('planejada', 'Planejada'),
            ('em_curso', 'Em Curso/Andamento'),
            ('completa', 'Completa/Concluído'),
            ('retardo', 'Retardo/Atrasada'),
            ('cancelada', 'Cancelada'),
        ]
        
        context = {
            'page_obj': page_obj,
            'acoes': page_obj.object_list,
            'total_acoes': paginator.count,
            'filtro_tipo': tipo_solucao,
            'filtro_status': status,
            'filtro_prioridade': prioridade,
            'filtro_responsavel': responsavel,
            'busca': busca,
            'status_choices': status_choices,
        }
        
        return render(request, self.template_name, context)
    
    def _agregar_acoes(self, tipo_solucao, status, prioridade, responsavel, busca):
        """
        Agrega ações de todos os 6 modelos em uma lista única
        Retorna lista de dicts com campos padronizados
        """
        from django.db.models import Prefetch
        acoes = []
        
        # PlanoAcao
        if tipo_solucao in ['todas', 'plano_acao']:
            planos = PlanoAcao.objects.select_related('solucao').prefetch_related('responsaveis_multiplos')
            planos = self._aplicar_filtros(planos, status, prioridade, responsavel, busca)
            for p in planos:
                acoes.append({
                    'id': f'plano_{p.id}',
                    'tipo_solucao': 'Plano de Ação',
                    'tipo_slug': 'plano_acao',
                    'numero_acao': p.numero_acao or '-',
                    'input_origem': p.input_origem or '-',
                    'problema': p.problema or '-',
                    'laboratorio': p.laboratorio or '-',
                    'kpi': p.kpi or '-',
                    'classificacao': p.get_classificacao_display() if p.classificacao else '-',
                    'status': p.get_status_display() if p.status else '-',
                    'prioridade': 'Sim' if p.prioridade else 'Não',
                    'responsaveis': ', '.join([str(r.nome) for r in p.responsaveis_multiplos.all()]) or (str(p.responsavel_acao.nome) if p.responsavel_acao else '-'),
                    'data_primeira_deadline': p.data_primeira_deadline or '-',
                    'data_segunda_deadline': p.data_deadline or '-',
                    'comentarios': p.comentarios or '-',
                    'acao_eficaz': p.get_acao_eficaz_display() if p.acao_eficaz else '-',
                    'model': 'PlanoAcao',
                    'object_id': p.id,
                    'solucao_id': p.solucao_id,
                })
        
        # SolucaoA3
        if tipo_solucao in ['todas', 'a3']:
            a3s = SolucaoA3.objects.select_related('solucao').prefetch_related('responsaveis_multiplos')
            a3s = self._aplicar_filtros(a3s, status, prioridade, responsavel, busca)
            for a in a3s:
                acoes.append({
                    'id': f'a3_{a.id}',
                    'tipo_solucao': 'Solução A3',
                    'tipo_slug': 'a3',
                    'numero_acao': a.numero_acao or '-',
                    'input_origem': a.input_origine or '-',
                    'problema': a.problema or '-',
                    'laboratorio': a.laboratorio or '-',
                    'kpi': a.kpi or '-',
                    'classificacao': a.get_classificacao_display() if a.classificacao else '-',
                    'status': a.solucao.get_status_display() if a.solucao and a.solucao.status else '-',
                    'prioridade': 'Sim' if a.prioridade else 'Não',
                    'responsaveis': ', '.join([str(r.nome) for r in a.responsaveis_multiplos.all()]) or '-',
                    'data_primeira_deadline': a.data_primeira_deadline or '-',
                    'data_segunda_deadline': a.data_mudanca or '-' if hasattr(a, 'data_mudanca') else '-',
                    'comentarios': a.comentarios or '-',
                    'acao_eficaz': a.get_acao_eficaz_display() if a.acao_eficaz else '-',
                    'model': 'SolucaoA3',
                    'object_id': a.id,
                    'solucao_id': a.solucao_id,
                })
        
        # Solucao8D
        if tipo_solucao in ['todas', '8d']:
            oito_ds = Solucao8D.objects.select_related('solucao').prefetch_related('responsaveis_multiplos')
            oito_ds = self._aplicar_filtros(oito_ds, status, prioridade, responsavel, busca)
            for o in oito_ds:
                acoes.append({
                    'id': f'8d_{o.id}',
                    'tipo_solucao': 'Solução 8D',
                    'tipo_slug': '8d',
                    'numero_acao': o.numero_acao or '-',
                    'input_origem': o.input_origem or '-',
                    'problema': o.problema_identificado or '-',
                    'laboratorio': o.laboratorio or '-',
                    'kpi': o.kpi or '-',
                    'classificacao': o.get_classificacao_display() if o.classificacao else '-',
                    'status': o.status or '-',
                    'prioridade': 'Sim' if o.prioridade else 'Não',
                    'responsaveis': ', '.join([str(r.nome) for r in o.responsaveis_multiplos.all()]) or '-',
                    'data_primeira_deadline': o.data_primeira_deadline or '-',
                    'data_segunda_deadline': o.prazo_projeto or '-',
                    'comentarios': o.comentarios or '-',
                    'acao_eficaz': o.get_acao_eficaz_display() if o.acao_eficaz else '-',
                    'model': 'Solucao8D',
                    'object_id': o.id,
                    'solucao_id': o.solucao_id,
                })
        
        # SolucaoRNC
        if tipo_solucao in ['todas', 'rnc']:
            rncs = SolucaoRNC.objects.select_related('solucao').prefetch_related('responsaveis_multiplos')
            rncs = self._aplicar_filtros(rncs, status, prioridade, responsavel, busca)
            for r in rncs:
                acoes.append({
                    'id': f'rnc_{r.id}',
                    'tipo_solucao': 'RNC',
                    'tipo_slug': 'rnc',
                    'numero_acao': r.numero_acao or '-',
                    'input_origem': r.input_origem or '-',
                    'problema': r.descricao_nc or '-',
                    'laboratorio': r.laboratorio or '-',
                    'kpi': r.kpi or '-',
                    'classificacao': r.get_classificacao_display() if r.classificacao else '-',
                    'status': r.status or '-',
                    'prioridade': 'Sim' if r.prioridade else 'Não',
                    'responsaveis': ', '.join([str(resp.nome) for resp in r.responsaveis_multiplos.all()]) or (str(r.responsavel.nome) if r.responsavel else '-'),
                    'data_primeira_deadline': r.data_primeira_deadline or '-',
                    'data_segunda_deadline': r.data_fechamento or '-',
                    'comentarios': r.comentarios or '-',
                    'acao_eficaz': r.get_acao_eficaz_display() if r.acao_eficaz else r.get_eficacia_display() if r.eficacia else '-',
                    'model': 'SolucaoRNC',
                    'object_id': r.id,
                    'solucao_id': r.solucao_id,
                })
        
        # SolucaoGestaoDeMudanca
        if tipo_solucao in ['todas', 'mudanca']:
            mudancas = SolucaoGestaoDeMudanca.objects.select_related('solucao').prefetch_related('responsaveis_multiplos')
            mudancas = self._aplicar_filtros(mudancas, status, prioridade, responsavel, busca)
            for m in mudancas:
                acoes.append({
                    'id': f'mudanca_{m.id}',
                    'tipo_solucao': 'Gestão de Mudança',
                    'tipo_slug': 'mudanca',
                    'numero_acao': m.numero_acao or '-',
                    'input_origem': m.input_origem or '-',
                    'problema': m.justificativa or '-',
                    'laboratorio': m.laboratorio_acao or '-',
                    'kpi': m.kpi or '-',
                    'classificacao': m.get_classificacao_display() if m.classificacao else '-',
                    'status': m.get_status_display() if m.status else '-',
                    'prioridade': 'Sim' if m.prioridade else 'Não',
                    'responsaveis': ', '.join([str(resp.nome) for resp in m.responsaveis_multiplos.all()]) or m.solicitante or '-',
                    'data_primeira_deadline': m.data_primeira_deadline or '-',
                    'data_segunda_deadline': m.data_mudanca or '-',
                    'comentarios': m.comentarios or '-',
                    'acao_eficaz': m.get_acao_eficaz_display() if m.acao_eficaz else '-',
                    'model': 'SolucaoGestaoDeMudanca',
                    'object_id': m.id,
                    'solucao_id': m.solucao_id,
                })
        
        # RevisaoGerencial
        if tipo_solucao in ['todas', 'rg']:
            rgs = RevisaoGerencial.objects.select_related('solucao').prefetch_related('responsaveis_multiplos')
            rgs = self._aplicar_filtros(rgs, status, prioridade, responsavel, busca)
            for rg in rgs:
                acoes.append({
                    'id': f'rg_{rg.id}',
                    'tipo_solucao': 'Revisão Gerencial',
                    'tipo_slug': 'rg',
                    'numero_acao': rg.numero_acao or '-',
                    'input_origem': rg.input_origem or '-',
                    'problema': rg.analises_criticas or '-',
                    'laboratorio': rg.laboratorio or '-',
                    'kpi': rg.kpi or '-',
                    'classificacao': rg.get_classificacao_display() if rg.classificacao else '-',
                    'status': rg.get_status_display() if rg.status else '-',
                    'prioridade': 'Sim' if rg.prioridade else 'Não',
                    'responsaveis': ', '.join([str(resp.nome) for resp in rg.responsaveis_multiplos.all()]) or rg.representante_direcao or '-',
                    'data_primeira_deadline': rg.data_primeira_deadline or '-',
                    'data_segunda_deadline': rg.data_realizacao or '-',
                    'comentarios': rg.comentarios or '-',
                    'acao_eficaz': rg.get_acao_eficaz_display() if rg.acao_eficaz else '-',
                    'model': 'RevisaoGerencial',
                    'object_id': rg.id,
                    'solucao_id': rg.solucao_id,
                })
        
        return sorted(acoes, key=lambda x: x['data_primeira_deadline'], reverse=True)
    
    def _aplicar_filtros(self, queryset, status, prioridade, responsavel, busca):
        """Aplica filtros ao queryset"""
        if status:
            queryset = queryset.filter(status=status)
        
        if prioridade:
            prioridade_bool = prioridade.lower() == 'sim'
            queryset = queryset.filter(prioridade=prioridade_bool)
        
        if responsavel:
            queryset = queryset.filter(responsaveis_multiplos__id=responsavel)
        
        if busca:
            queryset = queryset.filter(
                Q(numero_acao__icontains=busca) |
                Q(input_origem__icontains=busca) |
                Q(problema__icontains=busca) |
                Q(descricao__icontains=busca) |
                Q(criterios__icontains=busca)
            )
        
        return queryset.distinct()
