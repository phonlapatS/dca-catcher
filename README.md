# DCA Catcher 🚀

DCA Catcher คือ Telegram Bot สำหรับนักลงทุน DCA (Dollar-Cost Averaging) ที่ช่วยวิเคราะห์หุ้นและติดตามราคาเป้าหมายอัตโนมัติ รองรับทั้งตลาดหุ้นสหรัฐฯ (US) และหุ้นไทย (TH) ผ่านข้อมูลตลาดจริง (`yfinance`), ข่าวสารสด (`Google News RSS`), อารมณ์ตลาด (`CNN Fear & Greed Index`), และระบบ Real-time Price Tracking (`Alpaca WebSocket`)

**สถานะปัจจุบัน:** **Phase 5 (Multi-Agent Insight Pipeline & Deep Clean OOP Refactoring)**

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

### 🚀 Phase 5: Multi-Agent Pipeline & Clean Architecture (Timeline โดยละเอียด)

การพัฒนาใน Phase 5 แบ่งออกเป็น 4 รอบย่อย (Iterations) ตั้งแต่เริ่มพัฒนาจนถึงปัจจุบัน:

#### 🔹 Iteration 5.1: System Audit & Data Validation
*   **ตรวจสอบระบบดึงข้อมูลตลาดและข่าวสาร:**
    *   ทดสอบและยืนยันการดึงข่าวย้อนหลัง 7 วันจาก Google News RSS ร่วมกับ Named Entity Recognition (NER) กรองข่าวสแปม
    *   ขยาย `fetcher.py` ให้ดึงข้อมูลปัจจัยพื้นฐานจริง: P/E (Trailing), PEG Ratio, Revenue Growth, Profit Margin, Debt to Equity, และ Volume 20-day Average
    *   ดึงค่า CNN Fear & Greed Index เข้ามาเป็นส่วนประกอบของสภาวะตลาดรวม

#### 🔹 Iteration 5.2: Multi-Agent Insight Pipeline Design & Implementation
*   **แยกหน้าที่ Agent ให้ทำงานสอดคล้องกัน (ลดการหลอน/Hallucination):**
    *   สร้าง `src/insight_pipeline.py` ออกแบบสถาปัตยกรรม 5 บทบาท:
        1. **Data Collector (No LLM):** ดึงและเตรียมข้อมูลดิบ ไม่เปลืองโทเคน
        2. **Agent 1 (Fundamental Analyst):** วิเคราะห์ความถูก/แพง และความแข็งแกร่งของงบการเงิน
        3. **Agent 2 (News & Sentiment Analyst):** ให้คะแนนผลกระทบของข่าวแต่ละหัวข้อ
        4. **Agent 3 (Risk & Target Strategist):** อ่านผลวิเคราะห์จาก Agent 1 และ 2 ก่อนนำมากำหนดราคาเป้าหมาย 3 ระดับ
        5. **Composer Agent:** เรียบเรียงเป็นบทความภาษาไทยที่ต่อเนื่อง ไม่เป็นข้อๆ แข็งทื่อ
    *   **Quality Gate Agent (0-100% Scoring):** ตรวจสอบความถูกต้องของตัวเลขและการอ้างอิงข่าว หากคะแนนต่ำกว่า 75 จะส่ง Remark ให้ Composer แก้เฉพาะจุด (จำกัดสูงสุด 2 รอบ)
    *   สร้างคลาส `LLMCaller` จัดการ Key Rotation และ Fallback ข้ามตระกูลโมเดล Flash/Flash-Lite อัตโนมัติ

#### 🔹 Iteration 5.3: Hardcode Elimination & Config Centralization
*   **รวมศูนย์ค่าตัวแปรทั้งหมดเข้าสู่ `PipelineConfig`:**
    *   ปลดล็อก Model lists (`lite_models`, `smart_models`)
    *   ปลดล็อกเปอร์เซ็นต์ราคาเป้าหมาย (`target_ranges`: Conservative 2-5%, Moderate 5-12%, Deep Value 12-25%)
    *   ปลดล็อกเกณฑ์การตรวจ Quality Gate (`quality_weights` และ `quality_pass_threshold`)
    *   แปลงเกณฑ์ AI Confidence Badge เป็น Loop `QUALITY_TIERS`

#### 🔹 Iteration 5.4: System-wide Redundancy Audit & OOP Refactoring
*   **ขจัดความซ้ำซ้อนระดับ Architecture:**
    *   **TargetZone Single Source of Truth:** สร้าง `src/models.py` คลาส `TargetZone` รวมการ parse/serialize ข้อความราคาเป้าหมายจาก DB ไว้จุดเดียว แทนที่การเขียน regex ซ้ำกัน 3 ที่ใน `alert_manager.py`, `sniper.py`, และ `bot.py`
    *   **Unified AI Engine:** ปรับ `grader.py` ให้เรียกใช้ `LLMCaller` และ `PipelineConfig` ร่วมกับ `insight_pipeline.py` หมดปัญหา Dual-Engine ซ้ำซ้อน
    *   **Cleaner Indicators:** ลบโค้ด placeholder ใน `transform.py` ให้คำนวณ Volume anomaly และ P/E evaluation บริสุทธิ์
    *   **Configurable Operating Windows:** ย้ายเวลา Broadcast (`07:00, 09:30, 20:00`) และเวลาเปิด Sniper (`20:30-04:00`) เข้า `src/config.py` ปรับค่าผ่าน Environment Variables ได้ 100%
    *   **Test Suite 100% Pass:** ปรับปรุงชุดทดสอบทั้ง 41 tests ให้รองรับ Architecture ใหม่ทั้งหมด
