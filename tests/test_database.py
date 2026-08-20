from datetime import datetime
import pytest
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import Base, Database, Signal, User, Watchlist


@pytest.mark.asyncio
async def test_engine_creation():
    db = Database("sqlite+aiosqlite:///:memory:")
    assert db.engine is not None
    await db.create_tables()
    await db.close()


@pytest.mark.asyncio
async def test_models_and_session():
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.create_tables()

    async with db.session() as session:
        # Test large 64-bit Telegram ID
        big_telegram_id = 9876543210123
        user = User(telegram_id=big_telegram_id, username="testuser")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        assert user.id is not None
        assert user.telegram_id == big_telegram_id
        assert user.username == "testuser"

        watchlist = Watchlist(user_id=user.id, symbol="AAPL", market="US")
        session.add(watchlist)

        signal = Signal(symbol="AAPL", grade=4, confidence=90, advice="Buy now")
        session.add(signal)

        await session.commit()

        # Query back
        res_watchlist = await session.execute(
            select(Watchlist).where(Watchlist.symbol == "AAPL")
        )
        fetched_watchlist = res_watchlist.scalar_one()
        assert fetched_watchlist.user_id == user.id

        res_signal = await session.execute(
            select(Signal).where(Signal.symbol == "AAPL")
        )
        fetched_signal = res_signal.scalar_one()
        assert fetched_signal.grade == 4
        assert fetched_signal.confidence == 90
        assert fetched_signal.created_at is not None

    await db.close()


def test_watchlist_foreign_key():
    fk_list = list(Watchlist.__table__.foreign_keys)
    assert len(fk_list) == 1
    fk = fk_list[0]
    assert fk.target_fullname == "users.id"


def test_requirements_contains_asyncpg():
    with open("requirements.txt") as f:
        content = f.read()
    assert "asyncpg" in content


import pytest_asyncio


@pytest_asyncio.fixture
async def db():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_tables()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_get_unique_watchlist_symbols(db):
    async with db.session() as session:
        u1 = User(telegram_id=1, username="u1")
        u2 = User(telegram_id=2, username="u2")
        session.add_all([u1, u2])
        await session.commit()

        session.add_all(
            [
                Watchlist(user_id=u1.id, symbol="AAPL", market="US"),
                Watchlist(user_id=u1.id, symbol="NVDA", market="US"),
                Watchlist(user_id=u2.id, symbol="AAPL", market="US"),
                Watchlist(user_id=u2.id, symbol="PTT.BK", market="TH"),
            ]
        )
        await session.commit()

    symbols = await db.get_unique_watchlist_symbols()
    assert sorted(symbols) == ["AAPL", "NVDA", "PTT.BK"]

    th_symbols = await db.get_unique_watchlist_symbols(market="TH")
    assert th_symbols == ["PTT.BK"]


@pytest.mark.asyncio
async def test_seen_catalysts_deduplication(db):
    hash1 = "hash_123456"
    assert await db.is_catalyst_seen(hash1) is False

    # Record first time
    recorded = await db.record_seen_catalyst(
        headline_hash=hash1,
        symbol="MRNA",
        headline="Moderna Phase 3 Melanoma Success",
        publisher="Business Wire"
    )
    assert recorded is True
    assert await db.is_catalyst_seen(hash1) is True

    # Try recording duplicate hash
    recorded_again = await db.record_seen_catalyst(
        headline_hash=hash1,
        symbol="MRNA",
        headline="Duplicate Moderna Headline",
        publisher="Reuters"
    )
    assert recorded_again is False


