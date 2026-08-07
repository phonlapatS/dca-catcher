import os
from dataclasses import dataclass


@dataclass
class Config:
    """Application configuration loaded from environment variables."""
    telegram_token: str
    gemini_api_key: str
    database_url: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            telegram_token=os.environ.get("TELEGRAM_TOKEN", ""),
            gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
            database_url=os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///dca_catcher.db"),
        )
