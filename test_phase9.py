import os
import django
from django.test.utils import get_runner
from django.conf import settings

if __name__ == "__main__":
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    
    # Run comprehensive tests for Phase 9 modularization
    test_labels = [
        'qms.tests',
        'core.tests',
        'organization.tests', 
        'rh.tests',
        'metrologia.tests',
        'procurements.tests',
        'training.tests',
        'documents.tests',
        'shared.tests',
    ]
    
    failures = test_runner.run_tests(test_labels)
    exit(bool(failures))
