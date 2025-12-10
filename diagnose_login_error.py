#!/usr/bin/env python
"""
Comprehensive Login Error Diagnostic Script
Tests various scenarios that might cause 500 errors
"""

import os
import sys
import logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ['DEBUG'] = 'True'

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

import django
django.setup()

from django.test import Client, RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.views.debug import ExceptionReporter
from django.middleware.csrf import CsrfViewMiddleware
import traceback

def test_login_via_client():
    """Test login page via Django test client"""
    print("\n" + "="*60)
    print("TEST 1: Login Page via Django Test Client")
    print("="*60)
    
    client = Client()
    try:
        response = client.get('/login/?next=/metrologia/instrumento/74/')
        print(f"✓ Status: {response.status_code}")
        
        if response.status_code == 500:
            print("✗ ERROR 500 DETECTED")
            if hasattr(response, 'exc_info'):
                print(f"Exception: {response.exc_info[1]}")
            return False
        elif response.status_code == 200:
            print("✓ Login page loaded successfully")
            return True
        else:
            print(f"? Unexpected status: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Exception: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False

def test_login_post():
    """Test login POST request"""
    print("\n" + "="*60)
    print("TEST 2: Login POST Request")
    print("="*60)
    
    client = Client()
    try:
        # First, get the CSRF token
        response = client.get('/login/')
        csrf_token = response.cookies.get('csrftoken', '').value
        
        # Try to post invalid credentials
        response = client.post(
            '/login/?next=/metrologia/instrumento/74/',
            {
                'username': 'testuser',
                'password': 'wrongpass',
                'csrfmiddlewaretoken': csrf_token
            },
            follow=False
        )
        
        print(f"✓ POST Status: {response.status_code}")
        if response.status_code == 200:
            print("✓ Login form re-rendered on error")
            return True
        else:
            print(f"? Unexpected status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ Exception: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False

def test_models_import():
    """Test that all models can be imported without errors"""
    print("\n" + "="*60)
    print("TEST 3: Model Imports")
    print("="*60)
    
    try:
        from metrologia.models import Instrumento
        from qms.models import SolicitacaoInstrumento, OcorrenciaInstrumento
        from organization.models import Setor
        from rh.models import Colaborador
        
        print("✓ All models imported successfully")
        
        # Try to query a model
        count = Instrumento.objects.count()
        print(f"✓ Instrumento count: {count}")
        
        return True
    except Exception as e:
        print(f"✗ Exception: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False

def test_template_render():
    """Test that the login template can be rendered"""
    print("\n" + "="*60)
    print("TEST 4: Template Rendering")
    print("="*60)
    
    try:
        from django.template.loader import render_to_string
        from django.forms.models import ModelChoiceField
        from django import forms
        
        # Create a simple login form
        class SimpleLoginForm(forms.Form):
            username = forms.CharField()
            password = forms.CharField(widget=forms.PasswordInput)
        
        form = SimpleLoginForm()
        
        # Try rendering the login template
        html = render_to_string(
            'registration/login.html',
            {'form': form}
        )
        
        if 'login-card' in html or 'ENTRAR' in html:
            print("✓ Template rendered successfully")
            print(f"✓ HTML length: {len(html)} bytes")
            return True
        else:
            print("? Template rendered but unexpected content")
            return False
            
    except Exception as e:
        print(f"✗ Exception: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False

def test_csrf_middleware():
    """Test CSRF middleware functionality"""
    print("\n" + "="*60)
    print("TEST 5: CSRF Middleware")
    print("="*60)
    
    try:
        factory = RequestFactory()
        request = factory.get('/login/')
        request.user = AnonymousUser()
        
        middleware = CsrfViewMiddleware(lambda r: None)
        middleware.process_request(request)
        
        if hasattr(request, 'META') and 'CSRF_COOKIE' in request.META:
            print("✓ CSRF cookie set")
        
        print("✓ CSRF middleware works")
        return True
        
    except Exception as e:
        print(f"✗ Exception: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("CALIBRAWEB - LOGIN ERROR DIAGNOSTIC")
    print("="*60)
    
    results = {
        'Client Test': test_login_via_client(),
        'POST Test': test_login_post(),
        'Models Import': test_models_import(),
        'Template Render': test_template_render(),
        'CSRF Middleware': test_csrf_middleware(),
    }
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✓ All tests passed! Login page should work correctly.")
        print("\nIf you're still experiencing a 500 error, it may be:")
        print("1. A browser-specific issue (cache, extensions)")
        print("2. A network proxy issue")
        print("3. A production environment-specific issue")
        print("4. An issue with a specific browser or device")
    else:
        print("\n✗ Some tests failed. Check the errors above.")
    
    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())
