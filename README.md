# DCA Catcher 🚀

DCA Catcher คือ Telegram Bot สำหรับนักลงทุน DCA (Dollar-Cost Averaging) ที่ช่วยวิเคราะห์หุ้นและติดตามราคาเป้าหมายอัตโนมัติ รองรับทั้งตลาดหุ้นสหรัฐฯ (US) และหุ้นไทย (TH) ผ่านข้อมูลตลาดจริง (`yfinance`), ข่าวสารสด (`Google News RSS`), อารมณ์ตลาด (`CNN Fear & Greed Index`), และระบบ Real-time Price Tracking (`Alpaca WebSocket`)

**สถานะปัจจุบัน:** **Phase 5: Multi-Agent Insight Pipeline & Deep Dive Analytics**

---

## 🌟 ฟังก์ชันหลักของระบบ (Current Features)

### 1. ระบบวิเคราะห์หุ้นพื้นฐาน (`/scan`)
- ดึงข้อมูลราคาล่าสุด, จุดสูงสุดตลอดกาล (ATH), % การย่อตัว (ATH Drawdown), ปริมาณการซื้อขาย (Volume)
- ดึงข้อมูลปัจจัยพื้นฐาน: P/E (Trailing), PEG Ratio, Revenue Growth, Profit Margin, Debt to Equity
- AI ประเมินความน่าลงทุน (AI Score 1-10) และระดับความมั่นใจ (Confidence Score 0-100%)
- คำนวณราคาเป้าหมายสำหรับเข้าซื้อแบบ DCA จำนวน 3 ระดับ (อิงตามความเสี่ยงของผู้ใช้)
- มีปุ่ม Interactive ให้ผู้ใช้กดเลือกบันทึกราคาเป้าหมายเข้าสู่ระบบ Sniper ได้ทันที

### 2. Multi-Agent Deep Dive Insight Pipeline (`/scan-details` หรือปุ่มกด) 🧠
ระบบวิเคราะห์เจาะลึกแบบหลายเอเจนต์ (Multi-Agent Architecture) แยกหน้าที่การคิดเพื่อความแม่นยำและลดอาการ Hallucination:
```
[Market Data + News + Fear&Greed]
               │
               ▼
┌───────────────────────────────────────────────┐
│              Data Collector                   │
│   (รวบรวมข้อมูลดิบแบบ Real-time โดยไม่ใช้ LLM)     │
└──────┬───────────────┬───────────────┬────────┘
       │               │               │
       ▼               ▼               ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   Agent 1   │ │   Agent 2   │ │   Agent 3   │
│ Fundamental │ │ News & Sent │ │ Risk/Target │
│   Analyst   │ │   Analyst   │ │  Strategist │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │ (อ่านผล 1+2 ก่อนตั้งเป้า)
       └───────────────┼───────────────┘
                       ▼
        ┌─────────────────────────────┐
        │       Composer Agent        │
        │ (เรียบเรียงเป็นบทความภาษาไทย) │
        └──────────────┬──────────────┘
                       ▼
        ┌─────────────────────────────┐
        │     Quality Gate Agent      │
        │   (ตรวจความถูกต้อง 0-100%)   │
        └──────────────┬──────────────┘
                       │
         ┌─────────────┴─────────────┐
         ▼ (Score ≥ 75)              ▼ (Score < 75)
    [ส่ง Report ให้ User]      [Remark ส่งแก้เฉพาะจุด]
                                     (สูงสุด 2 รอบ)
```

- **Data Collector:** ดึงข้อมูลราคา, งบการเงิน, ข่าว 7 วันล่าสุด, และดัชนี Fear & Greed
- **Agent 1 (Fundamental Analyst):** วิเคราะห์มูลค่าความถูกแพง (Valuation), คุณภาพการเติบโต, หนี้สิน, และความผิดปกติของ Volume
- **Agent 2 (News & Sentiment Analyst):** ทำ Named Entity Recognition (NER) กรองข่าวที่ไม่เกี่ยวข้องออก วิเคราะห์ผลกระทบ (Positive/Negative/Neutral) ของแต่ละข่าว
- **Agent 3 (Risk & Target Strategist):** อ่านผลการวิเคราะห์จาก Agent 1 และ 2 ก่อนนำมาคำนวณเป้าหมายราคา 3 ระดับที่สอดคล้องกับบริบทจริง
- **Composer Agent:** สังเคราะห์ผลลัพธ์ทั้งหมดเป็นบทความเชิงลึกที่เรียบเรียงต่อเนื่อง อ่านเข้าใจง่าย
- **Quality Gate Agent:** ตรวจสอบความถูกต้องของตัวเลข, การอ้างอิงข่าว, ความสมเหตุสมผลของเป้าหมาย และการเรียบเรียง ให้คะแนน 0-100% (หากไม่ผ่านจะส่ง Remark กลับไปแก้เฉพาะจุดโดยไม่ต้องรันใหม่ทั้งหมด)

### 3. ระบบสไนเปอร์แจ้งเตือนราคา Real-time (`AlpacaSniper`) 🎯
- สตรีมราคาหุ้นแบบ WebSocket ผ่าน Alpaca Data Stream ช่วงเวลาตลาดสหรัฐฯ เปิดทำการ (20:30 - 04:00 น. เวลาไทย)
- แจ้งเตือนทาง Direct Message (DM) เมื่อราคาตลาดลงมาถึงเป้าหมายที่ผู้ใช้ตั้งไว้
- ระบบ Anti-Spam Hysteresis (`last_notified_zone`) ป้องกันการส่งข้อความซ้ำเมื่อราคาแกว่งตัวอยู่ในโซนเดิม

### 4. ที่ปรึกษาจัดพอร์ตการลงทุนส่วนบุคคล (`/advice` & `/survey`)
- `/survey`: แบบประเมินระดับความเสี่ยงและสไตล์การลงทุน เพื่อให้ AI ปรับจูนเป้าหมายราคาให้ตรงกับแต่ละบุคคล
- `/advice`: ออกแบบพอร์ตโฟลิโอตามระยะเวลาลงทุน (Time Horizon), เป้าหมาย (ปันผล/เติบโต), และกลุ่มอุตสาหกรรม (GICS) พร้อมเปรียบเทียบผลตอบแทนกับอัตราเงินเฟ้อ

### 5. ตั้งเวลาแจ้งเตือนประจำวัน (Automated Broadcast)
- แจ้งเตือนสรุปสถานะตลาดหุ้นใน Watchlist ผ่านช่องทาง Channel/Group ทุกเช้า (07:00 น.) และรอบเปิดตลาดหุ้นไทย (09:30 น.) / หุ้นสหรัฐฯ (20:00 น.)

---

## 📌 สรุปคำสั่ง Telegram Bot

| คำสั่ง | คำอธิบาย |
|---|---|
| `/start` | เริ่มต้นใช้งานบอท และลงทะเบียนผู้ใช้ |
| `/survey` | ทำแบบประเมินความเสี่ยงเพื่อบันทึกโปรไฟล์การลงทุน |
| `/advice` | ให้ AI ออกแบบและแนะนำพอร์ตหุ้นเฉพาะบุคคล |
| `/add <symbol> [market]` | เพิ่มหุ้นเข้า Watchlist (เช่น `/add NVDA US` หรือ `/add PTT.BK TH`) |
| `/list` | แสดงรายชื่อหุ้นและเป้าหมายราคาที่บันทึกไว้ใน Watchlist |
| `/scan [symbol]` | สั่งวิเคราะห์หุ้นทันที พร้อมปุ่มเลือกเป้าหมายราคาและปุ่ม Deep Dive |
| `/scan-details <symbol>` | สั่งรัน Multi-Agent Deep Dive Report เจาะลึกหุ้นตัวนั้นทันที |
| `/remove <symbol>` | ลบหุ้นออกจาก Watchlist |
| `/help` | แสดงรายการคำสั่งทั้งหมด |

---

## 🛠️ โครงสร้างโค้ดและสถาปัตยกรรม (Code Architecture)

```
dca-catcher/
├── src/
│   ├── bot.py                # Telegram Bot Handlers, Dispatcher & Lifecycle
│   ├── config.py             # Environment configuration (Tokens, Keys, DB)
│   ├── database.py           # SQLAlchemy Async ORM (User, Watchlist, Signal)
│   ├── fetcher.py            # Market Data Fetcher via yfinance (OHLCV, Fundamentals)
│   ├── transform.py          # Technical Indicators calculation (RSI, MA50, BB, Volume)
│   ├── grader.py             # Single-scan Gemini AI Grader & Advice generator
│   ├── insight_pipeline.py   # Multi-Agent Pipeline (OOP Architecture & Quality Gate)
│   ├── sniper.py             # Alpaca WebSocket real-time price monitoring
│   ├── alert_manager.py      # Notification formatter & Hysteresis logic
│   └── scrapers/
│       └── sentiment.py      # Google News RSS parser & CNN Fear & Greed scraper
├── tests/                    # Unit & Integration test suites
├── Dockerfile                # Container definition
├── docker-compose.yml        # Multi-container service configuration
└── requirements.txt          # Python dependencies
```

---

## ⚙️ การติดตั้งและรันระบบ (Setup & Deployment)

### 1. รันแบบ Local Python
```bash
# สร้างและเปิด Virtual Environment
python3 -m venv venv
source venv/bin/activate

# ติดตั้ง Dependencies
pip install -r requirements.txt

# กำหนดค่าตัวแปรในไฟล์ .env
cat <<EOF > .env
TELEGRAM_TOKEN=your_telegram_bot_token
GEMINI_API_KEYS=key1,key2
DATABASE_URL=sqlite+aiosqlite:///dca_catcher.db
BROADCAST_CHANNEL_ID=-100xxxxxxxxxx
ALPACA_API_KEY=your_alpaca_key
ALPACA_SECRET_KEY=your_alpaca_secret
EOF

# รันระบบ
python -m src.bot
```

### 2. รันด้วย Docker Compose
```bash
docker-compose up -d --build
```

### 3. Deploy บน Cloud (Google Cloud Always Free Tier)
1. สร้าง VM Instance บน Google Cloud Console: รุ่น **`e2-micro`** (Region: `us-central1`, `us-east1`, หรือ `us-west1`)
2. ติดตั้ง Docker และ Docker Compose บน VM:
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose
   ```
3. Clone repository และรันผ่าน `docker-compose up -d` เพื่อให้ระบบทำงาน 24/7

---

## 🗺️ ประวัติการพัฒนา (Phase Roadmap)

- **Phase 1: Foundation & Data Pipeline** — โครงสร้างฐานข้อมูล, ดึงราคา `yfinance`, คำนวณ Technical Indicators, ดึงข่าวและ Fear & Greed
- **Phase 2: AI Brain & Telegram Bot** — ผสาน Gemini ให้คะแนนและตั้งราคาเป้าหมาย, สร้าง Telegram Bot พื้นฐาน, วางระบบ WebSocket
- **Phase 3: Interactive UI & Automation** — ปรับปรุง Interactive Buttons, ระบบ Daily Broadcast ผ่าน APScheduler, รองรับ Docker
- **Phase 4: Production Ready & Advanced UX** — ระบบแจ้งเตือน DM ส่วนบุคคล, ระบบ Anti-Spam Hysteresis, API Key Rotation, ปรับจูนความเสถียร
- **Phase 5: Multi-Agent Insight Pipeline (ปัจจุบัน)** — ออกแบบสถาปัตยกรรม Multi-Agent (Specialists + Composer + Quality Gate), กรองข่าวสารด้วย NER, ดึงงบการเงินและวอลลุ่มแบบเรียลไทม์, ลดการ Hardcode ทั้งระบบด้วย `PipelineConfig`
