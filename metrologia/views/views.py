# -*- coding: utf-8 -*-
"""
Views para o módulo Metrologia (Calibração de Instrumentos)

AVISO: Este arquivo contém views DEPRECATED que foram consolidadas em qms/views.py.
Todas as views de metrologia agora estão centralizadas em qms/views.py para melhor
manutenção e evitar duplicação de código.

Views ativas:
- Redirecionadas para qms/views.py

Views legadas (não use):
- imp_instr_view() - USE: qms.views.imp_instr_view()
- imp_historico_view() - USE: qms.views.imp_historico_view()
- modulo_metrologia_view() - USE: qms.views.modulo_metrologia_view()
- novo_instrumento_view() - USE: qms.views.novo_instrumento_view()
- detalhe_instrumento_view() - USE: qms.views.detalhe_instrumento_view()
- ... e outras

Para adicionar novas views de metrologia, edit qms/views.py ao invés deste arquivo.
"""

import io
import os
import re
import tempfile
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
import pandas as pd
import logging

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4, portrait, landscape
    from reportlab.lib.colors import HexColor as RColor
    from PyPDF2 import PdfReader, PdfWriter
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Imports dos models
from metrologia.models import (
    Instrumento, FaixaMedicao, HistoricoCalibracao, CategoriaInstrumento,
    ResultadoFaixaCalibracao, ArquivoPadrao, TemplateEtiquetaInstrumento
)
from organization.models import Setor
from rh.models import Colaborador
from core.models import UnidadeMedida
from qms.models import ImportJob, SolicitacaoInstrumento

# Imports dos forms
from metrologia.forms import (
    InstrumentoForm, ImportacaoInstrumentosForm,
    ImportacaoHistoricoForm, HistoricoCalibracaoForm,
)

# Imports dos helpers
from qms.views_helpers import (
    export_to_excel_response, parse_date, excel_date_to_datetime
)


# ==============================================================================
# VIEWS DE ARQUIVO PADRÃO
# ==============================================================================

@login_required
@require_POST
def renomear_arquivo_padrao_view(request, arquivo_id):
    """Renomeia um arquivo PDF de padrão associado ao histórico."""
    arquivo = get_object_or_404(ArquivoPadrao, id=arquivo_id)
    novo_nome = request.POST.get('novo_nome', '').strip()
    historicos = arquivo.historicos.all()
    
    # Permissão: só responsável técnico do histórico ou staff pode renomear
    pode_renomear = False
    for historico in historicos:
        if historico.responsavel and historico.responsavel.strip().lower() == \
           (request.user.get_full_name() or request.user.username).strip().lower():
            pode_renomear = True
    if request.user.is_staff:
        pode_renomear = True
    
    if not pode_renomear:
        messages.error(request, "Você não tem permissão para renomear este arquivo.")
        if historicos:
            return redirect('registrar_historico_calibracao', instrumento_id=historicos[0].instrumento_id)
        return redirect('modulo_metrologia')
    
    if novo_nome:
        logger.info(f"Usuário {request.user.username} renomeou arquivo PDF id={arquivo.id} para '{novo_nome}'")
        arquivo.nome = novo_nome
        arquivo.save(update_fields=['nome'])
        messages.success(request, "Nome do arquivo atualizado com sucesso.")
    else:
        messages.error(request, "Nome inválido.")
    
    if historicos:
        return redirect('registrar_historico_calibracao', instrumento_id=historicos[0].instrumento_id)
    return redirect('modulo_metrologia')


@login_required
@require_POST
def remover_arquivo_padrao_view(request, arquivo_id):
    """Remove um arquivo PDF de padrão associado ao histórico."""
    arquivo = get_object_or_404(ArquivoPadrao, id=arquivo_id)
    historicos = arquivo.historicos.all()
    
    # Permissão: só responsável técnico ou staff pode remover
    pode_remover = False
    for historico in historicos:
        if historico.responsavel and historico.responsavel.strip().lower() == \
           (request.user.get_full_name() or request.user.username).strip().lower():
            pode_remover = True
    if request.user.is_staff:
        pode_remover = True
    
    if not pode_remover:
        messages.error(request, "Você não tem permissão para remover este arquivo.")
        if historicos:
            return redirect('registrar_historico_calibracao', instrumento_id=historicos[0].instrumento_id)
        return redirect('modulo_metrologia')
    
    # Remove arquivo (já não precisa remover de históricos pois há FK)
    logger.info(f"Usuário {request.user.username} removeu arquivo PDF id={arquivo.id}")
    arquivo.arquivo.delete(save=False)
    arquivo.delete()
    messages.success(request, "Arquivo removido com sucesso.")
    
    if historicos:
        return redirect('registrar_historico_calibracao', instrumento_id=historicos[0].instrumento_id)
    return redirect('modulo_metrologia')


# ==============================================================================
# VIEWS DE IMPORTAÇÃO
# ==============================================================================

@login_required
def imp_instr_view(request):
    """Importa instrumentos de calibração a partir de arquivo Excel/CSV."""
    if request.method == "POST":
        form = ImportacaoInstrumentosForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                uploaded = request.FILES["arquivo_excel"]
                suffix = os.path.splitext(uploaded.name)[1] or ".xlsx"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                for chunk in uploaded.chunks():
                    tmp.write(chunk)
                tmp.flush()
               
                job = ImportJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    filename=uploaded.name,
                    filepath=tmp.name,
                    job_type="INSTRUMENTOS",
                    status="PENDING",
                )

                from qms.tasks import import_instruments_task
                force_sync = os.environ.get("SYNC_IMPORTS", "1") == "1"
                if not force_sync:
                    try:
                        import_instruments_task.delay(str(job.id), tmp.name)
                        messages.success(request, f"Importação enfileirada (job {job.id}).")
                        return redirect("modulo_metrologia")
                    except Exception:
                        force_sync = True
                
                if force_sync:
                    import_instruments_task(job.id, tmp.name)
                    job.refresh_from_db()
                    messages.success(request, f"Importação concluída (job {job.id}). {job.result or ''}")
                    return redirect("modulo_metrologia")
            except Exception as e:
                messages.error(request, f"Erro ao enfileirar importação: {str(e)}")
                return redirect("metrologia:modulo_metrologia")
    else:
        form = ImportacaoInstrumentosForm()
    
    return render(
        request,
        "metrologia/imports/instrumentos.html",
        {"form": form, "jobs": ImportJob.objects.filter(job_type='INSTRUMENTOS').order_by('-created_at')[:5]},
    )


@login_required
def imp_historico_view(request):
    """Importa históricos de calibração a partir de arquivo Excel/CSV."""
    if request.method == "POST":
        form = ImportacaoHistoricoForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                uploaded = request.FILES["arquivo_excel"]
                suffix = os.path.splitext(uploaded.name)[1] or ".xlsx"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                for chunk in uploaded.chunks():
                    tmp.write(chunk)
                tmp.flush()
                tmp.close()

                job = ImportJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    filename=uploaded.name,
                    filepath=tmp.name,
                    job_type="HISTORICO",
                    status="PENDING",
                )

                from qms.tasks import import_historico_task
                force_sync = os.environ.get("SYNC_IMPORTS", "1") == "1"
                if not force_sync:
                    try:
                        import_historico_task.delay(str(job.id), tmp.name)
                        messages.success(request, f"Importação histórico enfileirada (job {job.id}).")
                        return redirect("modulo_metrologia")
                    except Exception:
                        force_sync = True
                
                if force_sync:
                    import_historico_task(job.id, tmp.name)
                    job.refresh_from_db()
                    try:
                        # Recalcula datas nos instrumentos afetados
                        from dateutil.relativedelta import relativedelta
                        afetados = HistoricoCalibracao.objects.filter(
                            criado_em__gte=job.created_at
                        ).values_list("instrumento_id", flat=True).distinct()
                        for iid in afetados:
                            inst = Instrumento.objects.filter(id=iid).first()
                            if inst:
                                ultima = HistoricoCalibracao.objects.filter(instrumento=inst).order_by("-data_calibracao").first()
                                if ultima:
                                    inst.data_ultima_calibracao = ultima.data_calibracao
                                    # Recalcular próxima calibração baseado na frequência do instrumento
                                    meses = None
                                    if inst.frequencia_meses:
                                        meses = inst.frequencia_meses
                                    elif inst.categoria and inst.categoria.frequencia_calibracao_meses:
                                        meses = inst.categoria.frequencia_calibracao_meses
                                    
                                    if meses:
                                        inst.data_proxima_calibracao = ultima.data_calibracao + relativedelta(months=meses)
                                    else:
                                        inst.data_proxima_calibracao = ultima.proxima_calibracao if hasattr(ultima, 'proxima_calibracao') else None
                                else:
                                    inst.data_ultima_calibracao = None
                                    inst.data_proxima_calibracao = None
                                inst.save(update_fields=["data_ultima_calibracao", "data_proxima_calibracao"])
                    except Exception:
                        pass
                    messages.success(request, f"Histórico importado (job {job.id}). {job.result or ''}")
                    return redirect("modulo_metrologia")
            except Exception as e:
                messages.error(request, f"Erro ao enfileirar importação: {str(e)}")
                return redirect("importar_historico")
    else:
        form = ImportacaoHistoricoForm()
    
    return render(
        request,
        "metrologia/imports/historico.html",
        {"form": form, "jobs": ImportJob.objects.filter(job_type='HISTORICO').order_by('-created_at')[:5]},
    )


# ==============================================================================
# VIEWS DE DASHBOARD E LISTAGEM
# ==============================================================================

@login_required
def modulo_metrologia_view(request):
    """Dashboard principal do módulo de Metrologia."""
    instrumentos = Instrumento.objects.all().select_related('categoria','setor').prefetch_related('historicos', 'ocorrencias').order_by("tag")

    # Filtro de status
    st_param = (request.GET.get('st') or '').upper()
    if st_param:
        parts = {p.strip() for p in st_param.split(',') if p.strip()}
        if 'ATIVO' in parts and 'INATIVO' not in parts:
            instrumentos = instrumentos.filter(ativo=True)
        elif 'INATIVO' in parts and 'ATIVO' not in parts:
            instrumentos = instrumentos.filter(ativo=False)

    status_filter = request.GET.get("status")
    hoje = date.today()
    alerta_30d = hoje + timedelta(days=30)
    alerta_60d = hoje + timedelta(days=60)
    alerta_90d = hoje + timedelta(days=90)
    alerta_120d = hoje + timedelta(days=120)
    
    if status_filter == "vencidos":
        messages.info(request, "Filtro sugerido: VENCIDOS (aplicado na interface).")
    elif status_filter == "avencer":
        messages.info(request, "Filtro sugerido: A Vencer (30d) (aplicado na interface).")

    # Filtros
    from django.db.models.functions import Lower
    setores_ids = Instrumento.objects.all().values_list("setor", flat=True).distinct()
    setores_filtro = Setor.objects.filter(id__in=setores_ids).order_by(Lower("nome"))

    categorias_ids = Instrumento.objects.all().values_list("categoria", flat=True).distinct()
    categorias_filtro = CategoriaInstrumento.objects.filter(
        id__in=categorias_ids
    ).order_by(Lower("nome"))

    # Periodos filtro logic
    periodos_set = set()
    for inst in instrumentos:
        if inst.data_proxima_calibracao:
            periodos_set.add(inst.data_proxima_calibracao.strftime('%Y-%m'))
    
    periodos_filtro = []
    meses_pt = {'01':'Jan', '02':'Fev', '03':'Mar', '04':'Abr', '05':'Mai', '06':'Jun', '07':'Jul', '08':'Ago', '09':'Set', '10':'Out', '11':'Nov', '12':'Dez'}
    for p in sorted(list(periodos_set)):
        ano, mes = p.split('-')
        label = f"{meses_pt.get(mes, mes)}/{ano}"
        periodos_filtro.append({'value': p, 'label': label})

    templates_etiquetas = TemplateEtiquetaInstrumento.objects.filter(ativo=True).defer('arquivo_base64').order_by('tipo_variacao', '-padrao', 'nome')

    from django.contrib.auth.models import User
    usuarios_responsaveis = User.objects.filter(is_active=True).select_related('colaborador', 'colaborador__setor').order_by('first_name', 'username')

    ctx = {
        "instrumentos": instrumentos,
        "setores_filtro": setores_filtro,
        "categorias_filtro": categorias_filtro,
        "usuarios_responsaveis": usuarios_responsaveis,
        "hoje": hoje,
        "alerta_30d": alerta_30d,
        "alerta_60d": alerta_60d,
        "alerta_90d": alerta_90d,
        "alerta_120d": alerta_120d,
        "can_edit": True,
        "historico_form": HistoricoCalibracaoForm(),
        "periodos_filtro": periodos_filtro,
        "templates_etiquetas_disponiveis": templates_etiquetas,
    }
    return render(request, "metrologia/dashboard.html", ctx)


# ==============================================================================
# VIEWS DE EXPORTAÇÃO
# ==============================================================================

@login_required
def export_metrologia_view(request):
    """Exporta instrumentos respeitando filtros para Excel."""
    q = (request.GET.get('q') or '').strip().lower()
    st = set((request.GET.get('st') or '').split(',')) if request.GET.get('st') else set()
    sit = set((request.GET.get('sit') or '').split(',')) if request.GET.get('sit') else set()
    cat = set((request.GET.get('cat') or '').split(',')) if request.GET.get('cat') else set()
    st_setor = set((request.GET.get('set') or '').split(',')) if request.GET.get('set') else set()

    qs = Instrumento.objects.all().select_related('categoria','setor').prefetch_related('faixas','faixas__unidade')
    
    # Aplica filtros
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
        qs = qs.filter(Q(tag__icontains=q) | Q(descricao__icontains=q) | 
                      Q(fabricante__icontains=q) | Q(modelo__icontains=q))

    # Monta dados para exportação
    hoje = date.today()
    alerta_30d = hoje + timedelta(days=30)
    alerta_60d = hoje + timedelta(days=60)
    alerta_90d = hoje + timedelta(days=90)
    alerta_120d = hoje + timedelta(days=120)
    rows = []
    
    for inst in qs:
        situacao = 'EM_DIA'
        if inst.data_proxima_calibracao:
            if inst.data_proxima_calibracao < hoje:
                situacao = 'VENCIDO'
            elif inst.data_proxima_calibracao <= alerta_30d:
                situacao = 'AVENCER_30'
            elif inst.data_proxima_calibracao <= alerta_60d:
                situacao = 'AVENCER_60'
            elif inst.data_proxima_calibracao <= alerta_90d:
                situacao = 'AVENCER_90'
            elif inst.data_proxima_calibracao <= alerta_120d:
                situacao = 'AVENCER_120'
        
        if sit and situacao not in sit:
            continue
        
        unidade = ''
        try:
            fx = inst.faixas.all().first()
            if fx and fx.unidade:
                unidade = fx.unidade.nome
        except Exception:
            pass
        
        rows.append({
            'TAG': inst.tag,
            'DESCRICAO': inst.descricao,
            'CATEGORIA': inst.categoria.nome if inst.categoria else '',
            'SETOR': inst.setor.nome if inst.setor else '',
            'FABRICANTE': inst.fabricante or '',
            'MODELO': inst.modelo or '',
            'SERIE': inst.serie or '',
            'SITUACAO': situacao,
            'ULTIMA_CALIB': inst.data_ultima_calibracao.strftime('%Y-%m-%d') if inst.data_ultima_calibracao else '',
            'PROXIMA_CALIB': inst.data_proxima_calibracao.strftime('%Y-%m-%d') if inst.data_proxima_calibracao else '',
            'UNIDADE': unidade,
        })

    return export_to_excel_response(rows, "instrumentos_export.xlsx")


@login_required
def export_etiquetas_view(request):
    """Gera PDF A4 com etiquetas de instrumentos filtrados."""
    from reportlab.lib.pagesizes import A4, portrait, landscape
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor as RColor
    
    q = (request.GET.get('q') or '').strip().lower()
    st = set((request.GET.get('st') or '').split(',')) if request.GET.get('st') else set()
    sit = set((request.GET.get('sit') or '').split(',')) if request.GET.get('sit') else set()
    cat = set((request.GET.get('cat') or '').split(',')) if request.GET.get('cat') else set()
    st_setor = set((request.GET.get('set') or '').split(',')) if request.GET.get('set') else set()

    orient = (request.GET.get('orient') or 'portrait').lower()
    try:
        cols = max(1, int(request.GET.get('cols') or 2))
        rows = max(1, int(request.GET.get('rows') or 5))
    except Exception:
        cols, rows = 2, 5
    margin_mm = float(request.GET.get('margin_mm') or 10)
    pad_mm = float(request.GET.get('pad_mm') or 5)

    # Filtro base
    qs = Instrumento.objects.all().select_related('categoria','setor')
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
        qs = qs.filter(Q(tag__icontains=q) | Q(descricao__icontains=q) | 
                      Q(fabricante__icontains=q) | Q(modelo__icontains=q))

    # IDs selecionados
    selected_ids = []
    try:
        raw_ids = (request.GET.get('ids') or '').strip()
        if raw_ids:
            selected_ids = [int(x) for x in raw_ids.split(',') if x.strip().isdigit()]
    except Exception:
        pass

    # Filtra por situação
    hoje = date.today()
    alerta_30d = hoje + timedelta(days=30)
    alerta_60d = hoje + timedelta(days=60)
    alerta_90d = hoje + timedelta(days=90)
    alerta_120d = hoje + timedelta(days=120)
    instrumentos = []
    base_iter = qs.order_by('tag')
    if selected_ids:
        base_iter = base_iter.filter(id__in=selected_ids)
    
    for inst in base_iter:
        situacao = 'EM_DIA'
        if inst.data_proxima_calibracao:
            if inst.data_proxima_calibracao < hoje:
                situacao = 'VENCIDO'
            elif inst.data_proxima_calibracao <= alerta_30d:
                situacao = 'AVENCER_30'
            elif inst.data_proxima_calibracao <= alerta_60d:
                situacao = 'AVENCER_60'
            elif inst.data_proxima_calibracao <= alerta_90d:
                situacao = 'AVENCER_90'
            elif inst.data_proxima_calibracao <= alerta_120d:
                situacao = 'AVENCER_120'
        if sit and situacao not in sit:
            continue
        instrumentos.append((inst, situacao))

    # Gera PDF com etiquetas
    buf = io.BytesIO()
    page_size = portrait(A4) if orient != 'landscape' else landscape(A4)
    c = canvas.Canvas(buf, pagesize=page_size)
    pw, ph = page_size

    mm = 2.834645669291339
    margin = margin_mm * mm
    pad = pad_mm * mm
    grid_w = pw - 2*margin
    grid_h = ph - 2*margin
    cell_w = (grid_w - (cols-1)*pad) / cols
    cell_h = (grid_h - (rows-1)*pad) / rows

    def draw_label(x, y, inst, situacao):
        c.setLineWidth(1)
        c.rect(x, y, cell_w, cell_h)
        
        last_calib_date = getattr(inst, 'data_ultima_calibracao', None)
        if not last_calib_date or not isinstance(last_calib_date, (date, datetime)):
            last_calib_date = None
        
        last_cert_num = ''
        try:
            hist_qs = HistoricoCalibracao.objects.filter(instrumento=inst)
            last_hist = hist_qs.order_by('-data_calibracao').first()
            if last_hist:
                if not last_calib_date and hasattr(last_hist, 'data_calibracao'):
                    last_calib_date = last_hist.data_calibracao
                if hasattr(last_hist, 'numero_certificado'):
                    last_cert_num = last_hist.numero_certificado or ''
        except Exception as e:
            import logging
            logging.exception(f"Erro ao buscar histórico de calibração para {inst.tag}: {e}")
        
        calib_str = last_calib_date.strftime('%d/%m/%Y') if last_calib_date else ''
        prox_str = inst.data_proxima_calibracao.strftime('%m/%Y') if getattr(inst, 'data_proxima_calibracao', None) else ''

        # Fallback layout genérico
        bar_h = 18
        c.setFillColor(RColor(0,0,0))
        c.rect(x, y+cell_h-bar_h, cell_w, bar_h, fill=1, stroke=0)
        c.setFillColor(RColor(1,1,1))
        c.setFont('Helvetica-Bold', 12)
        c.drawString(x+6, y+cell_h-bar_h+4, (inst.setor.nome if inst.setor else 'Metrologia'))
        c.drawRightString(x+cell_w-6, y+cell_h-bar_h+4, (inst.categoria.nome if inst.categoria else 'FOR.152.R1'))
        
        c.setFillColor(RColor(0,0,0))
        c.setFont('Helvetica-Bold', 11)
        cx = x+12
        cy = y+cell_h- bar_h - 12
        c.circle(cx, cy, 5, stroke=1, fill=1)
        c.drawString(cx+12, cy-3, 'Calibração')
        c.circle(cx+140, cy, 5, stroke=1, fill=0)
        c.drawString(cx+152, cy-3, 'Verificação')
        
        c.setFont('Helvetica', 9)
        line_y = cy - 14
        def field(label, value=''):
            nonlocal line_y
            c.drawString(x+10, line_y, f"{label}")
            c.line(x+120, line_y-2, x+cell_w-10, line_y-2)
            if value:
                c.drawString(x+125, line_y, value)
            line_y -= 16
        field('Cód do instrumento:', inst.tag or '')
        field('N° Certificado:', last_cert_num)
        field('Realizado em:', calib_str)
        field('Vencimento (mês/ano):', prox_str)

    i = 0
    for inst, situ in instrumentos:
        if i and (i // (cols*rows)) != ((i-1) // (cols*rows)):
            c.showPage()
        
        page_index = i // (cols*rows)
        r = (i - page_index*cols*rows) // cols
        cidx = (i - page_index*cols*rows) % cols
        ox = margin + cidx * (cell_w + pad)
        oy = margin + (rows-1-r) * (cell_h + pad)
        draw_label(ox, oy, inst, situ)
        i += 1

    c.showPage()
    c.save()
    buf.seek(0)
    resp = HttpResponse(buf, content_type='application/pdf')
    resp['Content-Disposition'] = 'attachment; filename="etiquetas_instrumentos.pdf"'
    return resp


# ==============================================================================
# VIEWS DE INSTRUMENTO
# ==============================================================================

@login_required
def novo_instrumento_view(request):
    """Cadastro de novo instrumento."""
    if request.method == 'POST':
        form = InstrumentoForm(request.POST)
        if form.is_valid():
            inst = form.save()
            messages.success(request, f"Instrumento '{inst.tag}' cadastrado!")
            return redirect('modulo_metrologia')
        else:
            messages.error(request, "Verifique os dados do instrumento.")
    else:
        form = InstrumentoForm()
    
    return render(request, 'shared/form_generico.html', {
        'form': form,
        'titulo': 'Novo Instrumento',
    })


@login_required
def detalhe_instrumento_view(request, instrumento_id):
    """Visualiza detalhe de instrumento com históricos e ocorrências."""
    try:
        inst = get_object_or_404(Instrumento, id=instrumento_id)
    except Exception as e:
        logger.error(f"Erro ao buscar instrumento {instrumento_id}: {e}")
        raise

    # Processamento de formulário de ocorrência rápida
    if request.method == "POST":
        from rh.forms import OcorrenciaForm
        form_ocorrencia = OcorrenciaForm(request.POST)
        if form_ocorrencia.is_valid():
            ocorrencia = form_ocorrencia.save(commit=False)
            ocorrencia.instrumento = inst
            ocorrencia.usuario_responsavel = request.user
            ocorrencia.save()
            messages.success(request, "Ocorrência registrada com sucesso!")
            return redirect("detalhe_instrumento", instrumento_id=inst.id)
        else:
            messages.error(request, "Erro ao registrar ocorrência.")
    else:
        from rh.forms import OcorrenciaForm
        form_ocorrencia = OcorrenciaForm()

    # Busca dados relacionados
    try:
        # Busca todas as faixas do instrumento
        faixas_inst = list(inst.faixas.all().select_related('unidade').order_by('valor_minimo'))
        
        historico_qs = HistoricoCalibracao.objects.filter(instrumento=inst).order_by("-data_calibracao")
        
        # Garante que para cada histórico, todas as faixas do instrumento estejam criadas em resultados_faixa
        if faixas_inst:
            for h in historico_qs:
                faixas_existentes = set(h.resultados_faixa.values_list('faixa_id', flat=True))
                for f in faixas_inst:
                    if f.id not in faixas_existentes:
                        ResultadoFaixaCalibracao.objects.get_or_create(
                            historico=h,
                            faixa=f,
                            defaults={
                                'valor_minimo': f.valor_minimo,
                                'valor_maximo': f.valor_maximo,
                                'nominal': f.nominal,
                                'tolerancia': f.tolerancia_mais_menos,
                            }
                        )
        
        historico = HistoricoCalibracao.objects.filter(instrumento=inst).prefetch_related('resultados_faixa').order_by("-data_calibracao")
    except Exception as e:
        logger.error(f"Erro ao buscar histórico: {e}")
        try:
            historico = HistoricoCalibracao.objects.filter(instrumento=inst).order_by("-data_calibracao")
        except Exception:
            historico = []

    try:
        calibracoes = inst.calibracoes.all().order_by("-data_prevista")
    except AttributeError:
        calibracoes = []

    try:
        ocorrencias = inst.ocorrencias.all().order_by("-data_ocorrencia")
    except AttributeError:
        ocorrencias = []

    try:
        for oc in ocorrencias:
            u = getattr(oc, "usuario_responsavel", None)
            if u:
                col = Colaborador.objects.filter(user_django=u).only("id").first()
                if col:
                    setattr(oc, "responsavel_colab_id", col.id)
    except Exception:
        pass

    try:
        faixas = inst.faixamedicao_set.all()
    except AttributeError:
        faixas = []

    if hasattr(inst, "faixas"):
        faixas = inst.faixas.all()

    # Get all quotation requests (SolicitacaoCotacao) that contain items with this instrument
    try:
        from metrologia.models import SolicitacaoCotacao
        
        solicitacoes_cotacao = list(
            SolicitacaoCotacao.objects.filter(
                itens__instrumento=inst
            ).select_related(
                'responsavel'
            ).distinct().order_by('-data_criacao')
        )
    except Exception as e:
        solicitacoes_cotacao = []
        logger.error(f"Erro ao buscar solicitações de cotação para instrumento {instrumento_id}: {str(e)}")

    from django.contrib.auth.models import User
    usuarios_responsaveis = User.objects.filter(is_active=True).select_related('colaborador', 'colaborador__setor').order_by('first_name', 'username')

    return render(
        request,
        "metrologia/instrumento_detalhe.html",
        {
            "instrumento": inst,
            "historicos": historico,
            "calibracoes": calibracoes,
            "ocorrencias": ocorrencias,
            "faixas": faixas,
            "usuarios_responsaveis": usuarios_responsaveis,
            "form_ocorrencia": form_ocorrencia,
            "today": date.today(),
            "edit_url": f"/instrumento/{inst.id}/editar/",
            "solicitacoes_cotacao": solicitacoes_cotacao,
            "historico_form": HistoricoCalibracaoForm(),
        },
    )


# ==============================================================================
# VIEWS DE HISTÓRICO DE CALIBRAÇÃO
# ==============================================================================

@login_required
def remover_historico_view(request, historico_id):
    """Remove um registro de histórico de calibração."""
    hist = get_object_or_404(HistoricoCalibracao, id=historico_id)
    i_id = hist.instrumento.id
    
    if request.method == 'POST':
        # Remover certificado se existir
        if hist.certificado:
            hist.certificado.delete(save=False)
        # Remover histórico
        hist.delete()
        messages.success(request, "Histórico removido com sucesso.")
        return redirect("detalhe_instrumento", instrumento_id=i_id)
    
    # GET request - show confirmation page
    context = {
        'historico': hist,
        'instrumento_id': i_id,
    }
    return render(request, 'metrologia/remover_historico_confirm.html', context)


@login_required
def anexar_certificado_historico_view(request, historico_id):
    """Anexa arquivo PDF ao histórico."""
    hist = get_object_or_404(HistoricoCalibracao, id=historico_id)
    inst_id = hist.instrumento.id if hist.instrumento else None
    
    if request.method != "POST":
        messages.error(request, "Método inválido.")
        return redirect("detalhe_instrumento", instrumento_id=inst_id)

    if hist.certificado:
        messages.warning(request, "Este histórico já possui certificado anexado.")
        return redirect("detalhe_instrumento", instrumento_id=inst_id)

    up = request.FILES.get("certificado_pdf")
    if not up:
        messages.error(request, "Selecione um arquivo PDF para anexar.")
        return redirect("detalhe_instrumento", instrumento_id=inst_id)

    ctype = getattr(up, "content_type", "") or ""
    if "pdf" not in ctype.lower():
        messages.error(request, "Arquivo inválido. Envie um PDF.")
        return redirect("detalhe_instrumento", instrumento_id=inst_id)

    try:
        filename = f"Cert_{hist.numero_certificado}_{hist.instrumento.tag}.pdf" if hist.instrumento else up.name
        hist.certificado.save(filename, up, save=True)
        messages.success(request, "Certificado anexado com sucesso!")
    except Exception as e:
        messages.error(request, f"Falha ao anexar certificado: {e}")
    
    return redirect("detalhe_instrumento", instrumento_id=inst_id)


@login_required
def download_certificado_view(request, historico_id):
    """Faz download do certificado PDF."""
    hist = get_object_or_404(HistoricoCalibracao, id=historico_id)
    
    if not hist.certificado:
        messages.error(request, "Este histórico não possui certificado anexado.")
        return redirect("detalhe_instrumento", instrumento_id=hist.instrumento.id if hist.instrumento else 1)
    
    try:
        certificado_file = hist.certificado
        file_size = certificado_file.size
        logger.info(f"Acessando certificado {historico_id}: {certificado_file.name} (size: {file_size})")
        
        file_content = certificado_file.read()
        
        if not file_content:
            logger.error(f"Certificado {historico_id} vazio")
            messages.error(request, "Arquivo de certificado está vazio.")
            return redirect("detalhe_instrumento", instrumento_id=hist.instrumento.id if hist.instrumento else 1)
        
        filename = f"Cert_{hist.numero_certificado}_{hist.instrumento.tag if hist.instrumento else 'documento'}.pdf"
        
        response = HttpResponse(file_content, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        response['Content-Type'] = 'application/pdf; charset=utf-8'
        response['X-Content-Type-Options'] = 'nosniff'
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        response['Content-Length'] = str(len(file_content))
        
        logger.info(f"Certificado {historico_id} servido com sucesso ({len(file_content)} bytes)")
        return response
        
    except Exception as e:
        logger.error(f"Erro ao servir certificado {historico_id}: {e}", exc_info=True)
        messages.error(request, f"Erro ao acessar certificado: {str(e)}")
        return redirect("detalhe_instrumento", instrumento_id=hist.instrumento.id if hist.instrumento else 1)


@login_required
def remover_certificado_historico_view(request, historico_id):
    """Remove certificado do histórico mantendo o registro."""
    hist = get_object_or_404(HistoricoCalibracao, id=historico_id)
    inst_id = hist.instrumento.id if hist.instrumento else None
    
    if request.method != "POST":
        messages.error(request, "Método inválido.")
        return redirect("detalhe_instrumento", instrumento_id=inst_id)

    if not hist.certificado:
        messages.warning(request, "Este histórico não possui certificado anexado.")
        return redirect("detalhe_instrumento", instrumento_id=inst_id)

    try:
        hist.certificado.delete(save=False)
        hist.certificado = None
        hist.save(update_fields=["certificado"])
        messages.success(request, "Certificado removido. Você pode anexar um novo.")
    except Exception as e:
        messages.error(request, f"Falha ao remover certificado: {e}")
    
    return redirect("detalhe_instrumento", instrumento_id=inst_id)


@login_required
def registrar_historico_calibracao_view(request, instrumento_id):
    """Cria novo histórico de calibração a partir do modal ou cria um vazio e redireciona (legado)."""
    try:
        from datetime import date
        
        instrumento = get_object_or_404(Instrumento, id=instrumento_id)
        logger.info(f"Registrar histórico: instrumento_id={instrumento_id}, method={request.method}, user={request.user}")
        
        if request.method == 'POST' and 'numero_certificado' in request.POST:
            # Submissão do modal (formulário simplificado)
            form = HistoricoCalibracaoForm(request.POST, request.FILES)
            if form.is_valid():
                historico = form.save(commit=False)
                historico.instrumento = instrumento
                historico.save()
                messages.success(request, f"✓ Histórico registrado com sucesso!")
                return redirect('detalhe_instrumento', instrumento_id=instrumento_id)
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
                return redirect('detalhe_instrumento', instrumento_id=instrumento_id)
        else:
            # Cria um novo histórico vazio para o instrumento
            historico = HistoricoCalibracao.objects.create(
                instrumento=instrumento,
                resultado='PENDENTE'  # Estado inicial
            )
            
            logger.info(f"✓ Histórico vazio {historico.id} criado com sucesso para instrumento {instrumento_id}")
            
            # Redireciona para edição no template unificado (editar_historico.html)
            messages.success(request, f"✓ Novo histórico criado! Agora preencha os dados.")
            return redirect('editar_historico_calibracao', historico_id=historico.id)
        
    except Exception as e:
        logger.error(f"❌ Erro crítico em registrar_historico_calibracao_view: {e}", exc_info=True)
        messages.error(request, f'Erro ao criar histórico: {str(e)}')
        return redirect('detalhe_instrumento', instrumento_id=instrumento_id)


@login_required
def preview_certificado_view(request, historico_id):
    """Pré-visualização do certificado."""
    try:
        logger.info(f"Preview certificado: {historico_id}")
        historico = get_object_or_404(HistoricoCalibracao, id=historico_id)
        
        if not historico.certificado:
            messages.error(request, 'Histórico sem arquivo de certificado.')
            return redirect('detalhe_instrumento', instrumento_id=historico.instrumento_id)
        
        return render(request, 'metrologia/certificado_preview.html', {
            'historico': historico,
        })
    except Exception as e:
        logger.error(f"Erro em preview_certificado_view: {e}")
        messages.error(request, f'Erro ao visualizar certificado: {str(e)}')
        return redirect('modulo_metrologia')


@login_required
def aplicar_carimbo_certificado_view(request, historico_id):
    """Aplica carimbo de validação no certificado PDF."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.colors import red
    from PyPDF2 import PdfReader, PdfWriter
    from django.core.files import File
    
    stamp_path = None
    out_path = None
    
    try:
        logger.info(f"Aplicar carimbo: {historico_id}")
        historico = get_object_or_404(HistoricoCalibracao, id=historico_id)
        
        if not historico.certificado:
            messages.error(request, 'Histórico sem certificado.')
            return redirect('detalhe_instrumento', instrumento_id=historico.instrumento_id)
        
        # Gera carimbo com ReportLab
        stamp_fd, stamp_path = tempfile.mkstemp(suffix='.pdf')
        os.close(stamp_fd)
        c = canvas.Canvas(stamp_path, pagesize=letter)
        c.setFillColor(red)
        c.setFont("Helvetica-Bold", 18)
        carimbo_texto = f"VALIDADO - {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        c.drawString(72, 72, carimbo_texto)
        responsavel_txt = (historico.responsavel or request.user.get_full_name() or request.user.username)
        c.setFont("Helvetica", 12)
        c.drawString(72, 52, f"Resp. Técnico: {responsavel_txt}")
        c.save()
        logger.debug(f"Carimbo gerado: {stamp_path}")
        
        # Mescla com PDF original
        cert_content = io.BytesIO(historico.certificado.read())
        reader = PdfReader(cert_content)
        writer = PdfWriter()
        stamp_reader = PdfReader(stamp_path)
        first_page = reader.pages[0]
        first_page.merge_page(stamp_reader.pages[0])
        writer.add_page(first_page)
        
        for i in range(1, len(reader.pages)):
            writer.add_page(reader.pages[i])
        
        out_fd, out_path = tempfile.mkstemp(suffix='.pdf')
        os.close(out_fd)
        with open(out_path, 'wb') as f_out:
            writer.write(f_out)
        
        # Salva PDF carimbado
        with open(out_path, 'rb') as f_final:
            filename = os.path.basename(historico.certificado.name).replace('.pdf', '_carimbado.pdf')
            historico.certificado_carimbado.save(filename, File(f_final), save=False)
        
        historico.certificado_validado = True
        historico.save(update_fields=['certificado_carimbado', 'certificado_validado'])
        messages.success(request, 'Certificado validado e carimbado com sucesso!')
        logger.info(f"Certificado {historico_id} validado")
        return redirect('detalhe_instrumento', instrumento_id=historico.instrumento_id)
        
    except Exception as e:
        logger.error(f"Erro ao aplicar carimbo: {e}", exc_info=True)
        messages.error(request, f'Erro ao aplicar carimbo: {str(e)}')
        return redirect('modulo_metrologia')
    finally:
        try:
            if stamp_path and os.path.exists(stamp_path):
                os.unlink(stamp_path)
            if out_path and os.path.exists(out_path):
                os.unlink(out_path)
        except Exception:
            pass


@login_required
def visualizar_historico_calibracao_view(request, historico_id):
    """Visualiza ou edita registro histórico de calibração."""
    try:
        historico = get_object_or_404(HistoricoCalibracao, id=historico_id)
        instrumento = historico.instrumento

        if not request.user.is_superuser and not request.user.is_staff:
            messages.warning(request, "Acesso restrito; verifique permissões.")

        edit_mode = request.GET.get('edit') == '1'
        logger.info(f"Usuário {request.user} acessou histórico {historico_id} (edit={edit_mode})")

        if request.method == 'POST' and edit_mode:
            form = HistoricoCalibracaoForm(
                request.POST, 
                request.FILES, 
                instance=historico, 
                instrumento=instrumento, 
                user=request.user
            )
            
            if form.is_valid():
                try:
                    # Validação de faixas (idêntico a registrar_historico_calibracao_view)
                    faixas_qs = FaixaMedicao.objects.filter(instrumento=instrumento).order_by('valor_minimo')
                    entradas_validas = []
                    problemas = []
                    ativos_marcados = 0

                    for faixa in faixas_qs:
                        prefix = f"faixa_{faixa.id}_"
                        ativa_key = prefix + "ativa"
                        if ativa_key not in request.POST:
                            continue
                        ativos_marcados += 1

                        erro_str = (request.POST.get(prefix + "erro", "") or "").strip()
                        inc_str = (request.POST.get(prefix + "incerteza", "") or "").strip()
                        tol_str = (request.POST.get(prefix + "tolerancia", "") or "").strip()

                        tol_val = None
                        if tol_str:
                            try:
                                tol_val = Decimal(str(tol_str))
                            except Exception:
                                tol_val = None
                        else:
                            tol_val = faixa.tolerancia_mais_menos

                        try:
                            erro_val = Decimal(str(erro_str)) if erro_str != "" else None
                        except Exception:
                            erro_val = None
                        try:
                            inc_val = Decimal(str(inc_str)) if inc_str != "" else None
                        except Exception:
                            inc_val = None

                        if erro_val is None or inc_val is None or tol_val is None:
                            problemas.append(f"Faixa {faixa.valor_minimo}-{faixa.valor_maximo}: incompleta.")
                            continue

                        entradas_validas.append({
                            'faixa': faixa,
                            'erro': erro_val,
                            'inc': inc_val,
                            'tol': tol_val,
                        })

                    if ativos_marcados > 0 and len(entradas_validas) == 0:
                        messages.error(request, "Selecione ao menos uma faixa completa.")
                        for p in problemas:
                            messages.warning(request, p)
                        form.add_error(None, "Faixas incompletas.")
                        faixas_medicao = faixas_qs
                        resultados_faixas = historico.resultados_faixas.all()
                        return render(request, 'metrologia/historico_calibracao_detail.html', {
                            'form': form,
                            'historico': historico,
                            'instrumento': instrumento,
                            'faixas_medicao': faixas_medicao,
                            'resultados_faixas': resultados_faixas,
                            'edit_mode': True,
                        })

                    # Salva histórico
                    historico_salvo = form.save(commit=False)
                    historico_salvo.save()
                    form.save_m2m()

                    # Limpa e recria resultados
                    historico.resultados_faixas.all().delete()
                    criadas = 0
                    ignoradas = 0
                    for ent in entradas_validas:
                        try:
                            ResultadoFaixaCalibracao.objects.create(
                                historico=historico,
                                faixa_medicao=ent['faixa'],
                                erro_encontrado=ent['erro'],
                                incerteza=ent['inc'],
                                tolerancia_usada=ent['tol'],
                                desconsiderada=False,
                            )
                            criadas += 1
                        except Exception as e_create:
                            logger.error(f"Erro: {e_create}")
                            ignoradas += 1

                    # Atualiza resultado geral
                    try:
                        resultados = list(historico.resultados_faixas.values_list('resultado', flat=True))
                        overall = None
                        if resultados:
                            if 'REPROVADO' in resultados:
                                overall = 'REPROVADO'
                            elif 'APROVADO_COM_CORRECAO' in resultados:
                                overall = 'APROVADO_COM_CORRECAO'
                            else:
                                overall = 'APROVADO_SEM_CORRECAO'
                        if overall and historico.resultado != overall:
                            historico.resultado = overall
                            historico.save(update_fields=['resultado'])
                    except Exception:
                        pass

                    messages.success(request, f"Histórico atualizado! Faixas: {criadas}.")
                    logger.info(f"Histórico {historico_id} atualizado")
                    return redirect('detalhe_instrumento', instrumento_id=instrumento.id)
                    
                except Exception as save_error:
                    logger.error(f"Erro ao salvar: {save_error}")
                    messages.error(request, f'Erro ao salvar: {str(save_error)}')
            else:
                messages.error(request, 'Corrija os erros.')
        else:
            form = HistoricoCalibracaoForm(
                instance=historico, 
                instrumento=instrumento, 
                user=request.user
            ) if edit_mode else None
        
        # Busca dados para renderização
        faixas_medicao = FaixaMedicao.objects.filter(instrumento=instrumento).order_by('valor_minimo')
        resultados_faixas = historico.resultados_faixas.all()
        resultados_map = {}
        for rf in resultados_faixas:
            if hasattr(rf, 'faixa_medicao_id'):
                resultados_map[rf.faixa_medicao_id] = rf
        
        # Atualiza resultado geral
        try:
            resultados = list(historico.resultados_faixas.values_list('resultado', flat=True))
            overall = None
            if resultados:
                if 'REPROVADO' in resultados:
                    overall = 'REPROVADO'
                elif 'APROVADO_COM_CORRECAO' in resultados:
                    overall = 'APROVADO_COM_CORRECAO'
                else:
                    overall = 'APROVADO_SEM_CORRECAO'
            if overall and historico.resultado != overall:
                historico.resultado = overall
                historico.save(update_fields=['resultado'])
        except Exception:
            pass
        
        return render(request, 'metrologia/historico_calibracao_detail.html', {
            'form': form,
            'historico': historico,
            'instrumento': instrumento,
            'faixas_medicao': faixas_medicao,
            'resultados_faixas': resultados_faixas,
            'resultados_map': resultados_map,
            'edit_mode': edit_mode,
        })
    except Exception as e:
        logger.error(f"Erro em visualizar_historico: {e}")
        messages.error(request, f'Erro: {str(e)}')
        return redirect('modulo_metrologia')


@login_required
def api_faixa_medicao_view(request, faixa_id):
    """API para retornar dados de uma faixa de medição."""
    try:
        faixa = get_object_or_404(FaixaMedicao, id=faixa_id)
        data = {
            'id': faixa.id,
            'unidade': faixa.unidade.nome if faixa.unidade else None,
            'valor_minimo': float(faixa.valor_minimo) if faixa.valor_minimo else None,
            'valor_maximo': float(faixa.valor_maximo) if faixa.valor_maximo else None,
            'tolerancia_mais_menos': float(faixa.tolerancia_mais_menos) if faixa.tolerancia_mais_menos else None,
            'nominal': float(faixa.nominal) if faixa.nominal else None,
            'resolucao': float(faixa.resolucao) if faixa.resolucao else None,
        }
        return JsonResponse(data)
    except Exception as e:
        logger.error(f"Erro ao buscar faixa {faixa_id}: {e}")
        return JsonResponse({'error': str(e)}, status=404)

@login_required
@require_http_methods(["POST"])
def registrar_historico_massa(request):
    """Cria novo histórico de calibração em massa para os instrumentos selecionados."""
    if request.method != 'POST':
        return redirect(request.META.get('HTTP_REFERER', 'modulo_metrologia'))

    instrumentos_ids_str = request.POST.get("instrumentos_ids", "")
    if not instrumentos_ids_str:
        messages.error(request, "Nenhum instrumento selecionado.")
        return redirect(request.META.get('HTTP_REFERER', 'modulo_metrologia'))
        
    ids = [int(i.strip()) for i in instrumentos_ids_str.split(",") if i.strip().isdigit()]
    if not ids:
        messages.error(request, "Nenhum instrumento válido selecionado.")
        return redirect(request.META.get('HTTP_REFERER', 'modulo_metrologia'))
        
    instrumentos = Instrumento.objects.filter(id__in=ids)
    
    sucesso = 0
    erros = 0
    
    for instrumento in instrumentos:
        post_data = request.POST.copy()
        cert_num = request.POST.get(f'certificado_{instrumento.id}', '').strip()
        post_data['numero_certificado'] = cert_num if cert_num else 'S/N'
        
        form = HistoricoCalibracaoForm(post_data, request.FILES)
        if form.is_valid():
            historico = form.save(commit=False)
            historico.instrumento = instrumento
            historico.save()
            
            # Garantir atualização imediata da data e status na tabela de Instrumentos
            Instrumento.objects.filter(id=instrumento.id).update(
                data_ultima_calibracao=historico.data_calibracao,
                data_proxima_calibracao=historico.proxima_calibracao
            )
            sucesso += 1
        else:
            erros += 1
            for field, form_errors in form.errors.items():
                for error in form_errors:
                    messages.error(request, f"{instrumento.tag} - {field}: {error}")
                    
    if sucesso > 0:
        messages.success(request, f"✓ {sucesso} registros de calibração criados com sucesso!")
        
    return redirect(request.META.get('HTTP_REFERER', 'modulo_metrologia'))


@login_required
def registrar_ocorrencia(request):
    from qms.models import OcorrenciaInstrumento
    from metrologia.models import Instrumento
    from django.contrib.auth.models import User
    from shared.inbox import invalidar_cache_inbox
    from django.shortcuts import redirect, get_object_or_404
    from django.contrib import messages
    from datetime import datetime

    if request.method == 'POST':
        instrumento_id = request.POST.get('instrumento_id')
        tipo = request.POST.get('tipo')
        descricao = request.POST.get('descricao')
        data_ocorrencia = request.POST.get('data_ocorrencia')
        usuario_responsavel_id = request.POST.get('usuario_responsavel')

        instrumento = get_object_or_404(Instrumento, pk=instrumento_id)
        
        usuario_responsavel = None
        if usuario_responsavel_id:
            try:
                usuario_responsavel = User.objects.get(pk=usuario_responsavel_id)
            except User.DoesNotExist:
                pass

        oc = OcorrenciaInstrumento.objects.create(
            instrumento=instrumento,
            tipo=tipo,
            descricao=descricao,
            data_ocorrencia=data_ocorrencia or datetime.now().date(),
            usuario_responsavel=usuario_responsavel,
            status='ABERTA'
        )

        invalidar_cache_inbox(request.user)
        if usuario_responsavel:
            invalidar_cache_inbox(usuario_responsavel)

        if usuario_responsavel:
            resp_nome = usuario_responsavel.get_full_name() or usuario_responsavel.username
            messages.success(request, f'Ocorrência registrada e direcionada para {resp_nome} com sucesso.')
        else:
            messages.success(request, 'Ocorrência registrada com sucesso.')

    return redirect(request.META.get('HTTP_REFERER', 'metrologia:modulo_metrologia'))

@login_required
def atribuir_responsavel_ocorrencia(request, ocorrencia_id):
    """Permite associar ou transferir rapidamente o responsável por uma ocorrência."""
    from qms.models import OcorrenciaInstrumento
    from django.contrib.auth.models import User
    from shared.inbox import invalidar_cache_inbox
    from django.shortcuts import redirect, get_object_or_404
    from django.contrib import messages

    if request.method == 'POST':
        ocorrencia = get_object_or_404(OcorrenciaInstrumento, pk=ocorrencia_id)
        usuario_antigo = ocorrencia.usuario_responsavel
        usuario_responsavel_id = request.POST.get('usuario_responsavel')

        if usuario_responsavel_id:
            try:
                novo_responsavel = User.objects.get(pk=usuario_responsavel_id)
                ocorrencia.usuario_responsavel = novo_responsavel
                ocorrencia.save(update_fields=['usuario_responsavel'])
                
                invalidar_cache_inbox(request.user)
                if usuario_antigo:
                    invalidar_cache_inbox(usuario_antigo)
                invalidar_cache_inbox(novo_responsavel)

                resp_nome = novo_responsavel.get_full_name() or novo_responsavel.username
                messages.success(request, f'Tratativa da ocorrência #{ocorrencia.id} direcionada com sucesso para {resp_nome}.')
            except User.DoesNotExist:
                messages.error(request, 'Usuário selecionado não encontrado.')
        else:
            ocorrencia.usuario_responsavel = None
            ocorrencia.save(update_fields=['usuario_responsavel'])
            invalidar_cache_inbox(request.user)
            if usuario_antigo:
                invalidar_cache_inbox(usuario_antigo)
            messages.info(request, f'Responsável da ocorrência #{ocorrencia.id} foi desatribuído.')

    return redirect(request.META.get('HTTP_REFERER', 'metrologia:modulo_metrologia'))

@login_required
def encerrar_ocorrencia(request, ocorrencia_id):
    from qms.models import OcorrenciaInstrumento
    from shared.inbox import invalidar_cache_inbox
    from django.shortcuts import redirect, get_object_or_404
    from django.contrib import messages
    from datetime import datetime

    if request.method == 'POST':
        ocorrencia = get_object_or_404(OcorrenciaInstrumento, pk=ocorrencia_id)
        usuario_antigo = ocorrencia.usuario_responsavel
        ocorrencia.status = 'ENCERRADA'
        ocorrencia.data_encerramento = datetime.now().date()
        ocorrencia.save()

        invalidar_cache_inbox(request.user)
        if usuario_antigo:
            invalidar_cache_inbox(usuario_antigo)

        messages.success(request, 'Ocorrência encerrada com sucesso.')
    return redirect(request.META.get('HTTP_REFERER', 'metrologia:modulo_metrologia'))

@login_required
def reabrir_ocorrencia(request, ocorrencia_id):
    """Reabre uma ocorrência anteriormente encerrada."""
    from qms.models import OcorrenciaInstrumento
    from shared.inbox import invalidar_cache_inbox
    from django.shortcuts import redirect, get_object_or_404
    from django.contrib import messages

    if request.method == 'POST':
        ocorrencia = get_object_or_404(OcorrenciaInstrumento, pk=ocorrencia_id)
        ocorrencia.status = 'ABERTA'
        ocorrencia.data_encerramento = None
        ocorrencia.save()

        invalidar_cache_inbox(request.user)
        if ocorrencia.usuario_responsavel:
            invalidar_cache_inbox(ocorrencia.usuario_responsavel)

        messages.success(request, f'Ocorrência #{ocorrencia.id} reaberta com sucesso.')
    return redirect(request.META.get('HTTP_REFERER', 'metrologia:modulo_metrologia'))

@login_required
def editar_ocorrencia(request, ocorrencia_id):
    from qms.models import OcorrenciaInstrumento
    from django.contrib.auth.models import User
    from shared.inbox import invalidar_cache_inbox
    from django.shortcuts import redirect, get_object_or_404
    from django.contrib import messages

    if request.method == 'POST':
        ocorrencia = get_object_or_404(OcorrenciaInstrumento, pk=ocorrencia_id)
        usuario_antigo = ocorrencia.usuario_responsavel
        
        tipo = request.POST.get('tipo')
        descricao = request.POST.get('descricao')
        data_ocorrencia = request.POST.get('data_ocorrencia')
        usuario_responsavel_id = request.POST.get('usuario_responsavel')
        status = request.POST.get('status')

        if tipo:
            ocorrencia.tipo = tipo
        if descricao is not None:
            ocorrencia.descricao = descricao
        if data_ocorrencia:
            ocorrencia.data_ocorrencia = data_ocorrencia
        if status in ['ABERTA', 'ENCERRADA']:
            ocorrencia.status = status
            if status == 'ENCERRADA' and not ocorrencia.data_encerramento:
                from datetime import date
                ocorrencia.data_encerramento = date.today()
            elif status == 'ABERTA':
                ocorrencia.data_encerramento = None

        if usuario_responsavel_id is not None:
            if usuario_responsavel_id != '':
                try:
                    ocorrencia.usuario_responsavel = User.objects.get(pk=usuario_responsavel_id)
                except User.DoesNotExist:
                    pass
            else:
                ocorrencia.usuario_responsavel = None

        ocorrencia.save()

        invalidar_cache_inbox(request.user)
        if usuario_antigo:
            invalidar_cache_inbox(usuario_antigo)
        if ocorrencia.usuario_responsavel:
            invalidar_cache_inbox(ocorrencia.usuario_responsavel)

        messages.success(request, 'Ocorrência atualizada com sucesso.')
    return redirect(request.META.get('HTTP_REFERER', 'metrologia:modulo_metrologia'))

@login_required
def deletar_ocorrencia(request, ocorrencia_id):
    from qms.models import OcorrenciaInstrumento
    from shared.inbox import invalidar_cache_inbox
    from django.shortcuts import redirect, get_object_or_404
    from django.contrib import messages

    if request.method == 'POST':
        ocorrencia = get_object_or_404(OcorrenciaInstrumento, pk=ocorrencia_id)
        usuario_antigo = ocorrencia.usuario_responsavel
        ocorrencia.delete()

        invalidar_cache_inbox(request.user)
        if usuario_antigo:
            invalidar_cache_inbox(usuario_antigo)

        messages.success(request, 'Ocorrência excluída com sucesso.')
    return redirect(request.META.get('HTTP_REFERER', 'metrologia:modulo_metrologia'))


@login_required
def relatorio_ocorrencias_view(request):
    """
    Relatório de Ocorrências e Tratativas por Setores.
    Permite filtrar, analisar, exportar para Excel e tratar diretamente com os setores
    atribuindo responsáveis e acompanhando status.
    """
    from qms.models import OcorrenciaInstrumento
    from metrologia.models import Instrumento
    from organization.models import Setor
    from django.contrib.auth.models import User
    from django.db.models import Q
    from datetime import datetime, date

    # Filtros
    setor_filtro = request.GET.get('setor', '').strip()
    status_filtro = request.GET.get('status', 'ABERTA').strip()
    tipo_filtro = request.GET.get('tipo', '').strip()
    responsavel_filtro = request.GET.get('responsavel', '').strip()
    data_inicio = request.GET.get('data_inicio', '').strip()
    data_fim = request.GET.get('data_fim', '').strip()
    search = request.GET.get('search', '').strip()
    ocorrencia_id = request.GET.get('ocorrencia_id', '').strip()
    formato = request.GET.get('formato', '').strip()

    qs = OcorrenciaInstrumento.objects.select_related(
        'instrumento',
        'instrumento__setor',
        'instrumento__categoria',
        'usuario_responsavel'
    ).order_by('-data_ocorrencia', '-id')

    if status_filtro and status_filtro != 'TODAS':
        qs = qs.filter(status=status_filtro)

    if setor_filtro:
        if setor_filtro == 'sem_setor':
            qs = qs.filter(instrumento__setor__isnull=True)
        elif setor_filtro.isdigit():
            qs = qs.filter(instrumento__setor_id=int(setor_filtro))

    if tipo_filtro:
        qs = qs.filter(tipo=tipo_filtro)

    if responsavel_filtro:
        if responsavel_filtro == 'sem_responsavel':
            qs = qs.filter(usuario_responsavel__isnull=True)
        elif responsavel_filtro == 'meus':
            qs = qs.filter(usuario_responsavel=request.user)
        elif responsavel_filtro.isdigit():
            qs = qs.filter(usuario_responsavel_id=int(responsavel_filtro))

    if data_inicio:
        try:
            dt_ini = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            qs = qs.filter(data_ocorrencia__gte=dt_ini)
        except ValueError:
            pass

    if data_fim:
        try:
            dt_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
            qs = qs.filter(data_ocorrencia__lte=dt_fim)
        except ValueError:
            pass

    if search:
        qs = qs.filter(
            Q(instrumento__tag__icontains=search) |
            Q(instrumento__codigo__icontains=search) |
            Q(instrumento__descricao__icontains=search) |
            Q(descricao__icontains=search) |
            Q(usuario_responsavel__first_name__icontains=search) |
            Q(usuario_responsavel__username__icontains=search)
        )

    # Exportação Excel
    if formato == 'excel':
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from django.http import HttpResponse

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Ocorrências e Tratativas"

        headers = [
            "ID", "Tag Instrumento", "Descrição Instrumento", "Setor",
            "Tipo", "Data Ocorrência", "Status", "Data Encerramento",
            "Responsável Tratativa", "Descrição / Desvio"
        ]

        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        alignment_center = Alignment(horizontal="center", vertical="center")
        border_thin = Border(
            left=Side(style="thin", color="E2E8F0"),
            right=Side(style="thin", color="E2E8F0"),
            top=Side(style="thin", color="E2E8F0"),
            bottom=Side(style="thin", color="E2E8F0")
        )

        ws.append(headers)
        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_num)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = alignment_center

        for oc in qs:
            inst = oc.instrumento
            inst_tag = inst.tag if inst else "N/A"
            inst_desc = inst.descricao if inst else "-"
            setor_nome = inst.setor.nome if (inst and inst.setor) else "Sem Setor"
            tipo_display = oc.get_tipo_display() if hasattr(oc, 'get_tipo_display') else oc.tipo
            resp_nome = oc.usuario_responsavel.get_full_name() or oc.usuario_responsavel.username if oc.usuario_responsavel else "Não atribuído"
            data_oc_str = oc.data_ocorrencia.strftime('%d/%m/%Y') if oc.data_ocorrencia else "-"
            data_enc_str = oc.data_encerramento.strftime('%d/%m/%Y') if oc.data_encerramento else "-"

            row = [
                oc.id,
                inst_tag,
                inst_desc,
                setor_nome,
                tipo_display,
                data_oc_str,
                oc.status,
                data_enc_str,
                resp_nome,
                oc.descricao
            ]
            ws.append(row)

        for row_cells in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=len(headers)):
            for cell in row_cells:
                cell.border = border_thin
                cell.alignment = Alignment(vertical="center")

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f'attachment; filename="relatorio_ocorrencias_{date.today().strftime("%Y%m%d")}.xlsx"'
        wb.save(response)
        return response

    # Estatísticas Globais
    total_ocorrencias = OcorrenciaInstrumento.objects.count()
    total_abertas = OcorrenciaInstrumento.objects.filter(status='ABERTA').count()
    total_encerradas = OcorrenciaInstrumento.objects.filter(status='ENCERRADA').count()
    sem_responsavel_count = OcorrenciaInstrumento.objects.filter(status='ABERTA', usuario_responsavel__isnull=True).count()
    minhas_tratativas_count = OcorrenciaInstrumento.objects.filter(status='ABERTA', usuario_responsavel=request.user).count()

    # Agrupamento por Setores para Tratativa Direta
    todos_setores = list(Setor.objects.all().order_by('nome'))

    ocorrencias_por_setor_map = {}
    for oc in qs:
        setor_obj = oc.instrumento.setor if (oc.instrumento and oc.instrumento.setor) else None
        setor_key = setor_obj.id if setor_obj else 0
        if setor_key not in ocorrencias_por_setor_map:
            ocorrencias_por_setor_map[setor_key] = {
                'setor': setor_obj,
                'nome': setor_obj.nome if setor_obj else "Sem Setor Definido",
                'ocorrencias': [],
                'total': 0,
                'abertas': 0,
                'encerradas': 0,
                'sem_responsavel': 0,
            }
        ocorrencias_por_setor_map[setor_key]['ocorrencias'].append(oc)
        ocorrencias_por_setor_map[setor_key]['total'] += 1
        if oc.status == 'ABERTA':
            ocorrencias_por_setor_map[setor_key]['abertas'] += 1
            if not oc.usuario_responsavel:
                ocorrencias_por_setor_map[setor_key]['sem_responsavel'] += 1
        else:
            ocorrencias_por_setor_map[setor_key]['encerradas'] += 1

    setores_dados = list(ocorrencias_por_setor_map.values())
    setores_dados.sort(key=lambda s: (-s['abertas'], -s['total'], s['nome']))

    usuarios_responsaveis = User.objects.filter(is_active=True).select_related('colaborador', 'colaborador__setor').order_by('first_name', 'username')
    todos_instrumentos = Instrumento.objects.filter(ativo=True).select_related('setor').order_by('tag')

    context = {
        'ocorrencias': qs,
        'setores_dados': setores_dados,
        'todos_setores': todos_setores,
        'todos_instrumentos': todos_instrumentos,
        'usuarios_responsaveis': usuarios_responsaveis,
        'tipos_ocorrencia': OcorrenciaInstrumento.TIPO_OCORRENCIA,
        'status_filtro': status_filtro,
        'setor_filtro': setor_filtro,
        'tipo_filtro': tipo_filtro,
        'responsavel_filtro': responsavel_filtro,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'search': search,
        'ocorrencia_id_foco': ocorrencia_id,
        'total_ocorrencias': total_ocorrencias,
        'total_abertas': total_abertas,
        'total_encerradas': total_encerradas,
        'sem_responsavel_count': sem_responsavel_count,
        'minhas_tratativas_count': minhas_tratativas_count,
        'hoje': date.today(),
    }
    return render(request, 'metrologia/relatorio_ocorrencias.html', context)
@login_required
def salvar_edicao_historico_modal_view(request, historico_id):
    """Atualiza o histórico e as medições por faixa diretamente pelo modal pop-up."""
    from decimal import Decimal
    hist = get_object_or_404(HistoricoCalibracao, id=historico_id)
    inst = hist.instrumento

    if request.method == 'POST':
        try:
            # 1. Atualizar campos básicos do histórico
            if 'data_calibracao' in request.POST and request.POST.get('data_calibracao'):
                hist.data_calibracao = request.POST.get('data_calibracao')
            if 'proxima_calibracao' in request.POST and request.POST.get('proxima_calibracao'):
                hist.proxima_calibracao = request.POST.get('proxima_calibracao')
            if 'numero_certificado' in request.POST:
                hist.numero_certificado = request.POST.get('numero_certificado', '').strip() or "S/N"
            if 'tipo_calibracao' in request.POST:
                hist.tipo_calibracao = request.POST.get('tipo_calibracao')
            if 'fornecedor' in request.POST:
                hist.fornecedor = request.POST.get('fornecedor', '').strip()
            if 'responsavel' in request.POST:
                hist.responsavel = request.POST.get('responsavel', '').strip()
            
            hist.tem_selo_rbc = ('tem_selo_rbc' in request.POST)
            
            if 'observacoes' in request.POST:
                hist.observacoes = request.POST.get('observacoes', '').strip()
            
            if 'link_certificado' in request.POST:
                hist.link_certificado = request.POST.get('link_certificado', '').strip() or None
            
            # Anexar novo certificado se enviado
            if 'certificado' in request.FILES:
                hist.certificado = request.FILES['certificado']

            hist.save()

            # 2. Atualizar Erro e Incerteza para cada ResultadoFaixaCalibracao
            faixas_inst = list(inst.faixas.all().order_by('valor_minimo')) if inst else []
            if faixas_inst:
                faixas_existentes = set(hist.resultados_faixa.values_list('faixa_id', flat=True))
                for f in faixas_inst:
                    if f.id not in faixas_existentes:
                        ResultadoFaixaCalibracao.objects.get_or_create(
                            historico=hist,
                            faixa=f,
                            defaults={
                                'valor_minimo': f.valor_minimo,
                                'valor_maximo': f.valor_maximo,
                                'nominal': f.nominal,
                                'tolerancia': f.tolerancia_mais_menos,
                            }
                        )

            resultados_faixa = hist.resultados_faixa.all()
            for rf in resultados_faixa:
                erro_val_str = request.POST.get(f'erro_faixa_{rf.id}', '').strip().replace(',', '.')
                inc_val_str = request.POST.get(f'incerteza_faixa_{rf.id}', '').strip().replace(',', '.')
                
                try:
                    erro_decimal = Decimal(erro_val_str) if erro_val_str != '' else None
                except Exception:
                    erro_decimal = None

                try:
                    inc_decimal = Decimal(inc_val_str) if inc_val_str != '' else None
                except Exception:
                    inc_decimal = None

                rf.erro = erro_decimal
                rf.incerteza = inc_decimal
                rf.save() # Dispara auto-cálculo de EMA, EME e resultado da faixa

            # 3. Recalcular resultado geral do Histórico
            resultados_list = list(hist.resultados_faixa.values_list('resultado', flat=True))
            if resultados_list:
                if 'REPROVADO' in resultados_list:
                    hist.resultado = 'REPROVADO'
                elif 'APROVADO_COM_CORRECAO' in resultados_list:
                    hist.resultado = 'APROVADO_COM_CORRECAO'
                else:
                    hist.resultado = 'APROVADO_SEM_CORRECAO'
                hist.save(update_fields=['resultado'])

            messages.success(request, f"✓ Certificado / Histórico {hist.numero_certificado} atualizado com sucesso!")
        except Exception as e:
            logger.error(f"Erro ao salvar edição do histórico {historico_id}: {e}")
            messages.error(request, f"Erro ao atualizar histórico: {e}")

    return redirect('detalhe_instrumento', instrumento_id=inst.id if inst else 1)


def get_metrologia_dashboard_data():
    """Agrega e pré-calcula todos os indicadores e instrumentos do dashboard de metrologia.
    
    Otimizado para evitar N+1 queries no Neon.tech.
    """
    from datetime import date, timedelta
    from django.urls import reverse
    from django.db.models import Prefetch
    from metrologia.models import Instrumento, SolicitacaoCotacao
    from qms.models import OcorrenciaInstrumento, SolicitacaoInstrumento

    hoje = date.today()
    trinta_dias = hoje + timedelta(days=30)
    
    ocorrencias_abertas_prefetch = Prefetch(
        'ocorrencias',
        queryset=OcorrenciaInstrumento.objects.filter(status='ABERTA').select_related('usuario_responsavel'),
        to_attr='ocorrencias_abertas'
    )
    
    instrumentos_qs = (
        Instrumento.objects.filter(ativo=True)
        .select_related('categoria', 'setor', 'responsavel')
        .prefetch_related(ocorrencias_abertas_prefetch)
    )
    
    instrumentos_list = []
    
    # Contadores TODOS
    total_instrumentos = 0
    vencidos_total = 0
    avencer_total = 0
    ocorrencias_total = 0
    em_dia_total = 0
    
    # Contadores EXTERNO
    vencidos_externo = 0
    avencer_externo = 0
    
    # Contadores INTERNO
    vencidos_interno = 0
    avencer_interno = 0
    fila_laboratorio_interno = 0
    ocorrencias_interno = 0
    
    for inst in instrumentos_qs:
        total_instrumentos += 1
        
        # Tratativa e Ação
        tratativa = (inst.tratativa_calibracao or (inst.categoria.tratativa_calibracao if inst.categoria else '') or 'INTERNA').upper()
        is_internal = tratativa != 'EXTERNA'
        
        acao = (inst.acao or (inst.categoria.acao if inst.categoria else '') or 'CALIBRACAO').upper()
        
        # Ocorrências abertas
        abertas = getattr(inst, 'ocorrencias_abertas', [])
        has_active_occurrence = len(abertas) > 0
        if has_active_occurrence:
            ocorrencias_total += len(abertas)
            if is_internal:
                ocorrencias_interno += len(abertas)
        
        # Status de Calibração
        prox_data = inst.data_proxima_calibracao
        status_situacao = 'EM_DIA'
        dias_para_vencer = None
        
        if prox_data:
            dias_para_vencer = (prox_data - hoje).days
            if prox_data < hoje:
                status_situacao = 'VENCIDO'
                vencidos_total += 1
                if is_internal:
                    vencidos_interno += 1
                    fila_laboratorio_interno += 1
                else:
                    vencidos_externo += 1
            elif prox_data <= trinta_dias:
                status_situacao = 'AVENCER_30'
                avencer_total += 1
                if is_internal:
                    avencer_interno += 1
                    fila_laboratorio_interno += 1
                else:
                    avencer_externo += 1
            else:
                em_dia_total += 1
        else:
            em_dia_total += 1
            
        try:
            url_detalhes = reverse('detalhe_instrumento', args=[inst.id])
        except Exception:
            try:
                url_detalhes = reverse('visualizar_instrumento', args=[inst.id])
            except Exception:
                url_detalhes = f'/metrologia/instrumento/{inst.id}/'
            
        # Situação detalhada
        sessenta_dias = hoje + timedelta(days=60)
        noventa_dias = hoje + timedelta(days=90)
        centovinte_dias = hoje + timedelta(days=120)
        situacao_detalhada = 'EM_DIA'
        if prox_data:
            if prox_data < hoje:
                situacao_detalhada = 'VENCIDO'
            elif prox_data <= trinta_dias:
                situacao_detalhada = 'AVENCER_30'
            elif prox_data <= sessenta_dias:
                situacao_detalhada = 'AVENCER_60'
            elif prox_data <= noventa_dias:
                situacao_detalhada = 'AVENCER_90'
            elif prox_data <= centovinte_dias:
                situacao_detalhada = 'AVENCER_120'

        periodos_set = set()
        meses_pt = {'01':'Jan', '02':'Fev', '03':'Mar', '04':'Abr', '05':'Mai', '06':'Jun', '07':'Jul', '08':'Ago', '09':'Set', '10':'Out', '11':'Nov', '12':'Dez'}
        if prox_data:
            periodos_set.add(prox_data.strftime('%Y-%m'))
            mes_ano_prox = f"{meses_pt.get(prox_data.strftime('%m'), '')}/{prox_data.strftime('%Y')}"
        else:
            mes_ano_prox = '-'

        instrumentos_list.append({
            'id': inst.id,
            'tag': inst.tag,
            'codigo': inst.codigo or '',
            'descricao': inst.descricao,
            'fabricante': inst.fabricante or '',
            'modelo': inst.modelo or '',
            'setor_nome': inst.setor.nome if inst.setor else '-',
            'setor_id': inst.setor_id,
            'categoria_nome': inst.categoria.nome if inst.categoria else '-',
            'categoria_id': inst.categoria_id,
            'tratativa': tratativa,
            'is_internal': is_internal,
            'activity_type': acao,
            'frequencia': getattr(inst, 'frequencia_meses', 12) or 12,
            'ativo': getattr(inst, 'ativo', True),
            'resultado_ultima_calibracao': getattr(inst, 'resultado_ultima_calibracao', 'APROVADO') or 'APROVADO',
            'data_proxima_calibracao': prox_data.strftime('%Y-%m-%d') if prox_data else None,
            'data_proxima_calibracao_display': prox_data.strftime('%d/%m/%Y') if prox_data else '-',
            'mes_ano_proxima_calibracao': mes_ano_prox,
            'periodo': prox_data.strftime('%Y-%m') if prox_data else '',
            'data_ultima_calibracao_display': inst.data_ultima_calibracao.strftime('%d/%m/%Y') if inst.data_ultima_calibracao else '-',
            'dias_para_vencer': dias_para_vencer,
            'status_situacao': status_situacao,
            'situacao_detalhada': situacao_detalhada,
            'has_active_occurrence': has_active_occurrence,
            'ocorrencias_count': len(abertas),
            'ocorrencias_tipos': [o.tipo for o in abertas],
            'ocorrencias_detalhes': [
                {
                    'id': o.id,
                    'tipo': o.tipo,
                    'tipo_display': o.get_tipo_display() if hasattr(o, 'get_tipo_display') else o.tipo,
                    'data_ocorrencia': o.data_ocorrencia.strftime('%d/%m/%Y') if o.data_ocorrencia else '-',
                    'descricao': o.descricao,
                    'usuario_responsavel_id': o.usuario_responsavel_id,
                    'usuario_responsavel_nome': (o.usuario_responsavel.get_full_name() or o.usuario_responsavel.username) if o.usuario_responsavel else None,
                }
                for o in abertas
            ],
            'url_detalhes': url_detalhes,
        })

    # Periodos filtro logic
    periodos_set = set()
    meses_pt = {'01':'Jan', '02':'Fev', '03':'Mar', '04':'Abr', '05':'Mai', '06':'Jun', '07':'Jul', '08':'Ago', '09':'Set', '10':'Out', '11':'Nov', '12':'Dez'}
    for inst_dict in instrumentos_list:
        if inst_dict.get('periodo'):
            periodos_set.add(inst_dict['periodo'])

    periodos_filtro = []
    for p in sorted(list(periodos_set)):
        ano, mes = p.split('-')
        label = f"{meses_pt.get(mes, mes)}/{ano}"
        periodos_filtro.append({'value': p, 'label': label})

    # Fornecedores, Categorias e Setores para Modais e Filtros
    try:
        from fornecedores.models import Fornecedor
        fornecedores_list = list(Fornecedor.objects.filter(ativo=True).order_by('nome'))
    except Exception:
        try:
            from fornecedores.models import Fornecedor
            fornecedores_list = list(Fornecedor.objects.all().order_by('nome'))
        except Exception:
            fornecedores_list = []

    try:
        from metrologia.models import CategoriaInstrumento
        from django.db.models.functions import Lower
        categorias_list = list(CategoriaInstrumento.objects.all().order_by(Lower('nome')))
    except Exception:
        try:
            from metrologia.models import CategoriaInstrumento
            categorias_list = list(CategoriaInstrumento.objects.all().order_by('nome'))
        except Exception:
            categorias_list = []

    if not categorias_list:
        cat_map = {}
        for inst in instrumentos_qs:
            if inst.categoria_id and inst.categoria:
                cat_map[inst.categoria_id] = inst.categoria.nome
        categorias_list = [{'id': k, 'nome': v} for k, v in sorted(cat_map.items(), key=lambda x: str(x[1]).lower())]

    try:
        from organization.models import Setor
        from django.db.models.functions import Lower
        setores_list = list(Setor.objects.all().order_by(Lower('nome')))
    except Exception:
        try:
            from organization.models import Setor
            setores_list = list(Setor.objects.all().order_by('nome'))
        except Exception:
            setores_list = []

    if not setores_list:
        set_map = {}
        for inst in instrumentos_qs:
            if inst.setor_id and inst.setor:
                set_map[inst.setor_id] = inst.setor.nome
        setores_list = [{'id': k, 'nome': v} for k, v in sorted(set_map.items(), key=lambda x: str(x[1]).lower())]

    # Cotações Abertas e Equipamentos no Fornecedor
    cotacoes_abertas = SolicitacaoCotacao.objects.filter(status='ABERTA').count()
    solicitacoes_cotacao_recentes = list(
        SolicitacaoCotacao.objects.filter(status='ABERTA')
        .select_related('responsavel')
        .order_by('-data_criacao')[:10]
    )
    
    # Orçamentos Pendentes / Equipamentos em Fornecedor (Itens de cotação em andamento)
    orcamentos_pendentes = SolicitacaoCotacao.objects.exclude(status__in=['CONCLUIDA', 'CANCELADA']).count()
    
    # Solicitações pendentes QMS
    qtd_solicitacoes_qms = SolicitacaoInstrumento.objects.filter(status='PENDENTE').count()
    
    # Ordenar instrumentos: primeiro os críticos (VENCIDOS, depois AVENCER_30, depois com ocorrência)
    def sort_key(item):
        peso_status = 0 if item['status_situacao'] == 'VENCIDO' else (1 if item['status_situacao'] == 'AVENCER_30' else 2)
        dias = item['dias_para_vencer'] if item['dias_para_vencer'] is not None else 9999
        return (peso_status, dias, 0 if item['has_active_occurrence'] else 1)
        
    instrumentos_list.sort(key=sort_key)
    
    kpis = {
        'todos': {
            'vencidos': vencidos_total,
            'avencer_30': avencer_total,
            'ocorrencias_ativas': ocorrencias_total,
            'total_instrumentos': total_instrumentos,
            'em_dia': em_dia_total,
        },
        'externo': {
            'vencidos': vencidos_externo,
            'avencer_30': avencer_externo,
            'cotacoes_abertas': cotacoes_abertas,
            'orcamentos_pendentes': orcamentos_pendentes,
            'necessitam_cotacao': vencidos_externo + avencer_externo,
        },
        'interno': {
            'vencidos': vencidos_interno,
            'avencer_30': avencer_interno,
            'fila_laboratorio': fila_laboratorio_interno,
            'ocorrencias_ativas': ocorrencias_interno,
        }
    }
    
    from django.contrib.auth.models import User
    usuarios_responsaveis = list(User.objects.filter(is_active=True).select_related('colaborador', 'colaborador__setor').order_by('first_name', 'username'))

    return {
        'kpis': kpis,
        'instrumentos': instrumentos_list,
        'solicitacoes_cotacao': solicitacoes_cotacao_recentes,
        'qtd_solicitacoes_qms': qtd_solicitacoes_qms,
        'fornecedores': fornecedores_list,
        'categorias': categorias_list,
        'setores': setores_list,
        'categorias_filtro': categorias_list,
        'setores_filtro': setores_list,
        'periodos_filtro': periodos_filtro,
        'usuarios_responsaveis': usuarios_responsaveis,
        'hoje': hoje.strftime('%Y-%m-%d'),
        'hoje_display': hoje.strftime('%d/%m/%Y'),
    }


@login_required
def api_dashboard_overview(request):
    """Endpoint REST JSON para o dashboard interativo de metrologia (React / Next.js / API)."""
    data = get_metrologia_dashboard_data()
    # Converte solicitacoes_cotacao objects para dict serializável
    solicitacoes_json = []
    for s in data['solicitacoes_cotacao']:
        solicitacoes_json.append({
            'id': s.id,
            'numero_solicitacao': getattr(s, 'numero_solicitacao', f"SOL-{s.id}"),
            'data_criacao': s.data_criacao.strftime('%d/%m/%Y') if getattr(s, 'data_criacao', None) else '-',
            'data_solicitacao_orcamento': s.data_solicitacao_orcamento.strftime('%d/%m/%Y') if getattr(s, 'data_solicitacao_orcamento', None) else '-',
            'status': s.status,
            'responsavel': s.responsavel.username if getattr(s, 'responsavel', None) else 'Não atribuído',
        })
    data['solicitacoes_cotacao'] = solicitacoes_json
    return JsonResponse(data, safe=False)


