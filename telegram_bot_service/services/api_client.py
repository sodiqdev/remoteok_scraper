import httpx
from telegram_bot_service.config import API_URL


async def search_jobs(query: str, page: int = 1):
    """Search jobs with pagination"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API_URL}/jobs/",
            params={"search": query, "page": page}
        )
        resp.raise_for_status()
        return resp.json()


async def get_job_detail(job_id: int):
    """Get full job detail by ID"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_URL}/jobs/{job_id}/")
        resp.raise_for_status()
        return resp.json()
