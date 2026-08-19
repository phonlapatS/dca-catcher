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
        webhook_secret="test_secret_abc",
        webhook_port=8080
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
    bot.bot.get_me = AsyncMock(return_value=MagicMock(username="dca_test_bot"))
    return bot


@pytest.mark.asyncio
async def test_webhook_unauthorized(mock_config, mock_bot):
    server = WebhookServer(
        config=mock_config,
        pipeline=MagicMock(),
        bot=mock_bot,
        broadcast_channel_id=mock_config.broadcast_channel_id
    )
    
    request = MagicMock()
    request.match_info = {"secret": "wrong_secret"}
    
    response = await server.handle_webhook(request)
    assert response.status == 403
    assert response.text == "Forbidden"


@pytest.mark.asyncio
async def test_webhook_valid_standard_symbol(mock_config, mock_bot):
    server = WebhookServer(
        config=mock_config,
        pipeline=MagicMock(),
        bot=mock_bot,
        broadcast_channel_id=mock_config.broadcast_channel_id
    )
    
    request = MagicMock()
    request.match_info = {"secret": "test_secret_abc"}
    request.json = AsyncMock(return_value={"symbol": "NVDA", "message": "RSI Oversold"})
    
    response = await server.handle_webhook(request)
    assert response.status == 200
    assert response.text == "OK"


@pytest.mark.asyncio
async def test_webhook_valid_exchange_prefix(mock_config, mock_bot):
    server = WebhookServer(
        config=mock_config,
        pipeline=MagicMock(),
        bot=mock_bot,
        broadcast_channel_id=mock_config.broadcast_channel_id
    )
    
    request = MagicMock()
    request.match_info = {"secret": "test_secret_abc"}
    request.json = AsyncMock(return_value={"ticker": "NASDAQ:AAPL", "action": "EMA 200 Cross"})
    
    response = await server.handle_webhook(request)
    assert response.status == 200
    assert response.text == "OK"


@pytest.mark.asyncio
async def test_webhook_thai_stock_normalization(mock_config, mock_bot):
    server = WebhookServer(
        config=mock_config,
        pipeline=MagicMock(),
        bot=mock_bot,
        broadcast_channel_id=mock_config.broadcast_channel_id
    )
    
    request = MagicMock()
    request.match_info = {"secret": "test_secret_abc"}
    request.json = AsyncMock(return_value={"ticker": "SET:KBANK", "alert": "Support Level"})
    
    response = await server.handle_webhook(request)
    assert response.status == 200
    assert response.text == "OK"


@pytest.mark.asyncio
async def test_webhook_missing_symbol(mock_config, mock_bot):
    server = WebhookServer(
        config=mock_config,
        pipeline=MagicMock(),
        bot=mock_bot,
        broadcast_channel_id=mock_config.broadcast_channel_id
    )
    
    request = MagicMock()
    request.match_info = {"secret": "test_secret_abc"}
    request.json = AsyncMock(return_value={"message": "No symbol here"})
    
    response = await server.handle_webhook(request)
    assert response.status == 400
    assert "Missing symbol" in response.text


@pytest.mark.asyncio
async def test_webhook_process_alert_flow(mock_config, mock_bot):
    server = WebhookServer(
        config=mock_config,
        pipeline=MagicMock(),
        bot=mock_bot,
        broadcast_channel_id=mock_config.broadcast_channel_id
    )

    # Setup mock data for process_alert
    mock_snapshot = MagicMock(current_price=220.0, drawdown_pct=15.0)
    mock_bot.fetcher.fetch.return_value = {"NVDA": mock_snapshot}
    
    mock_enriched = MagicMock(snapshot=mock_snapshot)
    mock_bot.transformer.enrich.return_value = {"NVDA": mock_enriched}
    
    mock_grade_result = MagicMock(
        symbol="NVDA",
        score=9,
        confidence=90,
        advice="เข้าซื้อสะสมไม้ 1",
        reasons=["RSI Oversold", "P/E ต่ำ"],
        buy_targets=[215.0, 200.0, 185.0]
    )
    mock_bot.grader.grade.return_value = mock_grade_result

    await server.process_alert("NVDA", "Test Signal")

    assert mock_bot.fetcher.fetch.called
    assert mock_bot.transformer.enrich.called
    assert mock_bot.grader.grade.called
    assert mock_bot.bot.send_message.called
