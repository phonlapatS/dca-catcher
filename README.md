# DCA Catcher 📈

**DCA Catcher** คือระบบ Telegram Bot ผู้ช่วยวิเคราะห์หุ้นและติดตามราคาเป้าหมายสำหรับการลงทุนแบบ DCA (Dollar-Cost Averaging) รองรับทั้งหุ้นสหรัฐฯ (US) และหุ้นไทย (TH) ทำงานร่วมกับข้อมูลราคาตลาดจริง ข่าวสาร ดัชนีอารมณ์ตลาด และระบบเฝ้าราคาแบบเรียลไทม์


## 🚀 What's New in Phase 5 (พัฒนาต่อยอดจาก Phase 4 อย่างไร?)

ใน Phase 4 ระบบสร้างกราฟและตีเส้นเป้าหมายได้แล้ว สำหรับ **Phase 5** เราได้ยกระดับ "ความฉลาดในการวิเคราะห์" ไปสู่ขีดสุดด้วย:
1. **Multi-Agent Pipeline:** เปลี่ยนจากการใช้ AI ตัวเดียว เป็นการใช้ "ทีมผู้เชี่ยวชาญ (Sub-Agents)" 
2. **Specialist Roles:** มีทั้ง AI ผู้เชี่ยวชาญด้านพื้นฐาน (Fundamental), ด้านข่าว/อารมณ์ตลาด (Sentiment), และด้านการจัดการความเสี่ยง (Risk Strategy) ทำงานคู่ขนานกัน
3. **Synthesis & Quality Gate:** มี AI หัวหน้างาน (Composer) ทำหน้าที่รวมบทวิเคราะห์ และตัวตรวจสอบคุณภาพ (Quality Gate) กรองข้อมูลหลอน (Hallucinations) ก่อนส่งถึงผู้ใช้

---

---

## ⚙️ กระบวนการทำงานของระบบ (How It Works)

ระบบถูกออกแบบให้ทำงานแบบแยกชั้น (Decoupled Architecture) โดยแบ่งกระบวนการหลักออกเป็น 4 ส่วน:

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│ 1. Data Ingestion│ ──> │ 2. Analysis & AI │ ──> │ 3. Chart & Delivery │
│ yfinance / News │     │ Indicators / LLM │     │  Telegram & Buttons │
└─────────────────┘     └──────────────────┘     └─────────────────────┘
                               ▲
                               │
┌──────────────────────────────┴───────────────────────────┐
│ 4. Real-time Monitoring & Webhooks (Alpaca / TradingView) │
└──────────────────────────────────────────────────────────┘
```

---

### กระบวนการที่ 1: การสแกนหุ้นรายตัว (`/scan <SYMBOL>`)

เมื่อผู้ใช้พิมพ์คำสั่งสแกน เช่น `/scan NVDA`:
1. **ดึงข้อมูลดิบ (Data Fetching):** ดึงราคา OHLCV ย้อนหลัง 3 เดือน, งบการเงินพื้นฐาน (P/E Trailing, PEG, Revenue Growth, Margin, Debt/Equity) ผ่าน `yfinance`
2. **คำนวณ Technical Indicators:** คำนวณ % การย่อตัวจากจุดสูงสุด (ATH Drawdown), การตรวจจับ Volume ผิดปกติ (>1.5 เท่าของค่าเฉลี่ย 20 วัน) และค่าเฉลี่ยเคลื่อนที่
3. **ประเมินผลผ่าน AI (Scoring & Target Planning):** ส่งตัวชี้วัดที่คำนวณแล้วให้ Gemini LLM ช่วยสรุปคะแนนความน่าลงทุน (1-10) และเสนอราคาเป้าหมาย DCA 3 ระดับ (ไม้ 1 ความเสี่ยงต่ำ, ไม้ 2 ปานกลาง, ไม้ 3 โซนลึก)
4. **สร้างกราฟแท่งเทียน (In-Memory Charting):** 
   - โมดูล `src/charting.py` นำข้อมูลราคามาวาดกราฟ Candlestick ด้วย `mplfinance`
   - ตีเส้นประระดับราคาเป้าหมาย 3 เส้น (สีฟ้า) และเส้นราคาปัจจุบัน (สีเขียว)
   - หากราคาเป้าหมายไม้ 3 ลึกกว่าจุดต่ำสุดในรอบ 3 เดือน ระบบจะขยาย Timeframe เป็น 6 เดือน หรือ 1 ปีอัตโนมัติ (Adaptive Timeframe) เพื่อให้เส้นพาดทับแนวรับในอดีตจริง
   - บันทึกภาพลง RAM (`io.BytesIO`) โดยไม่เซฟไฟล์ลง Harddisk
5. **ส่งผลลัพธ์เข้า Telegram:** 
   - ส่งข้อความบทวิเคราะห์ภาษาไทย พร้อมปุ่ม Checkbox เลือกราคาเป้าหมาย
   - ส่งภาพกราฟตามต่อท้ายข้อความ
   - หากผู้ใช้กดเลือกราคาแล้วกด `🎯 ยืนยันเป้าหมาย` ระบบจะบันทึกเป้าหมายเข้า Database และเพิ่มเข้าคิวเฝ้าราคาของ WebSocket ทันที (หรือกด `❌ ยังไม่สนใจ / ข้าม` เพื่อซ่อนปุ่ม)

---

### กระบวนการที่ 2: การวิเคราะห์เชิงลึกแบบหลายขั้นตอน (Multi-Agent Insight Pipeline)

เมื่อผู้ใช้กดปุ่ม **`📖 เจาะลึกบทวิเคราะห์ (Deep Dive)`** หรือใช้คำสั่ง `/scan-details`:
ระบบจะส่งต่อข้อมูลเข้าสู่ Pipeline ที่แบ่งหน้าที่ทำงานเป็นขั้นตอนเพื่อลดอาการข้อมูลคลาดเคลื่อน (Hallucination):

1. **Data Collector (Python):** รวบรวมข่าวย้อนหลัง 7 วันจาก Google News RSS, ดัชนี Fear & Greed Index จาก CNN, และงบการเงินจริง
2. **Fundamental Analyst (Specialist 1):** ตรวจสอบคุณภาพงบการเงิน หนี้สิน การเติบโต และความผิดปกติของ Volume
3. **News & Sentiment Analyst (Specialist 2):** กรองข่าวเฉพาะที่เกี่ยวข้องกับหุ้นตัวนั้น และจัดหมวดหมู่อารมณ์ข่าว (บวก/ลบ/เป็นกลาง)
4. **Risk & Target Strategist (Specialist 3):** อ่านผลจากขั้นตอน 1 และ 2 เพื่อนำมาคำนวณราคาเป้าหมาย 3 ไม้ให้สอดคล้องกับปัจจัยพื้นฐาน
5. **Composer:** เรียบเรียงข้อมูลทั้งหมดเป็นบทวิเคราะห์ภาษาไทยเชิงลึกที่อ่านเข้าใจง่าย
6. **Quality Gate:** ตรวจสอบความถูกต้องของตัวเลขและเหตุผล ให้คะแนนคุณภาพ 0-100% (หากคะแนนไม่ผ่านเกณฑ์ จะส่ง Remark ให้ Composer ปรับปรุงเฉพาะจุด สูงสุด 2 รอบ)

---

### กระบวนการที่ 3: การเฝ้าราคาแบบเรียลไทม์ (`Alpaca WebSocket`)

1. **การเชื่อมต่อ:** ในช่วงเวลาตลาดสหรัฐฯ เปิดทำการ (20:30 - 04:00 น. ตามเวลาไทย) บอทจะเปิด WebSocket เชื่อมต่อกับ Alpaca Data Stream (IEX)
2. **การตรวจจับราคา:** เมื่อมี Tick ข้อมูลราคาเทรดล่าสุดเข้ามา ระบบจะนำราคาไปเปรียบเทียบกับราคาเป้าหมายใน Watchlist
3. **ระบบป้องกันการสแปม (Hysteresis):** เมื่อราคาลงมาถึงเป้าหมาย ระบบจะส่งข้อความแจ้งเตือนทาง Telegram (DM หรือ Tag ในกลุ่ม) เพียง **1 ครั้งต่อโซนราคา** (`last_notified_zone`) และจะไม่ส่งซ้ำตราบใดที่ราคายังแกว่งตัวอยู่ในโซนเดิม

---

### กระบวนการที่ 4: การรับสัญญาณภายนอก (`TradingView Webhooks`)

1. บอทเปิด HTTP Server ขนาดเล็กด้วย `aiohttp` ที่พอร์ต `8080` (ตั้งค่าได้ใน `.env`)
2. รอรับ Webhook จาก TradingView ที่ Endpoint `POST /webhook/{WEBHOOK_SECRET}`
3. เมื่อได้รับสัญญาณแจ้งเตือน ระบบจะตรวจสอบ Secret Key ตอบรับ `200 OK` กลับไปยัง TradingView ภายในเสี้ยววินาที แล้วโยนคำสั่งให้ AI สแกนหุ้นและส่งผลเข้า Telegram ทันที

---

## 📌 คำสั่งการใช้งานบอท (Bot Commands)

| คำสั่ง | หน้าที่และผลลัพธ์ |
|---|---|
| `/start` | เริ่มต้นใช้งานบอท และลงทะเบียนผู้ใช้เข้าฐานข้อมูล |
| `/scan <SYMBOL>` | สแกนหุ้นรายตัว (เช่น `/scan NVDA` หรือ `/scan PTT.BK`) พร้อมกราฟและปุ่มเลือกเป้าหมาย |
| `/scan` | สแกนหุ้นทั้งหมดที่มีอยู่ใน Watchlist ของผู้ใช้ |
| `/scan-details <SYMBOL>` | สั่งรันบทวิเคราะห์เชิงลึก (Deep Dive Report) |
| `/add <SYMBOL> [PRICE]` | เพิ่มหุ้นเข้า Watchlist พร้อมระบุราคาเป้าหมาย (หรือเพิ่มเดี่ยวๆ ได้) |
| `/remove <SYMBOL>` | ลบหุ้นออกจาก Watchlist |
| `/list` | แสดงรายชื่อหุ้นและระดับราคาเป้าหมายที่บันทึกไว้ |
| `/survey` | ทำแบบประเมินความเสี่ยงเพื่อบันทึกโปรไฟล์การลงทุนของผู้ใช้ |
| `/advice` | ออกแบบพอร์ตโฟลิโอตามระยะเวลาลงทุนและเป้าหมายผลตอบแทน |
| `/help` | แสดงคำอธิบายคำสั่งทั้งหมด |

---

## 📁 โครงสร้างโปรเจกต์ (Project Structure)

```
dca-catcher/
├── src/
│   ├── bot.py                # Telegram Bot Handlers, Keyboards & Dispatcher
│   ├── config.py             # จัดการ Environment Variables และการตั้งค่าระบบ
│   ├── models.py             # Domain Models กลาง (TargetZone Single Source of Truth)
│   ├── database.py           # จัดการฐานข้อมูล SQLite ผ่าน Async SQLAlchemy
│   ├── fetcher.py            # ดึงข้อมูลตลาดและงบการเงินผ่าน yfinance
│   ├── transform.py          # คำนวณ Technical Indicators และ Volume Anomaly
│   ├── grader.py             # ประเมินคะแนนความน่าลงทุนและคำนวณเป้าหมายเบื้องต้น
│   ├── insight_pipeline.py   # Multi-Agent Pipeline (Specialists, Composer, Quality Gate)
│   ├── charting.py           # สร้างกราฟ Candlestick และ Target Lines (In-Memory)
│   ├── webhook.py            # aiohttp Server รองรับ Webhook จาก TradingView
│   ├── sniper.py             # Alpaca WebSocket สตรีมราคาเรียลไทม์
│   ├── alert_manager.py      # จัดรูปแบบข้อความแจ้งเตือนและระบบ Anti-Spam
│   └── scrapers/
│       └── sentiment.py      # ดึงข่าว Google News RSS และดัชนี Fear & Greed
├── tests/                    # ชุดทดสอบ Unit & Integration Tests (47 รายการ)
├── requirements.txt          # รายการ Python Dependencies
├── Dockerfile                # ไฟล์สำหรับ Build Docker Container
└── docker-compose.yml        # คอนฟิกสำหรับรันระบบบน Docker
```

---

## 🚀 การติดตั้งและรันระบบ (Setup & Running)

### 1. เตรียมสภาพแวดล้อม (Prerequisites)
- Python 3.10 ขึ้นไป
- บัญชี Telegram Bot Token (จาก @BotFather)
- Gemini API Key (จาก Google AI Studio)
- Alpaca API Keys (สำหรับระบบ Real-time Price Stream)

### 2. ติดตั้ง Dependencies
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. ตั้งค่าไฟล์สภาพแวดล้อม (`.env`)
สร้างไฟล์ `.env` ที่โฟลเดอร์หลักของโปรเจกต์:
```env
TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
GEMINI_API_KEYS="key1,key2"
DATABASE_URL="sqlite+aiosqlite:///dca_catcher.db"
BROADCAST_CHANNEL_ID="-100xxxxxxxxx"

# Alpaca WebSocket
ALPACA_API_KEY="your_alpaca_key"
ALPACA_SECRET_KEY="your_alpaca_secret"
ALPACA_SNIPER_START="20:30"
ALPACA_SNIPER_END="04:00"

# Webhook Server
WEBHOOK_PORT=8080
WEBHOOK_SECRET="your_custom_secret_key"
```

### 4. รันการทดสอบ (Run Tests)
```bash
venv/bin/pytest
```

### 5. เริ่มต้นการทำงานของบอท (Run Bot)
```bash
set -a && source .env && set +a && PYTHONPATH=. venv/bin/python -m src.bot
```

หรือรันผ่าน Docker:
```bash
docker-compose up -d --build
```
