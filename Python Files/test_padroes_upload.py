"""
Test script to verify padrões upload workflow
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from metrologia.models import HistoricoCalibracao, ArquivoPadrao, Instrumento
from django.contrib.auth.models import User
from datetime import date

# Get or create a test history
try:
    instrumento = Instrumento.objects.first()
    if not instrumento:
        print("No instruments found. Creating a test one...")
        # Get first categoria if exists
        from metrologia.models import CategoriaInstrumento
        categoria = CategoriaInstrumento.objects.first()
        if not categoria:
            categoria = CategoriaInstrumento.objects.create(
                nome="PAQUIMETRO",
                sequencia=1
            )
        instrumento = Instrumento.objects.create(
            categoria_instrumento=categoria,
            numero_serie="TEST-001",
            descricao="Test Instrument"
        )
    
    historico = HistoricoCalibracao.objects.create(
        instrumento=instrumento,
        data_calibracao=date.today(),
        data_aprovacao=date.today()
    )
    
    print(f"✓ Histórico criado: {historico.id}")
    
    # Check current padrões
    count_before = historico.padroes_arquivo.count()
    print(f"✓ Padrões antes: {count_before}")
    
    # Simulate file upload
    test_pdf = SimpleUploadedFile(
        "test_padrao.pdf",
        b"%PDF-1.4\n%dummy content",
        content_type="application/pdf"
    )
    
    # Create ArquivoPadrao
    padrao = ArquivoPadrao.objects.create(
        historico=historico,
        nome="Test Padrao",
        descricao="Test",
        arquivo=test_pdf
    )
    
    print(f"✓ ArquivoPadrao criado: {padrao.id}")
    
    # Verify relationship
    historico.refresh_from_db()
    count_after = historico.padroes_arquivo.count()
    print(f"✓ Padrões depois: {count_after}")
    
    # List all padrões
    for p in historico.padroes_arquivo.all():
        print(f"  - {p.nome}")
    
    # Test related_name works
    print(f"✓ Related name test: {ArquivoPadrao.objects.filter(historico=historico).count()} padrões")
    
    print("\n✅ Upload workflow OK!")
    
except Exception as e:
    import traceback
    print(f"❌ Error: {e}")
    traceback.print_exc()
