import pytest
from src.database import Database, User
from src.memory import MemoryManager


@pytest.mark.asyncio
async def test_memory_cold_start():
    """Test that cold start returns empty list and clean notice."""
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.create_tables()

    async with db.session() as session:
        user = User(telegram_id=111111, username="user_one")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        timeline = await MemoryManager.get_recent_timeline(session, user_id=user.id, symbol="NVDA")
        assert timeline == []
        prompt_str = MemoryManager.format_timeline_prompt(timeline)
        assert "Cold Start" in prompt_str

    await db.close()


@pytest.mark.asyncio
async def test_memory_save_and_retrieve_2plus1():
    """Test saving multiple snapshots and retrieving them chronologically."""
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.create_tables()

    async with db.session() as session:
        user = User(telegram_id=111111, username="user_one")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Save T-2 snapshot
        mem1 = await MemoryManager.save_memory_snapshot(
            session=session,
            user_id=user.id,
            symbol="NVDA",
            price=235.0,
            target_prices_str="215.0, 200.0, 185.0",
            thesis_status="CONTINUING",
            thesis_summary="งบ Data Center โตแกร่ง",
            calibrated_confidence=90
        )
        assert mem1 is not None

        # Save T-1 snapshot
        mem2 = await MemoryManager.save_memory_snapshot(
            session=session,
            user_id=user.id,
            symbol="NVDA",
            price=222.0,
            target_prices_str="215.0, 200.0, 185.0",
            thesis_status="CONTINUING",
            thesis_summary="ย่อตัวตามตลาดกังวลส่งออก",
            calibrated_confidence=85
        )
        assert mem2 is not None

        # Retrieve timeline (limit=2)
        timeline = await MemoryManager.get_recent_timeline(session, user_id=user.id, symbol="NVDA", limit=2)
        assert len(timeline) == 2
        # Check chronological ordering: T-2 (235.0) first, then T-1 (222.0)
        assert timeline[0].price == 235.0
        assert timeline[1].price == 222.0

        prompt_str = MemoryManager.format_timeline_prompt(timeline)
        assert "T-2" in prompt_str
        assert "T-1" in prompt_str
        assert "$235.00" in prompt_str
        assert "$222.00" in prompt_str
        assert "งบ Data Center โตแกร่ง" in prompt_str

    await db.close()


@pytest.mark.asyncio
async def test_memory_user_isolation():
    """Ensure User 1's memory is isolated from User 2."""
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.create_tables()

    async with db.session() as session:
        u1 = User(telegram_id=111111, username="u1")
        u2 = User(telegram_id=222222, username="u2")
        session.add_all([u1, u2])
        await session.commit()
        await session.refresh(u1)
        await session.refresh(u2)

        await MemoryManager.save_memory_snapshot(
            session=session,
            user_id=u1.id,
            symbol="TSLA",
            price=300.0,
            thesis_summary="User 1 analysis"
        )

        # User 2 queries TSLA -> must be empty
        u2_timeline = await MemoryManager.get_recent_timeline(session, user_id=u2.id, symbol="TSLA")
        assert u2_timeline == []

        # User 1 queries TSLA -> must find 1
        u1_timeline = await MemoryManager.get_recent_timeline(session, user_id=u1.id, symbol="TSLA")
        assert len(u1_timeline) == 1
        assert u1_timeline[0].price == 300.0

    await db.close()
