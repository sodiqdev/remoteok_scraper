from django.db import models


class Job(models.Model):
    remoteok_id = models.IntegerField(unique=True)

    title = models.CharField(max_length=255)
    company = models.CharField(max_length=255, null=True, blank=True)
    company_logo = models.URLField(max_length=500, null=True, blank=True)

    description = models.TextField(null=True, blank=True)
    short_description = models.TextField(null=True, blank=True)

    url = models.URLField(max_length=500)
    apply_url = models.URLField(max_length=500, null=True, blank=True)

    posted_at = models.DateTimeField(null=True, blank=True)
    scraped_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} @ {self.company or 'Unknown'}"
