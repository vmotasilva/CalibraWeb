"""
Management command para importar procedimentos do JSON
Execução: python manage.py importar_procedimentos
"""

import json
from pathlib import Path
from django.core.management.base import BaseCommand
from qms.models import Procedimento


class Command(BaseCommand):
    help = 'Importa procedimentos do arquivo JSON para o banco de dados'

    def handle(self, *args, **options):
        BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
        json_path = BASE_DIR / 'database' / 'procedimentos_extraidos.json'
        
        self.stdout.write(f"Lendo arquivo: {json_path}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            procedimentos_data = json.load(f)
        
        self.stdout.write(f"Total de {len(procedimentos_data)} procedimentos no JSON\n")
        
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
                    self.stdout.write(
                        self.style.SUCCESS(f"CRIADO: {codigo} - {nome[:50]}...")
                    )
                else:
                    atualizados += 1
                    
            except Exception as e:
                erros += 1
                self.stdout.write(
                    self.style.ERROR(f"ERRO em {proc_data.get('codigo', '???')}: {e}")
                )
        
        self.stdout.write("\n" + "="*70)
        self.stdout.write(self.style.WARNING("RELATORIO DE IMPORTACAO"))
        self.stdout.write("="*70)
        self.stdout.write(f"Criados: {criados}")
        self.stdout.write(f"Atualizados: {atualizados}")
        self.stdout.write(f"Erros: {erros}")
        self.stdout.write(f"Total processado: {len(procedimentos_data)}")
        self.stdout.write("="*70)
        
        # Verifica total no banco
        total_banco = Procedimento.objects.count()
        self.stdout.write(f"\nTotal de procedimentos no banco: {total_banco}")
        
        # Mostra distribuição por tipo
        self.stdout.write("\nDistribuicao por tipo:")
        tipos_count = {}
        for codigo in Procedimento.objects.values_list('codigo', flat=True):
            tipo = codigo.split('.')[0]
            tipos_count[tipo] = tipos_count.get(tipo, 0) + 1
        
        for tipo, count in sorted(tipos_count.items()):
            self.stdout.write(f"   {tipo}: {count} procedimentos")
        
        self.stdout.write(self.style.SUCCESS("\nImportacao concluida."))
