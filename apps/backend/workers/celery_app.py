import os
from pathlib import Path
from celery import Celery
from dotenv import load_dotenv

# Carga variables de entorno
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "brics_workers",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Mexico_City",
    enable_utc=True,
)

if __name__ == "__main__":
    celery_app.start()
