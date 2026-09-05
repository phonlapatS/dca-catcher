import asyncio
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
    forward_pe: float | None = None
    eps_ttm: float | None = None
    free_cash_flow: float | None = None
    debt_to_equity: float | None = None
    debt_to_equity: float | None = None


class MarketDataFetcher:
    """Fetches market data from yfinance for US and TH (.BK) stocks."""

    async def fetch_async(self, symbols: list[str]) -> dict[str, StockSnapshot]:
        """Async version of fetch() — runs yfinance calls in thread pool to avoid blocking event loop.
        
        Each symbol is fetched in a separate thread via asyncio.to_thread(),
        allowing parallel network requests without blocking the async event loop.
        """
        async def _fetch_one(symbol: str) -> tuple[str, StockSnapshot | None]:
            try:
                snapshot = await asyncio.to_thread(self._fetch_one_sync, symbol)
                return (symbol, snapshot)
            except Exception as e:
                logger.warning(f"Async fetch failed for '{symbol}': {e}")
                return (symbol, None)
        
        results = await asyncio.gather(*[_fetch_one(s) for s in symbols])
        return {sym: snap for sym, snap in results if snap is not None}
    
    def _fetch_one_sync(self, symbol: str) -> StockSnapshot | None:
        """Fetch a single symbol synchronously. Used by fetch_async via asyncio.to_thread."""
        result = self.fetch([symbol])
        return result.get(symbol)


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
                
                # After creating the StockSnapshot, compute indicators from the DataFrame
                try:
                    import pandas as pd
                    from src.transform import DataTransformer
                    transformer = DataTransformer()
                    df_indicators = transformer.calculate_indicators(df_clean)
                    if not df_indicators.empty:
                        last_row = df_indicators.iloc[-1]
                        snapshots[symbol].rsi = float(last_row["rsi"]) if pd.notna(last_row.get("rsi")) else None
                        snapshots[symbol].ma_50 = float(last_row["ma_50"]) if pd.notna(last_row.get("ma_50")) else None
                        snapshots[symbol].volume_20d_avg = float(last_row["volume_20d_avg"]) if pd.notna(last_row.get("volume_20d_avg")) else None
                        snapshots[symbol].is_volume_anomaly = bool(last_row["is_volume_anomaly"]) if pd.notna(last_row.get("is_volume_anomaly")) else None
                except Exception as e:
                    logger.warning(f"Failed to compute indicators for {symbol}: {e}")
            except Exception as e:
                logger.warning(f"Failed to fetch market data for symbol '{symbol}': {e}")
                continue

        return snapshots
