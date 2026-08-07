import json
from unittest.mock import MagicMock, patch
import pytest

from src.fetcher import StockSnapshot
from src.transform import DimensionScore, EnrichedSignal
from src.grader import GradeResult, SignalGrader


@pytest.fixture
def sample_enriched_signal():
    snapshot = StockSnapshot(
        symbol="AAPL",
        current_price=150.0,
        volume=1000000,
        ath_price=200.0,
        drawdown_pct=-25.0,
    )
    dimensions = {
        "PRICE": DimensionScore(
            label="BUY",
            score=70.0,
            reason="Significant pullback from ATH",
        ),
        "FLOW": DimensionScore(
            label="HOLD",
            score=50.0,
            reason="Volume analysis placeholder",
        ),
        "CONTEXT": DimensionScore(
            label="HOLD",
            score=50.0,
            reason="Context analysis placeholder",
        ),
    }
    return EnrichedSignal(
        symbol="AAPL",
        snapshot=snapshot,
        dimensions=dimensions,
    )


def test_build_prompt(sample_enriched_signal):
    grader = SignalGrader(api_key="fake-key")
    prompt = grader._build_prompt(sample_enriched_signal)

    assert "AAPL" in prompt
    assert "PRICE" in prompt
    assert "FLOW" in prompt
    assert "CONTEXT" in prompt
    assert "BUY" in prompt
    assert "Significant pullback from ATH" in prompt


def test_parse_response_valid_json():
    grader = SignalGrader(api_key="fake-key")
    raw_json = json.dumps({
        "score": 4,
        "confidence": 85,
        "advice": "ราคาย่อตัวลงมาน่าสนใจ DCA เพิ่มเติม",
        "reasons": ["✅ Drawdown > 20%", "🟡 Flow hold"],
    })

    res = grader._parse_response(raw_json, "AAPL")
    assert isinstance(res, GradeResult)
    assert res.symbol == "AAPL"
    assert res.score == 4
    assert res.confidence == 85
    assert res.advice == "ราคาย่อตัวลงมาน่าสนใจ DCA เพิ่มเติม"
    assert res.reasons == ["✅ Drawdown > 20%", "🟡 Flow hold"]


def test_parse_response_markdown_fence():
    grader = SignalGrader(api_key="fake-key")
    fence_json = """```json
{
    "score": 3,
    "confidence": 75,
    "advice": "สภาวะตลาดปานกลาง",
    "reasons": ["✅ PRICE: BUY"]
}
```"""

    res = grader._parse_response(fence_json, "AAPL")
    assert isinstance(res, GradeResult)
    assert res.symbol == "AAPL"
    assert res.score == 3
    assert res.confidence == 75
    assert res.advice == "สภาวะตลาดปานกลาง"
    assert res.reasons == ["✅ PRICE: BUY"]


def test_parse_response_invalid_json_fallback():
    grader = SignalGrader(api_key="fake-key")
    invalid_text = "Sorry, I cannot process this request."

    res = grader._parse_response(invalid_text, "AAPL")
    assert isinstance(res, GradeResult)
    assert res.symbol == "AAPL"
    assert res.score == 5
    assert res.confidence == 0
    assert "Failed to parse" in res.advice or "Parse error" in res.advice or "error" in res.advice.lower()


@patch("src.grader.genai.Client")
def test_grade_happy_path(mock_client_cls, sample_enriched_signal):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "score": 4,
        "confidence": 90,
        "advice": "แนะนำทยอยสะสม DCA",
        "reasons": ["✅ Drawdown 25%", "✅ ATH Drawdown Signal"],
    })
    mock_client.models.generate_content.return_value = mock_response

    grader = SignalGrader(api_key="fake-key")
    res = grader.grade(sample_enriched_signal)

    assert isinstance(res, GradeResult)
    assert res.symbol == "AAPL"
    assert res.score == 4
    assert res.confidence == 90
    assert res.advice == "แนะนำทยอยสะสม DCA"
    assert res.reasons == ["✅ Drawdown 25%", "✅ ATH Drawdown Signal"]
    mock_client.models.generate_content.assert_called_once()


@patch("src.grader.genai.Client")
def test_grade_api_failure_fallback(mock_client_cls, sample_enriched_signal):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.side_effect = Exception("API rate limit exceeded")

    grader = SignalGrader(api_key="fake-key")
    res = grader.grade(sample_enriched_signal)

    assert isinstance(res, GradeResult)
    assert res.symbol == "AAPL"
    assert res.score == 5
    assert res.confidence == 0
    assert "API error" in res.advice or "error" in res.advice.lower()

def test_build_prompt_with_news_and_indicators(sample_enriched_signal):
    grader = SignalGrader(api_key="fake-key")
    news = ["AAPL launches new iPhone", "Tech stocks rally"]
    sample_enriched_signal.snapshot.rsi = 30.5
    sample_enriched_signal.snapshot.ma_50 = 160.0
    
    prompt = grader._build_prompt(sample_enriched_signal, news)
    
    assert "AAPL launches new iPhone" in prompt
    assert "Tech stocks rally" in prompt
    assert "RSI: 30.5" in prompt
    assert "MA_50: 160.0" in prompt
    assert "NER" in prompt or "Named Entity Recognition" in prompt
