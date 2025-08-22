
from celery import shared_task
from .utils2 import scrape_jobs

@shared_task
def scrape_latest_jobs():
    return scrape_jobs()
