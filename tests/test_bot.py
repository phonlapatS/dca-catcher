from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aiogram.filters import CommandObject
from sqlalchemy import select

from src.bot import DCABot, create_add_watchlist_keyboard
from src.config import Config
from src.database import User, Watchlist


def test_create_add_watchlist_keyboard():
    kb = create_add_watchlist_keyboard("NVDA", "dca_catcher_bot")
    assert len(kb.inline_keyboard) == 1
    row = kb.inline_keyboard[0]
    assert len(row) == 1
    button = row[0]
    assert button.text == "➕ Add NVDA to Watchlist"
    assert button.url == "https://t.me/dca_catcher_bot?start=add_NVDA"


@pytest.mark.asyncio
async def test_cmd_start_regular(tmp_path):
    db_path = tmp_path / "test.db"
    config = Config(
        telegram_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        gemini_api_keys=["test_key"],
        database_url=f"sqlite+aiosqlite:///{db_path}",
        broadcast_channel_id="test_channel",
    )
    bot_app = DCABot(config)
    await bot_app.db.create_tables()

    message = AsyncMock()
    message.from_user = MagicMock(id=12345, username="testuser")

    await bot_app.cmd_start(message, command=None)
    message.answer.assert_called_once()
    args, _ = message.answer.call_args
    assert "Welcome to DCA Catcher Bot!" in args[0]

    await bot_app.db.close()


@pytest.mark.asyncio
async def test_cmd_start_deep_link_us(tmp_path):
    db_path = tmp_path / "test.db"
    config = Config(
        telegram_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        gemini_api_keys=["test_key"],
        database_url=f"sqlite+aiosqlite:///{db_path}",
        broadcast_channel_id="test_channel",
    )
    bot_app = DCABot(config)
    await bot_app.db.create_tables()

    message = AsyncMock()
    message.from_user = MagicMock(id=12345, username="testuser")

    command = CommandObject(command="start", args="add_NVDA")
    await bot_app.cmd_start(message, command=command)

    assert message.answer.call_count == 2
    answers = [call[0][0] for call in message.answer.call_args_list]
    assert "⏳ Adding NVDA to your watchlist..." in answers[0]
    assert "✅ Added NVDA (US) to your watchlist." in answers[1]

    async with bot_app.db.session() as session:
        stmt = select(Watchlist).join(User).where(User.telegram_id == 12345)
        res = await session.execute(stmt)
        items = res.scalars().all()
        assert len(items) == 1
        assert items[0].symbol == "NVDA"
        assert items[0].market == "US"

    await bot_app.db.close()


@pytest.mark.asyncio
async def test_cmd_start_deep_link_th(tmp_path):
    db_path = tmp_path / "test.db"
    config = Config(
        telegram_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        gemini_api_keys=["test_key"],
        database_url=f"sqlite+aiosqlite:///{db_path}",
        broadcast_channel_id="test_channel",
    )
    bot_app = DCABot(config)
    await bot_app.db.create_tables()

    message = AsyncMock()
    message.from_user = MagicMock(id=12345, username="testuser")

    command = CommandObject(command="start", args="add_PTT.BK")
    await bot_app.cmd_start(message, command=command)

    async with bot_app.db.session() as session:
        stmt = select(Watchlist).join(User).where(User.telegram_id == 12345)
        res = await session.execute(stmt)
        items = res.scalars().all()
        assert len(items) == 1
        assert items[0].symbol == "PTT.BK"
        assert items[0].market == "TH"

    await bot_app.db.close()


@pytest.mark.asyncio
async def test_catalyst_button_callbacks(tmp_path):
    db_path = tmp_path / "test_cat.db"
    config = Config(
        telegram_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        gemini_api_keys=["test_key"],
        database_url=f"sqlite+aiosqlite:///{db_path}",
        broadcast_channel_id="test_channel",
    )
    bot_app = DCABot(config)
    await bot_app.db.create_tables()

    # 1. Test cat_watch_btn
    cb_watch = AsyncMock()
    cb_watch.data = "cat_watch_NVDA"
    cb_watch.from_user = MagicMock(id=999, username="catalyst_user")
    await bot_app.cat_watch_btn(cb_watch)
    assert cb_watch.answer.called
    call_args = cb_watch.answer.call_args[0][0]
    assert "Added NVDA" in call_args

    # 2. Test cat_sniper_btn
    cb_sniper = AsyncMock()
    cb_sniper.data = "cat_sniper_NVDA"
    await bot_app.cat_sniper_btn(cb_sniper)
    assert cb_sniper.answer.called
    assert "/scan NVDA" in cb_sniper.answer.call_args[0][0]

    # 3. Test cat_scan_btn
    cb_scan = AsyncMock()
    cb_scan.data = "cat_scan_TSM"
    cb_scan.message = AsyncMock()
    with patch.object(bot_app, "cmd_scan", new_callable=AsyncMock) as mock_scan:
        await bot_app.cat_scan_btn(cb_scan)
        assert cb_scan.answer.called
        assert mock_scan.called
        assert "/scan TSM" in mock_scan.call_args[0][0].text

    await bot_app.db.close()


