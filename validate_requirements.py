#!/usr/bin/env python
"""
Validador de requirements.txt
Garante que todas as dependências estão listadas corretamente
"""

import subprocess
import sys
from pathlib import Path


def validate_requirements():
    """Valida se todos os pacotes listados em requirements.txt estão instalados."""
    
    req_file = Path("requirements.txt")
    
    if not req_file.exists():
        print("❌ requirements.txt não encontrado!")
        return False
    
    # Ler requirements.txt
    with open(req_file, 'r') as f:
        packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    print(f"📦 Verificando {len(packages)} pacotes...\n")
    
    missing = []
    installed = []
    
    for package in packages:
        # Extrair nome do pacote (antes de ==, >=, etc)
        pkg_name = package.split('==')[0].split('>=')[0].split('<=')[0].strip()
        
        try:
            __import__(pkg_name.replace('-', '_'))
            installed.append(package)
            print(f"✓ {package}")
        except ImportError:
            missing.append(package)
            print(f"✗ {package}")
    
    print(f"\n{'='*60}")
    print(f"✅ Instalados: {len(installed)}")
    print(f"❌ Faltando: {len(missing)}")
    
    if missing:
        print(f"\n⚠️  Pacotes faltando:")
        for pkg in missing:
            print(f"   - {pkg}")
        
        print("\n💡 Instale com:")
        print(f"   pip install {' '.join(missing)}")
        return False
    
    print("\n🎉 Todos os pacotes estão instalados!")
    return True


if __name__ == "__main__":
    success = validate_requirements()
    sys.exit(0 if success else 1)
