"""
Script de diagnóstico e criação de superusuário
Este script tenta criar o superusuário diretamente
"""
import os
import sys
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    django.setup()
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    print("=" * 60)
    print("DIAGNÓSTICO DO SUPERUSUÁRIO")
    print("=" * 60)
    print()
    
    # Verificar usuários existentes
    print("📊 Usuários existentes no banco de dados:")
    print("-" * 60)
    users = User.objects.all()
    if users.exists():
        for user in users:
            print(f"  - Username: {user.username}")
            print(f"    Email: {user.email}")
            print(f"    Is Staff: {user.is_staff}")
            print(f"    Is Superuser: {user.is_superuser}")
            print()
    else:
        print("  ❌ NENHUM USUÁRIO ENCONTRADO!")
        print()
    
    # Tentar criar superusuário
    username = 'admin'
    email = 'admin@calibraweb.com'
    password = 'Admin123!Railway'  # TROQUE POR SUA SENHA
    
    print("🔧 Tentando criar superusuário...")
    print("-" * 60)
    
    if User.objects.filter(username=username).exists():
        print(f"  ⚠️  Usuário '{username}' já existe!")
        user = User.objects.get(username=username)
        
        # Atualizar senha
        print(f"  🔄 Atualizando senha do usuário '{username}'...")
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.save()
        print(f"  ✅ Senha atualizada com sucesso!")
        print(f"  ✅ Permissões de superusuário ativadas!")
    else:
        print(f"  🆕 Criando novo superusuário '{username}'...")
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        print(f"  ✅ Superusuário '{username}' criado com sucesso!")
    
    print()
    print("=" * 60)
    print("✅ CONCLUÍDO!")
    print("=" * 60)
    print()
    print("🔐 Credenciais de Login:")
    print(f"  Username: {username}")
    print(f"  Password: {password}")
    print()
    print("🌐 Acesse: https://calibraweb.up.railway.app/admin/")
    print()
    print("⚠️  IMPORTANTE: Troque a senha acima pela que você definiu!")
    print("=" * 60)
    
except Exception as e:
    print()
    print("=" * 60)
    print("❌ ERRO!")
    print("=" * 60)
    print(f"Erro: {e}")
    print()
    print("Possíveis causas:")
    print("1. Variáveis de ambiente do PostgreSQL não configuradas")
    print("2. Não conectado ao banco de dados do Railway")
    print("3. Django não configurado corretamente")
    print()
    print("💡 Este script deve ser executado NO RAILWAY, não localmente!")
    print("=" * 60)
