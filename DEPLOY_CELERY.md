Deploying Celery (quick guide)
================================

This project now includes a minimal Celery setup at `config/celery.py` and example tasks in `qms/tasks.py`.

Quick steps to run Celery (using redis as broker):

1) Install requirements (redis & celery are in requirements.txt)

2) Start Redis (example, for local dev):

   # macOS/linux
   docker run -p 6379:6379 -d redis:7

3) Start a worker:

   # from project root
   celery -A config worker --loglevel=info

4) Run tasks (example in Django shell):

   python manage.py shell
   >>> from qms.tasks import ping_task
   >>> ping_task.delay()

Notes and next steps:
 - For production, use a managed Redis/streaming broker and run workers with process manager (systemd, supervisor) or scaled containers.
 - The view-level refactor to push heavy import work to a background task is the next step — I can implement it to queue imports and store progress events.
