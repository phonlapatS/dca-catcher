import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, time as dt_time
from typing import Awaitable, Callable, Optional, TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from aiogram import Bot

from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
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
        bot: Optional["Bot"] = None,
        broadcast_channel_id: Optional[str] = None,
        sniper_start_hour: int = 20,
        sniper_start_minute: int = 30,
        sniper_end_hour: int = 4,
        sniper_end_minute: int = 0,
    ):
        self.db = db
        self.api_key = api_key or os.environ.get("ALPACA_API_KEY", "")
        self.secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY", "")
        self.stream_url = stream_url
        self.on_tick_callback = on_tick_callback
        self.alert_manager = alert_manager or (AlertManager(db) if db else None)
        self.poll_interval = poll_interval
        self.bot = bot
        self.broadcast_channel_id = broadcast_channel_id
        self.sniper_start_hour = sniper_start_hour
        self.sniper_start_minute = sniper_start_minute
        self.sniper_end_hour = sniper_end_hour
        self.sniper_end_minute = sniper_end_minute

        self.running = False
        self._task: Optional[asyncio.Task] = None
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.subscribed_symbols: set[str] = set()
        self.targets: dict[str, list[float]] = {}
        self._watchlist_cache: list = []  # Cached watchlist rows
        self._cache_timestamp: float = 0
        self._CACHE_TTL: float = 60.0  # Refresh cache every 60 seconds

    def is_operating_hours(self, now: Optional[datetime] = None) -> bool:
        """Check if the current time in Asia/Bangkok is within sniper window."""
        bkk_tz = ZoneInfo("Asia/Bangkok")
        if now is None:
            now_bkk = datetime.now(bkk_tz)
        elif now.tzinfo is None:
            now_bkk = now.replace(tzinfo=bkk_tz)
        else:
            now_bkk = now.astimezone(bkk_tz)

        t = now_bkk.time()
        start = dt_time(self.sniper_start_hour, self.sniper_start_minute)
        end = dt_time(self.sniper_end_hour, self.sniper_end_minute)
        return t >= start or t < end

    def parse_target_zones(self, target_zones_str: Optional[str]) -> list[float]:
        """Parse float target prices from target_zones_str field in descending order."""
        if not target_zones_str:
            return []
        zones = AlertManager.parse_zones(target_zones_str)
        return [z["price"] for z in zones]

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

    async def update_subscriptions(self):
        """Update targets and send a new subscribe message if the stream is active."""
        if not self.running or not self.ws or not self.is_operating_hours():
            return
            
        targets = await self.load_us_targets()
        symbols = sorted(list(targets.keys()))
        
        if not symbols:
            return
            
        try:
            sub_payload = {
                "action": "subscribe",
                "trades": symbols,
                "quotes": [],
                "bars": [],
            }
            await self.ws.send(json.dumps(sub_payload))
            self.subscribed_symbols = set(symbols)
            self.targets = targets
            logger.info(f"Dynamically updated subscriptions to: {symbols}")
        except Exception as e:
            logger.error(f"Error updating subscriptions: {e}")

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

    async def _refresh_cache_if_needed(self):
        """Refresh the in-memory watchlist cache if TTL has expired."""
        if time.time() - self._cache_timestamp < self._CACHE_TTL:
            return
        try:
            async with self.db.session() as session:
                stmt = (
                    select(Watchlist, User.telegram_id, User.notify_dm, User.username)
                    .join(User, Watchlist.user_id == User.id)
                    .where(Watchlist.market == "US")
                )
                res = await session.execute(stmt)
                self._watchlist_cache = res.all()
            self._cache_timestamp = time.time()
            logger.debug(f"Sniper cache refreshed: {len(self._watchlist_cache)} watchlist items")
        except Exception as e:
            logger.error(f"Failed to refresh sniper cache: {e}")

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
            await self._refresh_cache_if_needed()
            
            # Filter from cache instead of querying DB
            matching_rows = [
                (item, tg_id, notify_dm, uname)
                for item, tg_id, notify_dm, uname in self._watchlist_cache
                if item.symbol and item.symbol.upper() == symbol.upper()
            ]

            for item, telegram_id, notify_dm, username in matching_rows:
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
                        # Send actual Telegram notification
                        await self._send_notification(
                            telegram_id=telegram_id,
                            username=username,
                            notify_dm=notify_dm,
                            symbol=symbol,
                            price=price,
                            msg=msg,
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
                                # Send actual Telegram notification
                                fallback_msg = f"🎯 {symbol} ถึงราคาเป้าหมาย ${target:,.2f} แล้ว! ราคาปัจจุบัน ${price:,.2f}"
                                await self._send_notification(
                                    telegram_id=telegram_id,
                                    username=username,
                                    notify_dm=notify_dm,
                                    symbol=symbol,
                                    price=price,
                                    msg=fallback_msg,
                                )
                            break
        except Exception as e:
            logger.error(f"Error checking target triggers for {symbol}: {e}", exc_info=True)

    async def _send_notification(
        self,
        telegram_id: int,
        username: str | None,
        notify_dm: bool,
        symbol: str,
        price: float,
        msg: str,
    ):
        """Send notification to user via DM or broadcast channel."""
        if not self.bot:
            logger.warning(f"No bot instance available to send notification to user {telegram_id}")
            return

        notification_text = (
            f"🔔 **แจ้งเตือนราคาเป้าหมาย!**\n\n"
            f"📊 **{symbol}** — ราคาปัจจุบัน: **${price:,.2f}**\n\n"
            f"{msg}"
        )

        try:
            if notify_dm:
                # Send private DM to user
                await self.bot.send_message(
                    chat_id=telegram_id,
                    text=notification_text,
                    parse_mode="Markdown",
                )
                logger.info(f"Sent DM notification to user {telegram_id} for {symbol}")
            else:
                # Send to broadcast channel with user tag
                if self.broadcast_channel_id:
                    mention = f"@{username}" if username else f"[User](tg://user?id={telegram_id})"
                    channel_text = f"🏷️ {mention}\n{notification_text}"
                    await self.bot.send_message(
                        chat_id=self.broadcast_channel_id,
                        text=channel_text,
                        parse_mode="Markdown",
                    )
                    logger.info(f"Sent channel notification tagging user {telegram_id} for {symbol}")
                else:
                    # Fallback to DM if no channel configured
                    await self.bot.send_message(
                        chat_id=telegram_id,
                        text=notification_text,
                        parse_mode="Markdown",
                    )
                    logger.info(f"Fallback DM (no channel) to user {telegram_id} for {symbol}")
        except TelegramForbiddenError:
            logger.warning(f"User {telegram_id} has blocked the bot. Unable to send DM for {symbol}.")
            # Fallback to group channel without tag if needed, or simply pass
        except TelegramAPIError as e:
            logger.error(f"Telegram API Error sending notification to {telegram_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending notification to {telegram_id}: {e}", exc_info=True)


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
