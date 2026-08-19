import asyncio
import logging
from aiohttp import web
from src.config import Config
from src.insight_pipeline import InsightPipeline

logger = logging.getLogger(__name__)

class WebhookServer:
    def __init__(self, config: Config, pipeline: InsightPipeline, bot, broadcast_channel_id: str):
        self.config = config
        self.pipeline = pipeline
        self.bot = bot
        self.broadcast_channel_id = broadcast_channel_id

    async def handle_webhook(self, request: web.Request):
        """Handles incoming TradingView webhooks."""
        secret = request.match_info.get('secret')
        
        # 1. Validate Secret
        if secret != self.config.webhook_secret:
            logger.warning("Unauthorized webhook access attempt.")
            return web.Response(status=403, text="Forbidden")

        try:
            data = await request.json()
            raw_symbol = data.get("symbol") or data.get("ticker") or data.get("sym")
            message = data.get("message") or data.get("action") or data.get("alert") or "TradingView Signal"
            
            if not raw_symbol:
                return web.Response(status=400, text="Missing symbol or ticker in payload")

            # Clean exchange prefix (e.g., "NASDAQ:NVDA" -> "NVDA", "SET:PTT" -> "PTT.BK")
            if ":" in str(raw_symbol):
                exchange, sym = str(raw_symbol).split(":", 1)
                if exchange.upper() in ("SET", "BKK") and not sym.endswith(".BK"):
                    symbol = f"{sym}.BK".upper()
                else:
                    symbol = sym.upper()
            else:
                symbol = str(raw_symbol).upper()

            logger.info(f"Received webhook for {symbol} (raw: {raw_symbol}): {message}")
            
            # 2. Schedule background task to avoid blocking the 3-second TV window
            asyncio.create_task(self.process_alert(symbol, message))
            
            # 3. Immediately return 200 OK
            return web.Response(status=200, text="OK")
            
        except Exception as e:
            logger.error(f"Error parsing webhook JSON: {e}")
            return web.Response(status=400, text="Bad Request")

    async def process_alert(self, symbol: str, message: str):
        """Runs the data fetch + AI pipeline and sends the result to Telegram."""
        try:
            symbol = symbol.upper()
            logger.info(f"Processing webhook alert for {symbol}...")
            
            # 1. Fetch market data snapshot
            snapshots = self.bot.fetcher.fetch([symbol])
            if not snapshots or symbol not in snapshots:
                logger.warning(f"Could not fetch market snapshot for {symbol}")
                await self.bot.bot.send_message(
                    chat_id=self.broadcast_channel_id,
                    text=f"🚨 **TradingView Alert:** {message}\n⚠️ Symbol: `{symbol}` (ไม่พบข้อมูลราคาตลาด)",
                    parse_mode="Markdown"
                )
                return

            enriched_signals = self.bot.transformer.enrich(snapshots)
            enriched = enriched_signals.get(symbol)
            if not enriched:
                logger.warning(f"Failed to enrich signal for {symbol}")
                return

            # 2. Grade signal
            grade_result = self.bot.grader.grade(enriched)
            snapshot = enriched.snapshot

            # 3. Format message
            targets_str = (
                "\n".join(f"  • ${t:,.2f}" for t in grade_result.buy_targets)
                if getattr(grade_result, "buy_targets", None)
                else "  • N/A"
            )
            reasons_str = (
                "\n".join(f"  • {r}" for r in grade_result.reasons)
                if grade_result.reasons
                else "  • N/A"
            )

            alert_text = (
                f"🚨 **TradingView Alert Triggered!**\n"
                f"📌 **Signal:** {message}\n"
                f"📊 **{symbol} Analysis**\n\n"
                f"🏷️ **Current Price:** ${snapshot.current_price:,.2f}\n"
                f"🤖 **AI Score:** {grade_result.score}/10 | **Confidence:** {grade_result.confidence}%\n\n"
                f"💡 **คำแนะนำจาก AI:**\n{grade_result.advice}\n\n"
                f"📌 **เหตุผล:**\n{reasons_str}\n\n"
                f"🛒 **ราคาเป้าหมาย (Buy Targets):**\n{targets_str}"
            )

            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            bot_user = await self.bot.bot.get_me()
            buttons = [
                [InlineKeyboardButton(text="📖 เจาะลึกบทวิเคราะห์ (Deep Dive)", callback_data=f"insight_{symbol}")],
                [InlineKeyboardButton(text=f"➕ ติดตาม #{symbol}", url=f"https://t.me/{bot_user.username}?start=add_{symbol}")]
            ]
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

            # 4. Send text analysis first
            await self.bot.bot.send_message(
                chat_id=self.broadcast_channel_id,
                text=alert_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )

            # 5. Generate and send chart right after text if targets exist
            if getattr(grade_result, "buy_targets", None) and getattr(snapshot, "current_price", None):
                try:
                    from src.charting import ChartGenerator
                    from aiogram.types import BufferedInputFile
                    
                    chart_bytes = ChartGenerator.generate_target_chart(
                        symbol=symbol,
                        current_price=snapshot.current_price,
                        targets=grade_result.buy_targets
                    )
                    if chart_bytes:
                        photo = BufferedInputFile(chart_bytes, filename=f"{symbol}_alert.png")
                        await self.bot.bot.send_photo(
                            chat_id=self.broadcast_channel_id,
                            photo=photo,
                            caption=f"📊 **{symbol} TradingView Signal Chart**",
                            parse_mode="Markdown"
                        )
                except Exception as err:
                    logger.error(f"Error sending webhook chart for {symbol}: {err}")
                
        except Exception as e:
            logger.error(f"Failed to process alert for {symbol}: {e}", exc_info=True)

    async def start(self):
        """Starts the aiohttp runner."""
        app = web.Application()
        app.router.add_post('/webhook/{secret}', self.handle_webhook)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.config.webhook_port)
        await site.start()
        logger.info(f"Webhook server started on port {self.config.webhook_port}")
