import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.token import TokenValidationError, validate_token
from sqlalchemy import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.config import Config
from src.database import Database, Signal, User, Watchlist
from src.fetcher import MarketDataFetcher
from src.grader import SignalGrader
from src.transform import DataTransformer

logger = logging.getLogger(__name__)

GRADE_EMOJIS = {
    1: "🔴",
    2: "🟡",
    3: "🟢",
    4: "🌟",
}

GRADE_LABELS = {
    1: "Risky (มีความเสี่ยงสูง)",
    2: "Moderate (ถือ/รอดู)",
    3: "Low Risk (เหมาะแก่การ DCA)",
    4: "Strong Buy (สัญญาณซื้อแข็งแกร่ง)",
}


def create_add_watchlist_keyboard(symbol: str, bot_username: str) -> InlineKeyboardMarkup:
    """Create an inline keyboard with a deep link to add a symbol to watchlist."""
    url = f"https://t.me/{bot_username}?start=add_{symbol}"
    keyboard = [[InlineKeyboardButton(text=f"➕ Add {symbol} to Watchlist", url=url)]]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


class RiskSurvey(StatesGroup):
    waiting_for_style = State()
    waiting_for_drawdown = State()

class AdviceSurvey(StatesGroup):
    waiting_for_horizon = State()
    waiting_for_goal = State()
    waiting_for_sector = State()


class DCABot:
    """Main application class — wires all components and handles Telegram commands."""

    def __init__(self, config: Config):
        self.config = config
        self.db = Database(config.database_url)
        self.fetcher = MarketDataFetcher()
        self.transformer = DataTransformer()
        self.grader = SignalGrader(config.gemini_api_key)

        token = config.telegram_token
        try:
            validate_token(token)
        except TokenValidationError:
            token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"

        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self._register_handlers()

    def _register_handlers(self):
        """Register all Telegram command handlers."""
        self.dp.message.register(self.cmd_start, Command("start"))
        self.dp.message.register(self.cmd_add, Command("add"))
        self.dp.message.register(self.cmd_remove, Command("remove"))
        self.dp.message.register(self.cmd_list, Command("list"))
        self.dp.message.register(self.cmd_scan, Command("scan"))
        self.dp.message.register(self.cmd_survey, Command("survey"))
        self.dp.message.register(self.cmd_advice, Command("advice"))
        self.dp.message.register(self.cmd_help, Command("help"))
        
        # FSM handlers for /survey
        self.dp.callback_query.register(self.survey_style, RiskSurvey.waiting_for_style)
        self.dp.callback_query.register(self.survey_drawdown, RiskSurvey.waiting_for_drawdown)
        
        # FSM handlers for /advice
        self.dp.callback_query.register(self.advice_horizon, AdviceSurvey.waiting_for_horizon)
        self.dp.callback_query.register(self.advice_goal, AdviceSurvey.waiting_for_goal)
        self.dp.callback_query.register(self.advice_sector, AdviceSurvey.waiting_for_sector)

    async def _add_to_watchlist(
        self, telegram_id: int, username: str | None, symbol: str, market: str
    ) -> str:
        """Helper method to upsert user and add symbol to watchlist."""
        async with self.db.session() as session:
            stmt = select(User).where(User.telegram_id == telegram_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()

            if not user:
                user = User(telegram_id=telegram_id, username=username)
                session.add(user)
                await session.commit()
                await session.refresh(user)

            stmt_w = select(Watchlist).where(
                Watchlist.user_id == user.id, Watchlist.symbol == symbol
            )
            res_w = await session.execute(stmt_w)
            existing = res_w.scalar_one_or_none()

            if existing:
                return f"ℹ️ Symbol {symbol} ({market}) is already in your watchlist."
            else:
                item = Watchlist(user_id=user.id, symbol=symbol, market=market)
                session.add(item)
                await session.commit()
                return f"✅ Added {symbol} ({market}) to your watchlist."

    async def cmd_start(self, message: types.Message, command: CommandObject | None = None):
        """Handle /start — welcome message and deep links (e.g. /start add_NVDA)."""
        if command and command.args and command.args.startswith("add_"):
            if not message.from_user:
                return
            symbol = command.args.split("_", 1)[1].upper()
            market = "TH" if symbol.endswith(".BK") else "US"
            await message.answer(f"⏳ Adding {symbol} to your watchlist...")
            res_text = await self._add_to_watchlist(
                message.from_user.id, message.from_user.username, symbol, market
            )
            await message.answer(res_text)
            return

        welcome_text = (
            "👋 Welcome to DCA Catcher Bot!\n"
            "ยินดีต้อนรับสู่ระบบวิเคราะห์หุ้นสำหรับ DCA ด้วย AI\n\n"
            "พิมพ์ /help เพื่อดูคำสั่งทั้งหมดที่ใช้งานได้ครับ"
        )
        await message.answer(welcome_text)

    async def cmd_help(self, message: types.Message):
        """Handle /help — display all available commands and their usage."""
        help_text = (
            "📌 **Available Commands (คำสั่งทั้งหมดที่ใช้งานได้):**\n\n"
            "🔹 `/start` - เริ่มต้นใช้งานบอท และดูคำทักทาย\n"
            "🔹 `/help` - แสดงหน้านี้ (รายการคำสั่งทั้งหมด)\n"
            "🔹 `/add <ชื่อหุ้น> [ตลาด]` - เพิ่มหุ้นเข้า Watchlist ส่วนตัวของคุณ\n"
            "   *(ตัวอย่าง: /add NVDA US หรือ /add PTT.BK TH)*\n"
            "🔹 `/remove <ชื่อหุ้น>` - ลบหุ้นออกจาก Watchlist\n"
            "   *(ตัวอย่าง: /remove NVDA)*\n"
            "🔹 `/list` - ดูรายชื่อหุ้นทั้งหมดใน Watchlist ของคุณ\n"
            "🔹 `/survey` - ทำแบบสอบถามเพื่อตั้งค่า Profile ความเสี่ยงของคุณ\n"
            "🔹 `/advice` - 🌟 ให้ AI ช่วยหาและจัดพอร์ตหุ้น 5 ตัวตามเป้าหมายของคุณ\n"
            "🔹 `/scan` - สั่ง AI ให้วิเคราะห์หุ้น **ทุกตัว** ใน Watchlist\n"
            "🔹 `/scan <ชื่อหุ้น>` - สั่ง AI ให้วิเคราะห์หุ้น **เฉพาะตัวที่ระบุ**\n"
            "   *(ตัวอย่าง: /scan TSLA)*"
        )
        await message.answer(help_text, parse_mode="Markdown")

    async def cmd_survey(self, message: types.Message, state: FSMContext):
        """Start the risk profile survey."""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛡️ ถือยาวเน้นปันผล (Safe & Value)", callback_data="style_safe")],
            [InlineKeyboardButton(text="⚖️ DCA สะสมเรื่อยๆ (Moderate)", callback_data="style_mod")],
            [InlineKeyboardButton(text="🚀 เก็งกำไรระยะสั้น (Aggressive)", callback_data="style_agg")]
        ])
        await message.answer(
            "มาทำความรู้จักสไตล์การลงทุนของคุณกันครับ 📊\nคุณเน้นลงทุนแบบไหน?",
            reply_markup=keyboard
        )
        await state.set_state(RiskSurvey.waiting_for_style)

    async def survey_style(self, callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        style = callback.data.split("_")[1]
        
        style_map = {
            "safe": "เน้นปลอดภัย ซื้อเมื่อถูกมาก",
            "agg": "เก็งกำไร ซื้อเมื่อย่อตัวเล็กน้อย",
            "mod": "DCA ทยอยสะสมเรื่อยๆ"
        }
        await state.update_data(style=style_map.get(style, "DCA"))
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🟢 รับความเสี่ยงได้ต่ำ (ทนติดลบ 1-10%)", callback_data="dd_10")],
            [InlineKeyboardButton(text="🟡 รับความเสี่ยงปานกลาง (ทนติดลบ 11-30%)", callback_data="dd_30")],
            [InlineKeyboardButton(text="🔴 รับความเสี่ยงสูง (ทนติดลบ 30-50%)", callback_data="dd_50")],
            [InlineKeyboardButton(text="⚠️ ไม่มีเงินเย็น (ไม่แนะนำให้ลงทุน DCA)", callback_data="dd_none")]
        ])
        
        await callback.message.edit_text(
            "เยี่ยมครับ! ต่อไปคือแบบประเมินความเสี่ยง (เหมือนที่ธนาคารถามเลยครับ)\n\n"
            "ถ้าราคาหุ้นในพอร์ตร่วงลง คุณสามารถทนเห็นพอร์ตติดลบได้สูงสุดเท่าไหร่ ก่อนจะรู้สึกกังวล?",
            reply_markup=keyboard
        )
        await state.set_state(RiskSurvey.waiting_for_drawdown)

    async def survey_drawdown(self, callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        dd = callback.data.split("_")[1]
        
        data = await state.get_data()
        style = data.get("style")
        
        dd_map = {
            "10": "ต่ำ (ทนติดลบ 1-10%)",
            "30": "ปานกลาง (ทนติดลบ 11-30%)",
            "50": "สูง (ทนติดลบ 30-50%)",
            "none": "ไม่มีเงินเย็น (ผิดหลัก DCA)"
        }
        
        if dd == "none":
            profile = f"สไตล์: {style}, ความเสี่ยง: {dd_map[dd]}"
            msg_reply = (
                f"📝 ระบบบันทึกโปรไฟล์ของคุณแล้วครับ:\n**{profile}**\n\n"
                f"⚠️ **คำแนะนำ:** การลงทุนแบบ DCA ต้องใช้ 'เงินเย็น' ที่สามารถทิ้งไว้ได้นานโดยไม่ต้องรีบใช้ "
                f"หากตอนนี้ยังไม่มีเงินเย็น แนะนำให้เก็บออมเงินสดไว้ก่อนนะครับ หรือถ้าวิเคราะห์หุ้น AI จะให้คำแนะนำแบบระมัดระวังสูงสุดครับ!"
            )
        else:
            profile = f"สไตล์: {style}, รับความเสี่ยงได้: {dd_map[dd]}"
            msg_reply = (
                f"บันทึกเรียบร้อย! 📝 ระบบจำได้แล้วว่าคุณเป็นสาย:\n"
                f"**{profile}**\n\n"
                f"ต่อไปนี้เวลาคุณพิมพ์ /scan AI จะปรับราคาเป้าหมายให้เข้ากับสไตล์ของคุณโดยเฉพาะครับ!"
            )
        
        # Save to DB
        telegram_id = callback.from_user.id
        async with self.db.session() as session:
            stmt = select(User).where(User.telegram_id == telegram_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            if user:
                user.risk_profile = profile
                await session.commit()
        
        await callback.message.edit_text(msg_reply, parse_mode="Markdown")
        await state.clear()

    async def cmd_advice(self, message: types.Message, state: FSMContext):
        """Start the personalized stock recommendation survey."""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏳ 1-3 เดือน (เก็งกำไรระยะสั้นมากๆ)", callback_data="hz_1_3m")],
            [InlineKeyboardButton(text="⌛ 3-6 เดือน (รอบเทรดระยะสั้น-กลาง)", callback_data="hz_3_6m")],
            [InlineKeyboardButton(text="📅 1-3 ปี (ระยะกลาง)", callback_data="hz_1_3y")],
            [InlineKeyboardButton(text="📆 3-5 ปี (ระยะยาว)", callback_data="hz_3_5y")],
            [InlineKeyboardButton(text="🗓️ 5-10 ปีขึ้นไป (เพื่อเกษียณ)", callback_data="hz_5_10y")]
        ])
        await message.answer(
            "🌟 **AI Personalized Stock Matchmaker** 🌟\n\n"
            "เป้าหมายของเงินก้อนนี้ คุณตั้งใจจะนำไปลงทุนและถือไว้นานแค่ไหนครับ?",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        await state.set_state(AdviceSurvey.waiting_for_horizon)
        
    async def advice_horizon(self, callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        hz_map = {
            "hz_1_3m": "1-3 เดือน",
            "hz_3_6m": "3-6 เดือน",
            "hz_1_3y": "1-3 ปี",
            "hz_3_5y": "3-5 ปี",
            "hz_5_10y": "5-10 ปีขึ้นไป"
        }
        await state.update_data(horizon=hz_map.get(callback.data, "1-3 ปี"))
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💸 เน้นปันผล (Dividend Income)", callback_data="gl_div")],
            [InlineKeyboardButton(text="📈 เน้นราคาเติบโต (Capital Gain)", callback_data="gl_grow")],
            [InlineKeyboardButton(text="⚖️ เน้นผสมผสาน (Balanced)", callback_data="gl_bal")]
        ])
        await callback.message.edit_text(
            "สิ่งที่คุณคาดหวังที่สุดจากการถือหุ้นชุดนี้คืออะไรครับ?",
            reply_markup=keyboard
        )
        await state.set_state(AdviceSurvey.waiting_for_goal)
        
    async def advice_goal(self, callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        gl_map = {
            "gl_div": "เน้นปันผล",
            "gl_grow": "เน้นเติบโต",
            "gl_bal": "เน้นผสมผสาน"
        }
        await state.update_data(goal=gl_map.get(callback.data, "เน้นผสมผสาน"))
        await state.update_data(sectors=[]) # Initialize empty list for multiple selections
        
        await self._show_sector_keyboard(callback.message, state)
        await state.set_state(AdviceSurvey.waiting_for_sector)
        
    async def _show_sector_keyboard(self, message: types.Message, state: FSMContext):
        data = await state.get_data()
        sectors = data.get("sectors", [])
        
        # Available sectors
        all_sectors = {
            "sec_tech": "💻 เทคโนโลยี & AI",
            "sec_health": "🏥 สุขภาพ & การแพทย์",
            "sec_def": "🛡️ ของกินของใช้ (Defensive)",
            "sec_energy": "⚡ พลังงาน & สาธารณูปโภค",
            "sec_fin": "🏦 การเงิน & ธนาคาร"
        }
        
        buttons = []
        for key, name in all_sectors.items():
            # Add checkmark if selected
            text = f"✅ {name}" if name in sectors else name
            buttons.append([InlineKeyboardButton(text=text, callback_data=key)])
            
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        count = len(sectors)
        text = (
            f"คุณมีความเชื่อมั่น หรือสนใจในอุตสาหกรรมไหนเป็นพิเศษไหมครับ?\n"
            f"(เลือกมา 3 อันดับแรก - ตอนนี้เลือกแล้ว {count}/3 อันดับ)"
        )
        
        if isinstance(message, types.Message):
            await message.edit_text(text, reply_markup=keyboard)
            
    async def advice_sector(self, callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        
        all_sectors = {
            "sec_tech": "💻 เทคโนโลยี & AI",
            "sec_health": "🏥 สุขภาพ & การแพทย์",
            "sec_def": "🛡️ ของกินของใช้ (Defensive)",
            "sec_energy": "⚡ พลังงาน & สาธารณูปโภค",
            "sec_fin": "🏦 การเงิน & ธนาคาร"
        }
        
        selected_name = all_sectors.get(callback.data)
        if not selected_name:
            return
            
        data = await state.get_data()
        sectors = data.get("sectors", [])
        
        # Toggle selection
        if selected_name in sectors:
            sectors.remove(selected_name)
        else:
            if len(sectors) < 3:
                sectors.append(selected_name)
                
        await state.update_data(sectors=sectors)
        
        if len(sectors) == 3:
            # Reached 3 choices, finish and call AI
            await callback.message.edit_text("⏳ AI กำลังประมวลผลข้อมูลและจัดพอร์ตให้คุณ กรุณารอสักครู่...")
            
            # Fetch risk profile from DB
            telegram_id = callback.from_user.id
            risk_profile = None
            async with self.db.session() as session:
                stmt = select(User).where(User.telegram_id == telegram_id)
                res = await session.execute(stmt)
                user = res.scalar_one_or_none()
                if user:
                    risk_profile = user.risk_profile
                    
            horizon = data.get("horizon")
            goal = data.get("goal")
            
            # Call Grader in a background thread or directly (it uses genai which blocks, but it's ok for now)
            # A better way would be asyncio.to_thread, but we'll just call it here.
            import asyncio
            advice_text = await asyncio.to_thread(
                self.grader.generate_advice,
                risk_profile=risk_profile,
                horizon=horizon,
                goal=goal,
                sectors=sectors
            )
            
            await callback.message.answer(advice_text, parse_mode="Markdown")
            await state.clear()
        else:
            # Re-render keyboard
            await self._show_sector_keyboard(callback.message, state)

    async def cmd_add(self, message: types.Message):
        """Handle /add <symbol> <market> — add stock to user's watchlist.

        Usage: /add NVDA US  or  /add PTT TH
        - Creates user if not exists (upsert by telegram_id)
        - Adds symbol+market to their watchlist
        - Responds with confirmation
        """
        if not message.text or not message.from_user:
            return

        parts = message.text.strip().split()
        if len(parts) < 2:
            await message.reply(
                "❌ Usage: /add <symbol> [market]\n"
                "Example: /add NVDA US or /add PTT.BK TH"
            )
            return

        symbol = parts[1].upper()
        market = parts[2].upper() if len(parts) >= 3 else ("TH" if symbol.endswith(".BK") else "US")

        telegram_id = message.from_user.id
        username = message.from_user.username

        res_text = await self._add_to_watchlist(telegram_id, username, symbol, market)
        await message.reply(res_text)

    async def cmd_remove(self, message: types.Message):
        """Handle /remove <symbol> — remove stock from user's watchlist."""
        if not message.text or not message.from_user:
            return

        parts = message.text.strip().split()
        if len(parts) < 2:
            await message.reply("❌ Usage: /remove <symbol>\nExample: /remove NVDA")
            return

        symbol = parts[1].upper()
        telegram_id = message.from_user.id

        async with self.db.session() as session:
            stmt = select(Watchlist).join(User, Watchlist.user_id == User.id).where(User.telegram_id == telegram_id, Watchlist.symbol == symbol)
            res = await session.execute(stmt)
            item = res.scalar_one_or_none()

            if item:
                await session.delete(item)
                await session.commit()
                await message.reply(f"🗑️ Removed {symbol} from your watchlist.")
            else:
                await message.reply(f"ℹ️ {symbol} is not in your watchlist.")

    async def cmd_list(self, message: types.Message):
        """Handle /list — show user's watchlist."""
        if not message.from_user:
            return

        telegram_id = message.from_user.id

        async with self.db.session() as session:
            stmt = select(Watchlist).join(User, Watchlist.user_id == User.id).where(User.telegram_id == telegram_id)
            res = await session.execute(stmt)
            items = res.scalars().all()

            if not items:
                await message.reply(
                    "📋 Your watchlist is empty.\n"
                    "Add stocks using: /add <symbol> [market]"
                )
                return

            lines = ["📋 Your Watchlist (รายการหุ้นของคุณ):"]
            for item in items:
                lines.append(f"• {item.symbol} ({item.market})")

            await message.reply("\n".join(lines))

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
            symbols = [parts[1].upper()]
        else:
            # Query user's watchlist
            telegram_id = message.from_user.id
            async with self.db.session() as session:
                stmt = select(Watchlist.symbol).join(User, Watchlist.user_id == User.id).where(User.telegram_id == telegram_id)
                res = await session.execute(stmt)
                symbols = list(res.scalars().all())

        if not symbols:
            await message.reply(
                "⚠️ Watchlist is empty and no symbol provided.\n"
                "Specify a symbol to scan (e.g. /scan NVDA) or add stocks to your watchlist with /add <symbol> <market>."
            )
            return

        await message.reply(f"🔍 Scanning {len(symbols)} symbol(s): {', '.join(symbols)}...")

        snapshots = self.fetcher.fetch(symbols)
        if not snapshots:
            await message.reply(f"❌ Failed to fetch market data for: {', '.join(symbols)}")
            return

        enriched_signals = self.transformer.enrich(snapshots)
        
        # Fetch user's risk profile
        risk_profile = None
        async with self.db.session() as session:
            stmt = select(User).where(User.telegram_id == message.from_user.id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            if user:
                risk_profile = user.risk_profile

        async with self.db.session() as session:
            for symbol, enriched in enriched_signals.items():
                grade_result = self.grader.grade(enriched, risk_profile=risk_profile)

                # Save signal to database
                signal_entry = Signal(
                    symbol=grade_result.symbol,
                    grade=grade_result.grade,
                    confidence=grade_result.confidence,
                    advice=grade_result.advice,
                )
                session.add(signal_entry)

                emoji = GRADE_EMOJIS.get(grade_result.grade, "❓")
                label = GRADE_LABELS.get(grade_result.grade, "Unknown")
                snapshot = enriched.snapshot

                reasons_str = (
                    "\n".join(f"  • {r}" for r in grade_result.reasons)
                    if grade_result.reasons
                    else "  • N/A"
                )

                targets_str = (
                    "\n".join(f"  • {t}" for t in grade_result.buy_targets)
                    if getattr(grade_result, "buy_targets", None)
                    else "  • N/A"
                )

                # Create a visual progress bar for confidence
                conf = grade_result.confidence
                filled = int(conf / 10)
                empty = 10 - filled
                bar = "█" * filled + "░" * empty

                report_text = (
                    f"{emoji} DCA Analysis: {grade_result.symbol}\n"
                    f"Grade: {grade_result.grade}/4 — {label}\n"
                    f"Confidence: {conf}% [{bar}]\n\n"
                    f"📊 Market Snapshot:\n"
                    f"• Current Price: ${snapshot.current_price:,.2f}\n"
                    f"• Drawdown from ATH: {snapshot.drawdown_pct}%\n"
                    f"• ATH Price: ${snapshot.ath_price:,.2f}\n\n"
                    f"💡 AI Advice (คำแนะนำ):\n"
                    f"{grade_result.advice}\n\n"
                    f"🎯 Buy Targets (ราคาเป้าหมาย):\n"
                    f"{targets_str}\n\n"
                    f"📝 Reasons:\n"
                    f"{reasons_str}"
                )
                await message.reply(report_text)

            await session.commit()

    async def broadcast_scan(self, market: str = None):
        """Run broadcast scan and send to configured channel."""
        if not self.config.broadcast_channel_id:
            logger.info("BROADCAST_CHANNEL_ID not set. Skipping broadcast.")
            return

        symbols = await self.db.get_unique_watchlist_symbols(market)
        if not symbols:
            logger.info(f"No symbols found for market {market}. Skipping broadcast.")
            return

        snapshots = self.fetcher.fetch(symbols)
        if not snapshots:
            return

        enriched = self.transformer.enrich(snapshots)
        bot_user = await self.bot.get_me()

        for symbol, signal in enriched.items():
            result = self.grader.grade(signal)
            
            targets_str = (
                "\n".join(f"  • {t}" for t in result.buy_targets)
                if getattr(result, "buy_targets", None)
                else "  • N/A"
            )
            
            conf = result.confidence
            filled = int(conf / 10)
            empty = 10 - filled
            bar = "█" * filled + "░" * empty
            
            msg = f"#{symbol} Analysis:\nGrade: {result.grade}/4\nConfidence: {conf}% [{bar}]\n\n💡 Advice:\n{result.advice}\n\n🎯 Buy Targets:\n{targets_str}"
            kb = create_add_watchlist_keyboard(symbol, bot_user.username)
            try:
                await self.bot.send_message(self.config.broadcast_channel_id, msg, reply_markup=kb)
            except Exception as e:
                logger.error(f"Failed to send broadcast for {symbol}: {e}")

    async def start(self):
        """Initialize database, scheduler, and start polling."""
        logger.info("Initializing database tables...")
        await self.db.create_tables()

        logger.info("Starting scheduler...")
        self.scheduler = AsyncIOScheduler(timezone="Asia/Bangkok")
        self.scheduler.add_job(self.broadcast_scan, 'cron', hour=7, minute=0)
        self.scheduler.add_job(self.broadcast_scan, 'cron', hour=9, minute=30, args=['TH'])
        self.scheduler.add_job(self.broadcast_scan, 'cron', hour=20, minute=0, args=['US'])
        self.scheduler.start()

        logger.info("Starting Telegram bot polling...")
        await self.dp.start_polling(self.bot)

    async def stop(self):
        """Cleanup: close database connections."""
        logger.info("Closing database connections...")
        await self.db.close()
        await self.bot.session.close()


async def main():
    config = Config.from_env()
    bot = DCABot(config)
    try:
        await bot.start()
    finally:
        await bot.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
