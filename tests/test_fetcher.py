import pytest
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
