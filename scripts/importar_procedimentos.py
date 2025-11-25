"""
Script para importar procedimentos do JSON para o banco de dados Django
Execução: python manage.py shell < scripts/importar_procedimentos.py
"""

import json
import os
import django
from pathlib import Path

# Setup Django
BASE_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from qms.models import Procedimento

def mapear_tipo_documento(tipo, classificacao):
    """
    Mapeia o tipo de documento para título legível
    """
    mapeamento = {
        'POP': 'Procedimento Operacional Padrão',
        'DOC': 'Documento',
        'FOR': 'Formulário',
        'TAB': 'Tabela',
        'IT': 'Instrução de Trabalho',
        'DEX': 'Documento Externo',
        'INS': 'Instrução'
    }
    return mapeamento.get(tipo, classificacao)


def importar_procedimentos():
    """
    Importa todos os procedimentos do JSON para o banco
    """
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
            tipo = proc_data['tipo']
            classificacao = proc_data.get('classificacao', 'Documento')
            
            # Cria ou atualiza o procedimento
            procedimento, created = Procedimento.objects.update_or_create(
                codigo=codigo,
                defaults={
                    'titulo': nome[:200],  # Limita a 200 caracteres
                    'revisao_atual': '00',  # Revisão inicial padrão
                    'aplica_treinamento': True,  # Por padrão, todos aplicam treinamento
                }
            )
            
            if created:
                criados += 1
                print(f"✅ CRIADO: {codigo} - {nome[:50]}...")
            else:
                atualizados += 1
                print(f"🔄 ATUALIZADO: {codigo} - {nome[:50]}...")
                
        except Exception as e:
            erros += 1
            print(f"❌ ERRO em {proc_data.get('codigo', 'DESCONHECIDO')}: {e}")
    
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
    
    # Mostra amostra por tipo
    print("\n📌 Distribuição por tipo:")
    tipos = Procedimento.objects.values_list('codigo', flat=True)
    tipos_count = {}
    for codigo in tipos:
        tipo = codigo.split('.')[0]
        tipos_count[tipo] = tipos_count.get(tipo, 0) + 1
    
    for tipo, count in sorted(tipos_count.items()):
        print(f"   {tipo}: {count} procedimentos")


if __name__ == '__main__':
    print("🚀 Iniciando importação de procedimentos...\n")
    importar_procedimentos()
    print("\n✨ Importação concluída!")
