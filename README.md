# DCA Catcher 🚀

DCA Catcher คือ Telegram Bot สำหรับนักลงทุน DCA (Dollar-Cost Averaging) ที่ช่วยวิเคราะห์หุ้นและติดตามราคาเป้าหมายอัตโนมัติ รองรับทั้งตลาดหุ้นสหรัฐฯ (US) และหุ้นไทย (TH) ผ่านข้อมูลตลาดจริง (`yfinance`), ข่าวสารสด (`Google News RSS`), อารมณ์ตลาด (`CNN Fear & Greed Index`), และระบบ Real-time Price Tracking (`Alpaca WebSocket`)

**สถานะปัจจุบัน:** **Phase 5.1 (Clean OOP Refactoring, Zero-Hardcode & Architecture Optimization)**

---

## 🌟 ฟังก์ชันหลักของระบบ (Current Features)

### 1. ระบบวิเคราะห์หุ้นพื้นฐาน (`/scan`)
- ดึงข้อมูลราคาล่าสุด, จุดสูงสุดตลอดกาล (ATH), % การย่อตัว (ATH Drawdown), ปริมาณการซื้อขาย (Volume)
- ดึงข้อมูลปัจจัยพื้นฐานจริง: P/E (Trailing), PEG Ratio, Revenue Growth, Profit Margin, Debt to Equity
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
│   ├── config.py             # Central Config (Env variables, Schedules, Operating hours)
│   ├── models.py             # Shared Domain Models (TargetZone Single Source of Truth)
│   ├── database.py           # SQLAlchemy Async ORM (User, Watchlist, Signal)
│   ├── fetcher.py            # Market Data Fetcher via yfinance (OHLCV, Fundamentals)
│   ├── transform.py          # Technical & Volume anomaly calculations
│   ├── grader.py             # Unified Single-scan & Advice generator (via LLMCaller)
│   ├── insight_pipeline.py   # Multi-Agent Pipeline (Specialists, Composer, Quality Gate)
│   ├── sniper.py             # Alpaca WebSocket real-time price monitoring
│   ├── alert_manager.py      # Notification formatter & Hysteresis logic
│   └── scrapers/
│       └── sentiment.py      # Google News RSS parser & CNN Fear & Greed scraper
├── tests/                    # 41 Unit & Integration test suites (100% Passed)
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

### 🚀 Phase 5: Multi-Agent Pipeline (AI Brain Evolution)
*   **Multi-Agent Architecture:** พัฒนา `src/insight_pipeline.py` แบ่งหน้าที่ 5 ตัว (DataCollector, FundamentalAgent, NewsAnalystAgent, RiskTargetAgent, ComposerAgent)
*   **Quality Gate QA:** เพิ่มตัวตรวจงานให้คะแนน 0-100% พร้อม Targeted Micro-Revision แก้เฉพาะจุดโดยไม่ต้องสร้างใหม่ทั้งหมด
*   **Real-time Data Enriched:** ดึงงบการเงินจริง (P/E, PEG, Margin, Debt/Equity) และข่าวย้อนหลัง 7 วันผ่าน NER Validation

---

### ⚡ Phase 5.1: Clean OOP Refactoring, Zero-Hardcode & Optimization (ปัจจุบัน)

มุ่งเน้นการปรับปรุงคุณภาพโค้ดระดับสถาปัตยกรรม (Codebase Health), ลบความซ้ำซ้อน, ขจัดค่า Hardcoded และ Optimize ประสิทธิภาพ:

#### 1. 🧹 Refactoring: Single Source of Truth & Redundancy Removal
*   **สร้างโมเดลกลาง `src/models.py` (`TargetZone`):** รวมศูนย์การ Parse และ Serialize สตริงราคาเป้าหมาย (เช่น `"$185.0 (Conservative)"` ➔ `185.0`) ไว้ที่เดียว ขจัดปัญหา Regex ซ้ำซ้อน 3 ที่ใน `alert_manager.py`, `sniper.py`, และ `bot.py`
*   **Unified AI Engine:** ปรับ `src/grader.py` ให้เรียกใช้ `LLMCaller` จาก `insight_pipeline.py` ยกเลิกการสร้าง Gemini Client และ Fallback list แยกซ้ำซ้อน
*   **Pure Indicators:** ล้าง Mock String และฟังก์ชัน Placeholder ใน `transform.py` ให้คำนวณ Volume anomaly (>1.5x) และ Trailing P/E จริง

#### 2. 🚫 Zero-Hardcode: Centralized Configuration
*   **`PipelineConfig` Dataclass:** รวมศูนย์ Model lists (`lite_models`, `smart_models`), ช่วงเปอร์เซ็นต์ราคาเป้าหมาย (`target_ranges`), และน้ำหนักคะแนน Quality Gate (`quality_weights`, `quality_pass_threshold`)
*   **`Config` Environment Variables:** ย้ายเวลา Broadcast ประจำวัน (`07:00`, `09:30`, `20:00`) และเวลาเปิด/ปิด Alpaca Sniper (`20:30 - 04:00`) เข้าสู่ `.env` สามารถปรับเปลี่ยนได้ 100% โดยไม่ต้องแก้โค้ด

#### 3. ⚡ Optimization & Reliability Benchmarks
*   **TargetZone Benchmark:** ประมวลผลและเรียงลำดับราคาเป้าหมายเสร็จสิ้นใน **~0.10 ms**
*   **Indicators Calculation:** คำนวณ Pure Math Indicators เสร็จสิ้นใน **~0.006 ms**
*   **Token & Quota Optimization:** การแก้ไขรายงานผ่าน Quality Gate ใช้โทเคนเพียงส่วนย่อย ไม่สูญเสียโควต้า 1,500 RPD ของ Gemini Free Tier
*   **100% Test Coverage:** ผ่านชุดทดสอบทั้งหมด **41/41 tests** ครอบคลุม Alert Manager, Database, WebSocket, Fetcher, Grader, และ Indicators
