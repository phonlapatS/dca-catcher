import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.slip_parser import GeminiSlipParser


@pytest.mark.asyncio
@patch("src.slip_parser.genai.Client")
async def test_parse_slip_success(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.text = (
        '{"symbol": "AAPL", "action": "BUY", "price": 150.0, "volume": 10.5}'
    )
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    parser = GeminiSlipParser(api_key="fake")
    result = await parser.parse_slip(b"fake_image_bytes")

    assert result is not None
    assert result["symbol"] == "AAPL"
    assert result["action"] == "BUY"
    assert result["price"] == 150.0
    assert result["volume"] == 10.5
    mock_client.aio.models.generate_content.assert_called_once()


@pytest.mark.asyncio
@patch("src.slip_parser.genai.Client")
async def test_parse_slip_markdown_wrapped(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.text = (
        '```json\n{"symbol": "TSLA", "action": "BUY", "price": 210.5, "volume": 4.0}\n```'
    )
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    parser = GeminiSlipParser(api_key="fake")
    result = await parser.parse_slip(b"fake_image_bytes")

    assert result is not None
    assert result["symbol"] == "TSLA"
    assert result["action"] == "BUY"
    assert result["price"] == 210.5
    assert result["volume"] == 4.0


@pytest.mark.asyncio
@patch("src.slip_parser.genai.Client")
async def test_parse_slip_non_slip_empty_json(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.text = "{}"
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    parser = GeminiSlipParser(api_key="fake")
    result = await parser.parse_slip(b"fake_image_bytes")

    assert result is None


@pytest.mark.asyncio
@patch("src.slip_parser.genai.Client")
async def test_parse_slip_invalid_json(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.text = "not a valid json response"
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    parser = GeminiSlipParser(api_key="fake")
    result = await parser.parse_slip(b"fake_image_bytes")

    assert result is None


@pytest.mark.asyncio
@patch("src.slip_parser.genai.Client")
async def test_parse_slip_api_exception(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=Exception("API Error")
    )

    parser = GeminiSlipParser(api_key="fake")
    result = await parser.parse_slip(b"fake_image_bytes")

    assert result is None
