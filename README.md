# DCA Catcher 🚀

DCA Catcher คือ Telegram Bot สำหรับนักลงทุน DCA (Dollar-Cost Averaging) ที่ช่วยวิเคราะห์หุ้นและติดตามราคาเป้าหมายอัตโนมัติ รองรับทั้งตลาดหุ้นสหรัฐฯ (US) และหุ้นไทย (TH) ผ่านข้อมูลตลาดจริง (`yfinance`), ข่าวสารสด (`Google News RSS`), อารมณ์ตลาด (`CNN Fear & Greed Index`), และระบบ Real-time Price Tracking (`Alpaca WebSocket`)

**สถานะปัจจุบัน:** **Phase 6 (Visual Analytics & Webhook Integration)**

---

## 🌟 ฟังก์ชันหลักของระบบ (Current Features)

### 1. ระบบวิเคราะห์หุ้นพื้นฐาน & กราฟแท่งเทียน (`/scan`)
- ดึงข้อมูลราคาล่าสุด, จุดสูงสุดตลอดกาล (ATH), % การย่อตัว (ATH Drawdown), ปริมาณการซื้อขาย (Volume)
- ดึงข้อมูลปัจจัยพื้นฐานจริง: P/E (Trailing), PEG Ratio, Revenue Growth, Profit Margin, Debt to Equity
- AI ประเมินความน่าลงทุน (AI Score 1-10) และระดับความมั่นใจ (Confidence Score 0-100%)
- คำนวณราคาเป้าหมายสำหรับเข้าซื้อแบบ DCA จำนวน 3 ระดับ (อิงตามความเสี่ยงของผู้ใช้)
- **Visual Analytics (In-Memory Candlestick Charting):** สร้างและส่งรูปภาพกราฟราคาแท่งเทียนพร้อมเส้นระดับราคาเป้าหมาย (Target Zones) ผ่านระบบ `io.BytesIO` ใน RAM (Zero Disk Footprint)
- **Adaptive Timeframe:** ปรับช่วงเวลาย้อนหลังอัตโนมัติ (3M ➔ 6M ➔ 1Y) เพื่อให้เส้นราคาเป้าหมายพาดทับแนวรับของแท่งเทียนในอดีตอย่างสมบูรณ์แบบ
- มีปุ่ม Interactive ให้ผู้ใช้กดเลือกบันทึกราคาเป้าหมายเข้าสู่ระบบ Sniper ได้ทันที พร้อมปุ่ม `❌ ยังไม่สนใจ / ข้าม` สำหรับเคลียร์ตัวเลือก

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
- สตรีมราคาหุ้นแบบ WebSocket ผ่าน Alpaca Data Stream ช่วงเวลาตลาดสหรัฐฯ เปิดทำการ (ปรับแต่งเวลาได้ใน Config)
- แจ้งเตือนทาง Direct Message (DM) เมื่อราคาตลาดลงมาถึงเป้าหมายที่ผู้ใช้ตั้งไว้
- ระบบ Anti-Spam Hysteresis (`last_notified_zone`) ป้องกันการส่งข้อความซ้ำเมื่อราคาแกว่งตัวอยู่ในโซนเดิม

### 4. ที่ปรึกษาจัดพอร์ตการลงทุนส่วนบุคคล (`/advice` & `/survey`)
- `/survey`: แบบประเมินระดับความเสี่ยงและสไตล์การลงทุน เพื่อให้ AI ปรับจูนเป้าหมายราคาให้ตรงกับแต่ละบุคคล
- `/advice`: ออกแบบพอร์ตโฟลิโอตามระยะเวลาลงทุน (Time Horizon), เป้าหมาย (ปันผล/เติบโต), และกลุ่มอุตสาหกรรม (GICS) พร้อมเปรียบเทียบผลตอบแทนกับอัตราเงินเฟ้อ

### 5. ตั้งเวลาแจ้งเตือนประจำวัน (Automated Broadcast)
- แจ้งเตือนสรุปสถานะตลาดหุ้นใน Watchlist ผ่านช่องทาง Channel/Group ทุกเช้า และรอบเปิดตลาดหุ้นไทย/สหรัฐฯ (ปรับเวลาได้ใน Config)

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
│   ├── config.py             # Central Config (Env variables, Schedules, Ports, Secrets)
│   ├── models.py             # Shared Domain Models (TargetZone Single Source of Truth)
│   ├── database.py           # SQLAlchemy Async ORM (User, Watchlist, Signal)
│   ├── fetcher.py            # Market Data Fetcher via yfinance (OHLCV, Fundamentals)
│   ├── transform.py          # Technical & Volume anomaly calculations
│   ├── grader.py             # Unified Single-scan & Advice generator (via LLMCaller)
│   ├── insight_pipeline.py   # Multi-Agent Pipeline (Specialists, Composer, Quality Gate)
│   ├── charting.py           # In-Memory Visual Analytics (mplfinance + Adaptive Timeframe)
│   ├── webhook.py            # Async Webhook Server (aiohttp for TradingView Alerts)
│   ├── sniper.py             # Alpaca WebSocket real-time price monitoring
│   ├── alert_manager.py      # Notification formatter & Hysteresis logic
│   └── scrapers/
│       └── sentiment.py      # Google News RSS parser & CNN Fear & Greed scraper
├── tests/                    # 47 Unit & Integration test suites (100% Passed)
├── Dockerfile                # Container definition
├── docker-compose.yml        # Multi-container service configuration
└── requirements.txt          # Python dependencies
```

---

## 🗺️ Project Roadmap & Development Timeline

### 📍 Phase 1 - 4: Foundation to Production Ready
*   **Phase 1: Foundation & Data Pipeline** — โครงสร้างฐานข้อมูล, ดึงราคา `yfinance`, คำนวณ Technical Indicators, ดึงข่าวและ Fear & Greed
*   **Phase 2: AI Brain & Telegram Bot** — ผสาน Gemini ให้คะแนนและตั้งราคาเป้าหมาย, สร้าง Telegram Bot พื้นฐาน, วางระบบ WebSocket
*   **Phase 3: Interactive UI & Automation** — ปรับปรุง Interactive Buttons, ระบบ Daily Broadcast ผ่าน APScheduler, รองรับ Docker
*   **Phase 4: Production Ready & Advanced UX** — ระบบแจ้งเตือน DM ส่วนบุคคล, ระบบ Anti-Spam Hysteresis, API Key Rotation, ปรับจูนความเสถียรบน GCP

---

### 🚀 Phase 5 & 5.1: Multi-Agent Pipeline & Clean OOP Refactoring
*   **Multi-Agent Architecture:** พัฒนา `src/insight_pipeline.py` แบ่งหน้าที่ 5 ตัว (DataCollector, FundamentalAgent, NewsAnalystAgent, RiskTargetAgent, ComposerAgent)
*   **Quality Gate QA:** เพิ่มตัวตรวจงานให้คะแนน 0-100% พร้อม Targeted Micro-Revision แก้เฉพาะจุดโดยไม่ต้องสร้างใหม่ทั้งหมด
*   **Clean OOP & Zero-Hardcode:** สร้างโมเดลกลาง `src/models.py` (`TargetZone`), รวมศูนย์คอนฟิกใน `config.py`, ลบค่า Hardcoded และขจัดโค้ดซ้ำซ้อน
*   **Unified AI Engine:** ปรับ `src/grader.py` ให้เรียกใช้ `LLMCaller` จาก `insight_pipeline.py` ยกเลิกการสร้าง Gemini Client ซ้ำซ้อน
*   **Pure Indicators:** คำนวณ Pure Math Indicators (Volume anomaly >1.5x, Trailing P/E)

---

### 🎨 Phase 6: Charting & Webhook Integration (ปัจจุบัน)

*   **In-Memory Visual Analytics (`src/charting.py`):** พัฒนาคลาส `ChartGenerator` ใช้วาดกราฟแท่งเทียน Candlestick พร้อมตีเส้นระดับราคาเป้าหมาย (Target Zones) ผ่าน RAM (`io.BytesIO`) แบบ Zero Disk Storage
*   **Adaptive Timeframe:** ปรับ Timeframe อัตโนมัติ (3M ➔ 6M ➔ 1Y) เพื่อให้เส้นราคาเป้าหมายพาดทับแนวรับของแท่งเทียนในอดีตอย่างสมบูรณ์แบบ
*   **TradingView Webhook Server (`src/webhook.py`):** เปิด Asynchronous Web Server บน `aiohttp` ทำงานคู่ขนานกับ Telegram Bot รองรับสัญญาณ Trigger ภายนอก ตอบรับกลับใน 0.05 วินาที
*   **Clean UX:** สลับลำดับการส่งบทวิเคราะห์ก่อนแล้วส่งกราฟตาม พร้อมปุ่ม `❌ ยังไม่สนใจ / ข้าม` สำหรับเคลียร์ Checkbox
*   **100% Test Coverage:** ผ่านชุดทดสอบทั้งหมด **47/47 tests** ครอบคลุมทุกโมดูลในระบบ 100%
