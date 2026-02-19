# 🚀 AI Job Autopilot: Naukri + RAG + Ollama

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Flask-API-black?style=for-the-badge&logo=flask" />
  <img src="https://img.shields.io/badge/Ollama-Local%20LLM-111827?style=for-the-badge" />
  <img src="https://img.shields.io/badge/RAG-Vector%20Search-10B981?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Selenium-Auto%20Apply-43B02A?style=for-the-badge&logo=selenium" />
</p>

<p align="center">
Automate job search, ranking, answer generation, and apply flows with a local AI stack.
</p>

---

## 🌈 What This Project Does

- 🕷️ **Scrapes jobs from Naukri (live)**
- 🧠 **Scores role fit** using resume + skills matching
- 📚 **Builds local vector DB (RAG)** for better retrieval/context
- 🤖 **Generates form answers** with Ollama (`llama3.2:3b`, DeepSeek, etc.)
- ⚙️ **Runs full pipeline**: scrape → rank → index → apply
- 🧪 **Dry-run mode** for safe testing before real apply

---

## 🧩 Tech Stack

- **Backend**: Flask + SQLAlchemy
- **AI**: Ollama local models (`/api/chat`, `/api/embeddings`, CLI fallback)
- **Automation**: Selenium (Chrome)
- **RAG Store**: local SQL table `rag_documents`
- **UI**: HTML/CSS/JS dashboard

---

## ⚡ Quick Start

### 1. Install dependencies
```bash
python3 -m pip install -r requirements.txt
```

### 2. Configure env
```bash
cp .env.example .env
```

Set required values in `.env`:
```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_EMBED_MODEL=llama3.2:3b
NAUKRI_EMAIL=your_email
NAUKRI_PASSWORD=your_password
```

### 3. Start Ollama
```bash
ollama serve
ollama list
```

### 4. Run app
```bash
python3 app.py
```

Open: **http://127.0.0.1:5001**

---

## 🔥 Full Pipeline (One API Call)

```bash
curl -X POST http://127.0.0.1:5001/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{
    "role":"Python Developer",
    "location":"Hyderabad",
    "limit":20,
    "min_score":70,
    "max_apply":5,
    "dry_run":true,
    "headless":true
  }'
```

---

## 🧭 UI Workflow

Go to **Settings** section in dashboard:

1. **AI Copilot**
- Set Ollama URL/model
- Click `Test Ollama Connection`
- Paste job questions (one per line)
- Click `Generate Auto Answers`

2. **Live Naukri + RAG Pipeline**
- Set role/location/min score
- Use `Dry Run` toggle for safe mode
- Click:
  - `Scrape Naukri Live`
  - `Test RAG Retrieval`
  - `Run Full Pipeline`

---

## 🧪 Core API Endpoints

### AI + Answers
- `GET /api/ai/provider-status`
- `GET/POST /api/ai/settings`
- `POST /api/ai/answers`

### Live Jobs + RAG
- `POST /api/naukri/scrape-live`
- `POST /api/rag/reindex`
- `POST /api/rag/query`

### Auto Apply
- `POST /api/naukri/auto-apply`
- `POST /api/pipeline/run`

### Existing Dashboard APIs
- `GET /api/dashboard-stats`
- `POST /api/search-jobs`
- `POST /api/apply-jobs`
- `GET /api/applications`

---

## 📁 Key Files

- `app.py` - main API routes + orchestration
- `rag_service.py` - local vector index and retrieval
- `job_scraper.py` - live Naukri scraper + mock fallback
- `application_engine.py` - apply engine + Selenium auto-apply agent
- `models.py` - SQLAlchemy models (`RagDocument`, `JobListing`, etc.)
- `templates/dashboard.html` - UI
- `static/js/dashboard.js` - UI actions and API wiring

---

## ⚠️ Important Notes

- Naukri may show anti-bot/CAPTCHA challenges.
- This project does **not** bypass CAPTCHA.
- Use `dry_run=true` first, then switch to real apply.
- Respect job portal terms and local laws.

---

## 🛠️ Troubleshooting

### Ollama not detected
```bash
ollama serve
ollama list
curl http://127.0.0.1:11434/api/tags
```

### Port busy
```bash
python3 app.py --port 5002
```

### Rebuild DB quickly
```bash
python3 -c "from app import create_app; from models import db; app = create_app(); app.app_context().push(); db.create_all()"
```

---

## 📜 Disclaimer

This tool is for educational/personal automation use. Always comply with platform policy and applicable law.
# CareerCopilot-AI
