from dataclasses import dataclass
import pandas as pd
import ta
from src.fetcher import StockSnapshot


@dataclass
class DimensionScore:
    label: str       # "BUY", "HOLD", or "SELL"
    reason: str      # Human-readable reason
    score: float     # Numeric score 0-100


@dataclass
class EnrichedSignal:
    symbol: str
    snapshot: StockSnapshot
    dimensions: dict[str, DimensionScore]  # keys: "PRICE", "FLOW", "CONTEXT"


class DataTransformer:
    """Transforms raw market snapshots into 3-dimension analysis signals."""

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators (rsi, ma_50, volume_20d_avg, is_volume_anomaly).

        Consumes a pandas DataFrame with 'close' (or 'Close') and 'volume' (or 'Volume') columns.
        Produces a DataFrame with additional columns:
        - rsi: Relative Strength Index (14 periods)
        - ma_50: 50-period Simple Moving Average of close price
        - volume_20d_avg: 20-period Simple Moving Average of volume
        - is_volume_anomaly: boolean indicating if volume > 1.5 * volume_20d_avg
        - bb_lower: Lower Bollinger Band (20 periods, 2 std dev)
        - bb_upper: Upper Bollinger Band (20 periods, 2 std dev)
        """
        df = df.copy()

        close_col = "close" if "close" in df.columns else ("Close" if "Close" in df.columns else None)
        volume_col = "volume" if "volume" in df.columns else ("Volume" if "Volume" in df.columns else None)

        if close_col is None:
            raise KeyError("DataFrame must contain 'close' or 'Close' column.")
        if volume_col is None:
            raise KeyError("DataFrame must contain 'volume' or 'Volume' column.")

        close_series = df[close_col].astype(float)
        volume_series = df[volume_col].astype(float)

        df["rsi"] = ta.momentum.rsi(close=close_series, window=14)
        df["ma_50"] = ta.trend.sma_indicator(close=close_series, window=50)
        df["volume_20d_avg"] = ta.trend.sma_indicator(close=volume_series, window=20)
        df["is_volume_anomaly"] = volume_series > (1.5 * df["volume_20d_avg"])

        indicator_bb = ta.volatility.BollingerBands(close=close_series, window=20, window_dev=2)
        df["bb_lower"] = indicator_bb.bollinger_lband()
        df["bb_upper"] = indicator_bb.bollinger_hband()

        return df

    def enrich(self, snapshots: dict[str, StockSnapshot]) -> dict[str, EnrichedSignal]:
        """Enrich each snapshot with PRICE, FLOW, and CONTEXT dimension scores."""
        enriched: dict[str, EnrichedSignal] = {}
        for symbol, snapshot in snapshots.items():
            dimensions = {
                "PRICE": self._score_price(snapshot),
                "FLOW": self._score_flow(snapshot),
                "CONTEXT": self._score_context(snapshot),
            }
            enriched[symbol] = EnrichedSignal(
                symbol=symbol,
                snapshot=snapshot,
                dimensions=dimensions,
            )
        return enriched

    def _score_price(self, snapshot: StockSnapshot) -> DimensionScore:
        """Score based on ATH drawdown percentage.

        Rules:
        - drawdown <= -30%: BUY (score 90) "Deep discount from ATH"
        - drawdown <= -20%: BUY (score 70) "Significant pullback from ATH"
        - drawdown <= -10%: HOLD (score 50) "Moderate pullback"
        - else: HOLD (score 30) "Near ATH, limited upside"
        """
        dd = snapshot.drawdown_pct
        if dd <= -30.0:
            return DimensionScore(
                label="BUY",
                score=90.0,
                reason="Deep discount from ATH",
            )
        elif dd <= -20.0:
            return DimensionScore(
                label="BUY",
                score=70.0,
                reason="Significant pullback from ATH",
            )
        elif dd <= -10.0:
            return DimensionScore(
                label="HOLD",
                score=50.0,
                reason="Moderate pullback",
            )
        else:
            return DimensionScore(
                label="HOLD",
                score=30.0,
                reason="Near ATH, limited upside",
            )

    def _score_flow(self, snapshot: StockSnapshot) -> DimensionScore:
        """Score based on volume anomaly detection.

        Uses is_volume_anomaly attribute if available (computed by
        calculate_indicators), otherwise returns a neutral score.
        """
        is_anomaly = getattr(snapshot, "is_volume_anomaly", None)
        if is_anomaly is True:
            return DimensionScore(
                label="BUY",
                score=80.0,
                reason="Volume anomaly detected (>1.5× 20-day avg) — institutional interest likely.",
            )
        elif is_anomaly is False:
            return DimensionScore(
                label="HOLD",
                score=40.0,
                reason="Volume within normal range — no unusual trading activity.",
            )
        return DimensionScore(
            label="HOLD",
            score=50.0,
            reason="Volume data not available for anomaly check.",
        )

    def _score_context(self, snapshot: StockSnapshot) -> DimensionScore:
        """Score based on fundamental valuation metrics.

        Uses trailing P/E if available to assess whether the stock
        is overvalued, fairly valued, or undervalued.
        """
        pe = getattr(snapshot, "trailing_pe", None)
        if pe is None:
            return DimensionScore(
                label="HOLD",
                score=50.0,
                reason="P/E data not available for context scoring.",
            )
        if pe < 15:
            return DimensionScore(
                label="BUY",
                score=80.0,
                reason=f"P/E {pe:.1f} — undervalued relative to broad market.",
            )
        elif pe < 30:
            return DimensionScore(
                label="HOLD",
                score=50.0,
                reason=f"P/E {pe:.1f} — fairly valued.",
            )
        else:
            return DimensionScore(
                label="HOLD",
                score=30.0,
                reason=f"P/E {pe:.1f} — premium valuation, proceed with caution.",
            )
