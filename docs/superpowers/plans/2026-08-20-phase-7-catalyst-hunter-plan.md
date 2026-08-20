# 🛰️ Phase 7: Real-Time Market Catalyst & Supply Chain Hunter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an asynchronous, zero-token pre-filtered, multi-agent Catalyst & Supply Chain Hunter engine that proactively discovers pre-market corporate events, evaluates dual-perspective fundamental impacts (Bull/Bear), maps economic supply chain spillovers, and delivers interactive Telegram Action Hub alerts.

**Architecture:** Hierarchical Supervisor-Worker pattern (`CatalystHunter` supervisor orchestrating stateless specialist workers) with a 3-tier cascade filtering gate (Python Regex/Microstructure ➔ Gemini Flash-Lite Classifier ➔ Gemini Flash Dual Analyst) integrated with `APScheduler` adaptive time windows.

**Tech Stack:** Python 3.10+, Async SQLAlchemy, Pydantic v2, Google GenAI SDK (`google-genai` / Gemini 2.5 Flash), `aiohttp`, `feedparser`, `python-telegram-bot`, `pytest`, `pytest-asyncio`.

---

## 🕒 Timeline & Planning Checkpoints (ประวัติการจัดทำแผน)

| วันที่ & เวลา (Timestamp) | หัวข้อเช็คพอยต์ (Checkpoint) | สาระสำคัญ (Key Actions) |
|---|---|---|
| **2026-08-20 12:45 BKK** | **Spec Approval & Sign-off** | Design Spec ได้รับการอนุมัติและบันทึกใน `docs/superpowers/specs/` |
| **2026-08-20 13:10 BKK** | **Priority Framework Breakdown** | จัดลำดับ 5 ลำดับความสำคัญ (Domain ➔ Ingestion ➔ AI Evaluator ➔ Batcher/Telegram ➔ Integration) |
| **2026-08-20 13:15 BKK** | **Implementation Plan Finalization** | จัดทำ Implementation Plan แบบ TDD ครอบคลุมทุกไฟล์พร้อมคำสั่งทดสอบ |
| **2026-08-20 13:20 BKK** | **Phase 6 Continuity & Strict Gate** | ระบุความเชื่อมโยงจาก Phase 6 สู่ Phase 7 และกำหนดกระบวนการ Review & Vulnerability Audit |

---

## 🔗 ความต่อเนื่องจาก Phase 6 สู่ Phase 7 (Architectural Continuity)

Phase 7 ไม่ใช่ระบบที่สร้างขึ้นมาลอยๆ แต่เป็นการ **"ต่อยอดและผสานรวมเข้ากับโครงสร้างที่สร้างสำเร็จใน Phase 6"** อย่างแนบแน่น:

1. **ต่อยอดจาก Adaptive AI Memory (`src/memory.py`):**
   * ใน Phase 6 เราสร้างความจำ 2+1 Window (`T-2`, `T-1`) สำหรับการวิเคราะห์หุ้น
   * ใน Phase 7 เมื่อระบบตรวจพบข่าวสำคัญ (เช่น MRNA) เหตุการณ์นี้จะถูกส่งต่อเข้าสู่ Memory เพื่อเป็น `NEW_CATALYST` ทำให้ประวัติการวิเคราะห์ของหุ้นตัวนั้นมีความต่อเนื่องแบบเรียลไทม์
2. **ต่อยอดจาก In-Memory Visual Analytics (`src/charting.py`):**
   * เมื่อแจ้งเตือนข่าวด่วน Tier S ระบบสามารถเรียกใช้ `generate_candlestick_chart()` ส่งแนบควบคู่กับข่าว เพื่อให้ผู้ใช้เห็นทรงกราฟและแนวรับทันทีโดยไม่ต้องไปเปิด TradingView
3. **ต่อยอดจาก Alpaca WebSocket Sniper (`src/sniper.py`):**
   * ปุ่ม Action Hub `[🎯 ตั้งราคาเข้า Sniper]` ในการแจ้งเตือนข่าว จะบันทึกราคาแนวรับ DCA เข้าสู่ Watchlist DB และส่งเข้า Alpaca Sniper เพื่อเฝ้าราคาหน้างานทันที
4. **ต่อยอดจากการ Deploy บน Fly.io 24/7 Worker:**
   * สถาปัตยกรรม 0-Token Ingestion และ Cascade AI ทำให้ระบบ Phase 7 รันบน Fly.io Worker (512MB RAM) ได้ต่อเนื่องโดยไม่เกินโควต้าทรัพยากร

---

## 🏆 ลำดับความสำคัญของงาน (Phase 7 Priority Matrix)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🥇 Priority 1: Domain Contracts & Database Deduplication Layer              │
│    สร้าง Pydantic Models และตาราง `seen_catalysts` เพื่อป้องกันข่าวซ้ำ 100%   │
├─────────────────────────────────────────────────────────────────────────────┤
│ 🥈 Priority 2: Zero-Token Ingestion & Microstructure Filter Gate            │
│    ตัวดึง RSS (Google News / Yahoo) + สกัด Ticker + เช็ค Spread & RVOL (0 Token)│
├─────────────────────────────────────────────────────────────────────────────┤
│ 🥉 Priority 3: Dual-Perspective AI Evaluator & Supply Chain Mapper           │
│    สมองกลวิเคราะห์ 2 ด้าน (Bull/Bear) + สกัดหุ้นลูกในห่วงโซ่อุปทาน (Cohen & Frazzini) │
├─────────────────────────────────────────────────────────────────────────────┤
│ 🏅 Priority 4: Smart Notification Batcher & Telegram Action Hub Dispatcher   │
│    ระบบรวมแจ้งเตือน (Digest) + Adaptive Scheduler (Turbo/Eco) + ปุ่มกดโต้ตอบ │
├─────────────────────────────────────────────────────────────────────────────┤
│ 🎖️ Priority 5: Bot Lifecycle Integration & End-to-End Test Suite             │
│    เชื่อมต่อเข้า Bot Lifecycle และทดสอบครอบคลุม 100% (All tests passing)    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 ไฟล์ที่ต้องสร้างและแก้ไข (File Manifest)

### New Files:
- `src/catalyst/__init__.py` — Package export
- `src/catalyst/models.py` — Domain models (`CatalystArticle`, `CatalystVerdict`, `ConnectedAsset`)
- `src/catalyst/providers/base.py` — Abstract base news provider
- `src/catalyst/providers/google_news.py` — Google News RSS reader with SHA-256 hashing
- `src/catalyst/providers/yahoo_finance.py` — Yahoo Finance ticker feed reader
- `src/catalyst/verifiers/density_filter.py` — Regex ticker extractor & Fact token density scorer
- `src/catalyst/verifiers/market_check.py` — Pre-market dollar volume & spread validator
- `src/catalyst/evaluator.py` — Cascade AI Evaluator (Classifier + Dual Analyst + Supply Chain)
- `src/catalyst/hunter.py` — Main Orchestrator & Adaptive Scheduler (`CatalystHunter`)
- `tests/test_catalyst_models.py` — Unit tests for data contracts & serialization
- `tests/test_catalyst_providers.py` — Unit tests for RSS feeds & deduplication hashing
- `tests/test_catalyst_verifiers.py` — Unit tests for density filter & market microstructure check
- `tests/test_catalyst_evaluator.py` — Unit tests for dual-perspective LLM evaluation & fallbacks
- `tests/test_catalyst_hunter.py` — Integration tests for scheduler, dispatcher & end-to-end flow

### Modified Files:
- `src/database.py` — Add `SeenCatalyst` model and DB helper functions
- `src/bot.py` — Register `CatalystHunter` in bot lifecycle and add Telegram callback button handlers
- `src/config.py` — Add configuration parameters for catalyst hunter intervals

---

## 🛡️ มาตรฐานคุณภาพและกฎเหล็กการพัฒนา (Engineering & Risk Standards)

1. **🧪 100% Test-Driven Development (TDD):**
   * ทุก Task ต้องเริ่มด้วยการเขียน Failing Test ใน `tests/` ก่อนเขียนโค้ดจริงเสมอ
   * ต้องรัน `pytest` และยืนยันว่าผลลัพธ์ผ่าน 100% (Green) ก่อน Commit ทุกครั้ง
2. **🏗️ Clean OOP & SOLID Principles (Maintainability):**
   * **Single Responsibility:** แยกโมดูลชัดเจน (`providers`, `verifiers`, `evaluator`, `hunter`) ห้ามรวมโค้ดในไฟล์เดียว
   * **Open/Closed:** เพิ่ม Provider หรือ Verifier ใหม่ได้ด้วยการสืบทอด Base Class โดยไม่ต้องแก้ไข Core Logic
   * **Dependency Injection:** ส่ง DB Session และ HTTP Client ผ่าน Constructor เพื่อให้ง่ายต่อการ Mock ใน Unit Test
3. **⚠️ การประเมินและป้องกันความเสี่ยง (Risk Assessment & Mitigation):**
   * *ความเสี่ยง API Rate Limits:* ใช้ In-Memory Hash Cache และ Density Filter กรองทิ้ง 95% ก่อนถึง LLM
   * *ความเสี่ยง Network/Feed ล่ม:* มี Exception Catching และ Retry Backoff ไม่ทำให้ Event Loop หลักของบอทหยุดทำงาน
   * *ความเสี่ยง Memory รั่วไหลบน Cloud:* ใช้ Stateless Processing และจำกัดขนาด Queue ไม่ให้เกิน 250MB RAM

---

## 📋 แผนดำเนินงานทีละ Task (Bite-Sized Tasks)

### Task 1: Domain Contracts & Database Deduplication Model (Priority 1) ✅

**Files to modify/create:**
- `src/catalyst/__init__.py`
- `src/catalyst/models.py`
- `src/database.py`
- `tests/test_catalyst_models.py`

- [x] **Step 1:** Write the failing test for `CatalystArticle`, `ConnectedAsset`, and `CatalystVerdict` models in `tests/test_catalyst_models.py`.
- [x] **Step 2:** Run pytest to verify test failure: `venv/bin/pytest tests/test_catalyst_models.py`.
- [x] **Step 3:** Implement `src/catalyst/models.py` and export in `src/catalyst/__init__.py`.
- [x] **Step 4:** Add `SeenCatalyst` model in `src/database.py` with methods `record_seen_catalyst(headline_hash, symbol, title)` and `is_catalyst_seen(headline_hash) -> bool`.
- [x] **Step 5:** Run tests and ensure 100% pass: `venv/bin/pytest tests/test_catalyst_models.py tests/test_database.py`.
- [x] **Step 6:** Commit changes: `git commit -m "feat(catalyst): add domain models and database deduplication layer"`.


---

### Task 2: Zero-Token News Ingestion & Deduplication Providers (Priority 2.1)

**Files to create:**
- `src/catalyst/providers/base.py`
- `src/catalyst/providers/google_news.py`
- `src/catalyst/providers/yahoo_finance.py`
- `tests/test_catalyst_providers.py`

- [ ] **Step 1:** Write failing tests in `tests/test_catalyst_providers.py` for fetching and parsing XML/RSS feeds with mocked network responses.
- [ ] **Step 2:** Run pytest to verify failure: `venv/bin/pytest tests/test_catalyst_providers.py`.
- [ ] **Step 3:** Implement `BaseNewsProvider` in `src/catalyst/providers/base.py` with async `fetch_recent_articles() -> List[CatalystArticle]`.
- [ ] **Step 4:** Implement `GoogleNewsProvider` and `YahooFinanceProvider` with RFC 2822 date parsing and SHA-256 headline hashing.
- [ ] **Step 5:** Run tests and verify: `venv/bin/pytest tests/test_catalyst_providers.py`.
- [ ] **Step 6:** Commit changes: `git commit -m "feat(catalyst): implement asynchronous RSS feed providers with SHA-256 deduplication"`.

---

### Task 3: Fact Density & Pre-Market Microstructure Verifiers (Priority 2.2)

**Files to create:**
- `src/catalyst/verifiers/density_filter.py`
- `src/catalyst/verifiers/market_check.py`
- `tests/test_catalyst_verifiers.py`

- [ ] **Step 1:** Write failing tests in `tests/test_catalyst_verifiers.py` testing:
  - Ticker extraction from headline / summary (e.g. `$MRNA`, `Moderna Inc.`)
  - Informativeness density filtering (rejecting clickbaits with zero hard facts)
  - Pre-market liquidity check (Dollar volume $\ge \$2\text{M}$ and Bid-Ask Spread $< 2.0\%$)
- [ ] **Step 2:** Run pytest to verify failure: `venv/bin/pytest tests/test_catalyst_verifiers.py`.
- [ ] **Step 3:** Implement `DensityFilter` in `src/catalyst/verifiers/density_filter.py`.
- [ ] **Step 4:** Implement `MarketMicrostructureChecker` in `src/catalyst/verifiers/market_check.py` using `yfinance` / `Alpaca` fast quotes.
- [ ] **Step 5:** Run tests and ensure all pass: `venv/bin/pytest tests/test_catalyst_verifiers.py`.
- [ ] **Step 6:** Commit changes: `git commit -m "feat(catalyst): add zero-token fact density filter and microstructure validator"`.

---

### Task 4: Dual-Perspective AI Evaluator & Supply Chain Mapper (Priority 3)

**Files to create:**
- `src/catalyst/evaluator.py`
- `tests/test_catalyst_evaluator.py`

- [ ] **Step 1:** Write failing unit tests in `tests/test_catalyst_evaluator.py` with mocked Gemini responses to verify:
  - Materiality classification (1.0 - 10.0 score)
  - Dual perspective extraction (Bull Catalysts + Bear Risks)
  - Supply Chain & Economic links mapping (`connected_stocks` with Ticker, relationship, and impact)
  - Fallback handling when Gemini fails or returns invalid JSON
- [ ] **Step 2:** Run pytest to verify failure: `venv/bin/pytest tests/test_catalyst_evaluator.py`.
- [ ] **Step 3:** Implement `CatalystEvaluator` in `src/catalyst/evaluator.py` using `google-genai` client and Pydantic structured output.
- [ ] **Step 4:** Run tests and verify 100% passing: `venv/bin/pytest tests/test_catalyst_evaluator.py`.
- [ ] **Step 5:** Commit changes: `git commit -m "feat(catalyst): implement dual-perspective AI evaluator and supply chain mapper"`.

---

### Task 5: Orchestrator, Adaptive Scheduler & Telegram Action Hub (Priority 4 & 5)

**Files to create/modify:**
- `src/catalyst/hunter.py`
- `src/bot.py`
- `tests/test_catalyst_hunter.py`

- [ ] **Step 1:** Write failing integration tests in `tests/test_catalyst_hunter.py` testing full cycle: feed fetch ➔ filter ➔ evaluate ➔ dispatch message to mock Telegram bot.
- [ ] **Step 2:** Run pytest to verify failure: `venv/bin/pytest tests/test_catalyst_hunter.py`.
- [ ] **Step 3:** Implement `CatalystHunter` supervisor in `src/catalyst/hunter.py` with:
  - Adaptive Polling (Turbo 17:00-20:30 BKK, Eco during day)
  - Daily Pre-Market Digest batching (at 19:00 BKK for Tier A news)
  - Instant Urgent Push Alert for Tier S news
  - Telegram Markdown formatter with Action Hub buttons (`[➕ ติดตาม]`, `[🎯 ตั้งเป้า Sniper]`, `[🔍 สแกนหุ้นลูก]`)
- [ ] **Step 4:** Hook `CatalystHunter` into `main()` in `src/bot.py` and add callback query handlers for the new interactive buttons.
- [ ] **Step 5:** Run entire project test suite: `venv/bin/pytest`.
- [ ] **Step 6:** Commit changes: `git commit -m "feat(catalyst): complete Catalyst Hunter orchestrator with Telegram Action Hub and adaptive scheduler"`.

---

## 🧪 Verification & Acceptance Criteria
- [ ] All new tests in `tests/test_catalyst_*.py` pass with 100% green.
- [ ] All existing 48 tests continue to pass without regressions.
- [ ] Zero token wasted on 95% of routine/clickbait news articles.
- [ ] Fly.io deployment remains stable with < 250MB RAM footprint.
