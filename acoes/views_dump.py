import json
from django.apps import apps
from django.core.serializers import serialize
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def dumpdata_view(request):
    if request.GET.get('token') != 'super-secret-migration-token-1234':
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    action = request.GET.get('action')
    
    try:
        excluded_apps = {'admin', 'auth', 'contenttypes', 'sessions', 'auditlog'}
        
        if action == 'list_models':
            models = []
            for m in apps.get_models():
                if m._meta.app_label not in excluded_apps:
                    models.append(f"{m._meta.app_label}.{m._meta.model_name}")
            return JsonResponse({'models': models})
            
        elif action == 'dump_model':
            model_name = request.GET.get('model')
            offset = int(request.GET.get('offset', 0))
            limit = int(request.GET.get('limit', 100))
            
            app_label, m_name = model_name.split('.')
            model = apps.get_model(app_label, m_name)
            
            # Remove transaction.atomic to prevent deadlocks with PgBouncer
            objects = list(model.objects.all()[offset:offset+limit])
            
            if objects:
                data_str = serialize('json', objects)
                return HttpResponse(data_str, content_type='application/json')
            else:
                return HttpResponse('[]', content_type='application/json')
                
        else:
            return JsonResponse({'error': 'Invalid action'}, status=400)
            
    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'trace': traceback.format_exc()}, status=500)

@csrf_exempt
def reset_sequences_view(request):
    if request.GET.get('token') != 'super-secret-migration-token-1234':
        return JsonResponse({'error': 'Unauthorized'}, status=401)
        
    try:
        from django.core.management import call_command
        from django.db import connection
        from django.apps import apps
        from io import StringIO
        
        app_labels = [app.label for app in apps.get_app_configs()]
        
        sql_statements = []
        for app_label in app_labels:
            output = StringIO()
            try:
                call_command('sqlsequencereset', app_label, stdout=output)
                sql = output.getvalue().strip()
                if sql:
                    sql_statements.append(sql)
            except Exception:
                pass
                
        statements = []
        for app_sql in sql_statements:
            for stmt in app_sql.split(';'):
                stmt = stmt.strip()
                if stmt:
                    statements.append(stmt)
                    
        success_count = 0
        errors = []
        with connection.cursor() as cursor:
            for stmt in statements:
                try:
                    cursor.execute(stmt)
                    success_count += 1
                except Exception as ex:
                    errors.append(f"{stmt[:60]}: {str(ex)}")
                    
        return JsonResponse({
            'status': 'success',
            'executed': success_count,
            'total': len(statements),
            'errors': errors
        })
    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'trace': traceback.format_exc()}, status=500)

