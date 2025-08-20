from django.core.management.base import BaseCommand
from jobs.utils import scrape_jobs


class Command(BaseCommand):
    help = "Scrape jobs from RemoteOK and store them in DB"

    def add_arguments(self, parser):
        parser.add_argument("--start", type=int)
        parser.add_argument("--end", type=int)

    def handle(self, *args, **options):
        result = scrape_jobs(
            start_id=options.get("start"),
            end_id=options.get("end")
        )
        self.stdout.write(self.style.SUCCESS(str(result)))
