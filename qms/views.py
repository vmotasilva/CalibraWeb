import pandas as pd
import io
import zipfile
import os
import re
from datetime import datetime, date, timedelta
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError, models
from django.urls import reverse
from django.db.models import Q
from django.core.files.base import ContentFile

# IMPORTA TODOS OS MODELOS
from .models import (
    Instrumento, Colaborador, ProcessoCotacao, Procedimento,
    Fornecedor, HistoricoCalibracao, Setor, CentroCusto,
    RegistroTreinamento, Ferias, Ocorrencia, HierarquiaSetor,
    CategoriaInstrumento, UnidadeMedida, FaixaMedicao, Padrao
)
from .forms import (
    CarimboForm, ImportacaoInstrumentosForm, ImportacaoColaboradoresForm, 
    ImportacaoProcedimentosForm, ImportacaoHierarquiaForm, ImportacaoHistoricoForm,
    ImportacaoPadroesForm
)
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color as RColor

# --- FUNÇÕES AUXILIARES ---
def get_colab(request):
    try: return Colaborador.objects.get(user_django=request.user)
    except: return None

# --- VIEWS DE TELA ---

@login_required
def dashboard_view(request):
    colab = get_colab(request)
    nome_display = colab.nome_completo if colab else request.user.username
    hoje = date.today()
    trinta_dias = hoje + timedelta(days=30)
    qtd_vencidos = Instrumento.objects.filter(data_proxima_calibracao__lt=hoje, ativo=True).count()
    qtd_avencer = Instrumento.objects.filter(data_proxima_calibracao__range=[hoje, trinta_dias], ativo=True).count()
    lista_urgentes = Instrumento.objects.filter(data_proxima_calibracao__lte=trinta_dias, ativo=True).order_by('data_proxima_calibracao')[:5]
    
    ctx = {'colaborador': colab, 'nome_display': nome_display, 'qtd_vencidos': qtd_vencidos, 'qtd_avencer': qtd_avencer, 'lista_urgentes': lista_urgentes, 'qtd_cotacoes': ProcessoCotacao.objects.filter(status='ABERTO').count(), 'today': hoje}
    return render(request, 'dashboard.html', ctx)

@login_required
def modulo_metrologia_view(request):
    colab = get_colab(request)
    ctx = {
        'colaborador': colab, 
        'instrumentos': Instrumento.objects.all().order_by('tag'),
        'setores': Setor.objects.all().order_by('nome'),
        'categorias': CategoriaInstrumento.objects.all().order_by('nome'),
        'can_edit': True
    }
    return render(request, 'modulo_metrologia.html', ctx)

@login_required
def modulo_rh_view(request):
    colab = get_colab(request)
    ctx = {'colaborador': colab, 'funcionarios': Colaborador.objects.all().order_by('nome_completo'), 'can_edit': True}
    return render(request, 'modulo_rh.html', ctx)

@login_required
def detalhe_instrumento_view(request, instrumento_id):
    inst = get_object_or_404(Instrumento, id=instrumento_id)
    historico = inst.historico_calibracoes.all().order_by('-data_calibracao')
    faixas = inst.faixas.all()
    return render(request, 'detalhe_instrumento.html', {'colaborador': get_colab(request), 'instrumento': inst, 'historico': historico, 'faixas': faixas, 'today': date.today()})

@login_required
def remover_historico_view(request, historico_id):
    hist = get_object_or_404(HistoricoCalibracao, id=historico_id)
    instrumento_id = hist.instrumento.id
    if hist.certificado: hist.certificado.delete(save=False)
    hist.delete()
    messages.success(request, "Certificado removido.")
    return redirect('detalhe_instrumento', instrumento_id=instrumento_id)

# --- CARIMBO ---
@login_required
def carimbar_view(request):
    colab = get_colab(request)
    instrumentos_disponiveis = Instrumento.objects.filter(ativo=True).order_by('tag')
    user_full_name = f"{request.user.first_name} {request.user.last_name}".strip()
    if not user_full_name: user_full_name = request.user.username.upper()
    
    if request.method == 'POST':
        form = CarimboForm(request.POST, request.FILES)
        if form.is_valid():
            c_resp = colab; dt_validacao = form.cleaned_data['data_validacao']; status_txt = form.cleaned_data['status_validacao']
            is_rbc = form.cleaned_data.get('is_rbc', False)
            padroes_selecionados = form.cleaned_data.get('padroes', [])
            
            resultado_banco = 'APROVADO'
            if status_txt == 'Reprovado': resultado_banco = 'REPROVADO'
            elif status_txt == 'Aprovado com correções': resultado_banco = 'CONDICIONAL'
            
            fs = request.FILES.getlist('arquivo_pdf'); processed_files = []
            try: screen_w = float(request.POST.get('page_width', 0)); screen_h = float(request.POST.get('page_height', 0))
            except: screen_w = 0; screen_h = 0

            for i, f in enumerate(fs):
                raw_x = request.POST.get(f'x_{i}', 0); raw_y = request.POST.get(f'y_{i}', 0); raw_w = request.POST.get(f'w_{i}', 0); raw_h = request.POST.get(f'h_{i}', 0)
                ui = (float(raw_x), float(raw_y), float(raw_w), float(raw_h), screen_w, screen_h)
                pdf_buffer = apply_stamp_logic(f, user_full_name, status_txt, ui, dt_validacao)
                inst_id = request.POST.get(f'instrument_id_{i}'); calib_date_str = request.POST.get(f'calib_date_{i}'); cert_num = request.POST.get(f'cert_num_{i}', f.name)
                
                if inst_id and calib_date_str:
                    try:
                        instrumento = Instrumento.objects.get(id=inst_id)
                        dt_calibracao = datetime.strptime(calib_date_str, '%Y-%m-%d').date()
                        prox_calib = None
                        if instrumento.frequencia_meses: prox_calib = dt_calibracao + timedelta(days=instrumento.frequencia_meses*30)
                        
                        hist, created = HistoricoCalibracao.objects.get_or_create(
                            instrumento=instrumento, data_calibracao=dt_calibracao, numero_certificado=cert_num,
                            defaults={
                                'proxima_calibracao': prox_calib, 'resultado': resultado_banco, 
                                'responsavel': str(c_resp), 'observacoes': f"Validado por {user_full_name}: {status_txt}",
                                'tem_selo_rbc': is_rbc, 'tipo_calibracao': 'EXTERNA'
                            }
                        )
                        if not created: hist.resultado = resultado_banco; hist.observacoes = f"Revalidado: {status_txt}"
                        if not is_rbc and padroes_selecionados: hist.padroes_utilizados.set(padroes_selecionados)
                        filename = f"Cert_{cert_num}_{instrumento.tag}.pdf"; hist.certificado.save(filename, ContentFile(pdf_buffer.getvalue())); hist.save()
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

# --- TEMPLATES DE DOWNLOAD ---
def dl_template_instr(request):
    colunas = ["TAG", "EQUIPAMENTO", "STATUS", "FABRICANTE", "MODELO", "N SERIE", "SETOR", "LOCALIZACAO", "FREQUENCIA_MESES", "DATA_ULTIMA_CALIBRACAO", "FAIXA", "UNIDADE"]
    df = pd.DataFrame(columns=colunas)
    r = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'); r['Content-Disposition'] = 'attachment; filename="template_instrumentos_v2.xlsx"'; df.to_excel(r, index=False); return r
def dl_template_colab(request):
    df = pd.DataFrame({'MATRICULA':['100'], 'NOME':['TESTE'], 'CPF':['000'], 'CARGO':['Y'], 'GRUPO':['ADM'], 'SETOR':['ADM'], 'CC':['100'], 'TURNO':['ADM'], 'STATUS':['ATIVO']}); b = io.BytesIO(); df.to_excel(b, index=False); b.seek(0); r = HttpResponse(b, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'); r['Content-Disposition'] = 'attachment; filename="template_colaboradores.xlsx"'; return r
def dl_template_hierarquia(request):
    df = pd.DataFrame({'SETOR': ['MANUTENCAO'], 'TURNO': ['TURNO 1'], 'MAT_LIDER': ['1001'], 'MAT_SUPERVISOR': [''], 'MAT_GERENTE': [''], 'MAT_DIRETOR': ['']}); b = io.BytesIO(); df.to_excel(b, index=False); b.seek(0); r = HttpResponse(b, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'); r['Content-Disposition'] = 'attachment; filename="template_hierarquia.xlsx"'; return r
def dl_template_historico(request):
    colunas = ["TAG", "DATA CALIBRAÇÃO", "DATA APROVAÇÃO", "N CERTIFICADO", "ERRO ENCONTRADO", "INCERTEZA", "TOLERANCIA PROCESSO (+/-)", "RBC (SIM/NAO)", "RESULTADO", "FORNECEDOR", "RESPONSÁVEL", "OBSERVAÇÕES"]
    df = pd.DataFrame(columns=colunas); r = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'); r['Content-Disposition'] = 'attachment; filename="template_historico_calibracao.xlsx"'; df.to_excel(r, index=False); return r

# --- IMPORTAÇÕES ---

@login_required
def imp_instr_view(request):
    if request.method == 'POST':
        form = ImportacaoInstrumentosForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                f = request.FILES['arquivo_excel']
                try: df = pd.read_csv(f, sep=None, engine='python', encoding='latin1')
                except: f.seek(0); df = pd.read_csv(f, sep=None, engine='python', encoding='utf-8') if f.name.endswith('.csv') else pd.read_excel(f)
                df.columns = df.columns.str.strip().str.upper()
                count_new = 0; count_upd = 0; count_faixas = 0
                with transaction.atomic():
                    for _, row in df.iterrows():
                        def get_val(k_list): 
                            for key in k_list:
                                if key in df.columns and pd.notna(row[key]): return str(row[key]).strip()
                            return None
                        def get_date(k_list):
                            val = get_val(k_list)
                            if not val or val == '-' or val == 'NaT': return None
                            try: return pd.to_datetime(val, dayfirst=True).date()
                            except: return None
                        def traduzir_frequencia(valor):
                            if not valor: return 12
                            s = str(valor).upper().replace(',', '.')
                            numeros = re.findall(r'\d+', s)
                            if numeros: return int(numeros[0])
                            try: return int(float(valor))
                            except: return 12
                        def extrair_min_max(texto_faixa):
                            if not texto_faixa: return 0, 0
                            txt = str(texto_faixa).replace(',', '.')
                            numeros = re.findall(r'-?\d+\.?\d*', txt)
                            if len(numeros) >= 2: return float(numeros[0]), float(numeros[1])
                            elif len(numeros) == 1: return 0, float(numeros[0])
                            return 0, 0

                        tag = get_val(['TAG', 'IDENTIFICACAO', 'CODIGO', 'CÓDIGO'])
                        if not tag: continue 
                        cat_nome = get_val(['CATEGORIA', 'FAMILIA', 'TIPO', 'EQUIPAMENTO']) 
                        if cat_nome: cat, _ = CategoriaInstrumento.objects.get_or_create(nome=cat_nome.title())
                        else: cat = None
                        setor_nome = get_val(['SETOR', 'DEPARTAMENTO'])
                        if setor_nome: setor, _ = Setor.objects.get_or_create(nome=setor_nome.upper())
                        else: setor = None
                        freq_meses = traduzir_frequencia(get_val(['FREQUENCIA_MESES', 'FREQUENCIA', 'PERIODICIDADE']))
                        dt_ultima = get_date(['DATA_ULTIMA_CALIBRACAO', 'DATA ÚLTIMA CALIBRAÇÃO', 'ULTIMA CALIBRACAO', 'DATA CALIBRAÇÃO'])
                        dt_proxima = dt_ultima + timedelta(days=freq_meses*30) if dt_ultima else None
                        dados = {'codigo': tag, 'descricao': get_val(['EQUIPAMENTO', 'DESCRIÇÃO', 'DESCRICAO']) or 'Sem Descrição', 'categoria': cat, 'fabricante': get_val(['FABRICANTE', 'MARCA']), 'modelo': get_val(['MODELO']), 'serie': get_val(['N SERIE', 'N° DE SÉRIE', 'N DE SERIE', 'SÉRIE', 'SERIE']), 'setor': setor, 'localizacao': get_val(['LOCALIZAÇÃO', 'LOCALIZACAO', 'AREA']), 'frequencia_meses': freq_meses, 'data_ultima_calibracao': dt_ultima, 'data_proxima_calibracao': dt_proxima, 'ativo': True}
                        obj, created = Instrumento.objects.update_or_create(tag=tag, defaults=dados)
                        if created: count_new += 1
                        else: count_upd += 1
                        faixa_txt = get_val(['FAIXA', 'RANGE', 'CAPACIDADE', 'FAIXA DE MEDICAO'])
                        unidade_txt = get_val(['UNIDADE', 'U.M.', 'UNIDADE DE MEDIDA'])
                        if faixa_txt and unidade_txt:
                            und, _ = UnidadeMedida.objects.get_or_create(sigla=unidade_txt, defaults={'nome': unidade_txt})
                            v_min, v_max = extrair_min_max(faixa_txt)
                            FaixaMedicao.objects.get_or_create(instrumento=obj, unidade=und, valor_minimo=v_min, valor_maximo=v_max, defaults={'resolucao': 0})
                            count_faixas += 1
                messages.success(request, f"Importação: {count_new} Novos, {count_upd} Atualizados. {count_faixas} Faixas.")
                return redirect('modulo_metrologia')
            except Exception as e: messages.error(request, f"Erro: {str(e)}"); return redirect('importar_instrumentos')
    else: form = ImportacaoInstrumentosForm()
    return render(request, 'importar_instrumentos.html', {'form': form, 'colaborador': get_colab(request)})

@login_required
def imp_historico_view(request):
    if request.method == 'POST':
        form = ImportacaoHistoricoForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                f = request.FILES['arquivo_excel']
                df = None
                try:
                    if f.name.endswith('.csv'):
                        try: df = pd.read_csv(f, sep=None, engine='python', encoding='latin1')
                        except: f.seek(0); df = pd.read_csv(f, sep=None, engine='python', encoding='utf-8')
                    else: df = pd.read_excel(f)
                except Exception as e: messages.error(request, f"Erro ao ler arquivo: {e}"); return redirect('importar_historico')
                
                if df is None or len(df.columns) < 2: messages.error(request, "Arquivo inválido ou vazio."); return redirect('importar_historico')

                df.columns = df.columns.str.strip().str.upper()
                df.columns = df.columns.str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
                count_new = 0; relatorio_erros = []
                
                with transaction.atomic():
                    for index, row in df.iterrows():
                        linha = index + 2
                        def finding_col(keys, avoid=[]):
                            for col in df.columns:
                                match = False
                                for k in keys:
                                    k_clean = k.upper().replace('Ç','C').replace('Ã','A').replace('Á','A').replace('É','E')
                                    if k_clean in col: match = True; break
                                if match:
                                    bad_match = False
                                    for b in avoid:
                                        if b.upper() in col: bad_match = True; break
                                    if not bad_match: return col
                            return None
                        
                        def get_val(col_name): return str(row[col_name]).strip() if col_name and pd.notna(row[col_name]) else None
                        
                        def conv_date(v):
                            if not v or str(v).strip() in ['-', 'NaT', 'nan', 'None', '']: return None
                            try: return pd.to_datetime(str(v).strip(), dayfirst=True).date()
                            except:
                                try: return (datetime(1899, 12, 30) + timedelta(days=float(v))).date()
                                except: return None

                        def conv_float(col_name):
                            v = get_val(col_name)
                            if not v: return None
                            try: return float(re.sub(r'[^\d,.-]', '', v).replace(',', '.'))
                            except: return None

                        col_tag = finding_col(['TAG', 'CODIGO', 'IDENTIFICACAO'])
                        col_dt = finding_col(['DATA CALIB', 'DATA ULTIMA', 'REALIZADO', 'CALIBRACAO'], evitar=['PROXIMA', 'VENCIMENTO'])
                        tag = get_val(col_tag); dt_cal = conv_date(row.get(col_dt)) if col_dt else None
                        
                        if not tag: continue
                        if not dt_cal: relatorio_erros.append(f"L.{linha}: Data inválida."); continue
                        try: inst = Instrumento.objects.get(tag=tag)
                        except: relatorio_erros.append(f"L.{linha}: Instrumento não cadastrado."); continue

                        col_apr = finding_col(['DATA APROVACAO', 'DATA VALIDACAO', 'AVALIACAO']); dt_apr = conv_date(row.get(col_apr)) if col_apr else dt_cal
                        col_cert = finding_col(['CERTIFICADO', 'N DOC'], evitar=['DATA']); num_cert = get_val(col_cert) or 'S/N'
                        
                        erro = conv_float(finding_col(['ERRO', 'TENDENCIA']))
                        inc = conv_float(finding_col(['INCERTEZA', 'U']))
                        tol = conv_float(finding_col(['TOLERANCIA', 'CRITERIO', 'EMA'], evitar=['NOMINAL']))

                        resp = get_val(finding_col(['RESPONSAVEL', 'APROVADOR', 'ANALISE']))
                        forn = get_val(finding_col(['FORNECEDOR', 'LABORATORIO']))
                        
                        res_raw = str(get_val(finding_col(['RESULTADO', 'STATUS', 'ANALISE RESULTADO'])) or '').upper()
                        res = 'APROVADO'
                        if 'REPROVADO' in res_raw: res = 'REPROVADO'
                        elif 'CONDICIONAL' in res_raw or 'RESTR' in res_raw: res = 'CONDICIONAL'
                        
                        tipo = 'INTERNA' if forn and 'INTERNA' in str(forn).upper() else 'EXTERNA'
                        rbc_raw = str(get_val(finding_col(['RBC', 'SELO', 'ACREDITADO'])) or '').upper()
                        rbc = True if rbc_raw in ['SIM', 'S', 'YES', 'RBC'] else False

                        col_prox = finding_col(['PROXIMA', 'VENCIMENTO'])
                        prox = conv_date(row.get(col_prox)) if col_prox else None
                        if not prox and inst.frequencia_meses and dt_cal:
                            try: prox = dt_cal + timedelta(days=inst.frequencia_meses*30)
                            except: pass

                        obj, cr = HistoricoCalibracao.objects.update_or_create(
                            instrumento=inst, data_calibracao=dt_cal, numero_certificado=num_cert, 
                            defaults={
                                'data_aprovacao': dt_apr, 'resultado': res, 'proxima_calibracao': prox, 
                                'erro_encontrado': erro, 'incerteza': inc, 'tolerancia_usada': tol, 
                                'responsavel': resp, 'fornecedor': forn, 'tipo_calibracao': tipo, 'tem_selo_rbc': rbc,
                                'observacoes': get_val(finding_col(['OBSERVACOES', 'OBS']))
                            }
                        )
                        if erro is not None: obj.save()
                        if cr: count_new += 1

                if relatorio_erros: messages.warning(request, f"Importados: {count_new}. Alertas: {' | '.join(relatorio_erros[:3])}")
                else: messages.success(request, f"Sucesso! {count_new} registros importados.")
                return redirect('modulo_metrologia')
            except Exception as e: messages.error(request, f"Erro Crítico: {str(e)}")
    else: form = ImportacaoHistoricoForm()
    return render(request, 'importar_historico.html', {'form': form, 'colaborador': get_colab(request)})

@login_required
def imp_padroes_view(request):
    if request.method == 'POST':
        form = ImportacaoPadroesForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                f = request.FILES['arquivo_excel']
                try: df = pd.read_excel(f)
                except: df = pd.read_csv(f, sep=None, engine='python')
                df.columns = df.columns.str.strip().str.upper()
                count = 0
                with transaction.atomic():
                    for _, row in df.iterrows():
                        def get_val(k): return str(row[k]).strip() if k in df.columns and pd.notna(row[k]) else None
                        def get_date(k): 
                            val = get_val(k)
                            if not val: return None
                            try: return pd.to_datetime(val, dayfirst=True).date()
                            except: return None
                        codigo = get_val('CODIGO')
                        if not codigo: continue
                        dt_cal = get_date('DATA CALIBRACAO') or date.today()
                        dt_val = get_date('DATA VALIDADE') or (date.today() + timedelta(days=365))
                        Padrao.objects.update_or_create(
                            codigo=codigo,
                            defaults={'descricao': get_val('DESCRICAO') or 'Padrão', 'numero_certificado': get_val('N CERTIFICADO') or 'S/N', 'data_calibracao': dt_cal, 'data_validade': dt_val, 'ativo': True}
                        )
                        count += 1
                messages.success(request, f"{count} Padrões importados!")
                return redirect('modulo_metrologia')
            except Exception as e: messages.error(request, f"Erro: {e}")
    else:
        form = ImportacaoPadroesForm()
    return render(request, 'importar_historico.html', {'form': form, 'titulo': 'Importar Padrões', 'colaborador': get_colab(request)})

@login_required
def imp_colab_view(request):
    if request.method == 'POST':
        form = ImportacaoColaboradoresForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                f = request.FILES['arquivo_excel']
                try: df = pd.read_excel(f)
                except: df = pd.read_csv(f, sep=None, engine='python', encoding='latin1')
                df.columns = df.columns.str.strip().str.upper()
                df.columns = df.columns.str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
                count_new = 0; count_upd = 0
                with transaction.atomic():
                    for index, row in df.iterrows():
                        def get_val(keywords):
                            for k in keywords:
                                for col in df.columns:
                                    if k in col and pd.notna(row[col]): return str(row[col]).strip()
                            return None
                        matricula = get_val(['MATRICULA', 'MAT', 'RE'])
                        if matricula: matricula = matricula.split('.')[0]
                        nome = get_val(['NOME', 'COLABORADOR', 'FUNCIONARIO'])
                        if not matricula or not nome: continue
                        cpf = re.sub(r'[^0-9]', '', get_val(['CPF', 'DOC'])) if get_val(['CPF', 'DOC']) else None
                        setor_nome = get_val(['SETOR', 'DEPARTAMENTO'])
                        setor_obj = None
                        if setor_nome: setor_obj, _ = Setor.objects.get_or_create(nome=setor_nome.upper())
                        
                        cc_raw = get_val(['CENTRO DE CUSTO', 'CC'])
                        cc_obj = None
                        if cc_raw and setor_obj:
                            parts = cc_raw.split('-')
                            c_code = parts[0].strip(); c_desc = parts[1].strip() if len(parts) > 1 else "Importado"
                            cc_obj, _ = CentroCusto.objects.get_or_create(codigo=c_code, setor=setor_obj, defaults={'descricao': c_desc})

                        turno = 'ADM'
                        t_raw = str(get_val(['TURNO']) or '').upper()
                        if '1' in t_raw: turno = 'TURNO_1'
                        elif '2' in t_raw: turno = 'TURNO_2'
                        elif '3' in t_raw: turno = 'TURNO_3'
                        elif '12' in t_raw: turno = '12X36'

                        status = str(get_val(['STATUS']) or 'ATIVO').upper()
                        is_active = False if 'INATIVO' in status else True
                        
                        sal_raw = get_val(['SALARIO'])
                        salario = float(sal_raw.replace(',', '.')) if sal_raw else None

                        Colaborador.objects.update_or_create(
                            matricula=matricula,
                            defaults={'nome_completo': nome.upper(), 'cpf': cpf, 'cargo': get_val(['CARGO']) or 'Não Informado', 'grupo': get_val(['GRUPO']) or 'Geral', 'setor': setor_obj, 'centro_custo': cc_obj, 'turno': turno, 'salario': salario, 'is_active': is_active}
                        )
                        if count_upd: count_upd += 1
                        else: count_new += 1
                messages.success(request, f"RH Importado: {count_new} registros processados.")
                return redirect('modulo_rh')
            except Exception as e: messages.error(request, f"Erro: {str(e)}")
    else: form = ImportacaoColaboradoresForm()
    return render(request, 'importar_colaboradores.html', {'form': form, 'colaborador': get_colab(request)})

@login_required
def imp_hierarquia_view(request):
    if request.method == 'POST': messages.success(request, "Hierarquia OK"); return redirect('modulo_rh')
    return render(request, 'importar_hierarquia.html', {'form': ImportacaoHierarquiaForm(), 'colaborador': get_colab(request)})