# 🛰️ Design Spec: Real-Time Market Catalyst & Veracity Hunter Engine (Phase 7)

**Author:** Antigravity Pairing System  
**Date:** 2026-08-20  
**Target Phase:** Phase 7  
**Status:** Validated Design / Ready for Implementation Planning  
**Architecture Style:** Clean OOP, Asynchronous Subagent Pipeline, Multi-Tenant Safe, 100% Free Tier Compatible  

---

## 🕒 Timeline & Development Checkpoints (ประวัติการอัปเดตและเช็คพอยต์)

| วันที่ & เวลา (Timestamp) | หัวข้อเช็คพอยต์ (Checkpoint) | สรุปสิ่งที่ทำและผลลัพธ์ (Summary of Actions) |
|---|---|---|
| **2026-08-20 10:20 BKK** | **Problem Definition & Ideation** | ริเริ่มไอเดียระบบตรวจจับข่าวเชิงรุก (Proactive Catalyst) เพื่อไม่ให้พลาดข่าวระดับ MRNA |
| **2026-08-20 10:45 BKK** | **Academic & Case Study Synthesis** | ศึกษาเปเปอร์ EMNLP 2025, Florida Study, และ MarketSenseAI 2.0 สกัดแก่นการวิเคราะห์ระดับ Headline |
| **2026-08-20 11:10 BKK** | **Historical Case Audit (2024-2026)** | ตรวจสอบข้อมูลจริง 5 เคส (MRNA, VKTX, NVAX, SMMT, CRWD) ยืนยันว่าข่าวออกช่วง Pre-Market ก่อนหุ้นพุ่ง |
| **2026-08-20 12:35 BKK** | **3-Tier Framework & Microstructure** | ออกแบบเกณฑ์คัดกรอง 3 Tiers (Tier S/A/B), RVOL, Bid-Ask Spread, และตัดปัญหา Alert Spam |
| **2026-08-20 12:45 BKK** | **Subagent Architecture & Spec Sign-off** | แบ่งงาน 4 Subagents (Agent 0-3) ประหยัด Token เหลือ <2.5% ของโควต้าฟรี และบันทึก Spec ทางการ |

---

## 📌 1. บทนำและวัตถุประสงค์ (Executive Summary & Goals)

ระบบ **Real-Time Market Catalyst & Veracity Hunter** ถูกออกแบบมาเพื่อยกระดับ DCA Catcher จากการเป็นระบบ **"ตั้งรับ (Reactive)"** (ที่ต้องรอให้ผู้ใช้พิมพ์ `/scan` หรือรอราคาแตะแนวรับ) ให้กลายเป็นระบบ **"ตรวจจับเชิงรุกอัจฉริยะ (Proactive Catalyst Engine)"** 

### เป้าหมายหลัก (Core Objectives):
1. **ดักจับข่าวเปลี่ยนโครงสร้างธุรกิจ (Game-Changer Catalysts):** เช่น ผลการทดลองยาเฟส 3 (กรณี MRNA), การอนุมัติ FDA, ดีลควบรวม M&A, และงบการเงินที่เติบโตก้าวกระโดด ในช่วง **Pre-Market (17:00 – 19:30 น. BKK)** ก่อนที่ตลาดจริงจะเปิด
2. **วิเคราะห์ 2 ด้านอย่างเป็นกลาง (Dual-Perspective Analysis):** นำเสนอทั้ง **โอกาสเติบโต (Bull Catalyst)** และ **ความเสี่ยง/จุดที่ต้องระวัง (Bear Risks)** เพื่อให้นักลงทุน DCA มีข้อมูลรอบด้านและไม่ตกเป็นเหยื่อการไล่ราคา
3. **การแบ่งงานแบบ Multi-Agent Lean Pipeline:** จัดสรรงานให้ Subagent แต่ละตัวรับผิดชอบเฉพาะส่วน เพื่อให้ LLM **ไม่แบกรับภาระเกินตัว** และใช้ทรัพยากรอยู่ใน **Free Tier (< 4% ของโควต้ารายวัน)** ตลอด 24 ชั่วโมง

---

## 👥 2. สถาปัตยกรรมการแบ่งงานของ Subagents (Division of Labor)

เพื่อป้องกันไม่ให้ LLM แบกรับภาระหนัก และประหยัด Token สูงสุด งานจะถูกแบ่งออกเป็น **4 ขั้นตอน (4 Specialized Agents)**:

```
[Google News RSS / Yahoo Finance / SEC 8-K Feeds]
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 🤖 Agent 0: Ingestion & Microstructure Filter (Pure Python) │
│ • Token Usage: 0 Token (รันบน CPU ไม่เรียก LLM)             │
│ • หน้าที่:                                                   │
│   1. คำนวณ SHA-256 Hash ตรวจสอบข่าวซ้ำใน DB                │
│   2. สกัด Ticker และตรวจสอบความสดใหม่ (Recency < 12 ชม.)      │
│   3. กรอง Quality Gate (Market Cap >= $1B, Dollar Volume)   │
│   4. ตรวจสอบ Microstructure: Spread < 2.0%, Active Trades    │
│ ➔ กรองข่าวขยะทิ้ง 95% (เหลือเข้ารอบ ~20–30 ข่าว/วัน)         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 🧠 Agent 1: Catalyst Veracity Classifier (Gemini Flash-Lite)│
│ • Token Usage: ~100 tokens ต่อข่าว (~30 calls/วัน)          │
│ • หน้าที่:                                                   │
│   1. อ่านเฉพาะ Headline + สำนักข่าว + สรุปสั้น 2 บรรทัด     │
│   2. สกัด Materiality Score (1.0 – 10.0)                    │
│   3. จัดหมวดหมู่อีเวนต์ (Archetype Category)                  │
│ ➔ คัดเฉพาะข่าวสำคัญระดับ Tier S / Tier A (Materiality >= 8.0)│
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ ⚖️ Agent 2: Dual-Perspective Market Analyst (Gemini Flash)  │
│ • Token Usage: ~250 tokens ต่อข่าว (~3–5 calls/วัน)         │
│ • หน้าที่:                                                   │
│   1. สกัด Bull Opportunity (โอกาสเติบโตทางธุรกิจ)            │
│   2. สกัด Bear Risks & Caveats (ความเสี่ยงและข้อควรระวัง)   │
│   3. สกัด Dynamic Run-up Assessment & คำแนะนำแนวรับ DCA     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 📲 Agent 3: Action Hub Dispatcher (Python Bot Engine)       │
│ • Token Usage: 0 Token                                      │
│ • หน้าที่:                                                   │
│   1. ประกอบ Event-Temporal Timeline Chain พร้อม Timestamp   │
│   2. ส่งข้อความเข้า Telegram Channel และผู้ใช้ที่เกี่ยวข้อง │
│   3. ผูก Inline Buttons: [➕ เพิ่มเข้า Watchlist] [🎯 ตั้ง Sniper] │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧮 3. การคำนวณภาระงานและค่าใช้จ่าย (Token & Compute Economics)

| ลำดับงาน | เครื่องมือ | จำนวนครั้งที่ทำงาน/วัน | Token ต่อครั้ง | รวม Token / วัน | โควต้าที่ใช้เทียบกับ Gemini Free Tier |
|---|---|:---:|:---:|:---:|:---:|
| **Agent 0 (Ingestion & Filters)** | Python Async | 1,000+ ข่าว | 0 | 0 | 0% |
| **Agent 1 (Classifier)** | Gemini Flash-Lite | ~30 ข่าว | ~100 | ~3,000 | **~2%** (จาก 1,500 RPD) |
| **Agent 2 (Dual Analyst)** | Gemini Flash-Lite | ~3–5 ข่าว | ~250 | ~1,000 | **~0.3%** |
| **Agent 3 (Dispatcher)** | Python Telegram | ~3–5 ครั้ง | 0 | 0 | 0% |
| **📊 รวมทั้งหมด** | — | — | — | **~4,000 Tokens/วัน** | **< 2.5% ของโควต้าฟรี** |

---

## 🛡️ 4. แบบแผนข้อมูล (Pydantic Domain Models)

ไฟล์ `src/catalyst/models.py`:

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class CatalystArticle(BaseModel):
    headline: str
    headline_hash: str
    symbol: str
    publisher: str
    published_at: datetime
    raw_snippet: str
    premarket_price: Optional[float] = None
    premarket_volume_ratio: Optional[float] = None
    bid_ask_spread_pct: Optional[float] = None

class CatalystVerdict(BaseModel):
    is_material: bool = Field(description="ข่าวนี้กระทบต่อมูลค่าพื้นฐานหรือรายได้กิจการจริงหรือไม่")
    materiality_score: float = Field(description="คะแนนความสำคัญ 1.0 ถึง 10.0")
    event_category: str = Field(description="CLINICAL_TRIAL, EARNINGS, M_AND_A, REGULATORY, CONTRACT, RISK_EVENT")
    bull_catalysts: str = Field(description="ปัจจัยบวกและโอกาสเติบโตทางธุรกิจ")
    bear_risks: str = Field(description="ปัจจัยลบ ความเสี่ยงที่ซ่อนอยู่ และความเสี่ยงราคาเปิดกระโดด")
    dca_guidance: str = Field(description="มุมมองกลยุทธ์ DCA แนวรับที่ปลอดภัย ไม่สนับสนุนการไล่ราคา")
    thai_summary: str = Field(description="สรุปเนื้อหาข่าวภาษาไทย 1-2 ประโยค")
```

---

## 🏗️ 5. โครงสร้างซอร์สโค้ดเชิงวัตถุ (Clean OOP Architecture)

```
dca-catcher/
├── src/
│   ├── catalyst/
│   │   ├── __init__.py
│   │   ├── models.py             # Data Contracts (CatalystArticle, CatalystVerdict)
│   │   ├── providers/            # OOP Feed Readers
│   │   │   ├── base.py           # Abstract Base Class (BaseNewsProvider)
│   │   │   ├── google_news.py    # Google News RSS Provider
│   │   │   ├── yahoo_finance.py  # Yahoo Finance RSS Provider
│   │   │   └── sec_edgar.py      # SEC Form 8-K Wire Provider
│   │   ├── verifiers/            # Pre-Processing & Quality Gates
│   │   │   ├── density_filter.py # Data Density & Regex Ticker Extractor
│   │   │   └── market_check.py   # Pre-Market Volume & Spread Validator
│   │   ├── evaluator.py          # LLM Classifier & Dual-Perspective Analyst
│   │   └── hunter.py             # Main CatalystHunter Engine (Async Worker)
│   ├── database.py               # เพิ่มตาราง `seen_catalysts`
│   └── bot.py                    # เชื่อมต่อ CatalystHunter เข้ากับ Lifecycle & Handlers
└── tests/
    └── test_catalyst_hunter.py   # Unit & Integration Tests ครอบคลุมทุก Flow
```

---

## ⏰ 6. ตารางเวลาทำงานอัจฉริยะ (Adaptive Scheduler Profile)

จัดการผ่าน `APScheduler` ใน `src/catalyst/hunter.py`:

*   🔥 **Turbo Polling (17:00 – 20:30 น. BKK):** ตรวจจับฟีดข่าวทุก **2 นาที** (ช่วง Pre-Market ที่ข่าวออกหนาแน่น 80%)
*   ⚡ **Post-Market Polling (03:00 – 04:30 น. BKK):** ตรวจจับทุก **5 นาที** (ช่วงงบการเงินหลังตลาดปิด)
*   💤 **Eco Mode (08:00 – 16:30 น. BKK):** ตรวจจับทุก **30–60 นาที** (ช่วงตลาดสหรัฐฯ ปิดทำการ)

---

## 📲 7. ตัวอย่างข้อความแจ้งเตือนจริงใน Telegram (User Interface)

```text
🚨 BREAKING CATALYST: #MRNA (Moderna Inc.)
⏰ อัปเดตล่าสุด: 20 ส.ค. 2026 เวลา 17:52 น. (เวลาไทย)

⏱️ ไทม์ไลน์เหตุการณ์จริง (Verified Chronological Chain):
├─ [17:45 น.] 📰 Business Wire: แถลงผลการทดลอง INTerpath-001 เฟส 3 มะเร็งผิวหนังผ่านเป้าหมายหลัก
├─ [17:50 น.] 🔥 Alpaca Market: Volume Pre-market พุ่ง +510% เหนือค่าเฉลี่ย, ราคาขยับที่ $65.20 (+12.5%)
└─ [18:15 น.] 🏛️ Reuters: ยืนยันข้อมูลสถิติลดความเสี่ยงกลับมาเป็นซ้ำ 44% (Multi-source Corroborated)

📊 การประเมินพื้นฐาน 2 ด้าน (Dual-Perspective Analysis):
• 🟢 ปัจจัยบวก (Bull Catalyst): ปลดล็อก New S-Curve ของธุรกิจวัคซีนรักษามะเร็ง เป็นแหล่งรายได้ประจำ 3-5 ปีข้างหน้า
• 🔴 ความเสี่ยง (Bear Risks): ต้องรอการยื่นอนุมัติอย่างเป็นทางการจาก FDA และระวังความผันผวนของราคาเปิดกระโดด (Gap Up)

🏷️ ราคาตลาดล่าสุด: $65.20 (Pre-market)
🛒 แผนกลยุทธ์ DCA Catcher:
"แม้จะมี Upside ระยะยาวสูง แต่ตามวินัย DCA ไม่แนะนำให้ไล่ซื้อราคาเปิดกระโดด แนะนำรอราคาพักตัวเข้าสู่แนวรับสะสมไม้ 1 ที่ $61.50"

[➕ เพิ่มเข้า Watchlist] [🎯 ตั้งราคาแนวรับนี้เข้า Sniper] [📖 สแกนเจาะลึกงบเต็ม]
```

---

## 🧪 8. แผนการทดสอบระบบ (Test Strategy)

1.  **Test Feed Parsing & Deduplication:** ทดสอบว่าฟีด XML/RSS ถูกแปลงเป็น `CatalystArticle` ถูกต้อง และแฮชข่าวเดิมซ้ำไม่หลุดรอด
2.  **Test Microstructure & Density Filter:** ทดสอบการตัดข่าวคลิกเบตทิ้ง และทดสอบการคำนวณ Spread / Dollar Volume
3.  **Test LLM Schema Output:** ทดสอบ Mock Response ว่าได้ค่า `CatalystVerdict` ตรงตามฟิลด์ ไม่มี Error
4.  **Test End-to-End Flow:** ทดสอบการรันจำลองตั้งแต่ข่าวเข้า ➔ AI ประเมิน ➔ ส่งข้อความ Telegram สำเร็จ
