import pytest
from unittest.mock import AsyncMock, MagicMock
from aiohttp import web
from src.config import Config
from src.webhook import WebhookServer

@pytest.fixture
def mock_config():
    return Config(
        telegram_token="fake_token",
        gemini_api_keys=["fake_key"],
        database_url="sqlite+aiosqlite:///:memory:",
        broadcast_channel_id="-100123456789",
        webhook_secret="test_secret_abc"
    )

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.fetcher = MagicMock()
    bot.transformer = MagicMock()
    bot.grader = MagicMock()
    bot.bot = MagicMock()
    bot.bot.send_message = AsyncMock()
    bot.bot.send_photo = AsyncMock()
    return bot

@pytest.mark.asyncio
async def test_webhook_unauthorized(mock_config, mock_bot):
    server = WebhookServer(
        config=mock_config,
        pipeline=MagicMock(),
        bot=mock_bot,
        broadcast_channel_id=mock_config.broadcast_channel_id
    )
    
    # Create mock request with wrong secret
    request = MagicMock()
    request.match_info = {"secret": "wrong_secret"}
    
    response = await server.handle_webhook(request)
    assert response.status == 403

@pytest.mark.asyncio
async def test_webhook_valid(mock_config, mock_bot):
    server = WebhookServer(
        config=mock_config,
        pipeline=MagicMock(),
        bot=mock_bot,
        broadcast_channel_id=mock_config.broadcast_channel_id
    )
    
    request = MagicMock()
    request.match_info = {"secret": "test_secret_abc"}
    request.json = AsyncMock(return_value={"symbol": "NVDA", "message": "RSI Overbought"})
    
    response = await server.handle_webhook(request)
    assert response.status == 200
    assert response.text == "OK"
