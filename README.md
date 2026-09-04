# DCA Catcher 📈 (Phase 10: Context-Aware News & Modular Architecture)

**DCA Catcher** คือระบบ Telegram Bot สำหรับช่วยวิเคราะห์หุ้นและแจ้งเตือนราคาเป้าหมายสำหรับการลงทุนแบบ DCA (Dollar-Cost Averaging) 

---


## 🚀 What's New in Phase 10 (Context-Aware News & Refactoring)

Phase 10 ยกระดับบอทให้มีความฉลาดด้านข่าวสารมากขึ้น และปรับปรุงโครงสร้างโค้ดระดับลึกเพื่อให้ทำงานได้เสถียรบน Free-Tier Cloud:

1. **Multi-Source News Fetching:** เพิ่มเครื่องมือดูดข่าวจาก `DuckDuckGo News API (DDGS)` เข้ามาทำงานคู่กับ Google News และ Yahoo Finance เพื่ออุดรอยรั่วเวลาถูกจำกัดการเข้าถึง (Error 429)
2. **AI Division of Labor:** แบ่งงานชัดเจน ใช้ระบบ Heuristic (JunkFilter) กรองข่าวขยะออกก่อนส่งให้ **Gemini 1.5 Flash** สรุปอารมณ์ข่าว (Sentiment) จากนั้นค่อยป้อนเข้า **Gemini Pro** เพื่อทำ Deep Dive
3. **Modular Bot Architecture (Tier 4 Completed):** รื้อโครงสร้างไฟล์ `bot.py` ที่ยาวกว่า 1,600 บรรทัด แตกออกเป็น 5 Class Mixins (`common`, `watchlist`, `scanning`, `portfolio`, `survey`) เพื่อให้โค้ดดูแลรักษาง่ายขึ้น
4. **Free-Tier API Protection:** 
   - ปรับการทำงานของ AI Pipeline ให้รันแบบ Sequential แทน Parallel เพื่อป้องกันการชน Rate Limit ของ Google (15 RPM)
   - วางระบบ Async Threading ให้ระบบวาดกราฟ (`asyncio.to_thread`) บอทจึงไม่ค้างระหว่างโหลดข้อมูล
   - เพิ่ม Cooldown 60 วินาที สำหรับคำสั่งที่กินโควต้าหนักๆ

---

## 🕒 ย้อนรอย Phase 7 (Real-Time Catalyst Hunter)

ใน Phase 6 ระบบได้พัฒนา **Adaptive AI Memory** และ **Multi-Agent Pipeline** เพื่อให้บอทมีความจำและวิเคราะห์เชิงลึกได้สมบูรณ์แบบ 
สำหรับ **Phase 7** เราได้ต่อยอดระบบให้กลายเป็น **"ผู้ล่าข่าวด่วน (Catalyst Hunter)"** แบบ Real-time ที่สามารถเฝ้าตลาดได้ 24/7 โดยมีฟีเจอร์เด่นดังนี้:

1. **Stateless Production Architecture:** ย้ายฐานข้อมูลจากเครื่อง Local (SQLite) ขึ้นสู่ **Supabase (PostgreSQL)** เต็มรูปแบบ ป้องกันปัญหา Database is locked และรองรับการดึงข้อมูลคู่ขนาน
2. **Pre-Market Adaptive Hunter:** ดักจับเหตุการณ์สำคัญ (Corporate Catalysts) ในช่วงเวลา Pre-Market (17:00–20:30 น. เวลาไทย) 
3. **Zero-Token Fact Density Gate:** สกัดข่าวขยะและ Deduplicate ข่าวซ้ำก่อนส่งให้ AI เพื่อประหยัด Token สูงสุดกว่า 95%
4. **Supply Chain Spillovers:** วิเคราะห์ผลกระทบทางอ้อมไปยังบริษัทคู่ค้า ซัพพลายเออร์ และกลุ่มอุตสาหกรรมที่เชื่อมโยงกัน 
5. **3-Tier Smart Alert Routing:**
    * 🚨 **Tier S (ข่าวด่วนระดับสูง):** ยิงแจ้งเตือนด่วนทันทีพร้อมปุ่ม Action บน Telegram
    * 📰 **Tier A (ข่าวน่าติดตาม):** รวบยอดส่งเป็น **Pre-Market Daily Digest เวลา 19:00 น.**
    * 🔕 **Tier B:** จัดเก็บเป็นประวัติเงียบๆ สำหรับดึงมาวิเคราะห์เมื่อผู้ใช้กดสั่งสแกน

---


## ⚙️ ภาพรวมการทำงานของระบบ (System Overview - Phase 10)

ระบบออกแบบโครงสร้างใหม่โดยยึดหลัก Clean Architecture และ Free-Tier Optimization:

```mermaid
flowchart TB
    %% Styling (Professional High Contrast)
    classDef actor fill:#f9f9f9,stroke:#333,stroke-width:2px,color:#000
    classDef app fill:#e1f5fe,stroke:#0288d1,stroke-width:2px,color:#000
    classDef handler fill:#b3e5fc,stroke:#01579b,stroke-width:2px,color:#000
    classDef ai fill:#f3e5f5,stroke:#8e24aa,stroke-width:2px,color:#000
    classDef db fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#000
    classDef external fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#000

    User(("👤 Telegram User")):::actor

    subgraph FlyIO [☁️ Application Tier - Hosted on Fly.io]
        Bot["🤖 DCABot Entrypoint"]:::app
        
        subgraph Handlers [Modular Bot Handlers (Mixins)]
            Common["Common"]:::handler
            Watchlist["Watchlist"]:::handler
            Scanning["Scanning"]:::handler
            Portfolio["Portfolio"]:::handler
            Survey["Survey"]:::handler
        end
        Bot --> Handlers

        Pipeline["⚙️ Insight Pipeline<br/>(Throttled Async)"]:::app
        NewsService["📰 News Service<br/>(Multi-Source Fetcher & JunkFilter)"]:::app
        Sniper["🎯 Alpaca Sniper<br/>(DST-Aware)"]:::app
    end

    subgraph Persistence [🗄️ Data Tier - Supabase PostgreSQL]
        DB[("Users, Watchlists,<br/>Signals, Memory,<br/>Seen Catalysts")]:::db
    end

    subgraph AI_Layer [🧠 AI & Intelligence Layer]
        Gemini["Google Gemini API<br/>(Flash 3.6 & Pro)"]:::ai
    end

    subgraph External_Sources [🌐 External Providers]
        Market["yfinance<br/>(Market Data)"]:::external
        News["Google / Yahoo / DuckDuckGo<br/>(News APIs)"]:::external
        Alpaca["Alpaca API<br/>(WSS Trading)"]:::external
    end

    %% Connections
    User <-->|"Commands & Callbacks"| Handlers
    Handlers -->|"Trigger Deep Dive"| Pipeline
    Handlers -->|"Fetch Radar"| NewsService
    Pipeline -->|"Get Cleaned Context"| NewsService
    
    Pipeline <-->|"Async HTTP"| Market
    Pipeline <-->|"Deep Dive Reasoning"| Gemini
    
    NewsService -->|"Fetch Raw Articles"| News
    NewsService <-->|"Deduplication"| DB
    NewsService -->|"Filter & Tag Sentiment"| Gemini
    
    Sniper <-->|"Live Ticks"| Alpaca
    Sniper <-->|"Operating Hours"| DB
    Sniper -->|"Target Hit Alert"| User

    Bot <-->|"SQLAlchemy ORM"| DB
```

---

### 1. การสแกนหุ้นรายตัว (`/scan <SYMBOL>`)
*   **การประประมวลผลข้อมูล:** ดึงราคาและงบการเงินพื้นฐานผ่าน `yfinance` พร้อมคำนวณตัวชี้วัดทางเทคนิค
*   **การประเมินเป้าหมาย:** ประมวลผลร่วมกับ AI เพื่อสรุปคะแนนและเสนอระดับราคาเป้าหมาย DCA 3 ไม้
*   **Visual Analytics:** สร้างภาพกราฟ Candlestick ใน RAM พร้อมระบบ **Adaptive Timeframe** 

### 2. บทวิเคราะห์เจาะลึกแบบ Multi-Stage Pipeline (`/scan-details`)
ระบบส่งต่อข้อมูลผ่าน Pipeline วิเคราะห์เฉพาะด้านเพื่อความถูกต้องของข้อมูล:
1. **Data Collection:** รวบรวมข่าวย้อนหลัง, ข้อมูลงบการเงิน และดัชนี Fear & Greed
2. **Specialist Evaluation:** วิเคราะห์แยกด้าน (Fundamental, Sentiment & News, Risk Strategy)
3. **Synthesis & Quality Gate:** ตรวจสอบความถูกต้องและสรุปเป็นภาษาไทย

### 3. การเฝ้าราคาแบบเรียลไทม์ (`Alpaca WebSocket`)
*   เชื่อมต่อ WebSocket สตรีมราคา IEX ในช่วงเวลาตลาดสหรัฐฯ เปิดทำการ
*   **Anti-Spam Hysteresis:** ตรวจจับเมื่อราคาแตะโซนเป้าหมาย และส่งแจ้งเตือนเพียง 1 ครั้งต่อโซนราคา

### 4. ระบบความจำวิเคราะห์ต่อเนื่อง (`Adaptive AI Memory`)
*   **2+1 Memory Window:** ดึงประวัติย้อนหลัง 2 ก้าว (`T-2`, `T-1`) เพื่อให้ AI เห็นพัฒนาการของหุ้น
*   **Dynamic Reflection & Calibration:** จำแนกสถานะสมมติฐานและให้คะแนนความมั่นใจ (0-100%)


### 5. ระบบแกะสลิปและบันทึกพอร์ต (Slip-to-Portfolio Tracker)
*   **Vision Extraction:** ส่งรูปสลิปซื้อขายให้บอทอ่านข้อมูล (หุ้น, ราคา, ปริมาณ, BUY/SELL) อัตโนมัติด้วย AI
*   **Portfolio PnL:** คำนวณต้นทุนเฉลี่ยและกำไร/ขาดทุน (PnL) แบบ Real-time เปรียบเทียบกับราคาตลาด (`/portfolio`)

---

## 📊 ตัวอย่างภาพกราฟที่ระบบสร้างขึ้น (Visual Analytics Preview)

| ตัวอย่างที่ 1: NVIDIA (NVDA) — Adaptive 6M Timeframe | ตัวอย่างที่ 2: Tesla (TSLA) — Target Levels |
|:---:|:---:|
| ![NVDA Chart](assets/chart_sample_nvda.png) | ![TSLA Chart](assets/chart_sample_tsla.png) |


---

## 🚀 ประวัติการพัฒนา (Development Roadmap & Phases)

การพัฒนาระบบ DCA Catcher ถูกแบ่งออกเป็น Phase ย่อยๆ เพื่อให้ระบบเติบโตอย่างมีแบบแผนและแก้ไขปัญหา (Pain point) ได้ตรงจุด:

| Phase | หัวข้อ | ฟีเจอร์ที่เพิ่มเข้ามา | ประโยชน์และการแก้ปัญหา |
|---|---|---|---|
| **Phase 1-2** | **Core Foundation** | ระบบสแกนหุ้นรายตัว (`/scan`), เชื่อมต่อ yfinance, ให้คะแนนเทคนิคด้วย Gemini | **ระบบพื้นฐาน:** ช่วยให้ผู้ใช้ดึงราคาและวิเคราะห์กราฟ (RSI, MA) เบื้องต้นได้ทันทีโดยไม่ต้องเปิดแอปเทรด |
| **Phase 3** | **Database & Risk** | เปลี่ยนเป็น PostgreSQL, เพิ่มระบบ Multi-user และแบบประเมินความเสี่ยง (`/survey`) | **การรองรับผู้ใช้:** แก้ปัญหาฐานข้อมูลล็อก (DB is locked) และทำให้ AI แนะนำเป้าหมายได้ตรงกับนิสัยความเสี่ยงของแต่ละบุคคล |
| **Phase 4** | **Real-time Sniper** | ระบบ WebSocket เชื่อมต่อตลาดสดผ่าน Alpaca API, แจ้งเตือนเมื่อราคาชนเป้า (Target Alerts) | **ความเร็ว:** แก้ปัญหาผู้ใช้พลาดจุดซื้อสำคัญ โดยบอทจะเฝ้าราคาแบบเรียลไทม์ และกันการแจ้งเตือนสแปมด้วย Hysteresis |
| **Phase 5** | **Insight Pipeline** | บทวิเคราะห์เจาะลึก (`/scan-details`) ทำงานแบบ Multi-Agent (ทีม AI แยกเฉพาะทาง) | **ความลึกของข้อมูล:** แก้ปัญหา AI ตัวเดียวให้ข้อมูลมั่ว โดยแบ่งเป็น Specialist อ่านงบการเงิน, ข่าว, และประเมินความเสี่ยงแยกกัน |
| **Phase 6** | **Visual Analytics** | ระบบสร้างภาพกราฟ (Charting) พร้อมระบบ Adaptive Timeframe | **UX/UI:** ช่วยให้ผู้ใช้เห็นภาพรวมราคา (Drawdown) และเป้าหมายที่ AI เสนอได้ทันทีบนกราฟ เข้าใจง่ายใน 3 วินาที |
| **Phase 7** | **Catalyst & Memory** | ระบบ Background สแกนข่าวแบบอัตโนมัติ และระบบความจำ AI (`Adaptive Memory`) | **ความต่อเนื่อง:** แก้ปัญหา AI ความจำสั้น โดยบอทจะจำสถานะหุ้นย้อนหลัง 2 ก้าว และตื่นมารายงานข่าว (Daily Digest) ให้เอง |
| **Phase 8** | **Slip-to-Portfolio** | แกะข้อมูลสลิปด้วย Vision AI, บันทึกพอร์ต, คำนวณ PnL แบบ Real-time (`/portfolio`) | **ความสะดวก:** แก้ปัญหาขี้เกียจคีย์ข้อมูลพอร์ต เพียงแค่โยนรูปสลิป บอทจะแกะเลขและติดตามกำไร/ขาดทุนให้เป๊ะๆ |

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
| `/list` | แสดงรายชื่อหุ้นและระดับราคาเป้าหมาย |
| `/portfolio` | แสดงสรุปพอร์ต DCA พร้อม P/L แบบเรียลไทม์ |
| `/survey` | แบบประเมินโปรไฟล์ความเสี่ยง |
| `/help` | แสดงรายการคำสั่งทั้งหมด |

---

## 📁 โครงสร้างโปรเจกต์ (Project Structure)

```
dca-catcher/
├── src/
│   ├── bot.py                # Telegram Bot Handlers
│   ├── config.py             # Environment Variables
│   ├── models.py             # Domain Models (TargetZone)
│   ├── memory.py             # Adaptive AI Memory
│   ├── database.py           # Database Manager (PostgreSQL/SQLite)
│   ├── fetcher.py            # Market Data (yfinance)
│   ├── transform.py          # Technical Indicators
│   ├── grader.py             # AI Evaluation & Target Pricing
│   ├── insight_pipeline.py   # Multi-Agent Pipeline
│   ├── charting.py           # Candlestick Generation
│   ├── sniper.py             # Alpaca WebSocket
│   ├── alert_manager.py      # Notification Formatting
│   ├── catalyst/             # 🛰️ Phase 7: Real-Time Market Catalyst
│   │   ├── models.py
│   │   ├── evaluator.py
│   │   ├── hunter.py
│   │   ├── providers/
│   │   └── verifiers/
│   └── scrapers/
│       └── sentiment.py
├── docs/                     # Architecture & Research Docs
├── assets/                   # Images & Assets
├── tests/                    # Pytest Suite (69 passing)
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## ☁️ สถาปัตยกรรมคลาวด์ระดับ Production (Stateless Architecture)

ปัจจุบันระบบถูกยกระดับเป็น **Stateless Architecture** เพื่อความเสถียร 100%:
1. **Compute Layer (Fly.io):** รันโค้ด Python, Telegram Bot, และ Scheduler
2. **Database Layer (Supabase PostgreSQL):** จัดเก็บข้อมูลทั้งหมด (Users, Watchlists, Memory) พร้อมรองรับ Connection Pooling (`asyncpg`) อัจฉริยะ ทำให้ระบบสามารถรันขนานกันได้โดยไม่เจอข้อจำกัด `Database is locked`

*(หมายเหตุ: โค้ดยังคงรองรับ SQLite สำหรับการรันทดสอบบนเครื่อง Local เพียงเปลี่ยน `DATABASE_URL`)*
