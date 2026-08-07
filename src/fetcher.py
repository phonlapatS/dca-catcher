import logging
from dataclasses import dataclass
import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass
class StockSnapshot:
    symbol: str
    current_price: float
    volume: int
    ath_price: float
    drawdown_pct: float  # negative value, e.g. -20.0
    rsi: float | None = None
    ma_50: float | None = None
    volume_20d_avg: float | None = None
    is_volume_anomaly: bool | None = None
    
    # Fundamental Data
    trailing_pe: float | None = None
    peg_ratio: float | None = None
    revenue_growth: float | None = None
    profit_margins: float | None = None
    debt_to_equity: float | None = None


class MarketDataFetcher:
    """Fetches market data from yfinance for US and TH (.BK) stocks."""

    def fetch(self, symbols: list[str]) -> dict[str, StockSnapshot]:
        """Fetch current price, volume, ATH, and drawdown for each symbol.

        Returns a dict keyed by symbol. Symbols that fail to fetch are
        silently skipped (logged, not raised).
        """
        snapshots: dict[str, StockSnapshot] = {}
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period="max")
                if df is None or df.empty:
                    logger.warning(f"No market data returned for symbol: {symbol}")
                    continue

                df_clean = df.dropna(subset=["Close", "High"])
                if df_clean.empty:
                    logger.warning(f"No valid price data for symbol: {symbol}")
                    continue

                current_price = float(df_clean["Close"].iloc[-1])
                volume = int(df_clean["Volume"].iloc[-1]) if "Volume" in df_clean.columns and not df_clean["Volume"].empty else 0
                ath_price = float(df_clean["High"].max())

                if ath_price <= 0:
                    drawdown_pct = 0.0
                else:
                    drawdown_pct = round(((current_price - ath_price) / ath_price) * 100.0, 2)
                    if drawdown_pct > 0:
                        drawdown_pct = 0.0

                info = ticker.info or {}
                
                snapshots[symbol] = StockSnapshot(
                    symbol=symbol,
                    current_price=round(current_price, 2),
                    volume=volume,
                    ath_price=round(ath_price, 2),
                    drawdown_pct=drawdown_pct,
                    trailing_pe=info.get("trailingPE"),
                    peg_ratio=info.get("pegRatio"),
                    revenue_growth=info.get("revenueGrowth"),
                    profit_margins=info.get("profitMargins"),
                    debt_to_equity=info.get("debtToEquity")
                )
            except Exception as e:
                logger.warning(f"Failed to fetch market data for symbol '{symbol}': {e}")
                continue

        return snapshots
