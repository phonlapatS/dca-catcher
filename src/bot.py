import asyncio
import logging
import re
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
    logger.error(f"Critical Global Error: {event.exception}", exc_info=True)
    
    # Notify the user who triggered it (if any)
    if event.update.message:
        try:
            await event.update.message.reply(
                f"⚠️ **ขออภัย เกิดข้อผิดพลาดในระบบหลังบ้าน (System Error)**\n"
                f"```text\n{type(event.exception).__name__}: {str(event.exception)[:100]}...\n```\n"
                f"ระบบได้บันทึก Log นี้ไว้แล้ว กรุณาลองใหม่อีกครั้งครับ",
                parse_mode="Markdown"
            )
        except Exception:
            pass
            
    # Notify Admin (Rockget GoGo)
    try:
        if event.update.bot:
            admin_id = 8942457900  # Rockget GoGo's Telegram ID
            error_msg = (
                f"🚨 **[ADMIN ALERT] System Crash Detected!** 🚨\n"
                f"**Error:** `{type(event.exception).__name__}`\n"
                f"**Details:** `{str(event.exception)}`\n"
            )
            if event.update.message:
                error_msg += f"**Triggered by User:** {event.update.message.from_user.id}\n"
                error_msg += f"**Message:** {event.update.message.text}\n"
            
            await event.update.bot.send_message(
                chat_id=admin_id,
                text=error_msg,
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Failed to send alert to admin: {e}")

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
    waiting_for_subsector = State()
    waiting_for_count = State()
    waiting_for_budget = State()
    waiting_for_watchlist_decision = State()


ALL_SECTORS = {
    "sec_tech": "💻 เทคโนโลยี & ซอฟต์แวร์",
    "sec_comm": "📱 สื่อสาร & บันเทิง",
    "sec_health": "🏥 สุขภาพ & การแพทย์",
    "sec_fin": "🏦 การเงิน & ฟินเทค",
    "sec_cons_disc": "🛍️ สินค้าฟุ่มเฟือย & ค้าปลีก",
    "sec_cons_stap": "🛒 สินค้าอุปโภคบริโภคจำเป็น",
    "sec_ind": "🏭 อุตสาหกรรม & โลจิสติกส์",
    "sec_energy_util": "⚡ พลังงาน & สาธารณูปโภค",
    "sec_re": "🏢 อสังหาริมทรัพย์",
    "sec_mat": "🧱 วัสดุก่อสร้าง & เหมืองแร่"
}

SUBSECTORS = {
    "💻 เทคโนโลยี & ซอฟต์แวร์": {
        "sub_tech_semi": "🔬 ชิป & เซมิคอนดักเตอร์",
        "sub_tech_cloud": "☁️ คลาวด์ & โครงสร้างพื้นฐาน",
        "sub_tech_cyber": "🔒 ไซเบอร์ซีเคียวริตี้",
        "sub_tech_ai": "🤖 AI & ซอฟต์แวร์องค์กร",
        "sub_tech_hw": "💻 ฮาร์ดแวร์ & อุปกรณ์"
    },
    "📱 สื่อสาร & บันเทิง": {
        "sub_comm_social": "🌐 โซเชียลมีเดีย",
        "sub_comm_stream": "🎬 สตรีมมิ่ง & บันเทิง",
        "sub_comm_tele": "📡 โทรคมนาคม",
        "sub_comm_game": "🎮 เกมมิ่ง & อีสปอร์ต"
    },
    "🏥 สุขภาพ & การแพทย์": {
        "sub_hlth_pharma": "💊 บริษัทยาขนาดใหญ่",
        "sub_hlth_bio": "🧬 เทคโนโลยีชีวภาพ",
        "sub_hlth_dev": "🔬 อุปกรณ์การแพทย์",
        "sub_hlth_prov": "🏥 ประกันและโรงพยาบาล"
    },
    "🏦 การเงิน & ฟินเทค": {
        "sub_fin_bank": "🏦 ธนาคารพาณิชย์",
        "sub_fin_tech": "💳 ฟินเทค & เพย์เมนต์",
        "sub_fin_ins": "🛡️ ประกันภัย"
    },
    "🛍️ สินค้าฟุ่มเฟือย & ค้าปลีก": {
        "sub_disc_ev": "🚗 ยานยนต์ & EV",
        "sub_disc_ecom": "🛒 อีคอมเมิร์ซ",
        "sub_disc_travel": "✈️ ท่องเที่ยว & โรงแรม",
        "sub_disc_lux": "💎 แบรนด์เนมหรู"
    },
    "🛒 สินค้าอุปโภคบริโภคจำเป็น": {
        "sub_stap_food": "🍎 อาหาร & เครื่องดื่ม",
        "sub_stap_house": "🧴 ของใช้ในบ้าน",
        "sub_stap_retail": "🏪 ซูเปอร์มาร์เก็ต"
    },
    "🏭 อุตสาหกรรม & โลจิสติกส์": {
        "sub_ind_aero": "✈️ การบิน & ป้องกันประเทศ",
        "sub_ind_space": "🚀 อวกาศ & ดาวเทียม (SpaceTech)",
        "sub_ind_logi": "📦 โลจิสติกส์ & ขนส่ง",
        "sub_ind_mach": "⚙️ เครื่องจักร & ก่อสร้าง"
    },
    "⚡ พลังงาน & สาธารณูปโภค": {
        "sub_eng_oil": "🛢️ พลังงานดั้งเดิม (Oil/Gas)",
        "sub_eng_clean": "☀️ พลังงานสะอาด",
        "sub_eng_util": "💧 สาธารณูปโภคพื้นฐาน"
    },
    "🏢 อสังหาริมทรัพย์": {
        "sub_re_data": "💾 Data Center REITs",
        "sub_re_logi": "🏭 Logistics REITs",
        "sub_re_com": "🏢 Commercial REITs",
        "sub_re_res": "🏠 Residential REITs"
    },
    "🧱 วัสดุก่อสร้าง & เหมืองแร่": {
        "sub_mat_chem": "🧪 เคมีภัณฑ์",
        "sub_mat_metal": "⛏️ เหมืองแร่ & โลหะ",
        "sub_mat_pkg": "📦 บรรจุภัณฑ์"
    }
}



class DCABot:
    """Main application class — wires all components and handles Telegram commands."""

    def __init__(self, config: Config):
        self.config = config
        self.db = Database(config.database_url)
        self.fetcher = MarketDataFetcher()
        if not hasattr(self.fetcher, "fetch_current_price"):
            async def _fetch_current_price(symbol: str) -> float:
                loop = asyncio.get_running_loop()
                snapshots = await loop.run_in_executor(None, self.fetcher.fetch, [symbol])
                if symbol in snapshots:
                    return snapshots[symbol].current_price
                return 0.0
            self.fetcher.fetch_current_price = _fetch_current_price
        self.transformer = DataTransformer()
        self.grader = SignalGrader(config.gemini_api_keys)
        
        # Multi-Agent Pipeline for Deep Dive reports
        from src.insight_pipeline import InsightPipeline
        try:
            self.insight_pipeline = InsightPipeline(config.gemini_api_keys)
        except ValueError:
            self.insight_pipeline = None
            logger.warning("InsightPipeline disabled: no API keys.")
        self.sniper = AlpacaSniper(
            db=self.db,
            api_key=getattr(config, "alpaca_api_key", ""),
            secret_key=getattr(config, "alpaca_secret_key", ""),
            sniper_start_hour=config.sniper_start_hour,
            sniper_start_minute=config.sniper_start_minute,
            sniper_end_hour=config.sniper_end_hour,
            sniper_end_minute=config.sniper_end_minute,
        )

        token = config.telegram_token
        try:
            validate_token(token)
        except TokenValidationError:
            token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"

        self.bot = Bot(token=token)
        self.sniper.bot = self.bot
        self.sniper.broadcast_channel_id = config.broadcast_channel_id
        self.catalyst_hunter = CatalystHunter(
            db=self.db,
            bot=self.bot,
            channel_id=config.broadcast_channel_id,
            gemini_api_key=config.gemini_api_keys[0] if config.gemini_api_keys else None
        )

        
        self.dp = Dispatcher()
        self._register_handlers()
        self.dp.errors.register(global_error_handler)
    def _register_handlers(self):
        """Register all Telegram command handlers."""
        self.dp.message.register(self.cmd_start, Command("start"))
        self.dp.message.register(self.cmd_add, Command("add"))
        self.dp.message.register(self.cmd_remove, Command("remove"))
        self.dp.message.register(self.cmd_list, Command("list"))
        self.dp.message.register(self.cmd_scan, Command("scan"))
        self.dp.message.register(self.cmd_insight, Command("scan-details"))
        self.dp.message.register(self.cmd_survey, Command("survey"))
        self.dp.message.register(self.cmd_advice, Command("advice"))
        self.dp.message.register(self.cmd_help, Command("help"))
        self.dp.message.register(self.cmd_portfolio, Command("portfolio"))
        self.dp.message.register(self.cmd_news, Command("news", "hotnews"))
        
        # FSM handlers for /survey
        self.dp.callback_query.register(self.survey_style, RiskSurvey.waiting_for_style)
        self.dp.callback_query.register(self.survey_drawdown, RiskSurvey.waiting_for_drawdown)
        
        # FSM handlers for /advice
        self.dp.callback_query.register(self.advice_horizon, AdviceSurvey.waiting_for_horizon)
        self.dp.callback_query.register(self.advice_goal, AdviceSurvey.waiting_for_goal)
        self.dp.callback_query.register(self.advice_sector, AdviceSurvey.waiting_for_sector)
        self.dp.callback_query.register(self.advice_subsector, AdviceSurvey.waiting_for_subsector)
        self.dp.callback_query.register(self.advice_count, AdviceSurvey.waiting_for_count)
        self.dp.callback_query.register(self.advice_budget, AdviceSurvey.waiting_for_budget)
        
        self.dp.callback_query.register(self.advice_add_watchlist, F.data == "advice_add_wl", AdviceSurvey.waiting_for_watchlist_decision)
        self.dp.callback_query.register(self.advice_skip_watchlist, F.data == "advice_skip_wl", AdviceSurvey.waiting_for_watchlist_decision)

        # Target approval handlers for /scan
        self.dp.callback_query.register(self.tgt_toggle, F.data.startswith("tgt_toggle_"))
        self.dp.callback_query.register(self.tgt_confirm, F.data.startswith("tgt_confirm_"))
        self.dp.callback_query.register(self.tgt_dismiss, F.data.startswith("tgt_dismiss_"))
        self.dp.callback_query.register(self.set_notify_pref, F.data.startswith("notify_pref_"))
        
        # Insight report handler
        self.dp.callback_query.register(self.insight_btn, F.data.startswith("insight_"))

        # Catalyst Action Hub handlers
        self.dp.callback_query.register(self.cat_watch_btn, F.data.startswith("cat_watch_"))
        self.dp.callback_query.register(self.cat_sniper_btn, F.data.startswith("cat_sniper_"))
        self.dp.callback_query.register(self.cat_scan_btn, F.data.startswith("cat_scan_"))

        # Photo slip upload and fast confirmation
        self.dp.message.register(self.handle_photo_slip, F.photo)
        self.dp.callback_query.register(self.handle_slip_confirm, F.data.startswith("slip_confirm_"))
        self.dp.callback_query.register(self.handle_slip_cancel, F.data == "slip_cancel")


    async def _add_to_watchlist(
        self, telegram_id: int, username: str | None, symbol: str, market: str, target_price: float | list[float] | None = None
    ) -> str:
        """Helper method to upsert user and add symbol to watchlist."""
        if isinstance(target_price, list):
            target_str = ", ".join(f"{p} (User Target)" for p in target_price) if target_price else None
            price_display = ", ".join(f"${p}" for p in target_price)
        elif target_price is not None:
            target_str = f"{target_price} (User Target)"
            price_display = f"${target_price}"
        else:
            target_str = None
            price_display = ""

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
                if target_str:
                    existing.target_zones_str = target_str
                    existing.last_notified_zone = None  # Reset notification state
                    await session.commit()
                    return f"✅ Updated {symbol} target to {price_display}"
                return f"ℹ️ Symbol {symbol} ({market}) is already in your watchlist."
            else:
                item = Watchlist(user_id=user.id, symbol=symbol, market=market, target_zones_str=target_str)
                session.add(item)
                await session.commit()
                return f"✅ Added {symbol} ({market}) to your watchlist."

    async def cmd_start(self, message: types.Message, command: CommandObject | None = None):
        """Handle /start — welcome message, user registration, and deep links."""
        if not message.from_user:
            return
            
        telegram_id = message.from_user.id
        username = message.from_user.username
        
        # Ensure user is registered
        async with self.db.session() as session:
            stmt = select(User).where(User.telegram_id == telegram_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            if not user:
                user = User(telegram_id=telegram_id, username=username)
                session.add(user)
                await session.commit()
                
        # If run in a group, ask them to start a private chat for DM capability
        if message.chat.type in ["group", "supergroup"]:
            bot_info = await self.bot.get_me()
            dm_link = f"https://t.me/{bot_info.username}?start=dm_setup"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👉 เปิดแชทส่วนตัว (DM) กับบอท", url=dm_link)]
            ])
            await message.reply(
                f"👋 สวัสดีครับ @{username or 'สมาชิก'}!\n"
                "เพื่อให้บอทสามารถแจ้งเตือนราคาหุ้นให้คุณทาง **DM ส่วนตัว** ได้โดยตรง รบกวนกดปุ่มด้านล่างเพื่อเปิดแชทและกด **Start** หนึ่งครั้งนะครับ 🚀",
                reply_markup=keyboard
            )
            return

        if command and command.args and command.args.startswith("add_"):
            symbol = command.args.split("_", 1)[1].upper()
            market = "TH" if symbol.endswith(".BK") else "US"
            await message.answer(f"⏳ Adding {symbol} to your watchlist...")
            res_text = await self._add_to_watchlist(
                telegram_id, username, symbol, market
            )
            await message.answer(res_text)
            return

        welcome_text = (
            "👋 Welcome to DCA Catcher Bot!\n"
            "ยินดีต้อนรับสู่ระบบวิเคราะห์หุ้นสำหรับ DCA ด้วย AI\n\n"
            "ตอนนี้บอทพร้อมที่จะแจ้งเตือนคุณผ่านทาง DM แล้วครับ! พิมพ์ /help เพื่อดูคำสั่งทั้งหมดที่ใช้งานได้"
        )
        await message.answer(welcome_text)

    async def cmd_help(self, message: types.Message):
        """Handle /help — display all available commands and their usage."""
        help_text = (
            "📌 **Available Commands (เรียงตามลำดับความสำคัญ):**\n\n"
            "🔹 `/survey` - 📝 ทำแบบสอบถามเพื่อตั้งค่า Profile ความเสี่ยงของคุณ (แนะนำให้ทำเป็นอันดับแรก)\n"
            "🔹 `/advice` - 🌟 ให้ AI ช่วยหาและจัดพอร์ตหุ้นแบบเจาะลึกเฉพาะคุณ\n"
            "🔹 `/add <ชื่อหุ้น> [ตลาด]` - ➕ เพิ่มหุ้นเข้า Watchlist เพื่อให้ AI ช่วยเตือนทุกวัน\n"
            "   *(ตัวอย่าง: /add NVDA US หรือ /add PTT.BK TH)*\n"
            "🔹 `/list` - 📋 ดูรายชื่อหุ้นทั้งหมดที่คุณติดตามอยู่ (Watchlist)\n"
            "🔹 `/portfolio` - 💼 สรุปพอร์ตหุ้น DCA และคำนวณกำไร/ขาดทุน (PnL)\n"
            "🔹 `/scan` - 🔍 สั่ง AI ให้วิเคราะห์พอร์ตหุ้น **ทุกตัว** ใน Watchlist ทันที\n"
            "🔹 `/scan <ชื่อหุ้น>` - 🔍 สั่ง AI ให้วิเคราะห์หุ้น **เฉพาะตัวที่ระบุ**\n"
            "   *(ตัวอย่าง: /scan TSLA)*\n"
            "🔹 `/scan-details <ชื่อหุ้น>` - 🧬 บทวิเคราะห์เจาะลึกปัจจัยพื้นฐานและข่าว\n"
            "🔹 `/news` หรือ `/hotnews` - 🛰️ เปิดเรดาร์จับข่าวด่วนของหุ้นในพอร์ตทั้งหมด\n"
            "🔹 `/remove <ชื่อหุ้น>` - 🗑️ ลบหุ้นออกจาก Watchlist\n"
            "🔹 `/help` - ❓ แสดงรายการคำสั่งทั้งหมด\n"
            "🔹 `/start` - 🚀 เริ่มต้นใช้งานบอท"
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
        
        buttons = []
        for key, name in ALL_SECTORS.items():
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
        
        selected_name = ALL_SECTORS.get(callback.data)
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
            # Transition to asking for subsectors
            await state.update_data(current_sub_idx=0, detailed_sectors=[])
            await self._ask_next_subsector(callback.message, state)
        else:
            # Re-render keyboard
            await self._show_sector_keyboard(callback.message, state)

    async def _ask_next_subsector(self, message: types.Message, state: FSMContext):
        data = await state.get_data()
        sectors = data.get("sectors", [])
        idx = data.get("current_sub_idx", 0)

        if idx >= len(sectors):
            # All 3 subsectors chosen, move to count
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎯 แนะนำ 3 ตัว (เน้นๆ โฟกัสๆ)", callback_data="cnt_3")],
                [InlineKeyboardButton(text="🖐️ แนะนำ 5 ตัว (มาตรฐาน)", callback_data="cnt_5")],
                [InlineKeyboardButton(text="🍀 แนะนำ 7 ตัว (กระจายความเสี่ยง)", callback_data="cnt_7")],
                [InlineKeyboardButton(text="🔟 แนะนำ 10 ตัว (จัดพอร์ตใหญ่)", callback_data="cnt_10")]
            ])
            text = "เกือบเสร็จแล้วครับ! 📈\nคุณอยากให้ AI แนะนำหุ้นกี่ตัวสำหรับพอร์ตนี้ครับ?"
            if isinstance(message, types.Message):
                await message.edit_text(text, reply_markup=keyboard)
            await state.set_state(AdviceSurvey.waiting_for_count)
            return

        current_main_sector = sectors[idx]
        current_chosen_subs = data.get("current_chosen_subs", [])
        
        subs = SUBSECTORS.get(current_main_sector, {"sub_any": "สนใจทั้งหมดในกลุ่มนี้"})
        buttons = []
        for key, name in subs.items():
            text = f"✅ {name}" if key in current_chosen_subs else name
            buttons.append([InlineKeyboardButton(text=text, callback_data=key)])
            
        # Add confirm button if at least 1 is selected
        if current_chosen_subs:
            buttons.append([InlineKeyboardButton(text="➡️ ยืนยันกลุ่มย่อย (Next)", callback_data="sub_confirm")])
            
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        text = f"สำหรับกลุ่ม **{current_main_sector}**\nคุณสนใจเจาะจงไปที่กลุ่มย่อยไหนเป็นพิเศษครับ? (เลือกได้ 1-3 กลุ่มย่อย)"
        
        if isinstance(message, types.Message):
            await message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await state.set_state(AdviceSurvey.waiting_for_subsector)

    async def advice_subsector(self, callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        data = await state.get_data()
        sectors = data.get("sectors", [])
        idx = data.get("current_sub_idx", 0)
        detailed = data.get("detailed_sectors", [])
        current_chosen_subs = data.get("current_chosen_subs", [])
        
        current_main_sector = sectors[idx]
        subs = SUBSECTORS.get(current_main_sector, {"sub_any": "สนใจทั้งหมดในกลุ่มนี้"})
        
        if callback.data == "sub_confirm":
            if not current_chosen_subs:
                return
            chosen_names = [subs.get(k, k) for k in current_chosen_subs]
            names_str = ", ".join(chosen_names)
            detailed.append(f"{current_main_sector} (เน้น: {names_str})")
            
            await state.update_data(detailed_sectors=detailed, current_sub_idx=idx + 1, current_chosen_subs=[])
            await self._ask_next_subsector(callback.message, state)
            return

        # Toggle subsector
        if callback.data in current_chosen_subs:
            current_chosen_subs.remove(callback.data)
        else:
            if len(current_chosen_subs) < 3:
                current_chosen_subs.append(callback.data)
                
        await state.update_data(current_chosen_subs=current_chosen_subs)
        await self._ask_next_subsector(callback.message, state)

    async def advice_count(self, callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        
        cnt_str = callback.data.split("_")[1]
        await state.update_data(count=cnt_str)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 1,000 - 3,000 บาท/เดือน", callback_data="bdg_3000")],
            [InlineKeyboardButton(text="💰 4,000 - 6,000 บาท/เดือน", callback_data="bdg_6000")],
            [InlineKeyboardButton(text="💰 7,000 - 10,000 บาท/เดือน", callback_data="bdg_10000")],
            [InlineKeyboardButton(text="💰 10,000 - 30,000 บาท/เดือน", callback_data="bdg_30000")],
            [InlineKeyboardButton(text="⏭️ ข้าม / ไม่ระบุ", callback_data="bdg_none")]
        ])
        
        await callback.message.edit_text(
            "ด่านสุดท้ายครับ! 🎉\nเพื่อให้ AI คำนวณแผนการออมเงินและการเติบโตให้แม่นยำยิ่งขึ้น คุณมีงบในการ DCA หุ้นพอร์ตนี้ต่อเดือนประมาณเท่าไหร่ครับ?",
            reply_markup=keyboard
        )
        await state.set_state(AdviceSurvey.waiting_for_budget)

    async def advice_budget(self, callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        
        budget_map = {
            "bdg_3000": "ประมาณ 3,000 บาท/เดือน",
            "bdg_6000": "ประมาณ 6,000 บาท/เดือน",
            "bdg_10000": "ประมาณ 10,000 บาท/เดือน",
            "bdg_30000": "ประมาณ 30,000 บาท/เดือน",
            "bdg_none": "ไม่ระบุ"
        }
        budget_str = budget_map.get(callback.data, "ไม่ระบุ")
        
        await callback.message.edit_text("⏳ AI กำลังประมวลผลข้อมูลและจัดพอร์ตให้คุณ กรุณารอสักครู่...")
        
        data = await state.get_data()
        horizon = data.get("horizon")
        goal = data.get("goal")
        detailed_sectors = data.get("detailed_sectors", [])
        cnt_str = data.get("count", "5")
        
        # Fetch risk profile from DB
        telegram_id = callback.from_user.id
        risk_profile = None
        async with self.db.session() as session:
            stmt = select(User).where(User.telegram_id == telegram_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            if user:
                risk_profile = user.risk_profile
                
        # Call Grader in a background thread
        import asyncio
        advice_text = await asyncio.to_thread(
            self.grader.generate_advice,
            risk_profile=risk_profile,
            horizon=horizon,
            goal=goal,
            sectors=detailed_sectors,
            count=cnt_str,
            budget=budget_str
        )
        
        try:
            await callback.message.answer(advice_text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Markdown parse error: {e}. Falling back to plain text.")
            await callback.message.answer(advice_text)
        
        import re
        # Support formats like: "1. **AAPL**", "- **NVDA (Nvidia)**", "* **TSLA**"
        tickers = re.findall(r"(?:^|\n)(?:\d+\.|\-|\*)\s*\*\*([A-Z0-9\.]+)(?:[^\*]*)\*\*", advice_text)
        
        # Fallback if no tickers found but they might have omitted the bold tags, or used markdown lists differently.
        if not tickers:
            # Look for "1. AAPL -" or "1. AAPL (Apple)"
            tickers = re.findall(r"(?:^|\n)(?:\d+\.|\-|\*)\s*([A-Z0-9\.]+)\b", advice_text)
        
        if tickers:
            await state.update_data(recommended_tickers=tickers)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ เพิ่มหุ้นที่แนะนำเข้า Watchlist ทั้งหมด", callback_data="advice_add_wl")],
                [InlineKeyboardButton(text="⏭️ ข้ามไปก่อน", callback_data="advice_skip_wl")]
            ])
            await callback.message.answer("คุณต้องการเพิ่มหุ้นที่แนะนำข้างต้นเข้าไปใน Watchlist เพื่อติดตามการแจ้งเตือนด้วย AI เป็นประจำทุกวันหรือไม่?", reply_markup=kb)
            await state.set_state(AdviceSurvey.waiting_for_watchlist_decision)
        else:
            await state.clear()

    async def advice_add_watchlist(self, callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        data = await state.get_data()
        tickers = data.get("recommended_tickers", [])
        telegram_id = callback.from_user.id
        username = callback.from_user.username
        
        added = []
        for symbol in tickers:
            market = "TH" if symbol.endswith(".BK") else "US"
            res = await self._add_to_watchlist(telegram_id, username, symbol, market)
            if "✅" in res:
                added.append(symbol)
                
        if added:
            await callback.message.edit_text(f"✅ เพิ่มหุ้น {', '.join(added)} ลงใน Watchlist เรียบร้อยแล้วครับ! บอทจะทำการสแกนรายวันให้ครับ")
        else:
            await callback.message.edit_text("ℹ️ หุ้นทั้งหมดอยู่ใน Watchlist ของคุณอยู่แล้วครับ")
            
        await state.clear()

    async def advice_skip_watchlist(self, callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await callback.message.edit_text("โอเคครับ! ถ้าต้องการเพิ่มทีหลังสามารถใช้คำสั่ง /add <ชื่อหุ้น> ได้ตลอดเลยครับ")
        await state.clear()

    async def cmd_add(self, message: types.Message):
        """Handle /add <symbol>... — add multiple stocks to user's watchlist.

        Usage: /add NVDA AAPL PTT.BK
        - Creates user if not exists (upsert by telegram_id)
        - Adds symbols to their watchlist
        - Responds with confirmation
        """
        if not message.text or not message.from_user:
            return

        # Remove the /add command part
        text = message.text.replace("/add", "", 1).strip()
        if not text:
            await message.reply(
                "❌ Usage: /add <symbol1> <symbol2> ...\n"
                "Example: /add NVDA AAPL PTT.BK"
            )
            return

        # Parse: /add AAPL 150 NVDA 200 TSLA MSFT 300
        parts = text.replace(",", " ").split()[1:] # skip command
        if not parts: return
        
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
            market = "TH" if symbol.endswith(".BK") else "US"
            res_text = await self._add_to_watchlist(telegram_id, username, symbol, market, target_price)
            results.append(res_text)
        
        # Update active sniper subscription dynamically
        if self.sniper.running:
            await self.sniper.update_subscriptions()

        await message.reply("\n".join(results))

    async def cmd_remove(self, message: types.Message):
        """Handle /remove <symbol>... — remove multiple stocks from user's watchlist."""
        if not message.text or not message.from_user:
            return

        text = message.text.replace("/remove", "", 1).strip()
        if not text:
            await message.reply("❌ Usage: /remove <symbol1> <symbol2> ...\nExample: /remove NVDA AAPL")
            return

        symbols = [s.strip().upper() for s in text.replace(",", " ").split() if s.strip()]
        telegram_id = message.from_user.id
        
        results = []
        async with self.db.session() as session:
            for symbol in symbols:
                stmt = select(Watchlist).join(User, Watchlist.user_id == User.id).where(User.telegram_id == telegram_id, Watchlist.symbol == symbol)
                res = await session.execute(stmt)
                item = res.scalar_one_or_none()

                if item:
                    await session.delete(item)
                    results.append(f"🗑️ Removed {symbol} from your watchlist.")
                else:
                    results.append(f"ℹ️ {symbol} is not in your watchlist.")
            await session.commit()
            
        await message.reply("\n".join(results))

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

            lines = ["📋 **Your Watchlist & Target Prices (รายการหุ้นและราคาเป้าหมาย):**\n"]
            for item in items:
                if item.target_zones_str:
                    prices = re.findall(r"(\d+(?:\.\d+)?)", item.target_zones_str)
                    if prices:
                        target_disp = ", ".join(f"${float(p):,.2f}" for p in prices)
                        lines.append(f"• **{item.symbol}** ({item.market}) 🎯 เป้าหมาย: `{target_disp}`")
                    else:
                        lines.append(f"• **{item.symbol}** ({item.market}) — `{item.target_zones_str}`")
                else:
                    lines.append(f"• **{item.symbol}** ({item.market}) — *(ไม่มีเป้าหมาย)*")

            await message.reply("\n".join(lines), parse_mode="Markdown")

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
            symbols = [p.upper().replace(",", "") for p in parts[1:] if p.strip()]
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

        status_msg = await message.reply(f"🔍 เริ่มสแกน {len(symbols)} หุ้น: {', '.join(symbols)}\n`[░░░░░░░░░░░░] 0%`\n👉 กำลังดึงข้อมูลตลาด...")
        
        def make_pb(pct: int, length: int = 12):
            f = int((pct / 100.0) * length)
            return "█" * f + "░" * (length - f)

        loop = asyncio.get_running_loop()
        snapshots = {}
        for i, sym in enumerate(symbols):
            pct = int(((i + 1) / len(symbols)) * 50)
            try:
                await status_msg.edit_text(f"🔍 กำลังสแกน...\n`[{make_pb(pct)}] {pct}%`\n👉 กำลังเชื่อมต่อ: {sym}", parse_mode="Markdown")
            except Exception:
                pass
            # Fetch one by one to show progress
            res = await loop.run_in_executor(None, self.fetcher.fetch, [sym])
            if res:
                snapshots.update(res)

        if not snapshots:
            await status_msg.edit_text(f"❌ Failed to fetch market data for: {', '.join(symbols)}")
            return
            
        try:
            await status_msg.edit_text(f"🔍 กำลังสแกน...\n`[{make_pb(70)}] 70%`\n👉 กำลังประมวลผล Technical Indicators...", parse_mode="Markdown")
        except Exception:
            pass

        enriched_signals = self.transformer.enrich(snapshots)
        
        # Fetch user's risk profile
        try:
            await status_msg.edit_text(f"🔍 กำลังสแกน...\n`[{make_pb(90)}] 90%`\n👉 กำลังประเมินร่วมกับ Risk Profile...", parse_mode="Markdown")
        except Exception:
            pass
            
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

                # Save signal to database (using grade field to store score for backwards compatibility)
                signal_entry = Signal(
                    symbol=grade_result.symbol,
                    grade=grade_result.score,
                    confidence=grade_result.confidence,
                    advice=grade_result.advice,
                )
                session.add(signal_entry)

                snapshot = enriched.snapshot

                reasons_str = (
                    "\n".join(f"  • {r}" for r in grade_result.reasons)
                    if grade_result.reasons
                    else "  • N/A"
                )

                targets_str = (
                    "\n".join(f"  • ${t}" for t in grade_result.buy_targets)
                    if getattr(grade_result, "buy_targets", None)
                    else "  • N/A"
                )

                # Create a visual progress bar for confidence
                conf = grade_result.confidence
                filled = int(conf / 10)
                empty = 10 - filled
                bar = "█" * filled + "░" * empty
                
                # Create a score visual (bar)
                score_val = max(1, min(10, grade_result.score))
                score_bar = "█" * score_val + "░" * (10 - score_val)
                
                # Create mention
                username = message.from_user.username
                mention = f"@{username}" if username else f"[{message.from_user.full_name}](tg://user?id={message.from_user.id})"

                report_text = (
                    f"🗣️ **สำหรับ {mention}**\n"
                    f"📊 **{grade_result.symbol} Analysis**\n\n"
                    f"🏷️ **Current Price:** ${snapshot.current_price:,.2f}\n"
                    f"📉 **ATH Drawdown:** {snapshot.drawdown_pct}%\n\n"
                    f"🤖 **AI Score (ความน่าลงทุน):** {score_val}/10\n"
                    f"[{score_bar}]\n"
                    f"🎯 **Confidence:** {conf}% [{bar}]\n\n"
                    f"💡 **คำแนะนำจาก AI:**\n"
                    f"{grade_result.advice}\n\n"
                    f"📌 **จุดสังเกต:**\n"
                    f"{reasons_str}\n\n"
                    f"🛒 **ราคาเป้าหมาย (Buy Targets):**\n"
                    f"{targets_str}"
                )
                # Create interactive target approval keyboard
                buttons = []
                if getattr(grade_result, "buy_targets", None):
                    for idx, t in enumerate(grade_result.buy_targets):
                        buttons.append([InlineKeyboardButton(text=f"[ ] ${t:,.2f}", callback_data=f"tgt_toggle_{grade_result.symbol}_{idx}")])
                    buttons.append([
                        InlineKeyboardButton(text="🎯 ยืนยันเป้าหมาย", callback_data=f"tgt_confirm_{grade_result.symbol}"),
                        InlineKeyboardButton(text="❌ ยังไม่สนใจ / ข้าม", callback_data=f"tgt_dismiss_{grade_result.symbol}")
                    ])
                
                # Add Insight button
                buttons.append([InlineKeyboardButton(text="📖 เจาะลึกบทวิเคราะห์ (Deep Dive)", callback_data=f"insight_{grade_result.symbol}")])

                keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

                # 1. Send text analysis first
                try:
                    await message.reply(report_text, parse_mode="Markdown", reply_markup=keyboard)
                except Exception as e:
                    logger.error(f"Markdown parse error in scan: {e}. Falling back to plain text.")
                    await message.reply(report_text, reply_markup=keyboard)

                # 2. Send in-memory target zones chart right after text
                if getattr(grade_result, "buy_targets", None) and getattr(snapshot, "current_price", None):
                    try:
                        from src.charting import ChartGenerator
                        from aiogram.types import BufferedInputFile
                        chart_bytes = ChartGenerator.generate_target_chart(
                            symbol=grade_result.symbol,
                            current_price=snapshot.current_price,
                            targets=grade_result.buy_targets
                        )
                        if chart_bytes:
                            photo = BufferedInputFile(chart_bytes, filename=f"{grade_result.symbol}_chart.png")
                            await message.answer_photo(photo=photo, caption=f"📊 **{grade_result.symbol} Target Zones Chart**", parse_mode="Markdown")
                    except Exception as err:
                        logger.error(f"Failed to generate target chart for {grade_result.symbol}: {err}")
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
                    if btn.text.startswith("[ ]"):
                        btn.text = btn.text.replace("[ ]", "[✅]", 1)
                    elif btn.text.startswith("[✅]"):
                        btn.text = btn.text.replace("[✅]", "[ ]", 1)

        await callback.message.edit_reply_markup(reply_markup=markup)

    async def tgt_confirm(self, callback: types.CallbackQuery):
        """Confirm selected target prices and add to watchlist for AlpacaSniper."""
        await callback.answer()
        symbol = callback.data.split("tgt_confirm_")[1]
        markup = callback.message.reply_markup
        if not markup:
            return

        selected_prices = []
        for row in markup.inline_keyboard:
            for btn in row:
                if btn.text.startswith("[✅]"):
                    try:
                        price_str = btn.text.split("$")[1].replace(",", "").strip()
                        selected_prices.append(float(price_str))
                    except (IndexError, ValueError):
                        pass

        if not selected_prices:
            await callback.message.answer(f"⚠️ คุณยังไม่ได้เลือกเป้าหมายสำหรับ {symbol} เลยครับ (แตะปุ่มเพื่อเลือกก่อนกด ยืนยัน)")
            return

        telegram_id = callback.from_user.id
        username = callback.from_user.username
        market = "TH" if symbol.endswith(".BK") else "US"

        res_text = await self._add_to_watchlist(telegram_id, username, symbol, market, selected_prices)

        if self.sniper and self.sniper.running:
            await self.sniper.update_subscriptions()

        prices_formatted = ", ".join(f"${p:,.2f}" for p in selected_prices)
        
        pref_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📩 แจ้งเตือนทาง DM ส่วนตัว (แนะนำ)", callback_data="notify_pref_dm")],
            [InlineKeyboardButton(text="📢 แจ้งเตือนในกลุ่ม (@tag)", callback_data="notify_pref_group")]
        ])
        
        await callback.message.reply(
            f"🎯 **อนุมัติเป้าหมายเรียบร้อย!**\n\n"
            f"บันทึกราคาเป้าหมายของ **{symbol}** ({prices_formatted}) เข้าระบบ Sniper เรียบร้อยแล้วครับ 🚀\n\n"
            f"⚙️ **ตั้งค่าการแจ้งเตือน**:\nเมื่อราคาถึงเป้าหมาย คุณต้องการให้บอทแจ้งเตือนแบบไหน?",
            reply_markup=pref_keyboard
        )

    async def tgt_dismiss(self, callback: types.CallbackQuery):
        """Dismiss target selection buttons to keep chat clean."""
        await callback.answer("ข้ามการตั้งราคาเป้าหมายแล้ว")
        symbol = callback.data.split("tgt_dismiss_")[1]
        
        # Keep only the Deep Dive button
        buttons = [
            [InlineKeyboardButton(text="📖 เจาะลึกบทวิเคราะห์ (Deep Dive)", callback_data=f"insight_{symbol}")]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await callback.message.edit_reply_markup(reply_markup=keyboard)
        except Exception:
            pass

    async def set_notify_pref(self, callback: types.CallbackQuery):
        """Handle notification preference selection."""
        await callback.answer()
        pref = callback.data.split("notify_pref_")[1]
        notify_dm = (pref == "dm")
        telegram_id = callback.from_user.id
        
        async with self.db.session() as session:
            stmt = select(User).where(User.telegram_id == telegram_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            if user:
                user.notify_dm = notify_dm
                await session.commit()
                
        mode_text = "DM ส่วนตัว" if notify_dm else "แท็กในกลุ่ม"
        await callback.message.edit_text(
            f"✅ ตั้งค่าการแจ้งเตือนสำเร็จ!\n\n"
            f"ต่อไปเมื่อหุ้นถึงเป้าหมาย บอทจะแจ้งเตือนคุณผ่านทาง **{mode_text}** ครับ",
            reply_markup=None
        )

    async def broadcast_scan(self, market: str = None):
        """Run broadcast scan and send to configured channel, personalized by risk profile."""
        if not self.config.broadcast_channel_id:
            logger.info("BROADCAST_CHANNEL_ID not set. Skipping broadcast.")
            return

        # Query all users and their watchlists
        async with self.db.session() as session:
            stmt = select(User, Watchlist).join(Watchlist, User.id == Watchlist.user_id)
            if market:
                stmt = stmt.where(Watchlist.market == market)
            res = await session.execute(stmt)
            rows = res.all()

        if not rows:
            logger.info(f"No users watching symbols for market {market}. Skipping broadcast.")
            return

        # Group users by (symbol, risk_profile)
        symbol_risk_users = {}
        unique_symbols = set()
        
        for user, wl in rows:
            symbol = wl.symbol
            unique_symbols.add(symbol)
            rp = user.risk_profile or "ทั่วไป (ไม่ได้ตั้งค่า)"
            key = (symbol, rp)
            
            if key not in symbol_risk_users:
                symbol_risk_users[key] = []
                
            mention = f"@{user.username}" if user.username else f"User_{user.id}"
            symbol_risk_users[key].append(mention)

        loop = asyncio.get_running_loop()
        snapshots = await loop.run_in_executor(None, self.fetcher.fetch, list(unique_symbols))
        if not snapshots:
            return

        enriched = self.transformer.enrich(snapshots)
        bot_user = await self.bot.get_me()

        for (symbol, rp), users in symbol_risk_users.items():
            if symbol not in enriched:
                continue
                
            signal = enriched[symbol]
            result = self.grader.grade(signal, risk_profile=rp)
            
            targets_str = (
                "\n".join(f"  • ${t}" for t in result.buy_targets)
                if getattr(result, "buy_targets", None)
                else "  • N/A"
            )
            
            conf = result.confidence
            filled = int(conf / 10)
            empty = 10 - filled
            bar = "█" * filled + "░" * empty
            
            score_val = max(1, min(10, result.score))
            score_bar = "█" * score_val + "░" * (10 - score_val)
            
            mentions_str = " ".join(users)
            msg = (
                f"🗣️ **แจ้งเตือนสำหรับ:** {mentions_str}\n"
                f"📊 **#{symbol} Analysis** (มุมมอง: {rp})\n\n"
                f"🤖 AI Score: {score_val}/10\n[{score_bar}]\n"
                f"🎯 Confidence: {conf}% [{bar}]\n\n"
                f"💡 Advice:\n{result.advice}\n\n"
                f"🛒 Buy Targets:\n{targets_str}"
            )
            kb = create_add_watchlist_keyboard(symbol, bot_user.username)
            try:
                await self.bot.send_message(self.config.broadcast_channel_id, msg, reply_markup=kb)
            except Exception as e:
                logger.error(f"Failed to send broadcast for {symbol} ({rp}): {e}")

    async def on_startup(self):
        """Startup lifecycle handler: start background tasks like AlpacaSniper."""
        if self.sniper:
            logger.info("Starting AlpacaSniper background task...")
            await self.sniper.start()

    async def start(self):
        """Initialize database, scheduler, sniper, and start polling."""
        logger.info("Initializing database tables...")
        await self.db.create_tables()

        logger.info("Starting scheduler...")
        self.scheduler = AsyncIOScheduler(timezone="Asia/Bangkok")
        self.scheduler.add_job(self.broadcast_scan, 'cron', hour=self.config.broadcast_morning_hour, minute=self.config.broadcast_morning_minute)
        self.scheduler.add_job(self.broadcast_scan, 'cron', hour=self.config.broadcast_th_hour, minute=self.config.broadcast_th_minute, args=['TH'])
        self.scheduler.add_job(self.broadcast_scan, 'cron', hour=self.config.broadcast_us_hour, minute=self.config.broadcast_us_minute, args=['US'])
        # Adaptive Catalyst Hunter Schedule (Turbo 17:00-20:30, Eco during day, Digest at 19:00)
        self.scheduler.add_job(self.catalyst_hunter.run_scan_cycle, 'cron', hour='17-20', minute='*/2')
        self.scheduler.add_job(self.catalyst_hunter.run_scan_cycle, 'cron', hour='8-16', minute='*/30')
        self.scheduler.add_job(self.catalyst_hunter.send_daily_digest, 'cron', hour=19, minute=0)
        self.scheduler.start()


        await self.on_startup()

        logger.info("Starting Telegram bot polling...")
        await self.dp.start_polling(self.bot)

    async def stop(self):
        """Cleanup: stop sniper and close database connections."""
        if self.sniper:
            logger.info("Stopping AlpacaSniper...")
            await self.sniper.stop()
        logger.info("Closing database connections...")
        await self.db.close()
        await self.bot.session.close()

    async def cat_watch_btn(self, callback: types.CallbackQuery):
        """Handle '➕ เพิ่มเข้า Watchlist' button click on Catalyst alert."""
        symbol = callback.data.split("_")[2]
        market = "TH" if symbol.endswith(".BK") else "US"
        res_text = await self._add_to_watchlist(
            callback.from_user.id, callback.from_user.username, symbol, market
        )
        await callback.answer(res_text, show_alert=True)

    async def cat_sniper_btn(self, callback: types.CallbackQuery):
        """Handle '🎯 ตั้งเป้า Sniper' button click on Catalyst alert."""
        symbol = callback.data.split("_")[2]
        await callback.answer(f"🎯 พิมพ์ /scan {symbol} เพื่อเลือกราคาเป้าหมายเข้าสู่ Sniper!", show_alert=True)

    async def cat_scan_btn(self, callback: types.CallbackQuery):
        """Handle '🔍 สแกน $SYMBOL' button click on Catalyst alert for connected stocks."""
        symbol = callback.data.split("_")[2]
        await callback.answer(f"🔍 กำลังสแกน ${symbol}...")
        if callback.message:
            msg = callback.message
            msg.text = f"/scan {symbol}"
            msg.from_user = callback.from_user
            await self.cmd_scan(msg)


    async def cmd_news(self, message: types.Message):
        """Force a catalyst scan immediately."""
        status_msg = await message.reply("🔄 เปิดเรดาร์เช็คข่าวด่วนล่าสุด (Real-time Catalyst)... กรุณารอสักครู่")
        
        def make_progress_bar(percent: int, length: int = 12) -> str:
            filled = int((percent / 100.0) * length)
            empty = length - filled
            return "█" * filled + "░" * empty

        async def update_progress(stage: str, percent: int = 0):
            try:
                bar = make_progress_bar(percent)
                await status_msg.edit_text(f"⏳ **Catalyst Hunter**\n`[{bar}] {percent}%`\n\n👉 {stage}", parse_mode="Markdown")
            except Exception:
                pass

        try:
            count = await self.catalyst_hunter.run_scan_cycle(["NVDA", "TSLA", "AAPL"], on_progress=update_progress)
            await status_msg.edit_text(f"✅ ประมวลผลและคัดกรองข่าวสารเสร็จสิ้น! พบข่าวด่วน (Tier S/A) จำนวน {count} รายการ")
        except Exception as e:
            await status_msg.edit_text(f"❌ เกิดข้อผิดพลาด: {e}")

    async def cmd_insight(self, message: types.Message):

        """Handle /scan-details <symbol> to generate deep dive report."""
        if not message.text:
            return
        parts = message.text.strip().split()
        if len(parts) < 2:
            await message.reply("⚠️ กรุณาระบุชื่อหุ้น เช่น /scan-details NVDA")
            return
            
        symbol = parts[1].upper()
        await self._generate_and_send_insight(message, symbol)
        
    async def insight_btn(self, callback: types.CallbackQuery):
        """Handle insight inline button click."""
        await callback.answer("กำลังเจาะลึกข้อมูลวิเคราะห์...")
        symbol = callback.data.split("_")[1]
        await self._generate_and_send_insight(callback.message, symbol)

    async def _generate_and_send_insight(self, message: types.Message, symbol: str):
        """Generate deep-dive insight report using Multi-Agent Pipeline.

        Pipeline: Data Collection → 3 Specialist Agents → Composer → Quality Gate.
        Shows live progress updates to the user during each phase.
        Falls back to old single-prompt method if pipeline is unavailable.
        """
        status_msg = await message.reply(f"⏳ กำลังเริ่ม Multi-Agent Analysis ของ {symbol}...")

        # --- Check pipeline availability ---
        if not self.insight_pipeline:
            await status_msg.edit_text("❌ ระบบ Multi-Agent Pipeline ยังไม่พร้อม (ไม่มี API Key)")
            return

        # --- Phase 0: Fetch raw data (no LLM) ---
        try:
            await status_msg.edit_text(f"📊 กำลังดึงข้อมูลตลาดของ {symbol}...")
        except Exception:
            pass

        loop = asyncio.get_running_loop()
        snapshots = await loop.run_in_executor(None, self.fetcher.fetch, [symbol])
        if symbol not in snapshots:
            await status_msg.edit_text(f"❌ ไม่พบข้อมูลราคาของ {symbol}")
            return

        signals = self.transformer.enrich(snapshots)
        signal = signals.get(symbol)

        # Fetch news in executor to prevent blocking the event loop
        loop = asyncio.get_running_loop()
        from src.scrapers.sentiment import get_recent_news, get_fear_greed_index
        news_headlines = await loop.run_in_executor(None, get_recent_news, symbol)
        fear_greed = await loop.run_in_executor(None, get_fear_greed_index)

        # Fetch user risk profile
        risk_profile = None
        user_db_id = None
        timeline_str = "ไม่มีประวัติการสแกนเดิมในระบบ (First-time / Cold Start Scan)"
        if message.from_user:
            async with self.db.session() as session:
                stmt = select(User).where(User.telegram_id == message.from_user.id)
                user = (await session.execute(stmt)).scalar_one_or_none()
                if user:
                    user_db_id = user.id
                    risk_profile = user.risk_profile
                    from src.memory import MemoryManager
                    recent_memory = await MemoryManager.get_recent_timeline(session, user_id=user.id, symbol=symbol, limit=2)
                    timeline_str = MemoryManager.format_timeline_prompt(recent_memory)

        # --- Run the Multi-Agent Pipeline ---
        main_loop = asyncio.get_running_loop()

        def make_progress_bar(percent: int, length: int = 12) -> str:
            filled = int((percent / 100.0) * length)
            empty = length - filled
            return "█" * filled + "░" * empty

        async def update_progress(stage: str, percent: int = 0):
            try:
                bar = make_progress_bar(percent)
                await status_msg.edit_text(f"⏳ **Deep Dive Analysis:** {symbol}\n`[{bar}] {percent}%`\n\n👉 {stage}", parse_mode="Markdown")
            except Exception:
                pass  # Telegram rate limit on edits

        def sync_progress(stage: str, percent: int = 0):
            """Bridge sync callback to async — best effort UI update."""
            try:
                asyncio.run_coroutine_threadsafe(update_progress(stage, percent), main_loop)
            except Exception:
                pass

        try:
            # Run pipeline in executor to avoid blocking the event loop
            loop = asyncio.get_running_loop()
            report, metadata = await loop.run_in_executor(
                None,
                lambda: self.insight_pipeline.generate(
                    signal=signal,
                    news_headlines=news_headlines,
                    fear_greed=fear_greed,
                    risk_profile=risk_profile,
                    timeline_history=timeline_str,
                    on_progress=sync_progress,
                ),
            )
        except Exception as e:
            logger.error(f"InsightPipeline failed for {symbol}: {e}", exc_info=True)
            await status_msg.edit_text(
                f"❌ Multi-Agent Pipeline ล้มเหลว: {e}\n\n"
                f"ลองใช้ /scan {symbol} แทนได้ครับ"
            )
            return

        # Save memory snapshot asynchronously for user continuity
        targets = metadata.get("targets", [])
        price = metadata.get("price", snapshots[symbol].current_price)
        if user_db_id and price:
            try:
                async with self.db.session() as session:
                    from src.memory import MemoryManager
                    targets_joined = ", ".join(f"{t}" for t in targets) if targets else None
                    await MemoryManager.save_memory_snapshot(
                        session=session,
                        user_id=user_db_id,
                        symbol=symbol,
                        price=float(price),
                        target_prices_str=targets_joined,
                        thesis_status=metadata.get("thesis_status", "CONTINUING"),
                        thesis_summary=metadata.get("thesis_summary", ""),
                        calibrated_confidence=metadata.get("calibrated_confidence", 80),
                        market="TH" if symbol.endswith(".BK") else "US"
                    )
            except Exception as mem_err:
                logger.error(f"Failed to persist memory snapshot for {symbol}: {mem_err}")

        # --- Send final report ---
        # Telegram has a 4096 char limit per message
        if len(report) > 4000:
            # Split into chunks
            chunks = [report[i:i+4000] for i in range(0, len(report), 4000)]
            await status_msg.edit_text(chunks[0], parse_mode="Markdown")
            for chunk in chunks[1:]:
                try:
                    await message.reply(chunk, parse_mode="Markdown")
                except Exception:
                    await message.reply(chunk)
        else:
            try:
                await status_msg.edit_text(report, parse_mode="Markdown")
            except Exception as e:
                logger.warning(f"Markdown parse error: {e}. Sending as plain text.")
                await status_msg.edit_text(report)

        # --- Send Chart right after report ---
        if targets and price:
            try:
                from src.charting import ChartGenerator
                from aiogram.types import BufferedInputFile
                chart_bytes = ChartGenerator.generate_target_chart(symbol, price, targets)
                if chart_bytes:
                    photo = BufferedInputFile(chart_bytes, filename=f"{symbol}_chart.png")
                    await message.answer_photo(photo=photo, caption=f"📊 **{symbol} Target Zones Deep Dive Chart**", parse_mode="Markdown")
            except Exception as err:
                logger.error(f"Error sending insight chart for {symbol}: {err}")

    async def handle_photo_slip(self, message: types.Message):
        status = await message.reply("📸 กำลังให้ AI สแกนสลิป...")
        # Download photo bytes
        file = await self.bot.get_file(message.photo[-1].file_id)
        img_bytes = await self.bot.download_file(file.file_path)

        api_key = getattr(self.config, "gemini_api_key", None) or (self.config.gemini_api_keys[0] if self.config.gemini_api_keys else "")
        parser = GeminiSlipParser(api_key=api_key)
        if hasattr(img_bytes, "read"):
            raw_bytes = img_bytes.read()
            if not raw_bytes and hasattr(img_bytes, "getvalue"):
                raw_bytes = img_bytes.getvalue()
        elif isinstance(img_bytes, bytes):
            raw_bytes = img_bytes
        else:
            raw_bytes = bytes(img_bytes)

        data = await parser.parse_slip(raw_bytes)

        if not data:
            await status.edit_text("❌ ไม่พบข้อมูลการซื้อขายหุ้น US ในรูปนี้ครับ")
            return

        text = (
            f"🎯 **สแกนสลิปสำเร็จ!**\n"
            f"กรุณาตรวจสอบความถูกต้องก่อนบันทึก:\n\n"
            f"🛒 **รายการ:** `{data['action']}`\n"
            f"📌 **หุ้น:** `{data['symbol']}`\n"
            f"📦 **จำนวน:** `{data['volume']}` หุ้น\n"
            f"💰 **ราคา:** `${data['price']}`\n"
        )
        try:
            total = float(data['price']) * float(data['volume'])
            text += f"💸 **รวมเป็นเงิน:** `${total:,.2f}`\n\n"
        except Exception:
            text += "\n"
        text += "ถูกต้องไหมครับ? กดปุ่มด้านล่างเพื่อยืนยัน ⬇️"

        # Save temp data in state or callback string
        cb_data = f"slip_confirm_{data['symbol']}_{data['action']}_{data['price']}_{data['volume']}"
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ ยืนยันบันทึก", callback_data=cb_data),
                    InlineKeyboardButton(text="❌ ยกเลิก", callback_data="slip_cancel"),
                ]
            ]
        )
        await status.edit_text(text, reply_markup=markup, parse_mode="Markdown")

    async def handle_slip_confirm(self, cq: types.CallbackQuery):
        _, _, sym, act, prc, vol = cq.data.split("_")
        user = await self.db.get_user(cq.from_user.id, username=cq.from_user.username)
        async with self.db.session() as session:
            txn = PortfolioTransaction(
                user_id=user.id,
                symbol=sym,
                action=act,
                price=float(prc),
                shares=float(vol),
            )
            session.add(txn)
            await session.commit()
        await cq.message.edit_text(f"✅ บันทึก {act} {sym} จำนวน {vol} หุ้น เข้าพอร์ตเรียบร้อยแล้ว!")

    async def handle_slip_cancel(self, cq: types.CallbackQuery):
        await cq.message.edit_text("❌ ยกเลิกการบันทึกสลิปครับ")

    async def cmd_portfolio(self, message: types.Message):
        user = await self.db.get_user(message.from_user.id)
        status = await message.reply("⏳ กำลังคำนวณต้นทุนพอร์ตและดึงราคาตลาดสด...")

        async with self.db.session() as session:
            res = await session.execute(select(PortfolioTransaction).where(PortfolioTransaction.user_id == user.id))
            txns = res.scalars().all()

        if not txns:
            await status.edit_text("พอร์ตคุณยังว่างเปล่า! โยนรูปสลิปแอปเทรดเข้ามาเพื่อเริ่มบันทึกพอร์ตได้เลยครับ")
            return

        # Group logic
        portfolio = {}
        for t in txns:
            if t.symbol not in portfolio:
                portfolio[t.symbol] = {"shares": 0, "total_cost": 0}
            if t.action == "BUY":
                portfolio[t.symbol]["shares"] += t.shares
                portfolio[t.symbol]["total_cost"] += t.price * t.shares
            elif t.action == "SELL":
                portfolio[t.symbol]["shares"] -= t.shares
                # Simplified sell logic for average cost preservation

        # Fetch prices and format
        lines = ["💼 **สรุปพอร์ต DCA ของคุณ**\n```", "━━━━━━━━━━━━━━━━━━━━━━━"]
        for sym, data in portfolio.items():
            if data["shares"] <= 0:
                continue
            avg_cost = data["total_cost"] / data["shares"]
            # fetcher logic
            live_price = await self.fetcher.fetch_current_price(sym)
            pnl_pct = ((live_price - avg_cost) / avg_cost) * 100
            emoji = "🟢" if pnl_pct >= 0 else "🔴"
            sign = "+" if pnl_pct >= 0 else ""
            lines.append(f"📌 {sym} | {data['shares']:,.2f} หุ้น")
            lines.append(f"   ต้นทุน:  ${avg_cost:,.2f}")
            lines.append(f"   ปัจจุบัน: ${live_price:,.2f}")
            lines.append(f"   P/L:    {emoji} {sign}{pnl_pct:.2f}%")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("```")

        if len(lines) == 2:
            await status.edit_text("พอร์ตคุณยังว่างเปล่า! โยนรูปสลิปแอปเทรดเข้ามาเพื่อเริ่มบันทึกพอร์ตได้เลยครับ")
            return

        await status.edit_text("\n".join(lines), parse_mode="Markdown")



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
