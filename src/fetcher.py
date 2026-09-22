import asyncio
import logging
import time
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
    sma_200: float | None = None
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
    return_on_equity: float | None = None
    dividend_yield: float | None = None


class MarketDataFetcher:
    """Fetches market data from yfinance for US and TH (.BK) stocks."""

    def __init__(self, cache_ttl: int = 180):
        self._cache: dict[str, tuple[StockSnapshot, float]] = {}
        self._cache_ttl = cache_ttl  # 3 minutes default

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
        Uses a TTL memory cache to avoid duplicate API calls within a short window.
        """
        snapshots: dict[str, StockSnapshot] = {}
        symbols_to_fetch: list[str] = []
        now = time.time()

        # Check cache first
        for symbol in symbols:
            if symbol in self._cache:
                snap, ts = self._cache[symbol]
                if now - ts < self._cache_ttl:
                    snapshots[symbol] = snap
                    continue
            symbols_to_fetch.append(symbol)

        for symbol in symbols_to_fetch:
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
                    debt_to_equity=info.get("debtToEquity"),
                    free_cash_flow=info.get("freeCashflow"),
                    return_on_equity=info.get("returnOnEquity"),
                    dividend_yield=info.get("dividendYield")
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
                        snapshots[symbol].sma_200 = float(last_row["sma_200"]) if pd.notna(last_row.get("sma_200")) else None
                        snapshots[symbol].volume_20d_avg = float(last_row["volume_20d_avg"]) if pd.notna(last_row.get("volume_20d_avg")) else None
                        snapshots[symbol].is_volume_anomaly = bool(last_row["is_volume_anomaly"]) if pd.notna(last_row.get("is_volume_anomaly")) else None
                except Exception as e:
                    logger.warning(f"Failed to compute indicators for {symbol}: {e}")
                
                # Store in memory cache
                self._cache[symbol] = (snapshots[symbol], now)
            except Exception as e:
                logger.warning(f"Failed to fetch market data for symbol '{symbol}': {e}")
                continue

        return snapshots

    def fetch_macro(self) -> dict:
        """Fetch market-wide macro indicators (VIX, SPY) for contextual analysis.
        
        Returns a dict with raw numbers for AI to interpret:
        {
            "vix": 18.5,
            "spy_change_pct": -1.2,
            "spy_price": 540.0,
            "market_state": "BULLISH" | "CAUTIOUS" | "BEARISH" | "PANIC"
        }
        Uses memory cache (TTL = 30 min) to avoid redundant API calls.
        """
        cache_key = "__MACRO__"
        now = time.time()
        
        if cache_key in self._cache:
            cached_data, ts = self._cache[cache_key]
            if now - ts < 1800:  # 30-minute TTL for macro
                return cached_data
        
        result = {"vix": None, "spy_change_pct": None, "spy_price": None, "market_state": "N/A"}
        
        try:
            vix_ticker = yf.Ticker("^VIX")
            vix_df = vix_ticker.history(period="5d")
            if vix_df is not None and not vix_df.empty:
                result["vix"] = round(float(vix_df["Close"].iloc[-1]), 2)
        except Exception as e:
            logger.warning(f"Failed to fetch VIX: {e}")
        
        try:
            spy_ticker = yf.Ticker("SPY")
            spy_df = spy_ticker.history(period="5d")
            if spy_df is not None and not spy_df.empty and len(spy_df) >= 2:
                today_close = float(spy_df["Close"].iloc[-1])
                prev_close = float(spy_df["Close"].iloc[-2])
                result["spy_price"] = round(today_close, 2)
                result["spy_change_pct"] = round(((today_close - prev_close) / prev_close) * 100, 2)
        except Exception as e:
            logger.warning(f"Failed to fetch SPY: {e}")
        
        # Determine market state from VIX
        vix = result.get("vix")
        if vix is not None:
            if vix < 15:
                result["market_state"] = "BULLISH"
            elif vix < 20:
                result["market_state"] = "CAUTIOUS"
            elif vix < 30:
                result["market_state"] = "BEARISH"
            else:
                result["market_state"] = "PANIC"
        
        self._cache[cache_key] = (result, now)
        return result
