# RemoteOK Job Scraper

👋 Hello! This project helps you fetch the latest job postings from **RemoteOK** and delivers them via Telegram. It includes a Django API, Celery task scheduler, and Telegram bot integration.

---

## 🛠️ Key Features

* API using Django Rest Framework (`JobViewSet`)
* Automatic job scraping with Celery
* Telegram bot to send jobs to users
* Task management via Redis broker
* Secure environment variables using `.env`

---

## ⚙️ Setup Instructions

### 1. Clone the project

```bash
git clone git@github.com:sodiqdev/remoteok_scraper.git
cd remoteok_scraper
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Setup environment variables

```bash
cp .env.example .env
```

* Edit `.env` to include your credentials (Telegram token, Redis URL, Django SECRET\_KEY, etc.)

### 4. Run database migrations

```bash
python manage.py migrate
```

### 5. Start Celery and Django server

* Celery worker:

```bash
celery -A scraper_api_service worker -l INFO -E
```

* Celery beat (scheduler):

```bash
celery -A scraper_api_service beat -l INFO
```

* Django server:

```bash
python manage.py runserver
```

* Telegram bot will now respond to `/start` and `/latest` commands.

---


## 🔒 Security

* `.env` is not tracked by GitHub
* `.env.example` provides setup guidance for other developers
* `.gitignore` excludes unnecessary files (`.idea`, `venv/`, `__pycache__/`, etc.)

---

## 👨‍💻 Usage

* Telegram bot commands: `/start` and `/latest`
* API endpoint available via Django Rest Framework (`JobViewSet`)

---
