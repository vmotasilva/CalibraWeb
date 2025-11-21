import pandas as pd
import io
import zipfile
import os
import re
from datetime import datetime, date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError, models
from django.urls import reverse
from django.db.models import Q
from django.core.files.base import ContentFile

from .models import (
    Instrumento, Colaborador, ProcessoCotacao, Procedimento,
    Fornecedor, HistoricoCalibracao, Setor, CentroCusto,
    RegistroTreinamento, Ferias, Ocorrencia, HierarquiaSetor
)
from .forms import (
    CarimboForm, ImportacaoInstrumentosForm, ImportacaoColaboradoresForm, 
    ImportacaoProcedimentosForm, ImportacaoHierarquiaForm, ImportacaoHistoricoForm
)
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color as RColor

def get_colab(request):
    """Retorna o colaborador logado ou None."""
    try: return Colaborador.objects.get(user_django=request.user)
    except: return None

def excel_date_to_datetime(serial):
    if pd.isnull(serial) or str(serial).strip() == '' or str(serial).strip() == '-': return None
    try:
        serial_str = str(serial).strip()
        if '/' in serial_str: return pd.to_datetime(serial_str, dayfirst=True).date()
        serial_float = float(serial)
        return (datetime(1899, 12, 30) + timedelta(days=serial_float)).date()
    except: return None

@login_required
def dashboard_view(request):
    colab = get_colab(request); nome_display = colab.nome_completo if colab else request.user.username; hoje = date.today(); trinta_dias = hoje + timedelta(days=30)
    qtd_vencidos = Instrumento.objects.filter(Q(data01_prox_calibracao__lt=hoje) | Q(data02_prox_calibracao__lt=hoje), status='Ativo').count()
    qtd_avencer = Instrumento.objects.filter((Q(data01_prox_calibracao__range=[hoje, trinta_dias]) | Q(data02_prox_calibracao__range=[hoje, trinta_dias])), status='Ativo').count()
    lista_urgentes = Instrumento.objects.filter(data01_prox_calibracao__lte=trinta_dias, status='Ativo').order_by('data01_prox_calibracao')[:5]
    ctx = {'colaborador': colab, 'nome_display': nome_display, 'qtd_vencidos': qtd_vencidos, 'qtd_avencer': qtd_avencer, 'lista_urgentes': lista_urgentes, 'qtd_cotacoes': ProcessoCotacao.objects.filter(status='ABERTO').count(), 'today': hoje}
    return render(request, 'dashboard.html', ctx)

@login_required
def modulo_metrologia_view(request):
    colab = get_colab(request); ctx = {'colaborador': colab, 'instrumentos': Instrumento.objects.all().order_by('codigo'), 'can_edit': True}
    return render(request, 'modulo_metrologia.html', ctx)

@login_required
def modulo_rh_view(request):
    colab = get_colab(request); ctx = {'colaborador': colab, 'funcionarios': Colaborador.objects.all().order_by('nome_completo'), 'can_edit': True}
    return render(request, 'modulo_rh.html', ctx)

@login_required
def detalhe_instrumento_view(request, instrumento_id):
    inst = get_object_or_404(Instrumento, id=instrumento_id)
    historico = inst.historico_calibracoes.all().order_by('-data_calibracao')
    return render(request, 'detalhe_instrumento.html', {'colaborador': get_colab(request), 'instrumento': inst, 'historico': historico, 'today': date.today()})

@login_required
def carimbar_view(request):
    colab = get_colab(request)
    instrumentos_disponiveis = Instrumento.objects.filter(status='Ativo').order_by('codigo')
    
    # Pega nome do usuário logado
    user_full_name = f"{request.user.first_name} {request.user.last_name}".strip()
    if not user_full_name: user_full_name = request.user.username.upper()
    
    if request.method == 'POST':
        form = CarimboForm(request.POST, request.FILES)
        if form.is_valid():
            c_resp = colab 
            dt_validacao = form.cleaned_data['data_validacao']
            status_txt = form.cleaned_data['status_validacao']
            
            # Mapeamento exato do status
            resultado_banco = 'APROVADO'
            if status_txt == 'Reprovado':
                resultado_banco = 'REPROVADO'
            elif status_txt == 'Aprovado com correções':
                resultado_banco = 'CONDICIONAL'
            else:
                resultado_banco = 'APROVADO' # Aprovado sem correções
            
            fs = request.FILES.getlist('arquivo_pdf')
            try: screen_w = float(request.POST.get('page_width', 0)); screen_h = float(request.POST.get('page_height', 0))
            except: screen_w = 0; screen_h = 0
            processed_files = []

            for i, f in enumerate(fs):
                raw_x = request.POST.get(f'x_{i}', 0); raw_y = request.POST.get(f'y_{i}', 0); raw_w = request.POST.get(f'w_{i}', 0); raw_h = request.POST.get(f'h_{i}', 0)
                ui = (float(raw_x), float(raw_y), float(raw_w), float(raw_h), screen_w, screen_h)

                # Passa nome do usuário para o carimbo
                pdf_buffer = apply_stamp_logic(f, user_full_name, status_txt, ui, dt_validacao)
                
                inst_id = request.POST.get(f'instrument_id_{i}')
                calib_date_str = request.POST.get(f'calib_date_{i}')
                cert_num = request.POST.get(f'cert_num_{i}', f.name)
                
                if inst_id and calib_date_str:
                    try:
                        instrumento = Instrumento.objects.get(id=inst_id)
                        dt_calibracao = datetime.strptime(calib_date_str, '%Y-%m-%d').date()
                        prox_calib = None
                        if instrumento.frequencia: dias = instrumento.frequencia * 30; prox_calib = dt_calibracao + timedelta(days=dias)
                        
                        hist, created = HistoricoCalibracao.objects.get_or_create(
                            instrumento=instrumento, data_calibracao=dt_calibracao, data_aprovacao=dt_validacao, numero_certificado=cert_num,
                            defaults={'proxima_calibracao': prox_calib, 'resultado': resultado_banco, 'responsavel': c_resp, 'observacoes': f"Validado por {user_full_name}: {status_txt}"}
                        )
                        if not created: hist.resultado = resultado_banco; hist.observacoes = f"Revalidado por {user_full_name}: {status_txt}"
                        
                        filename = f"Cert_{cert_num}_{instrumento.codigo}.pdf"
                        hist.certificado.save(filename, ContentFile(pdf_buffer.getvalue())); hist.save()
                        
                        if not instrumento.data01_ultima_calibracao or dt_calibracao >= instrumento.data01_ultima_calibracao:
                            instrumento.data01_ultima_calibracao = dt_calibracao; instrumento.data01_prox_calibracao = prox_calib
                            if resultado_banco == 'REPROVADO': instrumento.status = 'Manutenção'
                            elif resultado_banco in ['APROVADO', 'CONDICIONAL']: instrumento.status = 'Ativo'
                            instrumento.save()
                    except Exception as e: print(f"Erro: {e}")
                pdf_buffer.seek(0); processed_files.append((f.name, pdf_buffer))
            
            if len(processed_files) == 1: fname, fbuf = processed_files[0]; r = HttpResponse(fbuf, content_type='application/pdf'); r['Content-Disposition'] = f'attachment; filename="Validado_{fname}"'; return r
            elif len(processed_files) > 1: zb = io.BytesIO(); 
            with zipfile.ZipFile(zb, 'w') as zf:
                for fname, fbuf in processed_files: zf.writestr(f"Validado_{fname}", fbuf.getvalue())
            zb.seek(0); r = HttpResponse(zb, content_type='application/zip'); r['Content-Disposition'] = 'attachment; filename="Lote_Validados.zip"'; return r
    else: form = CarimboForm()
    return render(request, 'carimbo.html', {'form': form, 'colaborador': colab, 'user_full_name': user_full_name, 'instrumentos': instrumentos_disponiveis})

def apply_stamp_logic(f, user_name, status, ui, data_validacao):
    ipdf = PdfReader(f); o = PdfWriter()
    if len(ipdf.pages) > 0:
        p = ipdf.pages[0]
        try: pdf_w = float(p.mediabox.width); pdf_h = float(p.mediabox.height)
        except: pdf_w = 595.0; pdf_h = 842.0 
        screen_x, screen_y, screen_box_w, screen_box_h, screen_w, screen_h = ui
        if screen_w > 0 and screen_h > 0: scale_x = pdf_w / screen_w; scale_y = pdf_h / screen_h; final_x = screen_x * scale_x; final_y = pdf_h - (screen_y * scale_y) - (screen_box_h * scale_y)
        else: final_x = pdf_w - 150; final_y = 50
        b = io.BytesIO(); c = canvas.Canvas(b, pagesize=(pdf_w, pdf_h))
        
        if 'Reprovado' in status: main_color = RColor(0.8, 0, 0)
        else: main_color = RColor(0, 0.5, 0)
        
        c.setFillColor(main_color); c.setFont("Helvetica-Bold", 10); c.drawString(final_x, final_y + 20, status)
        c.setFillColor(RColor(0, 0, 0)); c.setFont("Helvetica", 9); c.drawString(final_x, final_y + 10, f"{data_validacao.strftime('%d/%m/%Y')}")
        c.drawString(final_x, final_y, f"{user_name}")
        c.save(); b.seek(0); st = PdfReader(b); p.merge_page(st.pages[0]); o.add_page(p)
        for pg in ipdf.pages[1:]: o.add_page(pg)
    out = io.BytesIO(); o.write(out); out.seek(0); return out

# ... (Funções de Template e Importação mantidas iguais) ...
def dl_template_instr(request):
    colunas = ["Código", "Equipamento", "Status", "Fabricante", "Modelo", "N° de Série", "Setor", "Localização/Area", "Frequencia", "Unidade 01", "Faixa 01", "Data 01 - Última Calibração", "Data 01 - Próxima Calibração", "Unidade 02", "Faixa 02", "Data 02 - Última Calibração", "Data 02 - Próxima Calibração"]
    df = pd.DataFrame(columns=colunas); r = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'); r['Content-Disposition'] = 'attachment; filename="template_instrumentos.xlsx"'; df.to_excel(r, index=False); return r
def dl_template_colab(request):
    df = pd.DataFrame({'MATRICULA':['100'], 'NOME':['TESTE'], 'CPF':['000'], 'CARGO':['Y'], 'GRUPO':['ADM'], 'SETOR':['ADM'], 'CC':['100'], 'TURNO':['ADM'], 'STATUS':['ATIVO']}); b = io.BytesIO(); df.to_excel(b, index=False); b.seek(0); r = HttpResponse(b, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'); r['Content-Disposition'] = 'attachment; filename="template_colaboradores.xlsx"'; return r
def dl_template_hierarquia(request):
    df = pd.DataFrame({'SETOR': ['MANUTENCAO'], 'TURNO': ['TURNO 1'], 'MAT_LIDER': ['1001'], 'MAT_SUPERVISOR': [''], 'MAT_GERENTE': [''], 'MAT_DIRETOR': ['']}); b = io.BytesIO(); df.to_excel(b, index=False); b.seek(0); r = HttpResponse(b, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'); r['Content-Disposition'] = 'attachment; filename="template_hierarquia.xlsx"'; return r
def dl_template_historico(request):
    colunas = ["CÓDIGO", "DATA CALIBRAÇÃO", "DATA APROVAÇÃO", "N CERTIFICADO", "RESULTADO (APROVADO/REPROVADO)", "OBSERVAÇÕES"]
    df = pd.DataFrame(columns=colunas); r = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'); r['Content-Disposition'] = 'attachment; filename="template_historico_calibracao.xlsx"'; df.to_excel(r, index=False); return r

@login_required
def imp_instr_view(request):
    if request.method == 'POST':
        form = ImportacaoInstrumentosForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                f = request.FILES['arquivo_excel']; df = pd.read_csv(f, sep=';', encoding='latin1') if f.name.endswith('.csv') else pd.read_excel(f); df.columns = df.columns.str.strip().str.upper(); count_new = 0; count_upd = 0
                with transaction.atomic():
                    for _, row in df.iterrows():
                        def get_val(k): 
                            for key in k:
                                if key.upper() in df.columns and pd.notna(row[key.upper()]): return str(row[k]).strip()
                            return None
                        def get_freq_meses(val):
                            if not val: return None
                            s = str(val).upper(); 
                            if 'ANUAL' in s: return 12
                            if 'SEMESTRAL' in s: return 6
                            if 'TRIMESTRAL' in s: return 3
                            if 'BIENAL' in s: return 24
                            try: return int(float(val))
                            except: return None
                        def get_date(k):
                            val = get_val(k); return pd.to_datetime(val).date() if val else None
                        
                        codigo = get_val(['CÓDIGO', 'CODIGO', 'TAG'])
                        if not codigo: continue
                        dados = {
                            'equipamento': get_val(['EQUIPAMENTO', 'DESCRIÇÃO', 'DESCRICAO']) or 'Sem Nome',
                            'status': get_val(['STATUS', 'SITUAÇÃO']) or 'Ativo',
                            'fabricante': get_val(['FABRICANTE', 'MARCA']), 'modelo': get_val(['MODELO']),
                            'numero_serie': get_val(['N° DE SÉRIE', 'N DE SERIE', 'SÉRIE']),
                            'setor': get_val(['SETOR', 'DEPARTAMENTO']), 'localizacao': get_val(['LOCALIZAÇÃO/AREA', 'LOCALIZACAO']),
                            'frequencia': get_freq_meses(get_val(['FREQUENCIA', 'PERIODICIDADE'])),
                            'unidade01': get_val(['UNIDADE 01']), 'faixa01': get_val(['FAIXA 01']),
                            'data01_ultima_calibracao': get_date(['DATA 01 - ÚLTIMA CALIBRAÇÃO', 'DATA ULTIMA']),
                            'data01_prox_calibracao': get_date(['DATA 01 - PRÓXIMA CALIBRAÇÃO', 'DATA PROXIMA']),
                            'unidade02': get_val(['UNIDADE 02']), 'faixa02': get_val(['FAIXA 02']),
                            'data02_ultima_calibracao': get_date(['DATA 02 - ÚLTIMA CALIBRAÇÃO']),
                            'data02_prox_calibracao': get_date(['DATA 02 - PRÓXIMA CALIBRAÇÃO']),
                        }
                        obj, created = Instrumento.objects.update_or_create(codigo=codigo, defaults=dados)
                        if created: count_new += 1
                        else: count_upd += 1
                messages.success(request, "Importação OK"); return redirect('modulo_metrologia')
            except Exception as e: messages.error(request, str(e)); return redirect('importar_instrumentos')
    else: form = ImportacaoInstrumentosForm()
    return render(request, 'importar_instrumentos.html', {'form': form, 'colaborador': get_colab(request)})

@login_required
def imp_colab_view(request):
    if request.method == 'POST':
        form = ImportacaoColaboradoresForm(request.POST, request.FILES)
        if form.is_valid(): messages.success(request, "Importação OK"); return redirect('modulo_rh')
    else: form = ImportacaoColaboradoresForm()
    return render(request, 'importar_colaboradores.html', {'form': form, 'colaborador': get_colab(request)})

@login_required
def imp_docs_view(request):
    if request.method == 'POST': messages.success(request, "Docs OK"); return redirect('modulo_metrologia')
    return render(request, 'importar_documentos.html', {'form': ImportacaoProcedimentosForm(), 'colaborador': get_colab(request)})

@login_required
def imp_hierarquia_view(request):
    if request.method == 'POST': messages.success(request, "Hierarquia OK"); return redirect('modulo_rh')
    return render(request, 'importar_hierarquia.html', {'form': ImportacaoHierarquiaForm(), 'colaborador': get_colab(request)})

@login_required
def imp_historico_view(request):
    if request.method == 'POST':
        form = ImportacaoHistoricoForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                f = request.FILES['arquivo_excel']; df = pd.read_excel(f); df.columns = df.columns.str.strip().str.upper(); count_new = 0
                with transaction.atomic():
                    for _, row in df.iterrows():
                        def get_val(k): return str(row[k]).strip() if k in df.columns and pd.notna(row[k]) else None
                        def get_date_val(k): return pd.to_datetime(row[k]).date() if k in df.columns and pd.notna(row[k]) else None
                        cod = get_val('CÓDIGO'); dt_cal = get_date_val('DATA CALIBRAÇÃO')
                        if not cod or not dt_cal: continue
                        try: inst = Instrumento.objects.get(codigo=cod)
                        except: continue
                        dt_apr = get_date_val('DATA APROVAÇÃO') or dt_cal; num_cert = get_val('N CERTIFICADO') or 'S/N'
                        
                        # CORREÇÃO NA IMPORTAÇÃO: Mapeia texto do Excel para o DB
                        res_raw = str(get_val('RESULTADO')).upper()
                        res = 'APROVADO'
                        if 'REPROVADO' in res_raw: res = 'REPROVADO'
                        elif 'CORRE' in res_raw or 'RESTRI' in res_raw: res = 'CONDICIONAL'
                        
                        prox = dt_cal + timedelta(days=inst.frequencia*30) if inst.frequencia else None
                        obj, cr = HistoricoCalibracao.objects.get_or_create(instrumento=inst, data_calibracao=dt_cal, data_aprovacao=dt_apr, numero_certificado=num_cert, defaults={'resultado': res, 'proxima_calibracao': prox, 'observacoes': get_val('OBSERVAÇÕES')})
                        if cr: count_new += 1
                        if not inst.data01_ultima_calibracao or dt_cal >= inst.data01_ultima_calibracao:
                            inst.data01_ultima_calibracao = dt_cal; inst.data01_prox_calibracao = prox; inst.save()
                messages.success(request, f"Importados: {count_new}"); return redirect('modulo_metrologia')
            except Exception as e: messages.error(request, str(e))
    else: form = ImportacaoHistoricoForm()
    return render(request, 'importar_historico.html', {'form': form, 'colaborador': get_colab(request)})