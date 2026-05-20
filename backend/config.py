from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    app_name: str = "Insurance Claim & Billing Debugger API"
    app_version: str = "1.0.0"
    debug: bool = False

    # LLM — OpenAI (https://platform.openai.com/api-keys)
    openai_api_key: str = ""
    openai_model_primary: str = "gpt-4o-mini"
    openai_model_fallback: str = "gpt-4o"
    openai_base_url: str = ""  # Optional; default https://api.openai.com/v1

    # Ollama (local fallback - only used in development)
    ollama_enabled: bool = False  # Set to true to enable Ollama as final fallback
    ollama_base_url: str = "http://localhost:11434"  # Default Ollama URL
    ollama_model: str = "llama3.2"  # Model to use (must be pulled: ollama pull llama3.2)

    # File upload limits
    max_file_size_mb: int = 10
    max_files_per_upload: int = 5

    # Rate limiting
    rate_limit_per_minute: int = 10
    
    # LLM rate limiting (raise concurrent for faster Action Plan; lower if you hit OpenAI 429s)
    llm_max_concurrent_requests: int = 3
    llm_retry_on_rate_limit: bool = True
    llm_min_delay_between_requests: float = 0.1

    # CORS
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://*.vercel.app",
    ]

    # Google Cloud Vision (fallback OCR)
    google_vision_api_key: str = ""

    # Google Search API (fallback web search)
    google_search_api_key: str = ""
    google_search_cx: str = ""


@lru_cache()
def get_settings() -> Settings:
    return Settings()
