# -*- coding: utf-8 -*-
"""
Views para Gerenciamento de Templates de Etiquetas de Metrologia e Exportação em Excel (.xlsx).
"""

import base64
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import HttpResponse, Http404, JsonResponse
from django.db.models import Q
from datetime import date, timedelta

from metrologia.models import Instrumento, CategoriaInstrumento, TemplateEtiquetaInstrumento
from metrologia.services.etiqueta_excel_service import (
    TAGS_ETIQUETAS_METROLOGIA,
    render_etiquetas_excel
)


@login_required
def templates_etiquetas_list_view(request):
    """
    Lista e gerencia templates de etiquetas em Excel para instrumentos de metrologia.
    Exibe guia de tags dinâmicas e estatísticas.
    """
    templates = TemplateEtiquetaInstrumento.objects.all().order_by('tipo_variacao', '-padrao', 'nome')
    
    total_templates = templates.count()
    total_ativos = templates.filter(ativo=True).count()
    total_individual = templates.filter(tipo_variacao='INDIVIDUAL', ativo=True).count()
    total_multi_aba = templates.filter(tipo_variacao='MULTI_ABA', ativo=True).count()
    total_grade = templates.filter(tipo_variacao='GRADE_TABELA', ativo=True).count()

    context = {
        'templates': templates,
        'total_templates': total_templates,
        'total_ativos': total_ativos,
        'total_individual': total_individual,
        'total_multi_aba': total_multi_aba,
        'total_grade': total_grade,
        'tags_guia': TAGS_ETIQUETAS_METROLOGIA,
        'variacoes_choices': TemplateEtiquetaInstrumento.VARIACAO_CHOICES,
    }
    return render(request, 'metrologia/templates_etiquetas_lista.html', context)


@login_required
@require_POST
def template_etiqueta_upload_view(request):
    """
    Processa o upload de um novo template de etiqueta (.xlsx).
    Converte o arquivo para Base64 para persistência garantida em banco de dados.
    """
    codigo = (request.POST.get('codigo') or '').strip().upper()
    nome = (request.POST.get('nome') or '').strip()
    descricao = (request.POST.get('descricao') or '').strip()
    tipo_variacao = (request.POST.get('tipo_variacao') or 'INDIVIDUAL').strip()
    padrao = request.POST.get('padrao') == 'on' or request.POST.get('padrao') == 'true'

    if not codigo or not nome:
        messages.error(request, "Código e Nome do template são obrigatórios.")
        return redirect('metrologia:templates_etiquetas_list')

    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        messages.error(request, "Por favor, selecione um arquivo de planilha (.xlsx).")
        return redirect('metrologia:templates_etiquetas_list')

    if not arquivo.name.lower().endswith('.xlsx'):
        messages.error(request, "Formato inválido. Apenas arquivos Excel (.xlsx) são suportados.")
        return redirect('metrologia:templates_etiquetas_list')

    try:
        conteudo_bytes = arquivo.read()
        b64_str = base64.b64encode(conteudo_bytes).decode('utf-8')
        tamanho = len(conteudo_bytes)

        template, created = TemplateEtiquetaInstrumento.objects.update_or_create(
            codigo=codigo,
            defaults={
                'nome': nome,
                'descricao': descricao,
                'tipo_variacao': tipo_variacao,
                'arquivo': arquivo,
                'arquivo_base64': b64_str,
                'nome_arquivo_original': arquivo.name,
                'tamanho_arquivo': tamanho,
                'ativo': True,
                'padrao': padrao,
                'criado_por': request.user,
            }
        )

        if padrao:
            TemplateEtiquetaInstrumento.objects.filter(
                tipo_variacao=tipo_variacao,
                padrao=True
            ).exclude(pk=template.pk).update(padrao=False)

        msg = f"Template '{template.nome}' cadastrado com sucesso!" if created else f"Template '{template.nome}' atualizado com sucesso!"
        messages.success(request, msg)

    except Exception as e:
        messages.error(request, f"Erro ao processar o arquivo: {str(e)}")

    return redirect('metrologia:templates_etiquetas_list')


@login_required
def template_etiqueta_download_view(request, template_id):
    """
    Download do arquivo Excel (.xlsx) original do template cadastrado.
    """
    template = get_object_or_404(TemplateEtiquetaInstrumento, pk=template_id)

    if template.arquivo_base64:
        content = base64.b64decode(template.arquivo_base64)
    elif template.arquivo:
        template.arquivo.seek(0)
        content = template.arquivo.read()
    else:
        raise Http404("Arquivo do template não encontrado.")

    filename = template.nome_arquivo_original or f"Template_{template.codigo}.xlsx"
    response = HttpResponse(
        content,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_POST
def template_etiqueta_toggle_view(request, template_id):
    """
    Alterna o status ativo/inativo ou define como padrão da variação.
    """
    template = get_object_or_404(TemplateEtiquetaInstrumento, pk=template_id)
    action = request.POST.get('action')

    if action == 'toggle_ativo':
        template.ativo = not template.ativo
        template.save()
        status_str = "ativado" if template.ativo else "desativado"
        messages.success(request, f"Template '{template.nome}' {status_str} com sucesso.")
    elif action == 'set_padrao':
        template.padrao = True
        template.ativo = True
        template.save()
        messages.success(request, f"Template '{template.nome}' definido como padrão para a variação '{template.get_tipo_variacao_display()}'.")

    return redirect('metrologia:templates_etiquetas_list')


@login_required
@require_POST
def template_etiqueta_delete_view(request, template_id):
    """
    Exclui um template de etiqueta.
    """
    template = get_object_or_404(TemplateEtiquetaInstrumento, pk=template_id)
    nome = template.nome
    template.delete()
    messages.success(request, f"Template '{nome}' excluído com sucesso.")
    return redirect('metrologia:templates_etiquetas_list')


@login_required
def export_etiquetas_excel_view(request):
    """
    Gera arquivo Excel (.xlsx) com as etiquetas dos instrumentos selecionados ou filtrados.
    Permite escolher o template/variação via parâmetro 'template_id' ou 'variacao'.
    """
    # 1. Filtros de Instrumentos
    q = (request.GET.get('q') or '').strip().lower()
    st = set((request.GET.get('st') or '').split(',')) if request.GET.get('st') else set()
    cat = set((request.GET.get('cat') or '').split(',')) if request.GET.get('cat') else set()
    st_setor = set((request.GET.get('set') or '').split(',')) if request.GET.get('set') else set()
    
    # IDs específicos selecionados
    selected_ids = []
    try:
        raw_ids = (request.GET.get('ids') or '').strip()
        if raw_ids:
            selected_ids = [int(x) for x in raw_ids.split(',') if x.strip().isdigit()]
    except Exception:
        pass

    # Instrumento único direto (ex: da linha da tabela)
    inst_id = request.GET.get('instrumento_id')
    if inst_id and inst_id.isdigit():
        selected_ids = [int(inst_id)]

    qs = Instrumento.objects.all().select_related('categoria', 'setor', 'responsavel').prefetch_related('calibracoes')

    if selected_ids:
        qs = qs.filter(id__in=selected_ids)
    else:
        if st:
            if 'ATIVO' in st and 'INATIVO' not in st:
                qs = qs.filter(ativo=True)
            elif 'INATIVO' in st and 'ATIVO' not in st:
                qs = qs.filter(ativo=False)
        if cat:
            try:
                cat_ids = [int(x) for x in cat if x.isdigit()]
                qs = qs.filter(categoria_id__in=cat_ids)
            except Exception:
                pass
        if st_setor:
            try:
                setor_ids = [int(x) for x in st_setor if x.isdigit()]
                qs = qs.filter(setor_id__in=setor_ids)
            except Exception:
                pass
        if q:
            qs = qs.filter(
                Q(tag__icontains=q) |
                Q(descricao__icontains=q) |
                Q(fabricante__icontains=q) |
                Q(modelo__icontains=q)
            )

    instrumentos = list(qs.order_by('tag'))

    if not instrumentos:
        messages.warning(request, "Nenhum instrumento encontrado para geração de etiquetas.")
        return redirect(request.META.get('HTTP_REFERER') or 'metrologia:dashboard')

    # 2. Escolha do Template / Variação
    template_id = request.GET.get('template_id')
    variacao = request.GET.get('variacao')
    template_obj = None

    if template_id and template_id.isdigit():
        template_obj = TemplateEtiquetaInstrumento.objects.filter(pk=int(template_id), ativo=True).first()

    if not template_obj and variacao:
        template_obj = TemplateEtiquetaInstrumento.objects.filter(
            tipo_variacao=variacao, ativo=True, padrao=True
        ).first() or TemplateEtiquetaInstrumento.objects.filter(
            tipo_variacao=variacao, ativo=True
        ).first()

    if not template_obj:
        # Se for 1 instrumento, busca padrão individual; se múltiplos, busca padrão multi_aba
        target_var = 'INDIVIDUAL' if len(instrumentos) == 1 else 'MULTI_ABA'
        template_obj = TemplateEtiquetaInstrumento.objects.filter(
            tipo_variacao=target_var, ativo=True, padrao=True
        ).first() or TemplateEtiquetaInstrumento.objects.filter(
            ativo=True, padrao=True
        ).first() or TemplateEtiquetaInstrumento.objects.filter(
            ativo=True
        ).first()

    try:
        excel_bytes = render_etiquetas_excel(template_obj, instrumentos)
        
        if len(instrumentos) == 1:
            filename = f"Etiqueta_{instrumentos[0].tag}_{date.today().strftime('%Y%m%d')}.xlsx"
        else:
            filename = f"Etiquetas_Instrumentos_{len(instrumentos)}_{date.today().strftime('%Y%m%d')}.xlsx"

        response = HttpResponse(
            excel_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Access-Control-Expose-Headers'] = 'Content-Disposition'
        return response

    except Exception as e:
        messages.error(request, f"Erro ao gerar arquivo Excel de etiquetas: {str(e)}")
        return redirect(request.META.get('HTTP_REFERER') or 'metrologia:dashboard')
