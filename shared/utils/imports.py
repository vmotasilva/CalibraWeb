"""Shared helpers for file-upload based data import jobs.

These utilities centralize the logic that was previously duplicated across the
different ``imp_*_view`` views (instruments, historico, colaboradores,
hierarquia, ferias): persisting the uploaded spreadsheet to a temporary file,
creating the tracking ``ImportJob`` record and dispatching the Celery task with
a synchronous fallback.
"""

import os
import tempfile


def save_uploaded_file_to_temp(uploaded):
    """Persist an uploaded file to a ``NamedTemporaryFile``.

    Returns the absolute path of the temporary file. The original extension is
    preserved (defaulting to ``.xlsx`` when the upload has none).
    """
    suffix = os.path.splitext(uploaded.name)[1] or ".xlsx"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        for chunk in uploaded.chunks():
            tmp.write(chunk)
        tmp.flush()
    finally:
        tmp.close()
    return tmp.name


def create_import_job(*, user, uploaded, job_type, filepath):
    """Create and return an ``ImportJob`` record for an upload.

    ``user`` is only stored when authenticated, matching the previous inline
    behaviour.
    """
    from qms.models import ImportJob

    return ImportJob.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        filename=uploaded.name,
        filepath=filepath,
        job_type=job_type,
        status="PENDING",
    )


def dispatch_import_task(task, job, filepath):
    """Dispatch an import task, falling back to synchronous execution.

    When ``SYNC_IMPORTS`` is not forcing synchronous mode, the task is enqueued
    via Celery (``.delay``); if that fails (e.g. broker unavailable) it runs
    synchronously instead.

    Returns ``True`` when the task ran synchronously (in which case ``job`` has
    been refreshed from the database), and ``False`` when it was enqueued.
    """
    force_sync = os.environ.get("SYNC_IMPORTS", "1") == "1"
    if not force_sync:
        try:
            task.delay(str(job.id), filepath)
            return False
        except Exception:
            force_sync = True

    task(str(job.id), filepath)
    job.refresh_from_db()
    return True
