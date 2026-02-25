# Naukri Auto Apply AI

Automation toolkit for Naukri job discovery, fit scoring, RAG-assisted Q&A, and guided auto-apply workflows.

## What this project does

- Scrapes jobs from Naukri using Selenium (`NaukriLiveScraper`)
- Scores jobs against your resume and skill profile
- Stores jobs/applications in SQLite via SQLAlchemy
- Indexes jobs into a local RAG store for semantic retrieval
- Generates job-form answers using local Ollama models
- Runs auto-apply in `dry_run` or real apply mode
- Streams end-to-end auto-apply progress over SSE
- Includes a daily Naukri profile updater (headline + rotating skill)

## Tech stack

- Python 3.10+
- Flask, Flask-SQLAlchemy, Flask-CORS
- Selenium (Chrome/Chromedriver)
- Ollama (local LLM + embeddings)
- APScheduler (optional scheduled jobs)

## Project structure

- `app.py` - main Flask app, dashboard routes, API orchestration
- `naukri_auto_apply_pipeline.py` - SSE-friendly full auto-apply pipeline
- `application_engine.py` - evaluation logic + application handling
- `job_scraper.py` - live Naukri scraper + fallback/mock data utilities
- `rag_service.py` - vector-like indexing/query layer for jobs
- `naukri_profile_updater.py` - daily profile freshness automation
- `models.py` - DB models (`CandidateProfile`, `JobListing`, `JobApplication`, etc.)
- `templates/dashboard.html` + `static/` - dashboard UI
- `scripts/naukri_profile_scrape.py` - extract profile data snapshot
- `scripts/naukri_daily_apply.py` - daily apply flow from profile data

## Setup

1. Create/activate virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Configure environment

```bash
cp .env.example .env
```

Set at minimum:

```env
NAUKRI_EMAIL=your_naukri_email
NAUKRI_PASSWORD=your_naukri_password
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_EMBED_MODEL=llama3.2:3b
```

4. Start Ollama

```bash
ollama serve
ollama pull llama3.2:3b
```

5. Run the app

```bash
python app.py --port 5001
```

Open: `http://127.0.0.1:5001`

## Quick API usage

### 1. Scrape + score + index (live Naukri)

```bash
curl -X POST http://127.0.0.1:5001/api/naukri/scrape-live \
  -H "Content-Type: application/json" \
  -d '{
    "role": "Python Developer",
    "location": "Hyderabad",
    "limit": 20,
    "headless": true
  }'
```

### 2. Full pipeline run

```bash
curl -X POST http://127.0.0.1:5001/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{
    "role": "Python Developer",
    "location": "Hyderabad",
    "limit": 20,
    "min_score": 70,
    "max_apply": 5,
    "dry_run": true,
    "headless": true
  }'
```

### 3. RAG query

```bash
curl -X POST http://127.0.0.1:5001/api/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query":"backend python jobs with aws and fastapi", "top_k": 5}'
```

### 4. Auto-apply stream (SSE)

```bash
curl -N http://127.0.0.1:5001/api/auto-apply/stream
```

## Key endpoints

- `GET /api/dashboard-stats`
- `GET /api/applications`
- `POST /api/search-jobs`
- `POST /api/naukri/scrape-live`
- `POST /api/naukri/auto-apply`
- `POST /api/pipeline/run`
- `POST /api/rag/reindex`
- `POST /api/rag/query`
- `GET|POST /api/ai/settings`
- `GET /api/ai/provider-status`
- `POST /api/ai/answers`
- `GET /api/auto-apply/stream`
- `GET /api/auto-apply/status`

## Automation scripts

### Daily profile update

```bash
python naukri_profile_updater.py --visible
# for scheduled/headless runs
python naukri_profile_updater.py
```

### Profile scrape + daily apply (scripts/)

```bash
python scripts/naukri_profile_scrape.py
python scripts/naukri_daily_apply.py
```

## Notes and limitations

- Naukri UI/CSS changes can break Selenium selectors.
- CAPTCHA/OTP/manual verification is not bypassed.
- Always test with `dry_run=true` before real apply mode.
- Respect Naukri terms of service and local laws.

## Troubleshooting

- Ollama check:

```bash
curl http://127.0.0.1:11434/api/tags
```

- If app port is busy:

```bash
python app.py --port 5002
```

- Recreate DB tables:

```bash
python -c "from app import create_app; from models import db; a=create_app(); a.app_context().push(); db.create_all()"
```

## Disclaimer

For educational/personal automation use. You are responsible for compliant usage of this project.
