import pytest
import asyncio
from sqlalchemy import select
from src.alert_manager import AlertManager
from src.database import Database, Watchlist, User

import pytest_asyncio

@pytest_asyncio.fixture
async def db():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_tables()
    yield database
    await database.close()

@pytest.mark.asyncio
async def test_hysteresis_logic(db):
    # Setup user and watchlist
    async with db.session() as session:
        user = User(telegram_id=123, username="test")
        session.add(user)
        await session.commit()
        item = Watchlist(user_id=user.id, symbol="AAPL", market="US")
        session.add(item)
        await session.commit()

    manager = AlertManager(db)
    
    # Target zones string could be "150.0 (Low Risk), 140.0 (Moderate), 130.0 (Risky)"
    target_zones_str = "150.0 (Low Risk), 140.0 (Moderate), 130.0 (Risky)"
    
    # Price is above all zones -> no alert
    alerted, msg = await manager.check_and_notify(
        user_id=123, symbol="AAPL", current_price=160.0, target_zones_str=target_zones_str
    )
    assert not alerted
    
    # Price hits first zone -> alert
    alerted, msg = await manager.check_and_notify(
        user_id=123, symbol="AAPL", current_price=150.0, target_zones_str=target_zones_str
    )
    assert alerted
    assert "ท่านสามารถเข้าซื้อที่ราคาเป้าหมายตอนนี้ได้แล้ว 150.0 (Low Risk)" in msg
    assert "140.0 (Moderate)" in msg
    
    # Price stays in zone -> no alert (hysteresis)
    alerted, msg = await manager.check_and_notify(
        user_id=123, symbol="AAPL", current_price=149.0, target_zones_str=target_zones_str
    )
    assert not alerted

    # Price drops to next zone -> alert
    alerted, msg = await manager.check_and_notify(
        user_id=123, symbol="AAPL", current_price=140.0, target_zones_str=target_zones_str
    )
    assert alerted
    assert "ท่านสามารถเข้าซื้อที่ราคาเป้าหมายตอนนี้ได้แล้ว 140.0 (Moderate)" in msg
    assert "130.0 (Risky)" in msg


@pytest.mark.asyncio
async def test_multiple_watchlist_entries_no_crash(db):
    # Setup user with duplicate watchlist items for same symbol
    async with db.session() as session:
        user = User(telegram_id=456, username="multi_test")
        session.add(user)
        await session.commit()
        item1 = Watchlist(user_id=user.id, symbol="NVDA", market="US")
        item2 = Watchlist(user_id=user.id, symbol="NVDA", market="US")
        session.add_all([item1, item2])
        await session.commit()

    manager = AlertManager(db)
    target_zones_str = "120.0 (Low Risk)"

    # Should not raise MultipleResultsFound
    alerted, msg = await manager.check_and_notify(
        user_id=456, symbol="NVDA", current_price=115.0, target_zones_str=target_zones_str
    )
    assert alerted
    assert "120.0" in msg


