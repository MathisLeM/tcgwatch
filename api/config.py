"""Application configuration via pydantic-settings (mirrors Vigilyx app/config.py).

Values are read from environment variables / a local .env file. See .env.example.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict

# Sentinel used by main.py to refuse to boot in production with a default secret.
_WEAK_SECRET = "changeme-use-a-long-random-string-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- Environment -----------------------------------------------------------
    ENVIRONMENT: str = "development"

    # -- Database --------------------------------------------------------------
    # Local dev defaults to the scraper's existing SQLite DB so the API serves
    # real data immediately. Production points at Supabase Postgres.
    DATABASE_URL: str = "sqlite:///./data/tcg_stock.sqlite"

    # -- API server ------------------------------------------------------------
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000

    # -- CORS ------------------------------------------------------------------
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # -- Auth ------------------------------------------------------------------
    # Generate: python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY: str = _WEAK_SECRET
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8 hours
    # Alpha: public self-signup is closed — accounts are provisioned with
    # `python -m scripts.manage_users create`. Flip to true to reopen /auth/signup.
    ALLOW_PUBLIC_SIGNUP: bool = False

    # -- Scraper worker scheduler ----------------------------------------------
    SCRAPE_INTERVAL_HOURS: int = 6
    SCRAPE_GAMES: str = "all"  # "all" | "optcg" | "pokemon"

    # -- Email (SMTP) ----------------------------------------------------------
    # Leave SMTP_HOST empty to disable real sending (dry-run logging only).
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    FROM_EMAIL: str = "TCGWatch <alertes@tcgwatch.app>"

    # -- Discord ---------------------------------------------------------------
    DISCORD_WEBHOOK_URL: str = ""  # optional global/system webhook

    # -- Frontend --------------------------------------------------------------
    APP_URL: str = "http://localhost:3000"

    # -- Cloudflare R2 (S3-compatible image storage) ---------------------------
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET: str = ""
    R2_PUBLIC_BASE_URL: str = ""

    # -- Derived ---------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def r2_enabled(self) -> bool:
        return bool(self.R2_BUCKET and self.R2_ACCESS_KEY_ID and self.R2_ACCOUNT_ID)


settings = Settings()
