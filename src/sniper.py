import asyncio
import json
import logging
import os
import re
from datetime import datetime, time
from typing import Awaitable, Callable, Optional
from zoneinfo import ZoneInfo

import websockets
from sqlalchemy import select, func

from src.alert_manager import AlertManager
from src.database import Database, User, Watchlist

logger = logging.getLogger(__name__)


class AlpacaSniper:
    """Alpaca WebSocket stream client for monitoring US stock trade ticks."""

    def __init__(
        self,
        db: Database,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        stream_url: str = "wss://stream.data.alpaca.markets/v2/iex",
        on_tick_callback: Optional[Callable[[str, float], Awaitable[None]]] = None,
        alert_manager: Optional[AlertManager] = None,
        poll_interval: float = 60.0,
    ):
        self.db = db
        self.api_key = api_key or os.environ.get("ALPACA_API_KEY", "")
        self.secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY", "")
        self.stream_url = stream_url
        self.on_tick_callback = on_tick_callback
        self.alert_manager = alert_manager or (AlertManager(db) if db else None)
        self.poll_interval = poll_interval

        self.running = False
        self._task: Optional[asyncio.Task] = None
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.subscribed_symbols: set[str] = set()
        self.targets: dict[str, list[float]] = {}

    def is_operating_hours(self, now: Optional[datetime] = None) -> bool:
        """Check if the current time in Asia/Bangkok is between 20:30 and 04:00."""
        bkk_tz = ZoneInfo("Asia/Bangkok")
        if now is None:
            now_bkk = datetime.now(bkk_tz)
        elif now.tzinfo is None:
            now_bkk = now.replace(tzinfo=bkk_tz)
        else:
            now_bkk = now.astimezone(bkk_tz)

        t = now_bkk.time()
        return t >= time(20, 30) or t < time(4, 0)

    def parse_target_zones(self, target_zones_str: Optional[str]) -> list[float]:
        """Parse float target prices from target_zones_str field in descending order.
        
        Example inputs:
          "150.0 (Low Risk), 140.0 (Moderate)" -> [150.0, 140.0]
          "110.0, 120.0" -> [120.0, 110.0]
        """
        if not target_zones_str:
            return []
        zones = []
        for part in target_zones_str.split(","):
            part = part.strip()
            if not part:
                continue
            match = re.search(r"(\d+(?:\.\d+)?)", part)
            if match:
                try:
                    zones.append(float(match.group(1)))
                except ValueError:
                    pass
        zones.sort(reverse=True)
        return zones

    async def load_us_targets(self) -> dict[str, list[float]]:
        """Query database for active US watchlist items and parse target prices."""
        async with self.db.session() as session:
            stmt = select(Watchlist).where(Watchlist.market == "US")
            result = await session.execute(stmt)
            items = result.scalars().all()

            targets: dict[str, list[float]] = {}
            for item in items:
                if not item.symbol:
                    continue
                symbol = item.symbol.upper()
                parsed = self.parse_target_zones(item.target_zones_str)
                if symbol not in targets:
                    targets[symbol] = []
                targets[symbol].extend(parsed)
            return targets

    async def start(self):
        """Start the AlpacaSniper execution loop in background."""
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self.run())
        logger.info("AlpacaSniper started.")

    async def stop(self):
        """Stop the AlpacaSniper loop and close WebSocket connection."""
        self.running = False
        if self.ws:
            try:
                await self.ws.close()
            except Exception as e:
                logger.warning(f"Error closing Alpaca websocket: {e}")
            self.ws = None

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("AlpacaSniper stopped.")

    async def check_target_triggers(self, symbol: str, price: float):
        """Check database US watchlists for symbol, trigger alert if price <= target price and update DB to prevent spam."""
        if not self.db:
            return

        # Performance optimization: if in-memory targets are loaded, check bounds before querying DB
        if self.targets:
            symbol_targets = self.targets.get(symbol.upper())
            if symbol_targets is None or not any(price <= t for t in symbol_targets):
                return

        try:
            async with self.db.session() as session:
                stmt = (
                    select(Watchlist, User.telegram_id)
                    .join(User, Watchlist.user_id == User.id)
                    .where(Watchlist.market == "US", func.upper(Watchlist.symbol) == symbol.upper())
                )
                res = await session.execute(stmt)
                rows = res.all()

            for item, telegram_id in rows:
                if not item.target_zones_str:
                    continue

                if self.alert_manager:
                    alerted, msg = await self.alert_manager.check_and_notify(
                        user_id=telegram_id,
                        symbol=symbol,
                        current_price=price,
                        target_zones_str=item.target_zones_str,
                    )
                    if alerted:
                        logger.info(
                            f"SNIPER TRIGGER: {symbol} at ${price} <= target zone for user {telegram_id}: {msg}"
                        )
                else:
                    zones = self.parse_target_zones(item.target_zones_str)
                    for target in zones:
                        if price <= target:
                            active_zone_str = f"{target}"
                            last_notified_price = None
                            if item.last_notified_zone:
                                m = re.search(r"(\d+(?:\.\d+)?)", item.last_notified_zone)
                                if m:
                                    last_notified_price = float(m.group(1))

                            if last_notified_price != target:
                                logger.info(f"SNIPER TRIGGER: {symbol} at ${price} <= target ${target}")
                                async with self.db.session() as session:
                                    w_item = await session.get(Watchlist, item.id)
                                    if w_item:
                                        w_item.last_notified_zone = active_zone_str
                                        await session.commit()
                            break
        except Exception as e:
            logger.error(f"Error checking target triggers for {symbol}: {e}", exc_info=True)


    async def on_trade_tick(self, symbol: str, price: float):
        """Handle incoming trade tick."""
        logger.debug(f"Tick received for {symbol}: ${price}")
        await self.check_target_triggers(symbol, price)
        if self.on_tick_callback:
            await self.on_tick_callback(symbol, price)

    async def handle_message(self, msg_str: str):
        """Parse Alpaca WebSocket text frame and process trade messages."""
        try:
            data = json.loads(msg_str)
            if isinstance(data, dict):
                data = [data]
            if not isinstance(data, list):
                return

            for item in data:
                if not isinstance(item, dict):
                    continue
                msg_type = item.get("T")
                if msg_type == "t":
                    symbol = item.get("S")
                    price = item.get("p")
                    if symbol and price is not None:
                        try:
                            price_float = float(price)
                            await self.on_trade_tick(symbol, price_float)
                        except ValueError:
                            pass
        except Exception as e:
            logger.error(f"Error processing Alpaca websocket message: {e}")

    async def run(self):
        """Main loop managing operating hours, connection, auth, subscription, and streaming."""
        logger.info("AlpacaSniper run loop initiated.")
        while self.running:
            try:
                if not self.is_operating_hours():
                    logger.debug("Outside operating hours (20:30-04:00 BKK). Waiting...")
                    await asyncio.sleep(self.poll_interval)
                    continue

                targets = await self.load_us_targets()
                symbols = sorted(list(targets.keys()))
                if not symbols:
                    logger.info("No US symbols found in Watchlist. Waiting...")
                    await asyncio.sleep(self.poll_interval)
                    continue

                logger.info(f"Connecting to Alpaca stream at {self.stream_url} for symbols {symbols}")
                async with websockets.connect(self.stream_url) as ws:
                    self.ws = ws

                    # 1. Greeting
                    greeting = await ws.recv()
                    logger.debug(f"Connected to stream: {greeting}")

                    # 2. Authenticate
                    auth_payload = {
                        "action": "auth",
                        "key": self.api_key,
                        "secret": self.secret_key,
                    }
                    await ws.send(json.dumps(auth_payload))
                    auth_res = await ws.recv()
                    logger.info(f"Auth response: {auth_res}")

                    auth_data = json.loads(auth_res)
                    if isinstance(auth_data, list) and auth_data and auth_data[0].get("T") == "error":
                        logger.error(f"Alpaca WebSocket auth failed: {auth_data[0].get('msg')}")
                        await asyncio.sleep(self.poll_interval)
                        continue

                    # 3. Subscribe
                    sub_payload = {
                        "action": "subscribe",
                        "trades": symbols,
                        "quotes": [],
                        "bars": [],
                    }
                    await ws.send(json.dumps(sub_payload))
                    sub_res = await ws.recv()
                    logger.info(f"Subscribed: {sub_res}")

                    self.subscribed_symbols = set(symbols)
                    self.targets = targets

                    # 4. Stream listen loop
                    while self.running and self.is_operating_hours():
                        try:
                            msg_str = await asyncio.wait_for(ws.recv(), timeout=5.0)
                            await self.handle_message(msg_str)
                        except asyncio.TimeoutError:
                            continue
                        except websockets.ConnectionClosed:
                            logger.warning("Alpaca WebSocket connection closed.")
                            break

            except asyncio.CancelledError:
                logger.info("AlpacaSniper run loop cancelled.")
                break
            except Exception as e:
                logger.error(f"AlpacaSniper error: {e}", exc_info=True)
                if self.running:
                    await asyncio.sleep(5)
            finally:
                self.ws = None
