#!/usr/bin/env python
"""
Validador de requirements.txt
Garante que todas as dependências estão listadas corretamente
"""

import subprocess
import sys
from pathlib import Path
import logging

logger = logging.getLogger(__name__) 


def validate_requirements():
    """Valida se todos os pacotes listados em requirements.txt estão instalados."""
    
    req_file = Path("requirements.txt")
    
    if not req_file.exists():
        logger.error("❌ requirements.txt não encontrado!")
        return False
    
    # Ler requirements.txt
    with open(req_file, 'r') as f:
        packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    logger.info(f"📦 Verificando {len(packages)} pacotes...\n")
    
    missing = []
    installed = []
    
    for package in packages:
        # Extrair nome do pacote (antes de ==, >=, etc)
        pkg_name = package.split('==')[0].split('>=')[0].split('<=')[0].strip()
        
        try:
            __import__(pkg_name.replace('-', '_'))
            installed.append(package)
            logger.info(f"✓ {package}")
        except ImportError:
            missing.append(package)
            logger.warning(f"✗ {package}")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"✅ Instalados: {len(installed)}")
    logger.info(f"❌ Faltando: {len(missing)}")
    
    if missing:
        logger.warning(f"\n⚠️  Pacotes faltando:")
        for pkg in missing:
            logger.warning(f"   - {pkg}")
        
        logger.info("\n💡 Instale com:")
        logger.info(f"   pip install {' '.join(missing)}")
        return False
    
    print("\n🎉 Todos os pacotes estão instalados!")
    return True


if __name__ == "__main__":
    success = validate_requirements()
    sys.exit(0 if success else 1)
