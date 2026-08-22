import io
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy import select

from src.bot import DCABot
from src.config import Config
from src.database import PortfolioTransaction, User


@pytest.fixture
def test_config(tmp_path):
    db_path = tmp_path / "test_portfolio.db"
    return Config(
        telegram_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        gemini_api_keys=["test_gemini_key"],
        database_url=f"sqlite+aiosqlite:///{db_path}",
        broadcast_channel_id="test_channel",
    )


@pytest.mark.asyncio
async def test_handle_photo_slip_success(test_config):
    bot_app = DCABot(test_config)
    await bot_app.db.create_tables()

    # Mock Telegram message with photo
    message = AsyncMock()
    photo_mock = MagicMock()
    photo_mock.file_id = "photo_abc_123"
    message.photo = [photo_mock]
    status_msg = AsyncMock()
    message.reply.return_value = status_msg

    # Mock bot get_file and download_file
    bot_app.bot.get_file = AsyncMock(return_value=MagicMock(file_path="photos/slip.jpg"))
    bot_app.bot.download_file = AsyncMock(return_value=io.BytesIO(b"fake_image_bytes"))

    # Mock GeminiSlipParser
    parsed_data = {
        "symbol": "NVDA",
        "action": "BUY",
        "price": 125.50,
        "volume": 10.0,
    }
    with patch("src.bot.GeminiSlipParser") as MockParser:
        mock_parser_instance = AsyncMock()
        mock_parser_instance.parse_slip.return_value = parsed_data
        MockParser.return_value = mock_parser_instance

        await bot_app.handle_photo_slip(message)

    # Verify status reply
    message.reply.assert_called_once_with("📸 กำลังให้ AI สแกนสลิป...")

    # Verify edit_text with confirmation text and buttons
    status_msg.edit_text.assert_called_once()
    args, kwargs = status_msg.edit_text.call_args
    text = args[0]
    assert "🎯 สแกนสลิปสำเร็จ!" in text
    assert "BUY NVDA" in text
    assert "10.0 หุ้น" in text
    assert "$125.5" in text

    # Verify inline keyboard buttons
    reply_markup = kwargs.get("reply_markup")
    assert reply_markup is not None
    assert len(reply_markup.inline_keyboard) == 1
    buttons = reply_markup.inline_keyboard[0]
    assert len(buttons) == 2
    assert buttons[0].text == "✅ ยืนยันบันทึก"
    assert buttons[0].callback_data == "slip_confirm_NVDA_BUY_125.5_10.0"
    assert buttons[1].text == "❌ ยกเลิก"
    assert buttons[1].callback_data == "slip_cancel"

    await bot_app.db.close()


@pytest.mark.asyncio
async def test_handle_photo_slip_invalid(test_config):
    bot_app = DCABot(test_config)
    await bot_app.db.create_tables()

    message = AsyncMock()
    photo_mock = MagicMock()
    photo_mock.file_id = "photo_xyz"
    message.photo = [photo_mock]
    status_msg = AsyncMock()
    message.reply.return_value = status_msg

    bot_app.bot.get_file = AsyncMock(return_value=MagicMock(file_path="photos/other.jpg"))
    bot_app.bot.download_file = AsyncMock(return_value=io.BytesIO(b"not_a_trade_slip"))

    with patch("src.bot.GeminiSlipParser") as MockParser:
        mock_parser_instance = AsyncMock()
        mock_parser_instance.parse_slip.return_value = None
        MockParser.return_value = mock_parser_instance

        await bot_app.handle_photo_slip(message)

    status_msg.edit_text.assert_called_once_with("❌ ไม่พบข้อมูลการซื้อขายหุ้น US ในรูปนี้ครับ")

    await bot_app.db.close()


@pytest.mark.asyncio
async def test_handle_slip_confirm(test_config):
    bot_app = DCABot(test_config)
    await bot_app.db.create_tables()

    # Pre-create a user
    telegram_id = 998877
    cq = AsyncMock()
    cq.data = "slip_confirm_TSLA_BUY_220.0_5.0"
    cq.from_user = MagicMock(id=telegram_id, username="investor_thai")
    cq.message = AsyncMock()

    await bot_app.handle_slip_confirm(cq)

    # Verify message edited
    cq.message.edit_text.assert_called_once_with("✅ บันทึก BUY TSLA จำนวน 5.0 หุ้น เข้าพอร์ตเรียบร้อยแล้ว!")

    # Verify DB insertion
    async with bot_app.db.session() as session:
        stmt = select(PortfolioTransaction)
        res = await session.execute(stmt)
        txns = res.scalars().all()
        assert len(txns) == 1
        txn = txns[0]
        assert txn.symbol == "TSLA"
        assert txn.action == "BUY"
        assert txn.price == 220.0
        assert txn.shares == 5.0

    await bot_app.db.close()


@pytest.mark.asyncio
async def test_handle_slip_cancel(test_config):
    bot_app = DCABot(test_config)
    await bot_app.db.create_tables()

    cq = AsyncMock()
    cq.data = "slip_cancel"
    cq.from_user = MagicMock(id=998877, username="investor_thai")
    cq.message = AsyncMock()

    await bot_app.handle_slip_cancel(cq)

    cq.message.edit_text.assert_called_once_with("❌ ยกเลิกการบันทึกสลิปครับ")

    # Verify no DB insertion
    async with bot_app.db.session() as session:
        stmt = select(PortfolioTransaction)
        res = await session.execute(stmt)
        txns = res.scalars().all()
        assert len(txns) == 0

    await bot_app.db.close()
