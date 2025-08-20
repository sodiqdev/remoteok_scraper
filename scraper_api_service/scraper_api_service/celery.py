
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scraper_api_service.settings")

app = Celery("scraper_api_service")

# Django settingsdan CELERY_ prefiksli sozlamalarni o‘qiydi
app.config_from_object("django.conf:settings", namespace="CELERY")

# Barcha app’lardan tasks.py import qiladi
app.autodiscover_tasks()
