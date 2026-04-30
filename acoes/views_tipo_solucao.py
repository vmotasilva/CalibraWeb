# -*- coding: utf-8 -*-
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from .models import TipoSolucao
from .forms import TipoSolucaoForm


class TipoSolucaoListView(LoginRequiredMixin, ListView):
    """Lista todos os tipos de solucao."""
    model = TipoSolucao
    template_name = 'acoes/tipo_solucao_list.html'
    context_object_name = 'tipos'
    paginate_by = 20
    login_url = 'login'

    def get_queryset(self):
        queryset = TipoSolucao.objects.all()

        busca = self.request.GET.get('busca', '')
        if busca:
            queryset = queryset.filter(
                Q(nome__icontains=busca) |
                Q(descricao__icontains=busca)
            )

        ativo = self.request.GET.get('ativo', '')
        if ativo:
            queryset = queryset.filter(ativo=(ativo == 'true'))

        return queryset.order_by('nome')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_tipos'] = TipoSolucao.objects.count()
        context['total_ativos'] = TipoSolucao.objects.filter(ativo=True).count()
        context['total_inativos'] = TipoSolucao.objects.filter(ativo=False).count()
        context['busca'] = self.request.GET.get('busca', '')
        return context


class TipoSolucaoCreateView(LoginRequiredMixin, CreateView):
    """Cria um novo tipo de solucao."""
    model = TipoSolucao
    form_class = TipoSolucaoForm
    template_name = 'acoes/tipo_solucao_form.html'
    success_url = reverse_lazy('acoes:tipo_solucao_list')
    login_url = 'login'

    def form_valid(self, form):
        messages.success(self.request, f"Tipo de solucao '{form.instance.nome}' criado com sucesso!")
        return super().form_valid(form)


class TipoSolucaoUpdateView(LoginRequiredMixin, UpdateView):
    """Atualiza um tipo de solucao."""
    model = TipoSolucao
    form_class = TipoSolucaoForm
    template_name = 'acoes/tipo_solucao_form.html'
    success_url = reverse_lazy('acoes:tipo_solucao_list')
    login_url = 'login'

    def form_valid(self, form):
        messages.success(self.request, f"Tipo de solucao '{form.instance.nome}' atualizado com sucesso!")
        return super().form_valid(form)


class TipoSolucaoDeleteView(LoginRequiredMixin, DeleteView):
    """Deleta um tipo de solucao."""
    model = TipoSolucao
    template_name = 'acoes/tipo_solucao_confirm_delete.html'
    success_url = reverse_lazy('acoes:tipo_solucao_list')
    login_url = 'login'
    context_object_name = 'tipo_solucao'

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Tipo de solucao deletado com sucesso!')
        return super().delete(request, *args, **kwargs)
