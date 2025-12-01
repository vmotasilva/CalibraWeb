
import io
from django.shortcuts import get_object_or_404
import os
import re
import zipfile
from datetime import date, datetime, timedelta
import tempfile
from decimal import Decimal
import unicodedata
from django.contrib.auth.decorators import login_required

@login_required
def imp_instr_view(request):
    """
    Importa instrumentos de calibração a partir de arquivo Excel/CSV.
    Para garantir que as faixas de medição (com tolerância) sejam importadas junto com os instrumentos,
    é necessário ajustar a task 'import_instruments_task' (em qms/tasks.py) para processar as colunas de faixas
    e criar/atualizar objetos FaixaMedicao associados ao Instrumento.

    Se o arquivo de importação já possui colunas como 'FAIXA', 'UNIDADE', 'TOLERANCIA_MAIS_MENOS', etc.,
    adapte a task para ler essas colunas e criar as faixas.
    """
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
               
                # create import job record
                job = ImportJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    filename=uploaded.name,
                    filepath=tmp.name,
                    job_type="INSTRUMENTOS",
                    status="PENDING",
                )

                # ATENÇÃO: Para importar faixas de medição, ajuste a task import_instruments_task
                # para processar as colunas de faixas e criar FaixaMedicao para cada instrumento.

                # Execução síncrona forçada se SYNC_IMPORTS=1 (default) ou se Celery falhar
                from .tasks import import_instruments_task
                force_sync = os.environ.get("SYNC_IMPORTS", "1") == "1"
                if not force_sync:
                    try:
                        # ...existing code...
                        return redirect("modulo_metrologia")
                    except Exception:
                        force_sync = True
                if force_sync:
                    import_instruments_task(job.id, tmp.name)
                    job.refresh_from_db()
                    messages.success(request, f"Importação concluída imediatamente (job {job.id}). {job.result or ''}")
                    return redirect("modulo_metrologia")
            except Exception as e:
                messages.error(request, f"Erro ao enfileirar importação: {str(e)}")
                return redirect("importar_instrumentos")
    else:
        form = ImportacaoInstrumentosForm()
    return render(
        request,
        "importar_instrumentos.html",
        {"form": form, "jobs": ImportJob.objects.order_by('-created_at')[:5]},
    )
    try:
        col = Colaborador.objects.get(user_django=u)
        return col
    except Colaborador.DoesNotExist:
        pass
    except Exception:
        pass

    def norm(s: str) -> str:
        if not s:
            return ""
        s = unicodedata.normalize('NFD', s)
        s = ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn')
        s = re.sub(r"[^A-Za-z0-9\s]", " ", s)
        s = re.sub(r"\s+", " ", s).strip().upper()
        return s

    fn = (u.first_name or "").strip()
    ln = (u.last_name or "").strip()

    # 2) FIRST+LAST iexact
    if fn and ln:
        nome_montado = f"{fn} {ln}".strip()
        c = Colaborador.objects.filter(nome_completo__iexact=nome_montado).first()
        if c:
            # vincula se possível
            try:
                if c.user_django_id is None:
                    c.user_django = u
                    c.save(update_fields=["user_django"])
            except Exception:
                pass
            return c

    # 3) prefixo/sufixo ignorando acentos
    if fn and ln:
        fn_n = norm(fn)
        ln_n = norm(ln)
        candidatos = []
        for c in Colaborador.objects.all().only("id", "nome_completo"):
            nc = norm(c.nome_completo)
            if nc.startswith(fn_n + " ") and nc.endswith(" " + ln_n):
                candidatos.append(c)
        if len(candidatos) == 1:
            c = candidatos[0]
            try:
                if c.user_django_id is None:
                    c.user_django = u
                    c.save(update_fields=["user_django"])
            except Exception:
                pass
            return c

    # 4) username == matricula
    if u.username:
        c = Colaborador.objects.filter(matricula__iexact=u.username).first()
        if c:
            try:
                if c.user_django_id is None:
                    c.user_django = u
                    c.save(update_fields=["user_django"])
            except Exception:
                pass
            return c
    return None


def excel_date_to_datetime(serial):
    if pd.isnull(serial) or str(serial).strip() == "" or str(serial).strip() == "-":
        return None
    try:
        serial_str = str(serial).strip()
        if "/" in serial_str:
            return pd.to_datetime(serial_str, dayfirst=True).date()
        serial_float = float(serial)
        return (datetime(1899, 12, 30) + timedelta(days=serial_float)).date()
    except:
        return None


def get_all_subordinates(colaborador):
    """
    Retorna um SET com os IDs de todos os subordinados (diretos e indiretos)
    de um colaborador, descendo toda a árvore hierárquica.
    """
    subordinados = set()
    diretos = colaborador.liderados.all()
    for direto in diretos:
        subordinados.add(direto.id)
        subordinados.update(get_all_subordinates(direto))
    return subordinados


# ==============================================================================
# VIEWS DE TELA (DASHBOARD E MÓDULOS)
# ==============================================================================


@login_required
def dashboard_view(request):
    nome_display = request.user.username
    hoje = date.today()
    trinta_dias = hoje + timedelta(days=30)

    qtd_vencidos = Instrumento.objects.filter(
        data_proxima_calibracao__lt=hoje, ativo=True
    ).count()
    qtd_avencer = Instrumento.objects.filter(
        data_proxima_calibracao__range=[hoje, trinta_dias], ativo=True
    ).count()
    lista_urgentes = Instrumento.objects.filter(
        data_proxima_calibracao__lte=trinta_dias, ativo=True
    ).order_by("data_proxima_calibracao")[:5]

    # NOVO: Contagem de solicitações pendentes
    qtd_pendentes = SolicitacaoInstrumento.objects.filter(status="PENDENTE").count()

    ctx = {
        "nome_display": nome_display,
        "qtd_vencidos": qtd_vencidos,
        "qtd_avencer": qtd_avencer,
        "lista_urgentes": lista_urgentes,
        "qtd_cotacoes": ProcessoCotacao.objects.filter(status="ABERTO").count(),
        "qtd_pendentes": qtd_pendentes,  # <--- Adicionado ao contexto
        "today": hoje,
    }
    return render(request, "dashboard.html", ctx)


@login_required
def modulo_metrologia_view(request):
    # Busca instrumentos (inclui ativos e inativos para permitir filtro na interface)
    instrumentos = Instrumento.objects.all().select_related('categoria','setor').order_by("tag")

    # Filtro opcional de status de atividade (st=ATIVO, st=INATIVO ou ambos separados por vírgula)
    st_param = (request.GET.get('st') or '').upper()
    if st_param:
        parts = {p.strip() for p in st_param.split(',') if p.strip()}
        if 'ATIVO' in parts and 'INATIVO' not in parts:
            instrumentos = instrumentos.filter(ativo=True)
        elif 'INATIVO' in parts and 'ATIVO' not in parts:
            instrumentos = instrumentos.filter(ativo=False)
        # Se ambos presentes, mantém todos

    # --- Parâmetro vindo do dashboard: apenas pré-seleciona situação no cliente ---
    status_filter = request.GET.get("status")  # "vencidos" | "avencer"
    hoje = date.today()
    alerta_30d = hoje + timedelta(days=30)
    if status_filter == "vencidos":
        messages.info(request, "Filtro sugerido: VENCIDOS (aplicado na interface).")
    elif status_filter == "avencer":
        messages.info(request, "Filtro sugerido: A Vencer (30d) (aplicado na interface).")

    # Preparação dos Filtros (Extraindo valores únicos presentes na base completa)
    setores_ids = Instrumento.objects.all().values_list("setor", flat=True).distinct()
    setores_filtro = Setor.objects.filter(id__in=setores_ids).order_by("nome")

    categorias_ids = Instrumento.objects.all().values_list("categoria", flat=True).distinct()
    categorias_filtro = CategoriaInstrumento.objects.filter(
        id__in=categorias_ids
    ).order_by("nome")

    # Datas de referência para o template calcular status (Vencido/A Vencer)
    hoje = date.today()
    alerta_30d = hoje + timedelta(days=30)

    ctx = {
        "instrumentos": instrumentos,
        "setores_filtro": setores_filtro,
        "categorias_filtro": categorias_filtro,
        "hoje": hoje,
        "alerta_30d": alerta_30d,
        "can_edit": True,
    }
    return render(request, "modulo_metrologia.html", ctx)


@login_required
def export_metrologia_view(request):
    """Exporta os instrumentos (respeitando filtros por querystring) para Excel."""
    q = (request.GET.get('q') or '').strip().lower()
    st = set((request.GET.get('st') or '').split(',')) if request.GET.get('st') else set()
    sit = set((request.GET.get('sit') or '').split(',')) if request.GET.get('sit') else set()
    cat = set((request.GET.get('cat') or '').split(',')) if request.GET.get('cat') else set()
    st_setor = set((request.GET.get('set') or '').split(',')) if request.GET.get('set') else set()

    qs = Instrumento.objects.all().select_related('categoria','setor').prefetch_related('faixas','faixas__unidade')
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
        qs = qs.filter(models.Q(tag__icontains=q) | models.Q(descricao__icontains=q) | models.Q(fabricante__icontains=q) | models.Q(modelo__icontains=q))

    # Situação (vencido/avencer/em_dia) é derivada de datas - filtra após fetch
    hoje = date.today()
    alerta_30d = hoje + timedelta(days=30)
    rows = []
    for inst in qs:
        situacao = 'EM_DIA'
        if inst.data_proxima_calibracao:
            if inst.data_proxima_calibracao < hoje:
                situacao = 'VENCIDO'
            elif inst.data_proxima_calibracao <= alerta_30d:
                situacao = 'AVENCER'
        if sit and situacao not in sit:
            continue
        unidade = ''
        try:
            fx = inst.faixas.all().first()
            if fx and fx.unidade:
                unidade = fx.unidade.sigla
        except Exception:
            unidade = ''
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
    import pandas as pd
    import io
    b = io.BytesIO()
    df = pd.DataFrame(rows)
    df.to_excel(b, index=False, engine='openpyxl')
    b.seek(0)
    r = HttpResponse(b, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    r['Content-Disposition'] = 'attachment; filename="instrumentos_export.xlsx"'
    return r


@login_required
def export_etiquetas_view(request):
    """Gera um PDF A4 com etiquetas dos instrumentos filtrados.

    Query params:
      - orient: 'portrait' (default) ou 'landscape'
      - cols: número de colunas (default 2)
      - rows: número de linhas (default 5)
      - margin_mm: margem externa em mm (default 10)
      - pad_mm: espaçamento interno entre etiquetas em mm (default 5)
    Respeita os mesmos filtros de export_metrologia_view: q, st, sit, cat, set.
    """
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

    # Filtro base igual ao Excel
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
        qs = qs.filter(models.Q(tag__icontains=q) | models.Q(descricao__icontains=q) | models.Q(fabricante__icontains=q) | models.Q(modelo__icontains=q))

    # Se houver lista explícita de IDs selecionados, prioriza apenas esses
    selected_ids = []
    try:
        raw_ids = (request.GET.get('ids') or '').strip()
        if raw_ids:
            selected_ids = [int(x) for x in raw_ids.split(',') if x.strip().isdigit()]
    except Exception:
        selected_ids = []

    # Situação derivada
    hoje = date.today()
    alerta_30d = hoje + timedelta(days=30)
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
                situacao = 'AVENCER'
        if sit and situacao not in sit:
            continue
        instrumentos.append((inst, situacao))

    # Monta PDF
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

    # Optional: load template positions from config file for exact layout
    template_cfg = None
    try:
        import json
        cfg_path = os.path.join(os.path.dirname(__file__), 'label_template.json')
        if os.path.exists(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as fh:
                template_cfg = json.load(fh)
    except Exception:
        template_cfg = None

    def draw_label(x, y, inst, situacao):
        # Label frame
        c.setLineWidth(1)
        c.rect(x, y, cell_w, cell_h)

        # Compute last calibration date and last certificate number
        last_calib_date = getattr(inst, 'data_ultima_calibracao', None)
        last_cert_num = ''
        if not last_calib_date or not isinstance(last_calib_date, (date, datetime)):
            last_calib_date = None
        try:
            hist_qs = getattr(inst, 'historico_calibracoes', None)
            if hist_qs is not None:
                last_hist = hist_qs.order_by('-data_calibracao').first()
                if last_hist:
                    if not last_calib_date:
                        last_calib_date = last_hist.data_calibracao
                    last_cert_num = last_hist.numero_certificado or ''
        except Exception:
            pass
        calib_str = last_calib_date.strftime('%d/%m/%Y') if last_calib_date else ''
        prox_str = inst.data_proxima_calibracao.strftime('%m/%Y') if getattr(inst, 'data_proxima_calibracao', None) else ''

        if template_cfg:
            # Optional background image (PNG) to match exact artwork
            try:
                bg_img = template_cfg.get('background_image')
                if bg_img:
                    # Resolve path relative to project root
                    img_path = bg_img
                    if not os.path.isabs(img_path):
                        # Try relative to repo root
                        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
                        candidate = os.path.join(repo_root, img_path)
                        if os.path.exists(candidate):
                            img_path = candidate
                    c.drawImage(img_path, x, y, width=cell_w, height=cell_h, preserveAspectRatio=True, anchor='sw')
            except Exception:
                pass
            # Use exact positions from template config (relative 0..1 in the label box)
            def rel(px, py):
                return (x + px * cell_w, y + py * cell_h)
            # Header bar
            hb = template_cfg.get('header_bar', {'h': 0.08})
            bar_h = cell_h * float(hb.get('h', 0.08))
            c.setFillColor(RColor(0,0,0))
            c.rect(x, y+cell_h-bar_h, cell_w, bar_h, fill=1, stroke=0)
            c.setFillColor(RColor(1,1,1))
            c.setFont(template_cfg.get('header_font','Helvetica-Bold'), int(template_cfg.get('header_size', 12)))
            tx, ty = rel(0.02, 1 - (bar_h/cell_h) + 0.02)
            c.drawString(tx, ty, template_cfg.get('header_left', ''))
            rx, ry = rel(0.98, 1 - (bar_h/cell_h) + 0.02)
            c.drawRightString(rx, ry, template_cfg.get('header_right', 'FOR.152.R1'))
            # Bullets
            c.setFillColor(RColor(0,0,0))
            c.setFont(template_cfg.get('label_font','Helvetica-Bold'), int(template_cfg.get('label_size', 11)))
            b1 = template_cfg.get('bullet_calibracao', {'x':0.05,'y':0.82})
            b2 = template_cfg.get('bullet_verificacao', {'x':0.45,'y':0.82})
            c.circle(x + float(b1['x'])*cell_w, y + float(b1['y'])*cell_h, 5, stroke=1, fill=1)
            c.drawString(x + (float(b1['x'])*cell_w) + 12, y + (float(b1['y'])*cell_h) - 3, 'Calibração')
            c.circle(x + float(b2['x'])*cell_w, y + float(b2['y'])*cell_h, 5, stroke=1, fill=0)
            c.drawString(x + (float(b2['x'])*cell_w) + 12, y + (float(b2['y'])*cell_h) - 3, 'Verificação')
            # Fields
            c.setFont(template_cfg.get('field_font','Helvetica'), int(template_cfg.get('field_size', 9)))
            fields = template_cfg.get('fields', [
                {'label':'Cód do instrumento:', 'x':0.03, 'y':0.70},
                {'label':'N° Certificado:', 'x':0.03, 'y':0.60},
                {'label':'Realizado em:', 'x':0.03, 'y':0.50},
                {'label':'Vencimento (mês/ano):', 'x':0.03, 'y':0.40},
            ])
            values = [
                inst.tag or '',
                last_cert_num,
                calib_str,
                prox_str,
            ]
            for idx, f in enumerate(fields):
                fx, fy = rel(float(f.get('x',0.03)), float(f.get('y',0.70)))
                c.drawString(fx, fy, f.get('label',''))
                # underline
                line_start = fx + 110
                c.line(line_start, fy-2, x+cell_w-10, fy-2)
                val = values[idx] if idx < len(values) else ''
                if val:
                    c.drawString(line_start + 5, fy, val)
            # Removed status badge on label per request
        else:
            # Fallback generic layout
            bar_h = 18
            c.setFillColor(RColor(0,0,0))
            c.rect(x, y+cell_h-bar_h, cell_w, bar_h, fill=1, stroke=0)
            c.setFillColor(RColor(1,1,1))
            c.setFont('Helvetica-Bold', 12)
            c.drawString(x+6, y+cell_h-bar_h+4, (inst.setor.nome if inst.setor else 'Metrologia'))
            c.drawRightString(x+cell_w-6, y+cell_h-bar_h+4, (inst.categoria.nome if inst.categoria else 'FOR.152.R1'))
            c.setFillColor(RColor(0,0,0))
            c.setFont('Helvetica-Bold', 11)
            cx = x+12; cy = y+cell_h- bar_h - 12
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
            # Removed status badge in fallback layout

    i = 0
    for inst, situ in instrumentos:
        r = (i // cols) % rows
        cidx = i % cols
        # Page break
        if i and (i // (cols*rows)) != ((i-1) // (cols*rows)):
            c.showPage()
        # Compute origin for this cell on current page
        page_index = i // (cols*rows)
        # within current page, compute row/col
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


@login_required
def modulo_rh_view(request):
    colab = None
    try:
        colab = Colaborador.objects.filter(user_django=request.user).first()
    except Exception:
        pass

    # 1. VISIBILIDADE (quem pode ver TODOS e quem vê sua árvore)
    ids_permitidos = set()
    can_see_salary = False

    can_view_all = False
    if request.user.is_superuser:
        can_view_all = True
    elif colab:
        setor_nome = (colab.setor.nome.upper() if colab.setor else "")
        if any(k in setor_nome for k in ["RH", "DP", "QUALIDADE"]):
            can_view_all = True
        elif (
            "GERENTE" in str(colab.cargo).upper()
            or HierarquiaSetor.objects.filter(gerente=colab).exists()
        ):
            can_view_all = True

    if can_view_all:
        ids_permitidos = set(Colaborador.objects.all().values_list("id", flat=True))
    elif colab:
        # Inclui subordinados diretos (por relação de líder) e a própria pessoa
        ids_permitidos = get_all_subordinates(colab)
        ids_permitidos.add(colab.id)
        # Também inclui quem o usuário lidera/supervisiona/gerencia diretamente
        diretos = Colaborador.objects.filter(
            Q(lider=colab) | Q(supervisor=colab) | Q(gerente=colab)
        ).values_list('id', flat=True)
        ids_permitidos.update(diretos)
    else:
        ids_permitidos = set()

    # Regra 2.2: salário/CPF apenas para superusuários, gerentes e diretores
    if request.user.is_superuser:
        can_see_salary = True
    elif colab:
        if "GERENTE" in str(colab.cargo).upper() or \
           HierarquiaSetor.objects.filter(gerente=colab).exists() or \
           ("DIRETOR" in str(colab.cargo).upper()) or \
           HierarquiaSetor.objects.filter(diretor=colab).exists():
            can_see_salary = True

    # QuerySet BASE: inclui ativos e desligados; filtro por ids_permitidos
    funcionarios_base = Colaborador.objects.filter(
        id__in=list(ids_permitidos)
    ).select_related('setor', 'centro_custo', 'lider', 'supervisor', 'gerente').prefetch_related('treinamentos', 'treinamentos__procedimento').order_by("nome_completo")

    # 2. CÁLCULO DAS OPÇÕES DE FILTRO - BASEADO APENAS NA BASE DE DADOS DE COLABORADORES
    
    # Setores: Pega todos os setores únicos dos colaboradores visíveis
    setores_ids = funcionarios_base.exclude(setor__isnull=True).values_list("setor", flat=True).distinct()
    setores_filtro = Setor.objects.filter(id__in=setores_ids).order_by("nome")

    # Líderes: Pega todos os líderes únicos dos colaboradores visíveis
    lideres_ids = funcionarios_base.exclude(lider__isnull=True).values_list("lider", flat=True).distinct()
    lideres_filtro = Colaborador.objects.filter(id__in=lideres_ids).order_by("nome_completo")

    # Supervisores: Pega todos os supervisores únicos dos colaboradores visíveis
    supervisores_ids = funcionarios_base.exclude(supervisor__isnull=True).values_list("supervisor", flat=True).distinct()
    supervisores_filtro = Colaborador.objects.filter(id__in=supervisores_ids).order_by("nome_completo")

    # Gerentes: Pega todos os gerentes únicos dos colaboradores visíveis
    gerentes_ids = funcionarios_base.exclude(gerente__isnull=True).values_list("gerente", flat=True).distinct()
    gerentes_filtro = Colaborador.objects.filter(id__in=gerentes_ids).order_by("nome_completo")

    # Turnos: Pega todos os turnos únicos dos colaboradores visíveis
    turnos_unicos = funcionarios_base.values_list("turno", flat=True).distinct()
    # Usa choices do próprio modelo para evitar depender de constantes globais
    turnos_map = dict(Colaborador._meta.get_field('turno').choices)
    turnos_filtro = [(turno, turnos_map.get(turno, turno)) for turno in turnos_unicos if turno]

    # 3. RESULTADO FINAL
    funcionarios_visiveis = funcionarios_base

    # 4. Estatísticas de Treinamento por colaborador (pendentes/vigentes, última data)
    for f in funcionarios_visiveis:
        vig = 0
        pend = 0
        last = None
        for rt in getattr(f, 'treinamentos').all():
            if rt.status_treinamento == "VIGENTE":
                vig += 1
            else:
                pend += 1
            if rt.data_treinamento and (last is None or rt.data_treinamento > last):
                last = rt.data_treinamento
        # Atribui no próprio objeto para fácil acesso no template
        f.trein_vigentes = vig
        f.trein_pendentes = pend
        f.trein_ultima_data = last

    ctx = {
        "funcionarios": funcionarios_visiveis,
        "lideres_filtro": lideres_filtro,
        "setores_filtro": setores_filtro,
        "supervisores_filtro": supervisores_filtro,
        "gerentes_filtro": gerentes_filtro,
        "turnos_filtro": turnos_filtro,
        "centros": CentroCusto.objects.all().order_by("codigo"),
        "can_see_salary": can_see_salary,
        "can_edit": True,
    }
    return render(request, "modulo_rh.html", ctx)


@login_required
def procedimentos_list_view(request):
    """Lista de Procedimentos com filtros avançados.
        GET params:
            q: busca em código / nome
            setor: setor id
            area: area id
            rev: revisão exata
            elaborador / revisor / aprovador: colaborador id
    """
    termo = (request.GET.get('q') or '').strip().upper()
    classificacao = (request.GET.get('classificacao') or '').strip().upper()
    setor_id = request.GET.get('setor')
    area_id = request.GET.get('area')
    rev = (request.GET.get('rev') or '').strip()
    elaborador_id = request.GET.get('elaborador')
    revisor_id = request.GET.get('revisor')
    aprovador_id = request.GET.get('aprovador')

    qs = Procedimento.objects.all()
    if termo:
        qs = qs.filter(models.Q(codigo__icontains=termo) | models.Q(nome__icontains=termo))
    if classificacao:
        qs = qs.filter(classificacao__iexact=classificacao)
    if setor_id and setor_id.isdigit():
        qs = qs.filter(pasta__icontains=setor_id)  # Ajuste conforme novo modelo, se necessário
    if area_id and area_id.isdigit():
        qs = qs.filter(sub_area__icontains=area_id)  # Ajuste conforme novo modelo, se necessário
    if rev:
        qs = qs.filter(numero_revisao__iexact=rev)
    # Remover filtros de elaborador, revisor, aprovador se não existirem mais

    from django.core.paginator import Paginator
    page_number = request.GET.get('page','1')
    paginator = Paginator(qs.order_by('codigo'), 50)
    page_obj = paginator.get_page(page_number)
    procedimentos = page_obj.object_list

    # tipos_stats removido pois campo 'tipo' não existe mais

    ctx = {
        'procedimentos': procedimentos,
        'termo': termo,
        'classificacao': classificacao,
        'page_obj': page_obj,
        'paginator': paginator,
        'rev': rev,
        'setor_id': setor_id,
        'area_id': area_id,
        'querystring_base': '&'.join([p for p in [
            f"q={termo}" if termo else '',
            f"classificacao={classificacao}" if classificacao else '',
            f"setor={setor_id}" if setor_id else '',
            f"area={area_id}" if area_id else '',
            f"rev={rev}" if rev else '',
        ] if p])
    }
    return render(request, 'procedimentos_lista.html', ctx)


@login_required
def export_procedimentos_excel_view(request):
    # Reusa lógica de filtros
    termo = (request.GET.get('q') or '').strip().upper()
    classificacao = (request.GET.get('classificacao') or '').strip().upper()
    setor_id = request.GET.get('setor')
    area_id = request.GET.get('area')
    rev = (request.GET.get('rev') or '').strip()
    elaborador_id = request.GET.get('elaborador')
    revisor_id = request.GET.get('revisor')
    aprovador_id = request.GET.get('aprovador')
    qs = Procedimento.objects.all()
    if termo:
        qs = qs.filter(models.Q(codigo__icontains=termo) | models.Q(nome__icontains=termo))
    if classificacao:
        qs = qs.filter(classificacao__iexact=classificacao)
    if setor_id and setor_id.isdigit():
        qs = qs.filter(pasta__icontains=setor_id)  # Ajuste conforme novo modelo
    if area_id and area_id.isdigit():
        qs = qs.filter(sub_area__icontains=area_id)  # Ajuste conforme novo modelo
    if rev:
        qs = qs.filter(numero_revisao__iexact=rev)
    rows = []
    for p in qs.order_by('codigo'):
        rows.append({
            'CODIGO': p.codigo,
            'NOME': p.nome,
            'CLASSIFICACAO': p.classificacao,
            'NUMERO_REVISAO': p.numero_revisao,
            'ULTIMA_REVISAO': p.ultima_revisao.strftime('%Y-%m-%d') if p.ultima_revisao else '',
            'DATA_APROVACAO': p.data_aprovacao.strftime('%Y-%m-%d') if p.data_aprovacao else '',
            'PROXIMA_REVISAO': p.proxima_revisao.strftime('%Y-%m-%d') if p.proxima_revisao else '',
            'DATA_VALIDADE': p.data_validade.strftime('%Y-%m-%d') if p.data_validade else '',
            'PASTA': p.pasta,
            'AUTOR': p.autor,
            'DOCUMENTOS_CONTROLADOS': p.documentos_controlados,
            'MATRIZ': p.matriz,
            'SUB_AREA': p.sub_area,
        })
    import pandas as pd, io
    b = io.BytesIO()
    pd.DataFrame(rows).to_excel(b, index=False)
    b.seek(0)
    r = HttpResponse(b, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    r['Content-Disposition'] = 'attachment; filename="procedimentos_export.xlsx"'
    return r


@login_required
def export_procedimentos_pdf_view(request):
    # Simple tabular PDF using reportlab
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    termo = (request.GET.get('q') or '').strip().upper()
    classificacao = (request.GET.get('classificacao') or '').strip().upper()
    qs = Procedimento.objects.all()
    if termo:
        qs = qs.filter(models.Q(codigo__icontains=termo) | models.Q(nome__icontains=termo))
    if classificacao:
        qs = qs.filter(classificacao__iexact=classificacao)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 40
    c.setFont('Helvetica-Bold', 14)
    c.drawString(40, y, 'Relatório de Procedimentos')
    y -= 25
    c.setFont('Helvetica', 8)
    headers = ['Código','Nome','Classificação','Número Revisão','Última Revisão','Data Aprovação','Próxima Revisão','Data Validade','Pasta','Autor','Documentos Controlados','Matriz','Sub-Área']
    c.drawString(40, y, ' | '.join(headers))
    y -= 12
    c.setFont('Helvetica', 7)
    for p in qs.order_by('codigo'):
        line = [
            str(p.codigo or ''),
            (p.nome[:40] + ('...' if p.nome and len(p.nome)>40 else '')) if p.nome else '',
            str(p.classificacao or ''),
            str(p.numero_revisao or ''),
            p.ultima_revisao.strftime('%d/%m/%Y') if p.ultima_revisao else '',
            p.data_aprovacao.strftime('%d/%m/%Y') if p.data_aprovacao else '',
            p.proxima_revisao.strftime('%d/%m/%Y') if p.proxima_revisao else '',
            p.data_validade.strftime('%d/%m/%Y') if p.data_validade else '',
            str(p.pasta or ''),
            str(p.autor or ''),
            str(p.documentos_controlados or ''),
            str(p.matriz or ''),
            str(p.sub_area or ''),
        ]
        c.drawString(40, y, ' | '.join(line))
        y -= 10
        if y < 50:
            c.showPage(); y = h - 50; c.setFont('Helvetica', 7)
    c.showPage(); c.save(); buf.seek(0)
    r = HttpResponse(buf, content_type='application/pdf')
    r['Content-Disposition'] = 'attachment; filename="procedimentos.pdf"'
    return r


@login_required
def novo_procedimento_view(request):
    if not can_manage_procedimentos(request.user):
        messages.error(request, 'Sem permissão para criar procedimentos.')
        return redirect('procedimentos_list')
    if request.method == 'POST':
        form = ProcedimentoForm(request.POST, request.FILES)
        if form.is_valid():
            proc = form.save()
            messages.success(request, f"Procedimento {proc.codigo} criado.")
            return redirect('procedimentos_list')
    else:
        form = ProcedimentoForm()
    return render(request, 'form_generico.html', {
        'form': form,
        'titulo': 'Novo Procedimento'
    })


@login_required
def editar_procedimento_view(request, procedimento_id):
    proc = get_object_or_404(Procedimento, id=procedimento_id)
    if not can_manage_procedimentos(request.user):
        messages.error(request, 'Sem permissão para editar procedimentos.')
        return redirect('detalhe_procedimento', procedimento_id=proc.id)
    if request.method == 'POST':
        form = ProcedimentoForm(request.POST, request.FILES, instance=proc)
        if form.is_valid():
            form.save()
            messages.success(request, "Atualizado.")
            return redirect('detalhe_procedimento', procedimento_id=proc.id)
    else:
        form = ProcedimentoForm(instance=proc)
    return render(request, 'form_generico.html', {
        'form': form,
        'titulo': f'Editar {proc.codigo}'
    })


@login_required
def detalhe_procedimento_view(request, procedimento_id):
    proc = get_object_or_404(Procedimento, id=procedimento_id)
    return render(request, 'procedimento_detalhe.html', {
        'proc': proc
    })


# --- Permissões internas ---
def can_manage_procedimentos(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    # Qualidade / RH (exige que nome de setor contenha palavra-chave) via Colaborador mapping
    try:
        col = Colaborador.objects.filter(user_django=user).select_related('setor').first()
        if col and col.setor and any(k in col.setor.nome.upper() for k in ['QUALIDADE','RH','ENGENHARIA']):
            return True
    except Exception:
        pass
    return False


@login_required
def detalhe_colaborador_view(request, colab_id):
    usuario_logado = None
    try:
        usuario_logado = Colaborador.objects.filter(user_django=request.user).first()
    except Exception:
        pass
    alvo = get_object_or_404(Colaborador, id=colab_id)

    # --- NOVO: BUSCA DE HIERARQUA POR SETOR/TURNO (para visualização) ---
    supervisor_rh = None
    gerente_rh = None

    if alvo.setor and alvo.turno:
        # Tenta encontrar a hierarquia exata para Setor e Turno
        hierarquia = HierarquiaSetor.objects.filter(
            setor=alvo.setor, turno=alvo.turno
        ).first()

        # Se não encontrar no turno específico, tenta o turno ADM como fallback
        if not hierarquia:
            hierarquia = HierarquiaSetor.objects.filter(
                setor=alvo.setor, turno="ADM"
            ).first()

        if hierarquia:
            supervisor_rh = hierarquia.supervisor
            gerente_rh = hierarquia.gerente

    # Segurança: pode ver todos se for superuser, gerente, RH/DP/Qualidade
    if not request.user.is_superuser:
        permitido = False
        if usuario_logado:
            setor_nome = (usuario_logado.setor.nome.upper() if usuario_logado.setor else "")
            pode_ver_todos = False
            if any(k in setor_nome for k in ["RH", "DP", "QUALIDADE"]):
                pode_ver_todos = True
            if ("GERENTE" in str(usuario_logado.cargo).upper() or
                HierarquiaSetor.objects.filter(gerente=usuario_logado).exists()):
                pode_ver_todos = True
            if pode_ver_todos:
                permitido = True
            elif usuario_logado.id == alvo.id:
                permitido = True
            else:
                meus_subordinados = get_all_subordinates(usuario_logado)
                if alvo.id in meus_subordinados:
                    permitido = True
        if not permitido:
            messages.error(request, "Acesso Negado.")
            return redirect("modulo_rh")

    # Regra 2.2: salário/CPF apenas para superusuários, gerentes e diretores
    can_see_salary = False
    if request.user.is_superuser:
        can_see_salary = True
    elif usuario_logado:
        if (
            "GERENTE" in str(usuario_logado.cargo).upper()
            or HierarquiaSetor.objects.filter(gerente=usuario_logado).exists()
            or "DIRETOR" in str(usuario_logado.cargo).upper()
            or HierarquiaSetor.objects.filter(diretor=usuario_logado).exists()
        ):
            can_see_salary = True

    # Permissões específicas para Ocorrências de RH
    can_register_occ = False
    can_view_occ = False
    if request.user.is_superuser or request.user.is_staff:
        can_register_occ = True
        can_view_occ = True
    elif usuario_logado:
        if usuario_logado.setor and "RH" in usuario_logado.setor.nome.upper():
            can_register_occ = True
            can_view_occ = True
        if HierarquiaSetor.objects.filter(gerente=usuario_logado).exists() or \
           HierarquiaSetor.objects.filter(supervisor=usuario_logado).exists():
            can_register_occ = True
            can_view_occ = True
        # O próprio colaborador pode ver a página, mas não vê ocorrências
        if usuario_logado.id == alvo.id and not (request.user.is_superuser or request.user.is_staff):
            can_view_occ = False

    ocorrencias = alvo.ocorrencias.all().order_by("-data_ocorrencia") if can_view_occ else []
    treinamentos = alvo.treinamentos.all().order_by("-data_treinamento")
    documentos = alvo.documentos_pessoais.all().order_by("-data_upload")

    # Férias
    try:
        ferias_qs = alvo.ferias_set.all().order_by("-periodo_aquisitivo_fim")
    except AttributeError:
        ferias_qs = []

    ferias_vencidas = 0
    ferias_programadas = 0
    hoje = date.today()

    for f in ferias_qs:
        dt_limite = (
            f.data_limite
            if f.data_limite
            else (
                f.periodo_aquisitivo_fim + timedelta(days=365)
                if f.periodo_aquisitivo_fim
                else None
            )
        )

        if dt_limite and dt_limite < hoje:
            if f.status != "GOZADAS" and (not f.data_inicio or f.data_inicio < hoje):
                ferias_vencidas += 1

        if f.data_inicio and f.data_inicio > hoje:
            ferias_programadas += 1

    ctx = {
        "colaborador": usuario_logado,
        "alvo": alvo,
        "can_see_salary": can_see_salary,
        "can_register_occ": can_register_occ,
        "can_view_occ": can_view_occ,
        "ocorrencias": ocorrencias,
        "treinamentos": treinamentos,
        "documentos": documentos,
        "ferias": ferias_qs,
        "kpi_ferias_vencidas": ferias_vencidas,
        "kpi_ferias_programadas": ferias_programadas,
        "can_edit": True,
        "supervisor_rh": supervisor_rh,  # <--- ENVIADO PARA O TEMPLATE
        "gerente_rh": gerente_rh,  # <--- ENVIADO PARA O TEMPLATE
    }
    return render(request, "detalhe_colaborador.html", ctx)


@login_required
def editar_colaborador_view(request, colab_id):
    usuario_logado = None
    try:
        usuario_logado = Colaborador.objects.filter(user_django=request.user).first()
    except Exception:
        pass
    alvo = get_object_or_404(Colaborador, id=colab_id)

    if not (request.user.is_superuser or request.user.is_staff):
        permitido = False
        if usuario_logado:
            if usuario_logado.setor and "RH" in usuario_logado.setor.nome.upper():
                permitido = True
            else:
                meus_subordinados = get_all_subordinates(usuario_logado)
                if alvo.id in meus_subordinados:
                    permitido = True
        if not permitido:
            messages.error(request, "Acesso Negado.")
            return redirect("modulo_rh")

    if request.method == "POST":
        form = ColaboradorForm(request.POST, instance=alvo)
        if form.is_valid():
            form.save()
            messages.success(request, "Atualizado!")
            return redirect("detalhe_colaborador", colab_id=alvo.id)
        else:
            messages.error(request, "Erro ao salvar.")
    else:
        form = ColaboradorForm(instance=alvo)
    return render(
        request,
        "editar_colaborador.html",
        {"form": form, "alvo": alvo, "colaborador": usuario_logado},
    )


# --- REGISTRO DE OCORRÊNCIA DO COLABORADOR ---
@login_required
def registrar_ocorrencia_view(request):
    # Permissão: apenas RH, liderança (supervisor/gerente) e staff/superuser podem registrar
    usuario_logado = None
    try:
        usuario_logado = Colaborador.objects.filter(user_django=request.user).first()
    except Exception:
        pass
    permitido = False
    if request.user.is_superuser or request.user.is_staff:
        permitido = True
    elif usuario_logado:
        if usuario_logado.setor and "RH" in usuario_logado.setor.nome.upper():
            permitido = True
        if HierarquiaSetor.objects.filter(gerente=usuario_logado).exists() or \
           HierarquiaSetor.objects.filter(supervisor=usuario_logado).exists():
            permitido = True
    if not permitido:
        messages.error(request, "Você não tem permissão para registrar ocorrências.")
        return redirect("modulo_rh")

    preselect_id = request.GET.get("colab_id")
    if request.method == "POST":
        form = OcorrenciaForm(request.POST, request.FILES)
        if form.is_valid():
            oc = form.save()
            messages.success(request, "Ocorrência registrada com sucesso!")
            if oc.colaborador_id:
                return redirect("detalhe_colaborador", colab_id=oc.colaborador_id)
            return redirect("modulo_rh")
        else:
            messages.error(request, "Verifique os dados da ocorrência.")
    else:
        initial = {}
        if preselect_id:
            initial["colaborador"] = preselect_id
        form = OcorrenciaForm(initial=initial)
    return render(
        request,
        "registro_ocorrencia.html",
        {"form": form, },
    )


# --- NOVA VIEW: SOLICITAÇÃO DE INSTRUMENTO ---
@login_required
def nova_solicitacao(request):
    if request.method == "POST":
        form = SolicitacaoForm(request.POST)
        if form.is_valid():
            solicitacao = form.save(commit=False)
            solicitacao.solicitante = request.user
            solicitacao.save()
            messages.success(request, "Solicitação enviada com sucesso!")
            return redirect("home")  # Volta para o dashboard
    else:
        form = SolicitacaoForm()

    return render(
        request,
        "form_generico.html",
        {"form": form, "titulo": "Nova Solicitação"},
    )


# --- NOVA VIEW: CADASTRO DE INSTRUMENTO (IN-APP) ---
@login_required
def novo_instrumento_view(request):
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
    return render(request, 'form_generico.html', {
        'form': form,
        'titulo': 'Novo Instrumento',
        })


# --- VIEW ATUALIZADA: DETALHE DO INSTRUMENTO (COM OCORRÊNCIAS E ORDENS) ---
@login_required
def detalhe_instrumento_view(
    request, instrumento_id
):  # Note que o URLs.py usa 'pk' ou 'instrumento_id', verifique se o urls.py espera <int:pk> ou <int:instrumento_id>. Vou manter instrumento_id conforme seu código antigo.
    inst = get_object_or_404(Instrumento, id=instrumento_id)

    # Processamento do Form de Ocorrência Rápida
    if request.method == "POST":
        form_ocorrencia = OcorrenciaForm(request.POST)
        if form_ocorrencia.is_valid():
            ocorrencia = form_ocorrencia.save(commit=False)
            ocorrencia.instrumento = inst
            ocorrencia.usuario_responsavel = request.user
            ocorrencia.save()
            messages.success(request, "Ocorrência registrada com sucesso!")
            # Recarrega a página para limpar o post
            return redirect("detalhe_instrumento", instrumento_id=inst.id)
        else:
            messages.error(request, "Erro ao registrar ocorrência. Verifique os dados.")
    else:
        form_ocorrencia = OcorrenciaForm()

    # Buscando dados para as novas abas
    try:
        historico = inst.historico_calibracoes.all().order_by("-data_calibracao")
    except Exception as e:
        import traceback
        print("[ERRO DETALHE INSTRUMENTO]", e)
        traceback.print_exc()
        historico = []

    # Usando related_names definidos no models.py (calibracoes e ocorrencias)
    # Se der erro aqui, verifique se no models.py está related_name='calibracoes'
    try:
        calibracoes = inst.calibracoes.all().order_by("-data_prevista")
    except AttributeError:
        calibracoes = []  # Fallback caso a migration não tenha rolado 100%

    try:
        ocorrencias = inst.ocorrencias.all().order_by("-data_ocorrencia")
    except AttributeError:
        ocorrencias = []

    # Anexa atributo responsavel_colab_id às ocorrências quando houver vínculo com Colaborador
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
        ocorrencias = []

    if hasattr(inst, "faixas"):
        faixas = inst.faixas.all()

    return render(
        request,
        "detalhe_instrumento.html",
        {
            "instrumento": inst,
            "historico": historico,
            "calibracoes": calibracoes,
            "ocorrencias": ocorrencias,
            # nenhuma var extra necessária: cada ocorrência pode ter atributo responsavel_colab_id
            "faixas": faixas,
            "form_ocorrencia": form_ocorrencia,
            "today": date.today(),
        },
    )


@login_required
def remover_historico_view(request, historico_id):
    hist = get_object_or_404(HistoricoCalibracao, id=historico_id)
    i_id = hist.instrumento.id
    if hist.certificado:
        hist.certificado.delete(save=False)
    hist.delete()
    messages.success(request, "Removido.")
    return redirect("detalhe_instrumento", instrumento_id=i_id)


@login_required
def anexar_certificado_historico_view(request, historico_id):
    """Anexa um arquivo PDF ao registro de histórico que ainda não tenha certificado."""
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

    # Validação simples de tipo
    ctype = getattr(up, "content_type", "") or ""
    if "pdf" not in ctype.lower():
        messages.error(request, "Arquivo inválido. Envie um PDF.")
        return redirect("detalhe_instrumento", instrumento_id=inst_id)

    # Salva no campo FileField; o nome ficará em certificados/
    try:
        filename = f"Cert_{hist.numero_certificado}_{hist.instrumento.tag}.pdf" if hist.instrumento else up.name
        hist.certificado.save(filename, up, save=True)
        messages.success(request, "Certificado anexado com sucesso!")
    except Exception as e:
        messages.error(request, f"Falha ao anexar certificado: {e}")
    return redirect("detalhe_instrumento", instrumento_id=inst_id)


@login_required
def remover_certificado_historico_view(request, historico_id):
    """Remove apenas o arquivo de certificado do histórico, mantendo o registro."""
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


# ==============================================================================
# CARIMBO (VALIDAÇÃO)
# ==============================================================================


# --- DOWNLOAD DE TEMPLATES ---
def dl_template_instr(request):
    return dl_generic(
        [
            "TAG",
            "EQUIPAMENTO",
            "STATUS",
            "FABRICANTE",
            "MODELO",
            "N SERIE",
            "SETOR",
            "LOCALIZACAO",
            "FREQUENCIA_MESES",
            "DATA_ULTIMA_CALIBRACAO",
            "FAIXA",
            "UNIDADE",
        ],
        "template_instrumentos_v2.xlsx",
    )


def dl_template_colab(request):
    return dl_df(
        pd.DataFrame(
            {
                "MATRICULA": ["100"],
                "NOME": ["TESTE"],
                "CPF": ["000"],
                "CARGO": ["Y"],
                "GRUPO": ["ADM"],
                "SETOR": ["ADM"],
                "CC": ["100"],
                "TURNO": ["ADM"],
                "STATUS": ["ATIVO"],
                "MAT_LIDER": ["999"],
                "MAT_SUPERVISOR": ["888"],
                "MAT_GERENTE": ["777"],
            }
        ),
        "template_colaboradores.xlsx",
    )


def dl_template_hierarquia(request):
    return dl_df(
        pd.DataFrame(
            {
                "SETOR": ["MAN"],
                "TURNO": ["T1"],
                "MAT_LIDER": ["1"],
                "MAT_SUPERVISOR": [""],
                "MAT_GERENTE": [""],
                "MAT_DIRETOR": [""],
            }
        ),
        "template_hierarquia.xlsx",
    )


def dl_template_historico(request):
    return dl_generic(
        [
            "TAG",
            "DATA CALIBRAÇÃO",
            "DATA APROVAÇÃO",
            "N CERTIFICADO",
            "ERRO ENCONTRADO",
            "INCERTEZA",
            "TOLERANCIA PROCESSO (+/-)",
            "RBC (SIM/NAO)",
            "RESULTADO",
            "FORNECEDOR",
            "RESPONSÁVEL",
            "OBSERVAÇÕES",
        ],
        "template_historico.xlsx",
    )


# --- NOVO TEMPLATE DE FÉRIAS ---
def dl_template_ferias(request):
    df = pd.DataFrame(
        {
            "MATRICULA": ["100"],
            "AQUISITIVO_INICIO": ["01/01/2023"],
            "AQUISITIVO_FIM": ["31/12/2023"],
            "DATA_INICIO": ["10/02/2024"],
            "DATA_FIM": ["20/02/2024"],
            "STATUS": ["PROGRAMADAS"],
        }
    )
    return dl_df(df, "template_ferias.xlsx")


def dl_template_categorias(request):
    import pandas as pd
    df = pd.DataFrame(
        {
            "nome": ["PAQUIMETROS", "MICROMETROS", "TORQUIMETROS"],
            "descricao": [
                "Instrumentos do tipo paquímetro",
                "Instrumentos do tipo micrômetro",
                "Instrumentos para torque",
            ],
            "unidade_sigla": ["mm", "mm", "Nm"],
        }
    )
    return dl_df(df, "template_categorias.xlsx")


@login_required
def dl_template_procedimentos(request):
    import pandas as pd, io
    # Colunas e ordem exatas do novo model
    cols = [
        'no', 'codigo', 'nome', 'descricao', 'pasta', 'classificacao', 'autor',
        'numero_revisao', 'ultima_revisao', 'data_aprovacao', 'proxima_revisao',
        'data_validade', 'documentos_controlados', 'matriz', 'sub_area'
    ]
    exemplo = {
        'no': ['1'],
        'codigo': ['POP.001'],
        'nome': ['EXEMPLO DE PROCEDIMENTO'],
        'descricao': ['Objetivo ou função do procedimento'],
        'pasta': ['QUALIDADE'],
        'classificacao': ['POP'],
        'autor': ['João da Silva'],
        'numero_revisao': ['01'],
        'ultima_revisao': ['01/10/2025'],
        'data_aprovacao': ['05/10/2025'],
        'proxima_revisao': ['05/10/2026'],
        'data_validade': ['05/10/2026'],
        'documentos_controlados': ['Sim'],
        'matriz': ['Matriz A'],
        'sub_area': ['Subárea 1'],
    }
    df = pd.DataFrame({col: exemplo.get(col, ['']) for col in cols})
    b = io.BytesIO()
    df.to_excel(b, index=False)
    b.seek(0)
    r = HttpResponse(b, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    r['Content-Disposition'] = 'attachment; filename="template_procedimentos.xlsx"'
    return r


def dl_generic(cols, fname):
    df = pd.DataFrame(columns=cols)
    return dl_df(df, fname)


def dl_df(df, fname):
    b = io.BytesIO()
    df.to_excel(b, index=False)
    b.seek(0)
    r = HttpResponse(
        b,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    r["Content-Disposition"] = f'attachment; filename="{fname}"'
    return r


# --- IMPORTAÇÕES COMPLETAS (SEM CORTES) ---


@login_required
def imp_instr_view(request):
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
               
                # create import job record
                job = ImportJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    filename=uploaded.name,
                    filepath=tmp.name,
                    job_type="INSTRUMENTOS",
                    status="PENDING",
                )

                # Execução síncrona forçada se SYNC_IMPORTS=1 (default) ou se Celery falhar
                from .tasks import import_instruments_task
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
                    messages.success(request, f"Importação concluída imediatamente (job {job.id}). {job.result or ''}")
                    return redirect("modulo_metrologia")
            except Exception as e:
                messages.error(request, f"Erro ao enfileirar importação: {str(e)}")
                return redirect("importar_instrumentos")
    else:
        form = ImportacaoInstrumentosForm()
    return render(
        request,
        "importar_instrumentos.html",
        {"form": form, "jobs": ImportJob.objects.order_by('-created_at')[:5]},
    )


@login_required
def imp_historico_view(request):
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

                from .tasks import import_historico_task
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
                        # Após importar, força recálculo das datas nos instrumentos afetados
                        afetados = HistoricoCalibracao.objects.filter(
                            criado_em__gte=job.created_at
                        ).values_list("instrumento_id", flat=True).distinct()
                        for iid in afetados:
                            inst = Instrumento.objects.filter(id=iid).first()
                            if inst:
                                ultima = inst.historico_calibracoes.order_by("-data_calibracao").first()
                                if ultima:
                                    inst.data_ultima_calibracao = ultima.data_calibracao
                                    inst.data_proxima_calibracao = ultima.proxima_calibracao
                                else:
                                    inst.data_ultima_calibracao = None
                                    inst.data_proxima_calibracao = None
                                inst.save(update_fields=["data_ultima_calibracao", "data_proxima_calibracao"])
                    except Exception:
                        pass
                    messages.success(request, f"Histórico importado imediatamente (job {job.id}). {job.result or ''}")
                    return redirect("modulo_metrologia")
            except Exception as e:
                messages.error(request, f"Erro ao enfileirar importação: {str(e)}")
                return redirect("importar_historico")
    else:
        form = ImportacaoHistoricoForm()
    return render(
        request,
        "importar_historico.html",
        {"form": form, "jobs": ImportJob.objects.order_by('-created_at')[:5]},
    )


@login_required
def imp_padroes_view(request):
    if request.method == "POST":
        form = ImportacaoPadroesForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                f = request.FILES["arquivo_excel"]
                try:
                    df = pd.read_excel(f)
                except:
                    df = pd.read_csv(f, sep=None, engine="python")
                df.columns = df.columns.str.strip().str.upper()
                count = 0
                with transaction.atomic():
                    for _, row in df.iterrows():
                        codigo = str(row.get("CODIGO", "")).strip()
                        if codigo:
                            Padrao.objects.update_or_create(
                                codigo=codigo,
                                defaults={"descricao": "Importado", "ativo": True},
                            )
                            count += 1
                messages.success(request, f"{count} Padrões importados!")
                return redirect("modulo_metrologia")
            except Exception as e:
                messages.error(request, f"Erro: {e}")
    else:
        form = ImportacaoPadroesForm()
    return render(
        request,
        "importar_historico.html",
        {"form": form, "titulo": "Importar Padrões"},
    )


@login_required
def imp_procedimentos_view(request):
    if request.method == 'POST':
        form = ImportacaoProcedimentosForm(request.POST, request.FILES)
        if form.is_valid():
            up = request.FILES.get('arquivo_excel')
            if not up:
                messages.error(request, 'Arquivo não enviado.')
                return redirect('importar_procedimentos')
            import pandas as pd, io, os
            ext = os.path.splitext(up.name)[1].lower()
            try:
                if ext in {'.xlsx','.xls','.xlsm'}:
                    df = pd.read_excel(up)
                else:
                    content = up.read()
                    try:
                        df = pd.read_csv(io.BytesIO(content), sep=None, engine='python')
                        if len(df.columns) == 1:
                            # Try semicolon delimiter if only one column detected
                            df = pd.read_csv(io.BytesIO(content), sep=';', engine='python')
                    except Exception:
                        # fallback: try semicolon
                        df = pd.read_csv(io.BytesIO(content), sep=';', engine='python')
            except Exception as e:
                messages.error(request, f'Falha ao ler planilha: {e}')
                return redirect('importar_procedimentos')
            df.columns = df.columns.map(lambda c: str(c).strip().lower())
            # Garante que todas as colunas do template estejam presentes
            expected_cols = ['no','codigo','nome','descricao','pasta','classificacao','autor','numero_revisao','ultima_revisao','data_aprovacao','proxima_revisao','data_validade','documentos_controlados','matriz','sub_area']
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = None
            created = 0; updated = 0; errors = 0
            import logging
            logger = logging.getLogger("qms.import_procedimentos")
            for idx, row in df.iterrows():
                row_dict = {str(k).strip().lower(): v for k, v in row.items()}
                def clean(val):
                    import pandas as pd
                    if pd.isna(val) or val is None:
                        return None
                    sval = str(val).strip()
                    if sval.lower() == 'nan' or sval == '':
                        return None
                    return sval
                no = clean(row_dict.get('no'))
                codigo = clean(row_dict.get('codigo'))
                if not codigo:
                    logger.warning(f"Linha {idx+1}: código vazio, linha ignorada. Dados: {row_dict}")
                    continue
                codigo = codigo.upper()
                nome = clean(row_dict.get('nome') or row_dict.get('titulo'))
                descricao = clean(row_dict.get('descricao'))
                pasta = clean(row_dict.get('pasta'))
                classificacao = clean(row_dict.get('classificacao'))
                autor = clean(row_dict.get('autor'))
                numero_revisao = clean(row_dict.get('numero_revisao') or row_dict.get('revisao'))
                def parse_date(val):
                    if not val or str(val).lower() == 'nan': return None
                    try:
                        return pd.to_datetime(val, dayfirst=True).date()
                    except Exception as e:
                        logger.warning(f"Linha {idx+1}: erro ao converter data '{val}': {e}")
                        return None
                ultima_revisao = parse_date(row_dict.get('ultima_revisao') or row_dict.get('data_revisao'))
                data_aprovacao = parse_date(row_dict.get('data_aprovacao'))
                proxima_revisao = parse_date(row_dict.get('proxima_revisao'))
                data_validade = parse_date(row_dict.get('data_validade'))
                documentos_controlados = clean(row_dict.get('documentos_controlados'))
                matriz = clean(row_dict.get('matriz'))
                sub_area = clean(row_dict.get('sub_area'))
                try:
                    obj, was_created = Procedimento.objects.update_or_create(
                        codigo=codigo,
                        defaults={
                            'no': no or None,
                            'nome': nome,
                            'descricao': descricao,
                            'pasta': pasta,
                            'classificacao': classificacao,
                            'autor': autor,
                            'numero_revisao': numero_revisao,
                            'ultima_revisao': ultima_revisao,
                            'data_aprovacao': data_aprovacao,
                            'proxima_revisao': proxima_revisao,
                            'data_validade': data_validade,
                            'documentos_controlados': documentos_controlados,
                            'matriz': matriz,
                            'sub_area': sub_area,
                        }
                    )
                    logger.info(f"Linha {idx+1}: Procedimento {codigo} {'criado' if was_created else 'atualizado'}.")
                    created += 1 if was_created else 0
                    updated += 0 if was_created else 1
                except Exception as e:
                    logger.error(f"Linha {idx+1}: erro ao importar procedimento {codigo}. Dados: {row_dict}. Erro: {e}")
                    errors += 1
            messages.success(request, f"Procedimentos criados: {created}, atualizados: {updated}, erros: {errors}")
            return redirect('procedimentos_lista')
    else:
        form = ImportacaoProcedimentosForm()
    return render(request, 'importar_procedimentos.html', {'form': form})


@login_required
def imp_categorias_view(request):
    """Importa categorias em massa a partir de CSV/Excel (nome,descricao,unidade_sigla)."""
    if request.method == 'POST':
        up = request.FILES.get('arquivo')
        if not up:
            messages.error(request, 'Selecione um arquivo CSV ou Excel.')
            return redirect('importar_categorias')

        import pandas as pd
        import io
        import os

        fname = getattr(up, 'name', '') or ''
        ext = os.path.splitext(fname)[1].lower()
        try:
            if ext in {'.xlsx', '.xls', '.xlsm'}:
                df = pd.read_excel(up)
            else:
                # Assume CSV; let pandas infer delimiter
                # io.BytesIO to reset pointer if needed
                if hasattr(up, 'read'):
                    content = up.read()
                    up = io.BytesIO(content)
                df = pd.read_csv(up, sep=None, engine='python')
        except Exception as e:
            messages.error(request, f'Falha ao ler arquivo: {e}. Use CSV ou Excel com colunas nome, descricao, unidade_sigla.')
            return redirect('importar_categorias')

        # Normaliza colunas
        df.columns = df.columns.map(lambda c: str(c).strip().lower())
        for col in ['nome', 'descricao', 'unidade_sigla']:
            if col not in df.columns:
                df[col] = None

        created = 0
        updated = 0
        not_found_units = 0
        for _, row in df.iterrows():
            nome = str(row.get('nome') or '').strip()
            if not nome:
                continue
            desc = str(row.get('descricao') or '').strip() or None
            unidade_sigla = str(row.get('unidade_sigla') or '').strip()
            unidade_obj = None
            if unidade_sigla:
                unidade_obj = UnidadeMedida.objects.filter(sigla__iexact=unidade_sigla).first()
                if not unidade_obj:
                    not_found_units += 1
            obj, was_created = CategoriaInstrumento.objects.update_or_create(
                nome=nome,
                defaults={'descricao': desc, 'unidade_padrao': unidade_obj}
            )
            if was_created:
                created += 1
            else:
                updated += 1
        messages.success(request, f"Categorias criadas: {created}, atualizadas: {updated}. Unidades não encontradas: {not_found_units}")
        return redirect('modulo_metrologia')
    return render(request, 'importar_categorias.html', {})


@login_required
def imp_colab_view(request):
    if request.method == "POST":
        form = ImportacaoColaboradoresForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                uploaded = request.FILES["arquivo_excel"]
                suffix = os.path.splitext(uploaded.name)[1] or ".xlsx"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                for chunk in uploaded.chunks():
                    tmp.write(chunk)
                tmp.flush(); tmp.close()

                job = ImportJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    filename=uploaded.name,
                    filepath=tmp.name,
                    job_type="RH_COLAB",
                    status="PENDING",
                )

                from .tasks import import_colab_task
                force_sync = os.environ.get("SYNC_IMPORTS", "1") == "1"
                if not force_sync:
                    try:
                        import_colab_task.delay(str(job.id), tmp.name)
                        messages.success(request, f"Importação de colaboradores enfileirada (job {job.id}).")
                        return redirect("modulo_rh")
                    except Exception:
                        force_sync = True
                if force_sync:
                    import_colab_task(job.id, tmp.name)
                    job.refresh_from_db()
                    messages.success(request, f"Colaboradores importados imediatamente (job {job.id}). {job.result or ''}")
                    return redirect("modulo_rh")
            except Exception as e:
                messages.error(request, f"Erro na importação: {str(e)}")
                return redirect("modulo_rh")
    else:
        form = ImportacaoColaboradoresForm()
    return render(
        request,
        "importar_colaboradores.html",
        {"form": form, "jobs": ImportJob.objects.order_by('-created_at')[:5]},
    )


@login_required
def imp_hierarquia_view(request):
    if request.method == "POST":
        form = ImportacaoHierarquiaForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                uploaded = request.FILES["arquivo_excel"]
                suffix = os.path.splitext(uploaded.name)[1] or ".xlsx"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                for chunk in uploaded.chunks():
                    tmp.write(chunk)
                tmp.flush(); tmp.close()

                job = ImportJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    filename=uploaded.name,
                    filepath=tmp.name,
                    job_type="RH_HIERARQUIA",
                    status="PENDING",
                )

                from .tasks import import_hierarquia_task
                force_sync = os.environ.get("SYNC_IMPORTS", "1") == "1"
                if not force_sync:
                    try:
                        import_hierarquia_task.delay(str(job.id), tmp.name)
                        messages.success(request, f"Importação de hierarquia enfileirada (job {job.id}).")
                        return redirect("modulo_rh")
                    except Exception:
                        force_sync = True
                if force_sync:
                    import_hierarquia_task(job.id, tmp.name)
                    job.refresh_from_db()
                    messages.success(request, f"Hierarquia importada imediatamente (job {job.id}). {job.result or ''}")
                    return redirect("modulo_rh")
            except Exception as e:
                messages.error(request, f"Erro na importação: {str(e)}")
                return redirect("modulo_rh")
    return render(
        request,
        "importar_hierarquia.html",
        {"form": ImportacaoHierarquiaForm(), "jobs": ImportJob.objects.order_by('-created_at')[:5]},
    )


# --- IMPORTAÇÃO DE FÉRIAS (COM DIAS VENDIDOS) ---
@login_required
def imp_ferias_view(request):
    if request.method == "POST":
        form = ImportacaoFeriasForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                uploaded = request.FILES["arquivo_excel"]
                suffix = os.path.splitext(uploaded.name)[1] or ".xlsx"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                for chunk in uploaded.chunks():
                    tmp.write(chunk)
                tmp.flush(); tmp.close()

                job = ImportJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    filename=uploaded.name,
                    filepath=tmp.name,
                    job_type="RH_FERIAS",
                    status="PENDING",
                )

                from .tasks import import_ferias_task
                force_sync = os.environ.get("SYNC_IMPORTS", "1") == "1"
                if not force_sync:
                    try:
                        import_ferias_task.delay(str(job.id), tmp.name)
                        messages.success(request, f"Importação de férias enfileirada (job {job.id}).")
                        return redirect("modulo_rh")
                    except Exception:
                        force_sync = True
                if force_sync:
                    import_ferias_task(job.id, tmp.name)
                    job.refresh_from_db()
                    messages.success(request, f"Férias importadas imediatamente (job {job.id}). {job.result or ''}")
                    return redirect("modulo_rh")
            except Exception as e:
                messages.error(request, f"Erro: {e}")
    else:
        form = ImportacaoFeriasForm()
    return render(
        request,
        "importar_ferias.html",
        {"form": form, "jobs": ImportJob.objects.order_by('-created_at')[:5]},
    )


# Adicione esta função na seção de Downloads de Templates (após dl_df):


@login_required
def dl_template_colab_dados(request):
    """Gera um arquivo Excel com dados completos dos Colaboradores ativos."""

    # Define permissão para visualizar salário conforme mesmas regras da tela RH
    colab = None
    try:
        colab = Colaborador.objects.filter(user_django=request.user).first()
    except Exception:
        pass
    can_see_salary = False
    if request.user.is_superuser or request.user.is_staff:
        can_see_salary = True
    elif colab:
        if colab.setor and "RH" in colab.setor.nome.upper():
            can_see_salary = True
        else:
            if (
                "GERENTE" in str(colab.cargo).upper()
                or HierarquiaSetor.objects.filter(gerente=colab).exists()
            ):
                can_see_salary = True

    # 1. Busca todos os colaboradores ativos
    qs = Colaborador.objects.filter(is_active=True).select_related(
        "setor", "centro_custo", "lider", "supervisor", "gerente"
    ).order_by("nome_completo")

    # 2. Cria uma lista de dicionários com os dados
    data = []
    for colab in qs:
        data.append(
            {
                "MATRICULA": colab.matricula,
                "NOME": colab.nome_completo,
                "CPF": colab.cpf or "",
                "CARGO": colab.cargo or "",
                "GRUPO": colab.grupo or "Geral",
                "SETOR": colab.setor.nome if colab.setor else "",
                "CC": colab.centro_custo.codigo if colab.centro_custo else "",
                "TURNO": colab.get_turno_display(),
                "TURNO_CODIGO": colab.turno,
                "STATUS": "ATIVO",
                "MAT_LIDER": colab.lider.matricula if colab.lider else "",
                "NOME_LIDER": colab.lider.nome_completo if colab.lider else "",
                "MAT_SUPERVISOR": colab.supervisor.matricula if colab.supervisor else "",
                "NOME_SUPERVISOR": colab.supervisor.nome_completo if colab.supervisor else "",
                "MAT_GERENTE": colab.gerente.matricula if colab.gerente else "",
                "NOME_GERENTE": colab.gerente.nome_completo if colab.gerente else "",
                "EM_FERIAS": "SIM" if colab.em_ferias else "NÃO",
                "SALARIO": (float(colab.salario) if (can_see_salary and colab.salario) else ""),
            }
        )

    # 3. Cria o DataFrame e o arquivo Excel na memória
    df = pd.DataFrame(data)
    fname = f"colaboradores_export_{date.today().strftime('%Y%m%d')}.xlsx"

    # Reutiliza a função dl_df para servir o arquivo
    b = io.BytesIO()
    df.to_excel(b, index=False, engine='openpyxl')
    b.seek(0)

    r = HttpResponse(
        b,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    r["Content-Disposition"] = f'attachment; filename="{fname}"'
    return r


def health_check(request):
    """Lightweight health check endpoint for monitoring and readiness probes.

    Returns HTTP 200 when Django is running and imports succeeded. This is intentionally
    simple so external systems can check app liveness quickly (eg. Railway/Heroku/Gunicorn).
    """
    from django.http import HttpResponse

    return HttpResponse("OK", content_type="text/plain")


@login_required
def import_jobs_view(request):
    """List recent import jobs with optional status filter."""
    try:
        from .models import ImportJob
        status = (request.GET.get('status') or '').upper()
        job_type = (request.GET.get('type') or '').upper()
        qs = ImportJob.objects.all()
        if status in {'PENDING','STARTED','SUCCESS','FAILURE'}:
            qs = qs.filter(status=status)
        if job_type:
            qs = qs.filter(job_type__iexact=job_type)
        jobs = list(qs.order_by('-created_at')[:100])
        # Prepare display fields: split summary and samples if present
        prepared = []
        for j in jobs:
            summary = j.result or ''
            samples = []
            try:
                if summary and '| Samples:' in summary:
                    parts = summary.split('| Samples:')
                    summary = parts[0].strip()
                    samples_str = parts[1].strip() if len(parts) > 1 else ''
                    if samples_str:
                        samples = [s.strip() for s in samples_str.split(',') if s.strip()]
            except Exception:
                samples = []
            prepared.append({
                'id': j.id,
                'job_type': j.job_type,
                'filename': j.filename,
                'status': j.status,
                'result_summary': summary,
                'result_samples': samples,
                'created_at': j.created_at,
                'updated_at': j.updated_at,
                'filepath': j.filepath,
            })
        return render(request, 'import_jobs.html', {
            'jobs': prepared,
            'status': status,
            'job_type': job_type,
            })
    except Exception as e:
        # Fallback: return minimal HTML to avoid 500 and expose error
        return HttpResponse(f"<pre>Falha ao carregar import-jobs: {str(e)}</pre>", content_type="text/html", status=200)


@login_required
def import_jobs_json_view(request):
    """Return recent import jobs as JSON for debugging when template fails."""
    from .models import ImportJob
    status = (request.GET.get('status') or '').upper()
    job_type = (request.GET.get('type') or '').upper()
    qs = ImportJob.objects.all()
    if status in {'PENDING','STARTED','SUCCESS','FAILURE'}:
        qs = qs.filter(status=status)
    if job_type:
        qs = qs.filter(job_type__iexact=job_type)
    jobs = qs.order_by('-created_at')[:100]
    data = []
    for j in jobs:
        data.append({
            'id': str(j.id),
            'job_type': j.job_type,
            'filename': j.filename,
            'status': j.status,
            'result': j.result,
            'created_at': j.created_at.isoformat() if j.created_at else None,
            'updated_at': j.updated_at.isoformat() if j.updated_at else None,
            'filepath': j.filepath,
        })
    return JsonResponse({'jobs': data})


@login_required
def retry_import_job_view(request, job_id):
    """Retry a failed or pending import job by re-enqueuing its task."""
    from .models import ImportJob
    from .tasks import import_instruments_task, import_historico_task, import_colab_task, import_hierarquia_task, import_ferias_task

    job = get_object_or_404(ImportJob, id=job_id)
    if not job.filepath:
        messages.error(request, "Este job não tem arquivo associado para reprocessar.")
        return redirect('import_jobs')

    try:
        if job.job_type == 'INSTRUMENTOS':
            try:
                import_instruments_task.delay(str(job.id), job.filepath)
            except Exception:
                import_instruments_task(job.id, job.filepath)
        elif job.job_type == 'HISTORICO':
            try:
                import_historico_task.delay(str(job.id), job.filepath)
            except Exception:
                import_historico_task(job.id, job.filepath)
        elif job.job_type == 'RH_COLAB':
            try:
                import_colab_task.delay(str(job.id), job.filepath)
            except Exception:
                import_colab_task(job.id, job.filepath)
        elif job.job_type == 'RH_HIERARQUIA':
            try:
                import_hierarquia_task.delay(str(job.id), job.filepath)
            except Exception:
                import_hierarquia_task(job.id, job.filepath)
        elif job.job_type == 'RH_FERIAS':
            try:
                import_ferias_task.delay(str(job.id), job.filepath)
            except Exception:
                import_ferias_task(job.id, job.filepath)
        else:
            messages.error(request, "Tipo de job não suportado para retry.")
            return redirect('import_jobs')
        messages.success(request, f"Reprocessando job {job.id} ({job.job_type}).")
    except Exception as e:
        messages.error(request, f"Falha ao reprocessar: {e}")
    return redirect('import_jobs')


# --- ADMIN-ONLY: disparar seed de dados demo ---
@login_required
def seed_demo_view(request):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Acesso negado.")
        return redirect('home')
    try:
        from django.core.management import call_command
        call_command('seed_demo')
        messages.success(request, 'Base de demonstração carregada com sucesso!')
    except Exception as e:
        messages.error(request, f'Falha ao gerar dados de demonstração: {e}')
    # retorna ao RH (tem indicadores visuais) por padrão
    return redirect('modulo_rh')


@login_required
def fix_historico_proxima_view(request):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Acesso negado.")
        return redirect('home')
    try:
        from django.core.management import call_command
        recalc = bool(request.GET.get('recalc'))
        call_command('fix_historico_proxima', recalc=recalc)
        messages.success(request, 'Recalculo de próxima calibração concluído!')
    except Exception as e:
        messages.error(request, f'Falha no recalculo: {e}')
    return redirect('modulo_metrologia')


@login_required
def treinamentos_list_view(request):
    from .models import RegistroTreinamento, Colaborador, Procedimento
    qs = RegistroTreinamento.objects.select_related('colaborador', 'procedimento').all()
    colaboradores = Colaborador.objects.order_by('nome_completo')
    procedimentos = Procedimento.objects.order_by('codigo')
    status = request.GET.get('status')
    colaborador_id = request.GET.get('colaborador')
    procedimento_id = request.GET.get('procedimento')
    busca = request.GET.get('q')

    if status:
        # status_treinamento é uma property, não pode ser filtrada no queryset
        qs = [t for t in qs if t.status_treinamento == status]
    if colaborador_id:
        qs = qs.filter(colaborador_id=colaborador_id)
    if procedimento_id:
        qs = qs.filter(procedimento_id=procedimento_id)
    if busca:
        qs = qs.filter(
            Q(colaborador__nome_completo__icontains=busca) |
              Q(procedimento__codigo__icontains=busca) |
              Q(procedimento__titulo__icontains=busca)
        )
    treinamentos = qs.order_by('-data_treinamento')[:100]
    return render(request, "treinamentos_lista.html", {
        "treinamentos": treinamentos,
        "colaboradores": colaboradores,
        "procedimentos": procedimentos,
        "status": status,
        "colaborador_id": colaborador_id,
        "procedimento_id": procedimento_id,
        "busca": busca,
    })


@login_required
def registrar_historico_calibracao_view(request, instrumento_id):
    instrumento = get_object_or_404(Instrumento, id=instrumento_id)
    if request.method == 'POST':
        form = HistoricoCalibracaoForm(request.POST, request.FILES)
        if form.is_valid():
            historico = form.save(commit=False)
            historico.instrumento = instrumento
            historico.save()
            form.save_m2m()
            messages.success(request, 'Histórico de calibração registrado com sucesso!')
            return redirect('detalhe_instrumento', instrumento_id=instrumento.id)
    else:
        form = HistoricoCalibracaoForm()
    return render(request, 'registrar_historico_calibracao.html', {
        'form': form,
        'instrumento': instrumento
    })
