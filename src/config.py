import os
from dataclasses import dataclass


@dataclass
class Config:
    """Application configuration loaded from environment variables."""
    telegram_token: str
    gemini_api_keys: list[str]
    database_url: str
    broadcast_channel_id: str

    @classmethod
    def from_env(cls) -> "Config":
        keys_str = os.environ.get("GEMINI_API_KEYS", os.environ.get("GEMINI_API_KEY", ""))
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        return cls(
            telegram_token=os.environ.get("TELEGRAM_TOKEN", ""),
            gemini_api_keys=keys,
            database_url=os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///dca_catcher.db"),
            broadcast_channel_id=os.environ.get("BROADCAST_CHANNEL_ID", ""),
        )
