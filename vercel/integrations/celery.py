# Mock Vercel Celery Integration
# This prevents the Vercel Python Builder from crashing when Celery is present in requirements.txt.
# It intercepts any attribute access and returns a dummy function.

class DummyIntegration:
    def __getattr__(self, name):
        def dummy_method(*args, **kwargs):
            print(f"[Vercel Mock] Ignored call to vercel.integrations.celery.{name}")
        return dummy_method

# By defining __getattr__ at the module level (Python 3.7+),
# any import or attribute access like `vercel.integrations.celery.install(...)` 
# will be caught and a dummy function returned.
def __getattr__(name):
    def dummy_method(*args, **kwargs):
        print(f"[Vercel Mock] Ignored module-level call to vercel.integrations.celery.{name}")
    return dummy_method
