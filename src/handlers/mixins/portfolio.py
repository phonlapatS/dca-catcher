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


class PortfolioMixin:

    async def handle_photo_slip(self, message: types.Message):
        status = await message.reply('📸 กำลังให้ AI สแกนสลิป...')
        file = await self.bot.get_file(message.photo[-1].file_id)
        img_bytes = await self.bot.download_file(file.file_path)
        api_key = getattr(self.config, 'gemini_api_key', None) or (self.
            config.gemini_api_keys[0] if self.config.gemini_api_keys else '')
        parser = GeminiSlipParser(api_key=api_key)
        if hasattr(img_bytes, 'read'):
            raw_bytes = img_bytes.read()
            if not raw_bytes and hasattr(img_bytes, 'getvalue'):
                raw_bytes = img_bytes.getvalue()
        elif isinstance(img_bytes, bytes):
            raw_bytes = img_bytes
        else:
            raw_bytes = bytes(img_bytes)
        data = await parser.parse_slip(raw_bytes)
        if not data:
            await status.edit_text(
                '❌ ไม่พบข้อมูลการซื้อขายหุ้น US ในรูปนี้ครับ')
            return
        text = f"""🎯 **สแกนสลิปสำเร็จ!**
กรุณาตรวจสอบความถูกต้องก่อนบันทึก:

🛒 **รายการ:** `{data['action']}`
📌 **หุ้น:** `{data['symbol']}`
📦 **จำนวน:** `{data['volume']}` หุ้น
💰 **ราคา:** `${data['price']}`
"""
        try:
            total = float(data['price']) * float(data['volume'])
            text += f'💸 **รวมเป็นเงิน:** `${total:,.2f}`\n\n'
        except Exception:
            text += '\n'
        text += 'ถูกต้องไหมครับ? กดปุ่มด้านล่างเพื่อยืนยัน ⬇️'
        cb_data = (
            f"slip_confirm_{data['symbol']}_{data['action']}_{data['price']}_{data['volume']}"
            )
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text='✅ ยืนยันบันทึก', callback_data=
            cb_data), InlineKeyboardButton(text='❌ ยกเลิก', callback_data=
            'slip_cancel')]])
        await status.edit_text(text, reply_markup=markup, parse_mode='Markdown'
            )

    async def handle_slip_confirm(self, cq: types.CallbackQuery):
        _, _, sym, act, prc, vol = cq.data.split('_')
        user = await self.db.get_user(cq.from_user.id, username=cq.
            from_user.username)
        async with self.db.session() as session:
            txn = PortfolioTransaction(user_id=user.id, symbol=sym, action=
                act, price=float(prc), shares=float(vol))
            session.add(txn)
            await session.commit()
        await cq.message.edit_text(
            f'✅ บันทึก {act} {sym} จำนวน {vol} หุ้น เข้าพอร์ตเรียบร้อยแล้ว!')

    async def handle_slip_cancel(self, cq: types.CallbackQuery):
        await cq.message.edit_text('❌ ยกเลิกการบันทึกสลิปครับ')


    async def cmd_paper_portfolio(self, message: types.Message):
        """Handle /paper_portfolio - View paper trading simulated positions."""
        from src.database import PaperTradeOrder, User
        from sqlalchemy import select
        
        async with self.db.session() as session:
            stmt = select(User).where(User.telegram_id == message.from_user.id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            
            if not user:
                await message.reply("ไม่พบข้อมูลผู้ใช้")
                return
                
            stmt = select(PaperTradeOrder).where(PaperTradeOrder.user_id == user.id, PaperTradeOrder.status == "accepted")
            res = await session.execute(stmt)
            orders = res.scalars().all()
            
        if not orders:
            await message.reply("📝 ยังไม่มีประวัติการเทรดจำลอง (Paper Trade) ผ่านบอทครับ\n\n(บอทจะยิงออเดอร์จำลองให้อัตโนมัติเมื่อราคาชนแนวรับ Sniper ของคุณ)")
            return
            
        # Group by symbol
        positions = {}
        for o in orders:
            if o.symbol not in positions:
                positions[o.symbol] = {"qty": 0.0, "total_cost": 0.0}
            if o.side == "buy":
                positions[o.symbol]["qty"] += o.qty
                positions[o.symbol]["total_cost"] += o.qty * (o.filled_price or 0.0)
                
        msg = "💼 **พอร์ตเทรดจำลอง (Paper Trading)**\n\n"
        
        # Fetch current prices
        unique_symbols = list(positions.keys())
        loop = asyncio.get_running_loop()
        snapshots = await loop.run_in_executor(None, self.fetcher.fetch, unique_symbols)
        
        total_value = 0.0
        total_cost_all = 0.0
        
        for sym, pos in positions.items():
            if pos["qty"] <= 0:
                continue
                
            avg_price = pos["total_cost"] / pos["qty"]
            curr_price = snapshots[sym].current_price if snapshots and sym in snapshots else avg_price
            val = pos["qty"] * curr_price
            
            total_value += val
            total_cost_all += pos["total_cost"]
            
            pnl = val - pos["total_cost"]
            pnl_pct = (pnl / pos["total_cost"]) * 100 if pos["total_cost"] > 0 else 0
            
            icon = "🟢" if pnl >= 0 else "🔴"
            msg += f"🔹 **{sym}**\n"
            msg += f"   • จำนวน: {pos['qty']} หุ้น (ต้นทุนเฉลี่ย ${avg_price:,.2f})\n"
            msg += f"   • มูลค่าปัจจุบัน: ${val:,.2f} ({icon} {pnl_pct:+.2f}%)\n\n"
            
        total_pnl = total_value - total_cost_all
        total_pnl_pct = (total_pnl / total_cost_all) * 100 if total_cost_all > 0 else 0
        main_icon = "🟩" if total_pnl >= 0 else "🟥"
        
        msg += f"**=== สรุปภาพรวม ===**\n"
        msg += f"💰 **Total Cost:** ${total_cost_all:,.2f}\n"
        msg += f"💵 **Total Value:** ${total_value:,.2f}\n"
        msg += f"📈 **Total P/L:** {main_icon} **${total_pnl:,.2f} ({total_pnl_pct:+.2f}%)**"
        
        await message.reply(msg, parse_mode='Markdown')


    async def cmd_portfolio(self, message: types.Message):
        user = await self.db.get_user(message.from_user.id)
        status = await message.reply(
            '⏳ กำลังคำนวณต้นทุนพอร์ตและดึงราคาตลาดสด...')
        async with self.db.session() as session:
            res = await session.execute(select(PortfolioTransaction).where(
                PortfolioTransaction.user_id == user.id))
            txns = res.scalars().all()
        if not txns:
            await status.edit_text(
                'พอร์ตคุณยังว่างเปล่า! โยนรูปสลิปแอปเทรดเข้ามาเพื่อเริ่มบันทึกพอร์ตได้เลยครับ'
                )
            return
        portfolio = {}
        for t in txns:
            if t.symbol not in portfolio:
                portfolio[t.symbol] = {'shares': 0, 'total_cost': 0}
            if t.action == 'BUY':
                portfolio[t.symbol]['shares'] += t.shares
                portfolio[t.symbol]['total_cost'] += t.price * t.shares
            elif t.action == 'SELL':
                if portfolio[t.symbol]['shares'] > 0:
                    avg_cost = portfolio[t.symbol]['total_cost'] / portfolio[t
                        .symbol]['shares']
                    portfolio[t.symbol]['total_cost'] -= avg_cost * min(t.
                        shares, portfolio[t.symbol]['shares'])
                portfolio[t.symbol]['shares'] -= t.shares
        lines = ['💼 **สรุปพอร์ต DCA ของคุณ**\n```', '━━━━━━━━━━━━━━━━━━━━━━━']
        for sym, data in portfolio.items():
            if data['shares'] <= 0:
                continue
            avg_cost = data['total_cost'] / data['shares']
            live_price = await self.fetcher.fetch_current_price(sym)
            pnl_pct = (live_price - avg_cost) / avg_cost * 100
            emoji = '🟢' if pnl_pct >= 0 else '🔴'
            sign = '+' if pnl_pct >= 0 else ''
            lines.append(f"📌 {sym} | {data['shares']:,.2f} หุ้น")
            lines.append(f'   ต้นทุน:  ${avg_cost:,.2f}')
            lines.append(f'   ปัจจุบัน: ${live_price:,.2f}')
            lines.append(f'   P/L:    {emoji} {sign}{pnl_pct:.2f}%')
            lines.append('━━━━━━━━━━━━━━━━━━━━━━━')
        lines.append('```')
        if len(lines) == 3:
            await status.edit_text(
                'พอร์ตคุณยังว่างเปล่า! โยนรูปสลิปแอปเทรดเข้ามาเพื่อเริ่มบันทึกพอร์ตได้เลยครับ'
                )
            return
        await status.edit_text('\n'.join(lines), parse_mode='Markdown')
