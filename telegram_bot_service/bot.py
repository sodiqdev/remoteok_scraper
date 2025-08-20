import asyncio
from datetime import datetime, timezone
from typing import Dict

from aiogram import Bot, Dispatcher
from aiogram.types import (
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent,
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from bs4 import BeautifulSoup

from telegram_bot_service.config import TELEGRAM_TOKEN
from telegram_bot_service.services.api_client import search_jobs, get_job_detail

bot = Bot(
    token=TELEGRAM_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

PAGE_SIZE = 10

def format_job_message(job: Dict) -> str:
    posted_at_str = job.get("posted_at", "")
    if posted_at_str:
        try:
            posted_at_dt = datetime.fromisoformat(posted_at_str.replace("Z", "+00:00"))
            posted_at_dt = posted_at_dt.astimezone(timezone.utc)
            posted_at = posted_at_dt.strftime("%B %d, %Y")
        except Exception:
            posted_at = posted_at_str
    else:
        posted_at = "Unknown"

    # Clean description
    description = job.get("description", "No description")
    description = BeautifulSoup(description, "html.parser").get_text()
    description = description.replace("\\n", "\n").strip()

    apply_url = job.get("apply_url") or job.get("url") or None
    apply_text = f"\n\n👉 <a href='{apply_url}'>Apply here</a>" if apply_url else ""

    # Construct message
    text = (
        f"💼 <b>{job.get('title', '')}</b>\n"
        f"🏢 <b>{job.get('company', '')}</b>\n"
        f"🕒 {posted_at}\n\n"
        f"{description[:3000]}..." + apply_text
    )

    return text


@dp.inline_query()
async def inline_handler(inline_query: InlineQuery):
    query = inline_query.query or ""
    offset = int(inline_query.offset or 0)
    page = offset // PAGE_SIZE + 1

    data = await search_jobs(query=query, page=page)
    results = []

    jobs_list = data.get("results", [])

    for index, job in enumerate(jobs_list):
        results.append(
            InlineQueryResultArticle(
                id=f"{job['id']}_{offset}_{query}_{index}",
                title=f"{job['title']} at {job['company']}",
                description=job.get("short_description", ""),
                thumb_url=job.get("company_logo", ""),
                input_message_content=InputTextMessageContent(
                    message_text=format_job_message(job)
                )
            )
        )

    next_offset = str(offset + len(results)) if data.get("next") else ""
    await inline_query.answer(results, cache_time=0, next_offset=next_offset)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    text = (
        "👋 Hello! I’m here to help you find the latest job opportunities.\n\n"
        "🔹 /latest - view the latest jobs\n"
        "🔹 You can also search for jobs using the inline search"
    )
    await message.answer(text)


async def show_latest(message_or_callback, page: int = 1, edit=True):
    data = await search_jobs(query="", page=page)
    jobs_list = data.get("results", [])

    if not jobs_list:
        text = "❌ Latest jobs not found!"
        if edit and hasattr(message_or_callback, "message"):
            try:
                await message_or_callback.message.edit_text(text)
            except TelegramBadRequest:
                await message_or_callback.message.answer(text)
        else:
            await message_or_callback.answer(text)
        return

    buttons = [
        [InlineKeyboardButton(text=f"{job['title']} @ {job['company']}", callback_data=f"job_{job['id']}")]
        for job in jobs_list[:PAGE_SIZE]
    ]

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=f"latest_{page - 1}"))
    if data.get("next"):
        nav_buttons.append(InlineKeyboardButton(text="➡️ Next", callback_data=f"latest_{page + 1}"))
    if nav_buttons:
        buttons.append(nav_buttons)

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = f"🆕 Latest Jobs - Page {page}"

    if edit and hasattr(message_or_callback, "message"):
        try:
            await message_or_callback.message.edit_text(text, reply_markup=keyboard)
        except TelegramBadRequest:
            await message_or_callback.message.answer(text, reply_markup=keyboard)
    else:
        await message_or_callback.answer(text, reply_markup=keyboard)


@dp.message(Command("latest"))
async def cmd_latest(message: Message):
    await show_latest(message, page=1, edit=False)


@dp.callback_query()
async def callback_handler(callback_query: CallbackQuery):
    data = callback_query.data

    if data.startswith("job_"):
        job_id = int(data.split("_")[1])
        job = await get_job_detail(job_id)
        if not job:
            await callback_query.message.answer("❌ Job not found!")
            return
        text = format_job_message(job)
        await callback_query.message.answer(text)

    elif data.startswith("latest_"):
        page = int(data.split("_")[1])
        await show_latest(callback_query, page=page, edit=True)


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
