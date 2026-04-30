# -*- coding: utf-8 -*-
from django.shortcuts import redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Q

from .models import KPIOpcao
from .forms import KPIOpcaoForm


class KPIOpcaoListView(LoginRequiredMixin, ListView):
    """Lista todas as opcoes de KPI"""
    model = KPIOpcao
    template_name = 'acoes/kpi_opcao_list.html'
    context_object_name = 'kpis'
    paginate_by = 20
    login_url = 'login'

    def get_queryset(self):
        queryset = KPIOpcao.objects.all()

        busca = self.request.GET.get('busca', '')
        if busca:
            queryset = queryset.filter(
                Q(nome__icontains=busca) |
                Q(descricao__icontains=busca) |
                Q(codigo__icontains=busca)
            )

        ativo = self.request.GET.get('ativo', '')
        if ativo:
            queryset = queryset.filter(ativo=(ativo == 'true'))

        return queryset.order_by('nome')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_kpis'] = KPIOpcao.objects.count()
        context['total_ativas'] = KPIOpcao.objects.filter(ativo=True).count()
        context['total_inativas'] = KPIOpcao.objects.filter(ativo=False).count()
        context['busca'] = self.request.GET.get('busca', '')
        return context


class KPIOpcaoCreateView(LoginRequiredMixin, CreateView):
    """Cria uma nova opcao de KPI"""
    model = KPIOpcao
    form_class = KPIOpcaoForm
    template_name = 'acoes/kpi_opcao_form.html'
    success_url = reverse_lazy('acoes:kpi_opcao_list')
    login_url = 'login'

    def form_valid(self, form):
        messages.success(self.request, f"KPI '{form.instance.nome}' criado com sucesso!")
        return super().form_valid(form)


class KPIOpcaoUpdateView(LoginRequiredMixin, UpdateView):
    """Atualiza uma opcao de KPI"""
    model = KPIOpcao
    form_class = KPIOpcaoForm
    template_name = 'acoes/kpi_opcao_form.html'
    success_url = reverse_lazy('acoes:kpi_opcao_list')
    login_url = 'login'

    def form_valid(self, form):
        messages.success(self.request, f"KPI '{form.instance.nome}' atualizado com sucesso!")
        return super().form_valid(form)


class KPIOpcaoDeleteView(LoginRequiredMixin, DeleteView):
    """Deleta uma opcao de KPI"""
    model = KPIOpcao
    template_name = 'acoes/kpi_opcao_confirm_delete.html'
    success_url = reverse_lazy('acoes:kpi_opcao_list')
    login_url = 'login'
    context_object_name = 'kpi'

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'KPI deletado com sucesso!')
        return super().delete(request, *args, **kwargs)
