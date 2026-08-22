# DCA Catcher 📈

**DCA Catcher** คือระบบ Telegram Bot สำหรับช่วยวิเคราะห์หุ้นและแจ้งเตือนราคาเป้าหมายสำหรับการลงทุนแบบ DCA (Dollar-Cost Averaging) รองรับหุ้นสหรัฐฯ (US) และหุ้นไทย (TH) ทำงานร่วมกับข้อมูลตลาดจริง ข่าวสาร ดัชนีอารมณ์ตลาด และระบบเฝ้าราคาแบบเรียลไทม์

---

## ⚙️ ภาพรวมการทำงานของระบบ (System Overview)

ระบบแบ่งออกเป็น 4 ส่วนหลัก:

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

### 1. การสแกนหุ้นรายตัว (`/scan <SYMBOL>`)
*   **การประประมวลผลข้อมูล:** ดึงราคาและงบการเงินพื้นฐานผ่าน `yfinance` พร้อมคำนวณตัวชี้วัดทางเทคนิค (ATH Drawdown, Volume Anomaly, Moving Averages)
*   **การประเมินเป้าหมาย:** ประมวลผลร่วมกับ AI เพื่อสรุปคะแนนและเสนอระดับราคาเป้าหมาย DCA 3 ไม้ตามระดับความเสี่ยง
*   **Visual Analytics (กราฟแท่งเทียน In-Memory):** สร้างภาพกราฟ Candlestick ด้วย `mplfinance` ใน RAM (`io.BytesIO`) พร้อมระบบ **Adaptive Timeframe** ปรับช่วงเวลาย้อนหลังอัตโนมัติเพื่อให้เส้นเป้าหมายพาดทับแนวรับในอดีตจริง
*   **Interactive Confirmation:** ส่งข้อความบทวิเคราะห์ตามด้วยรูปกราฟ พร้อมปุ่ม Checkbox ให้เลือกบันทึกเป้าหมายเข้าสู่ระบบ Sniper ทันที

---

### 2. บทวิเคราะห์เจาะลึกแบบ Multi-Stage Pipeline (`/scan-details`)
ระบบส่งต่อข้อมูลผ่าน Pipeline วิเคราะห์เฉพาะด้านเพื่อความถูกต้องของข้อมูล:
1. **Data Collection:** รวบรวมข่าวย้อนหลัง, ข้อมูลงบการเงิน และดัชนี Fear & Greed
2. **Specialist Evaluation:** วิเคราะห์แยกด้าน (Fundamental, Sentiment & News, Risk Strategy)
3. **Synthesis & Quality Gate:** ตรวจสอบความถูกต้องของข้อมูลและเรียบเรียงเป็นบทความสรุปภาษาไทย

---

### 3. การเฝ้าราคาแบบเรียลไทม์ (`Alpaca WebSocket`)
*   เชื่อมต่อ WebSocket สตรีมราคา IEX ในช่วงเวลาตลาดสหรัฐฯ เปิดทำการ
*   **Anti-Spam Hysteresis:** ตรวจจับเมื่อราคาแตะโซนเป้าหมาย และส่งแจ้งเตือนเพียง 1 ครั้งต่อโซนราคา เพื่อป้องกันการส่งข้อความซ้ำซ้อน

---

### 4. ระบบความจำวิเคราะห์ต่อเนื่อง (`Adaptive AI Memory`)
*   **2+1 Memory Window:** ดึงประวัติย้อนหลัง 2 ก้าว (`T-2`, `T-1`) เพื่อให้ AI เห็นพัฒนาการของหุ้น (Storyline Continuity)
*   **Dynamic Reflection:** จำแนกสถานะสมมติฐานอัตโนมัติ (`CONTINUING`, `INVALIDATED`, `NEW_CATALYST`, `RESOLVED`)
*   **ML Uncertainty Calibration:** คำนวณคะแนนความมั่นใจ (0–100%) ตามมาตรฐานสากล Machine Learning

---

### 5. ระบบดักจับข่าวและวิเคราะห์ห่วงโซ่อุปทาน (Real-Time Catalyst & Supply Chain Hunter)
*   **Pre-Market Adaptive Hunter:** ดักจับเหตุการณ์สำคัญของบริษัท (Corporate Catalysts) ในช่วงเวลา Pre-Market (17:00–20:30 น. เวลาไทย) ด้วยระบบ Zero-Token Deduplication & Fact Density Filter กรองข่าวซ้ำและข่าวคลิกเบตทิ้งได้กว่า 95% ก่อนส่งประมวลผล
*   **Dual-Perspective Evaluation:** ประเมินปัจจัยบวก (Bull Catalysts) และความเสี่ยงซ่อนเร้น (Bear Risks) ควบคู่กับคำแนะนำแนวรับสะสม DCA อย่างเป็นกลาง ไม่สนับสนุนการไล่ราคาเปิดกระโดด
*   **Supply Chain Spillovers (Economic Links):** วิเคราะห์ผลกระทบทางอ้อมไปยังบริษัทคู่ค้า ซัพพลายเออร์ และกลุ่มอุตสาหกรรมที่เชื่อมโยงกัน (อ้างอิงงานวิจัย Journal of Finance)
*   **3-Tier Smart Routing & Action Hub:**
    * 🚨 **Tier S (ข่าวด่วนระดับสูง):** ยิงแจ้งเตือนด่วนทันทีพร้อมปุ่มโต้ตอบ (`[➕ เพิ่มเข้า Watchlist]`, `[🎯 ตั้งเป้า Sniper]`, `[🔍 สแกนหุ้นลูก]`)
    * 📰 **Tier A (ข่าวน่าติดตาม):** รวบยอดส่งเป็น **Pre-Market Daily Digest เวลา 19:00 น. (เวลาไทย)**
    * 🔕 **Tier B:** จัดเก็บเป็นประวัติในฐานข้อมูลสำหรับการเรียกดูผ่านคำสั่ง `/scan`

---

## 📊 ตัวอย่างภาพกราฟที่ระบบสร้างขึ้น (Visual Analytics Preview)

| ตัวอย่างที่ 1: NVIDIA (NVDA) — Adaptive 6M Timeframe | ตัวอย่างที่ 2: Tesla (TSLA) — Target Levels |
|:---:|:---:|
| ![NVDA Chart](assets/chart_sample_nvda.png) | ![TSLA Chart](assets/chart_sample_tsla.png) |
| *ขยายเป็น 6 เดือนอัตโนมัติเพื่อให้เส้นไม้ 3 (T3) พาดทับแนวรับในอดีตจริง* | *แสดงเส้นราคาปัจจุบันและระดับเป้าหมาย 3 ไม้ พร้อมป้ายราคาชัดเจน* |

---

## 📌 คำสั่งการใช้งานบอท (Bot Commands)

| คำสั่ง | การทำงาน |
|---|---|
| `/start` | เริ่มต้นใช้งานและลงทะเบียนผู้ใช้ |
| `/scan <SYMBOL>` | สแกนหุ้นรายตัว พร้อมกราฟและปุ่มเลือกเป้าหมาย |
| `/scan` | สแกนหุ้นทั้งหมดใน Watchlist |
| `/scan-details <SYMBOL>` | สั่งรันบทวิเคราะห์เชิงลึก (Deep Dive Report) |
| `/add <SYMBOL> [PRICE]` | เพิ่มหุ้นและตั้งราคาเป้าหมายเข้า Watchlist |
| `/remove <SYMBOL>` | ลบหุ้นออกจาก Watchlist |
| `/list` | แสดงรายชื่อหุ้นและระดับราคาเป้าหมายที่บันทึกไว้ |
| `/survey` | แบบประเมินโปรไฟล์ความเสี่ยงของผู้ใช้ |
| `/advice` | ขอคำแนะนำจัดพอร์ตตามเป้าหมายและระยะเวลาลงทุน |
| `/help` | แสดงรายการคำสั่งทั้งหมด |

---

## 📁 โครงสร้างโปรเจกต์ (Project Structure)

```
dca-catcher/
├── src/
│   ├── bot.py                # Telegram Bot Handlers, Keyboards & Dispatcher
│   ├── config.py             # จัดการ Environment Variables และการตั้งค่าระบบ
│   ├── models.py             # Domain Models กลาง (TargetZone Single Source of Truth)
│   ├── memory.py             # Adaptive AI Memory (2+1 Window & Multi-tenant Snapshots)
│   ├── database.py           # จัดการฐานข้อมูล (รองรับ PostgreSQL และ SQLite) ผ่าน Async SQLAlchemy
│   ├── fetcher.py            # ดึงข้อมูลตลาดและงบการเงินผ่าน yfinance
│   ├── transform.py          # คำนวณ Technical Indicators และ Volume Anomaly
│   ├── grader.py             # ประเมินคะแนนความน่าลงทุนและคำนวณเป้าหมายเบื้องต้น
│   ├── insight_pipeline.py   # Multi-Agent Pipeline (Specialists, Composer, Quality Gate)
│   ├── charting.py           # สร้างกราฟ Candlestick และ Target Lines (In-Memory)
│   ├── sniper.py             # Alpaca WebSocket สตรีมราคาเรียลไทม์
│   ├── alert_manager.py      # จัดรูปแบบข้อความแจ้งเตือนและระบบ Anti-Spam
│   ├── catalyst/             # 🛰️ Phase 7: Real-Time Market Catalyst & Supply Chain Hunter
│   │   ├── models.py         # Data Contracts (CatalystArticle, CatalystVerdict, ConnectedAsset)
│   │   ├── evaluator.py      # Dual-Perspective AI Evaluator & Supply Chain Mapper
│   │   ├── hunter.py         # Supervisor Orchestrator & 3-Tier Alert Dispatcher
│   │   ├── providers/        # Async News Providers (Google News, Yahoo Finance RSS)
│   │   └── verifiers/        # Fact Density Regex Gate & Microstructure Validator
│   └── scrapers/
│       └── sentiment.py      # ดึงข่าว Google News RSS และดัชนี Fear & Greed
├── docs/
│   ├── archived_webhook_system.md # เอกสารสถาปัตยกรรม Webhook ที่บันทึกไว้
│   ├── superpowers/specs/    # เอกสารการออกแบบสถาปัตยกรรมระบบ (Design Specs)
│   └── research/             # เอกสารวิจัยและฐานความรู้สากล (Research Foundations)
├── assets/                   # รูปภาพตัวอย่างและ Assets ของโปรเจกต์
├── tests/                    # ชุดทดสอบ Unit & Integration Tests (69 รายการ ผ่าน 100%)
├── requirements.txt          # รายการ Python Dependencies
├── Dockerfile                # ไฟล์สำหรับ Build Docker Container
└── docker-compose.yml        # คอนฟิกสำหรับรันระบบบน Docker
```

---

## 🚀 การติดตั้งและรันระบบ (Setup & Running)

### 1. ติดตั้ง Dependencies
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. ตั้งค่าไฟล์สภาพแวดล้อม (`.env`)
คัดลอกไฟล์เทมเพลตและระบุค่าคอนฟิกที่จำเป็น:
```bash
cp .env.example .env
```
*(ดูคำอธิบายและรายละเอียดของแต่ละ Parameter ได้ภายในไฟล์ [`.env.example`](file:///.env.example))*

### 3. รันการทดสอบ (Run Tests)
```bash
venv/bin/pytest
```

### 4. เริ่มต้นการทำงานของบอท (Run Bot)
```bash
set -a && source .env && set +a && PYTHONPATH=. venv/bin/python -m src.bot
```

หรือรันผ่าน Docker:
```bash
docker-compose up -d --build
```

---

## ☁️ สถาปัตยกรรมคลาวด์ระดับ Production (Stateless Architecture)

ปัจจุบันระบบ DCA Catcher ได้ถูกยกระดับขึ้นเป็น **Stateless Architecture** เพื่อความเสถียรและปลอดภัยของข้อมูล 100% สำหรับการรันแบบ 24/7 เรียบร้อยแล้วครับ:

1. **Compute Layer (Fly.io - Singapore Region):**
   * **บทบาท:** ทำหน้าที่รันโค้ด Python, จัดการ Telegram Bot, คิวตารางเวลา (Scheduler), และเชื่อมต่อ WebSocket แบบ Always-On
   * **จุดเด่น:** Latency ต่ำ ใช้งานง่ายผ่าน `Dockerfile` และตั้งค่าการจัดการคอนเทนเนอร์แบบรันเบื้องหลัง (Background Worker)
2. **Database Layer (Supabase - PostgreSQL):**
   * **บทบาท:** เป็นศูนย์กลางจัดเก็บข้อมูลทั้งหมด (Users, Watchlists, Memory Snapshots, Signals)
   * **จุดเด่น:** แก้ปัญหาข้อมูลหายเมื่อเซิร์ฟเวอร์ (Fly.io) รีสตาร์ท รองรับ Connection Pooling (`asyncpg`) อัจฉริยะ ทำให้ระบบสามารถรันหลายสิบ Thread พร้อมกันได้โดยไม่เจอข้อจำกัด `Database is locked` แบบเดิม

*(หมายเหตุ: โค้ดยังคงรองรับ SQLite สำหรับการรันทดสอบบนเครื่อง Local ผ่าน `aiosqlite` เช่นเดิม เพียงแค่เปลี่ยน `DATABASE_URL` ในไฟล์ `.env`)*
