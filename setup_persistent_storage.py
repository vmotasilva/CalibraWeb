#!/usr/bin/env python
"""
Script para configurar o Railway volume para PDFs persistentes.

Este script é executado após criar o volume no Railway dashboard.
Crie um volume em: Settings → Environment → Volumes → Create Volume
  - Mount Path: /data/media
  - Size: 10GB

Depois, adicione esta variável de ambiente no Railway:
  PERSIST_MEDIA_PATH=/data/media
"""

import os
import sys
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def setup_persistent_storage():
    """Setup directory structure for persistent media storage."""
    
    # Caminho que será montado como volume no Railway
    persist_path = os.environ.get('PERSIST_MEDIA_PATH', '/data/media')
    
    logger.info(f"📁 Configurando armazenamento persistente em: {persist_path}")
    
    # Criar diretórios necessários
    subdirs = [
        'certificados',
        'certificados/carimbados',
        'padroes_historico',
        'procedimentos',
        'arquivos_padrao'
    ]
    
    try:
        for subdir in subdirs:
            dir_path = Path(persist_path) / subdir
            dir_path.mkdir(parents=True, exist_ok=True)
            os.chmod(dir_path, 0o755)
            logger.info(f"  ✅ Criado: {dir_path}")
        
        # Criar .gitkeep para garantir que os diretórios sejam rastreados
        gitkeep = Path(persist_path) / '.gitkeep'
        gitkeep.touch()
        
        logger.info(f"\n✅ Armazenamento persistente configurado com sucesso!")
        logger.info(f"📝 Diretório: {persist_path}")
        logger.info(f"📊 Tamanho alocado: Confira no Railway Dashboard")
        return True
        
    except Exception as e:
        logger.exception(f"\n❌ Erro ao configurar armazenamento: {e}")
        return False

if __name__ == '__main__':
    success = setup_persistent_storage()
    sys.exit(0 if success else 1)
