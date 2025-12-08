"""
Script para importar procedimentos via Django shell
Execução: python manage.py shell < scripts/importar_procedimentos_shell.py
"""

import json
from pathlib import Path

# Importa modelos
from training.models import Procedimento

# Define caminho do JSON
BASE_DIR = Path('C:/Users/Vinícius Mota/Documents/PYTHON/CalibraWeb')
json_path = BASE_DIR / 'database' / 'procedimentos_extraidos.json'

print(f"📂 Lendo arquivo: {json_path}")

with open(json_path, 'r', encoding='utf-8') as f:
    procedimentos_data = json.load(f)

print(f"📋 Total de {len(procedimentos_data)} procedimentos no JSON\n")

# Estatísticas
criados = 0
atualizados = 0
erros = 0

for proc_data in procedimentos_data:
    try:
        codigo = proc_data['codigo']
        nome = proc_data['nome']
        
        # Cria ou atualiza o procedimento
        procedimento, created = Procedimento.objects.update_or_create(
            codigo=codigo,
            defaults={
                'titulo': nome[:200],  # Limita a 200 caracteres
                'revisao_atual': '00',  # Revisão inicial padrão
                'aplica_treinamento': True,
            }
        )
        
        if created:
            criados += 1
            print(f"✅ CRIADO: {codigo} - {nome[:50]}...")
        else:
            atualizados += 1
            
    except Exception as e:
        erros += 1
        print(f"❌ ERRO em {proc_data.get('codigo', '???')}: {e}")

print("\n" + "="*70)
print("📊 RELATÓRIO DE IMPORTAÇÃO")
print("="*70)
print(f"✅ Criados: {criados}")
print(f"🔄 Atualizados: {atualizados}")
print(f"❌ Erros: {erros}")
print(f"📦 Total processado: {len(procedimentos_data)}")
print("="*70)

# Verifica total no banco
total_banco = Procedimento.objects.count()
print(f"\n🗄️  Total de procedimentos no banco: {total_banco}")

# Mostra distribuição por tipo
print("\n📌 Distribuição por tipo:")
tipos_count = {}
for codigo in Procedimento.objects.values_list('codigo', flat=True):
    tipo = codigo.split('.')[0]
    tipos_count[tipo] = tipos_count.get(tipo, 0) + 1

for tipo, count in sorted(tipos_count.items()):
    print(f"   {tipo}: {count} procedimentos")

print("\n✨ Importação concluída!")
