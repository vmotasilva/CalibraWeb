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
from .models import PlanoAcao, SolucaoA3, Solucao8D, SolucaoRNC, SolucaoGestaoDeMudanca, RevisaoGerencial, LinhaAcao


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
        ver_por = request.GET.get('ver_por', 'acoes')  # acoes ou responsaveis
        
        # Agregação: Obter ações de cada modelo
        acoes = self._agregar_acoes(tipo_solucao, status, prioridade, responsavel, busca)
        
        # Estatísticas gerais (sem filtros de status/responsavel para mostrar panorama completo)
        todas_acoes = self._agregar_acoes(tipo_solucao, '', '', '', '')
        estatisticas = self._calcular_estatisticas(todas_acoes)
        
        # Estatísticas por responsável
        acoes_por_responsavel = self._agrupar_por_responsavel(todas_acoes)
        
        # Lista de responsáveis para o filtro
        responsaveis_unicos = sorted(set([r['responsavel'] for r in acoes_por_responsavel if r['responsavel'] != '-']))
        
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
            'ver_por': ver_por,
            'status_choices': status_choices,
            'estatisticas': estatisticas,
            'acoes_por_responsavel': acoes_por_responsavel[:20],  # Top 20
            'responsaveis_unicos': responsaveis_unicos,
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
            planos = PlanoAcao.objects.select_related('solucao', 'solucao__acao_corretiva').prefetch_related('responsaveis_multiplos')
            planos = self._aplicar_filtros(planos, status, prioridade, responsavel, busca, campo_descricao='descricao')
            for p in planos:
                # Obter numero_registro da ação corretiva ou do próprio plano
                acao_corretiva = p.solucao.acao_corretiva if p.solucao else None
                numero_registro = acao_corretiva.numero_registro if acao_corretiva else (p.numero_registro or '-')
                
                acoes.append({
                    'id': f'plano_{p.id}',
                    'tipo_solucao': 'Plano de Ação',
                    'tipo_slug': 'plano_acao',
                    'numero_registro': numero_registro,
                    'numero_acao': p.numero_acao or '-',
                    'input_origem': p.input_origem or '-',
                    'problema': p.problema or '-',
                    'descricao': p.descricao or '-',
                    'laboratorio': p.laboratorio or '-',
                    'kpi': p.kpi or '-',
                    'classificacao': p.get_classificacao_display() if p.classificacao else '-',
                    'status': p.get_status_display() if p.status else '-',
                    'prioridade': 'Sim' if p.prioridade else 'Não',
                    'responsaveis': ', '.join([str(r.nome_completo) for r in p.responsaveis_multiplos.all()]) or (str(p.responsavel_acao.nome_completo) if p.responsavel_acao else '-'),
                    'data_primeira_deadline': p.data_primeira_deadline,
                    'data_segunda_deadline': p.data_deadline,
                    'comentarios': p.comentarios or '-',
                    'acao_eficaz': p.get_acao_eficaz_display() if p.acao_eficaz else '-',
                    'model': 'PlanoAcao',
                    'object_id': p.id,
                    'solucao_id': p.solucao_id,
                })
        
        # SolucaoA3
        if tipo_solucao in ['todas', 'a3']:
            a3s = SolucaoA3.objects.select_related('solucao', 'solucao__acao_corretiva').prefetch_related('responsaveis_multiplos')
            a3s = self._aplicar_filtros(a3s, status, prioridade, responsavel, busca, campo_descricao='objetivo')
            for a in a3s:
                # Obter numero_registro: a3_numero ou numero_registro da ação corretiva
                acao_corretiva = a.solucao.acao_corretiva if a.solucao else None
                numero_registro = a.a3_numero or (acao_corretiva.numero_registro if acao_corretiva else '-')
                
                acoes.append({
                    'id': f'a3_{a.id}',
                    'tipo_solucao': 'Solução A3',
                    'tipo_slug': 'a3',
                    'numero_registro': numero_registro,
                    'numero_acao': a.numero_acao or '-',
                    'input_origem': a.input_origem or '-',
                    'problema': a.problema or '-',
                    'descricao': a.objetivo or '-',
                    'laboratorio': a.laboratorio or '-',
                    'kpi': a.kpi or '-',
                    'classificacao': a.get_classificacao_display() if a.classificacao else '-',
                    'status': a.solucao.get_status_display() if a.solucao and a.solucao.status else '-',
                    'prioridade': 'Sim' if a.prioridade else 'Não',
                    'responsaveis': ', '.join([str(r.nome_completo) for r in a.responsaveis_multiplos.all()]) or '-',
                    'data_primeira_deadline': a.data_primeira_deadline,
                    'data_segunda_deadline': a.data_mudanca if hasattr(a, 'data_mudanca') else None,
                    'comentarios': a.comentarios or '-',
                    'acao_eficaz': a.get_acao_eficaz_display() if a.acao_eficaz else '-',
                    'model': 'SolucaoA3',
                    'object_id': a.id,
                    'solucao_id': a.solucao_id,
                })
        
        # Solucao8D
        if tipo_solucao in ['todas', '8d']:
            oito_ds = Solucao8D.objects.select_related('solucao', 'solucao__acao_corretiva').prefetch_related('responsaveis_multiplos')
            oito_ds = self._aplicar_filtros(oito_ds, status, prioridade, responsavel, busca, campo_descricao='d2_descricao', campo_problema='problema_identificado')
            for o in oito_ds:
                # Obter numero_registro: numero_formulario ou numero_registro da ação corretiva
                acao_corretiva = o.solucao.acao_corretiva if o.solucao else None
                numero_registro = o.numero_formulario or (acao_corretiva.numero_registro if acao_corretiva else '-')
                
                acoes.append({
                    'id': f'8d_{o.id}',
                    'tipo_solucao': 'Solução 8D',
                    'tipo_slug': '8d',
                    'numero_registro': numero_registro,
                    'numero_acao': o.numero_acao or '-',
                    'input_origem': o.input_origem or '-',
                    'problema': o.problema_identificado or '-',
                    'descricao': o.d2_descricao or '-',
                    'laboratorio': o.laboratorio or '-',
                    'kpi': o.kpi or '-',
                    'classificacao': o.get_classificacao_display() if o.classificacao else '-',
                    'status': o.status or '-',
                    'prioridade': 'Sim' if o.prioridade else 'Não',
                    'responsaveis': ', '.join([str(r.nome_completo) for r in o.responsaveis_multiplos.all()]) or '-',
                    'data_primeira_deadline': o.data_primeira_deadline,
                    'data_segunda_deadline': o.prazo_projeto,
                    'comentarios': o.comentarios or '-',
                    'acao_eficaz': o.get_acao_eficaz_display() if o.acao_eficaz else '-',
                    'model': 'Solucao8D',
                    'object_id': o.id,
                    'solucao_id': o.solucao_id,
                })
        
        # SolucaoRNC
        if tipo_solucao in ['todas', 'rnc']:
            rncs = SolucaoRNC.objects.select_related('solucao', 'solucao__acao_corretiva').prefetch_related('responsaveis_multiplos')
            rncs = self._aplicar_filtros(rncs, status, prioridade, responsavel, busca, campo_descricao='descricao', campo_problema='descricao_nc')
            for r in rncs:
                # Obter numero_registro: numero_rnc ou numero_registro da ação corretiva
                acao_corretiva = r.solucao.acao_corretiva if r.solucao else None
                numero_registro = r.numero_rnc or (acao_corretiva.numero_registro if acao_corretiva else '-')
                
                acoes.append({
                    'id': f'rnc_{r.id}',
                    'tipo_solucao': 'RNC',
                    'tipo_slug': 'rnc',
                    'numero_registro': numero_registro,
                    'numero_acao': r.numero_acao or '-',
                    'input_origem': r.input_origem or '-',
                    'problema': r.descricao_nc or '-',
                    'descricao': r.descricao or '-',
                    'laboratorio': r.laboratorio or '-',
                    'kpi': r.kpi or '-',
                    'classificacao': r.get_classificacao_display() if r.classificacao else '-',
                    'status': r.status or '-',
                    'prioridade': 'Sim' if r.prioridade else 'Não',
                    'responsaveis': ', '.join([str(resp.nome_completo) for resp in r.responsaveis_multiplos.all()]) or (str(r.responsavel.nome_completo) if r.responsavel else '-'),
                    'data_primeira_deadline': r.data_primeira_deadline,
                    'data_segunda_deadline': r.data_fechamento,
                    'comentarios': r.comentarios or '-',
                    'acao_eficaz': r.get_acao_eficaz_display() if r.acao_eficaz else r.get_eficacia_display() if r.eficacia else '-',
                    'model': 'SolucaoRNC',
                    'object_id': r.id,
                    'solucao_id': r.solucao_id,
                })
        
        # SolucaoGestaoDeMudanca
        if tipo_solucao in ['todas', 'mudanca']:
            mudancas = SolucaoGestaoDeMudanca.objects.select_related('solucao', 'solucao__acao_corretiva').prefetch_related('responsaveis_multiplos')
            mudancas = self._aplicar_filtros(mudancas, status, prioridade, responsavel, busca, campo_descricao='descricao_acao', campo_problema='justificativa')
            for m in mudancas:
                # Obter numero_registro da ação corretiva ou do próprio modelo
                acao_corretiva = m.solucao.acao_corretiva if m.solucao else None
                numero_registro = m.numero_registro or (acao_corretiva.numero_registro if acao_corretiva else '-')
                
                acoes.append({
                    'id': f'mudanca_{m.id}',
                    'tipo_solucao': 'Gestão de Mudança',
                    'tipo_slug': 'mudanca',
                    'numero_registro': numero_registro,
                    'numero_acao': m.numero_acao or '-',
                    'input_origem': m.input_origem or '-',
                    'problema': m.justificativa or '-',
                    'descricao': m.descricao_acao or '-',
                    'laboratorio': m.laboratorio_acao or '-',
                    'kpi': m.kpi or '-',
                    'classificacao': m.get_classificacao_display() if m.classificacao else '-',
                    'status': m.get_status_display() if m.status else '-',
                    'prioridade': 'Sim' if m.prioridade else 'Não',
                    'responsaveis': ', '.join([str(resp.nome_completo) for resp in m.responsaveis_multiplos.all()]) or m.solicitante or '-',
                    'data_primeira_deadline': m.data_primeira_deadline,
                    'data_segunda_deadline': m.data_mudanca,
                    'comentarios': m.comentarios or '-',
                    'acao_eficaz': m.get_acao_eficaz_display() if m.acao_eficaz else '-',
                    'model': 'SolucaoGestaoDeMudanca',
                    'object_id': m.id,
                    'solucao_id': m.solucao_id,
                })
        
        # RevisaoGerencial
        if tipo_solucao in ['todas', 'rg']:
            rgs = RevisaoGerencial.objects.select_related('solucao', 'solucao__acao_corretiva').prefetch_related('responsaveis_multiplos')
            rgs = self._aplicar_filtros(rgs, status, prioridade, responsavel, busca, campo_descricao='descricao', campo_problema='analises_criticas')
            for rg in rgs:
                # Obter numero_registro: numero_rg ou numero_registro da ação corretiva
                acao_corretiva = rg.solucao.acao_corretiva if rg.solucao else None
                numero_registro = rg.numero_rg or (acao_corretiva.numero_registro if acao_corretiva else '-')
                
                acoes.append({
                    'id': f'rg_{rg.id}',
                    'tipo_solucao': 'Revisão Gerencial',
                    'tipo_slug': 'rg',
                    'numero_registro': numero_registro,
                    'numero_acao': rg.numero_acao or '-',
                    'input_origem': rg.input_origem or '-',
                    'problema': rg.analises_criticas or '-',
                    'descricao': rg.descricao or '-',
                    'laboratorio': rg.laboratorio or '-',
                    'kpi': rg.kpi or '-',
                    'classificacao': rg.get_classificacao_display() if rg.classificacao else '-',
                    'status': rg.get_status_display() if rg.status else '-',
                    'prioridade': 'Sim' if rg.prioridade else 'Não',
                    'responsaveis': ', '.join([str(resp.nome_completo) for resp in rg.responsaveis_multiplos.all()]) or rg.representante_direcao or '-',
                    'data_primeira_deadline': rg.data_primeira_deadline,
                    'data_segunda_deadline': rg.data_realizacao,
                    'comentarios': rg.comentarios or '-',
                    'acao_eficaz': rg.get_acao_eficaz_display() if rg.acao_eficaz else '-',
                    'model': 'RevisaoGerencial',
                    'object_id': rg.id,
                    'solucao_id': rg.solucao_id,
                })
        
        # LinhaAcao - Ações individuais dentro dos Planos de Ação
        if tipo_solucao in ['todas', 'plano_acao', 'linha_acao']:
            linhas = LinhaAcao.objects.select_related('plano_acao', 'plano_acao__solucao', 'plano_acao__solucao__acao_corretiva').prefetch_related('responsaveis_multiplos')
            
            # Aplicar filtros específicos para LinhaAcao
            if status:
                linhas = linhas.filter(status=status)
            if prioridade:
                prioridade_bool = prioridade.lower() == 'sim'
                linhas = linhas.filter(prioridade=prioridade_bool)
            if responsavel:
                # Filtrar por responsaveis_multiplos ou por responsaveis_externos
                linhas = linhas.filter(
                    Q(responsaveis_multiplos__nome_completo__icontains=responsavel) |
                    Q(responsavel_acao__nome_completo__icontains=responsavel) |
                    Q(responsaveis_externos__icontains=responsavel)
                )
            if busca:
                linhas = linhas.filter(
                    Q(numero_acao__icontains=busca) |
                    Q(input_origem__icontains=busca) |
                    Q(problema__icontains=busca) |
                    Q(descricao__icontains=busca)
                )
            
            linhas = linhas.distinct()
            
            for linha in linhas:
                # Obter responsáveis (internos + externos)
                responsaveis_internos = ', '.join([str(r.nome_completo) for r in linha.responsaveis_multiplos.all()])
                responsavel_principal = str(linha.responsavel_acao.nome_completo) if linha.responsavel_acao else ''
                responsaveis_externos = linha.responsaveis_externos or ''
                
                # Juntar todos os responsáveis
                todos_responsaveis = []
                if responsavel_principal:
                    todos_responsaveis.append(responsavel_principal)
                if responsaveis_internos:
                    todos_responsaveis.append(responsaveis_internos)
                if responsaveis_externos:
                    todos_responsaveis.append(responsaveis_externos)
                
                responsaveis_str = ', '.join(todos_responsaveis) if todos_responsaveis else '-'
                
                # Obter informações do PlanoAcao pai
                plano = linha.plano_acao
                acao_corretiva = plano.solucao.acao_corretiva if plano and plano.solucao else None
                numero_registro = acao_corretiva.numero_registro if acao_corretiva else plano.numero_registro if plano else '-'
                
                acoes.append({
                    'id': f'linha_{linha.id}',
                    'tipo_solucao': 'Linha de Ação',
                    'tipo_slug': 'linha_acao',
                    'numero_registro': numero_registro,
                    'numero_acao': linha.numero_acao or '-',
                    'input_origem': linha.input_origem or '-',
                    'problema': linha.problema or '-',
                    'descricao': linha.descricao or '-',
                    'laboratorio': plano.laboratorio if plano and hasattr(plano, 'laboratorio') else '-',
                    'kpi': linha.kpi or '-',
                    'classificacao': linha.get_classificacao_display() if linha.classificacao else '-',
                    'status': linha.get_status_display() if linha.status else '-',
                    'prioridade': 'Sim' if linha.prioridade else 'Não',
                    'responsaveis': responsaveis_str,
                    'data_primeira_deadline': linha.data_primeira_deadline,
                    'data_segunda_deadline': linha.data_deadline,
                    'comentarios': linha.comentarios or '-',
                    'acao_eficaz': linha.get_acao_eficaz_display() if linha.acao_eficaz else '-',
                    'model': 'LinhaAcao',
                    'object_id': linha.id,
                    'plano_acao_id': plano.id if plano else None,
                    'numero_registro': numero_registro,
                })
        
        # Sort by date, putting None values at the end
        # Compute single deadline field: most recent date between data_primeira_deadline and data_segunda_deadline
        for acao in acoes:
            d1 = acao.get('data_primeira_deadline')
            d2 = acao.get('data_segunda_deadline')
            if d1 and d2:
                acao['deadline'] = max(d1, d2)
            elif d1:
                acao['deadline'] = d1
            elif d2:
                acao['deadline'] = d2
            else:
                acao['deadline'] = None
        
        return sorted(acoes, key=lambda x: (x['deadline'] is None, x['deadline'] or ''), reverse=True)
    
    def _calcular_estatisticas(self, acoes):
        """Calcula estatísticas gerais das ações"""
        from collections import Counter
        
        total = len(acoes)
        
        # Contagem por tipo
        por_tipo = Counter([a['tipo_solucao'] for a in acoes])
        
        # Contagem por status - usando slugs para facilitar acesso no template
        status_count = Counter()
        planejada = 0
        em_curso = 0
        completa = 0
        retardo = 0
        cancelada = 0
        
        for a in acoes:
            status = a['status']
            if status == '-':
                continue
            status_count[status] += 1
            
            # Categorizar por tipo simplificado
            if 'Planejada' in status:
                planejada += 1
            elif 'Curso' in status or 'Andamento' in status:
                em_curso += 1
            elif 'Complet' in status or 'Conclu' in status:
                completa += 1
            elif 'Retardo' in status or 'Atras' in status:
                retardo += 1
            elif 'Cancelada' in status:
                cancelada += 1
        
        # Contagem de prioridades
        prioridades = sum(1 for a in acoes if a['prioridade'] == 'Sim')
        
        # Contagem de eficácia
        eficaz = sum(1 for a in acoes if 'Eficaz' in str(a['acao_eficaz']) and 'Não' not in str(a['acao_eficaz']))
        nao_eficaz = sum(1 for a in acoes if 'Não Eficaz' in str(a['acao_eficaz']))
        parcialmente_eficaz = sum(1 for a in acoes if 'Parcialmente' in str(a['acao_eficaz']))
        
        return {
            'total': total,
            'por_tipo': dict(por_tipo),
            'por_status': dict(status_count),
            'planejada': planejada,
            'em_curso': em_curso,
            'completa': completa,
            'retardo': retardo,
            'cancelada': cancelada,
            'prioridades': prioridades,
            'eficaz': eficaz,
            'nao_eficaz': nao_eficaz,
            'parcialmente_eficaz': parcialmente_eficaz,
        }
    
    def _agrupar_por_responsavel(self, acoes):
        """Agrupa ações por responsável e retorna lista ordenada"""
        from collections import defaultdict
        
        responsaveis_dict = defaultdict(lambda: {
            'planejada': 0,
            'em_curso': 0,
            'completa': 0,
            'retardo': 0,
            'cancelada': 0,
            'total': 0
        })
        
        for acao in acoes:
            # Separar múltiplos responsáveis
            responsaveis = [r.strip() for r in str(acao['responsaveis']).split(',') if r.strip() and r.strip() != '-']
            
            for resp in responsaveis:
                responsaveis_dict[resp]['total'] += 1
                
                # Contagem por status
                status_slug = acao['status'].lower().replace(' ', '_').replace('/', '_')
                if 'planejada' in status_slug:
                    responsaveis_dict[resp]['planejada'] += 1
                elif 'curso' in status_slug or 'andamento' in status_slug:
                    responsaveis_dict[resp]['em_curso'] += 1
                elif 'complet' in status_slug or 'conclu' in status_slug:
                    responsaveis_dict[resp]['completa'] += 1
                elif 'retardo' in status_slug or 'atras' in status_slug:
                    responsaveis_dict[resp]['retardo'] += 1
                elif 'cancelada' in status_slug:
                    responsaveis_dict[resp]['cancelada'] += 1
        
        # Converter para lista e ordenar por total
        resultado = [
            {
                'responsavel': resp,
                **dados
            }
            for resp, dados in responsaveis_dict.items()
        ]
        
        return sorted(resultado, key=lambda x: x['total'], reverse=True)
    
    def _aplicar_filtros(self, queryset, status, prioridade, responsavel, busca, campo_descricao='descricao', campo_problema='problema'):
        """Aplica filtros ao queryset"""
        if status:
            queryset = queryset.filter(status=status)
        
        if prioridade:
            prioridade_bool = prioridade.lower() == 'sim'
            queryset = queryset.filter(prioridade=prioridade_bool)
        
        if responsavel:
            try:
                queryset = queryset.filter(
                    Q(responsaveis_multiplos__nome_completo__icontains=responsavel) |
                    Q(responsavel_acao__nome_completo__icontains=responsavel)
                )
            except Exception:
                queryset = queryset.filter(
                    responsaveis_multiplos__nome_completo__icontains=responsavel
                )
        
        if busca:
            busca_q = Q(numero_acao__icontains=busca)
            if campo_problema:
                busca_q |= Q(**{f'{campo_problema}__icontains': busca})
            if campo_descricao:
                busca_q |= Q(**{f'{campo_descricao}__icontains': busca})
            queryset = queryset.filter(busca_q)
        
        return queryset.distinct()
