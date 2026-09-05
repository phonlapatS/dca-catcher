import os
from dataclasses import dataclass, field


@dataclass
class Config:
    """Application configuration loaded from environment variables.

    Schedule times and operating hours are configurable via env vars
    so they can be adjusted without code changes (e.g. Daylight Saving).
    """
    telegram_token: str
    gemini_api_keys: list[str]
    database_url: str
    broadcast_channel_id: str
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    sentry_dsn: str = ""
    webhook_port: int = 8080
    webhook_secret: str = "default_secret_123"

    # Broadcast schedule (hours in Asia/Bangkok timezone)
    broadcast_morning_hour: int = 7
    broadcast_morning_minute: int = 0
    broadcast_th_hour: int = 9
    broadcast_th_minute: int = 30
    broadcast_us_hour: int = 20
    broadcast_us_minute: int = 0

    # Sniper operating window (Asia/Bangkok timezone)
    sniper_start_hour: int = 20
    sniper_start_minute: int = 30
    sniper_end_hour: int = 4
    sniper_end_minute: int = 0

    @property
    def gemini_api_key(self) -> str:
        return self.gemini_api_keys[0] if self.gemini_api_keys else ""

    @classmethod
    def from_env(cls) -> "Config":
        keys_str = os.environ.get("GEMINI_API_KEYS", os.environ.get("GEMINI_API_KEY", ""))
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        if not keys:
            raise ValueError("Missing critical environment variable: GEMINI_API_KEYS or GEMINI_API_KEY")
            
        telegram_token = os.environ.get("TELEGRAM_TOKEN", "").strip()
        if not telegram_token:
            raise ValueError("Missing critical environment variable: TELEGRAM_TOKEN")
            
        return cls(
            telegram_token=telegram_token,
            gemini_api_keys=keys,
            database_url=os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///dca_catcher.db"),
            broadcast_channel_id=os.environ.get("BROADCAST_CHANNEL_ID", ""),
            alpaca_api_key=os.environ.get("ALPACA_API_KEY", ""),
            alpaca_secret_key=os.environ.get("ALPACA_SECRET_KEY", ""),
            broadcast_morning_hour=int(os.environ.get("BROADCAST_MORNING_HOUR", "7")),
            broadcast_morning_minute=int(os.environ.get("BROADCAST_MORNING_MINUTE", "0")),
            broadcast_th_hour=int(os.environ.get("BROADCAST_TH_HOUR", "9")),
            broadcast_th_minute=int(os.environ.get("BROADCAST_TH_MINUTE", "30")),
            broadcast_us_hour=int(os.environ.get("BROADCAST_US_HOUR", "20")),
            broadcast_us_minute=int(os.environ.get("BROADCAST_US_MINUTE", "0")),
            sniper_start_hour=int(os.environ.get("SNIPER_START_HOUR", "20")),
            sniper_start_minute=int(os.environ.get("SNIPER_START_MINUTE", "30")),
            sniper_end_hour=int(os.environ.get("SNIPER_END_HOUR", "4")),
            sniper_end_minute=int(os.environ.get("SNIPER_END_MINUTE", "0")),
            webhook_port=int(os.environ.get("WEBHOOK_PORT", "8080")),
            webhook_secret=os.environ.get("WEBHOOK_SECRET", "default_secret_123"),
            sentry_dsn=os.environ.get("SENTRY_DSN", ""),
        )
