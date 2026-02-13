# -*- coding: utf-8 -*-
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from django.views.generic import (
    CreateView, UpdateView, DeleteView, DetailView, ListView, View
)
from django.forms import modelformset_factory
from django.urls import reverse_lazy
from django.http import JsonResponse
from datetime import timedelta, date
import unicodedata

from .models import (
    Solucao, PlanoAcao, SolucaoA3, Solucao8D, SolucaoRNC,
    SolucaoGestaoDeMudanca, RevisaoGerencial, AcaoCorretiva, AcaoComentario
)
from .forms import (
    PlanoAcaoForm, SolucaoA3Form, Solucao8DForm,
    SolucaoRNCForm, SolucaoGestaoDeMudancaForm, RevisaoGerencialForm,
    AcaoCorretivaForm, AcaoComentarioForm, AcaoCorretivaModalForm
)


# ============================================================================
# VIEWS ANTIGAS (Mantidas para compatibilidade)
# ============================================================================

@login_required
def listar_acoes(request):
    """Lista todas as ações corretivas/preventivas com filtros."""
    from rh.models import Colaborador
    from django.utils import timezone

    # Atualizar status de ações vencidas para ATRASADA
    # Ações que não estão concluídas e passaram da data de vencimento
    hoje = timezone.now().date()
    AcaoCorretiva.objects.exclude(
        Q(status='concluida') | Q(status='cancelada') | Q(status='atrasada')
    ).filter(
        data_vencimento__lt=hoje
    ).update(status='atrasada')

    def normalize_spaces(value):
        return " ".join(value.split())

    def status_key(value):
        value = normalize_spaces(value).lower().replace("_", " ")
        value = "".join(
            ch for ch in unicodedata.normalize("NFKD", value)
            if not unicodedata.combining(ch)
        )
        return value

    status_map = {
        "aberta": "aberta",
        "aberto": "aberta",
        "em progresso": "em_progresso",
        "em andamento": "em_progresso",
        "concluida": "concluida",
        "concluido": "concluida",
        "cancelada": "cancelada",
        "cancelado": "cancelada",
        "atrasada": "atrasada",
        "atrasado": "atrasada",
    }
    
    acoes = AcaoCorretiva.objects.all()
    
    # Obter lista de valores únicos para os filtros (remove duplicatas e espacos)
    tipos_solucao = sorted({
        normalize_spaces(t) for t in AcaoCorretiva.objects.values_list('tipo_solucao', flat=True) if t
    })
    origens = sorted({
        normalize_spaces(o) for o in AcaoCorretiva.objects.values_list('origem', flat=True) if o
    })
    anos = sorted({
        a for a in AcaoCorretiva.objects.values_list('ano', flat=True) if a
    }, reverse=True)
    responsaveis = Colaborador.objects.filter(afastado=False).order_by('nome_completo')
    
    # Filtros
    filtro_tipo_solucao = request.GET.get('tipo_solucao', '')
    filtro_origem = request.GET.get('origem', '')
    filtro_responsavel = request.GET.get('responsavel', '')
    filtro_status = request.GET.get('status', '')
    filtro_ano = request.GET.get('ano', '')
    filtro_busca = request.GET.get('busca', '')
    
    if filtro_tipo_solucao:
        acoes = acoes.filter(tipo_solucao__iexact=filtro_tipo_solucao)
    
    if filtro_origem:
        acoes = acoes.filter(origem__iexact=filtro_origem)
    
    if filtro_responsavel:
        acoes = acoes.filter(responsavel_id=filtro_responsavel)
    
    if filtro_status:
        filtro_status_key = status_key(filtro_status)
        filtro_status = status_map.get(filtro_status_key, filtro_status)

        if filtro_status == 'atrasada':
            # Filtrar apenas ações com status 'atrasada' (já atualizadas automaticamente)
            acoes = acoes.filter(status='atrasada')
        else:
            if filtro_status == 'em_progresso':
                acoes = acoes.filter(
                    Q(status__iexact='em_progresso') | Q(status__iexact='em andamento') | Q(status__iexact='em_andamento')
                )
            elif filtro_status == 'concluida':
                acoes = acoes.filter(Q(status__iexact='concluida') | Q(status__iexact='concluido'))
            elif filtro_status == 'cancelada':
                acoes = acoes.filter(Q(status__iexact='cancelada') | Q(status__iexact='cancelado'))
            else:
                acoes = acoes.filter(status=filtro_status)
    
    if filtro_ano:
        acoes = acoes.filter(ano=filtro_ano)
    
    if filtro_busca:
        acoes = acoes.filter(
            Q(numero_registro__icontains=filtro_busca) |
            Q(descricao__icontains=filtro_busca)
        )
    
    # Calcular totais GERAIS (todas as ações, sem filtros)
    hoje = timezone.now().date()
    total_concluido = AcaoCorretiva.objects.filter(
        Q(status__iexact='concluida') | Q(status__iexact='concluido')
    ).count()
    total_em_andamento = AcaoCorretiva.objects.filter(
        Q(status__iexact='em_progresso') | Q(status__iexact='em andamento') | Q(status__iexact='em_andamento')
    ).count()
    total_cancelado = AcaoCorretiva.objects.filter(
        Q(status__iexact='cancelada') | Q(status__iexact='cancelado')
    ).count()
    total_atrasado = AcaoCorretiva.objects.filter(status='atrasada').count()
    
    context = {
        'acoes': acoes,
        'filtro_tipo_solucao': filtro_tipo_solucao,
        'filtro_origem': filtro_origem,
        'filtro_responsavel': filtro_responsavel,
        'filtro_status': filtro_status,
        'filtro_ano': filtro_ano,
        'filtro_busca': filtro_busca,
        'total_concluido': total_concluido,
        'total_em_andamento': total_em_andamento,
        'total_cancelado': total_cancelado,
        'total_atrasado': total_atrasado,
        'tipos_solucao': tipos_solucao,
        'origens': origens,
        'anos': anos,
        'responsaveis': responsaveis,
    }
    
    return render(request, 'acoes/listar_acoes.html', context)


@login_required
def salvar_acao_corretiva_modal(request):
    """Salva/atualiza uma AcaoCorretiva via POST (modal)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=400)
    
    acao_id = request.POST.get('id')
    
    if acao_id:
        acao = get_object_or_404(AcaoCorretiva, id=acao_id)
        form = AcaoCorretivaModalForm(request.POST, instance=acao)
    else:
        form = AcaoCorretivaModalForm(request.POST)
    
    if form.is_valid():
        acao = form.save()
        messages.success(request, f'Ação "{acao.numero_registro}" salva com sucesso!')
        return JsonResponse({
            'success': True,
            'message': f'Ação "{acao.numero_registro}" salva com sucesso!',
            'id': acao.id
        })
    else:
        errors = {field: [str(err) for err in errs] for field, errs in form.errors.items()}
        return JsonResponse({
            'success': False,
            'errors': errors,
            'message': 'Erro ao salvar. Verifique os campos.'
        }, status=400)


@login_required
def detalhe_acao(request, acao_id):
    """Exibe detalhes de uma ação."""
    acao = get_object_or_404(AcaoCorretiva, id=acao_id)
    
    context = {
        'acao': acao,
        'comentarios': acao.comentarios.all(),
    }
    
    return render(request, 'acoes/detalhe_acao.html', context)


# ============================================================================
# MIXINS
# ============================================================================

class SolucaoAcessoMixin(LoginRequiredMixin):
    """Mixin para verificar acesso a soluções"""
    login_url = 'login'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Ações Corretivas/Preventivas"
        return context


# ============================================================================
# PLANO DE AÇÃO VIEWS
# ============================================================================

class PlanoAcaoListView(SolucaoAcessoMixin, ListView):
    """Lista de Planos de Ação"""
    model = PlanoAcao
    template_name = 'acoes/plano_acao_list.html'
    context_object_name = 'planos'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = PlanoAcao.objects.select_related('solucao', 'responsavel_acao').order_by('-criado_em')
        
        # Filtro por status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filtro por prioridade
        prioridade = self.request.GET.get('prioridade')
        if prioridade == 'true':
            queryset = queryset.filter(prioridade=True)
        
        # Busca por texto
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(descricao__icontains=search) |
                Q(problema__icontains=search) |
                Q(numero_acao__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_planos'] = PlanoAcao.objects.count()
        context['planos_em_andamento'] = PlanoAcao.objects.filter(status__in=['planejada', 'em_curso']).count()
        context['planos_atrasados'] = PlanoAcao.objects.filter(
            status__in=['planejada', 'em_curso'],
            data_deadline__lt=timezone.now().date()
        ).count()
        return context


class PlanoAcaoCreateView(SolucaoAcessoMixin, View):
    """Criar novo Plano de Ação com múltiplas ações"""
    template_name = 'acoes/planoacao_form_table.html'
    form_class = PlanoAcaoForm
    success_url = reverse_lazy('acoes:plano_acao_list')
    formset_prefix = 'acoes'

    def _build_formset(self, data=None):
        formset_class = modelformset_factory(
            PlanoAcao,
            form=self.form_class,
            extra=1,
            can_delete=False,
        )
        return formset_class(
            data=data,
            queryset=PlanoAcao.objects.none(),
            prefix=self.formset_prefix,
        )

    def get(self, request, *args, **kwargs):
        formset = self._build_formset()
        numero_registro = request.GET.get('numero_registro', '').strip()
        context = {
            'formset': formset,
            'numero_registro': numero_registro,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        formset = self._build_formset(data=request.POST)
        if formset.is_valid():
            from .forms import criar_numero_registro
            numero_registro = request.POST.get('numero_registro', '').strip() or criar_numero_registro()
            planos_salvos = 0

            for form in formset:
                if not form.has_changed():
                    continue
                plano = form.save(commit=False)
                if not plano.numero_registro:
                    plano.numero_registro = numero_registro
                plano.save()
                form.save_m2m()
                planos_salvos += 1

            if planos_salvos == 0:
                messages.error(request, 'Adicione pelo menos uma ação na tabela.')
                return render(request, self.template_name, {'formset': formset})

            messages.success(
                request,
                f"Plano de Ação '{numero_registro}' criado com {planos_salvos} ação(ões)!"
            )
            return redirect(self.success_url)

        return render(request, self.template_name, {'formset': formset})


class PlanoAcaoUpdateView(SolucaoAcessoMixin, UpdateView):
    """Atualizar Plano de Ação"""
    model = PlanoAcao
    form_class = PlanoAcaoForm
    template_name = 'acoes/planoacao_form.html'
    success_url = reverse_lazy('acoes:plano_acao_list')
    
    def form_valid(self, form):
        messages.success(self.request, "Plano de Ação atualizado com sucesso!")
        return super().form_valid(form)


@login_required
def plano_acao_delete(request, pk):
    """Excluir uma ação do plano"""
    plano = get_object_or_404(PlanoAcao, pk=pk)
    numero_registro = plano.numero_registro

    if request.method != 'POST':
        return redirect('acoes:plano_acao_detail', pk=pk)

    plano.delete()
    messages.success(request, 'Ação removida com sucesso.')

    if numero_registro:
        primeiro = PlanoAcao.objects.filter(numero_registro=numero_registro).order_by('id').first()
        if primeiro:
            return redirect('acoes:plano_acao_detail', pk=primeiro.id)

    return redirect('acoes:plano_acao_list')


class LinhaAcaoUpdateView(LoginRequiredMixin, UpdateView):
    """Atualizar Linha de Ação"""
    from acoes.models import LinhaAcao
    from acoes.forms import LinhaAcaoForm
    
    model = LinhaAcao
    form_class = LinhaAcaoForm
    template_name = 'acoes/linhaacao_form.html'
    
    def get_success_url(self):
        solucao = self.object.plano_acao.solucao
        return reverse('acoes:detalhe_solucao', kwargs={'solucao_id': solucao.id})
    
    def form_valid(self, form):
        messages.success(self.request, "Ação atualizada com sucesso!")
        return super().form_valid(form)


@login_required
def linha_acao_delete(request, pk):
    """Excluir uma linha de ação"""
    from acoes.models import LinhaAcao
    
    linha = get_object_or_404(LinhaAcao, pk=pk)
    solucao = linha.plano_acao.solucao

    if request.method != 'POST':
        return redirect('acoes:detalhe_solucao', solucao_id=solucao.id)

    linha.delete()
    messages.success(request, 'Ação removida com sucesso.')

    return redirect('acoes:detalhe_solucao', solucao_id=solucao.id)



class PlanoAcaoDetailView(SolucaoAcessoMixin, DetailView):
    """Detalhes do Plano de Ação"""
    model = PlanoAcao
    template_name = 'acoes/planoacao_detail.html'
    context_object_name = 'plano'

    def get_context_data(self, **kwargs):
        from acoes.models import LinhaAcao
        context = super().get_context_data(**kwargs)
        # Buscar linhas de ação deste plano
        context['acoes'] = LinhaAcao.objects.filter(
            plano_acao=self.object
        ).order_by('numero_acao')
        acoes = context['acoes']
        hoje = date.today()
        completas = 0
        em_curso = 0
        atrasadas = 0
        for acao in acoes:
            if acao.status == 'completa':
                completas += 1
            if acao.status == 'em_curso':
                em_curso += 1
            is_atrasada = bool(
                acao.data_deadline
                and acao.data_deadline < hoje
                and acao.status not in ['completa', 'cancelada']
            )
            acao.is_atrasada = is_atrasada
            if is_atrasada:
                atrasadas += 1

        context['hoje'] = hoje
        context['total_acoes'] = len(acoes)
        context['acoes_completas'] = completas
        context['acoes_em_curso'] = em_curso
        context['acoes_atrasadas'] = atrasadas
        return context


# ============================================================================
# A3 VIEWS
# ============================================================================

class SolucaoA3ListView(SolucaoAcessoMixin, ListView):
    """Lista de Soluções A3"""
    model = SolucaoA3
    template_name = 'acoes/solucao_a3_list.html'
    context_object_name = 'a3s'
    paginate_by = 20
    
    def get_queryset(self):
        return SolucaoA3.objects.select_related('lider_projeto', 'plano_acao_relacionado').order_by('-data_criacao')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_a3'] = SolucaoA3.objects.count()
        context['a3_com_plano_acao'] = SolucaoA3.objects.filter(plano_acao_relacionado__isnull=False).count()
        return context


class SolucaoA3CreateView(SolucaoAcessoMixin, CreateView):
    """Criar novo A3"""
    model = SolucaoA3
    form_class = SolucaoA3Form
    template_name = 'acoes/solucaoa3_form.html'
    success_url = reverse_lazy('acoes:solucao_a3_list')
    
    def form_valid(self, form):
        a3 = form.save(commit=False)
        
        # Gerar número de A3 se não existir
        if not a3.a3_numero:
            a3.a3_numero = timezone.now().strftime('%Y-%m-%d')
        
        a3.save()
        messages.success(self.request, f"A3 '{a3.a3_numero}' criado com sucesso!")
        return super().form_valid(form)


class SolucaoA3UpdateView(SolucaoAcessoMixin, UpdateView):
    """Atualizar A3"""
    model = SolucaoA3
    form_class = SolucaoA3Form
    template_name = 'acoes/solucaoa3_form.html'
    success_url = reverse_lazy('acoes:solucao_a3_list')
    
    def form_valid(self, form):
        messages.success(self.request, "A3 atualizado com sucesso!")
        return super().form_valid(form)


class SolucaoA3DetailView(SolucaoAcessoMixin, DetailView):
    """Detalhes do A3"""
    model = SolucaoA3
    template_name = 'acoes/solucaoa3_detail.html'
    context_object_name = 'a3'


# ============================================================================
# 8D VIEWS
# ============================================================================

class Solucao8DListView(SolucaoAcessoMixin, ListView):
    """Lista de Soluções 8D"""
    model = Solucao8D
    template_name = 'acoes/solucao_8d_list.html'
    context_object_name = 'oito_ds'
    paginate_by = 20
    
    def get_queryset(self):
        return Solucao8D.objects.select_related('lider_8d').order_by('-data_abertura')


class Solucao8DCreateView(SolucaoAcessoMixin, CreateView):
    """Criar novo 8D"""
    model = Solucao8D
    form_class = Solucao8DForm
    template_name = 'acoes/solucao8d_form.html'
    success_url = reverse_lazy('acoes:solucao_8d_list')
    
    def form_valid(self, form):
        oito_d = form.save(commit=False)
        
        # Gerar número do formulário se não existir
        if not oito_d.numero_formulario:
            oito_d.numero_formulario = f"8D-{timezone.now().strftime('%Y%m%d%H%M%S')}"
        
        oito_d.save()
        messages.success(self.request, f"8D '{oito_d.numero_formulario}' criado com sucesso!")
        return super().form_valid(form)


class Solucao8DUpdateView(SolucaoAcessoMixin, UpdateView):
    """Atualizar 8D"""
    model = Solucao8D
    form_class = Solucao8DForm
    template_name = 'acoes/solucao8d_form.html'
    success_url = reverse_lazy('acoes:solucao_8d_list')
    
    def form_valid(self, form):
        messages.success(self.request, "8D atualizado com sucesso!")
        return super().form_valid(form)


class Solucao8DDetailView(SolucaoAcessoMixin, DetailView):
    """Detalhes do 8D"""
    model = Solucao8D
    template_name = 'acoes/solucao8d_detail.html'
    context_object_name = 'oito_d'


# ============================================================================
# RNC VIEWS
# ============================================================================

class SolucaoRNCListView(SolucaoAcessoMixin, ListView):
    """Lista de RNCs"""
    model = SolucaoRNC
    template_name = 'acoes/solucao_rnc_list.html'
    context_object_name = 'rncs'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = SolucaoRNC.objects.select_related('responsavel', 'plano_acao_relacionado').order_by('-data_abertura')
        
        # Filtro por classificação
        classificacao = self.request.GET.get('classificacao')
        if classificacao:
            queryset = queryset.filter(classificacao=classificacao)
        
        # Filtro por risco
        risco = self.request.GET.get('risco')
        if risco:
            queryset = queryset.filter(risco=risco)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_rncs'] = SolucaoRNC.objects.count()
        context['rncs_criticas'] = SolucaoRNC.objects.filter(classificacao='critica').count()
        context['rncs_em_aberto'] = SolucaoRNC.objects.filter(eficacia__isnull=True).count()
        return context


class SolucaoRNCCreateView(SolucaoAcessoMixin, CreateView):
    """Criar novo RNC"""
    model = SolucaoRNC
    form_class = SolucaoRNCForm
    template_name = 'acoes/solucao_rnc_form.html'
    success_url = reverse_lazy('acoes:solucao_rnc_list')
    
    def form_valid(self, form):
        rnc = form.save(commit=False)
        
        # Gerar número RNC se não existir
        if not rnc.numero_rnc:
            rnc.numero_rnc = f"RNC-{timezone.now().strftime('%Y%m%d%H%M')}"
        
        rnc.save()
        messages.success(self.request, f"RNC '{rnc.numero_rnc}' criada com sucesso!")
        return super().form_valid(form)


class SolucaoRNCUpdateView(SolucaoAcessoMixin, UpdateView):
    """Atualizar RNC"""
    model = SolucaoRNC
    form_class = SolucaoRNCForm
    template_name = 'acoes/solucao_rnc_form.html'
    success_url = reverse_lazy('acoes:solucao_rnc_list')


class SolucaoRNCDetailView(SolucaoAcessoMixin, DetailView):
    """Detalhes do RNC"""
    model = SolucaoRNC
    template_name = 'acoes/solucao_rnc_detail.html'
    context_object_name = 'rnc'


# ============================================================================
# GESTÃO DE MUDANÇA VIEWS
# ============================================================================

class SolucaoGestaoDeMudancaListView(SolucaoAcessoMixin, ListView):
    """Lista de Gestões de Mudança"""
    model = SolucaoGestaoDeMudanca
    template_name = 'acoes/solucao_gestao_mudanca_list.html'
    context_object_name = 'mudancas'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = SolucaoGestaoDeMudanca.objects.select_related('responsavel_mudanca').order_by('-data_abertura')
        
        # Filtro por status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset


class SolucaoGestaoDeMudancaCreateView(SolucaoAcessoMixin, CreateView):
    """Criar nova Gestão de Mudança"""
    model = SolucaoGestaoDeMudanca
    form_class = SolucaoGestaoDeMudancaForm
    template_name = 'acoes/solucaogesta_de_mudanca_form.html'
    success_url = reverse_lazy('acoes:solucao_gestao_mudanca_list')
    
    def form_valid(self, form):
        mudanca = form.save(commit=False)
        
        # Gerar número de registro se não existir
        if not mudanca.numero_registro:
            mudanca.numero_registro = f"GM-{timezone.now().strftime('%Y%m%d%H%M')}"
        
        mudanca.save()
        messages.success(self.request, f"Gestão de Mudança '{mudanca.numero_registro}' criada com sucesso!")
        return super().form_valid(form)


class SolucaoGestaoDeMudancaUpdateView(SolucaoAcessoMixin, UpdateView):
    """Atualizar Gestão de Mudança"""
    model = SolucaoGestaoDeMudanca
    form_class = SolucaoGestaoDeMudancaForm
    template_name = 'acoes/solucaogesta_de_mudanca_form.html'
    success_url = reverse_lazy('acoes:solucao_gestao_mudanca_list')


class SolucaoGestaoDeMudancaDetailView(SolucaoAcessoMixin, DetailView):
    """Detalhes da Gestão de Mudança"""
    model = SolucaoGestaoDeMudanca
    template_name = 'acoes/solucao_gestao_mudanca_detail.html'
    context_object_name = 'mudanca'


# ============================================================================
# REVISÃO GERENCIAL VIEWS
# ============================================================================

class RevisaoGerencialListView(SolucaoAcessoMixin, ListView):
    """Lista de Revisões Gerenciais"""
    model = RevisaoGerencial
    template_name = 'acoes/revisao_gerencial_list.html'
    context_object_name = 'revisoes'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = RevisaoGerencial.objects.select_related('plano_acao_relacionado').order_by('-data_realizacao')
        
        # Filtro por status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset


class RevisaoGerencialCreateView(SolucaoAcessoMixin, CreateView):
    """Criar nova Revisão Gerencial"""
    model = RevisaoGerencial
    form_class = RevisaoGerencialForm
    template_name = 'acoes/revisaogerencial_form.html'
    success_url = reverse_lazy('acoes:revisao_gerencial_list')
    
    def form_valid(self, form):
        rg = form.save(commit=False)
        
        # Gerar número RG se não existir
        if not rg.numero_rg:
            rg.numero_rg = f"RG-{timezone.now().strftime('%Y%m%d%H%M')}"
        
        rg.save()
        messages.success(self.request, f"Revisão Gerencial '{rg.numero_rg}' criada com sucesso!")
        return super().form_valid(form)


class RevisaoGerencialUpdateView(SolucaoAcessoMixin, UpdateView):
    """Atualizar Revisão Gerencial"""
    model = RevisaoGerencial
    form_class = RevisaoGerencialForm
    template_name = 'acoes/revisaogerencial_form.html'
    success_url = reverse_lazy('acoes:revisao_gerencial_list')


class RevisaoGerencialDetailView(SolucaoAcessoMixin, DetailView):
    """Detalhes da Revisão Gerencial"""
    model = RevisaoGerencial
    template_name = 'acoes/revisaogerencial_detail.html'
    context_object_name = 'revisao'


# ============================================================================
# DASHBOARD VIEWS
# ============================================================================

class AcoesDashboardView(SolucaoAcessoMixin, ListView):
    """Dashboard geral de Ações"""
    model = Solucao
    template_name = 'acoes/dashboard.html'
    context_object_name = 'acoes'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Estatísticas gerais
        context['total_acoes'] = AcaoCorretiva.objects.filter(ativo=True).count()
        context['acoes_em_progresso'] = AcaoCorretiva.objects.filter(status='em_progresso', ativo=True).count()
        context['acoes_vencidas'] = AcaoCorretiva.objects.filter(
            status__in=['aberta', 'em_progresso'],
            data_vencimento__lt=timezone.now().date(),
            ativo=True
        ).count()
        
        # Soluções por tipo
        context['total_planos'] = PlanoAcao.objects.count()
        context['total_a3s'] = SolucaoA3.objects.count()
        context['total_8ds'] = Solucao8D.objects.count()
        context['total_rncs'] = SolucaoRNC.objects.count()
        context['total_mudancas'] = SolucaoGestaoDeMudanca.objects.count()
        context['total_revisoes'] = RevisaoGerencial.objects.count()
        
        # Ações recentes
        context['acoes_recentes'] = AcaoCorretiva.objects.filter(ativo=True).order_by('-data_abertura')[:5]
        
        # Soluções recentes
        context['solucoes_recentes'] = Solucao.objects.order_by('-data_criacao')[:5]
        
        return context


# ============================================================================
# API VIEWS - JSON RESPONSES
# ============================================================================

@login_required
def obter_proximo_numero(request):
    """Retorna o próximo número sequencial para um tipo de solução.
    
    Parâmetros: tipo (plano_acao, a3, 8d, rnc, gestao_mudanca, revisao_gerencial)
    Retorna: JSON com próximo número e tipo
    """
    tipo = request.GET.get('tipo', '')
    
    if not tipo:
        return JsonResponse({'error': 'Tipo não informado'}, status=400)
    
    try:
        # Mapear tipos para modelos e campos
        modelo_campo_map = {
            'plano_acao': (PlanoAcao, 'numero_acao'),
            'a3': (SolucaoA3, 'numero_acao'),  # A3 também usa numero_acao
            '8d': (Solucao8D, 'numero_acao'),
            'rnc': (SolucaoRNC, 'numero_acao'),
            'gestao_mudanca': (SolucaoGestaoDeMudanca, 'numero_acao'),
            'revisao_gerencial': (RevisaoGerencial, 'numero_acao'),
        }
        
        if tipo not in modelo_campo_map:
            return JsonResponse({'error': 'Tipo inválido'}, status=400)
        
        modelo, campo = modelo_campo_map[tipo]
        
        # Contar quantos registros existem para este tipo
        # Filtrando por numero_acao não nulo (para contar apenas registros com número atribuído)
        count = modelo.objects.filter(**{f'{campo}__isnull': False}).count()
        
        # Próximo número é count + 1, formatado com 3 dígitos
        proximo_numero = str(count + 1).zfill(3)
        
        return JsonResponse({
            'tipo': tipo,
            'proximo_numero': proximo_numero,
            'total_existente': count
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
