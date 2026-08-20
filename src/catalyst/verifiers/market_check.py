from typing import Optional, Tuple


class MarketMicrostructureChecker:
    """Validates pre-market institutional liquidity, dollar volume, and bid-ask spread tightness."""

    DEFAULT_MIN_DOLLAR_VOLUME = 2_000_000.0  # $2M USD
    DEFAULT_MAX_SPREAD_PCT = 2.0            # 2.0%

    def validate_premarket_liquidity(
        self,
        price: float,
        premarket_volume: int,
        bid_price: Optional[float] = None,
        ask_price: Optional[float] = None,
        min_dollar_volume: float = DEFAULT_MIN_DOLLAR_VOLUME,
        max_spread_pct: float = DEFAULT_MAX_SPREAD_PCT,
    ) -> Tuple[bool, str]:
        """Checks if pre-market trading activity has real institutional depth."""
        if price <= 0 or premarket_volume <= 0:
            return False, "Zero or negative price/volume"

        dollar_volume = price * premarket_volume
        if dollar_volume < min_dollar_volume:
            return False, f"Low Dollar Volume (${dollar_volume:,.0f} < ${min_dollar_volume:,.0f})"

        if bid_price is not None and ask_price is not None and bid_price > 0 and ask_price >= bid_price:
            mid_price = (bid_price + ask_price) / 2.0
            if mid_price > 0:
                spread_pct = ((ask_price - bid_price) / mid_price) * 100.0
                if spread_pct > max_spread_pct:
                    return False, f"Wide Bid-Ask Spread ({spread_pct:.2f}% > {max_spread_pct}%)"

        return True, "Passed Microstructure Validation"
