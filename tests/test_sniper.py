import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
import websockets

import pytest_asyncio
from src.config import Config
from src.database import Database, Watchlist, User
from src.sniper import AlpacaSniper


@pytest_asyncio.fixture
async def db(tmp_path):
    db_path = tmp_path / "test_sniper.db"
    db_obj = Database(f"sqlite+aiosqlite:///{db_path}")
    await db_obj.create_tables()
    yield db_obj
    await db_obj.close()


def test_is_operating_hours():
    bkk_tz = ZoneInfo("Asia/Bangkok")
    sniper = AlpacaSniper(db=None)

    # 20:30 BKK -> inside
    t1 = datetime(2026, 8, 7, 20, 30, 0, tzinfo=bkk_tz)
    assert sniper.is_operating_hours(t1) is True

    # 23:59 BKK -> inside
    t2 = datetime(2026, 8, 7, 23, 59, 59, tzinfo=bkk_tz)
    assert sniper.is_operating_hours(t2) is True

    # 00:00 BKK -> inside
    t3 = datetime(2026, 8, 8, 0, 0, 0, tzinfo=bkk_tz)
    assert sniper.is_operating_hours(t3) is True

    # 03:59 BKK -> inside
    t4 = datetime(2026, 8, 8, 3, 59, 59, tzinfo=bkk_tz)
    assert sniper.is_operating_hours(t4) is True

    # 04:00 BKK -> outside
    t5 = datetime(2026, 8, 8, 4, 0, 0, tzinfo=bkk_tz)
    assert sniper.is_operating_hours(t5) is False

    # 12:00 BKK -> outside
    t6 = datetime(2026, 8, 7, 12, 0, 0, tzinfo=bkk_tz)
    assert sniper.is_operating_hours(t6) is False

    # 20:29 BKK -> outside
    t7 = datetime(2026, 8, 7, 20, 29, 59, tzinfo=bkk_tz)
    assert sniper.is_operating_hours(t7) is False


def test_parse_target_zones():
    sniper = AlpacaSniper(db=None)

    assert sniper.parse_target_zones("150.0 (Low Risk), 140.0 (Moderate)") == [150.0, 140.0]
    assert sniper.parse_target_zones("150.5 (User Target)") == [150.5]
    assert sniper.parse_target_zones("100.0, 95.25") == [100.0, 95.25]
    assert sniper.parse_target_zones("") == []
    assert sniper.parse_target_zones(None) == []


@pytest.mark.asyncio
async def test_load_us_targets(db):
    async with db.session() as session:
        user = User(telegram_id=9999, username="test_sniper_user")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        w1 = Watchlist(
            user_id=user.id,
            symbol="NVDA",
            market="US",
            target_zones_str="120.0 (Low Risk), 110.0 (Moderate)",
        )
        w2 = Watchlist(
            user_id=user.id,
            symbol="AAPL",
            market="US",
            target_zones_str="180.0 (User Target)",
        )
        w3 = Watchlist(
            user_id=user.id,
            symbol="PTT.BK",
            market="TH",
            target_zones_str="30.0",
        )
        session.add_all([w1, w2, w3])
        await session.commit()

    sniper = AlpacaSniper(db=db)
    targets = await sniper.load_us_targets()

    assert "NVDA" in targets
    assert targets["NVDA"] == [120.0, 110.0]
    assert "AAPL" in targets
    assert targets["AAPL"] == [180.0]
    assert "PTT.BK" not in targets


@pytest.mark.asyncio
async def test_handle_message():
    received_ticks = []

    async def mock_callback(symbol: str, price: float):
        received_ticks.append((symbol, price))

    sniper = AlpacaSniper(db=None, on_tick_callback=mock_callback)

    sample_msg = json.dumps([
        {"T": "t", "S": "AAPL", "p": 150.25},
        {"T": "t", "S": "NVDA", "p": 125.50},
        {"T": "q", "S": "AAPL", "bp": 150.20, "ap": 150.30},  # Quote should be ignored
    ])

    await sniper.handle_message(sample_msg)

    assert len(received_ticks) == 2
    assert received_ticks[0] == ("AAPL", 150.25)
    assert received_ticks[1] == ("NVDA", 125.50)


@pytest.mark.asyncio
async def test_sniper_connect_auth_subscribe_loop(db):
    async with db.session() as session:
        user = User(telegram_id=8888, username="sniper_user_2")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        w1 = Watchlist(
            user_id=user.id,
            symbol="AAPL",
            market="US",
            target_zones_str="150.0",
        )
        session.add(w1)
        await session.commit()

    ticks = []

    async def tick_cb(symbol, price):
        ticks.append((symbol, price))

    sniper = AlpacaSniper(
        db=db,
        api_key="TEST_API_KEY",
        secret_key="TEST_SECRET_KEY",
        poll_interval=0.1,
        on_tick_callback=tick_cb,
    )

    mock_ws = AsyncMock()
    # Mock sequence of incoming ws messages:
    # 1. Greeting
    # 2. Auth response
    # 3. Sub response
    # 4. Trade tick
    mock_ws.recv.side_effect = [
        json.dumps([{"T": "success", "msg": "connected"}]),
        json.dumps([{"T": "success", "msg": "authenticated"}]),
        json.dumps([{"T": "subscription", "trades": ["AAPL"]}]),
        json.dumps([{"T": "t", "S": "AAPL", "p": 149.0}]),
        asyncio.CancelledError(),  # to exit listen loop cleanly
    ]

    with patch("websockets.connect") as mock_connect, patch.object(
        sniper, "is_operating_hours", return_value=True
    ):
        mock_connect.return_value.__aenter__.return_value = mock_ws

        await sniper.start()
        await asyncio.sleep(0.3)
        await sniper.stop()

    assert ("AAPL", 149.0) in ticks
    # Verify auth payload sent
    auth_sent = json.loads(mock_ws.send.call_args_list[0][0][0])
    assert auth_sent["action"] == "auth"
    assert auth_sent["key"] == "TEST_API_KEY"

    # Verify sub payload sent
    sub_sent = json.loads(mock_ws.send.call_args_list[1][0][0])
    assert sub_sent["action"] == "subscribe"
    assert sub_sent["trades"] == ["AAPL"]


@pytest.mark.asyncio
async def test_check_target_triggers_and_anti_spam_db_update(db):
    async with db.session() as session:
        user = User(telegram_id=7777, username="trigger_user")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        w1 = Watchlist(
            user_id=user.id,
            symbol="NVDA",
            market="US",
            target_zones_str="120.0 (Low Risk), 110.0 (Moderate)",
            last_notified_zone=None,
        )
        session.add(w1)
        await session.commit()
        item_id = w1.id

    sniper = AlpacaSniper(db=db)

    # 1. Tick price above targets (125.0) -> no DB update
    await sniper.on_trade_tick("NVDA", 125.0)
    async with db.session() as session:
        item = await session.get(Watchlist, item_id)
        assert item.last_notified_zone is None

    # 2. Tick price drops <= target 120.0 (118.0) -> updates last_notified_zone
    await sniper.on_trade_tick("NVDA", 118.0)
    async with db.session() as session:
        item = await session.get(Watchlist, item_id)
        assert item.last_notified_zone == "120.0 (Low Risk)"

    # 3. Tick price stays in same zone (115.0) -> anti-spam keeps last_notified_zone unchanged
    await sniper.on_trade_tick("NVDA", 115.0)
    async with db.session() as session:
        item = await session.get(Watchlist, item_id)
        assert item.last_notified_zone == "120.0 (Low Risk)"

    # 4. Tick price drops to next zone (108.0) -> updates last_notified_zone to next zone
    await sniper.on_trade_tick("NVDA", 108.0)
    async with db.session() as session:
        item = await session.get(Watchlist, item_id)
        assert item.last_notified_zone == "110.0 (Moderate)"

