from __future__ import annotations

from celery import shared_task
from django.utils import timezone

from .models import LinhaAcao, PlanoAcao
from .status_utils import bulk_mark_overdue_as_retardo


@shared_task(name="acoes.tasks.atualizar_status_acoes_atrasadas")
def atualizar_status_acoes_atrasadas():
    """Atualiza automaticamente o status para Retardo/Atrasada quando o prazo expira.

    Aplica em:
    - PlanoAcao
    - LinhaAcao

    Critério:
    - status em (planejada, em_curso)
    - effective deadline (max entre 1º deadline e deadline final) < hoje
    """

    today = timezone.localdate()

    planos_result = bulk_mark_overdue_as_retardo(PlanoAcao.objects.all(), today=today)
    linhas_result = bulk_mark_overdue_as_retardo(LinhaAcao.objects.all(), today=today)

    return {
        "date": str(today),
        "planos_updated": planos_result.updated_count,
        "linhas_updated": linhas_result.updated_count,
    }
