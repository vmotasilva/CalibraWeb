#!/usr/bin/env python
"""
Test form submission using the running Django instance 
assuming we're already logged in via browser
"""
import requests
from bs4 import BeautifulSoup

session = requests.Session()
BASE_URL = 'http://localhost:8000'

# Skip login, go directly to the page
print("📄 Step 1: Load historico edit page...")
page = session.get(f'{BASE_URL}/metrologia/historico/127/editar/')
print(f"   Status: {page.status_code}")

if page.status_code != 200:
    print(f"   ❌ Page failed to load")
    print(f"   Is server running? Try: python manage.py runserver")
    exit(1)

print(f"   ✅ Page loaded! (assuming already authenticated via browser)")

# Parse the CSRF token
soup = BeautifulSoup(page.text, 'html.parser')
csrf_input = soup.find('input', {'name': 'csrfmiddlewaretoken'})
csrf_token = csrf_input['value'] if csrf_input else None

if not csrf_token:
    print("   ❌ CSRF token not found in page!")
    exit(1)

print(f"   ✅ CSRF token found: {csrf_token[:20]}...")

# Find the form
form = soup.find('form', {'id': 'carimboForm'})
if not form:
    print("   ❌ carimboForm not found!")
    exit(1)

form_action = form.get('action')
print(f"   ✅ Form action: {form_action}")

print("\n📝 Step 2: Prepare form data...")
post_data = {
    'csrfmiddlewaretoken': csrf_token,
    'resultado': 'APROVADO_SEM_CORRECAO',
    'data_validacao': '2024-01-15',
    'nome_validador': 'admin',
    'carimbo_x': '150',
    'carimbo_y': '200',
    'carimbo_page': '1',
}

print("   Submitting with data:")
for key, value in post_data.items():
    if key != 'csrfmiddlewaretoken':
        print(f"     {key}: {value}")

print("\n🔄 Step 3: Submit form...")
submit_url = f'{BASE_URL}{form_action}' if form_action.startswith('/') else form_action
print(f"   POST to: {submit_url}")

# Important: Add headers to look like a real form submission
headers = {
    'Referer': f'{BASE_URL}/metrologia/historico/127/editar/',
}

submit_response = session.post(submit_url, data=post_data, headers=headers, allow_redirects=False)
print(f"   Status: {submit_response.status_code}")

if submit_response.status_code == 302:
    print(f"   ✅ SUCCESS! Redirect to: {submit_response.headers.get('Location')}")
elif submit_response.status_code == 500:
    print(f"   ❌ ERROR 500")
    print(f"\n📋 Response content (first 1000 chars):")
    print(submit_response.text[:1000])
else:
    print(f"   Response: {submit_response.status_code}")
    print(f"   Content: {submit_response.text[:200]}")
