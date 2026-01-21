#!/usr/bin/env python
"""Apply stamp to certificate for testing."""
import os
import django
from io import BytesIO
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import HistoricoCalibracao
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from django.core.files.base import ContentFile

# Get historico 127
historico = HistoricoCalibracao.objects.get(id=127)
print(f"\n{'='*60}")
print(f"Aplicando carimbo ao Histórico ID: 127")
print(f"{'='*60}")

# Check certificate exists
if not historico.certificado:
    print("✗ Certificado original não encontrado!")
    exit(1)

print(f"\n✓ Certificado Original: {historico.certificado.name}")

try:
    # Read original PDF
    with historico.certificado.open('rb') as f:
        pdf_bytes = f.read()
    
    # Create stamp canvas
    stamp_buffer = BytesIO()
    stamp_canvas = canvas.Canvas(stamp_buffer, pagesize=letter)
    
    # Draw stamp content
    stamp_canvas.setFont("Helvetica-Bold", 12)
    stamp_canvas.drawString(100, 750, "CARIMBO DE VALIDACAO")
    stamp_canvas.setFont("Helvetica", 10)
    stamp_canvas.drawString(100, 730, "Resultado: OK")
    stamp_canvas.drawString(100, 715, "Data: 2025-01-11")
    stamp_canvas.drawString(100, 700, "Validador: Admin User")
    stamp_canvas.save()
    stamp_buffer.seek(0)
    
    # Read stamp PDF
    stamp_pdf = PdfReader(stamp_buffer)
    stamp_page = stamp_pdf.pages[0]
    
    # Read original PDF
    pdf_buffer = BytesIO(pdf_bytes)
    reader = PdfReader(pdf_buffer)
    writer = PdfWriter()
    
    # Merge stamp with first page of original
    first_page = reader.pages[0]
    first_page.merge_page(stamp_page)
    
    # Add all pages to writer
    for page in reader.pages:
        writer.add_page(page)
    
    # Write stamped PDF
    output = BytesIO()
    writer.write(output)
    output.seek(0)
    
    # Save to database
    filename = historico.certificado.name.replace('.pdf', '_carimbado.pdf')
    historico.certificado_carimbado.save(
        filename,
        ContentFile(output.getvalue())
    )
    historico.certificado_validado = True
    historico.save()
    
    print(f"\n✓ Carimbo aplicado com sucesso!")
    print(f"✓ Certificado Carimbado: {historico.certificado_carimbado.name}")
    print(f"✓ Certificado Validado: {historico.certificado_validado}")
    
except Exception as e:
    print(f"\n✗ Erro ao aplicar carimbo: {e}")
    import traceback
    traceback.print_exc()

print(f"\n{'='*60}\n")
