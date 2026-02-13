# -*- coding: utf-8 -*-
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Q

from .models import OrigemProblema
from .forms import OrigemProblemaForm


class OrigemProblemaListView(LoginRequiredMixin, ListView):
    """Lista todas as origens de problema"""
    model = OrigemProblema
    template_name = 'acoes/origem_problema_list.html'
    context_object_name = 'origens'
    paginate_by = 20
    login_url = 'login'
    
    def get_queryset(self):
        queryset = OrigemProblema.objects.all()
        
        # Busca por nome ou descrição
        busca = self.request.GET.get('busca', '')
        if busca:
            queryset = queryset.filter(
                Q(nome__icontains=busca) |
                Q(descricao__icontains=busca) |
                Q(codigo__icontains=busca)
            )
        
        # Filtro por status ativo
        ativo = self.request.GET.get('ativo', '')
        if ativo:
            queryset = queryset.filter(ativo=(ativo == 'true'))
        
        return queryset.order_by('nome')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_origens'] = OrigemProblema.objects.count()
        context['total_ativas'] = OrigemProblema.objects.filter(ativo=True).count()
        context['total_inativas'] = OrigemProblema.objects.filter(ativo=False).count()
        context['busca'] = self.request.GET.get('busca', '')
        return context


class OrigemProblemaCreateView(LoginRequiredMixin, CreateView):
    """Cria uma nova origem de problema"""
    model = OrigemProblema
    form_class = OrigemProblemaForm
    template_name = 'acoes/origem_problema_form.html'
    success_url = reverse_lazy('acoes:origem_problema_list')
    login_url = 'login'
    
    def form_valid(self, form):
        messages.success(self.request, f"Origem de problema '{form.instance.nome}' criada com sucesso!")
        return super().form_valid(form)


class OrigemProblemaUpdateView(LoginRequiredMixin, UpdateView):
    """Atualiza uma origem de problema existente"""
    model = OrigemProblema
    form_class = OrigemProblemaForm
    template_name = 'acoes/origem_problema_form.html'
    success_url = reverse_lazy('acoes:origem_problema_list')
    login_url = 'login'
    
    def form_valid(self, form):
        messages.success(self.request, f"Origem de problema '{form.instance.nome}' atualizada com sucesso!")
        return super().form_valid(form)


class OrigemProblemaDeleteView(LoginRequiredMixin, DeleteView):
    """Deleta uma origem de problema"""
    model = OrigemProblema
    template_name = 'acoes/origem_problema_confirm_delete.html'
    success_url = reverse_lazy('acoes:origem_problema_list')
    login_url = 'login'
    context_object_name = 'origem_problema'
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, f"Origem de problema deletada com sucesso!")
        return super().delete(request, *args, **kwargs)
