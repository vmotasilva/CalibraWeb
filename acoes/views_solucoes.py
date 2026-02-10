from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, FileResponse
from django.db.models import Q
from .models import (
    AcaoCorretiva,
    Solucao,
    TemplateSolucao,
    PlanoAcao,
    SolucaoA3,
    Solucao8D,
    SolucaoRNC,
    SolucaoGestaoDeMudanca,
    RevisaoGerencial
)


@login_required
def listar_templates(request):
    """Lista todos os templates de solução disponíveis"""
    templates = TemplateSolucao.objects.filter(ativo=True).order_by('tipo')
    
    context = {
        'templates': templates,
    }
    
    return render(request, 'acoes/listar_templates.html', context)


@login_required
def download_template(request, template_id):
    """Faz download de um template PDF"""
    template = get_object_or_404(TemplateSolucao, id=template_id, ativo=True)
    
    if template.arquivo_pdf:
        response = FileResponse(template.arquivo_pdf.open('rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="template_{template.get_tipo_display()}.pdf"'
        return response
    
    return JsonResponse({'error': 'Arquivo não encontrado'}, status=404)



@login_required
def listar_solucoes(request):
    """Lista todas as soluções com filtros"""
    solucoes = Solucao.objects.select_related('acao_corretiva', 'responsavel')
    
    # Filtros
    tipo_filter = request.GET.get('tipo')
    status_filter = request.GET.get('status')
    busca = request.GET.get('busca', '')
    
    if tipo_filter:
        solucoes = solucoes.filter(tipo=tipo_filter)
    
    if status_filter:
        solucoes = solucoes.filter(status=status_filter)
    
    if busca:
        solucoes = solucoes.filter(
            Q(titulo__icontains=busca) | Q(descricao__icontains=busca)
        )
    
    # Contar por tipo
    contagem = {
        'total': Solucao.objects.count(),
        'plano_acao': Solucao.objects.filter(tipo='plano_acao').count(),
        'a3': Solucao.objects.filter(tipo='a3').count(),
        '8d': Solucao.objects.filter(tipo='8d').count(),
        'rnc': Solucao.objects.filter(tipo='rnc').count(),
        'gestao_mudanca': Solucao.objects.filter(tipo='gestao_mudanca').count(),
        'revisao_gerencial': Solucao.objects.filter(tipo='revisao_gerencial').count(),
    }
    
    context = {
        'solucoes': solucoes,
        'contagem': contagem,
        'tipo_selecionado': tipo_filter,
        'status_selecionado': status_filter,
        'busca': busca,
    }
    
    return render(request, 'acoes/listar_solucoes.html', context)


@login_required
def detalhe_solucao(request, solucao_id):
    """Mostra detalhes de uma solução"""
    solucao = get_object_or_404(Solucao, id=solucao_id)
    
    # Carrega a solução específica do tipo
    if solucao.tipo == 'plano_acao':
        detalhes = solucao.plano_acao
    elif solucao.tipo == 'a3':
        detalhes = solucao.a3
    elif solucao.tipo == '8d':
        detalhes = solucao.oito_d
    elif solucao.tipo == 'rnc':
        detalhes = solucao.rnc
    elif solucao.tipo == 'gestao_mudanca':
        detalhes = solucao.gestao_mudanca
    elif solucao.tipo == 'revisao_gerencial':
        detalhes = solucao.revisao_gerencial
    else:
        detalhes = None
    
    context = {
        'solucao': solucao,
        'detalhes': detalhes,
    }
    
    return render(request, 'acoes/detalhe_solucao.html', context)


@login_required
def criar_solucao(request, acao_id):
    """Cria uma nova solução para uma ação corretiva"""
    acao = get_object_or_404(AcaoCorretiva, id=acao_id)
    
    if request.method == 'POST':
        tipo = request.POST.get('tipo')
        
        if not tipo or tipo not in [choice[0] for choice in Solucao.TIPO_SOLUCAO_CHOICES]:
            return JsonResponse({'error': 'Tipo de solução inválido'}, status=400)
        
        # Criar solução base
        solucao = Solucao.objects.create(
            acao_corretiva=acao,
            tipo=tipo,
            titulo=request.POST.get('titulo', f'Solução {tipo} para {acao.numero_registro}'),
            descricao=request.POST.get('descricao', ''),
            responsavel_id=request.POST.get('responsavel'),
        )
        
        # Criar solução específica do tipo
        if tipo == 'plano_acao':
            PlanoAcao.objects.create(
                solucao=solucao,
                acao_proposta=request.POST.get('acao_proposta', ''),
                responsavel_acao_id=request.POST.get('responsavel_acao'),
                data_inicio=request.POST.get('data_inicio'),
                data_conclusao=request.POST.get('data_conclusao'),
            )
        elif tipo == 'a3':
            SolucaoA3.objects.create(
                solucao=solucao,
                problema_descricao=request.POST.get('problema_descricao', ''),
                problema_impacto=request.POST.get('problema_impacto', ''),
                situacao_atual=request.POST.get('situacao_atual', ''),
                analise_causas=request.POST.get('analise_causas', ''),
                causa_raiz=request.POST.get('causa_raiz', ''),
                contramedidas=request.POST.get('contramedidas', ''),
                resultados_esperados=request.POST.get('resultados_esperados', ''),
            )
        elif tipo == '8d':
            Solucao8D.objects.create(
                solucao=solucao,
                d1_time=request.POST.get('d1_time', ''),
                d2_descricao=request.POST.get('d2_descricao', ''),
                d2_especificacoes=request.POST.get('d2_especificacoes', ''),
            )
        elif tipo == 'rnc':
            SolucaoRNC.objects.create(
                solucao=solucao,
                nc_descricao=request.POST.get('nc_descricao', ''),
                nc_tipo=request.POST.get('nc_tipo', 'menor'),
                analise_causas=request.POST.get('analise_causas', ''),
                causa_raiz=request.POST.get('causa_raiz', ''),
                acao_imediata=request.POST.get('acao_imediata', ''),
                acao_corretiva=request.POST.get('acao_corretiva_rnc', ''),
                plano_verificacao=request.POST.get('plano_verificacao', ''),
            )
        elif tipo == 'gestao_mudanca':
            SolucaoGestaoDeMudanca.objects.create(
                solucao=solucao,
                mudanca_descricao=request.POST.get('mudanca_descricao', ''),
                motivacao=request.POST.get('motivacao', ''),
                impacto_processos=request.POST.get('impacto_processos', ''),
                plano_implementacao=request.POST.get('plano_implementacao', ''),
                data_implementacao=request.POST.get('data_implementacao'),
            )
        elif tipo == 'revisao_gerencial':
            RevisaoGerencial.objects.create(
                solucao=solucao,
                revisao_descricao=request.POST.get('revisao_descricao', ''),
                escopo=request.POST.get('escopo', ''),
                achados_principais=request.POST.get('achados_principais', ''),
                oportunidades_melhoria=request.POST.get('oportunidades_melhoria', ''),
                recomendacoes=request.POST.get('recomendacoes', ''),
                prioridade_implementacao=request.POST.get('prioridade_implementacao', 'media'),
                plano_acao=request.POST.get('plano_acao', ''),
                data_alvo_implementacao=request.POST.get('data_alvo_implementacao'),
            )
        
        return redirect('acoes:detalhe_solucao', solucao_id=solucao.id)
    
    context = {
        'acao': acao,
    }
    
    return render(request, 'acoes/criar_solucao.html', context)


@login_required
def editar_solucao(request, solucao_id):
    """Edita uma solução existente"""
    solucao = get_object_or_404(Solucao, id=solucao_id)
    
    # Carrega a solução específica do tipo
    if solucao.tipo == 'plano_acao':
        detalhes = solucao.plano_acao
    elif solucao.tipo == 'a3':
        detalhes = solucao.a3
    elif solucao.tipo == '8d':
        detalhes = solucao.oito_d
    elif solucao.tipo == 'rnc':
        detalhes = solucao.rnc
    elif solucao.tipo == 'gestao_mudanca':
        detalhes = solucao.gestao_mudanca
    elif solucao.tipo == 'revisao_gerencial':
        detalhes = solucao.revisao_gerencial
    else:
        detalhes = None
    
    if request.method == 'POST':
        # Atualizar solução base
        solucao.titulo = request.POST.get('titulo', solucao.titulo)
        solucao.descricao = request.POST.get('descricao', solucao.descricao)
        solucao.status = request.POST.get('status', solucao.status)
        if request.POST.get('responsavel'):
            solucao.responsavel_id = request.POST.get('responsavel')
        solucao.save()
        
        # Atualizar solução específica do tipo
        if detalhes:
            # Implementar atualização específica por tipo
            detalhes.save()
        
        return redirect('acoes:detalhe_solucao', solucao_id=solucao.id)
    
    context = {
        'solucao': solucao,
        'detalhes': detalhes,
    }
    
    return render(request, 'acoes/editar_solucao.html', context)
