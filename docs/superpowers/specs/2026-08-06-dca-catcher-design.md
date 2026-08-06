# DCA Catcher (Automated DCA & Signal Assistant) - Design Specification

## 1. Project Overview
ระบบ AI Agent ผู้ช่วยสแกนตลาด สรุปข่าวสาร และวิเคราะห์สัญญาณเข้าซื้อหุ้นเป้าหมายสำหรับสาย DCA โดยดึงข้อมูลราคา ปริมาณการซื้อขาย และข่าวสาร มาสังเคราะห์และประเมินความเสี่ยง แจ้งเตือนผ่าน Telegram Bot ในจังหวะเวลาที่เหมาะสม (Smart Notification) โครงการนี้เน้นใช้เครื่องมือฟรี (Free Tier) ทั้งหมด

## 2. System Architecture
- **Core Workflow**: LangGraph Agent (Fetch -> Transform -> Analyze -> Grade -> Notify)
- **Execution**: Single Docker Container, async Python (asyncio)
- **Triggers**:
  1. **Scheduler**: Daily Summary (07:00) & Pre-market (09:30 TH / 20:00 US)
  2. **Real-time Monitor**: Polling every 15 mins during market hours (alerts on >= 5% drop)
  3. **Manual**: User `/scan` command via Telegram
- **Database**: PostgreSQL (Store users, watchlists, market history, news cache, signals)

## 3. Data Sources (Free Tier Strategy)
- **Market Data (OHLCV)**: `yfinance` (Supports US and TH `.BK` stocks)
- **News**: Google News RSS + Custom Web Scraping
- **Market Sentiment**: CNN Fear & Greed Index (Scraping)
- **Technical Indicators**: Python `ta` library (RSI, etc.)
- **AI Engine**: Google Gemini (Free Tier) for summarization and risk grading

## 4. Analysis Logic (The 3 Dimensions)
เพื่อป้องกันปัญหา Overfitting และ Outliers ข้อมูลจะถูกประมวลผลผ่าน `TRANSFORM` node (ตรวจสอบความถูกต้อง/กรองข้อมูลขยะ) และ `ANALYZE` node (Python) จะจัดกลุ่ม 6 ตัวชี้วัดเป็น 3 มิติ ก่อนส่งให้ AI ประเมิน:
1. **PRICE (ราคา)**: ATH Drawdown %, RSI -> ราคาน่าสนใจหรือไม่?
2. **FLOW (แรงซื้อขาย)**: Volume Anomaly (vs 20d avg) -> มีแรงซื้อกลับหรือไม่?
3. **CONTEXT (บริบท)**: News Sentiment, Fear & Greed, Historical Recovery -> สถานการณ์โดยรวมเอื้อต่อการฟื้นตัวหรือไม่?

## 5. AI Grading & Signal Format
`GRADE` node (Gemini) จะวิเคราะห์ข้อมูลทั้ง 3 มิติและสังเคราะห์ออกมาในรูปแบบ JSON:
- **Grades**: 🔴 (เสี่ยงมาก/1) | 🟡 (ปานกลาง/2) | 🟢 (เสี่ยงน้อย/3) | 🌟 (เข้าซื้อได้เลย/4)
- **Reason Tags**: แสดงเหตุผลรองรับทั้งเชิงบวกและลบ (เช่น `✅ RSI ต่ำกว่า 30`, `⚠️ ปริมาณซื้อขายต่ำกว่าค่าเฉลี่ย 45%`)
- **AI Advice & Hashtags**: สังเคราะห์ความขัดแย้ง/สอดคล้องของข้อมูล
  - Examples: `#ควรซื้อตอนนี้`, `#รอดูสถานการณ์ก่อน`, `#ไม่ควรซื้อตอนนี้`
  - Cross-analysis: "ราคาลดลง RSI Oversold แต่ปริมาณการซื้อขายต่ำมาก แนะนำให้รอดูสถานการณ์"

## 6. Smart Notification Strategy
ลดการแจ้งเตือนที่น่ารำคาญ ส่งเมื่อผู้ใช้สามารถตัดสินใจได้จริง:
- **07:00**: Daily Summary (ภาพรวมตลาดสั้นๆ, สรุป Fear/Greed, จัดอันดับหุ้นน่าสนใจ)
- **09:30 (เวลาไทย)**: SET Pre-market deep signal (สำหรับหุ้นไทย)
- **20:00 (เวลาไทย)**: US Pre-market deep signal (อิงตามเวลา DIME สำหรับหุ้นอเมริกา)
- **Intraday**: แจ้งเตือนฉุกเฉินเฉพาะเมื่อราคาร่วง >= 5% ในระหว่างวัน

## 7. Database Schema (PostgreSQL)
รองรับ Multi-user (เพื่อนๆ ในกลุ่ม):
- `users`: id, telegram_id, username, created_at
- `watchlists`: id, user_id, symbol, market (US/TH), added_at
- `market_data`: symbol, date, ohlcv, volume, rsi, ath_price, drawdown_pct, fetched_at
- `news_cache`: symbol, headline, source_url, summary, sentiment, published_at, scraped_at
- `signals`: symbol, grade, fear_greed_index, indicators_json, signal_text, trigger_type, created_at

## 8. Telegram Commands
- `/start` - เริ่มต้นใช้งานและแนะนำระบบ
- `/add <symbol> <market>` - เพิ่มหุ้น (เช่น `/add NVDA US`, `/add PTT TH`)
- `/remove <symbol>` - ลบหุ้น
- `/list` - ดูรายชื่อหุ้นที่ติดตาม
- `/scan [symbol]` - วิเคราะห์ทันที
- `/settings` - ตั้งค่าการแจ้งเตือน (เปิด/ปิด)
- รองรับ Interactive Inline Keyboards (ปุ่มกดในแชท) สำหรับ Action ด่วน (เช่น กดปุ่ม Scan ละเอียดจากการแจ้งเตือน)
