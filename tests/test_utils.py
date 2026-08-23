import pytest
from src.utils import extract_json_from_llm


def test_extract_json_plain():
    result = extract_json_from_llm('{"key": "value"}')
    assert result == {"key": "value"}


def test_extract_json_with_markdown_fence():
    raw = '```json\n{"grade": 8, "advice": "ซื้อได้"}\n```'
    result = extract_json_from_llm(raw)
    assert result["grade"] == 8


def test_extract_json_with_newline_before_fence():
    raw = '\n```json\n{"symbol": "NVDA"}\n```\n'
    result = extract_json_from_llm(raw)
    assert result["symbol"] == "NVDA"


def test_extract_json_with_preamble():
    raw = 'Here is the analysis:\n```json\n{"score": 9.5}\n```\nEnd.'
    result = extract_json_from_llm(raw)
    assert result["score"] == 9.5


def test_extract_json_array():
    raw = '```json\n[{"symbol": "AAPL"}, {"symbol": "NVDA"}]\n```'
    result = extract_json_from_llm(raw)
    assert len(result) == 2


def test_extract_json_invalid_raises():
    with pytest.raises(ValueError):
        extract_json_from_llm("This is not JSON at all.")
