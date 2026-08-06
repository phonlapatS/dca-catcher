from datetime import datetime
import pytest
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import Base, Signal, User, Watchlist, get_engine, get_session_maker


@pytest.mark.asyncio
async def test_engine_creation():
    engine = get_engine("sqlite+aiosqlite:///:memory:")
    assert engine is not None
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.mark.asyncio
async def test_models_and_session():
    engine = get_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = get_session_maker(engine)
    async with session_factory() as session:
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


def test_watchlist_foreign_key():
    fk_list = list(Watchlist.__table__.foreign_keys)
    assert len(fk_list) == 1
    fk = fk_list[0]
    assert fk.target_fullname == "users.id"


def test_requirements_contains_asyncpg():
    with open("requirements.txt") as f:
        content = f.read()
    assert "asyncpg" in content
