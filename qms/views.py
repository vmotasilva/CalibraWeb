import pandas as pd
import io
import zipfile
import os
from datetime import datetime, date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages

# Importando TODOS os modelos para garantir que nada falte
from .models import (
    Instrumento, Colaborador, TipoMedicao, ProcessoCotacao, 
    Fornecedor, HistoricoCalibracao, Setor, CentroCusto,
    Documento, RegistroTreinamento
)
from .forms import CarimboForm, ImportacaoInstrumentosForm, ImportacaoColaboradoresForm

from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color as RColor

# ==============================================================================
# 1. DASHBOARD E VISUALIZAÇÃO
# ==============================================================================

def dashboard_view(request):
    """Tela inicial com indicadores e alertas."""
    hoje = date.today()
    aviso_30_dias = hoje + timedelta(days=30)

    # Indicadores de Calibração
    qtd_vencidos = TipoMedicao.objects.filter(data_proxima_calibracao__lt=hoje).count()
    qtd_avencer = TipoMedicao.objects.filter(data_proxima_calibracao__range=[hoje, aviso_30_dias]).count()
    
    # Tabela de urgência (Top 5)
    lista_urgentes = TipoMedicao.objects.filter(
        data_proxima_calibracao__lte=aviso_30_dias
    ).order_by('data_proxima_calibracao')[:5]

    # Outros Indicadores
    qtd_cotacoes_abertas = ProcessoCotacao.objects.filter(status='ABERTO').count()
    qtd_fornecedores_analise = Fornecedor.objects.filter(status='EM_ANALISE').count()

    context = {
        'today': hoje,
        'qtd_vencidos': qtd_vencidos,
        'qtd_avencer': qtd_avencer,
        'lista_urgentes': lista_urgentes,
        'qtd_cotacoes': qtd_cotacoes_abertas,
        'qtd_fornecedores': qtd_fornecedores_analise,
    }
    return render(request, 'dashboard.html', context)

def detalhe_instrumento_view(request, instrumento_id):
    """Ficha técnica visual do instrumento."""
    instrumento = get_object_or_404(Instrumento, id=instrumento_id)
    medicoes = instrumento.medicoes.all()
    # Histórico ordenado por data (mais recente primeiro)
    historico = HistoricoCalibracao.objects.filter(tipo_medicao__instrumento=instrumento).order_by('-data_calibracao')

    context = {
        'instrumento': instrumento,
        'medicoes': medicoes,
        'historico': historico,
        'today': date.today()
    }
    return render(request, 'detalhe_instrumento.html', context)

# ==============================================================================
# 2. LÓGICA DE CARIMBO (OTIMIZADA)
# ==============================================================================

def apply_stamp_logic(pdf_file, colaborador, status_texto, ui_coords):
    """Função auxiliar que aplica o carimbo em um único arquivo PDF (em memória)."""
    input_pdf = PdfReader(pdf_file)
    output_pdf = PdfWriter()
    page0 = input_pdf.pages[0]
    
    pdf_w_pt = float(page0.mediabox.width)
    pdf_h_pt = float(page0.mediabox.height)

    # Desempacota coordenadas da tela
    ui_x, ui_y, ui_w, ui_h, ui_pw, ui_ph = ui_coords

    # Conversão de escala (Tela -> PDF)
    if ui_w > 0:
        scale_x = pdf_w_pt / ui_pw
        scale_y = pdf_h_pt / ui_ph
        rect_h = ui_h * scale_y
        pdf_x0 = ui_x * scale_x
        pdf_y0 = pdf_h_pt - (ui_y * scale_y) - rect_h
    else:
        # Posição padrão se o usuário não desenhar
        rect_w = pdf_w_pt * 0.30
        rect_h = pdf_h_pt * 0.08
        margin = pdf_w_pt * 0.05
        pdf_x0 = pdf_w_pt - rect_w - margin
        pdf_y0 = pdf_h_pt - rect_h - margin - 50

    # Desenho com ReportLab
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(pdf_w_pt, pdf_h_pt))

    # Definição de Cores
    C_BLUE = RColor(0, 0, 0.8)
    C_GREEN = RColor(0, 0.5, 0)
    C_YELLOW = RColor(0.8, 0.6, 0)
    C_RED = RColor(0.8, 0, 0)

    if "sem" in status_texto: cor_status = C_GREEN
    elif "com" in status_texto: cor_status = C_YELLOW
    else: cor_status = C_RED

    text_y_start = pdf_y0 + (rect_h if ui_w > 0 else pdf_h_pt * 0.08) - 13
    
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(cor_status)
    c.drawString(pdf_x0, text_y_start, status_texto)

    c.setFont("Helvetica", 11)
    c.setFillColor(C_BLUE)
    c.drawString(pdf_x0, text_y_start - 16, datetime.now().strftime("%d/%m/%Y"))
    c.drawString(pdf_x0, text_y_start - 32, colaborador.nome_completo)
    
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(pdf_x0, text_y_start - 46, colaborador.cargo)

    c.save()
    packet.seek(0)

    # Mesclagem
    stamp_reader = PdfReader(packet)
    page0.merge_page(stamp_reader.pages[0])
    output_pdf.add_page(page0)

    for p in input_pdf.pages[1:]:
        output_pdf.add_page(p)

    out_buffer = io.BytesIO()
    output_pdf.write(out_buffer)
    out_buffer.seek(0)
    return out_buffer

def carimbar_view(request):
    """View principal do carimbo (Recebe formulário e decide se baixa PDF ou ZIP)."""
    if request.method == 'POST':
        form = CarimboForm(request.POST, request.FILES)
        if form.is_valid():
            colaborador = form.cleaned_data['colaborador']
            status_texto = form.cleaned_data['status_validacao']
            files = request.FILES.getlist('arquivo_pdf')
            
            ui_coords = (
                form.cleaned_data.get('x') or 0,
                form.cleaned_data.get('y') or 0,
                form.cleaned_data.get('w') or 0,
                form.cleaned_data.get('h') or 0,
                form.cleaned_data.get('page_width') or 1,
                form.cleaned_data.get('page_height') or 1
            )

            # Caso 1: Apenas um arquivo (Baixa direto o PDF)
            if len(files) == 1:
                pdf_buffer = apply_stamp_logic(files[0], colaborador, status_texto, ui_coords)
                filename = f"{files[0].name.replace('.pdf','')}_{datetime.now().strftime('%Y%m%d')}_validado.pdf"
                response = HttpResponse(pdf_buffer, content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
            
            # Caso 2: Múltiplos arquivos (Baixa um ZIP)
            else:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                    for f in files:
                        pdf_buffer = apply_stamp_logic(f, colaborador, status_texto, ui_coords)
                        clean_name = f.name.replace('.pdf','')
                        fname_zip = f"{clean_name}_{datetime.now().strftime('%Y%m%d')}_validado.pdf"
                        zip_file.writestr(fname_zip, pdf_buffer.getvalue())
                
                zip_buffer.seek(0)
                response = HttpResponse(zip_buffer, content_type='application/zip')
                response['Content-Disposition'] = f'attachment; filename="Lote_Certificados_{datetime.now().strftime("%Y%m%d")}.zip"'
                return response
    else:
        form = CarimboForm()

    return render(request, 'carimbo.html', {'form': form})

# ==============================================================================
# 3. DOWNLOADS DE TEMPLATES (MODELOS EXCEL)
# ==============================================================================

def download_template_instrumentos(request):
    data = {
        'TAG': ['BAL-01', 'TER-05'],
        'DESCRICAO': ['BALANÇA ANALÍTICA', 'TERMOHIGRÔMETRO'],
        'FABRICANTE': ['METTLER', 'TESTO'],
        'MODELO': ['XP205', '608-H1'],
        'SERIE': ['123456', 'SN-999'],
        'LOCALIZACAO': ['LABORATORIO', 'PRODUCAO'],
        'STATUS': ['ATIVO', 'ATIVO'],
        'GRANDEZA': ['MASSA', 'TEMPERATURA'],
        'FAIXA': ['0 a 200g', '-10 a 50 °C'],
        'RESOLUCAO': ['0.0001g', '0.1 °C'],
        'PERIODICIDADE_MESES': [12, 6],
        'DATA_ULTIMA_CALIBRACAO': [date.today().strftime('%d/%m/%Y'), '']
    }
    df = pd.DataFrame(data)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Instrumentos')
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="template_instrumentos.xlsx"'
    return response

def download_template_colaboradores(request):
    data = {
        'MATRICULA': ['1001'],
        'NOME_COMPLETO': ['JOAO SILVA'],
        'GRUPO': ['MANUTENCAO'],
        'CARGO': ['TECNICO'],
        'SETOR': ['OFICINA'],
        'CENTRO_CUSTO': ['2050'],
        'TURNO': ['TURNO 1'],
        'STATUS': ['ATIVO']
    }
    df = pd.DataFrame(data)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Colaboradores')
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="template_colaboradores.xlsx"'
    return response


# ==============================================================================
# 4. IMPORTAÇÃO INTELIGENTE (INSTRUMENTOS)
# ==============================================================================

def importar_instrumentos_view(request):
    if request.method == 'POST':
        form = ImportacaoInstrumentosForm(request.POST, request.FILES)
        if form.is_valid():
            arquivo = request.FILES['arquivo_excel']
            try:
                nome_arquivo = arquivo.name.lower()
                # Suporte a CSV e Excel
                if nome_arquivo.endswith('.csv'):
                    try: df = pd.read_csv(arquivo, sep=';', encoding='utf-8-sig')
                    except: df = pd.read_csv(arquivo, sep=';', encoding='latin1')
                    xls_dict = {'Planilha1': df}
                else:
                    xls_dict = pd.read_excel(arquivo, sheet_name=None)

                total_instr = 0
                total_med = 0
                
                for nome_aba, df in xls_dict.items():
                    df.columns = df.columns.str.strip().str.upper()
                    
                    for index, row in df.iterrows():
                        # 1. Identificação
                        tag_val = str(row.get('TAG') or row.get('CODIGO') or row.get('IDENTIFICACAO') or '').strip().upper()
                        if not tag_val or tag_val == 'NAN': continue

                        # 2. Tratamento de Campos
                        marca_val = str(row.get('FABRICANTE') or row.get('MARCA') or '').strip()
                        status_raw = str(row.get('STATUS') or row.get('SITUACAO') or 'ATIVO').strip().upper()
                        
                        status_final = 'ATIVO'
                        if 'INATIVO' in status_raw or 'PARADO' in status_raw: status_final = 'INATIVO'
                        elif 'SUCATA' in status_raw: status_final = 'SUCATA'

                        # 3. Busca/Cria Setor Automaticamente
                        local_val = str(row.get('LOCALIZACAO') or row.get('LOCAL') or row.get('SETOR') or '').strip().upper()
                        setor_obj = None
                        if local_val and local_val != 'NAN':
                            setor_obj, _ = Setor.objects.get_or_create(nome=local_val)

                        # 4. Upsert Instrumento
                        instr, created = Instrumento.objects.update_or_create(
                            tag=tag_val,
                            defaults={
                                'descricao': str(row.get('DESCRICAO') or 'N/D').strip(),
                                'marca': marca_val,
                                'modelo': str(row.get('MODELO') or '').strip(),
                                'serie': str(row.get('SERIE') or '').strip(),
                                'setor': setor_obj,
                                'status': status_final,
                            }
                        )
                        if created: total_instr += 1

                        # 5. Upsert Medição
                        grandeza_val = str(row.get('GRANDEZA') or row.get('TIPO') or nome_aba).strip().upper()
                        if not grandeza_val or grandeza_val == 'NAN': grandeza_val = "GERAL"

                        dt_str = row.get('DATA_ULTIMA_CALIBRACAO') or row.get('DATA')
                        try: dt_ult = pd.to_datetime(dt_str, dayfirst=True).date()
                        except: dt_ult = None

                        try: freq = int(row.get('PERIODICIDADE_MESES') or 12)
                        except: freq = 12

                        TipoMedicao.objects.update_or_create(
                            instrumento=instr,
                            grandeza=grandeza_val,
                            defaults={
                                'faixa': str(row.get('FAIXA') or '').strip(),
                                'resolucao': str(row.get('RESOLUCAO') or '').strip(),
                                'periodicidade_meses': freq,
                                'data_ultima_calibracao': dt_ult
                            }
                        )
                        total_med += 1
                
                messages.success(request, f"Sucesso! {total_instr} instrumentos criados e {total_med} medições processadas.")
                return redirect('importar_instrumentos')

            except Exception as e:
                messages.error(request, f"Erro ao processar arquivo: {str(e)}")
    else:
        form = ImportacaoInstrumentosForm()
        
    return render(request, 'importar_instrumentos.html', {'form': form})

# ==============================================================================
# 5. IMPORTAÇÃO COLABORADORES (COM SETOR E TURNO)
# ==============================================================================

def importar_colaboradores_view(request):
    if request.method == 'POST':
        form = ImportacaoColaboradoresForm(request.POST, request.FILES)
        if form.is_valid():
            arquivo = request.FILES['arquivo_excel']
            try:
                nome_arq = arquivo.name.lower()
                if nome_arq.endswith('.csv'):
                    try: df = pd.read_csv(arquivo, sep=';', encoding='utf-8-sig', dtype=str)
                    except: df = pd.read_csv(arquivo, sep=';', encoding='latin1', dtype=str)
                else:
                    df = pd.read_excel(arquivo, dtype=str)

                df.columns = df.columns.str.strip().str.upper()
                count = 0
                
                for index, row in df.iterrows():
                    # Limpa Matrícula (.0 se houver)
                    matr = str(row.get('MATRICULA', '')).strip().upper()
                    if matr.endswith('.0'): matr = matr[:-2]
                    if not matr or matr == 'NAN': continue
                    
                    # Trata Status
                    st_raw = str(row.get('STATUS', 'ATIVO')).upper()
                    is_active = True
                    if 'INATIVO' in st_raw or 'DEMITIDO' in st_raw: is_active = False
                    
                    # Trata Setor e Centro de Custo
                    setor_nome = str(row.get('SETOR', '')).strip().upper()
                    setor_obj = None
                    if setor_nome and setor_nome != 'NAN':
                        setor_obj, _ = Setor.objects.get_or_create(nome=setor_nome)

                    cc_cod = str(row.get('CENTRO_CUSTO', row.get('CC', ''))).strip()
                    cc_obj = None
                    if cc_cod and cc_cod != 'NAN' and setor_obj:
                        cc_obj, _ = CentroCusto.objects.get_or_create(setor=setor_obj, codigo=cc_cod)

                    # Trata Turno (Conversão de texto livre para código do banco)
                    turno_raw = str(row.get('TURNO', 'ADM')).upper().strip()
                    turno_final = 'ADM'
                    if '1' in turno_raw or 'PRIMEIRO' in turno_raw: turno_final = 'TURNO_1'
                    elif '2' in turno_raw or 'SEGUNDO' in turno_raw: turno_final = 'TURNO_2'
                    elif '3' in turno_raw or 'TERCEIRO' in turno_raw: turno_final = 'TURNO_3'
                    elif '12' in turno_raw: turno_final = '12X36'

                    # Upsert Colaborador
                    Colaborador.objects.update_or_create(
                        matricula=matr,
                        defaults={
                            'username': matr, 
                            'nome_completo': str(row.get('NOME_COMPLETO', row.get('NOME', ''))).upper(),
                            'grupo': str(row.get('GRUPO', '')).upper(),
                            'cargo': str(row.get('CARGO', row.get('FUNCAO', ''))).upper(),
                            'setor': setor_obj,
                            'centro_custo': cc_obj,
                            'turno': turno_final,
                            'is_active': is_active
                        }
                    )
                    count += 1
                
                messages.success(request, f"{count} colaboradores processados com sucesso!")
                return redirect('importar_colaboradores')

            except Exception as e:
                messages.error(request, f"Erro ao importar: {str(e)}")
    else:
        form = ImportacaoColaboradoresForm()
    
    return render(request, 'importar_colaboradores.html', {'form': form})