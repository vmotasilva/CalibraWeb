#!/usr/bin/env python
"""
Test PDF stamping logic directly
"""
import os
import sys
import traceback
os.chdir(r'c:\CalibraWeb')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from metrologia.models import HistoricoCalibracao
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

print("🔍 Testing PDF stamping logic...")

# Get historico
historico = HistoricoCalibracao.objects.filter(id=127).first()
if not historico:
    print("❌ Historico not found")
    sys.exit(1)

print(f"✅ Historico: {historico}")

# Check if certificate exists
if not historico.certificado:
    print("❌ No certificate available")
    sys.exit(1)

print(f"✅ Certificate file: {historico.certificado}")
print(f"   File size: {historico.certificado.size} bytes")

# Test data
resultado = 'APROVADO_SEM_CORRECAO'
data_validacao = '2024-01-15'
nome_validador = 'admin'
carimbo_x = 150.0
carimbo_y = 200.0
carimbo_page = 1

print("\n📋 Stamp data:")
print(f"  resultado: {resultado}")
print(f"  data_validacao: {data_validacao}")
print(f"  nome_validador: {nome_validador}")
print(f"  carimbo_x: {carimbo_x}")
print(f"  carimbo_y: {carimbo_y}")
print(f"  carimbo_page: {carimbo_page}")

try:
    print("\n🔄 Reading PDF...")
    # Read original PDF - keep bytes in memory
    pdf_file = historico.certificado.open('rb')
    pdf_bytes = pdf_file.read()
    pdf_file.close()
    
    print(f"   ✅ PDF bytes read: {len(pdf_bytes)}")
    
    pdf_buffer = BytesIO(pdf_bytes)
    original_pdf = PdfReader(pdf_buffer)
    
    print(f"   ✅ PDF pages: {len(original_pdf.pages)}")
    
    print("\n🔄 Creating stamp...")
    # Create stamp overlay
    stamp_buffer = BytesIO()
    stamp_canvas = canvas.Canvas(stamp_buffer, pagesize=letter)
    
    x, y = carimbo_x, carimbo_y
    stamp_width, stamp_height = 120, 100
    
    # Draw rectangle border
    stamp_canvas.setLineWidth(2)
    stamp_canvas.rect(x, y, stamp_width, stamp_height)
    
    # Draw stamp text
    stamp_canvas.setFont("Helvetica-Bold", 8)
    stamp_canvas.drawString(x + 5, y + 85, "VALIDADO")
    
    stamp_canvas.setFont("Helvetica", 7)
    stamp_canvas.drawString(x + 5, y + 70, f"Resultado:")
    
    # Map resultado display names
    resultado_map = {
        'APROVADO_SEM_CORRECAO': 'Aprovado',
        'APROVADO_COM_CORRECAO': 'Aprovado c/ Correção',
        'REPROVADO': 'Reprovado'
    }
    resultado_display = resultado_map.get(resultado, resultado)
    stamp_canvas.setFont("Helvetica-Bold", 7)
    stamp_canvas.drawString(x + 5, y + 60, resultado_display)
    
    stamp_canvas.setFont("Helvetica", 7)
    stamp_canvas.drawString(x + 5, y + 45, f"Data: {data_validacao}")
    stamp_canvas.drawString(x + 5, y + 30, f"Validador:")
    stamp_canvas.drawString(x + 5, y + 20, nome_validador[:18])
    
    stamp_canvas.save()
    stamp_buffer.seek(0)
    
    print(f"   ✅ Stamp created: {len(stamp_buffer.getvalue())} bytes")
    
    print("\n🔄 Merging stamp with PDF...")
    # Read stamp from buffer
    stamp_buffer_bytes = BytesIO(stamp_buffer.getvalue())
    stamp_pdf = PdfReader(stamp_buffer_bytes)
    stamp_page = stamp_pdf.pages[0]
    
    print(f"   ✅ Stamp PDF pages: {len(stamp_pdf.pages)}")
    
    # Apply stamp to specific page
    writer = PdfWriter()
    for idx, page in enumerate(original_pdf.pages):
        if idx == (carimbo_page - 1):
            print(f"   ℹ️  Merging stamp on page {idx + 1}")
            page.merge_page(stamp_page)
        writer.add_page(page)
    
    print(f"   ✅ All pages added to writer: {len(writer.pages)}")
    
    print("\n🔄 Writing stamped PDF...")
    # Save stamped PDF
    stamped_buffer = BytesIO()
    writer.write(stamped_buffer)
    stamped_buffer.seek(0)
    
    print(f"   ✅ Stamped PDF created: {len(stamped_buffer.getvalue())} bytes")
    
    print("\n✅ PDF stamping logic works correctly!")
    
except Exception as e:
    print(f"\n❌ Error:")
    print(f"  Type: {type(e).__name__}")
    print(f"  Message: {str(e)}")
    print("\n📋 Traceback:")
    traceback.print_exc()
