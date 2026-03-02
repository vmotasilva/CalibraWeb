#!/usr/bin/env python
import requests
from bs4 import BeautifulSoup
import re

# URL base
BASE_URL = "http://127.0.0.1:8000"
LOGIN_URL = f"{BASE_URL}/login/"
INSTRUMENTO_URL = f"{BASE_URL}/metrologia/instrumento/109/?q=th&st=ATIVO&sit=VENCIDO"

session = requests.Session()

# Step 1: Get login page to extract CSRF token
print("1. Obtendo CSRF token...")
login_page = session.get(LOGIN_URL)
csrf_token = re.search(r'csrfmiddlewaretoken["\']?\s*[":=]+\s*["\']([^"\']+)["\']', login_page.text)
if csrf_token:
    csrf_token = csrf_token.group(1)
    print(f"   ✓ CSRF Token: {csrf_token[:20]}...")
else:
    print("   ✗ Não encontrou CSRF token")
    exit(1)

# Step 2: Login
print("\n2. Fazendo login...")
login_data = {
    'username': 'admin',
    'password': 'admin',
    'csrfmiddlewaretoken': csrf_token,
}
response = session.post(LOGIN_URL, data=login_data, allow_redirects=True)
if 'instrumeltrologia' in response.text or 'logout' in response.text:
    print("   ✓ Login bem-sucedido")
else:
    print("   ✗ Falha no login")

# Step 3: Access instrumento page
print("\n3. Acessando página do instrumento...")
inst_page = session.get(INSTRUMENTO_URL)

# Parse HTML
soup = BeautifulSoup(inst_page.text, 'html.parser')

# Look for debug comment
debug_comment = None
for comment in soup.find_all(string=lambda text: isinstance(text, str) and 'DEBUG' in text):
    debug_comment = comment
    print(f"   ✓ Encontrado: {comment.strip()}")
    break

if not debug_comment:
    print("   ! Não encontrou debug comment")

# Look for table with cotações
table = soup.find('table', {'class': 'table'})
if table:
    rows = table.find_all('tr')
    print(f"   ✓ Tabela encontrada com {len(rows)-1} linhas")
    for i, row in enumerate(rows[:5]):
        cells = row.find_all(['td', 'th'])
        print(f"      Linha {i}: {[c.get_text()[:20] for c in cells]}")
else:
    print("   ✗ Tabela não encontrada")

# Look for "Nenhuma cotação pendente"
if 'Nenhuma cotação pendente' in inst_page.text:
    print("\n   ! Mensagem 'Nenhuma cotação pendente' encontrada na página")
else:
    print("\n   ✓ Mensagem 'Nenhuma cotação pendente' NÃO está na página")

# Look for "Histórico de Cotações"
if 'Histórico de Cotações' in inst_page.text:
    print("   ✓ Seção 'Histórico de Cotações' encontrada")
else:
    print("   ! Seção 'Histórico de Cotações' NÃO encontrada")

print("\n✓ Teste concluído")
