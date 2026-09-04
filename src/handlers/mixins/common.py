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


class CommonMixin:

    async def cmd_start(self, message: types.Message, command: (
        CommandObject | None)=None):
        """Handle /start — welcome message, user registration, and deep links."""
        if not message.from_user:
            return
        telegram_id = message.from_user.id
        username = message.from_user.username
        async with self.db.session() as session:
            stmt = select(User).where(User.telegram_id == telegram_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            if not user:
                user = User(telegram_id=telegram_id, username=username)
                session.add(user)
                await session.commit()
        if message.chat.type in ['group', 'supergroup']:
            bot_info = await self.bot.get_me()
            dm_link = f'https://t.me/{bot_info.username}?start=dm_setup'
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text='👉 เปิดแชทส่วนตัว (DM) กับบอท',
                url=dm_link)]])
            await message.reply(
                f"""👋 สวัสดีครับ @{username or 'สมาชิก'}!
เพื่อให้บอทสามารถแจ้งเตือนราคาหุ้นให้คุณทาง **DM ส่วนตัว** ได้โดยตรง รบกวนกดปุ่มด้านล่างเพื่อเปิดแชทและกด **Start** หนึ่งครั้งนะครับ 🚀"""
                , reply_markup=keyboard)
            return
        if command and command.args and command.args.startswith('add_'):
            symbol = command.args.split('_', 1)[1].upper()
            market = 'TH' if symbol.endswith('.BK') else 'US'
            await message.answer(f'⏳ Adding {symbol} to your watchlist...')
            res_text = await self._add_to_watchlist(telegram_id, username,
                symbol, market)
            await message.answer(res_text)
            return
        welcome_text = """👋 Welcome to DCA Catcher Bot!
ยินดีต้อนรับสู่ระบบวิเคราะห์หุ้นสำหรับ DCA ด้วย AI

ตอนนี้บอทพร้อมที่จะแจ้งเตือนคุณผ่านทาง DM แล้วครับ! พิมพ์ /help เพื่อดูคำสั่งทั้งหมดที่ใช้งานได้"""
        await message.answer(welcome_text)

    async def cmd_help(self, message: types.Message):
        """Handle /help — display all available commands and their usage."""
        help_text = """📌 **Available Commands (เรียงตามลำดับความสำคัญ):**

🔹 `/survey` - 📝 ทำแบบสอบถามเพื่อตั้งค่า Profile ความเสี่ยงของคุณ (แนะนำให้ทำเป็นอันดับแรก)
🔹 `/advice` - 🌟 ให้ AI ช่วยหาและจัดพอร์ตหุ้นแบบเจาะลึกเฉพาะคุณ
🔹 `/add <ชื่อหุ้น> [ตลาด]` - ➕ เพิ่มหุ้นเข้า Watchlist เพื่อให้ AI ช่วยเตือนทุกวัน
   *(ตัวอย่าง: /add NVDA US หรือ /add PTT.BK TH)*
🔹 `/list` - 📋 ดูรายชื่อหุ้นทั้งหมดที่คุณติดตามอยู่ (Watchlist)
🔹 `/portfolio` - 💼 สรุปพอร์ตหุ้น DCA และคำนวณกำไร/ขาดทุน (PnL)
🔹 `/scan` - 🔍 สั่ง AI ให้วิเคราะห์พอร์ตหุ้น **ทุกตัว** ใน Watchlist ทันที
🔹 `/scan <ชื่อหุ้น>` - 🔍 สั่ง AI ให้วิเคราะห์หุ้น **เฉพาะตัวที่ระบุ**
   *(ตัวอย่าง: /scan TSLA)*
🔹 `/scan-details <ชื่อหุ้น>` - 🧬 บทวิเคราะห์เจาะลึกปัจจัยพื้นฐานและข่าว
🔹 `/news` หรือ `/hotnews` - 🛰️ เปิดเรดาร์จับข่าวด่วนของหุ้นในพอร์ตทั้งหมด
🔹 `/remove <ชื่อหุ้น>` - 🗑️ ลบหุ้นออกจาก Watchlist
🔹 `/help` - ❓ แสดงรายการคำสั่งทั้งหมด
🔹 `/start` - 🚀 เริ่มต้นใช้งานบอท"""
        await message.answer(help_text, parse_mode='Markdown')
