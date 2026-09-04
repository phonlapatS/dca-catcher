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


class SurveyMixin:

    async def cmd_survey(self, message: types.Message, state: FSMContext):
        """Start the risk profile survey."""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text='🛡️ ถือยาวเน้นปันผล (Safe & Value)',
            callback_data='style_safe')], [InlineKeyboardButton(text=
            '⚖️ DCA สะสมเรื่อยๆ (Moderate)', callback_data='style_mod')], [
            InlineKeyboardButton(text='🚀 เก็งกำไรระยะสั้น (Aggressive)',
            callback_data='style_agg')]])
        await message.answer(
            'มาทำความรู้จักสไตล์การลงทุนของคุณกันครับ 📊\nคุณเน้นลงทุนแบบไหน?',
            reply_markup=keyboard)
        await state.set_state(RiskSurvey.waiting_for_style)

    async def survey_style(self, callback: types.CallbackQuery, state:
        FSMContext):
        await callback.answer()
        style = callback.data.split('_')[1]
        style_map = {'safe': 'เน้นปลอดภัย ซื้อเมื่อถูกมาก', 'agg':
            'เก็งกำไร ซื้อเมื่อย่อตัวเล็กน้อย', 'mod': 'DCA ทยอยสะสมเรื่อยๆ'}
        await state.update_data(style=style_map.get(style, 'DCA'))
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=
            '🟢 รับความเสี่ยงได้ต่ำ (ทนติดลบ 1-10%)', callback_data='dd_10')
            ], [InlineKeyboardButton(text=
            '🟡 รับความเสี่ยงปานกลาง (ทนติดลบ 11-30%)', callback_data=
            'dd_30')], [InlineKeyboardButton(text=
            '🔴 รับความเสี่ยงสูง (ทนติดลบ 30-50%)', callback_data='dd_50')],
            [InlineKeyboardButton(text=
            '⚠️ ไม่มีเงินเย็น (ไม่แนะนำให้ลงทุน DCA)', callback_data=
            'dd_none')]])
        await callback.message.edit_text(
            """เยี่ยมครับ! ต่อไปคือแบบประเมินความเสี่ยง (เหมือนที่ธนาคารถามเลยครับ)

ถ้าราคาหุ้นในพอร์ตร่วงลง คุณสามารถทนเห็นพอร์ตติดลบได้สูงสุดเท่าไหร่ ก่อนจะรู้สึกกังวล?"""
            , reply_markup=keyboard)
        await state.set_state(RiskSurvey.waiting_for_drawdown)

    async def survey_drawdown(self, callback: types.CallbackQuery, state:
        FSMContext):
        await callback.answer()
        dd = callback.data.split('_')[1]
        data = await state.get_data()
        style = data.get('style')
        dd_map = {'10': 'ต่ำ (ทนติดลบ 1-10%)', '30':
            'ปานกลาง (ทนติดลบ 11-30%)', '50': 'สูง (ทนติดลบ 30-50%)',
            'none': 'ไม่มีเงินเย็น (ผิดหลัก DCA)'}
        if dd == 'none':
            profile = f'สไตล์: {style}, ความเสี่ยง: {dd_map[dd]}'
            msg_reply = f"""📝 ระบบบันทึกโปรไฟล์ของคุณแล้วครับ:
**{profile}**

⚠️ **คำแนะนำ:** การลงทุนแบบ DCA ต้องใช้ 'เงินเย็น' ที่สามารถทิ้งไว้ได้นานโดยไม่ต้องรีบใช้ หากตอนนี้ยังไม่มีเงินเย็น แนะนำให้เก็บออมเงินสดไว้ก่อนนะครับ หรือถ้าวิเคราะห์หุ้น AI จะให้คำแนะนำแบบระมัดระวังสูงสุดครับ!"""
        else:
            profile = f'สไตล์: {style}, รับความเสี่ยงได้: {dd_map[dd]}'
            msg_reply = f"""บันทึกเรียบร้อย! 📝 ระบบจำได้แล้วว่าคุณเป็นสาย:
**{profile}**

ต่อไปนี้เวลาคุณพิมพ์ /scan AI จะปรับราคาเป้าหมายให้เข้ากับสไตล์ของคุณโดยเฉพาะครับ!"""
        telegram_id = callback.from_user.id
        async with self.db.session() as session:
            stmt = select(User).where(User.telegram_id == telegram_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            if user:
                user.risk_profile = profile
                await session.commit()
        await callback.message.edit_text(msg_reply, parse_mode='Markdown')
        await state.clear()

    async def cmd_advice(self, message: types.Message, state: FSMContext):
        """Start the personalized stock recommendation survey."""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text='⏳ 1-3 เดือน (เก็งกำไรระยะสั้นมากๆ)',
            callback_data='hz_1_3m')], [InlineKeyboardButton(text=
            '⌛ 3-6 เดือน (รอบเทรดระยะสั้น-กลาง)', callback_data='hz_3_6m')],
            [InlineKeyboardButton(text='📅 1-3 ปี (ระยะกลาง)', callback_data
            ='hz_1_3y')], [InlineKeyboardButton(text='📆 3-5 ปี (ระยะยาว)',
            callback_data='hz_3_5y')], [InlineKeyboardButton(text=
            '🗓️ 5-10 ปีขึ้นไป (เพื่อเกษียณ)', callback_data='hz_5_10y')]])
        await message.answer(
            """🌟 **AI Personalized Stock Matchmaker** 🌟

เป้าหมายของเงินก้อนนี้ คุณตั้งใจจะนำไปลงทุนและถือไว้นานแค่ไหนครับ?"""
            , reply_markup=keyboard, parse_mode='Markdown')
        await state.set_state(AdviceSurvey.waiting_for_horizon)

    async def advice_horizon(self, callback: types.CallbackQuery, state:
        FSMContext):
        await callback.answer()
        hz_map = {'hz_1_3m': '1-3 เดือน', 'hz_3_6m': '3-6 เดือน', 'hz_1_3y':
            '1-3 ปี', 'hz_3_5y': '3-5 ปี', 'hz_5_10y': '5-10 ปีขึ้นไป'}
        await state.update_data(horizon=hz_map.get(callback.data, '1-3 ปี'))
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text='💸 เน้นปันผล (Dividend Income)',
            callback_data='gl_div')], [InlineKeyboardButton(text=
            '📈 เน้นราคาเติบโต (Capital Gain)', callback_data='gl_grow')], [
            InlineKeyboardButton(text='⚖️ เน้นผสมผสาน (Balanced)',
            callback_data='gl_bal')]])
        await callback.message.edit_text(
            'สิ่งที่คุณคาดหวังที่สุดจากการถือหุ้นชุดนี้คืออะไรครับ?',
            reply_markup=keyboard)
        await state.set_state(AdviceSurvey.waiting_for_goal)

    async def advice_goal(self, callback: types.CallbackQuery, state:
        FSMContext):
        await callback.answer()
        gl_map = {'gl_div': 'เน้นปันผล', 'gl_grow': 'เน้นเติบโต', 'gl_bal':
            'เน้นผสมผสาน'}
        await state.update_data(goal=gl_map.get(callback.data, 'เน้นผสมผสาน'))
        await state.update_data(sectors=[])
        await self._show_sector_keyboard(callback.message, state)
        await state.set_state(AdviceSurvey.waiting_for_sector)

    async def _show_sector_keyboard(self, message: types.Message, state:
        FSMContext):
        data = await state.get_data()
        sectors = data.get('sectors', [])
        buttons = []
        for key, name in ALL_SECTORS.items():
            text = f'✅ {name}' if name in sectors else name
            buttons.append([InlineKeyboardButton(text=text, callback_data=key)]
                )
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        count = len(sectors)
        text = f"""คุณมีความเชื่อมั่น หรือสนใจในอุตสาหกรรมไหนเป็นพิเศษไหมครับ?
(เลือกมา 3 อันดับแรก - ตอนนี้เลือกแล้ว {count}/3 อันดับ)"""
        if isinstance(message, types.Message):
            await message.edit_text(text, reply_markup=keyboard)

    async def advice_sector(self, callback: types.CallbackQuery, state:
        FSMContext):
        await callback.answer()
        selected_name = ALL_SECTORS.get(callback.data)
        if not selected_name:
            return
        data = await state.get_data()
        sectors = data.get('sectors', [])
        if selected_name in sectors:
            sectors.remove(selected_name)
        elif len(sectors) < 3:
            sectors.append(selected_name)
        await state.update_data(sectors=sectors)
        if len(sectors) == 3:
            await state.update_data(current_sub_idx=0, detailed_sectors=[])
            await self._ask_next_subsector(callback.message, state)
        else:
            await self._show_sector_keyboard(callback.message, state)

    async def _ask_next_subsector(self, message: types.Message, state:
        FSMContext):
        data = await state.get_data()
        sectors = data.get('sectors', [])
        idx = data.get('current_sub_idx', 0)
        if idx >= len(sectors):
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text='🎯 แนะนำ 3 ตัว (เน้นๆ โฟกัสๆ)',
                callback_data='cnt_3')], [InlineKeyboardButton(text=
                '🖐️ แนะนำ 5 ตัว (มาตรฐาน)', callback_data='cnt_5')], [
                InlineKeyboardButton(text=
                '🍀 แนะนำ 7 ตัว (กระจายความเสี่ยง)', callback_data='cnt_7')],
                [InlineKeyboardButton(text='🔟 แนะนำ 10 ตัว (จัดพอร์ตใหญ่)',
                callback_data='cnt_10')]])
            text = (
                'เกือบเสร็จแล้วครับ! 📈\nคุณอยากให้ AI แนะนำหุ้นกี่ตัวสำหรับพอร์ตนี้ครับ?'
                )
            if isinstance(message, types.Message):
                await message.edit_text(text, reply_markup=keyboard)
            await state.set_state(AdviceSurvey.waiting_for_count)
            return
        current_main_sector = sectors[idx]
        current_chosen_subs = data.get('current_chosen_subs', [])
        subs = SUBSECTORS.get(current_main_sector, {'sub_any':
            'สนใจทั้งหมดในกลุ่มนี้'})
        buttons = []
        for key, name in subs.items():
            text = f'✅ {name}' if key in current_chosen_subs else name
            buttons.append([InlineKeyboardButton(text=text, callback_data=key)]
                )
        if current_chosen_subs:
            buttons.append([InlineKeyboardButton(text=
                '➡️ ยืนยันกลุ่มย่อย (Next)', callback_data='sub_confirm')])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        text = f"""สำหรับกลุ่ม **{current_main_sector}**
คุณสนใจเจาะจงไปที่กลุ่มย่อยไหนเป็นพิเศษครับ? (เลือกได้ 1-3 กลุ่มย่อย)"""
        if isinstance(message, types.Message):
            await message.edit_text(text, reply_markup=keyboard, parse_mode
                ='Markdown')
        await state.set_state(AdviceSurvey.waiting_for_subsector)

    async def advice_subsector(self, callback: types.CallbackQuery, state:
        FSMContext):
        await callback.answer()
        data = await state.get_data()
        sectors = data.get('sectors', [])
        idx = data.get('current_sub_idx', 0)
        detailed = data.get('detailed_sectors', [])
        current_chosen_subs = data.get('current_chosen_subs', [])
        current_main_sector = sectors[idx]
        subs = SUBSECTORS.get(current_main_sector, {'sub_any':
            'สนใจทั้งหมดในกลุ่มนี้'})
        if callback.data == 'sub_confirm':
            if not current_chosen_subs:
                return
            chosen_names = [subs.get(k, k) for k in current_chosen_subs]
            names_str = ', '.join(chosen_names)
            detailed.append(f'{current_main_sector} (เน้น: {names_str})')
            await state.update_data(detailed_sectors=detailed,
                current_sub_idx=idx + 1, current_chosen_subs=[])
            await self._ask_next_subsector(callback.message, state)
            return
        if callback.data in current_chosen_subs:
            current_chosen_subs.remove(callback.data)
        elif len(current_chosen_subs) < 3:
            current_chosen_subs.append(callback.data)
        await state.update_data(current_chosen_subs=current_chosen_subs)
        await self._ask_next_subsector(callback.message, state)

    async def advice_count(self, callback: types.CallbackQuery, state:
        FSMContext):
        await callback.answer()
        cnt_str = callback.data.split('_')[1]
        await state.update_data(count=cnt_str)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text='💰 1,000 - 3,000 บาท/เดือน',
            callback_data='bdg_3000')], [InlineKeyboardButton(text=
            '💰 4,000 - 6,000 บาท/เดือน', callback_data='bdg_6000')], [
            InlineKeyboardButton(text='💰 7,000 - 10,000 บาท/เดือน',
            callback_data='bdg_10000')], [InlineKeyboardButton(text=
            '💰 10,000 - 30,000 บาท/เดือน', callback_data='bdg_30000')], [
            InlineKeyboardButton(text='⏭️ ข้าม / ไม่ระบุ', callback_data=
            'bdg_none')]])
        await callback.message.edit_text(
            """ด่านสุดท้ายครับ! 🎉
เพื่อให้ AI คำนวณแผนการออมเงินและการเติบโตให้แม่นยำยิ่งขึ้น คุณมีงบในการ DCA หุ้นพอร์ตนี้ต่อเดือนประมาณเท่าไหร่ครับ?"""
            , reply_markup=keyboard)
        await state.set_state(AdviceSurvey.waiting_for_budget)

    async def advice_budget(self, callback: types.CallbackQuery, state:
        FSMContext):
        await callback.answer()
        budget_map = {'bdg_3000': 'ประมาณ 3,000 บาท/เดือน', 'bdg_6000':
            'ประมาณ 6,000 บาท/เดือน', 'bdg_10000':
            'ประมาณ 10,000 บาท/เดือน', 'bdg_30000':
            'ประมาณ 30,000 บาท/เดือน', 'bdg_none': 'ไม่ระบุ'}
        budget_str = budget_map.get(callback.data, 'ไม่ระบุ')
        await callback.message.edit_text(
            '⏳ AI กำลังประมวลผลข้อมูลและจัดพอร์ตให้คุณ กรุณารอสักครู่...')
        data = await state.get_data()
        horizon = data.get('horizon')
        goal = data.get('goal')
        detailed_sectors = data.get('detailed_sectors', [])
        cnt_str = data.get('count', '5')
        telegram_id = callback.from_user.id
        risk_profile = None
        async with self.db.session() as session:
            stmt = select(User).where(User.telegram_id == telegram_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            if user:
                risk_profile = user.risk_profile
        import asyncio
        advice_text = await asyncio.to_thread(self.grader.generate_advice,
            risk_profile=risk_profile, horizon=horizon, goal=goal, sectors=
            detailed_sectors, count=cnt_str, budget=budget_str)
        try:
            await callback.message.answer(advice_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(
                f'Markdown parse error: {e}. Falling back to plain text.')
            await callback.message.answer(advice_text)
        import re
        tickers = re.findall(
            '(?:^|\\n)(?:\\d+\\.|\\-|\\*)\\s*\\*\\*([A-Z0-9\\.]+)(?:[^\\*]*)\\*\\*'
            , advice_text)
        if not tickers:
            tickers = re.findall(
                '(?:^|\\n)(?:\\d+\\.|\\-|\\*)\\s*([A-Z0-9\\.]+)\\b',
                advice_text)
        if tickers:
            await state.update_data(recommended_tickers=tickers)
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=
                '➕ เพิ่มหุ้นที่แนะนำเข้า Watchlist ทั้งหมด', callback_data=
                'advice_add_wl')], [InlineKeyboardButton(text=
                '⏭️ ข้ามไปก่อน', callback_data='advice_skip_wl')]])
            await callback.message.answer(
                'คุณต้องการเพิ่มหุ้นที่แนะนำข้างต้นเข้าไปใน Watchlist เพื่อติดตามการแจ้งเตือนด้วย AI เป็นประจำทุกวันหรือไม่?'
                , reply_markup=kb)
            await state.set_state(AdviceSurvey.waiting_for_watchlist_decision)
        else:
            await state.clear()

    async def advice_add_watchlist(self, callback: types.CallbackQuery,
        state: FSMContext):
        await callback.answer()
        data = await state.get_data()
        tickers = data.get('recommended_tickers', [])
        telegram_id = callback.from_user.id
        username = callback.from_user.username
        added = []
        for symbol in tickers:
            market = 'TH' if symbol.endswith('.BK') else 'US'
            res = await self._add_to_watchlist(telegram_id, username,
                symbol, market)
            if '✅' in res:
                added.append(symbol)
        if added:
            await callback.message.edit_text(
                f"✅ เพิ่มหุ้น {', '.join(added)} ลงใน Watchlist เรียบร้อยแล้วครับ! บอทจะทำการสแกนรายวันให้ครับ"
                )
        else:
            await callback.message.edit_text(
                'ℹ️ หุ้นทั้งหมดอยู่ใน Watchlist ของคุณอยู่แล้วครับ')
        await state.clear()

    async def advice_skip_watchlist(self, callback: types.CallbackQuery,
        state: FSMContext):
        await callback.answer()
        await callback.message.edit_text(
            'โอเคครับ! ถ้าต้องการเพิ่มทีหลังสามารถใช้คำสั่ง /add <ชื่อหุ้น> ได้ตลอดเลยครับ'
            )
        await state.clear()
