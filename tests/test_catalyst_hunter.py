import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.database import Database
from src.catalyst.models import CatalystArticle, CatalystVerdict, ConnectedAsset
from src.catalyst.hunter import CatalystHunter

SAMPLE_ARTICLE = CatalystArticle(
    headline="Moderna Reports Positive Phase 3 Trial Results - Business Wire",
    headline_hash="hash_mrna_1",
    symbol="MRNA",
    publisher="Business Wire",
    published_at=datetime.utcnow(),
    raw_snippet="Topline results show 44% reduction in recurrence risk."
)

SAMPLE_VERDICT_TIER_S = CatalystVerdict(
    is_material=True,
    materiality_score=9.5,
    event_category="CLINICAL_TRIAL",
    bull_catalysts="ปลดล็อก New S-Curve",
    bear_risks="รอ FDA อนุมัติ",
    dca_guidance="รอรับไม้ 1 ที่แนวรับ $61.50",
    thai_summary="Moderna แถลงผลการทดลองเฟส 3 วัคซีนมะเร็งผิวหนังผ่านเป้าหมายหลัก",
    confidence_score=90,
    scope="MICRO",
    impact_summary="TEST",
    sentiment="POSITIVE",
    connected_stocks=[
        ConnectedAsset(
            symbol="MRK",
            relationship="CUSTOMER",
            impact_direction="POSITIVE",
            rationale_thai="พันธมิตรร่วมพัฒนา Keytruda"
        )
    ]
)

@pytest_asyncio.fixture
async def db():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_tables()
    yield database
    await database.close()

@pytest.mark.asyncio
async def test_catalyst_hunter_pipeline_flow(db):
    bot_mock = AsyncMock()
    hunter = CatalystHunter(db=db, bot=bot_mock, channel_id="@test_channel", gemini_api_key="mock_key")

    # Mock provider returning SAMPLE_ARTICLE
    hunter.providers[0].fetch_articles_for_symbol = AsyncMock(return_value=[SAMPLE_ARTICLE])
    # Mock evaluator returning Tier S verdict
    hunter.evaluator.evaluate_catalyst = AsyncMock(return_value=SAMPLE_VERDICT_TIER_S)

    # Run one scan cycle
    processed_count = await hunter.run_scan_cycle(symbols=["MRNA"])
    assert processed_count == 1

    # Verify DB recorded the hash
    assert await db.is_catalyst_seen(SAMPLE_ARTICLE.headline_hash) is True

    # Verify bot sent message to channel
    assert bot_mock.send_message.called
    call_kwargs = bot_mock.send_message.call_args[1]
    assert call_kwargs["chat_id"] == "@test_channel"
    assert "BREAKING CATALYST: #MRNA" in call_kwargs["text"]
    assert "$MRK" in call_kwargs["text"]
    assert call_kwargs["reply_markup"] is not None

@pytest.mark.asyncio
async def test_catalyst_hunter_skips_seen_article(db):
    bot_mock = AsyncMock()
    hunter = CatalystHunter(db=db, bot=bot_mock, channel_id="@test_channel", gemini_api_key="mock_key")

    # Pre-record the hash
    await db.record_seen_catalyst(
        headline_hash=SAMPLE_ARTICLE.headline_hash,
        symbol="MRNA",
        headline=SAMPLE_ARTICLE.headline
    )

    hunter.providers[0].fetch_articles_for_symbol = AsyncMock(return_value=[SAMPLE_ARTICLE])
    hunter.evaluator.evaluate_catalyst = AsyncMock()

    processed_count = await hunter.run_scan_cycle(symbols=["MRNA"])
    assert processed_count == 0
    # Evaluator should not be called (0 Token used)
    assert not hunter.evaluator.evaluate_catalyst.called
    assert not bot_mock.send_message.called


@pytest.mark.asyncio
async def test_catalyst_hunter_tier_a_batching_and_digest(db):
    bot_mock = AsyncMock()
    hunter = CatalystHunter(db=db, bot=bot_mock, channel_id="@test_channel", gemini_api_key="mock_key")

    article_tier_a = CatalystArticle(
        headline="Apple signs minor supplier contract for sensors",
        headline_hash="hash_aapl_a",
        symbol="AAPL",
        publisher="Reuters",
        published_at=datetime.utcnow(),
        raw_snippet="Supply chain agreement for next-gen sensors."
    )
    verdict_tier_a = CatalystVerdict(
        is_material=True,
        materiality_score=7.8, # Tier A (7.5 - 8.9) -> Batched to 19:00 Digest
        event_category="CONTRACT",
        bull_catalysts="ขยายห่วงโซ่อุปทาน",
        bear_risks="มาร์จิ้นต่ำ",
        dca_guidance="สะสมตามรอบปกติ",
        thai_summary="Apple ลงนามสัญญาจัดซื้อเซนเซอร์รุ่นใหม่",
        connected_stocks=[]
    )

    hunter.providers[0].fetch_articles_for_symbol = AsyncMock(return_value=[article_tier_a])
    hunter.evaluator.evaluate_catalyst = AsyncMock(return_value=verdict_tier_a)

    # 1. Scan cycle: should not send instant message, but put into digest queue
    processed_count = await hunter.run_scan_cycle(symbols=["AAPL"])
    assert processed_count == 1
    assert not bot_mock.send_message.called
    assert len(hunter.digest_queue) == 1

    # 2. Trigger daily digest at 19:00
    sent_count = await hunter.send_daily_digest()
    assert sent_count == 1
    assert bot_mock.send_message.called
    call_kwargs = bot_mock.send_message.call_args[1]
    assert "PRE-MARKET CATALYST DAILY DIGEST" in call_kwargs["text"]
    assert "$AAPL" in call_kwargs["text"]
    assert len(hunter.digest_queue) == 0

