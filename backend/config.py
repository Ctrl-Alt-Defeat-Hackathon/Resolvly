from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Insurance Claim & Billing Debugger API"
    app_version: str = "1.0.0"
    debug: bool = False

    # LLM — Groq (OpenAI-compatible) preferred; Gemini optional fallback
    groq_api_key: str = ""
    groq_model_primary: str = "llama-3.3-70b-versatile"
    groq_model_fallback: str = "llama-3.1-8b-instant"

    gemini_api_key: str = ""
    gemini_model_primary: str = "gemini-2.5-flash-preview-04-17"
    gemini_model_fallback: str = "gemini-2.0-flash"

    # File upload limits
    max_file_size_mb: int = 10
    max_files_per_upload: int = 5

    # Rate limiting
    rate_limit_per_minute: int = 10

    # CORS
    allowed_origins: list[str] = ["http://localhost:3000", "https://*.vercel.app"]

    # Google Cloud Vision (fallback OCR)
    google_vision_api_key: str = ""

    # Google Search API (fallback web search)
    google_search_api_key: str = ""
    google_search_cx: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
