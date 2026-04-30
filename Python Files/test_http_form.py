#!/usr/bin/env python
"""
Test form submission using HTTP requests directly to the running server
"""
import requests
import re

# First, get the login page to extract CSRF token
session = requests.Session()

print("🔐 Getting login page...")
login_response = session.get('http://localhost:8000/login/')
print(f"Login page status: {login_response.status_code}")

# Extract CSRF token from login page
csrf_match = re.search(r'<input[^>]*name="csrfmiddlewaretoken"[^>]*value="([^"]*)"', login_response.text)
csrf_token = csrf_match.group(1) if csrf_match else None
print(f"CSRF token: {csrf_token[:20]}..." if csrf_token else "❌ No CSRF token found")

# Login
print("\n🔐 Logging in...")
login_data = {
    'username': 'admin',
    'password': 'admin',
    'csrfmiddlewaretoken': csrf_token
}

login_response = session.post('http://localhost:8000/login/', data=login_data, allow_redirects=False)
print(f"Login response status: {login_response.status_code}")
if login_response.status_code == 302:
    print(f"Redirected to: {login_response.headers.get('Location')}")

# Now try to access the page
print("\n📄 Getting historico page...")
page_response = session.get('http://localhost:8000/metrologia/historico/127/editar/')
print(f"Page status: {page_response.status_code}")

# Get CSRF token from the historico page
csrf_match = re.search(r'<input[^>]*name="csrfmiddlewaretoken"[^>]*value="([^"]*)"', page_response.text)
csrf_token_page = csrf_match.group(1) if csrf_match else None
print(f"Page CSRF token: {csrf_token_page[:20] if csrf_token_page else 'Not found'}...")

# Now try to submit the form
print("\n📝 Submitting stamp form...")
post_data = {
    'csrfmiddlewaretoken': csrf_token_page,
    'resultado_carimbo': 'APROVADO_SEM_CORRECAO',
    'data_validacao_carimbo': '2024-01-15',
    'nome_validador': 'admin',
    'carimbo_x': '150',
    'carimbo_y': '200',
    'carimbo_page': '1',
}

print("POST Data:")
for key, value in post_data.items():
    if key != 'csrfmiddlewaretoken':
        print(f"  {key}: {value}")

response = session.post('http://localhost:8000/metrologia/historico/127/aplicar-carimbo/', data=post_data, allow_redirects=False)

print(f"\n📊 Response Status: {response.status_code}")
if response.status_code == 302:
    print(f"✅ Redirect successful!")
    print(f"Location: {response.headers.get('Location')}")
elif response.status_code == 500:
    print(f"❌ Server error 500")
    print(f"Error content (first 1000 chars):\n{response.text[:1000]}")
else:
    print(f"Response content preview:\n{response.text[:500]}")
