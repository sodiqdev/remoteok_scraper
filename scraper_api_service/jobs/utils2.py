import time
import re
import json
import requests
import logging
from bs4 import BeautifulSoup
from django.utils import timezone
from .models import Job
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"⚠️ Page not found (404) for {url}. Skipping...")
                return None
            if attempt < retries - 1:
                logger.warning(f"⚠️ Error fetching {url}: {e}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"❌ Failed to fetch {url}: {e}", exc_info=True)
                return None
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                logger.warning(f"⚠️ Error fetching {url}: {e}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"❌ Failed to fetch {url}: {e}", exc_info=True)
                return None
    return None


def parse_job_page(job_id: int, html: str):
    soup = BeautifulSoup(html, "html.parser")

    json_scripts = soup.find_all("script", {"type": "application/ld+json"})
    if not json_scripts:
        logger.warning(f"⚠️ Job {job_id} skipped: No JSON-LD script found")
        return None

    try:
        json_data = json.loads(json_scripts[-1].string)
        if json_data.get("@type") != "JobPosting":
            logger.warning(f"⚠️ Job {job_id} skipped: Last JSON-LD is not a JobPosting")
            return None
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ Job {job_id} skipped: Failed to parse JSON - {e}")
        return None

    title = json_data.get("title", "").strip()
    company = json_data.get("hiringOrganization", {}).get("name", "").strip()
    company_logo = json_data.get("hiringOrganization", {}).get("logo", {}).get("url", "")

    desc_tag = soup.find("div", {"class": "markdown"})
    description = clean_description(desc_tag.get_text(strip=True, separator="\n") if desc_tag else "")

    short_description = clean_description(json_data.get("description", ""))
    posted_at = None
    if json_data.get("datePosted"):
        posted_at = datetime.fromisoformat(json_data["datePosted"])


    apply_url = ""
    apply_url_tag = soup.find("a", {"class": "action-apply"})
    if apply_url_tag:
        href = apply_url_tag.get("href", "")
        apply_url = BASE_URL + href if href.startswith("/") else href
    else:
        logger.warning(f"⚠️ Job {job_id}: No apply URL found")

    if not title or not company:
        logger.warning(f"⚠️ Job {job_id} skipped: Missing title or company")
        return None

    if company_logo and not company_logo.startswith("http"):
        company_logo = BASE_URL + company_logo
    if company_logo:
        logger.info(f"✅ Job {job_id}: Company logo extracted from JSON")
    else:
        logger.warning(f"⚠️ Job {job_id}: No valid company logo found")

    return {
        "remoteok_id": job_id,
        "title": title,
        "company": company,
        "company_logo": company_logo,
        "description": description,
        "short_description": short_description,
        "url": f"{BASE_URL}/remote-jobs/{job_id}",
        "apply_url": apply_url,
        "posted_at": posted_at,
    }


def save_job(job_data: dict):
    try:
        Job.objects.update_or_create(
            remoteok_id=job_data["remoteok_id"],
            defaults=job_data,
        )
        logger.info(f"✅ Saved job {job_data['remoteok_id']}: {job_data['title'][:50]}")
    except Exception as e:
        logger.error(f"❌ Failed to save job {job_data['remoteok_id']}: {e}")


def get_latest_remoteok_id():
    resp = fetch_page(BASE_URL + "?order_by=date")
    if not resp:
        logger.error("❌ Cannot fetch latest job id: No response from server")
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    latest_job_tag = soup.find("tr", {"class": "job"})
    if latest_job_tag and latest_job_tag.has_attr("data-id"):
        return int(latest_job_tag["data-id"])
    logger.warning("⚠️ No valid job ID found on the main page")
    return None


def scrape_job_wrapper(job_id):
    logger.info(f"🔎 Processing job {job_id}...")
    resp = fetch_page(f"{BASE_URL}/remote-jobs/{job_id}")
    if not resp:
        logger.warning(f"⚠️ Job {job_id} skipped: Failed to fetch page")
        return None
    job_data = parse_job_page(job_id, resp.text)
    if not job_data:
        logger.warning(f"⚠️ Job {job_id} skipped: No valid data parsed")
        return None
    save_job(job_data)
    return job_data


def scrape_jobs(start_id=None, end_id=None, max_workers=5):
    try:
        if start_id is None or end_id is None:
            logger.info("🔍 start/end berilmagan, RemoteOK dan oxirgi job id olinmoqda...")
            latest_remoteok_id = get_latest_remoteok_id()
            if not latest_remoteok_id:
                return {"error": "cannot fetch latest job id"}

            last_job = Job.objects.order_by("-remoteok_id").first()
            last_id = last_job.remoteok_id if last_job else 1090000

            start_id = last_id + 1
            end_id = latest_remoteok_id
            if start_id > end_id:
                logger.info("✅ No new jobs")
                return {"status": "no new jobs"}

        logger.info(f"🚀 Scraping jobs from {start_id} to {end_id}...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_job = {executor.submit(scrape_job_wrapper, job_id): job_id for job_id in range(start_id, end_id + 1)}
            for future in as_completed(future_to_job):
                job_id = future_to_job[future]
                try:
                    result = future.result()
                    if result:
                        logger.info(f"✅ Job {job_id} processed successfully")
                except Exception as e:
                    logger.error(f"❌ Job {job_id} failed: {e}")

        return {"status": "done"}

    except Exception as e:
        logger.exception(f"❌ scrape_jobs failed: {e}")
        return {"error": str(e)}