import pytest
from unittest.mock import patch
from src.fetcher import MarketDataFetcher, StockSnapshot


def test_fetch_valid_symbol():
    fetcher = MarketDataFetcher()
    results = fetcher.fetch(["AAPL"])
    assert "AAPL" in results
    snapshot = results["AAPL"]

    assert isinstance(snapshot, StockSnapshot)
    assert snapshot.symbol == "AAPL"
    assert snapshot.current_price > 0
    assert snapshot.volume >= 0
    assert snapshot.ath_price >= snapshot.current_price
    assert snapshot.drawdown_pct <= 0.0


def test_fetch_th_symbol():
    fetcher = MarketDataFetcher()
    results = fetcher.fetch(["CPALL.BK"])
    assert "CPALL.BK" in results
    snapshot = results["CPALL.BK"]

    assert isinstance(snapshot, StockSnapshot)
    assert snapshot.symbol == "CPALL.BK"
    assert snapshot.current_price > 0
    assert snapshot.volume >= 0
    assert snapshot.ath_price >= snapshot.current_price
    assert snapshot.drawdown_pct <= 0.0


def test_fetch_invalid_symbol():
    fetcher = MarketDataFetcher()
    results = fetcher.fetch(["XXXYYYZZZ123"])
    assert "XXXYYYZZZ123" not in results
    assert len(results) == 0


def test_fetch_multiple_symbols():
    fetcher = MarketDataFetcher()
    results = fetcher.fetch(["AAPL", "XXXYYYZZZ123"])
    assert "AAPL" in results
    assert "XXXYYYZZZ123" not in results
    assert len(results) == 1

@pytest.mark.asyncio
async def test_fetch_async_returns_snapshots():
    """fetch_async should return the same results as fetch but asynchronously."""
    fetcher = MarketDataFetcher()
    # Mock the sync fetch to avoid network calls
    with patch.object(fetcher, '_fetch_one_sync') as mock_fetch:
        mock_fetch.return_value = StockSnapshot(
            symbol="TEST", current_price=100.0, volume=1000,
            ath_price=150.0, drawdown_pct=-33.33
        )
        result = await fetcher.fetch_async(["TEST"])
        assert "TEST" in result
        assert result["TEST"].current_price == 100.0
