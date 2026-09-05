import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from src.catalyst.models import CatalystArticle, CatalystVerdict, ConnectedAsset
from src.catalyst.evaluator import CatalystEvaluator

SAMPLE_ARTICLE = CatalystArticle(
    headline="Moderna reports Phase 3 melanoma trial success with Merck",
    headline_hash="hash_123",
    symbol="MRNA",
    publisher="Business Wire",
    published_at=datetime.utcnow(),
    raw_snippet="Topline results show 44% reduction in recurrence risk."
)

SAMPLE_LLM_JSON = """{
  "is_material": true,
  "materiality_score": 9.5,
  "confidence_score": 95.0,
  "scope": "MICRO",
  "sentiment": "POSITIVE",
  "impact_summary": "ผลกระทบเชิงบวกต่อรายได้ในอนาคต",
  "event_category": "CLINICAL_TRIAL",
  "bull_catalysts": "ปลดล็อก New S-Curve รายได้ประจำ 3-5 ปีข้างหน้า",
  "bear_risks": "ต้องรอการยื่นขออนุมัติจาก FDA และระวังราคาเปิดกระโดด",
  "dca_guidance": "แนะนำรอราคาพักตัวเข้าสู่แนวรับสะสมไม้ 1 ที่ $61.50",
  "thai_summary": "Moderna แถลงผลการทดลองเฟส 3 วัคซีนมะเร็งผิวหนังผ่านเป้าหมายหลัก",
  "connected_stocks": [
    {
      "symbol": "MRK",
      "relationship": "CUSTOMER",
      "impact_direction": "POSITIVE",
      "rationale_thai": "พันธมิตรร่วมพัฒนา Keytruda + mRNA-4157"
    },
    {
      "symbol": "BNTX",
      "relationship": "SYMPATHY_PEER",
      "impact_direction": "POSITIVE",
      "rationale_thai": "คู่แข่งในกลุ่มเทคโนโลยี mRNA ได้รับอานิสงส์ความเชื่อมั่นตามกลุ่ม"
    }
  ]
}"""

@pytest.mark.asyncio
async def test_catalyst_evaluator_success():
    evaluator = CatalystEvaluator(api_keys=["mock_key"])
    with patch.object(evaluator, "_call_gemini", return_value=SAMPLE_LLM_JSON):
        verdict = await evaluator.evaluate_catalyst(SAMPLE_ARTICLE)
        assert verdict.is_material is True
        assert verdict.materiality_score == 9.5
        assert verdict.event_category == "CLINICAL_TRIAL"
        assert "ปลดล็อก" in verdict.bull_catalysts
        assert "FDA" in verdict.bear_risks
        assert len(verdict.connected_stocks) == 2
        assert verdict.connected_stocks[0].symbol == "MRK"
        assert verdict.connected_stocks[1].symbol == "BNTX"

@pytest.mark.asyncio
async def test_catalyst_evaluator_fallback_on_error():
    evaluator = CatalystEvaluator(api_keys=["mock_key"])
    with patch.object(evaluator, "_call_gemini", side_effect=Exception("API Error")):
        verdict = await evaluator.evaluate_catalyst(SAMPLE_ARTICLE)
        assert verdict.is_material is False
        assert verdict.materiality_score == 1.0
        assert "เกิดข้อผิดพลาด" in verdict.thai_summary
        assert verdict.connected_stocks == []
