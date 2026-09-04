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


class WatchlistMixin:

    async def _add_to_watchlist(self, telegram_id: int, username: (str |
        None), symbol: str, market: str, target_price: (float | list[float] |
        None)=None) ->str:
        """Helper method to upsert user and add symbol to watchlist."""
        if isinstance(target_price, list):
            target_str = ', '.join(f'{p} (User Target)' for p in target_price
                ) if target_price else None
            price_display = ', '.join(f'${p}' for p in target_price)
        elif target_price is not None:
            target_str = f'{target_price} (User Target)'
            price_display = f'${target_price}'
        else:
            target_str = None
            price_display = ''
        async with self.db.session() as session:
            stmt = select(User).where(User.telegram_id == telegram_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            if not user:
                try:
                    user = User(telegram_id=telegram_id, username=username)
                    session.add(user)
                    await session.commit()
                    await session.refresh(user)
                except Exception as e:
                    await session.rollback()
                    res = await session.execute(stmt)
                    user = res.scalar_one_or_none()
                    if not user:
                        raise e
            stmt_w = select(Watchlist).where(Watchlist.user_id == user.id, 
                Watchlist.symbol == symbol)
            res_w = await session.execute(stmt_w)
            existing = res_w.scalar_one_or_none()
            if existing:
                if target_str:
                    existing.target_zones_str = target_str
                    existing.last_notified_zone = None
                    await session.commit()
                    return f'✅ Updated {symbol} target to {price_display}'
                return (
                    f'ℹ️ Symbol {symbol} ({market}) is already in your watchlist.'
                    )
            else:
                item = Watchlist(user_id=user.id, symbol=symbol, market=
                    market, target_zones_str=target_str)
                session.add(item)
                await session.commit()
                return f'✅ Added {symbol} ({market}) to your watchlist.'

    async def cmd_add(self, message: types.Message):
        """Handle /add <symbol>... — add multiple stocks to user's watchlist.

        Usage: /add NVDA AAPL PTT.BK
        - Creates user if not exists (upsert by telegram_id)
        - Adds symbols to their watchlist
        - Responds with confirmation
        """
        if not message.text or not message.from_user:
            return
        text = message.text.replace('/add', '', 1).strip()
        if not text:
            await message.reply(
                """❌ Usage: /add <symbol1> <symbol2> ...
Example: /add NVDA AAPL PTT.BK"""
                )
            return
        parts = text.replace(',', ' ').split()[1:]
        if not parts:
            return
        telegram_id = message.from_user.id
        username = message.from_user.username
        results = []
        i = 0
        while i < len(parts):
            symbol = parts[i].strip().upper()
            target_price = None
            i += 1
            if i < len(parts):
                try:
                    target_price = float(parts[i])
                    i += 1
                except ValueError:
                    pass
            market = 'TH' if symbol.endswith('.BK') else 'US'
            res_text = await self._add_to_watchlist(telegram_id, username,
                symbol, market, target_price)
            results.append(res_text)
        if self.sniper.running:
            await self.sniper.update_subscriptions()
        await message.reply('\n'.join(results))

    async def cmd_remove(self, message: types.Message):
        """Handle /remove <symbol>... — remove multiple stocks from user's watchlist."""
        if not message.text or not message.from_user:
            return
        text = message.text.replace('/remove', '', 1).strip()
        if not text:
            await message.reply(
                """❌ Usage: /remove <symbol1> <symbol2> ...
Example: /remove NVDA AAPL"""
                )
            return
        symbols = [s.strip().upper() for s in text.replace(',', ' ').split(
            ) if s.strip()]
        telegram_id = message.from_user.id
        results = []
        async with self.db.session() as session:
            stmt = select(Watchlist).join(User, Watchlist.user_id == User.id
                ).where(User.telegram_id == telegram_id, Watchlist.symbol.
                in_(symbols))
            res = await session.execute(stmt)
            found_items = {item.symbol: item for item in res.scalars().all()}
            for symbol in symbols:
                if symbol in found_items:
                    await session.delete(found_items[symbol])
                    results.append(f'🗑️ Removed {symbol} from your watchlist.')
                else:
                    results.append(f'ℹ️ {symbol} is not in your watchlist.')
            await session.commit()
        await message.reply('\n'.join(results))

    async def cmd_list(self, message: types.Message):
        """Handle /list — show user's watchlist."""
        if not message.from_user:
            return
        telegram_id = message.from_user.id
        async with self.db.session() as session:
            stmt = select(Watchlist).join(User, Watchlist.user_id == User.id
                ).where(User.telegram_id == telegram_id)
            res = await session.execute(stmt)
            items = res.scalars().all()
            if not items:
                await message.reply(
                    """📋 Your watchlist is empty.
Add stocks using: /add <symbol> [market]"""
                    )
                return
            lines = [
                '📋 **Your Watchlist & Target Prices (รายการหุ้นและราคาเป้าหมาย):**\n'
                ]
            for item in items:
                if item.target_zones_str:
                    prices = re.findall('(\\d+(?:\\.\\d+)?)', item.
                        target_zones_str)
                    if prices:
                        target_disp = ', '.join(f'${float(p):,.2f}' for p in
                            prices)
                        lines.append(
                            f'• **{item.symbol}** ({item.market}) 🎯 เป้าหมาย: `{target_disp}`'
                            )
                    else:
                        lines.append(
                            f'• **{item.symbol}** ({item.market}) — `{item.target_zones_str}`'
                            )
                else:
                    lines.append(
                        f'• **{item.symbol}** ({item.market}) — *(ไม่มีเป้าหมาย)*'
                        )
            await message.reply('\n'.join(lines), parse_mode='Markdown')
