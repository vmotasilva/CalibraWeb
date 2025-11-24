import pandas as pd
import io
import zipfile
import os
import re
from datetime import datetime, date, timedelta
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, Http404
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
    ImportacaoPadroesForm, ColaboradorForm
)
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color as RColor

# --- FUNÇÕES AUXILIARES ---
def get_colab(request):
    """
    Tenta identificar qual Colaborador (RH) corresponde ao Usuário Logado (Django).
    """
    # 1. Tenta pelo vínculo manual
    try: 
        return Colaborador.objects.get(user_django=request.user)
    except Colaborador.DoesNotExist:
        pass
    except Exception:
        pass

    # 2. Tenta pelo Nome (Feature Automática)
    if request.user.first_name and request.user.last_name:
        nome_montado = f"{request.user.first_name} {request.user.last_name}".strip()
        colab = Colaborador.objects.filter(nome_completo__iexact=nome_montado).first()
        if colab:
            return colab
    return None

def excel_date_to_datetime(serial):
    if pd.isnull(serial) or str(serial).strip() == '' or str(serial).strip() == '-': return None
    try:
        serial_str = str(serial).strip()
        if '/' in serial_str: return pd.to_datetime(serial_str, dayfirst=True).date()
        serial_float = float(serial)
        return (datetime(1899, 12, 30) + timedelta(days=serial_float)).date()
    except: return None

def get_all_subordinates(colaborador):
    subordinados = set()
    diretos = colaborador.liderados.all()
    for direto in diretos:
        subordinados.add(direto.id)
        subordinados.update(get_all_subordinates(direto))
    return subordinados

# ==============================================================================
# VIEWS
# ==============================================================================

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
        'colaborador': colab, 'nome_display': nome_display, 
        'qtd_vencidos': qtd_vencidos, 'qtd_avencer': qtd_avencer, 
        'lista_urgentes': lista_urgentes, 
        'qtd_cotacoes': ProcessoCotacao.objects.filter(status='ABERTO').count(), 
        'today': hoje
    }
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
    
    funcionarios_visiveis = Colaborador.objects.none()
    can_see_salary = False

    if request.user.is_superuser or request.user.is_staff:
        funcionarios_visiveis = Colaborador.objects.all().order_by('nome_completo')
        can_see_salary = True
    elif colab:
        if colab.setor and 'RH' in colab.setor.nome.upper():
            funcionarios_visiveis = Colaborador.objects.all().order_by('nome_completo')
            can_see_salary = True
        else:
            # Visão de Túnel
            ids_permitidos = get_all_subordinates(colab)
            ids_permitidos.add(colab.id)
            funcionarios_visiveis = Colaborador.objects.filter(id__in=ids_permitidos).order_by('nome_completo')
            
            if 'GERENTE' in str(colab.cargo).upper(): can_see_salary = True
            if HierarquiaSetor.objects.filter(gerente=colab).exists(): can_see_salary = True
    else:
        if not (request.user.is_superuser or request.user.is_staff):
            messages.warning(request, f"Não foi possível vincular seu usuário '{request.user.username}' a um colaborador.")

    # Filtros
    lideres_ids = funcionarios_visiveis.values_list('lider', flat=True).distinct()
    lideres_filtro = Colaborador.objects.filter(id__in=lideres_ids).order_by('nome_completo')
    
    setores_ids = funcionarios_visiveis.values_list('setor', flat=True).distinct()
    setores_filtro = Setor.objects.filter(id__in=setores_ids).order_by('nome')

    turnos_filtro = [
        ('ADM', 'Administrativo'),
        ('TURNO_1', 'Turno 1'),
        ('TURNO_2', 'Turno 2'),
        ('TURNO_3', 'Turno 3'),
        ('12X36', '12x36'),
    ]

    ctx = {
        'colaborador': colab, 
        'funcionarios': funcionarios_visiveis,
        'lideres_filtro': lideres_filtro, 
        'setores_filtro': setores_filtro, 
        'turnos_filtro': turnos_filtro,
        'centros': CentroCusto.objects.all().order_by('codigo'), 
        'can_see_salary': can_see_salary,
        'can_edit': True
    }
    return render(request, 'modulo_rh.html', ctx)

@login_required
def detalhe_colaborador_view(request, colab_id):
    usuario_logado = get_colab(request)
    alvo = get_object_or_404(Colaborador, id=colab_id)
    
    # Segurança de Acesso
    if not (request.user.is_superuser or request.user.is_staff):
        permitido = False
        if usuario_logado:
            if usuario_logado.id == alvo.id: permitido = True
            elif usuario_logado.setor and 'RH' in usuario_logado.setor.nome.upper(): permitido = True
            else:
                meus_subordinados = get_all_subordinates(usuario_logado)
                if alvo.id in meus_subordinados: permitido = True
        if not permitido:
            messages.error(request, "Acesso Negado.")
            return redirect('modulo_rh')

    can_see_salary = False
    if request.user.is_superuser or request.user.is_staff: can_see_salary = True
    elif usuario_logado:
        if 'GERENTE' in str(usuario_logado.cargo).upper(): can_see_salary = True
        if HierarquiaSetor.objects.filter(gerente=usuario_logado).exists(): can_see_salary = True
        if usuario_logado.id == alvo.id: can_see_salary = True

    # Dados Relacionados
    ocorrencias = alvo.ocorrencias.all().order_by('-data_ocorrencia')
    treinamentos = alvo.treinamentos.all().order_by('-data_treinamento')
    documentos = alvo.documentos_pessoais.all().order_by('-data_upload')
    
    # --- CORREÇÃO: LÓGICA DE FÉRIAS ---
    try:
        # Tenta acessar pelo nome padrão reverso do Django (ferias_set)
        ferias_qs = alvo.ferias_set.all().order_by('-periodo_aquisitivo_fim')
    except AttributeError:
        # Se tiver related_name definido diferente, tenta o padrão 'ferias' ou lista vazia
        ferias_qs = getattr(alvo, 'ferias', [])
        if hasattr(ferias_qs, 'all'): ferias_qs = ferias_qs.all().order_by('-periodo_aquisitivo_fim')

    ferias_vencidas = 0
    ferias_programadas = 0
    hoje = date.today()

    # KPI Calculator
    for f in ferias_qs:
        # Data limite (vencimento legal)
        dt_limite = f.data_limite if f.data_limite else (f.periodo_aquisitivo_fim + timedelta(days=365) if f.periodo_aquisitivo_fim else None)
        
        # Vencida: Passou do limite e não tem programação futura
        if dt_limite and dt_limite < hoje:
             if f.status != 'GOZADAS' and (not f.data_inicio or f.data_inicio < hoje):
                 ferias_vencidas += 1
        
        # Programada: Tem data futura
        if f.data_inicio and f.data_inicio > hoje:
            ferias_programadas += 1

    ctx = {
        'colaborador': usuario_logado, 'alvo': alvo,
        'can_see_salary': can_see_salary, 
        'ocorrencias': ocorrencias,
        'treinamentos': treinamentos, 
        'documentos': documentos,
        'ferias': ferias_qs, 
        'kpi_ferias_vencidas': ferias_vencidas, 
        'kpi_ferias_programadas': ferias_programadas,
        'can_edit': True
    }
    return render(request, 'detalhe_colaborador.html', ctx)

@login_required
def editar_colaborador_view(request, colab_id):
    usuario_logado = get_colab(request)
    alvo = get_object_or_404(Colaborador, id=colab_id)
    
    if not (request.user.is_superuser or request.user.is_staff):
        permitido = False
        if usuario_logado:
            if usuario_logado.setor and 'RH' in usuario_logado.setor.nome.upper(): permitido = True
            else:
                meus_subordinados = get_all_subordinates(usuario_logado)
                if alvo.id in meus_subordinados: permitido = True
        if not permitido: messages.error(request, "Acesso Negado."); return redirect('modulo_rh')
    
    if request.method == 'POST':
        form = ColaboradorForm(request.POST, instance=alvo)
        if form.is_valid(): form.save(); messages.success(request, "Atualizado!"); return redirect('detalhe_colaborador', colab_id=alvo.id)
        else: messages.error(request, "Erro ao salvar.")
    else: form = ColaboradorForm(instance=alvo)
    return render(request, 'editar_colaborador.html', {'form': form, 'alvo': alvo, 'colaborador': usuario_logado})

@login_required
def detalhe_instrumento_view(request, instrumento_id):
    inst = get_object_or_404(Instrumento, id=instrumento_id)
    historico = inst.historico_calibracoes.all().order_by('-data_calibracao')
    faixas = inst.faixas.all()
    return render(request, 'detalhe_instrumento.html', {'colaborador': get_colab(request), 'instrumento': inst, 'historico': historico, 'faixas': faixas, 'today': date.today()})

@login_required
def remover_historico_view(request, historico_id):
    hist = get_object_or_404(HistoricoCalibracao, id=historico_id); i_id = hist.instrumento.id
    if hist.certificado: hist.certificado.delete(save=False)
    hist.delete(); messages.success(request, "Removido."); return redirect('detalhe_instrumento', instrumento_id=i_id)

@login_required
def carimbar_view(request):
    colab = get_colab(request); user_full_name = f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username.upper()
    if request.method == 'POST':
        form = CarimboForm(request.POST, request.FILES)
        if form.is_valid():
            c_resp = colab; dt_val = form.cleaned_data['data_validacao']; status = form.cleaned_data['status_validacao']; is_rbc = form.cleaned_data.get('is_rbc', False); padroes = form.cleaned_data.get('padroes', [])
            res_banco = 'REPROVADO' if status == 'Reprovado' else 'CONDICIONAL' if 'correções' in status else 'APROVADO'
            fs = request.FILES.getlist('arquivo_pdf'); processed = []
            try: sw = float(request.POST.get('page_width', 0)); sh = float(request.POST.get('page_height', 0))
            except: sw=0; sh=0
            for i, f in enumerate(fs):
                rx = request.POST.get(f'x_{i}',0); ry = request.POST.get(f'y_{i}',0); rw = request.POST.get(f'w_{i}',0); rh = request.POST.get(f'h_{i}',0)
                ui = (float(rx), float(ry), float(rw), float(rh), sw, sh)
                buf = apply_stamp_logic(f, user_full_name, status, ui, dt_val)
                inst_id = request.POST.get(f'instrument_id_{i}'); calib_dt = request.POST.get(f'calib_date_{i}'); c_num = request.POST.get(f'cert_num_{i}', f.name)
                if inst_id and calib_dt:
                    try:
                        inst = Instrumento.objects.get(id=inst_id); dt_c = datetime.strptime(calib_dt, '%Y-%m-%d').date()
                        prox = dt_c + timedelta(days=inst.frequencia_meses*30) if inst.frequencia_meses else None
                        h, cr = HistoricoCalibracao.objects.get_or_create(instrumento=inst, data_calibracao=dt_c, numero_certificado=c_num, defaults={'proxima_calibracao': prox, 'resultado': res_banco, 'responsavel': str(c_resp), 'observacoes': f"Validado por {user_full_name}: {status}", 'tem_selo_rbc': is_rbc, 'tipo_calibracao': 'EXTERNA'})
                        if not cr: h.resultado = res_banco; h.observacoes = f"Revalidado: {status}"
                        if not is_rbc and padroes: h.padroes_utilizados.set(padroes)
                        fn = f"Cert_{c_num}_{inst.tag}.pdf"; h.certificado.save(fn, ContentFile(buf.getvalue())); h.save()
                    except: pass
                buf.seek(0); processed.append((f.name, buf))
            if len(processed)==1: r = HttpResponse(processed[0][1], content_type='application/pdf'); r['Content-Disposition'] = f'attachment; filename="Validado_{processed[0][0]}"'; return r
            elif len(processed)>1: 
                zb = io.BytesIO()
                with zipfile.ZipFile(zb, 'w') as zf: 
                    for n, b in processed: zf.writestr(f"Validado_{n}", b.getvalue())
                zb.seek(0); r = HttpResponse(zb, content_type='application/zip'); r['Content-Disposition'] = 'attachment; filename="Lote.zip"'; return r
    else: form = CarimboForm()
    return render(request, 'carimbo.html', {'form': form, 'colaborador': colab, 'user_full_name': user_full_name, 'instrumentos': instrumentos_disponiveis})

def apply_stamp_logic(f, user, status, ui, dt):
    ipdf = PdfReader(f); o = PdfWriter(); p = ipdf.pages[0] if ipdf.pages else None
    if p:
        try: pw = float(p.mediabox.width); ph = float(p.mediabox.height)
        except: pw=595.0; ph=842.0
        sx, sy, sbw, sbh, sw, sh = ui
        fx = (sx*(pw/sw)) if sw>0 else pw-150; fy = (ph-(sy*(ph/sh))-(sbh*(ph/sh))) if sh>0 else 50
        b = io.BytesIO(); c = canvas.Canvas(b, pagesize=(pw, ph))
        c.setFillColor(RColor(0.8,0,0) if 'Reprovado' in status else RColor(0,0.5,0))
        c.setFont("Helvetica-Bold", 10); c.drawString(fx, fy+20, status)
        c.setFillColor(RColor(0,0,0)); c.setFont("Helvetica", 9); c.drawString(fx, fy+10, dt.strftime('%d/%m/%Y')); c.drawString(fx, fy, user)
        c.save(); b.seek(0); st = PdfReader(b); p.merge_page(st.pages[0]); o.add_page(p)
        for pg in ipdf.pages[1:]: o.add_page(pg)
    out = io.BytesIO(); o.write(out); out.seek(0); return out

# --- TEMPLATES ---
def dl_template_instr(request): return dl_generic(["TAG","EQUIPAMENTO","STATUS","FABRICANTE","MODELO","N SERIE","SETOR","LOCALIZACAO","FREQUENCIA_MESES","DATA_ULTIMA_CALIBRACAO","FAIXA","UNIDADE"], "template_instrumentos_v2.xlsx")
def dl_template_colab(request): 
    df = pd.DataFrame({'MATRICULA':['100'], 'NOME':['TESTE'], 'CPF':['000'], 'CARGO':['Y'], 'GRUPO':['ADM'], 'SETOR':['ADM'], 'CC':['100'], 'TURNO':['ADM'], 'STATUS':['ATIVO'], 'MAT_LIDER': ['999'], 'MAT_SUPERVISOR': ['888'], 'MAT_GERENTE': ['777']})
    return dl_df(df, "template_colaboradores.xlsx")
def dl_template_hierarquia(request): return dl_df(pd.DataFrame({'SETOR': ['MAN'], 'TURNO': ['T1'], 'MAT_LIDER': ['1'], 'MAT_SUPERVISOR': [''], 'MAT_GERENTE': [''], 'MAT_DIRETOR': ['']}), "template_hierarquia.xlsx")
def dl_template_historico(request): return dl_generic(["TAG","DATA CALIBRAÇÃO","DATA APROVAÇÃO","N CERTIFICADO","ERRO ENCONTRADO","INCERTEZA","TOLERANCIA PROCESSO (+/-)","RBC (SIM/NAO)","RESULTADO","FORNECEDOR","RESPONSÁVEL","OBSERVAÇÕES"], "template_historico.xlsx")

def dl_generic(cols, fname): df = pd.DataFrame(columns=cols); return dl_df(df, fname)
def dl_df(df, fname): b = io.BytesIO(); df.to_excel(b, index=False); b.seek(0); r = HttpResponse(b, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'); r['Content-Disposition'] = f'attachment; filename="{fname}"'; return r

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
                            val = get_val(k_list); 
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
                        
                        dados = {
                            'codigo': tag, 
                            'descricao': get_val(['EQUIPAMENTO', 'DESCRIÇÃO', 'DESCRICAO']) or 'Sem Descrição', 
                            'categoria': cat, 
                            'fabricante': get_val(['FABRICANTE', 'MARCA']), 
                            'modelo': get_val(['MODELO']), 
                            'serie': get_val(['N SERIE', 'N° DE SÉRIE', 'N DE SERIE', 'SÉRIE', 'SERIE']), 
                            'setor': setor, 
                            'localizacao': get_val(['LOCALIZAÇÃO', 'LOCALIZACAO', 'AREA']), 
                            'frequencia_meses': freq_meses, 
                            'data_ultima_calibracao': dt_ultima, 
                            'data_proxima_calibracao': dt_proxima, 
                            'ativo': True
                        }
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
                df.columns = df.columns.str.strip().str.upper(); df.columns = df.columns.str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
                count_new = 0; relatorio_erros = []
                with transaction.atomic():
                    for index, row in df.iterrows():
                        linha = index + 2
                        def encontrar_coluna(palavras_chave, evitar=[]):
                            for col in df.columns:
                                match = False
                                for k in palavras_chave:
                                    k_clean = k.upper().replace('Ç','C').replace('Ã','A').replace('Á','A').replace('É','E')
                                    if k_clean in col: match = True; break
                                if match:
                                    proibido = False
                                    for bad in evitar:
                                        if bad.upper() in col: proibido = True; break
                                    if not proibido: return col
                            return None
                        def get_val_by_col(col_name): return str(row[col_name]).strip() if col_name and pd.notna(row[col_name]) else None
                        def converter_data(valor):
                            if not valor or str(valor).strip() in ['-', 'NaT', 'nan', 'None', '']: return None
                            try: return pd.to_datetime(str(valor).strip(), dayfirst=True).date()
                            except: 
                                try: return (datetime(1899, 12, 30) + timedelta(days=float(valor))).date()
                                except: return None
                        def get_float_by_col(col_name):
                            val = get_val_by_col(col_name)
                            if not val: return None
                            try: return float(re.sub(r'[^\d,.-]', '', val).replace(',', '.'))
                            except: return None
                        col_tag = encontrar_coluna(['TAG', 'CODIGO', 'IDENTIFICACAO'])
                        col_dt_cal = encontrar_coluna(['DATA CALIB', 'DATA ULTIMA', 'REALIZADO', 'CALIBRACAO'], evitar=['PROXIMA', 'VENCIMENTO', 'VALIDADE'])
                        tag = get_val_by_col(col_tag)
                        dt_cal = converter_data(row.get(col_dt_cal)) if col_dt_cal else None
                        if not tag: continue
                        if not dt_cal: relatorio_erros.append(f"L.{linha} ({tag}): Data inválida."); continue
                        try: inst = Instrumento.objects.get(tag=tag)
                        except: relatorio_erros.append(f"L.{linha}: Instrumento não cadastrado."); continue
                        col_dt_apr = encontrar_coluna(['DATA APROVACAO', 'DATA VALIDACAO', 'AVALIACAO'])
                        val_apr = converter_data(row.get(col_dt_apr)) if col_dt_apr else None
                        dt_apr = val_apr if val_apr else dt_cal
                        col_cert = encontrar_coluna(['CERTIFICADO', 'N DOC'], evitar=['DATA'])
                        num_cert = get_val_by_col(col_cert) or 'S/N'
                        col_erro = encontrar_coluna(['ERRO', 'TENDENCIA'])
                        col_inc = encontrar_coluna(['INCERTEZA', 'U'])
                        col_tol = encontrar_coluna(['TOLERANCIA', 'CRITERIO', 'EMA'], evitar=['NOMINAL'])
                        erro = get_float_by_col(col_erro)
                        inc = get_float_by_col(col_inc)
                        tol = get_float_by_col(col_tol)
                        col_resp = encontrar_coluna(['RESPONSAVEL', 'APROVADOR', 'ANALISE'])
                        resp_txt = get_val_by_col(col_resp)
                        col_forn = encontrar_coluna(['FORNECEDOR', 'LABORATORIO'])
                        forn_txt = get_val_by_col(col_forn)
                        col_res = encontrar_coluna(['RESULTADO', 'STATUS', 'ANALISE RESULTADO'])
                        res_excel = str(get_val_by_col(col_res) or '').upper()
                        res = 'APROVADO'
                        if 'REPROVADO' in res_excel: res = 'REPROVADO'
                        elif 'CONDICIONAL' in res_excel or 'RESTR' in res_excel: res = 'CONDICIONAL'
                        val_tipo = 'EXTERNA' 
                        if forn_txt and 'INTERNA' in str(forn_txt).upper(): val_tipo = 'INTERNA'
                        col_rbc = encontrar_coluna(['RBC', 'SELO', 'ACREDITADO'])
                        val_rbc = str(get_val_by_col(col_rbc) or '').upper()
                        tem_rbc = True if val_rbc in ['SIM', 'S', 'YES', 'RBC'] else False
                        col_prox = encontrar_coluna(['PROXIMA', 'VENCIMENTO'])
                        prox = converter_data(row.get(col_prox)) if col_prox else None
                        if not prox and inst.frequencia_meses and dt_cal:
                            try: prox = dt_cal + timedelta(days=inst.frequencia_meses*30)
                            except: prox = None
                        obj, cr = HistoricoCalibracao.objects.update_or_create(
                            instrumento=inst, data_calibracao=dt_cal, numero_certificado=num_cert, 
                            defaults={'data_aprovacao': dt_apr, 'resultado': res, 'proxima_calibracao': prox, 'erro_encontrado': erro, 'incerteza': inc, 'tolerancia_usada': tol, 'responsavel': resp_txt, 'fornecedor': forn_txt, 'tipo_calibracao': val_tipo, 'tem_selo_rbc': tem_rbc, 'observacoes': get_val_by_col(encontrar_coluna(['OBSERVACOES', 'OBS']))}
                        )
                        if erro is not None and inc is not None and tol is not None: obj.save()
                        if cr: count_new += 1
                if relatorio_erros: msg = " | ".join(relatorio_erros[:3]); messages.warning(request, f"Importados: {count_new}. Alertas: {msg}")
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
                        codigo = str(row.get('CODIGO', '')).strip()
                        if codigo:
                            Padrao.objects.update_or_create(codigo=codigo, defaults={'descricao': 'Importado', 'ativo': True})
                            count += 1
                messages.success(request, f"{count} Padrões importados!")
                return redirect('modulo_metrologia')
            except Exception as e: messages.error(request, f"Erro: {e}")
    else: form = ImportacaoPadroesForm()
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
                count_new = 0; count_upd = 0; count_lider = 0
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
                        cpf_raw = get_val(['CPF', 'DOC'])
                        cpf = None
                        if cpf_raw:
                            limpo = re.sub(r'[^0-9]', '', str(cpf_raw))
                            if len(limpo) == 11 and limpo != '00000000000' and limpo != '00': cpf = limpo
                        setor_nome = get_val(['SETOR', 'DEPARTAMENTO', 'AREA'])
                        setor_obj = None
                        if setor_nome: setor_obj, _ = Setor.objects.get_or_create(nome=setor_nome.upper())
                        cc_raw = get_val(['CENTRO DE CUSTO', 'CC'])
                        cc_obj = None
                        if cc_raw and setor_obj:
                            parts = cc_raw.split('-')
                            c_code = parts[0].strip()
                            c_desc = parts[1].strip() if len(parts) > 1 else "Importado"
                            cc_obj, _ = CentroCusto.objects.get_or_create(codigo=c_code, setor=setor_obj, defaults={'descricao': c_desc})
                        turno_raw = str(get_val(['TURNO', 'HORARIO']) or 'ADM').upper()
                        turno = 'ADM'
                        if '1' in turno_raw: turno = 'TURNO_1'
                        elif '2' in turno_raw: turno = 'TURNO_2'
                        elif '3' in turno_raw: turno = 'TURNO_3'
                        elif '12' in turno_raw: turno = '12X36'
                        status_raw = str(get_val(['STATUS']) or 'ATIVO').upper()
                        is_active = False if 'INATIVO' in status_raw or 'DEMITIDO' in status_raw else True
                        sal_raw = get_val(['SALARIO'])
                        salario = float(sal_raw.replace(',', '.')) if sal_raw else None
                        obj, created = Colaborador.objects.update_or_create(
                            matricula=matricula,
                            defaults={'nome_completo': nome.upper(), 'cpf': cpf, 'cargo': get_val(['CARGO', 'FUNCAO']) or 'Não Informado', 'grupo': get_val(['GRUPO', 'MACRO']) or 'Geral', 'setor': setor_obj, 'centro_custo': cc_obj, 'turno': turno, 'salario': salario, 'is_active': is_active}
                        )
                        if created: count_new += 1
                        else: count_upd += 1
                    for index, row in df.iterrows():
                        def get_val_h(keywords):
                            for k in keywords:
                                for col in df.columns:
                                    if k in col and pd.notna(row[col]): return str(row[col]).strip()
                            return None
                        matricula = get_val_h(['MATRICULA', 'MAT', 'RE'])
                        if matricula: matricula = matricula.split('.')[0]
                        mat_chefe = None
                        cand_lider = get_val_h(['MAT_LIDER', 'LIDER', 'COD_LIDER'])
                        if cand_lider: mat_chefe = cand_lider.split('.')[0]
                        if not mat_chefe:
                            cand_super = get_val_h(['MAT_SUPERVISOR', 'SUPERVISOR'])
                            if cand_super: mat_chefe = cand_super.split('.')[0]
                        if not mat_chefe:
                            cand_gerente = get_val_h(['MAT_GERENTE', 'GERENTE'])
                            if cand_gerente: mat_chefe = cand_gerente.split('.')[0]
                        if matricula and mat_chefe and matricula != mat_chefe:
                            try:
                                colab = Colaborador.objects.get(matricula=matricula)
                                lider = Colaborador.objects.get(matricula=mat_chefe)
                                colab.lider = lider
                                colab.save(update_fields=['lider'])
                                count_lider += 1
                            except Colaborador.DoesNotExist: pass
                messages.success(request, f"RH: {count_new} Novos, {count_upd} Atu, {count_lider} Vínculos Hierárquicos.")
                return redirect('modulo_rh')
            except Exception as e: messages.error(request, f"Erro na importação: {str(e)}")
    else: form = ImportacaoColaboradoresForm()
    return render(request, 'importar_colaboradores.html', {'form': form, 'colaborador': get_colab(request)})

# --- NOVA VIEW: IMPORTAÇÃO DE FÉRIAS (ADICIONADO AGORA) ---
@login_required
def imp_ferias_view(request):
    if request.method == 'POST':
        form = ImportacaoFeriasForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                f = request.FILES['arquivo_excel']
                try: df = pd.read_excel(f)
                except: df = pd.read_csv(f, sep=None, engine='python')
                
                df.columns = df.columns.str.strip().str.upper()
                count = 0
                
                with transaction.atomic():
                    for _, row in df.iterrows():
                        # 1. Encontra o Colaborador
                        def get_v(k): return str(row.get(k,'')).strip()
                        matricula = get_v('MATRICULA')
                        if not matricula: continue
                        
                        try: colab = Colaborador.objects.get(matricula=matricula.split('.')[0])
                        except Colaborador.DoesNotExist: continue
                        
                        # 2. Processa Datas
                        def parse_dt(col):
                            val = get_v(col)
                            if not val or val in ['-','NaT','nan']: return None
                            try: return pd.to_datetime(val, dayfirst=True).date()
                            except: return None
                            
                        dt_aq_ini = parse_dt('AQUISITIVO_INICIO')
                        dt_aq_fim = parse_dt('AQUISITIVO_FIM')
                        dt_ini = parse_dt('DATA_INICIO')
                        dt_fim = parse_dt('DATA_FIM')
                        
                        if not dt_aq_fim: continue # Obrigatório ter referência do período
                        
                        # 3. Cria/Atualiza Registro de Férias
                        Ferias.objects.update_or_create(
                            colaborador=colab,
                            periodo_aquisitivo_fim=dt_aq_fim,
                            defaults={
                                'periodo_aquisitivo_inicio': dt_aq_ini,
                                'data_inicio': dt_ini,
                                'data_fim': dt_fim,
                                'status': get_v('STATUS') or 'PROGRAMADAS'
                            }
                        )
                        count += 1
                        
                messages.success(request, f"{count} registros de férias importados!")
                return redirect('modulo_rh')
            except Exception as e: messages.error(request, f"Erro: {e}")
    else:
        form = ImportacaoFeriasForm()
    return render(request, 'importar_ferias.html', {'form': form, 'colaborador': get_colab(request)})

@login_required
def imp_hierarquia_view(request):
    if request.method == 'POST': messages.success(request, "Hierarquia OK"); return redirect('modulo_rh')
    return render(request, 'importar_hierarquia.html', {'form': ImportacaoHierarquiaForm(), 'colaborador': get_colab(request)})