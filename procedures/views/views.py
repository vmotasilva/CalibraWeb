# -*- coding: utf-8 -*-
"""
Views para o módulo Procedures
Consolida training + procurements:
"""

import io
import os
import logging
from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
import pandas as pd

logger = logging.getLogger(__name__)



@login_required
def treinamentos_historico_view(request):
    """Exibe todos os registros de treinamento de um colaborador para um procedimento."""
    colaborador_id = request.GET.get('colaborador')
    procedimento_id = request.GET.get('procedimento')
    colaborador = get_object_or_404(Colaborador, id=colaborador_id)
    procedimento = get_object_or_404(Procedimento, id=procedimento_id)
    historico = RegistroTreinamento.objects.filter(colaborador_id=colaborador_id, procedimento_id=procedimento_id).order_by('-data_treinamento')
    return render(request, "procedures/treinamento_historico.html", {
        "colaborador": colaborador,
        "procedimento": procedimento,
        "historico": historico,
    })
from procedures.models import (
    Procedimento, RegistroTreinamento, PacoteTreinamento,
    MatrizProcedimento, SubAreaProcedimento,
    ResponsavelTreinamentoMatriz,
    Fornecedor, AvaliacaoFornecedor, ProcessoCotacao, Orcamento
)
from rh.models import Colaborador

# Forms
from procedures.forms import (
    MatrizProcedimentoForm, SubAreaProcedimentoForm,
    ImportacaoMatrizSubAreaForm, MatrizResponsabilidadeTreinamentoForm,
    ProcedimentoForm, RegistroTreinamentoForm, PacoteTreinamentoForm,
    FornecedorForm, AvaliacaoFornecedorForm, ProcessoCotacaoForm, OrcamentoForm
)

# Helpers
from qms.views_helpers import export_to_excel_response, can_manage_procedimentos
from shared.permissions import has_view_access


# ==============================================================================
# PROCEDIMENTOS
# ==============================================================================

@login_required
def procedimentos_list_view(request):
    """Lista de Procedimentos com filtros avançados."""
    termo = (request.GET.get('q') or '').strip().upper()
    classificacao = (request.GET.get('classificacao') or '').strip()
    matriz = (request.GET.get('matriz') or '').strip()
    sub_area = (request.GET.get('sub_area') or '').strip()
    criticidade = (request.GET.get('criticidade') or '').strip()
    rev = (request.GET.get('rev') or '').strip()

    qs = Procedimento.objects.all()
    if termo:
        qs = qs.filter(Q(codigo__icontains=termo) | Q(nome__icontains=termo))
    if classificacao:
        qs = qs.filter(classificacao__iexact=classificacao)
    if matriz:
        qs = qs.filter(matriz__iexact=matriz)
    if sub_area:
        qs = qs.filter(sub_area__iexact=sub_area)
    if criticidade:
        qs = qs.filter(criticidade__iexact=criticidade)
    if rev:
        qs = qs.filter(numero_revisao__iexact=rev)

    page_number = request.GET.get('page', '1')
    paginator = Paginator(qs.order_by('codigo'), 50)
    page_obj = paginator.get_page(page_number)
    procedimentos = page_obj.object_list

    # Filtros dinâmicos vindos das tabelas normalizadas
    all_procedimentos = Procedimento.objects.all()
    classificacoes = sorted(set(
        p.classificacao for p in all_procedimentos 
        if p.classificacao
    ))
    matrizes = list(
        MatrizProcedimento.objects.filter(ativo=True)
        .order_by('nome')
        .values_list('nome', flat=True)
    )
    sub_areas = list(
        SubAreaProcedimento.objects.filter(ativo=True)
        .order_by('nome')
        .values_list('nome', flat=True)
    )
    criticidades = [
        ('CRITICO', 'Crítico'),
        ('NAO_CRITICO', 'Não Crítico'),
    ]

    ctx = {
        'procedimentos': procedimentos,
        'termo': termo,
        'classificacao': classificacao,
        'page_obj': page_obj,
        'paginator': paginator,
        'rev': rev,
        'matriz': matriz,
        'sub_area': sub_area,
        'criticidade': criticidade,
        'classificacoes': classificacoes,
        'matrizes': matrizes,
        'sub_areas': sub_areas,
        'criticidades': criticidades,
        'querystring_base': '&'.join([p for p in [
            f"q={termo}" if termo else '',
            f"classificacao={classificacao}" if classificacao else '',
            f"matriz={matriz}" if matriz else '',
            f"sub_area={sub_area}" if sub_area else '',
            f"criticidade={criticidade}" if criticidade else '',
            f"rev={rev}" if rev else '',
        ] if p])
    }
    return render(request, 'procedures/procedimento_lista.html', ctx)


@login_required
def export_procedimentos_excel_view(request):
    """Exporta procedimentos para Excel respeitando filtros (mesma estrutura do template de importação)."""
    termo = (request.GET.get('q') or '').strip()
    classificacao = (request.GET.get('classificacao') or '').strip()
    matriz = (request.GET.get('matriz') or '').strip()
    sub_area = (request.GET.get('sub_area') or '').strip()
    criticidade = (request.GET.get('criticidade') or '').strip()
    rev = (request.GET.get('rev') or '').strip()
    
    qs = Procedimento.objects.all()
    if termo:
        qs = qs.filter(Q(codigo__icontains=termo) | Q(nome__icontains=termo))
    if classificacao:
        qs = qs.filter(classificacao__iexact=classificacao)
    if matriz:
        qs = qs.filter(matriz__iexact=matriz)
    if sub_area:
        qs = qs.filter(sub_area__iexact=sub_area)
    if criticidade:
        qs = qs.filter(criticidade__iexact=criticidade)
    if rev:
        qs = qs.filter(numero_revisao__iexact=rev)
    
    # Estrutura idêntica ao template de importação
    rows = []
    for p in qs.order_by('codigo'):
        rows.append({
            'codigo': p.codigo or '',
            'nome': p.nome or '',
            'descricao': p.descricao or '',
            'pasta': p.pasta or '',
            'classificacao': p.classificacao or '',
            'autor': p.autor or '',
            'numero_revisao': p.numero_revisao or '',
            'ultima_revisao': p.ultima_revisao.strftime('%Y-%m-%d') if p.ultima_revisao else '',
            'data_aprovacao': p.data_aprovacao.strftime('%Y-%m-%d') if p.data_aprovacao else '',
            'proxima_revisao': p.proxima_revisao.strftime('%Y-%m-%d') if p.proxima_revisao else '',
            'data_validade': p.data_validade.strftime('%Y-%m-%d') if p.data_validade else '',
            'documentos_controlados': p.documentos_controlados or '',
            'matriz': p.matriz or '',
            'sub_area': p.sub_area or '',
            'criticidade': p.criticidade or '',
        })
    
    return export_to_excel_response(rows, "procedimentos_export.xlsx")


@login_required
def download_template_procedimentos_view(request):
    """Download do template de importação de procedimentos."""
    # Dados de exemplo
    rows = [
        {
            'codigo': 'POP.001',
            'nome': 'Procedimento Operacional Padrão 1',
            'descricao': 'Descrição do procedimento',
            'pasta': 'QUALIDADE',
            'classificacao': 'POP',
            'autor': 'Nome do Autor',
            'numero_revisao': '01',
            'ultima_revisao': '2025-12-24',
            'data_aprovacao': '2025-12-24',
            'proxima_revisao': '2026-12-24',
            'data_validade': '2026-12-24',
            'documentos_controlados': 'Sim',
            'matriz': 'Matriz Principal',
            'sub_area': 'Área de Processos',
            'criticidade': 'CRITICO',
        },
        {
            'codigo': 'POP.002',
            'nome': 'Procedimento Operacional Padrão 2',
            'descricao': 'Outro procedimento de exemplo',
            'pasta': 'PRODUÇÃO',
            'classificacao': 'IT',
            'autor': 'Outro Autor',
            'numero_revisao': '02',
            'ultima_revisao': '2025-12-24',
            'data_aprovacao': '2025-12-24',
            'proxima_revisao': '2026-12-24',
            'data_validade': '2026-12-24',
            'documentos_controlados': 'Não',
            'matriz': 'Matriz Principal',
            'sub_area': 'Área de Produção',
            'criticidade': 'NAO_CRITICO',
        },
    ]
    
    return export_to_excel_response(rows, "template_procedimentos.xlsx")


@login_required
def importar_procedimentos_view(request):
    """Importação em massa de procedimentos via arquivo Excel/CSV."""
    if not can_manage_procedimentos(request.user):
        messages.error(request, 'Sem permissão para importar procedimentos.')
        return redirect('procedimentos_list')
    
    from procedures.forms import ImportacaoProcedimentosForm
    from procedures.services.importacao_procedimentos import ImportacaoProcedimentosService
    from django.utils.safestring import mark_safe
    
    relatorio_html = None
    
    if request.method == 'POST' and request.FILES.get('arquivo_excel'):
        form = ImportacaoProcedimentosForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                arquivo = request.FILES['arquivo_excel']
                servico = ImportacaoProcedimentosService(arquivo)
                
                # Processa arquivo (modo upsert por padrão)
                resultados = servico.processar(modo='upsert')
                
                # Gera relatório
                relatorio_html = mark_safe(servico.gerar_relatorio_html())
                
                # Mensagem de sucesso
                if resultados['erros'] == 0:
                    messages.success(request, 
                        f"✅ Importação concluída com sucesso! "
                        f"{resultados['criados']} criados, {resultados['atualizados']} atualizados.")
                else:
                    messages.warning(request, 
                        f"⚠️ Importação com algumas inconsistências: "
                        f"{resultados['criados']} criados, {resultados['atualizados']} atualizados, "
                        f"{resultados['erros']} erros. Verifique os detalhes abaixo.")
                
                logger.info(f"Importação de procedimentos realizada por {request.user}: "
                           f"Criados: {resultados['criados']}, Atualizados: {resultados['atualizados']}, Erros: {resultados['erros']}")
                
            except Exception as e:
                messages.error(request, f"❌ Erro ao processar arquivo: {str(e)}")
                logger.error(f"Erro ao importar procedimentos: {e}", exc_info=True)
    else:
        form = ImportacaoProcedimentosForm()
    
    return render(request, 'procedures/procedimentos_importar.html', {
        'form': form,
        'relatorio_html': relatorio_html,
    })


@login_required
def novo_procedimento_view(request):
    """Cria novo procedimento."""
    if not can_manage_procedimentos(request.user):
        messages.error(request, 'Sem permissão para criar procedimentos.')
        return redirect('procedimentos_list')
    
    if request.method == 'POST':
        form = ProcedimentoForm(request.POST, request.FILES)
        if form.is_valid():
            proc = form.save()
            messages.success(request, f"Procedimento {proc.codigo} criado com sucesso!")
            return redirect('procedimentos_list')
    else:
        form = ProcedimentoForm()
    
    return render(request, 'shared/form_generico.html', {
        'form': form,
        'titulo': 'Novo Procedimento'
    })


@login_required
def editar_procedimento_view(request, procedimento_id):
    """Edita um procedimento existente."""
    proc = get_object_or_404(Procedimento, id=procedimento_id)
    
    if not can_manage_procedimentos(request.user):
        messages.error(request, 'Sem permissão para editar procedimentos.')
        return redirect('procedures:detalhe_procedimento', procedimento_id=proc.id)
    
    if request.method == 'POST':
        form = ProcedimentoForm(request.POST, request.FILES, instance=proc)
        if form.is_valid():
            form.save()
            messages.success(request, "Procedimento atualizado com sucesso!")
            return redirect('procedures:detalhe_procedimento', procedimento_id=proc.id)
    else:
        form = ProcedimentoForm(instance=proc)
    
    return render(request, 'procedures/procedimento_form.html', {
        'form': form,
        'proc': proc,
        'titulo': f'Editar Procedimento: {proc.codigo}'
    })


@login_required
def detalhe_procedimento_view(request, procedimento_id):
    """Visualiza detalhes de um procedimento."""
    proc = get_object_or_404(Procedimento, id=procedimento_id)
    return render(request, 'procedures/procedimento_detalhe.html', {
        'proc': proc
    })


@login_required
def procedimento_matrizes_list_view(request):
    """Lista e cadastra matrizes de procedimentos."""
    if not has_view_access(request.user, 'procedures:procedimento_matrizes_list'):
        messages.error(request, 'Sem permissão para acessar matrizes de procedimentos.')
        return redirect('procedures:procedimentos_list')

    termo = (request.GET.get('q') or '').strip()
    qs = MatrizProcedimento.objects.all().order_by('nome')
    if termo:
        qs = qs.filter(nome__icontains=termo)

    if request.method == 'POST':
        form = MatrizProcedimentoForm(request.POST)
        if form.is_valid():
            matriz = form.save()
            messages.success(request, f"Matriz '{matriz.nome}' cadastrada com sucesso.")
            return redirect('procedures:procedimento_matriz_detalhe', matriz_id=matriz.id)
    else:
        form = MatrizProcedimentoForm()

    return render(request, 'procedures/procedimento_matriz_lista.html', {
        'form': form,
        'matrizes': qs,
        'termo': termo,
    })


@login_required
def importar_matrizes_subareas_view(request):
    """Importa matrizes e sub-áreas em massa via Excel/CSV."""
    if not has_view_access(request.user, 'procedures:importar_matrizes_subareas'):
        messages.error(request, 'Sem permissão para importar matrizes e sub-áreas.')
        return redirect('procedures:procedimento_matrizes_list')

    resultado = None

    if request.method == 'POST':
        form = ImportacaoMatrizSubAreaForm(request.POST, request.FILES)
        if form.is_valid():
            arquivo = form.cleaned_data['arquivo']
            nome_arquivo = (arquivo.name or '').lower()

            try:
                if nome_arquivo.endswith('.csv'):
                    df = pd.read_csv(arquivo)
                else:
                    df = pd.read_excel(arquivo)
            except Exception as exc:
                messages.error(request, f'Erro ao ler arquivo: {exc}')
                return render(request, 'procedures/procedimento_matriz_importar.html', {'form': form, 'resultado': resultado})

            # Normaliza nomes das colunas para facilitar planilhas de fontes diferentes
            colunas_norm = {str(col).strip().lower(): col for col in df.columns}
            col_matriz = colunas_norm.get('matriz')
            col_sub_area = colunas_norm.get('sub_area') or colunas_norm.get('sub-área') or colunas_norm.get('subarea')
            col_ativo_matriz = colunas_norm.get('ativo_matriz')
            col_ativo_sub_area = colunas_norm.get('ativo_sub_area')

            if not col_matriz:
                messages.error(request, 'A coluna obrigatória "matriz" não foi encontrada no arquivo.')
                return render(request, 'procedures/procedimento_matriz_importar.html', {'form': form, 'resultado': resultado})

            criadas_matrizes = 0
            atualizadas_matrizes = 0
            criadas_subareas = 0
            atualizadas_subareas = 0
            ignoradas = 0
            erros = []

            def to_bool(value, default=True):
                if pd.isna(value):
                    return default
                texto = str(value).strip().lower()
                if texto in ('1', 'true', 'sim', 's', 'yes', 'y'):
                    return True
                if texto in ('0', 'false', 'nao', 'não', 'n', 'no'):
                    return False
                return default

            for idx, row in df.iterrows():
                linha = idx + 2
                try:
                    nome_matriz = '' if pd.isna(row[col_matriz]) else str(row[col_matriz]).strip()
                    if not nome_matriz:
                        ignoradas += 1
                        continue

                    ativo_matriz = to_bool(row[col_ativo_matriz], True) if col_ativo_matriz else True
                    matriz_obj, matriz_criada = MatrizProcedimento.objects.get_or_create(
                        nome=nome_matriz,
                        defaults={'ativo': ativo_matriz},
                    )

                    if matriz_criada:
                        criadas_matrizes += 1
                    else:
                        if col_ativo_matriz and matriz_obj.ativo != ativo_matriz:
                            matriz_obj.ativo = ativo_matriz
                            matriz_obj.save(update_fields=['ativo', 'atualizado_em'])
                            atualizadas_matrizes += 1

                    if col_sub_area:
                        nome_sub_area = '' if pd.isna(row[col_sub_area]) else str(row[col_sub_area]).strip()
                        if nome_sub_area:
                            ativo_sub_area = to_bool(row[col_ativo_sub_area], True) if col_ativo_sub_area else True
                            sub_area_obj, sub_area_criada = SubAreaProcedimento.objects.get_or_create(
                                matriz=matriz_obj,
                                nome=nome_sub_area,
                                defaults={'ativo': ativo_sub_area},
                            )

                            if sub_area_criada:
                                criadas_subareas += 1
                            else:
                                if col_ativo_sub_area and sub_area_obj.ativo != ativo_sub_area:
                                    sub_area_obj.ativo = ativo_sub_area
                                    sub_area_obj.save(update_fields=['ativo', 'atualizado_em'])
                                    atualizadas_subareas += 1
                except Exception as exc:
                    erros.append(f'Linha {linha}: {exc}')

            resultado = {
                'criadas_matrizes': criadas_matrizes,
                'atualizadas_matrizes': atualizadas_matrizes,
                'criadas_subareas': criadas_subareas,
                'atualizadas_subareas': atualizadas_subareas,
                'ignoradas': ignoradas,
                'erros': erros,
            }

            if erros:
                messages.warning(request, 'Importação concluída com inconsistências. Verifique o relatório abaixo.')
            else:
                messages.success(request, 'Importação de matrizes/sub-áreas concluída com sucesso.')
    else:
        form = ImportacaoMatrizSubAreaForm()

    return render(request, 'procedures/procedimento_matriz_importar.html', {
        'form': form,
        'resultado': resultado,
    })


@login_required
def download_template_matrizes_subareas_view(request):
    """Baixa template de importação de matrizes e sub-áreas."""
    if not has_view_access(request.user, 'procedures:download_template_matrizes_subareas'):
        messages.error(request, 'Sem permissão para baixar template de importação.')
        return redirect('procedures:procedimento_matrizes_list')

    rows = [
        {'matriz': 'SURFAÇAGEM', 'sub_area': 'Blocagem', 'ativo_matriz': 1, 'ativo_sub_area': 1},
        {'matriz': 'SURFAÇAGEM', 'sub_area': 'Recebimento', 'ativo_matriz': 1, 'ativo_sub_area': 1},
        {'matriz': 'MONTAGEM', 'sub_area': 'Linha A', 'ativo_matriz': 1, 'ativo_sub_area': 1},
    ]
    return export_to_excel_response(rows, 'template_importacao_matrizes_subareas.xlsx')


@login_required
def procedimento_matriz_detalhe_view(request, matriz_id):
    """Detalha uma matriz e permite cadastrar/associar sub-áreas."""
    if not has_view_access(request.user, 'procedures:procedimento_matriz_detalhe'):
        messages.error(request, 'Sem permissão para gerenciar sub-áreas da matriz.')
        return redirect('procedures:procedimento_matrizes_list')

    matriz = get_object_or_404(MatrizProcedimento, id=matriz_id)

    if request.method == 'POST':
        acao = (request.POST.get('acao') or '').strip()

        if acao == 'editar_matriz':
            matriz_form = MatrizProcedimentoForm(request.POST, instance=matriz)
            sub_area_form = SubAreaProcedimentoForm()
            if matriz_form.is_valid():
                matriz_form.save()
                messages.success(request, 'Matriz atualizada com sucesso.')
                return redirect('procedures:procedimento_matriz_detalhe', matriz_id=matriz.id)
        elif acao == 'deletar_sub_area':
            sub_area_id = request.POST.get('sub_area_id')
            sub_area = get_object_or_404(SubAreaProcedimento, id=sub_area_id, matriz=matriz)
            sub_area.delete()
            messages.success(request, 'Sub-área removida com sucesso.')
            return redirect('procedures:procedimento_matriz_detalhe', matriz_id=matriz.id)
        else:
            matriz_form = MatrizProcedimentoForm(instance=matriz)
            sub_area_form = SubAreaProcedimentoForm(request.POST)
            if sub_area_form.is_valid():
                sub_area = sub_area_form.save(commit=False)
                sub_area.matriz = matriz
                sub_area.save()
                messages.success(request, f"Sub-área '{sub_area.nome}' associada com sucesso.")
                return redirect('procedures:procedimento_matriz_detalhe', matriz_id=matriz.id)
    else:
        matriz_form = MatrizProcedimentoForm(instance=matriz)
        sub_area_form = SubAreaProcedimentoForm()

    sub_areas = matriz.sub_areas.all().order_by('nome')

    return render(request, 'procedures/procedimento_matriz_detalhe.html', {
        'matriz': matriz,
        'matriz_form': matriz_form,
        'sub_area_form': sub_area_form,
        'sub_areas': sub_areas,
    })


@login_required
def procedimento_responsabilidades_treinamento_view(request):
    """Matriz de responsaveis de treinamento por matriz e turno."""
    from procedures.models import ColaboradorPerfil

    if not has_view_access(request.user, 'procedures:procedimento_responsabilidades_treinamento'):
        messages.error(request, 'Sem permissao para gerenciar responsaveis de treinamento por matriz.')
        return redirect('procedures:procedimento_matrizes_list')

    nomes_matrizes_com_procedimentos = list(
        Procedimento.objects.exclude(matriz__isnull=True)
        .exclude(matriz__exact='')
        .values_list('matriz', flat=True)
        .distinct()
    )
    total_procedimentos_por_matriz = dict(
        Procedimento.objects.exclude(matriz__isnull=True)
        .exclude(matriz__exact='')
        .values('matriz')
        .annotate(total=Count('id'))
        .values_list('matriz', 'total')
    )

    matrizes = list(
        MatrizProcedimento.objects.filter(
            Q(nome__in=nomes_matrizes_com_procedimentos)
            | Q(responsaveis_treinamento__isnull=False)
        )
        .distinct()
        .order_by('nome')
    )
    if not matrizes:
        matrizes = list(MatrizProcedimento.objects.order_by('nome'))

    responsabilidades = {
        (responsabilidade.matriz_id, responsabilidade.turno): responsabilidade
        for responsabilidade in ResponsavelTreinamentoMatriz.objects.select_related('matriz', 'colaborador').filter(
            matriz__in=matrizes
        )
    }

    if request.method == 'POST':
        form = MatrizResponsabilidadeTreinamentoForm(
            request.POST,
            matrizes=matrizes,
            responsabilidades=responsabilidades,
        )
        if form.is_valid():
            resultado = form.save()
            total_alteracoes = resultado['atualizadas'] + resultado['removidas']
            if total_alteracoes:
                messages.success(
                    request,
                    f"Matriz de responsabilidade atualizada com sucesso. {resultado['atualizadas']} atribuicoes salvas e {resultado['removidas']} removidas.",
                )
            else:
                messages.info(request, 'Nenhuma alteracao foi identificada na matriz de responsabilidade.')
            return redirect('procedures:procedimento_responsabilidades_treinamento')
    else:
        form = MatrizResponsabilidadeTreinamentoForm(
            matrizes=matrizes,
            responsabilidades=responsabilidades,
        )

    colaboradores_qualificados = {}
    colaboradores_por_chave = {}
    nomes_matrizes = {matriz.nome for matriz in matrizes}
    colaboradores_perfil = ColaboradorPerfil.objects.filter(
        ativo=True,
        colaborador__isnull=False,
    ).select_related('colaborador')

    for colaborador_perfil in colaboradores_perfil:
        colaborador = colaborador_perfil.colaborador
        if not colaborador or not colaborador.turno:
            continue

        matrizes_do_perfil = set(
            colaborador_perfil.get_procedimentos_necessarios()
            .exclude(matriz__isnull=True)
            .exclude(matriz__exact='')
            .filter(matriz__in=nomes_matrizes)
            .values_list('matriz', flat=True)
        )
        for matriz_nome in matrizes_do_perfil:
            chave = (matriz_nome, colaborador.turno)
            colaboradores_por_chave.setdefault(chave, set()).add(colaborador.id)

    for chave, colaboradores_ids in colaboradores_por_chave.items():
        colaboradores_qualificados[chave] = len(colaboradores_ids)

    linhas_matriz = form.build_rows(colaboradores_qualificados=colaboradores_qualificados)
    for linha in linhas_matriz:
        linha['total_procedimentos'] = total_procedimentos_por_matriz.get(linha['matriz'].nome, 0)

    return render(request, 'procedures/procedimento_matriz_responsabilidades.html', {
        'form': form,
        'linhas_matriz': linhas_matriz,
        'turnos': form.turnos,
        'total_responsabilidades': len(responsabilidades),
        'total_matrizes': len(matrizes),
    })


# ==============================================================================
# TREINAMENTOS
# ==============================================================================

@login_required
def treinamentos_list_view(request):
    """Lista de treinamentos realizados com filtros.
    
    Mostra apenas o registro mais recente para cada combinação colaborador+procedimento.
    O histórico completo fica disponível na tela de detalhes.
    """
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    from django.db.models import Max, OuterRef, Subquery, Exists
    from datetime import date
    
    # Obs: por padrão esta tela mostra apenas o registro mais recente por colaborador+procedimento.
    # Quando vier do dashboard (ocorridos=1 e/ou mes=YYYY-MM), precisamos listar TODOS os registros
    # ocorridos no período para bater com o gráfico.
    # Alinhar o escopo base com o Dashboard de Treinamentos:
    # - somente colaboradores ativos (não afastados / não em férias)
    # - apenas registros com colaborador+procedimento vinculados
    qs = RegistroTreinamento.objects.select_related('colaborador', 'procedimento').filter(
        colaborador__isnull=False,
        procedimento__isnull=False,
        colaborador__is_active=True,
        colaborador__afastado=False,
        colaborador__em_ferias=False,
    )
    from organization.models import Setor

    colaboradores = Colaborador.objects.filter(
        is_active=True,
        afastado=False,
        em_ferias=False,
    ).order_by('nome_completo')
    procedimentos = Procedimento.objects.order_by('codigo')
    lideres = Colaborador.objects.filter(
        id__in=RegistroTreinamento.objects.values_list('colaborador__lider_id', flat=True).distinct()
    ).order_by('nome_completo')

    setores = Setor.objects.order_by('nome')
    matrizes = list(
        Procedimento.objects.exclude(matriz__isnull=True)
        .exclude(matriz__exact='')
        .values_list('matriz', flat=True)
        .distinct()
        .order_by('matriz')
    )
    sub_areas = list(
        Procedimento.objects.exclude(sub_area__isnull=True)
        .exclude(sub_area__exact='')
        .values_list('sub_area', flat=True)
        .distinct()
        .order_by('sub_area')
    )
    criticidade_choices = list(Procedimento._meta.get_field('criticidade').choices)
    
    from core.models import TURNOS_CHOICES

    def _getlist_or_single(param_name: str):
        values = [v for v in request.GET.getlist(param_name) if str(v).strip()]
        if values:
            return values
        single = (request.GET.get(param_name) or '').strip()
        return [single] if single else []

    status = request.GET.get('status', '')
    # Compatibilidade: NAO_INICIADO passa a ser considerado PENDENTE
    if status == 'NAO_INICIADO':
        status = 'PENDENTE'
    colaborador_id = request.GET.get('colaborador', '')
    procedimento_id = request.GET.get('procedimento', '')
    busca = request.GET.get('q', '')
    ativo_raw = request.GET.get('ativo', None)
    ativo = (ativo_raw or '').strip()
    # Padrão: mesma regra do dashboard (apenas registros ativos)
    if ativo_raw is None:
        ativo = '1'
    perfil_assoc_raw = request.GET.get('perfil_assoc', None)
    perfil_assoc = (perfil_assoc_raw or '').strip()
    # Padrão: marcar/aplicar "Somente associados a perfil" quando o parâmetro não vier.
    # Observação: quando o usuário desmarca, o form envia perfil_assoc=0.
    if perfil_assoc_raw is None:
        perfil_assoc = '1'

    lider_ids = _getlist_or_single('lider')
    setor_ids = _getlist_or_single('setor')
    turnos = _getlist_or_single('turno')
    criticidades = _getlist_or_single('criticidade')
    matrizes_filtro = _getlist_or_single('matriz')
    sub_areas_filtro = _getlist_or_single('sub_area')

    # Para template (primeiro valor ou vazio)
    lider_id = lider_ids[0] if lider_ids else ''
    setor_id = setor_ids[0] if setor_ids else ''
    turno = turnos[0] if turnos else ''
    criticidade = criticidades[0] if criticidades else ''
    matriz = matrizes_filtro[0] if matrizes_filtro else ''
    sub_area = sub_areas_filtro[0] if sub_areas_filtro else ''

    ocorridos = (request.GET.get('ocorridos') or '').strip()
    mes = (request.GET.get('mes') or '').strip()

    modo_ocorridos = (ocorridos in {'1', 'true', 'True', 'sim', 'SIM'}) or bool(mes)

    # Aplicar filtro de ativo no QuerySet (alinha com dashboard)
    if ativo:
        qs = qs.filter(ativo=ativo == '1')

    # Se solicitado, listar SOMENTE procedimentos associados a perfil.
    # Quando há colaborador definido, a fonte de verdade passa a ser a lista de procedimentos do(s) perfil(is)
    # (incluindo aqueles ainda sem RegistroTreinamento), para bater com a Matriz exibida no RH.
    if perfil_assoc in {'1', 'true', 'True', 'sim', 'SIM'} and colaborador_id:
        from procedures.models import ColaboradorPerfil

        try:
            colaborador_obj = Colaborador.objects.get(id=colaborador_id)
        except Exception:
            colaborador_obj = None

        # Alinhar com dashboard: ignorar colaborador inativo/afastado/em férias
        if colaborador_obj:
            if not getattr(colaborador_obj, 'is_active', False):
                colaborador_obj = None
            if getattr(colaborador_obj, 'afastado', False):
                colaborador_obj = None
            if getattr(colaborador_obj, 'em_ferias', False):
                colaborador_obj = None

        procedimentos_ids = set()
        if colaborador_obj:
            for cp in ColaboradorPerfil.objects.filter(colaborador_id=colaborador_id, ativo=True).select_related('perfil'):
                procedimentos_ids.update(cp.get_procedimentos_necessarios().values_list('id', flat=True))

        if not procedimentos_ids:
            qs = []
        else:
            # Aplicar filtros de procedimento diretamente nos procedimentos do perfil
            procs_qs = Procedimento.objects.filter(id__in=procedimentos_ids)
            if procedimento_id:
                procs_qs = procs_qs.filter(id=procedimento_id)
            if criticidades:
                procs_qs = procs_qs.filter(criticidade__in=criticidades)
            if matrizes_filtro:
                procs_qs = procs_qs.filter(matriz__in=matrizes_filtro)
            if sub_areas_filtro:
                procs_qs = procs_qs.filter(sub_area__in=sub_areas_filtro)
            if busca:
                procs_qs = procs_qs.filter(Q(codigo__icontains=busca) | Q(nome__icontains=busca))

            # Buscar "último" registro por procedimento seguindo a mesma regra do RH:
            # 1) Preferir o mais recente com data válida (não nula e não 1970-01-01)
            # 2) Se não houver, cair para o mais recente sem data
            EPOCH_DATE = date(1970, 1, 1)
            treinos_por_proc_id = {}
            treinos_qs = (
                RegistroTreinamento.objects.filter(
                    colaborador_id=colaborador_id,
                    procedimento_id__in=procs_qs.values_list('id', flat=True),
                    procedimento__isnull=False,
                )
                .select_related('colaborador', 'procedimento')
                .order_by('-data_treinamento', '-id')
            )

            for t in treinos_qs:
                proc_id = t.procedimento_id
                if proc_id in treinos_por_proc_id:
                    continue
                if not t.data_treinamento:
                    continue
                if t.data_treinamento == EPOCH_DATE:
                    continue
                treinos_por_proc_id[proc_id] = t

            for t in treinos_qs:
                proc_id = t.procedimento_id
                if proc_id in treinos_por_proc_id:
                    continue
                if t.data_treinamento:
                    continue
                treinos_por_proc_id[proc_id] = t

            itens = []
            for proc in procs_qs.order_by('codigo'):
                t = treinos_por_proc_id.get(proc.id)
                if t is None:
                    # Criar instância em memória para representar "não iniciado" (sem registro)
                    t = RegistroTreinamento(
                        colaborador=colaborador_obj,
                        procedimento=proc,
                        tipo='PROCEDIMENTO',
                        ativo=True,
                        data_treinamento=None,
                        revisao_treinada=None,
                    )
                itens.append(t)

            # Respeitar filtros de ocorridos/mes/status/ativo no nível do registro
            if ocorridos in {'1', 'true', 'True', 'sim', 'SIM'}:
                itens = [t for t in itens if getattr(t, 'data_treinamento', None)]
            if mes:
                try:
                    ano_str, mes_str = mes.split('-', 1)
                    ano = int(ano_str)
                    mes_num = int(mes_str)
                    data_inicio = date(ano, mes_num, 1)
                    if mes_num == 12:
                        data_fim = date(ano + 1, 1, 1)
                    else:
                        data_fim = date(ano, mes_num + 1, 1)
                    itens = [t for t in itens if t.data_treinamento and data_inicio <= t.data_treinamento < data_fim]
                except Exception:
                    pass
            if ativo:
                ativo_bool = (ativo == '1')
                itens = [t for t in itens if bool(getattr(t, 'ativo', True)) == ativo_bool]
            if status:
                if status == 'PENDENTE':
                    itens = [t for t in itens if t.status_treinamento in {'PENDENTE', 'NAO_INICIADO'}]
                else:
                    itens = [t for t in itens if t.status_treinamento == status]

            # Filtros de líder/setor/turno (quando presentes) precisam ser respeitados.
            # Como estamos no modo de colaborador único, basta validar o colaborador.
            try:
                if lider_ids and str(getattr(colaborador_obj, 'lider_id', '') or '') not in set(map(str, lider_ids)):
                    itens = []
                if setor_ids and str(getattr(colaborador_obj, 'setor_id', '') or '') not in set(map(str, setor_ids)):
                    itens = []
                if turnos and str(getattr(colaborador_obj, 'turno', '') or '') not in set(map(str, turnos)):
                    itens = []
            except Exception:
                pass

            # Ordenação padrão (data desc; sem data vai pro fim)
            itens.sort(key=lambda x: (x.data_treinamento is not None, x.data_treinamento or date.min), reverse=True)
            qs = itens

    qs_is_list = isinstance(qs, list)

    # Filtro de status - nota: status_treinamento é uma property
    # ⚠️ NOTA: Não é possível filtrar por property diretamente no QuerySet
    # Aplicar filtros no QuerySet primeiro
    if not qs_is_list:
        if colaborador_id:
            qs = qs.filter(colaborador_id=colaborador_id)
        if lider_ids:
            qs = qs.filter(colaborador__lider_id__in=lider_ids)
        if setor_ids:
            qs = qs.filter(colaborador__setor_id__in=setor_ids)
        if turnos:
            qs = qs.filter(colaborador__turno__in=turnos)
        if procedimento_id:
            qs = qs.filter(procedimento_id=procedimento_id)
        if criticidades:
            qs = qs.filter(procedimento__criticidade__in=criticidades)
        if matrizes_filtro:
            qs = qs.filter(procedimento__matriz__in=matrizes_filtro)
        if sub_areas_filtro:
            qs = qs.filter(procedimento__sub_area__in=sub_areas_filtro)
        if busca:
            qs = qs.filter(
                Q(colaborador__nome_completo__icontains=busca) |
                Q(procedimento__codigo__icontains=busca) |
                Q(procedimento__nome__icontains=busca)
            )

    # Treinamentos que ocorreram: têm data_treinamento
    if not qs_is_list and ocorridos in {'1', 'true', 'True', 'sim', 'SIM'}:
        qs = qs.filter(data_treinamento__isnull=False)

    # Filtrar por mês (YYYY-MM) considerando data_treinamento
    if (not qs_is_list) and mes:
        try:
            ano_str, mes_str = mes.split('-', 1)
            ano = int(ano_str)
            mes_num = int(mes_str)
            data_inicio = date(ano, mes_num, 1)
            if mes_num == 12:
                data_fim = date(ano + 1, 1, 1)
            else:
                data_fim = date(ano, mes_num + 1, 1)
            qs = qs.filter(data_treinamento__gte=data_inicio, data_treinamento__lt=data_fim)
        except Exception:
            pass

    # Somente treinamentos associados a algum Perfil atribuído
    if (not qs_is_list) and perfil_assoc in {'1', 'true', 'True', 'sim', 'SIM'}:
        from procedures.models import ColaboradorPerfil

        # Se filtrou um colaborador específico, aplicar regra exata (inclui seleção de subgrupos)
        if colaborador_id:
            procedimentos_ids = set()
            for cp in ColaboradorPerfil.objects.filter(colaborador_id=colaborador_id, ativo=True).select_related('perfil'):
                procedimentos_ids.update(cp.get_procedimentos_necessarios().values_list('id', flat=True))
            if procedimentos_ids:
                qs = qs.filter(procedimento_id__in=procedimentos_ids)
            else:
                qs = qs.none()
        else:
            # Sem colaborador: filtrar pelo relacionamento de perfil (sem considerar seleções JSON)
            perfil_exists_qs = ColaboradorPerfil.objects.filter(
                colaborador_id=OuterRef('colaborador_id'),
                ativo=True,
                perfil__grupos__subgrupos__procedimentos=OuterRef('procedimento_id'),
            )
            qs = qs.annotate(_associado_perfil=Exists(perfil_exists_qs)).filter(_associado_perfil=True)

    # Reduzir para o registro mais recente por colaborador+procedimento APÓS aplicar filtros,
    # para bater com o Dashboard.
    if (not qs_is_list) and (not modo_ocorridos):
        ultimos_registros_ids = qs.values('colaborador_id', 'procedimento_id').annotate(
            ultimo_id=Max('id')
        ).values_list('ultimo_id', flat=True)
        qs = qs.filter(id__in=ultimos_registros_ids)
    
    # Ordenar
    if not qs_is_list:
        qs = qs.order_by('-data_treinamento')
    
    # Se houver filtro de status (property), aplicar em memória
    if status:
        if status == 'PENDENTE':
            qs = [t for t in qs if t.status_treinamento in {'PENDENTE', 'NAO_INICIADO'}]
        else:
            qs = [t for t in qs if t.status_treinamento == status]
    
    # Contar total de registros
    total_registros = len(qs) if isinstance(qs, list) else qs.count()
    
    # Paginar resultados (20 por página)
    paginator = Paginator(qs, 20)
    page = request.GET.get('page')
    
    try:
        treinamentos = paginator.page(page)
    except PageNotAnInteger:
        treinamentos = paginator.page(1)
    except EmptyPage:
        treinamentos = paginator.page(paginator.num_pages)

    query_params = request.GET.copy()
    query_params.pop('page', None)
    if 'ativo' not in query_params and ativo == '1':
        query_params['ativo'] = '1'
    if 'perfil_assoc' not in query_params and perfil_assoc == '1':
        query_params['perfil_assoc'] = '1'
    query_string = query_params.urlencode()
    
    return render(request, "procedures/treinamento_lista.html", {
        "treinamentos": treinamentos,
        "colaboradores": colaboradores,
        "procedimentos": procedimentos,
        "lideres": lideres,
        "setores": setores,
        "turnos": [{'value': t[0], 'label': t[1]} for t in TURNOS_CHOICES],
        "criticidade_choices": criticidade_choices,
        "matrizes": matrizes,
        "sub_areas": sub_areas,
        "status": status,
        "colaborador_id": colaborador_id,
        "procedimento_id": procedimento_id,
        "lider_id": lider_id,
        "turno": turno,
        "busca": busca,
        "ativo": ativo,
        "setor_id": setor_id,
        "criticidade": criticidade,
        "matriz": matriz,
        "sub_area": sub_area,
        "ocorridos": ocorridos,
        "mes": mes,
        "perfil_assoc": perfil_assoc,
        "query_string": query_string,
        "total_registros": total_registros,
    })


@login_required
def treinamentos_exportar_excel_view(request):
    """Exporta matriz de treinamentos com filtros para Excel."""
    from procedures.utils.export_utils import PlanejamentoExcelExporter
    from django.db.models import Exists, OuterRef
    
    # Aplicar os mesmos filtros da lista (alinhado ao Dashboard):
    # - somente colaboradores ativos (não afastados / não em férias)
    # - apenas registros com colaborador+procedimento vinculados
    qs = RegistroTreinamento.objects.select_related('colaborador', 'procedimento').filter(
        colaborador__isnull=False,
        procedimento__isnull=False,
        colaborador__is_active=True,
        colaborador__afastado=False,
        colaborador__em_ferias=False,
    )
    
    def _getlist_or_single(param_name: str):
        values = [v for v in request.GET.getlist(param_name) if str(v).strip()]
        if values:
            return values
        single = (request.GET.get(param_name) or '').strip()
        return [single] if single else []

    status = request.GET.get('status', '')
    # Compatibilidade: NAO_INICIADO passa a ser considerado PENDENTE
    if status == 'NAO_INICIADO':
        status = 'PENDENTE'
    colaborador_id = request.GET.get('colaborador', '')
    procedimento_id = request.GET.get('procedimento', '')
    busca = request.GET.get('q', '')
    ativo_raw = request.GET.get('ativo', None)
    ativo = (ativo_raw or '').strip()
    if ativo_raw is None:
        ativo = '1'
    perfil_assoc_raw = request.GET.get('perfil_assoc', None)
    perfil_assoc = (perfil_assoc_raw or '').strip()
    if perfil_assoc_raw is None:
        perfil_assoc = '1'

    lider_ids = _getlist_or_single('lider')
    setor_ids = _getlist_or_single('setor')
    turnos = _getlist_or_single('turno')
    criticidades = _getlist_or_single('criticidade')
    matrizes_filtro = _getlist_or_single('matriz')
    sub_areas_filtro = _getlist_or_single('sub_area')

    ocorridos = (request.GET.get('ocorridos') or '').strip()
    mes = (request.GET.get('mes') or '').strip()

    modo_ocorridos = (ocorridos in {'1', 'true', 'True', 'sim', 'SIM'}) or bool(mes)

    if ativo:
        qs = qs.filter(ativo=ativo == '1')

    # Filtros por QuerySet (aplicar antes de filtro por status)
    if colaborador_id:
        qs = qs.filter(colaborador_id=colaborador_id)
    if lider_ids:
        qs = qs.filter(colaborador__lider_id__in=lider_ids)
    if setor_ids:
        qs = qs.filter(colaborador__setor_id__in=setor_ids)
    if turnos:
        qs = qs.filter(colaborador__turno__in=turnos)
    if procedimento_id:
        qs = qs.filter(procedimento_id=procedimento_id)
    if criticidades:
        qs = qs.filter(procedimento__criticidade__in=criticidades)
    if matrizes_filtro:
        qs = qs.filter(procedimento__matriz__in=matrizes_filtro)
    if sub_areas_filtro:
        qs = qs.filter(procedimento__sub_area__in=sub_areas_filtro)
    # "ativo" já foi aplicado antes do modo "último registro" (para evitar inconsistência)
    if busca:
        qs = qs.filter(
            Q(colaborador__nome_completo__icontains=busca) |
            Q(procedimento__codigo__icontains=busca) |
            Q(procedimento__nome__icontains=busca)
        )

    if ocorridos in {'1', 'true', 'True', 'sim', 'SIM'}:
        qs = qs.filter(data_treinamento__isnull=False)

    if mes:
        try:
            from datetime import date
            ano_str, mes_str = mes.split('-', 1)
            ano = int(ano_str)
            mes_num = int(mes_str)
            data_inicio = date(ano, mes_num, 1)
            if mes_num == 12:
                data_fim = date(ano + 1, 1, 1)
            else:
                data_fim = date(ano, mes_num + 1, 1)
            qs = qs.filter(data_treinamento__gte=data_inicio, data_treinamento__lt=data_fim)
        except Exception:
            pass

    # Modo Perfil + Colaborador: exportar todos os procedimentos do perfil (incluindo sem registro)
    if perfil_assoc in {'1', 'true', 'True', 'sim', 'SIM'} and colaborador_id:
        from procedures.models import ColaboradorPerfil
        try:
            colaborador_obj = Colaborador.objects.get(id=colaborador_id)
        except Exception:
            colaborador_obj = None

        # Alinhar com dashboard: ignorar colaborador inativo/afastado/em férias
        if colaborador_obj:
            if not getattr(colaborador_obj, 'is_active', False):
                colaborador_obj = None
            if getattr(colaborador_obj, 'afastado', False):
                colaborador_obj = None
            if getattr(colaborador_obj, 'em_ferias', False):
                colaborador_obj = None

        procedimentos_ids = set()
        if colaborador_obj:
            for cp in ColaboradorPerfil.objects.filter(colaborador_id=colaborador_id, ativo=True).select_related('perfil'):
                procedimentos_ids.update(cp.get_procedimentos_necessarios().values_list('id', flat=True))

        if not procedimentos_ids:
            qs = []
        else:
            procs_qs = Procedimento.objects.filter(id__in=procedimentos_ids)
            if procedimento_id:
                procs_qs = procs_qs.filter(id=procedimento_id)
            if criticidades:
                procs_qs = procs_qs.filter(criticidade__in=criticidades)
            if matrizes_filtro:
                procs_qs = procs_qs.filter(matriz__in=matrizes_filtro)
            if sub_areas_filtro:
                procs_qs = procs_qs.filter(sub_area__in=sub_areas_filtro)
            if busca:
                procs_qs = procs_qs.filter(Q(codigo__icontains=busca) | Q(nome__icontains=busca))

            # Mesmo critério do RH para selecionar o "último" registro por procedimento
            from datetime import date
            EPOCH_DATE = date(1970, 1, 1)
            treinos_por_proc_id = {}
            treinos_qs = (
                RegistroTreinamento.objects.filter(
                    colaborador_id=colaborador_id,
                    procedimento_id__in=procs_qs.values_list('id', flat=True),
                    procedimento__isnull=False,
                )
                .select_related('colaborador', 'procedimento')
                .order_by('-data_treinamento', '-id')
            )

            for t in treinos_qs:
                proc_id = t.procedimento_id
                if proc_id in treinos_por_proc_id:
                    continue
                if not t.data_treinamento:
                    continue
                if t.data_treinamento == EPOCH_DATE:
                    continue
                treinos_por_proc_id[proc_id] = t

            for t in treinos_qs:
                proc_id = t.procedimento_id
                if proc_id in treinos_por_proc_id:
                    continue
                if t.data_treinamento:
                    continue
                treinos_por_proc_id[proc_id] = t

            itens = []
            for proc in procs_qs.order_by('codigo'):
                t = treinos_por_proc_id.get(proc.id)
                if t is None:
                    t = RegistroTreinamento(
                        colaborador=colaborador_obj,
                        procedimento=proc,
                        tipo='PROCEDIMENTO',
                        ativo=True,
                        data_treinamento=None,
                        revisao_treinada=None,
                    )
                itens.append(t)

            if ocorridos in {'1', 'true', 'True', 'sim', 'SIM'}:
                itens = [t for t in itens if getattr(t, 'data_treinamento', None)]
            if mes:
                try:
                    ano_str, mes_str = mes.split('-', 1)
                    ano = int(ano_str)
                    mes_num = int(mes_str)
                    data_inicio = date(ano, mes_num, 1)
                    if mes_num == 12:
                        data_fim = date(ano + 1, 1, 1)
                    else:
                        data_fim = date(ano, mes_num + 1, 1)
                    itens = [t for t in itens if t.data_treinamento and data_inicio <= t.data_treinamento < data_fim]
                except Exception:
                    pass
            if ativo:
                ativo_bool = (ativo == '1')
                itens = [t for t in itens if bool(getattr(t, 'ativo', True)) == ativo_bool]
            if status:
                if status == 'PENDENTE':
                    itens = [t for t in itens if t.status_treinamento in {'PENDENTE', 'NAO_INICIADO'}]
                else:
                    itens = [t for t in itens if t.status_treinamento == status]

            itens.sort(key=lambda x: (x.data_treinamento is not None, x.data_treinamento or date.min), reverse=True)
            qs = itens

    qs_is_list = isinstance(qs, list)

    # Somente treinamentos associados a algum Perfil atribuído
    if (not qs_is_list) and perfil_assoc in {'1', 'true', 'True', 'sim', 'SIM'}:
        from procedures.models import ColaboradorPerfil

        if colaborador_id:
            procedimentos_ids = set()
            for cp in ColaboradorPerfil.objects.filter(colaborador_id=colaborador_id, ativo=True).select_related('perfil'):
                procedimentos_ids.update(cp.get_procedimentos_necessarios().values_list('id', flat=True))
            if procedimentos_ids:
                qs = qs.filter(procedimento_id__in=procedimentos_ids)
            else:
                qs = qs.none()
        else:
            perfil_exists_qs = ColaboradorPerfil.objects.filter(
                colaborador_id=OuterRef('colaborador_id'),
                ativo=True,
                perfil__grupos__subgrupos__procedimentos=OuterRef('procedimento_id'),
            )
            qs = qs.annotate(_associado_perfil=Exists(perfil_exists_qs)).filter(_associado_perfil=True)

    # Reduzir para o registro mais recente por colaborador+procedimento APÓS aplicar filtros
    if (not qs_is_list) and (not modo_ocorridos):
        from django.db.models import Max
        ultimos_registros_ids = qs.values('colaborador_id', 'procedimento_id').annotate(
            ultimo_id=Max('id')
        ).values_list('ultimo_id', flat=True)
        qs = qs.filter(id__in=ultimos_registros_ids)

    # Ordenar
    if not qs_is_list:
        qs = qs.order_by('-data_treinamento')
    
    # Filtro de status (aplicar por Python após converter para lista)
    if status:
        if status == 'PENDENTE':
            qs = [t for t in qs if t.status_treinamento in {'PENDENTE', 'NAO_INICIADO'}]
        else:
            qs = [t for t in qs if t.status_treinamento == status]
    
    # Exportar
    exporter = PlanejamentoExcelExporter()
    return exporter.export_matriz_treinamentos(qs)


@login_required
def treinamentos_detalhe_view(request, treinamento_id):
    """View detalhes de um registro de treinamento."""
    treinamento = get_object_or_404(RegistroTreinamento, id=treinamento_id)
    return render(request, "procedures/treinamento_detalhe.html", {
        "treinamento": treinamento
    })


@login_required
def novo_treinamento_view(request):
    """Criar novo registro de treinamento."""
    if request.method == "POST":
        form = RegistroTreinamentoForm(request.POST)
        if form.is_valid():
            try:
                treinamento = form.save()
                messages.success(request, "Treinamento registrado com sucesso.")
                return redirect("treinamentos_list")
            except Exception as e:
                messages.error(request, f"Erro ao salvar: {str(e)}")
    else:
        form = RegistroTreinamentoForm()
    
    return render(request, "procedures/treinamento_form.html", {
        "form": form,
        "titulo": "Novo Treinamento"
    })


@login_required
def editar_treinamento_view(request, treinamento_id):
    """Editar registro de treinamento existente."""
    treinamento = get_object_or_404(RegistroTreinamento, id=treinamento_id)
    if request.method == "POST":
        form = RegistroTreinamentoForm(request.POST, instance=treinamento)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Treinamento atualizado com sucesso.")
                return redirect("treinamentos_list")
            except Exception as e:
                messages.error(request, f"Erro ao salvar: {str(e)}")
        else:
            messages.error(request, "Formulário contém erros. Verifique os campos.")
    else:
        form = RegistroTreinamentoForm(instance=treinamento)
    
    return render(request, "procedures/treinamento_form.html", {
        "form": form,
        "titulo": f"Editar Treinamento - {treinamento.colaborador.nome_completo if treinamento.colaborador else 'Externo'}"
    })


# ==============================================================================
# FORNECEDORES
# ==============================================================================

@login_required
def fornecedores_list_view(request):
    """Lista de fornecedores com filtros."""
    qs = Fornecedor.objects.all()
    
    termo = request.GET.get('q')
    status = request.GET.get('status')
    
    if termo:
        qs = qs.filter(Q(nome_fantasia__icontains=termo) | Q(cnpj__icontains=termo))
    if status:
        qs = qs.filter(status=status)
    
    page_number = request.GET.get('page', '1')
    paginator = Paginator(qs.order_by('nome_fantasia'), 50)
    page_obj = paginator.get_page(page_number)
    
    return render(request, "procedures/fornecedor_lista.html", {
        "page_obj": page_obj,
        "termo": termo,
        "status": status,
    })


@login_required
def novo_fornecedor_view(request):
    """Criar novo fornecedor."""
    if request.method == "POST":
        form = FornecedorForm(request.POST)
        if form.is_valid():
            fornecedor = form.save()
            messages.success(request, f"Fornecedor {fornecedor.nome_fantasia} criado com sucesso!")
            return redirect("fornecedores_list")
    else:
        form = FornecedorForm()
    
    return render(request, "procedures/fornecedor_form.html", {
        "form": form,
        "titulo": "Novo Fornecedor"
    })


@login_required
def editar_fornecedor_view(request, fornecedor_id):
    """Editar fornecedor existente."""
    fornecedor = get_object_or_404(Fornecedor, id=fornecedor_id)
    if request.method == "POST":
        form = FornecedorForm(request.POST, instance=fornecedor)
        if form.is_valid():
            form.save()
            messages.success(request, "Fornecedor atualizado com sucesso!")
            return redirect("fornecedores_list")
    else:
        form = FornecedorForm(instance=fornecedor)
    
    return render(request, "procedures/fornecedor_form.html", {
        "form": form,
        "titulo": f"Editar {fornecedor.nome_fantasia}"
    })


@login_required
def detalhe_fornecedor_view(request, fornecedor_id):
    """Detalhes de um fornecedor."""
    fornecedor = get_object_or_404(Fornecedor, id=fornecedor_id)
    avaliacoes = fornecedor.avaliacoes.all()
    
    return render(request, "procedures/fornecedor_detalhe.html", {
        "fornecedor": fornecedor,
        "avaliacoes": avaliacoes,
    })


# ==============================================================================
# AVALIAÇÕES DE FORNECEDOR
# ==============================================================================

@login_required
def nova_avaliacao_fornecedor_view(request):
    """Criar nova avaliação de fornecedor."""
    if request.method == "POST":
        form = AvaliacaoFornecedorForm(request.POST)
        if form.is_valid():
            avaliacao = form.save(commit=False)
            avaliacao.avaliador = request.user if hasattr(request.user, 'colaborador') else None
            avaliacao.save()
            messages.success(request, "Avaliação registrada com sucesso!")
            return redirect("fornecedores_list")
    else:
        form = AvaliacaoFornecedorForm()
    
    return render(request, "procedures/avaliacao_fornecedor_form.html", {
        "form": form
    })


# ==============================================================================
# PROCESSOS DE COTAÇÃO
# ==============================================================================

@login_required
def cotacoes_list_view(request):
    """Lista de processos de cotação."""
    qs = ProcessoCotacao.objects.all()
    
    status = request.GET.get('status')
    if status:
        qs = qs.filter(status=status)
    
    page_number = request.GET.get('page', '1')
    paginator = Paginator(qs.order_by('-data_abertura'), 50)
    page_obj = paginator.get_page(page_number)
    
    return render(request, "procedures/cotacao_lista.html", {
        "page_obj": page_obj,
        "status": status,
    })


@login_required
def nova_cotacao_view(request):
    """Criar novo processo de cotação."""
    if request.method == "POST":
        form = ProcessoCotacaoForm(request.POST)
        if form.is_valid():
            cotacao = form.save(commit=False)
            cotacao.responsavel = request.user if hasattr(request.user, 'colaborador') else None
            cotacao.save()
            form.save_m2m()
            messages.success(request, f"Cotação {cotacao.titulo} criada com sucesso!")
            return redirect("cotacoes_list")
    else:
        form = ProcessoCotacaoForm()
    
    return render(request, "procedures/cotacao_form.html", {
        "form": form,
        "titulo": "Nova Cotação"
    })


@login_required
def editar_cotacao_view(request, cotacao_id):
    """Editar processo de cotação existente."""
    cotacao = get_object_or_404(ProcessoCotacao, id=cotacao_id)
    if request.method == "POST":
        form = ProcessoCotacaoForm(request.POST, instance=cotacao)
        if form.is_valid():
            form.save()
            messages.success(request, "Cotação atualizada com sucesso!")
            return redirect("cotacoes_list")
    else:
        form = ProcessoCotacaoForm(instance=cotacao)
    
    return render(request, "procedures/cotacao_form.html", {
        "form": form,
        "titulo": f"Editar {cotacao.titulo}"
    })


@login_required
def detalhe_cotacao_view(request, cotacao_id):
    """Detalhes de um processo de cotação."""
    cotacao = get_object_or_404(ProcessoCotacao, id=cotacao_id)
    orcamentos = cotacao.orcamentos.all()
    
    return render(request, "procedures/cotacao_detalhe.html", {
        "cotacao": cotacao,
        "orcamentos": orcamentos,
    })


# ==============================================================================
# ORÇAMENTOS
# ==============================================================================

@login_required
def novo_orcamento_view(request):
    """Criar novo orçamento."""
    if request.method == "POST":
        form = OrcamentoForm(request.POST, request.FILES)
        if form.is_valid():
            orcamento = form.save()
            messages.success(request, "Orçamento criado com sucesso!")
            return redirect("cotacoes_list")
    else:
        form = OrcamentoForm()
    
    return render(request, "procedures/orcamento_form.html", {
        "form": form
    })


@login_required
def editar_orcamento_view(request, orcamento_id):
    """Editar orçamento existente."""
    orcamento = get_object_or_404(Orcamento, id=orcamento_id)
    if request.method == "POST":
        form = OrcamentoForm(request.POST, request.FILES, instance=orcamento)
        if form.is_valid():
            form.save()
            messages.success(request, "Orçamento atualizado com sucesso!")
            return redirect("detalhe_cotacao", cotacao_id=orcamento.processo.id)
    else:
        form = OrcamentoForm(instance=orcamento)
    
    return render(request, "procedures/orcamento_form.html", {
        "form": form
    })


# ==============================================================================
# API ENDPOINTS
# ==============================================================================

from django.http import JsonResponse


@login_required
@require_http_methods(["GET"])
def api_subareas_por_matriz_view(request):
    """Retorna sub-áreas ativas de uma matriz para preenchimento dinâmico de formulário."""
    matriz_id = request.GET.get('matriz_id')
    if not matriz_id:
        return JsonResponse({'items': []})

    sub_areas = SubAreaProcedimento.objects.filter(
        matriz_id=matriz_id,
        ativo=True,
    ).order_by('nome')

    data = {
        'items': [
            {'id': sub_area.id, 'nome': sub_area.nome}
            for sub_area in sub_areas
        ]
    }
    return JsonResponse(data)

def api_procedimentos_list(request):
    """API endpoint para listar procedimentos com filtros e paginação."""
    termo = (request.GET.get('q') or '').strip()
    classificacao = (request.GET.get('classificacao') or '').strip()
    matriz = (request.GET.get('matriz') or '').strip()
    sub_area = (request.GET.get('sub_area') or '').strip()
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    
    # Query otimizada - apenas campos necessários
    qs = Procedimento.objects.only('id', 'codigo', 'nome', 'classificacao', 'matriz', 'sub_area')
    
    if termo:
        qs = qs.filter(Q(codigo__icontains=termo) | Q(nome__icontains=termo))
    if classificacao:
        qs = qs.filter(classificacao__iexact=classificacao)
    if matriz:
        qs = qs.filter(matriz__icontains=matriz)
    if sub_area:
        qs = qs.filter(sub_area__icontains=sub_area)
    
    qs = qs.order_by('codigo')
    
    # Contar total para paginação
    total = qs.count()
    
    # Aplicar paginação
    start = (page - 1) * page_size
    end = start + page_size
    qs = qs[start:end]
    
    # Debug
    print(f"[DEBUG API] Filtros: q='{termo}', matriz='{matriz}', sub_area='{sub_area}'")
    print(f"[DEBUG API] Total encontrado: {total}")
    
    data = {
        'items': [{
            'id': p.id,
            'codigo': p.codigo,
            'nome': p.nome,
            'classificacao': p.get_classificacao_display() if hasattr(p, 'get_classificacao_display') else p.classificacao,
            'matriz': p.matriz or '',
            'sub_area': p.sub_area or '',
        } for p in qs],
        'total': total,
        'page': page,
        'page_size': page_size,
        'has_more': end < total
    }
    
    return JsonResponse(data)
