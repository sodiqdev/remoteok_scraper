import time
import re
import requests
import logging
from bs4 import BeautifulSoup
from django.utils import timezone
from .models import Job
from datetime import datetime


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/115.0 Safari/537.36"
}
BASE_URL = "https://remoteok.com"


def clean_description(text: str) -> str:
    """Keraksiz probellarni tozalaydi"""
    if not text:
        return ""
    text = text.replace("\xa0", " ")
    text = text.replace("\t", " ")
    text = re.sub(r"\s*\n\s*", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    text = text.strip()
    return text


def scrape_jobs(start_id=None, end_id=None):

    try:
        if start_id is None or end_id is None:
            logger.info("🔍 start/end berilmagan, RemoteOK dan oxirgi job id olinmoqda...")

            retries = 3
            for attempt in range(retries):
                try:
                    resp = requests.get(BASE_URL + "?order_by=date", headers=HEADERS, timeout=30)
                    resp.raise_for_status()
                    logger.info("✅ RemoteOK dan oxirgi job id muvaffaqiyatli olindi")
                    break
                except requests.exceptions.RequestException as e:
                    if attempt < retries - 1:
                        logger.warning(f"⚠️ Error fetching latest job id: {e}. Retrying in 10s...")
                        time.sleep(10)
                    else:
                        logger.error(f"❌ scrape_jobs failed after {retries} attempts: {e}", exc_info=True)
                        return {"error": str(e)}

            soup = BeautifulSoup(resp.text, "html.parser")
            latest_job_tag = soup.find("tr", {"class": "job"})
            logger.info("🔎 RemoteOK sahifasi parse qilindi")

            if latest_job_tag and latest_job_tag.has_attr("data-id"):
                latest_remoteok_id = int(latest_job_tag["data-id"])
                logger.info(f"📌 Oxirgi job id: {latest_remoteok_id}")
            else:
                logger.error("❌ Cannot find latest job ID on RemoteOK")
                return {"error": "cannot find latest job id"}

            last_job = Job.objects.order_by("-remoteok_id").first()
            last_id = last_job.remoteok_id if last_job else 1093276
            logger.info(f"📌 Bizning DB dagi oxirgi job id: {last_id}")

            start_id = last_id + 1
            end_id = latest_remoteok_id

            if start_id > end_id:
                logger.info("✅ NO new jobs")
                return {"status": "no new jobs"}

        logger.info(f"🚀 Scraping jobs from {start_id} to {end_id}...")

        for job_id in range(start_id, end_id + 1):
            logger.info(f"🔎 Processing job {job_id}...")

            url = f"{BASE_URL}/remote-jobs/{job_id}"
            try:
                resp = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)

                logger.info(f"🌍 Job {job_id} uchun status: {resp.status_code}")
                if resp.status_code == 404:
                    logger.debug(f"❌ Job {job_id} not found (404)")
                    continue
                if resp.status_code == 429:
                    logger.warning(f"⚠️ Too many requests at {job_id}, sleeping 30s...")
                    time.sleep(30)
                    continue
                if resp.status_code != 200:
                    logger.warning(f"⚠️ Unexpected status {resp.status_code} for job {job_id}")
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")

                title_tag = soup.find("h2", {"itemprop": "title"})
                title = title_tag.text.strip() if title_tag else ""

                company_tag = soup.find("h3", {"itemprop": "name"})
                company = company_tag.text.strip() if company_tag else ""

                if not title or not company:
                    logger.warning(f"⚠️ Job {job_id} skipped (missing title/company)")
                    continue

                logo_tag = soup.find("img", {"itemprop": "image"})
                company_logo = logo_tag.get("data-src") or "" if logo_tag else ""

                desc_tag = soup.find("div", {"class": "markdown"})
                description = desc_tag.get_text(strip=True, separator="\n") if desc_tag else ""
                description = clean_description(description)

                meta_desc = soup.find("meta", {"name": "description"})
                short_description = meta_desc["content"].strip() if meta_desc else ""

                apply_url_tag = soup.find("a", {"class": "action-apply"})
                href = apply_url_tag["href"] if apply_url_tag else ""
                apply_url = BASE_URL + href if href.startswith("/") else href

                time_tag = soup.find("time")
                posted_at = None
                if time_tag and time_tag.has_attr("datetime"):
                    try:
                        posted_at = datetime.fromisoformat(time_tag["datetime"])
                    except Exception:
                        posted_at = timezone.now()

                Job.objects.update_or_create(
                    remoteok_id=job_id,
                    defaults={
                        "title": title,
                        "company": company,
                        "company_logo": company_logo,
                        "description": description,
                        "short_description": short_description,
                        "url": resp.url,
                        "apply_url": apply_url,
                        "posted_at": posted_at,
                    },
                )
                logger.info(f"✅ Saved job {job_id}: {title[:50]}")

                time.sleep(0.5)  # bloklanmaslik uchun

            except Exception as e:
                logger.error(f"❌ Error scraping {job_id}: {e}", exc_info=True)
                time.sleep(1)

        return {"status": "done"}

    except Exception as e:
        logger.exception(f"❌ scrape_jobs failed: {e}")
        return {"error": str(e)}
