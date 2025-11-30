import io
from datetime import datetime, timedelta
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.shortcuts import render, redirect
from .forms import CarimboForm
from .models import Instrumento, HistoricoCalibracao
from PyPDF2 import PdfReader, PdfWriter

@login_required
def carimbar_view(request):
    colab = get_colab(request)
    instrumentos_disponiveis = Instrumento.objects.filter(ativo=True).prefetch_related('faixas').order_by("tag")
    instrumentos_data = []
    for inst in instrumentos_disponiveis:
        tol_val = None
        try:
            for fx in inst.faixas.all():
                if getattr(fx, 'tolerancia_mais_menos', None) is not None:
                    tol_val = fx.tolerancia_mais_menos
                    break
        except Exception:
            tol_val = None
        instrumentos_data.append({
            'id': inst.id,
            'tag': inst.tag,
            'descricao': inst.descricao,
            'tolerancia': tol_val,
        })
    user_full_name = f"{request.user.first_name} {request.user.last_name}".strip()
    if not user_full_name:
        user_full_name = request.user.username.upper()

    if request.method == "POST":
        form = CarimboForm(request.POST, request.FILES)
        if form.is_valid():
            responsavel_tecnico = request.POST.get("responsavel_tecnico_0") or str(colab)
            dt_validacao = form.cleaned_data["data_validacao"]
            status_txt = form.cleaned_data["status_validacao"]
            is_rbc = form.cleaned_data.get("is_rbc", False)
            padroes_selecionados = form.cleaned_data.get("padroes", [])
            def parse_dec(v):
                if v is None or v == "":
                    return None
                try:
                    return Decimal(str(v).replace(',', '.'))
                except Exception:
                    return None
            fs = request.FILES.getlist("arquivo_pdf")
            processed_files = []
            try:
                screen_w = float(request.POST.get("page_width", 0))
                screen_h = float(request.POST.get("page_height", 0))
            except:
                screen_w = 0
                screen_h = 0
            processed_files = []
            for i, f in enumerate(fs):
                raw_x = request.POST.get(f"x_{i}", 0)
                raw_y = request.POST.get(f"y_{i}", 0)
                raw_w = request.POST.get(f"w_{i}", 0)
                raw_h = request.POST.get(f"h_{i}", 0)
                ui = (
                    float(raw_x),
                    float(raw_y),
                    float(raw_w),
                    float(raw_h),
                    screen_w,
                    screen_h,
                )
                try:
                    page_index = int(request.POST.get(f"page_{i}", 0))
                except Exception:
                    page_index = 0
                inst_id = request.POST.get(f"instrument_id_{i}")
                calib_date_str = request.POST.get(f"calib_date_{i}")
                cert_num = request.POST.get(f"cert_num_{i}", f.name)
                if inst_id and calib_date_str:
                    try:
                        instrumento = Instrumento.objects.get(id=inst_id)
                        dt_calibracao = datetime.strptime(
                            calib_date_str, "%Y-%m-%d"
                        ).date()
                        prox_calib = None
                        if instrumento.frequencia_meses:
                            prox_calib = dt_calibracao + timedelta(
                                days=instrumento.frequencia_meses * 30
                            )
                        erro_in = parse_dec(request.POST.get(f"err_{i}"))
                        inc_in = parse_dec(request.POST.get(f"inc_{i}"))
                        tol_in = parse_dec(request.POST.get(f"tol_{i}"))
                        if tol_in is None:
                            try:
                                for fx in instrumento.faixas.all():
                                    v = getattr(fx, 'tolerancia_mais_menos', None)
                                    if v is not None:
                                        tol_in = Decimal(str(v))
                                        break
                            except Exception:
                                tol_in = None
                        status_item = status_txt
                        resultado_item = "APROVADO"
                        if erro_in is not None and inc_in is not None and tol_in is not None:
                            try:
                                ema = abs(tol_in) / Decimal(2)
                                eme = abs(erro_in) + abs(inc_in)
                                if eme <= ema:
                                    resultado_item = "APROVADO"
                                    status_item = "Aprovado sem correções"
                                elif eme > (ema * Decimal(3)):
                                    resultado_item = "REPROVADO"
                                    status_item = "Reprovado"
                                else:
                                    resultado_item = "CONDICIONAL"
                                    status_item = "Aprovado com correções"
                            except Exception:
                                pass
                        else:
                            if status_item == "Reprovado":
                                resultado_item = "REPROVADO"
                            elif status_item == "Aprovado com correções":
                                resultado_item = "CONDICIONAL"
                        hist, created = HistoricoCalibracao.objects.get_or_create(
                            instrumento=instrumento,
                            data_calibracao=dt_calibracao,
                            numero_certificado=cert_num,
                            defaults={
                                "proxima_calibracao": prox_calib,
                                "resultado": resultado_item,
                                "responsavel": responsavel_tecnico,
                                "observacoes": f"Validado por {responsavel_tecnico}: {status_item}",
                                "tem_selo_rbc": is_rbc,
                                "tipo_calibracao": "EXTERNA",
                            },
                        )
                        if erro_in is not None:
                            hist.erro_encontrado = erro_in
                        if inc_in is not None:
                            hist.incerteza = inc_in
                        if tol_in is not None:
                            hist.tolerancia_usada = tol_in
                        if not created:
                            hist.resultado = resultado_item
                            hist.observacoes = f"Revalidado: {status_item}"
                        if not is_rbc and padroes_selecionados:
                            hist.padroes_utilizados.set(padroes_selecionados)
                        pdf_buffer = apply_stamp_logic(
                            f, responsavel_tecnico, status_item, instrumento.id, dt_validacao
                        )
                        filename = f"Cert_{cert_num}_{instrumento.tag}.pdf"
                        hist.certificado.save(
                            filename, ContentFile(pdf_buffer.getvalue())
                        )
                        hist.save()
                    except Exception as e:
                        print(f"Erro: {e}")
                if inst_id and calib_date_str:
                    try:
                        pdf_buffer.seek(0)
                        processed_files.append((f.name, pdf_buffer))
                    except Exception:
                        processed_files.append((f.name, io.BytesIO()))
            if len(processed_files) == 1:
                fname, fbuf = processed_files[0]
                r = HttpResponse(fbuf, content_type="application/pdf")
                r["Content-Disposition"] = f'attachment; filename="Validado_{fname}"'
                return r
            else:
                messages.error(request, "Selecione apenas um arquivo por vez para carimbar.")
                return redirect("carimbar")
    else:
        form = CarimboForm()
    return render(
        request,
        "carimbo.html",
        {
            "form": form,
            "colaborador": colab,
            "user_full_name": user_full_name,
            "instrumentos": instrumentos_disponiveis,
            "instrumentos_data": instrumentos_data,
            "is_superuser": request.user.is_superuser,
        },
    )

# Função utilitária (pode ser importada do views.py original ou movida para cá)
from .views import get_colab




# Nova versão: usa placeholder salvo e campos dinâmicos

from qms.models import CarimboPlaceholder
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse


# View para salvar o placeholder do carimbo (fora de qualquer função)
@csrf_exempt
def salvar_placeholder_carimbo(request):
    if request.method == 'POST':
        try:
            data = request.POST
            instrumento = str(data.get('instrumento')) if data.get('instrumento') is not None else None
            page_index = int(data.get('page_index', 0))
            x = float(data.get('x'))
            y = float(data.get('y'))
            w = float(data.get('w'))
            h = float(data.get('h'))
            screen_w = float(data.get('screen_w'))
            screen_h = float(data.get('screen_h'))
            # Remove placeholders antigos para o mesmo instrumento e página
            CarimboPlaceholder.objects.filter(instrumento=instrumento, page_index=page_index).delete()
            CarimboPlaceholder.objects.create(
                instrumento=instrumento,
                page_index=page_index,
                x=x, y=y, w=w, h=h, screen_w=screen_w, screen_h=screen_h
            )
            return JsonResponse({'success': True, 'msg': 'Placeholder salvo com sucesso!'})
        except Exception as e:
            return JsonResponse({'success': False, 'msg': f'Erro ao salvar: {e}'})
    return JsonResponse({'success': False, 'msg': 'Método não permitido.'})

def apply_stamp_logic(pdf_file, responsavel, resultado, instrumento, dt_validacao):

    """
    Aplica o carimbo na posição do placeholder salvo para o instrumento (ou global), preenchendo campos dinâmicos.
    """
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import black, white, HexColor
    from PyPDF2 import PdfReader, PdfWriter
    import io

    # Busca placeholder salvo
    try:
        placeholder = CarimboPlaceholder.objects.filter(instrumento=instrumento).order_by('-criado_em').first()
        if not placeholder:
            placeholder = CarimboPlaceholder.objects.filter(instrumento__isnull=True).order_by('-criado_em').first()
        if not placeholder:
            raise Exception("Nenhum placeholder de carimbo configurado.")
    except Exception as e:
        raise Exception(f"Erro ao buscar placeholder: {e}")

    x, y, w, h, screen_w, screen_h = placeholder.x, placeholder.y, placeholder.w, placeholder.h, placeholder.screen_w, placeholder.screen_h
    page_index = placeholder.page_index

    # Cores do resultado (case-insensitive, tolerante a variações)
    resultado_key = (resultado or '').strip().lower()
    if 'reprovado' in resultado_key:
        cor = '#d32f2f'
    elif 'correç' in resultado_key:
        cor = '#fbc02d'
    else:
        cor = '#388e3c'

    pdf_file.seek(0)
    reader = PdfReader(pdf_file)
    writer = PdfWriter()

    page = reader.pages[page_index]
    mediabox = page.mediabox
    page_width = float(mediabox.width)
    page_height = float(mediabox.height)

    # Ajuste de escala para posição do carimbo
    scale_x = page_width / screen_w if screen_w else 1
    scale_y = page_height / screen_h if screen_h else 1
    cx = x * scale_x
    cy = page_height - (y * scale_y) - (h * scale_y)
    cw = w * scale_x
    ch = h * scale_y
    if cw < 80: cw = 180
    if ch < 30: ch = 40

    # Cria overlay apenas para a página do carimbo
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_width, page_height))
    # Limpa área do carimbo
    c.setFillColor(white)
    c.rect(cx, cy, cw, ch, fill=1, stroke=0)
    # Borda
    c.setStrokeColor(HexColor(cor))
    c.setLineWidth(2)
    c.rect(cx, cy, cw, ch, fill=0, stroke=1)
    # Padding interno
    pad_x, pad_y, line_gap = 16, 14, 18
    # Texto do carimbo
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(HexColor(cor))
    c.drawString(cx + pad_x, cy + ch - pad_y, resultado)
    c.setFont("Helvetica", 11)
    c.setFillColor(black)
    c.drawString(cx + pad_x, cy + ch - pad_y - line_gap, str(dt_validacao))
    c.drawString(cx + pad_x, cy + pad_y, f"RESP: {responsavel}")
    c.save()
    packet.seek(0)
    overlay = PdfReader(packet)

    for i in range(len(reader.pages)):
        base = reader.pages[i]
        if i == page_index:
            base.merge_page(overlay.pages[0])
        writer.add_page(base)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output
