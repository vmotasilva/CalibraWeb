"""Token-gated data export endpoint used for one-off data migrations."""

import os
import secrets

from django.apps import apps
from django.core.serializers import serialize
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def dumpdata_view(request):
    """Serialize model data for migration, gated by the DUMPDATA_TOKEN secret."""
    # The endpoint is disabled unless an explicit token is provisioned via the
    # environment. This avoids shipping a usable data-exfiltration route with a
    # hardcoded secret.
    expected_token = os.environ.get("DUMPDATA_TOKEN")
    if not expected_token:
        return JsonResponse({"error": "Not found"}, status=404)

    provided_token = request.GET.get("token", "")
    if not secrets.compare_digest(provided_token, expected_token):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    action = request.GET.get("action")

    try:
        excluded_apps = {"admin", "auth", "contenttypes", "sessions", "auditlog"}

        if action == "list_models":
            models = []
            for m in apps.get_models():
                if m._meta.app_label not in excluded_apps:
                    models.append(f"{m._meta.app_label}.{m._meta.model_name}")
            return JsonResponse({"models": models})

        elif action == "dump_model":
            model_name = request.GET.get("model")
            offset = int(request.GET.get("offset", 0))
            limit = int(request.GET.get("limit", 100))

            app_label, m_name = model_name.split(".")
            if app_label in excluded_apps:
                return JsonResponse({"error": "Invalid model"}, status=400)
            model = apps.get_model(app_label, m_name)

            # Remove transaction.atomic to prevent deadlocks with PgBouncer
            end = offset + limit
            objects = list(model.objects.all()[offset:end])

            if objects:
                data_str = serialize("json", objects)
                return HttpResponse(data_str, content_type="application/json")
            else:
                return HttpResponse("[]", content_type="application/json")

        else:
            return JsonResponse({"error": "Invalid action"}, status=400)

    except Exception:
        # Avoid leaking internal details (stack traces) to callers.
        return JsonResponse({"error": "Internal server error"}, status=500)
