#!/usr/bin/env python
"""
Test script for carimbo functionality
"""
import os
import django
from io import BytesIO

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import HistoricoCalibracao
from django.contrib.auth.models import User
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from django.core.files.base import ContentFile

# Get test data
historico_id = 127
try:
    historico = HistoricoCalibracao.objects.get(id=historico_id)
    print(f"✓ Histórico encontrado: {historico.id}")
    print(f"  - Certificado original: {historico.certificado}")
    print(f"  - Certificado carimbado: {historico.certificado_carimbado}")
    
    if historico.certificado:
        print(f"\n✓ Certificado original existe: {historico.certificado.size} bytes")
        
        # Try to read the original PDF
        with historico.certificado.open('rb') as f:
            original_pdf = PdfReader(f)
            print(f"✓ PDF original carregado com {len(original_pdf.pages)} páginas")
        
        # Test stamp creation
        print("\n--- Testando criação de carimbo ---")
        
        # Create stamp overlay using ReportLab
        stamp_buffer = BytesIO()
        stamp_canvas = canvas.Canvas(stamp_buffer, pagesize=(612, 792))  # letter size
        
        # Draw stamp box
        x, y = 450, 100
        stamp_width, stamp_height = 120, 100
        
        stamp_canvas.setLineWidth(2)
        stamp_canvas.rect(x, y, stamp_width, stamp_height)
        
        stamp_canvas.setFont("Helvetica-Bold", 8)
        stamp_canvas.drawString(x + 5, y + 85, "VALIDADO")
        
        stamp_canvas.setFont("Helvetica", 7)
        stamp_canvas.drawString(x + 5, y + 70, f"Resultado:")
        stamp_canvas.drawString(x + 5, y + 60, "Aprovado")
        stamp_canvas.drawString(x + 5, y + 45, f"Data: 2024-01-15")
        stamp_canvas.drawString(x + 5, y + 30, f"Validador:")
        stamp_canvas.drawString(x + 5, y + 20, "Admin User")
        
        stamp_canvas.save()
        stamp_buffer.seek(0)
        
        print("✓ Carimbo criado com sucesso")
        
        # Test merging
        stamp_pdf = PdfReader(stamp_buffer)
        stamp_page = stamp_pdf.pages[0]
        
        writer = PdfWriter()
        with historico.certificado.open('rb') as f:
            original_pdf = PdfReader(f)
            for page in original_pdf.pages:
                page.merge_page(stamp_page)
                writer.add_page(page)
        
        stamped_buffer = BytesIO()
        writer.write(stamped_buffer)
        stamped_buffer.seek(0)
        
        print(f"✓ PDF carimbado criado: {stamped_buffer.getbuffer().nbytes} bytes")
        print("\n✓ Teste de carimbo PASSOU!")
        
    else:
        print("✗ Histórico não possui certificado")
        
except HistoricoCalibracao.DoesNotExist:
    print(f"✗ Histórico {historico_id} não encontrado")
except Exception as e:
    print(f"✗ Erro: {str(e)}")
    import traceback
    traceback.print_exc()
