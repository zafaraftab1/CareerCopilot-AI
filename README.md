<div align="center">

# Naukri Auto Apply AI

### Smart Job Search + RAG + Ollama + Auto Apply

<img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/Flask-API-000000?style=for-the-badge&logo=flask&logoColor=white" />
<img src="https://img.shields.io/badge/Selenium-Automation-43B02A?style=for-the-badge&logo=selenium&logoColor=white" />
<img src="https://img.shields.io/badge/Ollama-Local%20LLM-111827?style=for-the-badge" />
<img src="https://img.shields.io/badge/RAG-Job%20Retrieval-0EA5E9?style=for-the-badge" />
<img src="https://img.shields.io/badge/Status-Production%20Ready-22C55E?style=for-the-badge" />

<p>
  <b>Beautiful automation pipeline for discovering, ranking, and applying to jobs on Naukri with AI assistance.</b>
</p>

</div>

---

## Why this project is powerful

- Live job scraping from Naukri using Selenium
- Resume-aware match scoring and filtering
- RAG indexing for better job context retrieval
- Ollama-based answer generation for application forms
- `dry_run` mode for safe testing
- Real-time SSE pipeline stream for progress tracking
- Daily profile freshness automation (headline + key skills rotation)

---

## Feature highlights

| Feature | What it gives you |
|---|---|
| Live Naukri Scraper | Pulls fresh jobs by role/location |
| Match Scoring Engine | Prioritizes jobs based on your profile fit |
| RAG Layer | Makes retrieval smarter from stored jobs |
| AI Answer Copilot | Auto-generates concise job-form answers |
| Auto Apply Agent | Batch applies to shortlisted URLs |
| SSE Progress Stream | Shows each step live in the dashboard |
| Profile Updater | Keeps profile active with rotating content |

---

## Tech stack

- **Backend:** Flask, Flask-SQLAlchemy, Flask-CORS
- **Automation:** Selenium + ChromeDriver
- **AI:** Ollama (`/api/chat`, embeddings)
- **Data:** SQLite (default), optional PostgreSQL
- **Scheduling:** APScheduler

---

## Project map

```text
app.py                         -> Flask app + routes + orchestration
naukri_auto_apply_pipeline.py  -> Full auto-apply pipeline (SSE-friendly)
application_engine.py          -> Match/evaluation + application state
job_scraper.py                 -> Naukri live scraper + fallback data
rag_service.py                 -> Job indexing + semantic query
naukri_profile_updater.py      -> Daily profile headline/skills updater
models.py                      -> SQLAlchemy models
scripts/naukri_profile_scrape.py -> Profile data snapshot utility
scripts/naukri_daily_apply.py    -> Daily scripted apply flow
```

---

## Quick start

### 1) Setup environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2) Add required `.env` values

```env
NAUKRI_EMAIL=your_naukri_email
NAUKRI_PASSWORD=your_naukri_password
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_EMBED_MODEL=llama3.2:3b
```

### 3) Start Ollama + app

```bash
ollama serve
ollama pull llama3.2:3b
python app.py --port 5001
```

Open: **http://127.0.0.1:5001**

---

## API showcase

### Live scrape + score + index

```bash
curl -X POST http://127.0.0.1:5001/api/naukri/scrape-live \
  -H "Content-Type: application/json" \
  -d '{"role":"Python Developer","location":"Hyderabad","limit":20,"headless":true}'
```

### Full pipeline

```bash
curl -X POST http://127.0.0.1:5001/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"role":"Python Developer","location":"Hyderabad","limit":20,"min_score":70,"max_apply":5,"dry_run":true,"headless":true}'
```

### RAG query

```bash
curl -X POST http://127.0.0.1:5001/api/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query":"backend python jobs with aws and fastapi","top_k":5}'
```

### Stream live progress (SSE)

```bash
curl -N http://127.0.0.1:5001/api/auto-apply/stream
```

---

## Important endpoints

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

---

## Extra automation tools

```bash
python naukri_profile_updater.py --visible
python naukri_profile_updater.py
python scripts/naukri_profile_scrape.py
python scripts/naukri_daily_apply.py
```

---

## Notes

- Naukri UI changes can break selectors.
- CAPTCHA/OTP bypass is not implemented.
- Use `dry_run=true` before enabling real apply mode.
- Follow platform policies and applicable laws.

---

## Troubleshooting

```bash
curl http://127.0.0.1:11434/api/tags
python app.py --port 5002
python -c "from app import create_app; from models import db; a=create_app(); a.app_context().push(); db.create_all()"
```

---

<div align="center">

### Built for high-signal job hunting with local AI

</div>
