import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

import django
django.setup()

from django.conf import settings

print("=" * 60)
print("CONFIGURAÇÃO DE SESSÃO E CACHE")
print("=" * 60)

print(f"\n1. DEBUG MODE: {settings.DEBUG}")
print(f"2. SESSION_ENGINE: {settings.SESSION_ENGINE}")
print(f"3. SESSION_CACHE_ALIAS: {getattr(settings, 'SESSION_CACHE_ALIAS', 'não definido')}")

print(f"\n4. CACHE BACKENDS DISPONÍVEIS:")
for cache_name, cache_config in settings.CACHES.items():
    backend = cache_config.get('BACKEND', 'unknown')
    print(f"   - {cache_name}: {backend}")

print(f"\n5. CSRF_TRUSTED_ORIGINS:")
for origin in settings.CSRF_TRUSTED_ORIGINS:
    print(f"   - {origin}")

print(f"\n6. CSRF_COOKIE_SECURE: {getattr(settings, 'CSRF_COOKIE_SECURE', False)}")
print(f"7. SESSION_COOKIE_SECURE: {getattr(settings, 'SESSION_COOKIE_SECURE', False)}")

print("\n" + "=" * 60)
print("TESTE DE SESSÃO")
print("=" * 60)

from django.contrib.sessions.backends.db import SessionStore

try:
    session = SessionStore()
    session['test'] = 'value'
    session.save()
    print(f"✅ Sessão criada com sucesso!")
    print(f"   Session Key: {session.session_key}")
    
    # Verificar
    session2 = SessionStore(session_key=session.session_key)
    print(f"✅ Sessão recuperada: {session2.get('test')}")
    
    # Limpar
    session.delete()
    print(f"✅ Sessão deletada com sucesso!")
    
except Exception as e:
    print(f"❌ Erro ao testar sessão: {e}")

print("\n" + "=" * 60)
