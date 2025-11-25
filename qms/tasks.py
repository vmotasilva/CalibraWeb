from celery import shared_task


@shared_task
def ping_task():
    """Simple task used for smoke-testing the worker.

    Returns a known value so tests and monitors can ensure Celery is functional.
    """
    return "pong"


@shared_task
def import_instruments_task(job_id, filepath):
    """Placeholder: this task should wrap the heavy import_instruments logic.

    Replace this with the real implementation or call a helper service to process uploads
    asynchronously. For now it just returns success so integration tests can be built.
    """
    import os
    import pandas as pd
    from django.db import transaction
    from .models import ImportJob, Instrumento, CategoriaInstrumento, Setor, UnidadeMedida, FaixaMedicao

    try:
        job = ImportJob.objects.get(id=job_id)
        job.status = 'STARTED'
        job.save()
    except ImportJob.DoesNotExist:
        # cannot proceed without job record
        return {'error': 'job not found', 'job_id': job_id}

    count_new = 0
    count_upd = 0
    count_faixas = 0

    try:
        # Read file
        df = None
        if filepath.endswith('.csv'):
            try:
                df = pd.read_csv(filepath, sep=None, engine='python', encoding='latin1')
            except Exception:
                df = pd.read_csv(filepath, sep=None, engine='python', encoding='utf-8')
        else:
            df = pd.read_excel(filepath)

        df.columns = df.columns.str.strip().str.upper()

        with transaction.atomic():
            for _, row in df.iterrows():
                def get_val(k_list):
                    for key in k_list:
                        if key in df.columns and pd.notna(row[key]):
                            return str(row[key]).strip()
                    return None

                tag = get_val(['TAG', 'IDENTIFICACAO', 'CODIGO', 'CÓDIGO'])
                if not tag:
                    continue

                descricao = get_val(['EQUIPAMENTO', 'DESCRIÇÃO', 'DESCRICAO']) or 'Sem Descrição'
                obj, created = Instrumento.objects.update_or_create(tag=tag, defaults={'descricao': descricao})
                if created:
                    count_new += 1
                else:
                    count_upd += 1

        job.status = 'SUCCESS'
        job.result = f'Imported: {count_new} new, {count_upd} updated'
        job.save()
        return {'job_id': str(job_id), 'status': 'SUCCESS', 'imported': count_new, 'updated': count_upd}

    except Exception as exc:
        job.status = 'FAILURE'
        job.result = f'Error: {str(exc)}'
        job.save()
        return {'job_id': str(job_id), 'status': 'FAILURE', 'error': str(exc)}
