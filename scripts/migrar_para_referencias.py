#!/usr/bin/env python
# coding: utf-8
"""
Script para migrar instrumentos existentes para o novo modelo de referencia.

Objetivo:
- Atribuir cada instrumento ativo a uma InstrumentoReferencia
- Criar FaixaMedicaoPadrao baseadas nas faixas existentes
- Vincular faixas existentes ao template

Uso:
    python manage.py shell < scripts/migrar_para_referencias.py
    
Ou de dentro do shell Django:
    exec(open('scripts/migrar_para_referencias.py').read())
"""

import logging
from decimal import Decimal
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def migrar_instrumentos_para_referencias():
    """
    Migra instrumentos existentes para usar o modelo de referência.
    """
    from metrologia.models import (
        Instrumento, InstrumentoReferencia, FaixaMedicao, FaixaMedicaoPadrao
    )
    from django.db import transaction
    
    logger.info("=" * 80)
    logger.info("INICIANDO MIGRAÇÃO DE INSTRUMENTOS PARA REFERÊNCIAS")
    logger.info("=" * 80)
    
    # Contadores
    total_instrumentos = Instrumento.objects.count()
    referencias_criadas = 0
    instrumentos_vinculados = 0
    faixas_padrao_criadas = 0
    faixas_vinculadas = 0
    erros = 0
    
    logger.info(f"\nTotal de instrumentos no banco: {total_instrumentos}")
    
    try:
        with transaction.atomic():
            # 1. Processar instrumentos ativos primeiro
            logger.info("\n--- PROCESSANDO INSTRUMENTOS ATIVOS ---")
            
            instrumentos_ativos = Instrumento.objects.filter(ativo=True).order_by('categoria', 'tag')
            logger.info(f"Instrumentos ativos: {instrumentos_ativos.count()}")
            
            for instrumento in instrumentos_ativos:
                try:
                    # Se já tem referência, pular
                    if instrumento.referencia:
                        logger.debug(f"  {instrumento.tag} já tem referência: {instrumento.referencia.codigo_referencia}")
                        continue
                    
                    # Criar ou obter referência usando o código do instrumento como base
                    codigo_ref = f"{instrumento.categoria.nome[:3].upper()}-{instrumento.tag}"
                    
                    referencia, criada = InstrumentoReferencia.objects.get_or_create(
                        codigo_referencia=codigo_ref,
                        defaults={
                            'categoria': instrumento.categoria,
                            'descricao': f"Referência para {instrumento.descricao}"
                        }
                    )
                    
                    if criada:
                        logger.info(f"  ✓ Referência criada: {codigo_ref}")
                        referencias_criadas += 1
                    else:
                        logger.info(f"  ✓ Referência existente: {codigo_ref}")
                    
                    # Vincular instrumento à referência
                    instrumento.referencia = referencia
                    instrumento.save()
                    instrumentos_vinculados += 1
                    
                    # 2. Criar templates de faixas (FaixaMedicaoPadrao)
                    faixas = FaixaMedicao.objects.filter(instrumento=instrumento)
                    
                    for faixa in faixas:
                        faixa_padrao, created = FaixaMedicaoPadrao.objects.get_or_create(
                            referencia_instrumento=referencia,
                            unidade=faixa.unidade,
                            valor_minimo=faixa.valor_minimo,
                            valor_maximo=faixa.valor_maximo,
                            defaults={
                                'resolucao': faixa.resolucao,
                                'nominal': faixa.nominal,
                                'tolerancia_mais_menos': faixa.tolerancia_mais_menos,
                                'ativa': True
                            }
                        )
                        
                        if created:
                            logger.debug(f"    Template criado: {faixa.unidade.simbolo} ({faixa.valor_minimo}-{faixa.valor_maximo})")
                            faixas_padrao_criadas += 1
                        
                        # Vincular faixa existente ao template
                        if not faixa.faixa_padrao:
                            faixa.faixa_padrao = faixa_padrao
                            faixa.save()
                            faixas_vinculadas += 1
                    
                    logger.info(f"    {instrumento.tag}: {faixas.count()} faixa(s)")
                    
                except Exception as e:
                    logger.error(f"  ✗ Erro ao processar {instrumento.tag}: {str(e)}")
                    erros += 1
            
            # 3. Processar instrumentos inativos (para manter histórico)
            logger.info("\n--- PROCESSANDO INSTRUMENTOS INATIVOS ---")
            
            instrumentos_inativos = Instrumento.objects.filter(ativo=False).order_by('categoria', 'tag')
            logger.info(f"Instrumentos inativos: {instrumentos_inativos.count()}")
            
            for instrumento in instrumentos_inativos:
                try:
                    if instrumento.referencia:
                        logger.debug(f"  {instrumento.tag} já tem referência: {instrumento.referencia.codigo_referencia}")
                        continue
                    
                    # Tentar encontrar referência compatível pelo código ou tag
                    codigo_ref = f"{instrumento.categoria.nome[:3].upper()}-{instrumento.tag}"
                    
                    # Procurar por referência similar (mesmo código base)
                    referencias_similares = InstrumentoReferencia.objects.filter(
                        categoria=instrumento.categoria,
                        codigo_referencia__startswith=instrumento.categoria.nome[:3].upper()
                    )
                    
                    if referencias_similares.exists():
                        # Usar a primeira referência similar
                        referencia = referencias_similares.first()
                        logger.info(f"  ✓ Vinculado a referência existente: {referencia.codigo_referencia}")
                    else:
                        # Criar nova referência
                        referencia, _ = InstrumentoReferencia.objects.get_or_create(
                            codigo_referencia=codigo_ref,
                            defaults={
                                'categoria': instrumento.categoria,
                                'descricao': f"Referência para {instrumento.descricao} (histórico)"
                            }
                        )
                        logger.info(f"  ✓ Referência criada: {codigo_ref}")
                        referencias_criadas += 1
                    
                    instrumento.referencia = referencia
                    instrumento.save()
                    instrumentos_vinculados += 1
                    
                except Exception as e:
                    logger.error(f"  ✗ Erro ao processar {instrumento.tag}: {str(e)}")
                    erros += 1
            
            logger.info("\n" + "=" * 80)
            logger.info("RESUMO DA MIGRAÇÃO")
            logger.info("=" * 80)
            logger.info(f"Referências criadas: {referencias_criadas}")
            logger.info(f"Instrumentos vinculados: {instrumentos_vinculados}")
            logger.info(f"Templates de faixa criados: {faixas_padrao_criadas}")
            logger.info(f"Faixas vinculadas a templates: {faixas_vinculadas}")
            logger.info(f"Erros encontrados: {erros}")
            
            if erros == 0:
                logger.info("\n✓ Migração concluída com SUCESSO!")
            else:
                logger.warning(f"\n⚠ Migração concluída com {erros} ERRO(S)")
            
    except Exception as e:
        logger.error(f"\n✗ ERRO CRÍTICO DURANTE MIGRAÇÃO: {str(e)}")
        raise


def validar_migracao():
    """
    Valida se a migração foi bem-sucedida.
    """
    from metrologia.models import Instrumento, InstrumentoReferencia
    
    logger.info("\n" + "=" * 80)
    logger.info("VALIDANDO MIGRAÇÃO")
    logger.info("=" * 80)
    
    total_instrumentos = Instrumento.objects.count()
    com_referencia = Instrumento.objects.filter(referencia__isnull=False).count()
    sem_referencia = Instrumento.objects.filter(referencia__isnull=True).count()
    total_referencias = InstrumentoReferencia.objects.count()
    
    logger.info(f"Total de instrumentos: {total_instrumentos}")
    logger.info(f"Com referência: {com_referencia}")
    logger.info(f"Sem referência: {sem_referencia}")
    logger.info(f"Total de referências: {total_referencias}")
    
    cobertura = (com_referencia / total_instrumentos * 100) if total_instrumentos > 0 else 0
    logger.info(f"Cobertura: {cobertura:.1f}%")
    
    if sem_referencia == 0:
        logger.info("\n✓ VALIDAÇÃO OK: Todos os instrumentos têm referência!")
    else:
        logger.warning(f"\n⚠ VALIDAÇÃO INCOMPLETA: {sem_referencia} instrumento(s) sem referência")


# Executar migração
if __name__ == "__main__":
    migrar_instrumentos_para_referencias()
    validar_migracao()
else:
    # Quando executado via Django shell
    logger.info("Script de migração carregado. Execute migrar_instrumentos_para_referencias()")
