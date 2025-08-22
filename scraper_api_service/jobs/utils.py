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
    if not text:
        return ""
    text = text.replace("\xa0", " ").replace("\t", " ")
    text = re.sub(r"\s*\n\s*", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()


def fetch_page(url: str, retries=3, delay=10):
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                logger.warning(f"⚠️ Error fetching {url}: {e}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"❌ Failed to fetch {url}: {e}", exc_info=True)
                return None


def parse_job_page(job_id: int, html: str):
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("h2", {"itemprop": "title"})
    company_tag = soup.find("h3", {"itemprop": "name"})
    if not title_tag or not company_tag:
        return None

    logo_tag = soup.find("img", {"itemprop": "image"})
    desc_tag = soup.find("div", {"class": "markdown"})
    meta_desc = soup.find("meta", {"name": "description"})
    apply_url_tag = soup.find("a", {"class": "action-apply"})
    time_tag = soup.find("time")

    posted_at = None
    if time_tag and time_tag.has_attr("datetime"):
        try:
            posted_at = datetime.fromisoformat(time_tag["datetime"])
        except Exception:
            posted_at = timezone.now()

    description = clean_description(desc_tag.get_text(strip=True, separator="\n") if desc_tag else "")
    short_description = meta_desc["content"].strip() if meta_desc else ""
    apply_url = ""
    if apply_url_tag:
        href = apply_url_tag.get("href", "")
        apply_url = BASE_URL + href if href.startswith("/") else href

    return {
        "remoteok_id": job_id,
        "title": title_tag.text.strip(),
        "company": company_tag.text.strip(),
        "company_logo": logo_tag.get("data-src") if logo_tag else "",
        "description": description,
        "short_description": short_description,
        "url": f"{BASE_URL}/remote-jobs/{job_id}",
        "apply_url": apply_url,
        "posted_at": posted_at,
    }


def save_job(job_data: dict):
    Job.objects.update_or_create(
        remoteok_id=job_data["remoteok_id"],
        defaults=job_data,
    )
    logger.info(f"✅ Saved job {job_data['remoteok_id']}: {job_data['title'][:50]}")


def get_latest_remoteok_id():
    resp = fetch_page(BASE_URL + "?order_by=date")
    if not resp:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    latest_job_tag = soup.find("tr", {"class": "job"})
    if latest_job_tag and latest_job_tag.has_attr("data-id"):
        return int(latest_job_tag["data-id"])
    return None


def scrape_jobs(start_id=None, end_id=None):
    try:
        if start_id is None or end_id is None:
            logger.info("🔍 start/end berilmagan, RemoteOK dan oxirgi job id olinmoqda...")
            latest_remoteok_id = get_latest_remoteok_id()
            if not latest_remoteok_id:
                return {"error": "cannot fetch latest job id"}

            last_job = Job.objects.order_by("-remoteok_id").first()
            last_id = last_job.remoteok_id if last_job else 1093276

            start_id = last_id + 1
            end_id = latest_remoteok_id
            if start_id > end_id:
                logger.info("✅ NO new jobs")
                return {"status": "no new jobs"}

        logger.info(f"🚀 Scraping jobs from {start_id} to {end_id}...")

        for job_id in range(start_id, end_id + 1):
            logger.info(f"🔎 Processing job {job_id}...")
            resp = fetch_page(f"{BASE_URL}/remote-jobs/{job_id}")
            if not resp:
                continue
            job_data = parse_job_page(job_id, resp.text)
            if not job_data:
                logger.warning(f"⚠️ Job {job_id} skipped (missing title/company)")
                continue
            save_job(job_data)
            time.sleep(0.5)  # bloklanmaslik uchun

        return {"status": "done"}

    except Exception as e:
        logger.exception(f"❌ scrape_jobs failed: {e}")
        return {"error": str(e)}
