import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()
if not User.objects.filter(username='tmpchecker').exists():
    User.objects.create_superuser('tmpchecker','tmp@example.com','tmpcheck')

c = Client()
logged = c.login(username='tmpchecker', password='tmpcheck')
print('logged_in=', logged)
resp = c.get('/procedures/dashboard/')
print('status', resp.status_code)
ct = resp.content.decode('utf-8')
for cid in ['chartStatus','chartMeses','chartLider','chartSetorTurno']:
    print(cid, cid in ct)

# Print short snippets around canvas elements
for cid in ['chartStatus','chartLider','chartSetorTurno']:
    idx = ct.find(cid)
    if idx>-1:
        snippet = ct[max(0, idx-200):idx+200]
        print('---', cid, 'snippet ---')
        print(snippet)
    else:
        print('---', cid, 'not found ---')
