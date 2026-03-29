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
    gemini_model_primary: str = "gemini-2.5-flash"  # Stable model (10 RPM free tier)
    gemini_model_fallback: str = "gemini-2.5-flash-lite"  # Faster fallback (15 RPM free tier)

    # Ollama (local fallback - only used in development)
    ollama_enabled: bool = False  # Set to true to enable Ollama as final fallback
    ollama_base_url: str = "http://localhost:11434"  # Default Ollama URL
    ollama_model: str = "llama3.2"  # Model to use (must be pulled: ollama pull llama3.2)

    # File upload limits
    max_file_size_mb: int = 10
    max_files_per_upload: int = 5

    # Rate limiting
    rate_limit_per_minute: int = 10
    
    # LLM rate limiting
    llm_max_concurrent_requests: int = 1  # Max concurrent LLM API calls (conservative to avoid rate limits)
    llm_retry_on_rate_limit: bool = True  # Retry with backoff on 429 errors
    llm_min_delay_between_requests: float = 2.0  # Minimum seconds between LLM requests

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
