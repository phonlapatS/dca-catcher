from dataclasses import dataclass
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
        """Score based on volume (placeholder for MVP).

        For MVP, return HOLD with score 50 and note "Volume analysis requires
        historical data — will be enriched with 20-day average comparison."
        """
        return DimensionScore(
            label="HOLD",
            score=50.0,
            reason="Volume analysis requires historical data — will be enriched with 20-day average comparison.",
        )

    def _score_context(self, snapshot: StockSnapshot) -> DimensionScore:
        """Score based on market context (placeholder for MVP).

        For MVP, return HOLD with score 50 and note "Context analysis
        (news sentiment, Fear & Greed) will be added in future iteration."
        """
        return DimensionScore(
            label="HOLD",
            score=50.0,
            reason="Context analysis (news sentiment, Fear & Greed) will be added in future iteration.",
        )
