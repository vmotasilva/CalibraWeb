#!/usr/bin/env python
"""
Create a test that simulates the exact form submission like a real browser would
This includes CSRF token handling
"""
import requests
from bs4 import BeautifulSoup
import re

# Start a session to maintain cookies
session = requests.Session()

BASE_URL = 'http://localhost:8000'

print("🔐 Step 1: Login...")
# Get login page
login_page = session.get(f'{BASE_URL}/login/')
print(f"   Status: {login_page.status_code}")

# Parse CSRF token from login page
soup = BeautifulSoup(login_page.text, 'html.parser')
csrf_input = soup.find('input', {'name': 'csrfmiddlewaretoken'})
csrf_token_login = csrf_input['value'] if csrf_input else None
print(f"   CSRF token: {csrf_token_login[:20] if csrf_token_login else 'NOT FOUND'}...")

# Post login
login_data = {
    'username': 'admin',
    'password': 'admin',
    'csrfmiddlewaretoken': csrf_token_login
}

login_response = session.post(f'{BASE_URL}/login/', data=login_data)
print(f"   Login status: {login_response.status_code}")
print(f"   Session cookies: {list(session.cookies.keys())}")

print("\n📄 Step 2: Load historico edit page...")
historico_page = session.get(f'{BASE_URL}/metrologia/historico/127/editar/')
print(f"   Status: {historico_page.status_code}")

if historico_page.status_code != 200:
    print(f"   ❌ Failed to load page!")
    print(f"   Content preview: {historico_page.text[:300]}")
else:
    print(f"   ✅ Page loaded!")
    
    # Parse CSRF token from the page
    soup = BeautifulSoup(historico_page.text, 'html.parser')
    csrf_input = soup.find('input', {'name': 'csrfmiddlewaretoken'})
    csrf_token_page = csrf_input['value'] if csrf_input else None
    print(f"   CSRF token: {csrf_token_page[:20] if csrf_token_page else 'NOT FOUND'}...")
    
    # Get the form element
    form = soup.find('form', {'id': 'carimboForm'})
    if form:
        action = form.get('action')
        print(f"   Form action: {action}")
        
        print("\n📝 Step 3: Prepare form data...")
        # Get all form inputs
        form_inputs = form.find_all('input')
        print(f"   Found {len(form_inputs)} inputs")
        
        post_data = {
            'csrfmiddlewaretoken': csrf_token_page,
            'resultado': 'APROVADO_SEM_CORRECAO',
            'data_validacao': '2024-01-15',
            'nome_validador': 'admin',
            'carimbo_x': '150',
            'carimbo_y': '200',
            'carimbo_page': '1',
        }
        
        print("   Form data to submit:")
        for key, value in post_data.items():
            if key != 'csrfmiddlewaretoken':
                print(f"     {key}: {value}")
        
        print("\n🔄 Step 4: Submit form...")
        submit_url = f'{BASE_URL}{action}' if action.startswith('/') else action
        print(f"   POST URL: {submit_url}")
        
        submit_response = session.post(submit_url, data=post_data, allow_redirects=False)
        print(f"   Status: {submit_response.status_code}")
        
        if submit_response.status_code == 302:
            print(f"   ✅ Redirect to: {submit_response.headers.get('Location')}")
        elif submit_response.status_code == 500:
            print(f"   ❌ Server error 500")
            print(f"   Content preview:\n{submit_response.text[:500]}")
        else:
            print(f"   Status code: {submit_response.status_code}")
            if len(submit_response.text) > 0:
                print(f"   Content preview:\n{submit_response.text[:300]}")

