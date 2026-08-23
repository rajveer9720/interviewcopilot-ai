"""
Application configuration — loaded from environment variables.
All secrets injected via Docker secrets / GitHub Actions secrets at runtime.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Literal

# Resolved relative to this file (not the process cwd) so `.env` loads
# correctly whether the app is started from the repo root (`backend.main:app`,
# the convention used both in Docker and locally) or from within `backend/`.
ENV_FILE_PATH = Path(__file__).resolve().parent / ".env"


class Settings(BaseSettings):
    # ──────────────────────────────────────────────
    # Application
    # ──────────────────────────────────────────────
    APP_NAME: str = "InterviewCopilot AI"
    APP_VERSION: str = "1.0.0"
    ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    SECRET_KEY: str                         # generate: openssl rand -hex 32
    FRONTEND_URL: str = "http://localhost:3000"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # ──────────────────────────────────────────────
    # Database
    # ──────────────────────────────────────────────
    DATABASE_URL: str                       # postgresql+asyncpg://user:pass@host/db
    DB_POOL_SIZE: int = 10
    DB_POOL_OVERFLOW: int = 20

    # ──────────────────────────────────────────────
    # Redis
    # ──────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_POOL_SIZE: int = 20

    # ──────────────────────────────────────────────
    # JWT Auth
    # ──────────────────────────────────────────────
    PRIVATE_KEY: str                        # RSA private key (PEM format)
    PUBLIC_KEY: str                         # RSA public key (PEM format)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ALGORITHM: Literal["RS256"] = "RS256"

    # ──────────────────────────────────────────────
    # AI Providers
    # ──────────────────────────────────────────────
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_WHISPER_MODEL: str = "whisper-1"

    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-1.5-pro"

    # ──────────────────────────────────────────────
    # Storage (S3-compatible)
    # ──────────────────────────────────────────────
    # Use Google Cloud Storage (GCS) instead of AWS S3.
    GCS_BUCKET_NAME: str = "interviewcopilot-resumes"
    # Optional: path to a service account JSON file. If omitted, Application
    # Default Credentials will be used (e.g. GOOGLE_APPLICATION_CREDENTIALS env).
    GOOGLE_APPLICATION_CREDENTIALS: str | None = None

    # ──────────────────────────────────────────────
    # Razorpay
    # ──────────────────────────────────────────────
    RAZORPAY_KEY_ID: str
    RAZORPAY_KEY_SECRET: str
    RAZORPAY_WEBHOOK_SECRET: str
    RAZORPAY_PRO_PLAN_ID: str
    RAZORPAY_ENTERPRISE_PLAN_ID: str

    # ──────────────────────────────────────────────
    # Rate Limiting
    # ──────────────────────────────────────────────
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10
    RATE_LIMIT_API_PER_MINUTE: int = 100
    RATE_LIMIT_AI_FREE_PER_MINUTE: int = 30
    RATE_LIMIT_AI_PRO_PER_MINUTE: int = 200

    # ──────────────────────────────────────────────
    # CORS
    # ──────────────────────────────────────────────
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "app://.",       # Electron custom protocol
    ]

    model_config = SettingsConfigDict(env_file=ENV_FILE_PATH, case_sensitive=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
