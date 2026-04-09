# AI Content Synthesis Engine

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Playwright](https://img.shields.io/badge/Playwright-Web_Scraping-31A8FF.svg)
![MoviePy](https://img.shields.io/badge/MoviePy-Video_Engine-FF3366.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-Optional_API-009688.svg)

An automated, end-to-end pipeline that discovers trending topics, generates engaging scripts, synthesizes background visuals, renders short-form videos (like Instagram Reels/TikToks), and uploads them directly to Google Drive.

## Features

- **Automated Topic Discovery**: Scrapes Google Trends and Reddit subreddits to find the most viral, up-to-date topics.
- **AI Brain (Gemini)**: Utilizes Google's Gemini Flash models to select the best topic, write a catchy video script, and generate engaging social media captions. Includes dynamic rate-limit resilience and model fallbacks.
- **Image Generation**: Integrates with SiliconFlow/FLUX to generate cinematic, ultra-HD background images based on the script's mood.
- **Video Rendering Engine**: Pure Python rendering utilizing `MoviePy 2.x` and `Pillow`, completely bypassing standard external dependencies like ImageMagick for cross-platform stability.
- **Cloud Delivery**: Automatically authenticates via Google Service Accounts and uploads the rendered video and text captions to designated, date-stamped folders in Google Drive.
- **Headless & Server Modes**: Run the pipeline directly via CLI or deploy the built-in FastAPI module.

## Prerequisites

- Python 3.11 or higher
- Windows/macOS/Linux
- Active API Keys for:
  - **Google Gemini API** (Google AI Studio)
  - **SiliconFlow API** (for Image Gen)
- A **Google Cloud Service Account** (`credentials.json`) with Google Drive API enabled.

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Sameershahh/ai-content-engine.git
   cd ai-content-engine
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   ```
   *Activate it:*
   - Windows: `.\.venv\Scripts\activate`
   - Mac/Linux: `source .venv/bin/activate`

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

## Configuration

1. Copy the example `.env` file:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and fill in your keys:
   ```env
   GEMINI_API_KEY="your_google_gemini_key"
   SILICONFLOW_API_KEY="your_siliconflow_key"
   GDRIVE_ROOT_FOLDER_ID="your_drive_folder_id"
   ```
3. Place your Google Service Account JSON key in the root directory and name it `credentials.json`. Ensure that this service account email is added as an **Editor** to your target Google Drive folder.

## Usage

To run the pipeline from start to finish via the command line, use the included CLI script. 

**Run with automatic topic discovery:**
```bash
python run_pipeline.py
```

**Run with a custom topic:**
```bash
python run_pipeline.py "How AI is changing the future of software engineering"
```

### Outputs
Once completed, the pipeline outputs will be saved in the local `outputs/` directory and automatically pushed to Google Drive:
- `*_reel.mp4`: The final 15-second portrait video.
- `*_content.txt`: The script, captions, and hashtags.

## Repository Structure

```text
├── core/                  # Configurations, Logging, Pydantic Models 
├── services/              # Core Logic / Sub-agents
│   ├── ai_brain.py        # Gemini API handling & Fallback Logic
│   ├── scraper.py         # Playwright-based Trends & Reddit scraping
│   ├── image_gen.py       # SiliconFlow image generation
│   ├── video_engine.py    # MoviePy 2.x rendering engine (Pillow backend)
│   ├── drive_uploader.py  # Google Drive API delivery
│   └── pipeline.py        # Master Orchestrator connecting all services
├── app/                   # FastAPI Server implementation (Optional)
├── utils/                 # Utility helpers
├── run_pipeline.py        # Main CLI Entrypoint
├── requirements.txt       # Project dependencies
└── README.md              # Documentation
```

## License & Disclaimer
This is for educational and personal use. Make sure your scraping operations comply with Reddit and Google's Terms of Service.

## Author
**Sameer Shah** — AI & Full-Stack Developer  
[Portfolio](https://sameershah-portfolio.vercel.app/) 

