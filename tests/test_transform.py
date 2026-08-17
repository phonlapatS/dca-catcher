import pytest
from src.fetcher import StockSnapshot
from src.transform import DataTransformer, DimensionScore, EnrichedSignal


def test_score_price_deep_discount():
    transformer = DataTransformer()
    snapshot = StockSnapshot(
        symbol="AAPL",
        current_price=100.0,
        volume=1000000,
        ath_price=150.0,
        drawdown_pct=-33.33,
    )
    score = transformer._score_price(snapshot)
    assert isinstance(score, DimensionScore)
    assert score.label == "BUY"
    assert score.score == 90.0
    assert score.reason == "Deep discount from ATH"


def test_score_price_significant_pullback():
    transformer = DataTransformer()
    snapshot = StockSnapshot(
        symbol="AAPL",
        current_price=120.0,
        volume=1000000,
        ath_price=150.0,
        drawdown_pct=-20.0,
    )
    score = transformer._score_price(snapshot)
    assert score.label == "BUY"
    assert score.score == 70.0
    assert score.reason == "Significant pullback from ATH"


def test_score_price_moderate_pullback():
    transformer = DataTransformer()
    snapshot = StockSnapshot(
        symbol="AAPL",
        current_price=135.0,
        volume=1000000,
        ath_price=150.0,
        drawdown_pct=-10.0,
    )
    score = transformer._score_price(snapshot)
    assert score.label == "HOLD"
    assert score.score == 50.0
    assert score.reason == "Moderate pullback"


def test_score_price_near_ath():
    transformer = DataTransformer()
    snapshot = StockSnapshot(
        symbol="AAPL",
        current_price=145.0,
        volume=1000000,
        ath_price=150.0,
        drawdown_pct=-3.33,
    )
    score = transformer._score_price(snapshot)
    assert score.label == "HOLD"
    assert score.score == 30.0
    assert score.reason == "Near ATH, limited upside"


def test_score_flow_placeholder():
    transformer = DataTransformer()
    snapshot = StockSnapshot(
        symbol="AAPL",
        current_price=100.0,
        volume=1000000,
        ath_price=150.0,
        drawdown_pct=-33.33,
    )
    score = transformer._score_flow(snapshot)
    assert score.label == "HOLD"
    assert score.score == 50.0
    assert "Volume data" in score.reason


def test_score_context_placeholder():
    transformer = DataTransformer()
    snapshot = StockSnapshot(
        symbol="AAPL",
        current_price=100.0,
        volume=1000000,
        ath_price=150.0,
        drawdown_pct=-33.33,
    )
    score = transformer._score_context(snapshot)
    assert score.label == "HOLD"
    assert score.score == 50.0
    assert "P/E data" in score.reason


def test_enrich():
    transformer = DataTransformer()
    snap1 = StockSnapshot(
        symbol="AAPL",
        current_price=100.0,
        volume=1000000,
        ath_price=150.0,
        drawdown_pct=-33.33,
    )
    snap2 = StockSnapshot(
        symbol="NVDA",
        current_price=140.0,
        volume=2000000,
        ath_price=150.0,
        drawdown_pct=-6.67,
    )
    snapshots = {"AAPL": snap1, "NVDA": snap2}

    enriched = transformer.enrich(snapshots)

    assert len(enriched) == 2
    assert "AAPL" in enriched
    assert "NVDA" in enriched

    signal_aapl = enriched["AAPL"]
    assert isinstance(signal_aapl, EnrichedSignal)
    assert signal_aapl.symbol == "AAPL"
    assert signal_aapl.snapshot == snap1
    assert set(signal_aapl.dimensions.keys()) == {"PRICE", "FLOW", "CONTEXT"}
    assert signal_aapl.dimensions["PRICE"].label == "BUY"
    assert signal_aapl.dimensions["PRICE"].score == 90.0

    signal_nvda = enriched["NVDA"]
    assert signal_nvda.symbol == "NVDA"
    assert signal_nvda.snapshot == snap2
    assert signal_nvda.dimensions["PRICE"].label == "HOLD"
    assert signal_nvda.dimensions["PRICE"].score == 30.0


def test_calculate_indicators():
    import pandas as pd
    import numpy as np

    closes = [100.0 + i * 0.5 for i in range(60)]
    volumes = [1000000] * 59 + [3000000]

    df = pd.DataFrame({
        "close": closes,
        "volume": volumes,
    })

    transformer = DataTransformer()
    result_df = transformer.calculate_indicators(df)

    for col in ["rsi", "ma_50", "volume_20d_avg", "is_volume_anomaly", "bb_lower", "bb_upper"]:
        assert col in result_df.columns

    expected_ma50 = sum(closes[10:60]) / 50.0
    assert pytest.approx(result_df["ma_50"].iloc[-1], abs=1e-2) == expected_ma50
    assert result_df["volume_20d_avg"].iloc[58] == 1000000.0
    assert bool(result_df["is_volume_anomaly"].iloc[-1]) is True
    assert bool(result_df["is_volume_anomaly"].iloc[58]) is False
    assert not result_df["rsi"].dropna().empty
    assert 0 <= result_df["rsi"].iloc[-1] <= 100


def test_calculate_indicators_uppercase_columns():
    import pandas as pd

    closes = [100.0 + i for i in range(60)]
    volumes = [100000] * 60
    df = pd.DataFrame({"Close": closes, "Volume": volumes})

    transformer = DataTransformer()
    result_df = transformer.calculate_indicators(df)

    for col in ["rsi", "ma_50", "volume_20d_avg", "is_volume_anomaly", "bb_lower", "bb_upper"]:
        assert col in result_df.columns

