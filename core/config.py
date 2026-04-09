"""
core/config.py — Centralised settings via pydantic-settings.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Gemini ──────────────────────────────────
    gemini_api_key: str = Field(..., alias="GEMINI_API_KEY")
    gemini_model: str = "gemini-2.5-flash"

    # ── SiliconFlow ─────────────────────────────
    siliconflow_api_key: str = Field(..., alias="SILICONFLOW_API_KEY")
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_image_model: str = "black-forest-labs/FLUX.1-schnell"

    # ── Google Drive ────────────────────────────
    gdrive_credentials_json: str = "credentials.json"
    gdrive_root_folder_id: str = Field(..., alias="GDRIVE_ROOT_FOLDER_ID")

    # ── App ─────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"
    output_dir: str = "outputs"
    temp_dir: str = "temp"

    # ── Scraping ────────────────────────────────
    reddit_subreddits: str = "technology,artificial,MachineLearning"
    trends_geo: str = "US"

    # ── System ──────────────────────────────────
    imagemagick_binary: str = Field(
        default=r"D:\Program\ImageMagick-7.1.2-Q16\magick.exe",
        alias="IMAGEMAGICK_BINARY",
    )

    @property
    def subreddit_list(self) -> list[str]:
        return [s.strip() for s in self.reddit_subreddits.split(",")]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
