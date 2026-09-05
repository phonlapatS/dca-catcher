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
    sniper = AlpacaSniper(db=None)
    et_tz = ZoneInfo("America/New_York")
    
    # During market hours (10:00 ET on a Monday)
    market_open = datetime(2026, 8, 24, 10, 0, tzinfo=et_tz)  # Monday
    assert sniper.is_operating_hours(market_open) is True
    
    # After market close (17:00 ET)
    after_close = datetime(2026, 8, 24, 17, 0, tzinfo=et_tz)
    assert sniper.is_operating_hours(after_close) is False
    
    # Before market open (8:00 ET)
    before_open = datetime(2026, 8, 24, 8, 0, tzinfo=et_tz)
    assert sniper.is_operating_hours(before_open) is False
    
    # Weekend (Saturday)
    saturday = datetime(2026, 8, 22, 12, 0, tzinfo=et_tz)
    assert sniper.is_operating_hours(saturday) is False



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
    ), patch.object(sniper, "_submit_paper_order", return_value="mock_msg"):
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
        assert item.last_notified_zone == "120.0"

    # 3. Tick price stays in same zone (115.0) -> anti-spam keeps last_notified_zone unchanged
    await sniper.on_trade_tick("NVDA", 115.0)
    async with db.session() as session:
        item = await session.get(Watchlist, item_id)
        assert item.last_notified_zone == "120.0"

    # 4. Tick price drops to next zone (108.0) -> updates last_notified_zone to next zone
    await sniper.on_trade_tick("NVDA", 108.0)
    async with db.session() as session:
        item = await session.get(Watchlist, item_id)
        assert item.last_notified_zone == "110.0"


@pytest.mark.asyncio
async def test_case_insensitive_db_query_and_in_memory_filtering(db):
    async with db.session() as session:
        user = User(telegram_id=6666, username="case_user")
        session.add(user)
        await session.commit()

        # Save symbol in lowercase
        w = Watchlist(
            user_id=user.id,
            symbol="nvda",
            market="US",
            target_zones_str="120.0 (Low Risk)",
        )
        session.add(w)
        await session.commit()
        item_id = w.id

    sniper = AlpacaSniper(db=db)

    # 1. In-memory targets filtering
    sniper.targets = {"NVDA": [120.0]}

    # Tick for NVDA at 150.0 (above target 120.0) -> filtered out before DB query
    await sniper.on_trade_tick("NVDA", 150.0)
    async with db.session() as session:
        item = await session.get(Watchlist, item_id)
        assert item.last_notified_zone is None

    # Tick for NVDA at 115.0 (below target 120.0) -> matches lowercase "nvda" in DB
    await sniper.on_trade_tick("NVDA", 115.0)
    async with db.session() as session:
        item = await session.get(Watchlist, item_id)
        assert item.last_notified_zone == "120.0"


def test_parse_target_zones_descending_sort():
    sniper = AlpacaSniper(db=None)
    assert sniper.parse_target_zones("110.0, 120.0, 105.0") == [120.0, 110.0, 105.0]


