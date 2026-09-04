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


class ScanningMixin:

    async def cmd_scan(self, message: types.Message):
        """Handle /scan [symbol] — run analysis pipeline.

        If symbol provided: scan that specific symbol.
        If no symbol: scan all symbols in user's watchlist.

        Pipeline: fetch → transform → grade → format → reply
        """
        if not message.text or not message.from_user:
            return
        parts = message.text.strip().split()
        symbols: list[str] = []
        if len(parts) >= 2:
            symbols = [p.upper().replace(',', '') for p in parts[1:] if p.
                strip()]
        else:
            telegram_id = message.from_user.id
            async with self.db.session() as session:
                stmt = select(Watchlist.symbol).join(User, Watchlist.
                    user_id == User.id).where(User.telegram_id == telegram_id)
                res = await session.execute(stmt)
                symbols = list(res.scalars().all())
        if not symbols:
            await message.reply(
                """⚠️ Watchlist is empty and no symbol provided.
Specify a symbol to scan (e.g. /scan NVDA) or add stocks to your watchlist with /add <symbol> <market>."""
                )
            return
        status_msg = await message.reply(
            f"""🔍 เริ่มสแกน {len(symbols)} หุ้น: {', '.join(symbols)}
`[░░░░░░░░░░░░] 0%`
👉 กำลังดึงข้อมูลตลาด..."""
            )

        def make_pb(pct: int, length: int=12):
            f = int(pct / 100.0 * length)
            return '█' * f + '░' * (length - f)
        loop = asyncio.get_running_loop()
        await self._throttled_edit(status_msg,
            f"""🔍 กำลังสแกน...
`[{make_pb(10)}] 10%`
👉 กำลังเชื่อมต่อตลาดดึงข้อมูล {len(symbols)} หุ้นพร้อมกัน..."""
            )
        snapshots = await loop.run_in_executor(None, self.fetcher.fetch,
            symbols)
        await self._throttled_edit(status_msg,
            f"""🔍 กำลังสแกน...
`[{make_pb(50)}] 50%`
👉 โหลดข้อมูลเสร็จสิ้น กำลังเตรียมวิเคราะห์..."""
            )
        if not snapshots:
            await status_msg.edit_text(
                f"❌ Failed to fetch market data for: {', '.join(symbols)}")
            return
        await self._throttled_edit(status_msg,
            f"""🔍 กำลังสแกน...
`[{make_pb(70)}] 70%`
👉 กำลังประมวลผล Technical Indicators..."""
            )
        enriched_signals = self.transformer.enrich(snapshots)
        await self._throttled_edit(status_msg,
            f"""🔍 กำลังสแกน...
`[{make_pb(90)}] 90%`
👉 กำลังประเมินร่วมกับ Risk Profile..."""
            )
        risk_profile = None
        async with self.db.session() as session:
            stmt = select(User).where(User.telegram_id == message.from_user.id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            if user:
                risk_profile = user.risk_profile
        for symbol, enriched in enriched_signals.items():
            grade_result = self.grader.grade(enriched, risk_profile=
                risk_profile)
            async with self.db.session() as session:
                signal_entry = Signal(symbol=grade_result.symbol, grade=
                    grade_result.score, confidence=grade_result.confidence,
                    advice=grade_result.advice)
                session.add(signal_entry)
                await session.commit()
            snapshot = enriched.snapshot
            reasons_str = '\n'.join(f'  • {r}' for r in grade_result.reasons
                ) if grade_result.reasons else '  • N/A'
            targets_str = '\n'.join(f'  • ${t}' for t in grade_result.
                buy_targets) if getattr(grade_result, 'buy_targets', None
                ) else '  • N/A'
            conf = grade_result.confidence
            filled = int(conf / 10)
            empty = 10 - filled
            bar = '█' * filled + '░' * empty
            score_val = max(1, min(10, grade_result.score))
            score_bar = '█' * score_val + '░' * (10 - score_val)
            try:
                news_teaser = await self.news_service.get_scan_teaser(
                    grade_result.symbol)
                news_teaser_text = f'\n\n{news_teaser}' if news_teaser else ''
            except Exception as e:
                logger.error(
                    f'Failed to fetch news teaser for {grade_result.symbol}: {e}'
                    )
                news_teaser_text = ''
            username = message.from_user.username
            mention = (f'@{username}' if username else
                f'[{message.from_user.full_name}](tg://user?id={message.from_user.id})'
                )
            report_text = f"""🗣️ **สำหรับ {mention}**
📊 **{grade_result.symbol} Analysis**

🏷️ **Current Price:** ${snapshot.current_price:,.2f}
📉 **ATH Drawdown:** {snapshot.drawdown_pct}%

🤖 **AI Score (ความน่าลงทุน):** {score_val}/10
[{score_bar}]
🎯 **Confidence:** {conf}% [{bar}]

💡 **คำแนะนำจาก AI:**
{grade_result.advice}

📌 **จุดสังเกต:**
{reasons_str}

🛒 **ราคาเป้าหมาย (Buy Targets):**
{targets_str}{news_teaser_text}"""
            buttons = []
            if getattr(grade_result, 'buy_targets', None):
                for idx, t in enumerate(grade_result.buy_targets):
                    buttons.append([InlineKeyboardButton(text=
                        f'[ ] ${t:,.2f}', callback_data=
                        f'tgt_toggle_{grade_result.symbol}_{idx}')])
                buttons.append([InlineKeyboardButton(text=
                    '🎯 ยืนยันเป้าหมาย', callback_data=
                    f'tgt_confirm_{grade_result.symbol}'),
                    InlineKeyboardButton(text='❌ ยังไม่สนใจ / ข้าม',
                    callback_data=f'tgt_dismiss_{grade_result.symbol}')])
            buttons.append([InlineKeyboardButton(text=
                '📖 เจาะลึกบทวิเคราะห์ (Deep Dive)', callback_data=
                f'insight_{grade_result.symbol}')])
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons
                ) if buttons else None
            try:
                await message.reply(report_text, parse_mode='Markdown',
                    reply_markup=keyboard)
            except Exception as e:
                logger.error(
                    f'Markdown parse error in scan: {e}. Falling back to plain text.'
                    )
                await message.reply(report_text, reply_markup=keyboard)
            if getattr(grade_result, 'buy_targets', None) and getattr(snapshot,
                'current_price', None):
                try:
                    from src.charting import ChartGenerator
                    from aiogram.types import BufferedInputFile
                    chart_bytes = await asyncio.to_thread(ChartGenerator.
                        generate_target_chart, grade_result.symbol,
                        snapshot.current_price, grade_result.buy_targets)
                    if chart_bytes:
                        photo = BufferedInputFile(chart_bytes, filename=
                            f'{grade_result.symbol}_chart.png')
                        await message.answer_photo(photo=photo, caption=
                            f'📊 **{grade_result.symbol} Target Zones Chart**',
                            parse_mode='Markdown')
                except Exception as err:
                    logger.error(
                        f'Failed to generate target chart for {grade_result.symbol}: {err}'
                        )
            await session.commit()
        try:
            await status_msg.delete()
        except Exception:
            pass

    async def tgt_toggle(self, callback: types.CallbackQuery):
        """Toggle [ ] and [✅] selection on target buttons."""
        await callback.answer()
        markup = callback.message.reply_markup
        if not markup:
            return
        for row in markup.inline_keyboard:
            for btn in row:
                if btn.callback_data == callback.data:
                    if btn.text.startswith('[ ]'):
                        btn.text = btn.text.replace('[ ]', '[✅]', 1)
                    elif btn.text.startswith('[✅]'):
                        btn.text = btn.text.replace('[✅]', '[ ]', 1)
        await callback.message.edit_reply_markup(reply_markup=markup)

    async def tgt_confirm(self, callback: types.CallbackQuery):
        """Confirm selected target prices and add to watchlist for AlpacaSniper."""
        await callback.answer()
        symbol = callback.data.split('tgt_confirm_')[1]
        markup = callback.message.reply_markup
        if not markup:
            return
        selected_prices = []
        for row in markup.inline_keyboard:
            for btn in row:
                if btn.text.startswith('[✅]'):
                    try:
                        price_str = btn.text.split('$')[1].replace(',', ''
                            ).strip()
                        selected_prices.append(float(price_str))
                    except (IndexError, ValueError):
                        pass
        if not selected_prices:
            await callback.message.answer(
                f'⚠️ คุณยังไม่ได้เลือกเป้าหมายสำหรับ {symbol} เลยครับ (แตะปุ่มเพื่อเลือกก่อนกด ยืนยัน)'
                )
            return
        telegram_id = callback.from_user.id
        username = callback.from_user.username
        market = 'TH' if symbol.endswith('.BK') else 'US'
        res_text = await self._add_to_watchlist(telegram_id, username,
            symbol, market, selected_prices)
        if self.sniper and self.sniper.running:
            await self.sniper.update_subscriptions()
        prices_formatted = ', '.join(f'${p:,.2f}' for p in selected_prices)
        pref_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text='📩 แจ้งเตือนทาง DM ส่วนตัว (แนะนำ)',
            callback_data='notify_pref_dm')], [InlineKeyboardButton(text=
            '📢 แจ้งเตือนในกลุ่ม (@tag)', callback_data='notify_pref_group')]])
        await callback.message.reply(
            f"""🎯 **อนุมัติเป้าหมายเรียบร้อย!**

บันทึกราคาเป้าหมายของ **{symbol}** ({prices_formatted}) เข้าระบบ Sniper เรียบร้อยแล้วครับ 🚀

⚙️ **ตั้งค่าการแจ้งเตือน**:
เมื่อราคาถึงเป้าหมาย คุณต้องการให้บอทแจ้งเตือนแบบไหน?"""
            , reply_markup=pref_keyboard)

    async def tgt_dismiss(self, callback: types.CallbackQuery):
        """Dismiss target selection buttons to keep chat clean."""
        await callback.answer('ข้ามการตั้งราคาเป้าหมายแล้ว')
        symbol = callback.data.split('tgt_dismiss_')[1]
        buttons = [[InlineKeyboardButton(text=
            '📖 เจาะลึกบทวิเคราะห์ (Deep Dive)', callback_data=
            f'insight_{symbol}')]]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await callback.message.edit_reply_markup(reply_markup=keyboard)
        except Exception:
            pass

    async def set_notify_pref(self, callback: types.CallbackQuery):
        """Handle notification preference selection."""
        await callback.answer()
        pref = callback.data.split('notify_pref_')[1]
        notify_dm = pref == 'dm'
        telegram_id = callback.from_user.id
        async with self.db.session() as session:
            stmt = select(User).where(User.telegram_id == telegram_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            if user:
                user.notify_dm = notify_dm
                await session.commit()
        mode_text = 'DM ส่วนตัว' if notify_dm else 'แท็กในกลุ่ม'
        await callback.message.edit_text(
            f"""✅ ตั้งค่าการแจ้งเตือนสำเร็จ!

ต่อไปเมื่อหุ้นถึงเป้าหมาย บอทจะแจ้งเตือนคุณผ่านทาง **{mode_text}** ครับ"""
            , reply_markup=None)

    async def broadcast_scan(self, market: str=None):
        """Run broadcast scan and send to configured channel, personalized by risk profile."""
        if not self.config.broadcast_channel_id:
            logger.info('BROADCAST_CHANNEL_ID not set. Skipping broadcast.')
            return
        async with self.db.session() as session:
            stmt = select(User, Watchlist).join(Watchlist, User.id ==
                Watchlist.user_id)
            if market:
                stmt = stmt.where(Watchlist.market == market)
            res = await session.execute(stmt)
            rows = res.all()
        if not rows:
            logger.info(
                f'No users watching symbols for market {market}. Skipping broadcast.'
                )
            return
        symbol_risk_users = {}
        unique_symbols = set()
        for user, wl in rows:
            symbol = wl.symbol
            unique_symbols.add(symbol)
            rp = user.risk_profile or 'ทั่วไป (ไม่ได้ตั้งค่า)'
            key = symbol, rp
            if key not in symbol_risk_users:
                symbol_risk_users[key] = []
            mention = (f'@{user.username}' if user.username else
                f'User_{user.id}')
            symbol_risk_users[key].append(mention)
        loop = asyncio.get_running_loop()
        snapshots = await loop.run_in_executor(None, self.fetcher.fetch,
            list(unique_symbols))
        if not snapshots:
            return
        enriched = self.transformer.enrich(snapshots)
        bot_user = await self.bot.get_me()
        for (symbol, rp), users in symbol_risk_users.items():
            if symbol not in enriched:
                continue
            signal = enriched[symbol]
            result = self.grader.grade(signal, risk_profile=rp)
            targets_str = '\n'.join(f'  • ${t}' for t in result.buy_targets
                ) if getattr(result, 'buy_targets', None) else '  • N/A'
            conf = result.confidence
            filled = int(conf / 10)
            empty = 10 - filled
            bar = '█' * filled + '░' * empty
            score_val = max(1, min(10, result.score))
            score_bar = '█' * score_val + '░' * (10 - score_val)
            mentions_str = ' '.join(users)
            msg = f"""🗣️ **แจ้งเตือนสำหรับ:** {mentions_str}
📊 **#{symbol} Analysis** (มุมมอง: {rp})

🤖 AI Score: {score_val}/10
[{score_bar}]
🎯 Confidence: {conf}% [{bar}]

💡 Advice:
{result.advice}

🛒 Buy Targets:
{targets_str}"""
            kb = create_add_watchlist_keyboard(symbol, bot_user.username)
            try:
                await self.bot.send_message(self.config.
                    broadcast_channel_id, msg, reply_markup=kb)
            except Exception as e:
                logger.error(
                    f'Failed to send broadcast for {symbol} ({rp}): {e}')

    async def cat_watch_btn(self, callback: types.CallbackQuery):
        """Handle '➕ เพิ่มเข้า Watchlist' button click on Catalyst alert."""
        symbol = callback.data.split('_')[2]
        market = 'TH' if symbol.endswith('.BK') else 'US'
        res_text = await self._add_to_watchlist(callback.from_user.id,
            callback.from_user.username, symbol, market)
        await callback.answer(res_text, show_alert=True)

    async def cat_sniper_btn(self, callback: types.CallbackQuery):
        """Handle '🎯 ตั้งเป้า Sniper' button click on Catalyst alert."""
        symbol = callback.data.split('_')[2]
        await callback.answer(
            f'🎯 พิมพ์ /scan {symbol} เพื่อเลือกราคาเป้าหมายเข้าสู่ Sniper!',
            show_alert=True)

    async def cat_scan_btn(self, callback: types.CallbackQuery):
        """Handle '🔍 สแกน $SYMBOL' button click on Catalyst alert for connected stocks."""
        symbol = callback.data.split('_')[2]
        await callback.answer(f'🔍 กำลังสแกน ${symbol}...')
        if callback.message:
            msg = callback.message
            msg.text = f'/scan {symbol}'
            msg.from_user = callback.from_user
            await self.cmd_scan(msg)

    async def cmd_news(self, message: types.Message):
        """Handle /news [symbol] — full news radar."""
        if not message.text:
            return
        parts = message.text.strip().split()
        if len(parts) < 2:
            await message.reply('⚠️ โปรดระบุชื่อหุ้น เช่น `/news NVDA`',
                parse_mode='Markdown')
            return
        symbol = parts[1].upper().replace(',', '')
        status_msg = await message.reply(
            f'📰 กำลังค้นหาและประมวลผลข่าวทั้งหมดของ {symbol}...')
        try:
            report_text = await self.news_service.get_news_radar(symbol)
            await status_msg.edit_text(report_text, parse_mode='Markdown')
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)[:200]
            
            source = "Unknown"
            if "503" in error_msg or "429" in error_msg or "google" in str(type(e)).lower() or "llmcaller" in error_msg.lower():
                source = "Google Gemini API (AI)"
            elif "asyncpg" in str(type(e)).lower() or "sqlalchemy" in str(type(e)).lower():
                source = "Supabase PostgreSQL (Database)"
            elif "fly" in error_msg.lower():
                source = "Fly.io (Server)"
                
            admin_debug = f"\n\n🚨 **[System Error: {source}]**\n`{error_type}: {error_msg}`"
            
            logger.error(f'Error in /news command for {symbol}: {e}')
            await status_msg.edit_text(
                f'❌ เกิดข้อผิดพลาดในการดึงข้อมูลข่าวของ {symbol}{admin_debug}', parse_mode='Markdown')

    async def cmd_insight(self, message: types.Message):
        """Handle /scan-details <symbol> to generate deep dive report."""
        if not message.text or not message.from_user:
            return
        if not await self._check_cooldown(message.from_user.id, message):
            return
        parts = message.text.strip().split()
        if len(parts) < 2:
            await message.reply('⚠️ กรุณาระบุชื่อหุ้น เช่น /scan-details NVDA')
            return
        symbol = parts[1].upper()
        await self._generate_and_send_insight(message, symbol)

    async def insight_btn(self, callback: types.CallbackQuery):
        """Handle insight inline button click."""
        if not callback.data or '_' not in callback.data:
            await callback.answer('ข้อมูลปุ่มไม่ถูกต้อง', show_alert=True)
            return
        parts = callback.data.split('_')
        if len(parts) < 2:
            await callback.answer('ไม่พบชื่อหุ้น', show_alert=True)
            return
        symbol = parts[1]
        await callback.answer('กำลังเจาะลึกข้อมูลวิเคราะห์...')
        await self._generate_and_send_insight(callback.message, symbol,
            explicit_user=callback.from_user)

    async def _generate_and_send_insight(self, message: types.Message,
        symbol: str, explicit_user: (types.User | None)=None):
        """Generate deep-dive insight report using Multi-Agent Pipeline."""
        status_msg = await message.reply(
            f'⏳ กำลังเริ่ม Multi-Agent Analysis ของ {symbol}...')
        if not self.insight_pipeline:
            await status_msg.edit_text(
                '❌ ระบบ Multi-Agent Pipeline ยังไม่พร้อม (ไม่มี API Key)')
            return
        try:
            await status_msg.edit_text(f'📊 กำลังดึงข้อมูลตลาดของ {symbol}...')
        except Exception:
            pass
        loop = asyncio.get_running_loop()
        snapshots = await loop.run_in_executor(None, self.fetcher.fetch, [
            symbol])
        if symbol not in snapshots:
            await status_msg.edit_text(f'❌ ไม่พบข้อมูลราคาของ {symbol}')
            return
        signals = self.transformer.enrich(snapshots)
        signal = signals.get(symbol)
        loop = asyncio.get_running_loop()
        from src.scrapers.sentiment import get_fear_greed_index
        fear_greed = await loop.run_in_executor(None, get_fear_greed_index)
        try:
            radar_text = await self.news_service.get_news_radar(symbol)
            news_headlines = [f'Pre-Scored News Context:\n{radar_text}']
        except Exception as e:
            logger.error(f'Failed to fetch news radar for Insight: {e}')
            news_headlines = ['(ไม่พบข่าวจากเรดาร์)']
        risk_profile = None
        user_db_id = None
        timeline_str = (
            'ไม่มีประวัติการสแกนเดิมในระบบ (First-time / Cold Start Scan)')
        active_user = explicit_user or message.from_user
        if active_user:
            async with self.db.session() as session:
                stmt = select(User).where(User.telegram_id == active_user.id)
                user = (await session.execute(stmt)).scalar_one_or_none()
                if user:
                    user_db_id = user.id
                    risk_profile = user.risk_profile
                    from src.memory import MemoryManager
                    recent_memory = await MemoryManager.get_recent_timeline(
                        session, user_id=user.id, symbol=symbol, limit=2)
                    timeline_str = MemoryManager.format_timeline_prompt(
                        recent_memory)
        main_loop = asyncio.get_running_loop()

        def make_progress_bar(percent: int, length: int=12) ->str:
            filled = int(percent / 100.0 * length)
            empty = length - filled
            return '█' * filled + '░' * empty

        async def update_progress(stage: str, percent: int=0):
            try:
                bar = make_progress_bar(percent)
                await status_msg.edit_text(
                    f"""⏳ **Deep Dive Analysis:** {symbol}
`[{bar}] {percent}%`

👉 {stage}"""
                    , parse_mode='Markdown')
            except Exception:
                pass

        def sync_progress(stage: str, percent: int=0):
            """Bridge sync callback to async — best effort UI update."""
            try:
                asyncio.run_coroutine_threadsafe(update_progress(stage,
                    percent), main_loop)
            except Exception:
                pass
        try:
            loop = asyncio.get_running_loop()
            report, metadata = await loop.run_in_executor(None, lambda :
                self.insight_pipeline.generate(signal=signal,
                news_headlines=news_headlines, fear_greed=fear_greed,
                risk_profile=risk_profile, timeline_history=timeline_str,
                on_progress=sync_progress))
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)[:200]
            
            source = "Unknown"
            if "503" in error_msg or "429" in error_msg or "google" in str(type(e)).lower() or "llmcaller" in error_msg.lower():
                source = "Google Gemini API (AI)"
            elif "asyncpg" in str(type(e)).lower() or "sqlalchemy" in str(type(e)).lower():
                source = "Supabase PostgreSQL (Database)"
            elif "fly" in error_msg.lower():
                source = "Fly.io (Server)"
                
            admin_debug = f"\n\n🚨 **[System Error: {source}]**\n`{error_type}: {error_msg}`"
            
            logger.error(f'InsightPipeline failed for {symbol}: {e}', exc_info=True)
            await status_msg.edit_text(
                f"❌ Multi-Agent Pipeline ล้มเหลว:\nลองใช้ `/scan {symbol}` แทนได้ครับ{admin_debug}",
                parse_mode='Markdown'
            )
            return
        targets = metadata.get('targets', [])
        price = metadata.get('price', snapshots[symbol].current_price)
        if user_db_id and price:
            try:
                async with self.db.session() as session:
                    from src.memory import MemoryManager
                    targets_joined = ', '.join(f'{t}' for t in targets
                        ) if targets else None
                    await MemoryManager.save_memory_snapshot(session=
                        session, user_id=user_db_id, symbol=symbol, price=
                        float(price), target_prices_str=targets_joined,
                        thesis_status=metadata.get('thesis_status',
                        'CONTINUING'), thesis_summary=metadata.get(
                        'thesis_summary', ''), calibrated_confidence=
                        metadata.get('calibrated_confidence', 80), market=
                        'TH' if symbol.endswith('.BK') else 'US')
            except Exception as mem_err:
                logger.error(
                    f'Failed to persist memory snapshot for {symbol}: {mem_err}'
                    )
        if len(report) > 4000:
            chunks = [report[i:i + 4000] for i in range(0, len(report), 4000)]
            await status_msg.edit_text(chunks[0], parse_mode='Markdown')
            for chunk in chunks[1:]:
                try:
                    await message.reply(chunk, parse_mode='Markdown')
                except Exception:
                    await message.reply(chunk)
        else:
            try:
                await status_msg.edit_text(report, parse_mode='Markdown')
            except Exception as e:
                logger.warning(
                    f'Markdown parse error: {e}. Sending as plain text.')
                await status_msg.edit_text(report)
        if targets and price:
            try:
                from src.charting import ChartGenerator
                from aiogram.types import BufferedInputFile
                chart_bytes = await asyncio.to_thread(ChartGenerator.
                    generate_target_chart, symbol, price, targets)
                if chart_bytes:
                    photo = BufferedInputFile(chart_bytes, filename=
                        f'{symbol}_chart.png')
                    await message.answer_photo(photo=photo, caption=
                        f'📊 **{symbol} Target Zones Deep Dive Chart**',
                        parse_mode='Markdown')
            except Exception as err:
                logger.error(f'Error sending insight chart for {symbol}: {err}'
                    )
