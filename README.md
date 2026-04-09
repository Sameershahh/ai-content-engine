# 🤖 AI Content Synthesis Engine

> Discover trends → Generate multi-channel content → Deliver to Google Drive.  
> **Zero cost. Fully async. Production-grade.**

---

## Architecture

```
Playwright Scraper (Reddit + Google Trends)
        │
        ▼
Gemini 2.0 Flash  ──►  Topic Selection + Script + LinkedIn Post + Image Prompt
        │
        ├──► SiliconFlow FLUX  ──►  Background Image (1024×1024)
        │
        ▼
MoviePy Video Engine  ──►  1080×1920 MP4 Reel (15s captions burned in)
        │
        ▼
Google Drive API  ──►  Dated folder: video + text assets
```

---

## Stack

| Layer | Tech |
|---|---|
| API Server | FastAPI + Uvicorn (async) |
| Scraping | Playwright (headless Chromium) |
| LLM | Google Gemini 2.0 Flash (free tier) |
| Image Gen | SiliconFlow FLUX.1-schnell (free tier) |
| Video | MoviePy 2.x + Pillow |
| Delivery | Google Drive API v3 |
| Config | pydantic-settings + .env |
| Logging | structlog (JSON in prod, pretty in dev) |

---

## Quickstart

### 1. Clone & Install

```bash
git clone <repo-url> ai_content_engine
cd ai_content_engine

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env — fill in all API keys
```

### 3. Google Drive Credentials

**Option A — Service Account (recommended for automation)**

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create project → Enable **Google Drive API**
3. IAM → Service Accounts → Create → Download JSON → save as `credentials.json`
4. Share your target Drive folder with the service account email

**Option B — OAuth2 (personal use)**

1. Google Cloud Console → APIs & Services → Credentials
2. Create OAuth2 Client ID (Desktop App) → Download JSON → save as `credentials.json`
3. First run will open a browser for consent; token cached as `token.json`

```bash
# Set your root folder ID in .env
# Get it from the Drive folder URL:
# https://drive.google.com/drive/folders/THIS_IS_YOUR_FOLDER_ID
GDRIVE_ROOT_FOLDER_ID=1aBcDeFgHiJkLmNoPqRsTuVwXyZ
```

### 4. Get API Keys

| Key | Where |
|---|---|
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) → Get API Key |
| `SILICONFLOW_API_KEY` | [cloud.siliconflow.cn](https://cloud.siliconflow.cn) → Register (free credits) |

### 5. Run

```bash
uvicorn main:app --reload --port 8000
```

Swagger UI → `http://localhost:8000/docs`

---

## API Reference

### `POST /api/v1/pipeline/run`

Trigger the full pipeline. Returns `job_id` immediately (non-blocking).

```json
// Request body (all fields optional)
{
  "custom_topic": "How AI is replacing spreadsheets",  // skip scraping
  "subreddits": ["technology", "artificial"],          // override .env
  "geo": "US"                                          // Google Trends geo
}
```

```json
// Response 202
{ "job_id": "3f9a1b2c-...", "status": "queued" }
```

---

### `GET /api/v1/pipeline/status/{job_id}`

Poll for results.

```json
// Response when done
{
  "job_id": "3f9a1b2c-...",
  "status": "done",
  "topic": "AI is replacing spreadsheets in finance",
  "video_path": "outputs/3f9a1b2c_reel.mp4",
  "text_path": "outputs/3f9a1b2c_content.txt",
  "drive_folder_url": "https://drive.google.com/drive/folders/..."
}
```

Possible `status` values: `queued` → `running` → `done` | `failed`

---

### `GET /api/v1/pipeline/jobs`

List all jobs in current session.

---

### `GET /api/v1/health`

```json
{ "status": "ok", "timestamp": "2026-04-08T10:00:00Z" }
```

---

## Example: cURL

```bash
# Trigger pipeline
JOB=$(curl -s -X POST http://localhost:8000/api/v1/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")

echo "Job: $JOB"

# Poll status
watch -n 5 "curl -s http://localhost:8000/api/v1/pipeline/status/$JOB | python3 -m json.tool"
```

---

## Project Structure

```
ai_content_engine/
├── main.py                          # FastAPI app + lifespan
├── requirements.txt
├── .env.example
├── credentials.json                 # Google credentials (gitignored)
│
├── app/
│   └── api/v1/
│       ├── router.py
│       └── endpoints/
│           ├── health.py
│           └── pipeline.py
│
├── core/
│   ├── config.py                    # pydantic-settings
│   ├── logging.py                   # structlog setup
│   └── models.py                    # shared Pydantic schemas
│
├── services/
│   ├── scraper.py                   # Playwright Reddit + Google Trends
│   ├── ai_brain.py                  # Gemini topic selection + content gen
│   ├── image_gen.py                 # SiliconFlow FLUX image generation
│   ├── video_engine.py              # MoviePy MP4 renderer (thread pool)
│   ├── drive_uploader.py            # Google Drive upload
│   └── pipeline.py                  # End-to-end orchestrator + job store
│
├── utils/
│   └── file_utils.py
│
├── outputs/                         # Generated MP4s + text files
└── temp/                            # Intermediate images (auto-cleaned)
```

---

## Production Considerations

| Concern | Current | Upgrade Path |
|---|---|---|
| Job state | In-memory dict | Redis + Celery |
| Workers | Single process | Gunicorn multi-worker |
| Auth | None | API key middleware |
| Cleanup | Manual | Scheduled task (APScheduler) |
| Rate limits | tenacity retry | Token bucket per service |
| Drive quota | 15 GB free | Workspace (paid) |

---

## Troubleshooting

**Playwright browser not found**
```bash
playwright install chromium --with-deps
```

**SiliconFlow returns no image**  
Check your free credit balance at cloud.siliconflow.cn. Fallback gradient image is used automatically.

**MoviePy font errors**  
Install system fonts:
```bash
# Ubuntu/Debian
sudo apt-get install fonts-liberation

# macOS
brew install --cask font-liberation
```

**Google Drive 403**  
Ensure the service account email has Editor access to your Drive folder, or re-run OAuth2 consent.

---

## License

MIT
