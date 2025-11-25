from celery import shared_task


@shared_task
def ping_task():
    """Simple task used for smoke-testing the worker.

    Returns a known value so tests and monitors can ensure Celery is functional.
    """
    return 'pong'


@shared_task
def import_instruments_task(filename):
    """Placeholder: this task should wrap the heavy import_instruments logic.

    Replace this with the real implementation or call a helper service to process uploads
    asynchronously. For now it just returns success so integration tests can be built.
    """
    # NOTE: implement actual import streaming / validation here
    return {'filename': filename, 'status': 'queued'}
