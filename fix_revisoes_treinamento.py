#!/usr/bin/env python
"""
Script para atualizar revisão_treinada nos registros de treinamento

Problema: Registros antigos têm revisao_treinada vazia ou errada
Solução: Preencher com a revisão atual do procedimento para cada registro

Uso: python manage.py shell < fix_revisoes_treinamento.py
"""

from training.models import RegistroTreinamento
from procedures.models import Procedimento

def fix_revisoes():
    print("=" * 70)
    print("ATUALIZANDO REVISÕES DE TREINAMENTO")
    print("=" * 70)
    
    total_registros = RegistroTreinamento.objects.count()
    print(f"\nTotal de registros: {total_registros}")
    
    # Contar problemas
    sem_revisao = 0
    com_revisao_errada = 0
    atualizados = 0
    
    for registro in RegistroTreinamento.objects.all():
        proc = registro.procedimento
        revisao_atual = str(proc.numero_revisao).strip() if hasattr(proc, 'numero_revisao') else 'ATUAL'
        revisao_registrada = str(registro.revisao_treinada).strip() if registro.revisao_treinada else ''
        
        # Verificar se está vazio ou diferente
        if not revisao_registrada or revisao_registrada == '':
            sem_revisao += 1
            print(f"[SEM REVISÃO] {registro.colaborador.nome_completo} - {proc.codigo}")
            
            # Atualizar com a revisão atual
            registro.revisao_treinada = revisao_atual
            registro.save(update_fields=['revisao_treinada'])
            atualizados += 1
            
        elif revisao_registrada != revisao_atual and revisao_registrada != 'PENDENTE':
            com_revisao_errada += 1
            print(f"[REVISÃO ERRADA] {registro.colaborador.nome_completo} - {proc.codigo}: {revisao_registrada} → {revisao_atual}")
            
            # Se tem data de treinamento e revisão diferente, atualizar
            if registro.data_treinamento:
                registro.revisao_treinada = revisao_atual
                registro.save(update_fields=['revisao_treinada'])
                atualizados += 1
    
    print("\n" + "=" * 70)
    print("RESUMO DA ATUALIZAÇÃO")
    print("=" * 70)
    print(f"Registros SEM revisão: {sem_revisao}")
    print(f"Registros COM revisão errada: {com_revisao_errada}")
    print(f"Registros ATUALIZADOS: {atualizados}")
    print("\nProblema resolvido! Agora 'Vigentes' deve mostrar os valores corretos.")
    print("=" * 70)

if __name__ == "__main__":
    fix_revisoes()
