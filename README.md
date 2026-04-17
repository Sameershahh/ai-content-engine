# AI Content Engine

The AI Content Engine is a high-performance system designed to automate the creation of short-form video content (Reels, TikToks) and cross-platform social media assets. It leverages advanced Large Language Models (LLMs) and generative media APIs to produce professional-grade videos from a single topic input.

## Features

- **Automated Research**: Scrapes trending topics and audience sentiment from social platforms.
- **Multimodal Generation**:
    - **Scripting**: Utilizes Gemini 2.x/3.x for viral script development and LinkedIn post generation.
    - **Voiceover**: High-fidelity narration via SiliconFlow (Fish Audio) with a robust gTTS fallback.
    - **Visuals**: Dynamic video generation using FLUX/Wan2.1 models with automatic image/gradient fallbacks.
- **High-End Rendering**: Orchestrated via MoviePy with custom ImageMagick configurations for text overlay and cinematic effects.
- **Automated Delivery**: Direct integration with Google Drive for asset storage and distribution.

## System Architecture

The engine follows a modular service-oriented architecture:

1.  **Core Configuration**: Centralized settings management using Pydantic Settings and strict environment validation.
2.  **Scraper Service**: Handles topic discovery and data enrichment.
3.  **AIBrain Service**: Manages LLM orchestration, including robust JSON parsing and model failover logic.
4.  **Voice Service**: Connects to TTS providers with automatic error handling and local synthesis fallback.
5.  **Visual Service**: Generates background media (video/images) tailored to the script's emotional context.
6.  **Video Engine**: Performs the final assembly, synchronizing audio, visuals, and dynamic subtitles.

## Setup Requirements

### External Dependencies

1.  **Python 3.10+**: Recommended environment.
2.  **ImageMagick**: Required by MoviePy for text rendering. Ensure the binary path is correctly set in `core/config.py` or your environment variables.
3.  **FFmpeg**: Required for video transcoding and audio merging.

### Installation

```bash
# Clone the repository
git clone https://github.com/Sameershahh/ai-content-engine.git
cd ai-content-engine

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the root directory based on `.env.example`:

1. Copy the example `.env` file:
   ```bash
   cp .env.example .env
   ```
2. Configure your API keys and parameters:
   ```env
   GEMINI_API_KEY=your_gemini_key
   SILICONFLOW_API_KEY=your_siliconflow_key
   DRIVE_CREDENTIALS_PATH=credentials.json
   ```
3. Place your Google Service Account JSON key in the root directory as `credentials.json`. Ensure the service account email is added as an **Editor** to your target Google Drive folder.

## Usage

To generate a new reel and its associated metadata:

```bash
# Generate content for a specific topic
python run_pipeline.py "The impact of quantum computing on cybersecurity"

# Direct run with default trending discovery
python run_pipeline.py
```

Outputs will be generated in the `outputs/` directory and automatically uploaded to the configured Google Drive folder.

## Failover Mechanisms

The system is designed for high availability:
- **LLM Failover**: If the primary Gemini model is unavailable, the system automatically cycles through fallback models.
- **TTS Fallback**: If the SiliconFlow API returns a 401 or connection error, the system seamlessly switches to gTTS to ensure the pipeline completes.
- **Visual Fallback**: If video generation fails, the system transitions to static image generation, and finally to cinematic gradient rendering.

## License & Disclaimer

This project is specialized for professional content automation. Ensure compliance with API provider terms of service (Google, SiliconFlow) and platform guidelines (Reddit, LinkedIn) before deployment.

---

**Author**  
**Sameer Shah** — AI & Full-Stack Developer  
[Portfolio](https://sameershah-portfolio.vercel.app/)
