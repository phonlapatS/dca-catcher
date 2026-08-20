import pytest
from datetime import datetime
from pydantic import ValidationError
from src.catalyst.models import CatalystArticle, CatalystVerdict, ConnectedAsset

def test_catalyst_article_valid():
    article = CatalystArticle(
        headline="Moderna reports Phase 3 melanoma trial success",
        headline_hash="a"*64,
        symbol="MRNA",
        publisher="Business Wire",
        published_at=datetime.utcnow(),
        raw_snippet="Topline results show 44% reduction in recurrence risk.",
        premarket_price=65.20,
        premarket_volume_ratio=5.1,
        bid_ask_spread_pct=0.45
    )
    assert article.symbol == "MRNA"
    assert article.premarket_price == 65.20
    assert article.premarket_volume_ratio == 5.1
    assert article.bid_ask_spread_pct == 0.45

def test_catalyst_article_defaults():
    article = CatalystArticle(
        headline="Some headline",
        headline_hash="b"*64,
        symbol="NVDA",
        publisher="Reuters",
        published_at=datetime.utcnow(),
        raw_snippet="Snippet text"
    )
    assert article.premarket_price is None
    assert article.premarket_volume_ratio is None
    assert article.bid_ask_spread_pct is None

def test_connected_asset_valid():
    asset = ConnectedAsset(
        symbol="MRK",
        relationship="CUSTOMER",
        impact_direction="POSITIVE",
        rationale_thai="พันธมิตรร่วมพัฒนา Keytruda"
    )
    assert asset.symbol == "MRK"
    assert asset.impact_direction == "POSITIVE"

def test_catalyst_verdict_valid():
    verdict = CatalystVerdict(
        is_material=True,
        materiality_score=9.5,
        event_category="CLINICAL_TRIAL",
        bull_catalysts="ปลดล็อก New S-Curve",
        bear_risks="รอ FDA อนุมัติ",
        dca_guidance="รอรับไม้ 1 ที่แนวรับ $61.50",
        thai_summary="ผลทดลองเฟส 3 ผ่านเป้าหมาย",
        connected_stocks=[
            ConnectedAsset(
                symbol="MRK",
                relationship="CUSTOMER",
                impact_direction="POSITIVE",
                rationale_thai="พันธมิตรร่วมพัฒนา"
            )
        ]
    )
    assert verdict.is_material is True
    assert verdict.materiality_score == 9.5
    assert len(verdict.connected_stocks) == 1
    assert verdict.connected_stocks[0].symbol == "MRK"

def test_catalyst_verdict_validation_error():
    with pytest.raises(ValidationError):
        # Missing required fields
        CatalystVerdict(is_material=True)
