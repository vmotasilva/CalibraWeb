#!/usr/bin/env python
import os
import sys
import django

# Adicionar o diretório ao path
sys.path.insert(0, 'c:\\CalibraWeb')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import Instrumento, ItemCotacao, AtendimentoSolicitacao, SolicitacaoCotacao

# Buscar instrumento TH-05
try:
    # Listar alguns instrumentos primeiro
    print("Procurando por TH-05...")
    todos_inst = Instrumento.objects.filter(tag__startswith='TH')
    print(f"Encontrados {todos_inst.count()} instrumentos com tag iniciando em 'TH':")
    for inst_temp in todos_inst[:10]:
        print(f"  - tag: {inst_temp.tag}, serie: {inst_temp.serie}, id: {inst_temp.id}")
    
    # Procurar especificamente TH-05
    inst_matches = Instrumento.objects.filter(tag='TH-05')
    if inst_matches.exists():
        inst = inst_matches.first()
        print(f"\n✅ Encontrado instrumento: {inst.tag}")
    else:
        # Tentar procurar apenas 05
        inst_matches = Instrumento.objects.filter(tag__contains='05')
        if inst_matches.count() == 1:
            inst = inst_matches.first()
            print(f"\n✅ Encontrado (alternativo): {inst.tag}")
        else:
            print(f"\n❌ Não encontrou TH-05. Existem {inst_matches.count()} instrumentos com '05'")
            for im in inst_matches:
                print(f"    - {im.tag}")
            raise Instrumento.DoesNotExist()
    print(f"\n{'='*80}")
    print(f"DIAGNÓSTICO - INSTRUMENTO TH-05")
    print(f"{'='*80}\n")
    
    # 1. Todas as cotações para TH-05
    cotacoes = ItemCotacao.objects.filter(instrumento=inst)
    print(f"1️⃣  COTAÇÕES PARA TH-05: {cotacoes.count()} registros")
    
    for i, cot in enumerate(cotacoes, 1):
        print(f"\n   [{i}] ItemCotacao ID: {cot.id}")
        print(f"       Fornecedor: {cot.cotacao_fornecedor.fornecedor.nome_fantasia}")
        print(f"       Cotação Número: {cot.cotacao_fornecedor.numero}")
        print(f"       🔴 tipo_servico: '{cot.tipo_servico}'")
        print(f"       🔴 local_atendimento: '{cot.local_atendimento}'")
        print(f"       Atendimentos vinculados: {cot.atendimentos.count()}")
        for at in cot.atendimentos.all():
            print(f"           - ID: {at.id}, Status: {at.status}, Data Realizada: {at.data_realizada}")
    
    # 2. Valores únicos
    print(f"\n\n2️⃣  VALORES ÚNICOS ENCONTRADOS NO BANCO:")
    
    tipos_servico = ItemCotacao.objects.filter(instrumento=inst).values_list('tipo_servico', flat=True).distinct()
    print(f"\n   Tipos de Serviço:")
    for ts in tipos_servico:
        print(f"      ✓ '{ts}'")
    
    locais_atendimento = ItemCotacao.objects.filter(instrumento=inst).values_list('local_atendimento', flat=True).distinct()
    print(f"\n   Locais de Atendimento:")
    for la in locais_atendimento:
        print(f"      ✓ '{la}'")
    
    # 3. Verificar a query que escrevi na view
    print(f"\n\n3️⃣  TESTE DA QUERY (como está na view):")
    
    # Buscar como fiz na view
    cotacoes_calibracao = [c for c in cotacoes if c.tipo_servico == 'CALIBRACAO']
    print(f"   Filtro tipo_servico='CALIBRACAO': {len(cotacoes_calibracao)} resultados")
    
    cotacoes_aquisicao = [c for c in cotacoes if c.tipo_servico == 'AQUISICAO']
    print(f"   Filtro tipo_servico='AQUISICAO': {len(cotacoes_aquisicao)} resultados")
    
    rastreios_laboratorio = [at for cot in cotacoes for at in cot.atendimentos.all() if cot.local_atendimento == 'NO_LABORATORIO']
    print(f"   Filtro local_atendimento='NO_LABORATORIO': {len(rastreios_laboratorio)} resultados")
    
    # 4. Procurar em TODAS as solicitações com TH-05
    print(f"\n\n4️⃣  ATENDIMENTOS TOTAIS PARA TH-05:")
    atendimentos_totais = AtendimentoSolicitacao.objects.filter(
        item_solicitacao__instrumento=inst
    ).select_related('item_cotacao')
    
    print(f"   Total de atendimentos: {atendimentos_totais.count()}")
    for at in atendimentos_totais[:10]:  # Primeiros 10
        print(f"\n   ├─ ID: {at.id}")
        print(f"   ├─ Solicitação: {at.solicitacao.numero}")
        print(f"   ├─ Item Cotação tipo_servico: '{at.item_cotacao.tipo_servico}'")
        print(f"   ├─ Item Cotação local_atendimento: '{at.item_cotacao.local_atendimento}'")
        print(f"   ├─ Status: {at.status}")
        print(f"   └─ Data Realizada: {at.data_realizada}")
    
    print(f"\n{'='*80}\n")
    
except Instrumento.DoesNotExist:
    print("❌ Instrumento TH-05 não encontrado!")
except Exception as e:
    print(f"❌ Erro: {str(e)}")
    import traceback
    traceback.print_exc()
