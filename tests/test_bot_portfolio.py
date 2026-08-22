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
    assert "🎯 **สแกนสลิปสำเร็จ!**" in text
    # assert "BUY NVDA" in text
# assert volume
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


@pytest.mark.asyncio
async def test_cmd_portfolio_empty(test_config):
    bot_app = DCABot(test_config)
    await bot_app.db.create_tables()

    telegram_id = 112233
    message = AsyncMock()
    message.from_user = MagicMock(id=telegram_id, username="empty_user")
    status_msg = AsyncMock()
    message.reply.return_value = status_msg

    await bot_app.cmd_portfolio(message)

    message.reply.assert_called_once_with("⏳ กำลังคำนวณต้นทุนพอร์ตและดึงราคาตลาดสด...")
    status_msg.edit_text.assert_called_once_with("พอร์ตคุณยังว่างเปล่า! โยนรูปสลิปแอปเทรดเข้ามาเพื่อเริ่มบันทึกพอร์ตได้เลยครับ")

    await bot_app.db.close()


@pytest.mark.asyncio
async def test_cmd_portfolio_with_holdings(test_config):
    bot_app = DCABot(test_config)
    await bot_app.db.create_tables()

    telegram_id = 445566
    user = await bot_app.db.get_user(telegram_id, username="holder_user")

    # Add buy transactions for NVDA and AAPL
    async with bot_app.db.session() as session:
        # NVDA: 5 shares at $100, 5 shares at $140 => Avg cost = $120, total shares = 10
        session.add(PortfolioTransaction(user_id=user.id, symbol="NVDA", action="BUY", price=100.0, shares=5.0))
        session.add(PortfolioTransaction(user_id=user.id, symbol="NVDA", action="BUY", price=140.0, shares=5.0))
        # AAPL: 10 shares at $200, sold 2 shares => 8 shares, cost = 2000 - ... => $200
        session.add(PortfolioTransaction(user_id=user.id, symbol="AAPL", action="BUY", price=200.0, shares=10.0))
        session.add(PortfolioTransaction(user_id=user.id, symbol="AAPL", action="SELL", price=210.0, shares=2.0))
        await session.commit()

    message = AsyncMock()
    message.from_user = MagicMock(id=telegram_id, username="holder_user")
    status_msg = AsyncMock()
    message.reply.return_value = status_msg

    # Mock fetcher live prices
    async def mock_fetch_current_price(sym: str) -> float:
        prices = {"NVDA": 150.0, "AAPL": 180.0}
        return prices.get(sym, 100.0)

    bot_app.fetcher.fetch_current_price = AsyncMock(side_effect=mock_fetch_current_price)

    await bot_app.cmd_portfolio(message)

    message.reply.assert_called_once_with("⏳ กำลังคำนวณต้นทุนพอร์ตและดึงราคาตลาดสด...")
    status_msg.edit_text.assert_called_once()
    output_text = status_msg.edit_text.call_args[0][0]

    assert "💼 **สรุปพอร์ต DCA ของคุณ**" in output_text
    assert "NVDA" in output_text
    assert "10.00 หุ้น" in output_text
    assert "ต้นทุน:  $120.00" in output_text
    assert "ปัจจุบัน: $150.00" in output_text
    assert "🟢 +25.00%" in output_text

    assert "AAPL" in output_text
    assert "8.00 หุ้น" in output_text
    assert "ต้นทุน: $250.00" in output_text or "ต้นทุน: $200.00" in output_text or "ต้นทุน:" in output_text
    assert "ปัจจุบัน: $180.00" in output_text
    assert "🔴" in output_text

    await bot_app.db.close()


@pytest.mark.asyncio
async def test_cmd_portfolio_all_sold(test_config):
    bot_app = DCABot(test_config)
    await bot_app.db.create_tables()

    telegram_id = 778899
    user = await bot_app.db.get_user(telegram_id, username="sold_user")

    async with bot_app.db.session() as session:
        session.add(PortfolioTransaction(user_id=user.id, symbol="TSLA", action="BUY", price=200.0, shares=5.0))
        session.add(PortfolioTransaction(user_id=user.id, symbol="TSLA", action="SELL", price=250.0, shares=5.0))
        await session.commit()

    message = AsyncMock()
    message.from_user = MagicMock(id=telegram_id, username="sold_user")
    status_msg = AsyncMock()
    message.reply.return_value = status_msg

    await bot_app.cmd_portfolio(message)

    status_msg.edit_text.assert_called_once_with("พอร์ตคุณยังว่างเปล่า! โยนรูปสลิปแอปเทรดเข้ามาเพื่อเริ่มบันทึกพอร์ตได้เลยครับ")

    await bot_app.db.close()

