import os
from celery import Celery

# Initialisation de l'application Celery
celery_app = Celery(
    "shadow_scanner",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    include=[
        "app.workers.worker_dns",
        "app.workers.worker_http",
        "app.workers.worker_geoip",
        "app.workers.worker_cve",
        "app.workers.worker_secrets",
        "app.workers.worker_harvester",
        "app.workers.worker_breach",
    ]
)

# Configuration optionnelle
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)
