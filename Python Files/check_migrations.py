import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

import django
django.setup()

from django.core.management import call_command
from io import StringIO

# Capture the output
out = StringIO()
call_command('showmigrations', 'procedures', stdout=out)
output = out.getvalue()

print(output)
