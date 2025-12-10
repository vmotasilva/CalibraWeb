#!/usr/bin/env python
"""
Test script to verify if measurement ranges are now appearing in the calibration history editor.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from metrologia.models import HistoricoCalibracao

def test_measurement_ranges():
    """Test if measurement ranges are displayed in the calibration history editor."""
    
    client = Client()
    
    # Find a historical calibration record with measurement ranges
    historicos = HistoricoCalibracao.objects.all().first()
    
    if not historicos:
        print("⚠ No calibration history found.")
        return
    
    # Check if it has measurement ranges
    num_resultados = historicos.resultados_faixa.count()
    if num_resultados == 0:
        # Try to find one with ranges
        historicos = None
        for h in HistoricoCalibracao.objects.all()[:10]:
            if h.resultados_faixa.count() > 0:
                historicos = h
                num_resultados = h.resultados_faixa.count()
                break
    
    if not historicos or num_resultados == 0:
        print("⚠ No calibration history with measurement ranges found.")
        return
    
    historico_id = historicos.id
    print(f"Testing calibration history ID: {historico_id}")
    print(f"Expected number of measurement ranges: {num_resultados}")
    
    # Make a request to the edit page
    response = client.get(f'/metrologia/historico/{historico_id}/editar/')
    
    print(f"Response Status: {response.status_code}")
    
    if response.status_code == 200:
        content = response.content.decode('utf-8')
        
        # Check if the measurement ranges section is present
        if 'Resultados de Medição por Faixa' in content:
            print("✓ Measurement ranges section found in HTML")
        else:
            print("✗ Measurement ranges section NOT found in HTML")
        
        # Check if "Nenhum resultado" message appears
        if 'Nenhum resultado de faixa cadastrado ainda' in content:
            print("✗ 'No measurement ranges' message found - Ranges not displaying")
        else:
            print("✓ 'No measurement ranges' message NOT found - Good sign!")
        
        # Check if we can find table rows with range data
        if '<tr>' in content and 'Faixa' in content:
            # Count how many range result rows are in the response
            import re
            # This is a simple check - looking for the table structure
            modal_count = content.count('editResultModal')
            print(f"Found {modal_count} measurement range result rows")
            
            if modal_count > 0:
                print("✓ SUCCESS: Measurement ranges are now displaying!")
                
                # Show sample of range data
                import re
                ranges = re.findall(r'<strong>([\d.]+)</strong> a <strong>([\d.]+)</strong>', content)
                if ranges:
                    print(f"\nSample ranges found:")
                    for i, (min_val, max_val) in enumerate(ranges[:5], 1):
                        print(f"  {i}. {min_val} a {max_val}")
                    if len(ranges) > 5:
                        print(f"  ... and {len(ranges) - 5} more")
            else:
                print("✗ FAIL: No measurement ranges found in HTML")
    else:
        print(f"✗ Failed to retrieve page: Status {response.status_code}")

if __name__ == '__main__':
    test_measurement_ranges()
