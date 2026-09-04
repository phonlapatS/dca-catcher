import asyncio
import logging
import re
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ErrorEvent
from aiogram.utils.token import TokenValidationError, validate_token
from sqlalchemy import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.config import Config
from src.database import Database, Signal, User, Watchlist, PortfolioTransaction
from src.fetcher import MarketDataFetcher
from src.grader import SignalGrader
from src.sniper import AlpacaSniper
from src.transform import DataTransformer
from src.catalyst.hunter import CatalystHunter
from src.slip_parser import GeminiSlipParser
logger = logging.getLogger(__name__)
async def global_error_handler(event: ErrorEvent):
    logger.error(f'Critical Global Error: {event.exception}', exc_info=True)
    if event.update.message:
        try:
            await event.update.message.reply(
                f"""⚠️ **ขออภัย เกิดข้อผิดพลาดในระบบหลังบ้าน (System Error)**
```text
{type(event.exception).__name__}: {str(event.exception)[:100]}...
```
ระบบได้บันทึก Log นี้ไว้แล้ว กรุณาลองใหม่อีกครั้งครับ"""
                , parse_mode='Markdown')
        except Exception:
            pass
    try:
        if event.update.bot:
            admin_id = 8942457900
            error_msg = f"""🚨 **[ADMIN ALERT] System Crash Detected!** 🚨
**Error:** `{type(event.exception).__name__}`
**Details:** `{str(event.exception)}`
"""
            if event.update.message:
                error_msg += (
                    f'**Triggered by User:** {event.update.message.from_user.id}\n'
                    )
                error_msg += f'**Message:** {event.update.message.text}\n'
            await event.update.bot.send_message(chat_id=admin_id, text=
                error_msg, parse_mode='Markdown')
    except Exception as e:
        logger.error(f'Failed to send alert to admin: {e}')
GRADE_EMOJIS = {(1): '🔴', (2): '🟡', (3): '🟢', (4): '🌟'}
GRADE_LABELS = {(1): 'Risky (มีความเสี่ยงสูง)', (2): 'Moderate (ถือ/รอดู)',
    (3): 'Low Risk (เหมาะแก่การ DCA)', (4): 'Strong Buy (สัญญาณซื้อแข็งแกร่ง)'}
def create_add_watchlist_keyboard(symbol: str, bot_username: str
    ) ->InlineKeyboardMarkup:
    """Create an inline keyboard with a deep link to add a symbol to watchlist."""
    url = f'https://t.me/{bot_username}?start=add_{symbol}'
    keyboard = [[InlineKeyboardButton(text=f'➕ Add {symbol} to Watchlist',
        url=url)]]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
class RiskSurvey(StatesGroup):
    waiting_for_style = State()
    waiting_for_drawdown = State()
class AdviceSurvey(StatesGroup):
    waiting_for_horizon = State()
    waiting_for_goal = State()
    waiting_for_sector = State()
    waiting_for_subsector = State()
    waiting_for_count = State()
    waiting_for_budget = State()
    waiting_for_watchlist_decision = State()
ALL_SECTORS = {'sec_tech': '💻 เทคโนโลยี & ซอฟต์แวร์', 'sec_comm':
    '📱 สื่อสาร & บันเทิง', 'sec_health': '🏥 สุขภาพ & การแพทย์', 'sec_fin':
    '🏦 การเงิน & ฟินเทค', 'sec_cons_disc': '🛍️ สินค้าฟุ่มเฟือย & ค้าปลีก',
    'sec_cons_stap': '🛒 สินค้าอุปโภคบริโภคจำเป็น', 'sec_ind':
    '🏭 อุตสาหกรรม & โลจิสติกส์', 'sec_energy_util':
    '⚡ พลังงาน & สาธารณูปโภค', 'sec_re': '🏢 อสังหาริมทรัพย์', 'sec_mat':
    '🧱 วัสดุก่อสร้าง & เหมืองแร่'}
SUBSECTORS = {'💻 เทคโนโลยี & ซอฟต์แวร์': {'sub_tech_semi':
    '🔬 ชิป & เซมิคอนดักเตอร์', 'sub_tech_cloud':
    '☁️ คลาวด์ & โครงสร้างพื้นฐาน', 'sub_tech_cyber':
    '🔒 ไซเบอร์ซีเคียวริตี้', 'sub_tech_ai': '🤖 AI & ซอฟต์แวร์องค์กร',
    'sub_tech_hw': '💻 ฮาร์ดแวร์ & อุปกรณ์'}, '📱 สื่อสาร & บันเทิง': {
    'sub_comm_social': '🌐 โซเชียลมีเดีย', 'sub_comm_stream':
    '🎬 สตรีมมิ่ง & บันเทิง', 'sub_comm_tele': '📡 โทรคมนาคม',
    'sub_comm_game': '🎮 เกมมิ่ง & อีสปอร์ต'}, '🏥 สุขภาพ & การแพทย์': {
    'sub_hlth_pharma': '💊 บริษัทยาขนาดใหญ่', 'sub_hlth_bio':
    '🧬 เทคโนโลยีชีวภาพ', 'sub_hlth_dev': '🔬 อุปกรณ์การแพทย์',
    'sub_hlth_prov': '🏥 ประกันและโรงพยาบาล'}, '🏦 การเงิน & ฟินเทค': {
    'sub_fin_bank': '🏦 ธนาคารพาณิชย์', 'sub_fin_tech':
    '💳 ฟินเทค & เพย์เมนต์', 'sub_fin_ins': '🛡️ ประกันภัย'},
    '🛍️ สินค้าฟุ่มเฟือย & ค้าปลีก': {'sub_disc_ev': '🚗 ยานยนต์ & EV',
    'sub_disc_ecom': '🛒 อีคอมเมิร์ซ', 'sub_disc_travel':
    '✈️ ท่องเที่ยว & โรงแรม', 'sub_disc_lux': '💎 แบรนด์เนมหรู'},
    '🛒 สินค้าอุปโภคบริโภคจำเป็น': {'sub_stap_food': '🍎 อาหาร & เครื่องดื่ม',
    'sub_stap_house': '🧴 ของใช้ในบ้าน', 'sub_stap_retail':
    '🏪 ซูเปอร์มาร์เก็ต'}, '🏭 อุตสาหกรรม & โลจิสติกส์': {'sub_ind_aero':
    '✈️ การบิน & ป้องกันประเทศ', 'sub_ind_space':
    '🚀 อวกาศ & ดาวเทียม (SpaceTech)', 'sub_ind_logi':
    '📦 โลจิสติกส์ & ขนส่ง', 'sub_ind_mach': '⚙️ เครื่องจักร & ก่อสร้าง'},
    '⚡ พลังงาน & สาธารณูปโภค': {'sub_eng_oil':
    '🛢️ พลังงานดั้งเดิม (Oil/Gas)', 'sub_eng_clean': '☀️ พลังงานสะอาด',
    'sub_eng_util': '💧 สาธารณูปโภคพื้นฐาน'}, '🏢 อสังหาริมทรัพย์': {
    'sub_re_data': '💾 Data Center REITs', 'sub_re_logi':
    '🏭 Logistics REITs', 'sub_re_com': '🏢 Commercial REITs', 'sub_re_res':
    '🏠 Residential REITs'}, '🧱 วัสดุก่อสร้าง & เหมืองแร่': {'sub_mat_chem':
    '🧪 เคมีภัณฑ์', 'sub_mat_metal': '⛏️ เหมืองแร่ & โลหะ', 'sub_mat_pkg':
    '📦 บรรจุภัณฑ์'}}
from src.handlers.mixins.common import CommonMixin
from src.handlers.mixins.survey import SurveyMixin
from src.handlers.mixins.watchlist import WatchlistMixin
from src.handlers.mixins.scanning import ScanningMixin
from src.handlers.mixins.portfolio import PortfolioMixin
class DCABot(CommonMixin, SurveyMixin, WatchlistMixin, ScanningMixin,
    PortfolioMixin):
    """Main application class — wires all components and handles Telegram commands."""

    def __init__(self, config: Config):
        self.config = config
        self.db = Database(config.database_url)
        self.fetcher = MarketDataFetcher()
        if not hasattr(self.fetcher, 'fetch_current_price'):

            async def _fetch_current_price(symbol: str) ->float:
                loop = asyncio.get_running_loop()
                snapshots = await loop.run_in_executor(None, self.fetcher.
                    fetch, [symbol])
                if symbol in snapshots:
                    return snapshots[symbol].current_price
                return 0.0
            self.fetcher.fetch_current_price = _fetch_current_price
        self.transformer = DataTransformer()
        self.grader = SignalGrader(config.gemini_api_keys)
        from src.insight_pipeline import InsightPipeline
        try:
            self.insight_pipeline = InsightPipeline(config.gemini_api_keys)
        except ValueError:
            self.insight_pipeline = None
            logger.warning('InsightPipeline disabled: no API keys.')
        self.sniper = AlpacaSniper(db=self.db, api_key=getattr(config,
            'alpaca_api_key', ''), secret_key=getattr(config,
            'alpaca_secret_key', ''), sniper_start_hour=config.
            sniper_start_hour, sniper_start_minute=config.
            sniper_start_minute, sniper_end_hour=config.sniper_end_hour,
            sniper_end_minute=config.sniper_end_minute)
        token = config.telegram_token
        try:
            validate_token(token)
        except TokenValidationError:
            token = '123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11'
        self.bot = Bot(token=token)
        self.sniper.bot = self.bot
        self.sniper.broadcast_channel_id = config.broadcast_channel_id
        self.catalyst_hunter = CatalystHunter(db=self.db, bot=self.bot,
            channel_id=config.broadcast_channel_id, gemini_api_key=config.
            gemini_api_keys[0] if config.gemini_api_keys else None)
        from src.news_service import NewsService
        self.news_service = NewsService(db=self.db, evaluator=self.
            catalyst_hunter.evaluator, providers=self.catalyst_hunter.providers
            )
        self.dp = Dispatcher()
        self._user_cooldowns: dict[int, float] = {}
        self._HEAVY_CMD_COOLDOWN = 60
        self._register_handlers()
        self.dp.errors.register(global_error_handler)

    async def _throttled_edit(self, msg, text: str, min_interval: float=2.0,
        parse_mode: str='Markdown'):
        """Edit message text with throttling to avoid Telegram rate limits."""
        now = time.time()
        last = getattr(msg, '_last_edit_ts', 0)
        if now - last < min_interval:
            return
        try:
            await msg.edit_text(text, parse_mode=parse_mode)
            msg._last_edit_ts = now
        except Exception:
            pass

    async def _check_cooldown(self, user_id: int, message: types.Message
        ) ->bool:
        """Check if user is allowed to use a heavy command. Returns True if allowed."""
        now = time.time()
        last = self._user_cooldowns.get(user_id, 0)
        if now - last < self._HEAVY_CMD_COOLDOWN:
            remaining = int(self._HEAVY_CMD_COOLDOWN - (now - last))
            await message.reply(
                f'⏳ กรุณารอ {remaining} วินาทีก่อนใช้คำสั่งนี้อีกครั้งครับ')
            return False
        self._user_cooldowns[user_id] = now
        return True

    def _register_handlers(self):
        """Register all Telegram command handlers."""
        self.dp.message.register(self.cmd_start, Command('start'))
        self.dp.message.register(self.cmd_add, Command('add'))
        self.dp.message.register(self.cmd_remove, Command('remove'))
        self.dp.message.register(self.cmd_list, Command('list'))
        self.dp.message.register(self.cmd_scan, Command('scan'))
        self.dp.message.register(self.cmd_insight, Command('scan-details'))
        self.dp.message.register(self.cmd_survey, Command('survey'))
        self.dp.message.register(self.cmd_advice, Command('advice'))
        self.dp.message.register(self.cmd_help, Command('help'))
        self.dp.message.register(self.cmd_portfolio, Command('portfolio'))
        self.dp.message.register(self.cmd_news, Command('news', 'hotnews'))
        self.dp.callback_query.register(self.survey_style, RiskSurvey.
            waiting_for_style)
        self.dp.callback_query.register(self.survey_drawdown, RiskSurvey.
            waiting_for_drawdown)
        self.dp.callback_query.register(self.advice_horizon, AdviceSurvey.
            waiting_for_horizon)
        self.dp.callback_query.register(self.advice_goal, AdviceSurvey.
            waiting_for_goal)
        self.dp.callback_query.register(self.advice_sector, AdviceSurvey.
            waiting_for_sector)
        self.dp.callback_query.register(self.advice_subsector, AdviceSurvey
            .waiting_for_subsector)
        self.dp.callback_query.register(self.advice_count, AdviceSurvey.
            waiting_for_count)
        self.dp.callback_query.register(self.advice_budget, AdviceSurvey.
            waiting_for_budget)
        self.dp.callback_query.register(self.advice_add_watchlist, F.data ==
            'advice_add_wl', AdviceSurvey.waiting_for_watchlist_decision)
        self.dp.callback_query.register(self.advice_skip_watchlist, F.data ==
            'advice_skip_wl', AdviceSurvey.waiting_for_watchlist_decision)
        self.dp.callback_query.register(self.tgt_toggle, F.data.startswith(
            'tgt_toggle_'))
        self.dp.callback_query.register(self.tgt_confirm, F.data.startswith
            ('tgt_confirm_'))
        self.dp.callback_query.register(self.tgt_dismiss, F.data.startswith
            ('tgt_dismiss_'))
        self.dp.callback_query.register(self.set_notify_pref, F.data.
            startswith('notify_pref_'))
        self.dp.callback_query.register(self.insight_btn, F.data.startswith
            ('insight_'))
        self.dp.callback_query.register(self.cat_watch_btn, F.data.
            startswith('cat_watch_'))
        self.dp.callback_query.register(self.cat_sniper_btn, F.data.
            startswith('cat_sniper_'))
        self.dp.callback_query.register(self.cat_scan_btn, F.data.
            startswith('cat_scan_'))
        self.dp.message.register(self.handle_photo_slip, F.photo)
        self.dp.callback_query.register(self.handle_slip_confirm, F.data.
            startswith('slip_confirm_'))
        self.dp.callback_query.register(self.handle_slip_cancel, F.data ==
            'slip_cancel')

    async def on_startup(self):
        """Startup lifecycle handler: start background tasks like AlpacaSniper."""
        if self.sniper:
            logger.info('Starting AlpacaSniper background task...')
            await self.sniper.start()

    async def start(self):
        """Initialize database, scheduler, sniper, and start polling."""
        logger.info('Initializing database tables...')
        await self.db.create_tables()
        logger.info('Starting scheduler...')
        self.scheduler = AsyncIOScheduler(timezone='Asia/Bangkok')
        self.scheduler.add_job(self.broadcast_scan, 'cron', hour=self.
            config.broadcast_morning_hour, minute=self.config.
            broadcast_morning_minute)
        self.scheduler.add_job(self.broadcast_scan, 'cron', hour=self.
            config.broadcast_th_hour, minute=self.config.
            broadcast_th_minute, args=['TH'])
        self.scheduler.add_job(self.broadcast_scan, 'cron', hour=self.
            config.broadcast_us_hour, minute=self.config.
            broadcast_us_minute, args=['US'])
        self.scheduler.add_job(self.catalyst_hunter.run_scan_cycle, 'cron',
            hour='17-20', minute='*/2')
        self.scheduler.add_job(self.catalyst_hunter.run_scan_cycle, 'cron',
            hour='8-16', minute='*/30')
        self.scheduler.add_job(self.catalyst_hunter.send_daily_digest,
            'cron', hour=19, minute=0)
        self.scheduler.start()
        await self.on_startup()
        logger.info('Starting Telegram bot polling...')
        await self.dp.start_polling(self.bot)

    async def stop(self):
        """Cleanup: stop sniper and close database connections."""
        if self.sniper:
            logger.info('Stopping AlpacaSniper...')
            await self.sniper.stop()
        logger.info('Closing database connections...')
        await self.db.close()
        await self.bot.session.close()
async def main():
    config = Config.from_env()
    bot = DCABot(config)
    try:
        await bot.start()
    finally:
        await bot.stop()
if __name__ == '__main__':
    asyncio.run(main())
