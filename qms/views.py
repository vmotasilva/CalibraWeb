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

# IMPORTA TODOS OS MODELOS NECESSÁRIOS
from .models import (
    Instrumento, Colaborador, ProcessoCotacao, Procedimento,
    Fornecedor, HistoricoCalibracao, Setor, CentroCusto,
    RegistroTreinamento, Ferias, Ocorrencia, HierarquiaSetor,
    CategoriaInstrumento, UnidadeMedida, FaixaMedicao
)
from .forms import (
    CarimboForm, ImportacaoInstrumentosForm, ImportacaoColaboradoresForm, 
    ImportacaoProcedimentosForm, ImportacaoHierarquiaForm, ImportacaoHistoricoForm
)
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color as RColor

# --- FUNÇÕES AUXILIARES ---
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

# --- VIEWS DE TELA (DASHBOARD E MÓDULOS) ---

@login_required
def dashboard_view(request):
    colab = get_colab(request)
    nome_display = colab.nome_completo if colab else request.user.username
    hoje = date.today()
    trinta_dias = hoje + timedelta(days=30)
    
    qtd_vencidos = Instrumento.objects.filter(data_proxima_calibracao__lt=hoje, ativo=True).count()
    qtd_avencer = Instrumento.objects.filter(data_proxima_calibracao__range=[hoje, trinta_dias], ativo=True).count()
    lista_urgentes = Instrumento.objects.filter(data_proxima_calibracao__lte=trinta_dias, ativo=True).order_by('data_proxima_calibracao')[:5]
    
    ctx = {
        'colaborador': colab, 
        'nome_display': nome_display, 
        'qtd_vencidos': qtd_vencidos, 
        'qtd_avencer': qtd_avencer, 
        'lista_urgentes': lista_urgentes, 
        'qtd_cotacoes': ProcessoCotacao.objects.filter(status='ABERTO').count(), 
        'today': hoje
    }
    return render(request, 'dashboard.html', ctx)

@login_required
def modulo_metrologia_view(request):
    colab = get_colab(request)
    ctx = {'colaborador': colab, 'instrumentos': Instrumento.objects.all().order_by('tag'), 'can_edit': True}
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
    # Busca o histórico ou dá erro 404
    hist = get_object_or_404(HistoricoCalibracao, id=historico_id)
    instrumento_id = hist.instrumento.id
    
    # Se tiver arquivo de PDF, deleta ele do sistema de arquivos
    if hist.certificado:
        hist.certificado.delete(save=False)
        
    hist.delete()
    # O Signal no models.py vai rodar automaticamente e arrumar as datas
    messages.success(request, "Certificado removido e datas atualizadas com sucesso.")
    return redirect('detalhe_instrumento', instrumento_id=instrumento_id)

# --- FUNÇÃO DE CARIMBO ---

@login_required
def carimbar_view(request):
    colab = get_colab(request)
    instrumentos_disponiveis = Instrumento.objects.filter(ativo=True).order_by('tag')
    user_full_name = f"{request.user.first_name} {request.user.last_name}".strip()
    if not user_full_name: user_full_name = request.user.username.upper()
    
    if request.method == 'POST':
        form = CarimboForm(request.POST, request.FILES)
        if form.is_valid():
            c_resp = colab 
            dt_validacao = form.cleaned_data['data_validacao']
            status_txt = form.cleaned_data['status_validacao']
            
            resultado_banco = 'APROVADO'
            if status_txt == 'Reprovado': resultado_banco = 'REPROVADO'
            elif status_txt == 'Aprovado com correções': resultado_banco = 'CONDICIONAL'
            
            fs = request.FILES.getlist('arquivo_pdf')
            try: screen_w = float(request.POST.get('page_width', 0)); screen_h = float(request.POST.get('page_height', 0))
            except: screen_w = 0; screen_h = 0
            processed_files = []

            for i, f in enumerate(fs):
                raw_x = request.POST.get(f'x_{i}', 0); raw_y = request.POST.get(f'y_{i}', 0); raw_w = request.POST.get(f'w_{i}', 0); raw_h = request.POST.get(f'h_{i}', 0)
                ui = (float(raw_x), float(raw_y), float(raw_w), float(raw_h), screen_w, screen_h)

                pdf_buffer = apply_stamp_logic(f, user_full_name, status_txt, ui, dt_validacao)
                
                inst_id = request.POST.get(f'instrument_id_{i}')
                calib_date_str = request.POST.get(f'calib_date_{i}')
                cert_num = request.POST.get(f'cert_num_{i}', f.name)
                
                if inst_id and calib_date_str:
                    try:
                        instrumento = Instrumento.objects.get(id=inst_id)
                        dt_calibracao = datetime.strptime(calib_date_str, '%Y-%m-%d').date()
                        prox_calib = None
                        if instrumento.frequencia_meses: 
                            prox_calib = dt_calibracao + timedelta(days=instrumento.frequencia_meses*30)
                        
                        hist, created = HistoricoCalibracao.objects.get_or_create(
                            instrumento=instrumento, data_calibracao=dt_calibracao, data_aprovacao=dt_validacao, numero_certificado=cert_num,
                            defaults={'proxima_calibracao': prox_calib, 'resultado': resultado_banco, 'responsavel': c_resp, 'observacoes': f"Validado por {user_full_name}: {status_txt}"}
                        )
                        if not created: hist.resultado = resultado_banco; hist.observacoes = f"Revalidado por {user_full_name}: {status_txt}"
                        
                        filename = f"Cert_{cert_num}_{instrumento.tag}.pdf"
                        hist.certificado.save(filename, ContentFile(pdf_buffer.getvalue())); hist.save()
                        
                        # Atualização automática das datas é feita pelo Signal no models.py
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


# ==============================================================================
# TEMPLATES DE DOWNLOAD
# ==============================================================================
def dl_template_instr(request):
    colunas = [
        "TAG", "EQUIPAMENTO", "STATUS", "FABRICANTE", "MODELO", "N SERIE", 
        "SETOR", "LOCALIZACAO", "FREQUENCIA_MESES", "DATA_ULTIMA_CALIBRACAO", 
        "FAIXA", "UNIDADE"
    ]
    df = pd.DataFrame(columns=colunas)
    r = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    r['Content-Disposition'] = 'attachment; filename="template_instrumentos_v2.xlsx"'
    df.to_excel(r, index=False)
    return r

def dl_template_colab(request):
    df = pd.DataFrame({'MATRICULA':['100'], 'NOME':['TESTE'], 'CPF':['000'], 'CARGO':['Y'], 'GRUPO':['ADM'], 'SETOR':['ADM'], 'CC':['100'], 'TURNO':['ADM'], 'STATUS':['ATIVO']}); b = io.BytesIO(); df.to_excel(b, index=False); b.seek(0); r = HttpResponse(b, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'); r['Content-Disposition'] = 'attachment; filename="template_colaboradores.xlsx"'; return r

def dl_template_hierarquia(request):
    df = pd.DataFrame({'SETOR': ['MANUTENCAO'], 'TURNO': ['TURNO 1'], 'MAT_LIDER': ['1001'], 'MAT_SUPERVISOR': [''], 'MAT_GERENTE': [''], 'MAT_DIRETOR': ['']}); b = io.BytesIO(); df.to_excel(b, index=False); b.seek(0); r = HttpResponse(b, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'); r['Content-Disposition'] = 'attachment; filename="template_hierarquia.xlsx"'; return r

# TEMPLATE ATUALIZADO COM COLUNAS DE CÁLCULO AUTOMÁTICO
def dl_template_historico(request):
    colunas = [
        "TAG", "DATA CALIBRAÇÃO", "DATA APROVAÇÃO", "N CERTIFICADO", 
        "ERRO ENCONTRADO", "INCERTEZA", "TOLERANCIA PROCESSO (+/-)", 
        "OBSERVAÇÕES"
    ]
    df = pd.DataFrame(columns=colunas)
    r = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    r['Content-Disposition'] = 'attachment; filename="template_historico_calibracao.xlsx"'
    df.to_excel(r, index=False)
    return r


# ==============================================================================
# IMPORTAÇÃO DE INSTRUMENTOS (LÓGICA HORIZONTAL: U1, F1, U2, F2...)
# ==============================================================================
@login_required
def imp_instr_view(request):
    if request.method == 'POST':
        form = ImportacaoInstrumentosForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                f = request.FILES['arquivo_excel']
                try:
                    df = pd.read_csv(f, sep=';', encoding='latin1') if f.name.endswith('.csv') else pd.read_excel(f)
                except:
                    f.seek(0); df = pd.read_csv(f, sep=',', encoding='utf-8')

                df.columns = df.columns.str.strip().str.upper()
                count_new = 0; count_upd = 0; count_faixas = 0
                
                with transaction.atomic():
                    for _, row in df.iterrows():
                        # --- HELPERS INTERNOS ---
                        def get_val(k_list): 
                            for key in k_list:
                                if key in df.columns and pd.notna(row[key]): return str(row[key]).strip()
                            return None
                        
                        def get_date(k_list):
                            val = get_val(k_list)
                            if not val or val == '-' or val == 'NaT': return None
                            try:
                                return pd.to_datetime(val, dayfirst=True).date()
                            except:
                                return None

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

                        # --- 1. DADOS DO INSTRUMENTO ---
                        tag = get_val(['TAG', 'IDENTIFICACAO', 'CODIGO', 'CÓDIGO'])
                        if not tag: continue 

                        cat_nome = get_val(['CATEGORIA', 'FAMILIA', 'TIPO', 'EQUIPAMENTO']) 
                        categoria_obj = None
                        if cat_nome: categoria_obj, _ = CategoriaInstrumento.objects.get_or_create(nome=cat_nome.title())

                        setor_nome = get_val(['SETOR', 'DEPARTAMENTO'])
                        setor_obj = None
                        if setor_nome: setor_obj, _ = Setor.objects.get_or_create(nome=setor_nome.upper())

                        freq_meses = traduzir_frequencia(get_val(['FREQUENCIA_MESES', 'FREQUENCIA', 'PERIODICIDADE']))
                        dt_ultima = get_date(['DATA_ULTIMA_CALIBRACAO', 'DATA ÚLTIMA CALIBRAÇÃO', 'ULTIMA CALIBRACAO', 'DATA CALIBRAÇÃO'])
                        
                        dt_proxima = None
                        if dt_ultima: dt_proxima = dt_ultima + timedelta(days=freq_meses*30)

                        dados = {
                            'codigo': tag,
                            'descricao': get_val(['EQUIPAMENTO', 'DESCRIÇÃO', 'DESCRICAO']) or 'Sem Descrição',
                            'categoria': categoria_obj,
                            'fabricante': get_val(['FABRICANTE', 'MARCA']),
                            'modelo': get_val(['MODELO']),
                            'serie': get_val(['N SERIE', 'N° DE SÉRIE', 'N DE SERIE', 'SÉRIE', 'SERIE']),
                            'setor': setor_obj,
                            'localizacao': get_val(['LOCALIZAÇÃO', 'LOCALIZACAO', 'AREA']),
                            'frequencia_meses': freq_meses,
                            'data_ultima_calibracao': dt_ultima,
                            'data_proxima_calibracao': dt_proxima,
                            'ativo': True
                        }

                        obj, created = Instrumento.objects.update_or_create(tag=tag, defaults=dados)
                        if created: count_new += 1
                        else: count_upd += 1

                        # --- 2. DADOS DA FAIXA ---
                        faixa_txt = get_val(['FAIXA', 'RANGE', 'CAPACIDADE', 'FAIXA DE MEDICAO'])
                        unidade_txt = get_val(['UNIDADE', 'U.M.', 'UNIDADE DE MEDIDA'])
                        
                        if faixa_txt and unidade_txt:
                            und_obj, _ = UnidadeMedida.objects.get_or_create(sigla=unidade_txt, defaults={'nome': unidade_txt})
                            v_min, v_max = extrair_min_max(faixa_txt)
                            
                            FaixaMedicao.objects.get_or_create(
                                instrumento=obj, 
                                unidade=und_obj,
                                valor_minimo=v_min,
                                valor_maximo=v_max,
                                defaults={'resolucao': 0} 
                            )
                            count_faixas += 1

                messages.success(request, f"Importação: {count_new} Novos, {count_upd} Atualizados. {count_faixas} Faixas processadas.")
                return redirect('modulo_metrologia')
            
            except Exception as e:
                messages.error(request, f"Erro ao importar: {str(e)}")
                return redirect('importar_instrumentos')
    else:
        form = ImportacaoInstrumentosForm()
    return render(request, 'importar_instrumentos.html', {'form': form, 'colaborador': get_colab(request)})

# ==============================================================================
# IMPORTAÇÃO DE HISTÓRICO (COM DEBUG DE COLUNAS)
# ==============================================================================
@login_required
def imp_historico_view(request):
    if request.method == 'POST':
        form = ImportacaoHistoricoForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                f = request.FILES['arquivo_excel']
                df = None
                
                # 1. TENTATIVAS DE LEITURA (Força Bruta para descobrir o formato)
                if f.name.endswith('.csv'):
                    # Tentativa A: Padrão Brasileiro (Ponto e vírgula + Latin1)
                    try:
                        f.seek(0)
                        df = pd.read_csv(f, sep=';', encoding='latin1')
                    except: pass
                    
                    # Tentativa B: Padrão Internacional (Vírgula + UTF-8) - Se A falhou ou veio 1 coluna
                    if df is None or len(df.columns) < 2:
                        try:
                            f.seek(0)
                            df = pd.read_csv(f, sep=',', encoding='utf-8')
                        except: pass

                    # Tentativa C: Motor Python (Adivinhação)
                    if df is None or len(df.columns) < 2:
                        try:
                            f.seek(0)
                            df = pd.read_csv(f, sep=None, engine='python', encoding='latin1')
                        except: pass
                else:
                    # Excel (.xlsx)
                    df = pd.read_excel(f)

                # Verifica se conseguiu ler algo útil
                if df is None or len(df.columns) < 2:
                    cols_lidas = list(df.columns) if df is not None else "Nenhuma"
                    messages.error(request, f"Erro de Leitura: O sistema não reconheceu as colunas. Colunas encontradas: {cols_lidas}. Verifique se é CSV separado por ponto-e-vírgula.")
                    return redirect('importar_historico')

                # 2. LIMPEZA DE CABEÇALHO
                df.columns = df.columns.str.strip().str.upper()
                # Remove acentos e caracteres estranhos
                df.columns = df.columns.str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
                
                count_new = 0
                relatorio_erros = []

                with transaction.atomic():
                    for index, row in df.iterrows():
                        linha = index + 2
                        
                        # --- HELPERS ---
                        def get_val(k_list):
                            if isinstance(k_list, str): k_list = [k_list]
                            for key in k_list:
                                # Normaliza a chave de busca (remove acentos)
                                key_clean = key.upper().encode('ascii', 'ignore').decode('utf-8')
                                # Procura coluna exata ou coluna que CONTÉM o nome (ex: "TAG DO INSTRUMENTO")
                                for col in df.columns:
                                    if key_clean == col or key_clean in col:
                                        if pd.notna(row[col]): return str(row[col]).strip()
                            return None
                        
                        def get_date_val(k_list):
                            val = get_val(k_list)
                            if not val or val == '-' or val == 'NaT': return None
                            try: return pd.to_datetime(val, dayfirst=True).date() 
                            except: 
                                try:
                                    return (datetime(1899, 12, 30) + timedelta(days=float(val))).date()
                                except: return None

                        def get_float(k_list):
                            val = get_val(k_list)
                            if not val: return None
                            clean_val = re.sub(r'[^\d,.-]', '', val).replace(',', '.')
                            try: return float(clean_val)
                            except: return None
                        
                        # --- LÓGICA PRINCIPAL ---
                        # Busca por TAG, CODIGO, etc.
                        tag = get_val(['TAG', 'CODIGO', 'IDENTIFICACAO', 'INSTRUMENTO'])
                        
                        if not tag: 
                            if any(pd.notna(row)): relatorio_erros.append(f"L.{linha}: Coluna TAG vazia ou não identificada.")
                            continue
                        
                        dt_cal = get_date_val(['DATA CALIBRACAO', 'DATA DA CALIBRACAO', 'CALIBRACAO'])
                        if not dt_cal:
                            relatorio_erros.append(f"L.{linha} ({tag}): Data inválida.")
                            continue
                        
                        try: inst = Instrumento.objects.get(tag=tag)
                        except: 
                            relatorio_erros.append(f"L.{linha}: Instrumento '{tag}' não existe no sistema.")
                            continue
                        
                        dt_apr = get_date_val(['DATA APROVACAO', 'DATA VALIDACAO', 'APROVADO EM']) or dt_cal
                        num_cert = get_val(['N CERTIFICADO', 'CERTIFICADO', 'N DOC']) or 'S/N'
                        
                        erro = get_float(['ERRO', 'TENDENCIA'])
                        inc = get_float(['INCERTEZA', 'U'])
                        tol = get_float(['TOLERANCIA', 'CRITERIO', 'EMA'])
                        
                        nome_resp = get_val(['RESPONSAVEL', 'APROVADOR'])
                        resp_obj = None
                        if nome_resp:
                            resp_obj = Colaborador.objects.filter(
                                Q(nome_completo__iexact=nome_resp) | Q(nome_completo__icontains=nome_resp) | Q(matricula=nome_resp)
                            ).first()

                        # Resultado
                        res_excel = str(get_val(['RESULTADO', 'STATUS']) or '').upper()
                        res = 'APROVADO'
                        if 'REPROVADO' in res_excel: res = 'REPROVADO'
                        elif 'CONDICIONAL' in res_excel: res = 'CONDICIONAL'
                        
                        prox = get_date_val(['PROXIMA CALIBRACAO', 'VENCIMENTO'])
                        if not prox and inst.frequencia_meses:
                            prox = dt_cal + timedelta(days=inst.frequencia_meses*30)
                        
                        obj, cr = HistoricoCalibracao.objects.update_or_create(
                            instrumento=inst, data_calibracao=dt_cal, numero_certificado=num_cert, 
                            defaults={
                                'data_aprovacao': dt_apr, 'resultado': res, 'proxima_calibracao': prox, 
                                'erro_encontrado': erro, 'incerteza': inc, 'tolerancia_usada': tol, 
                                'responsavel': resp_obj, 'observacoes': get_val(['OBSERVACOES', 'OBS'])
                            }
                        )
                        if erro is not None and inc is not None and tol is not None: obj.save()
                        if cr: count_new += 1

                if relatorio_erros:
                    msg = " | ".join(relatorio_erros[:3])
                    # SE FALHAR, MOSTRA QUAIS COLUNAS ELE LEU PARA AJUDAR NO DEBUG
                    messages.warning(request, f"Importados: {count_new}. Problemas: {msg}. (Colunas lidas no arquivo: {list(df.columns)})")
                else:
                    messages.success(request, f"Sucesso! {count_new} registros importados.")
                
                return redirect('modulo_metrologia')

            except Exception as e: messages.error(request, f"Erro Crítico: {str(e)}")
    else: form = ImportacaoHistoricoForm()
    return render(request, 'importar_historico.html', {'form': form, 'colaborador': get_colab(request)})

@login_required
def imp_colab_view(request):
    if request.method == 'POST':
        form = ImportacaoColaboradoresForm(request.POST, request.FILES)
        if form.is_valid(): messages.success(request, "Importação OK"); return redirect('modulo_rh')
    else: form = ImportacaoColaboradoresForm()
    return render(request, 'importar_colaboradores.html', {'form': form, 'colaborador': get_colab(request)})

@login_required
def imp_hierarquia_view(request):
    if request.method == 'POST': messages.success(request, "Hierarquia OK"); return redirect('modulo_rh')
    return render(request, 'importar_hierarquia.html', {'form': ImportacaoHierarquiaForm(), 'colaborador': get_colab(request)})