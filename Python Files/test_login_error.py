#!/usr/bin/env python
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ['DEBUG'] = 'True'

import django
django.setup()

from django.test import Client

client = Client()
print('Making request to /login/?next=/metrologia/instrumento/74/')
print('-' * 60)

try:
    response = client.get('/login/?next=/metrologia/instrumento/74/', follow=False)
    print(f'Response Status: {response.status_code}')
    
    if response.status_code == 500:
        print('\n*** 500 ERROR FOUND ***\n')
        content = response.content.decode('utf-8', errors='replace')
        print(content[:3000])
    elif response.status_code == 200:
        print('\nSUCCESS: Login page loaded correctly')
    else:
        print(f'\nUnexpected status code: {response.status_code}')
        content = response.content.decode('utf-8', errors='replace')
        print(content[:1000])
        
except Exception as e:
    print(f'\nEXCEPTION: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
