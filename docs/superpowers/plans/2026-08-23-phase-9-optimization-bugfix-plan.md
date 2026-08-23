# Phase 9: Optimization & Bug Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** แก้ไข Critical Bugs, ปรับปรุง Performance, เพิ่มความเสถียร และยกระดับคุณภาพโค้ดของ DCA Catcher ทั้งระบบ โดยไม่เพิ่มฟีเจอร์ใหม่

**Design Spec:** `docs/superpowers/specs/2026-08-23-phase-9-optimization-bugfix-design.md`

**Tech Stack:** Python 3.10+, SQLAlchemy (asyncpg), Aiogram 3.x, Google GenAI SDK (`google-genai`), yfinance, asyncio.

## Global Constraints
- **ห้ามเปลี่ยนชื่อ Gemini Model** — อ่าน `docs/superpowers/specs/models.md` ก่อนแก้ไขทุกครั้ง
- ข้อความแสดงผลทั้งหมดเป็นภาษาไทย
- ทุก Task ต้อง Run Existing Tests ผ่านก่อน Commit
- ไม่เปลี่ยน Database Schema (ยกเว้นเพิ่ม Index)

---

## Task 1: Critical Bug Fixes (Tier 1.1 — 1.4)

**ลำดับความสำคัญ:** 🔴 สูงมาก — ข้อมูลผิด / ฟีเจอร์พัง
**ไฟล์ที่แก้ไข:** `src/bot.py`, `src/transform.py`, `src/catalyst/evaluator.py`, `src/slip_parser.py`, `src/insight_pipeline.py`
**ไฟล์ทดสอบ:** `tests/test_transform.py`, `tests/test_bot_portfolio.py`, `tests/test_slip_parser.py`

### Sub-task 1.1: แก้ Portfolio SELL Cost Calculation

- [ ] **Step 1:** เปิดไฟล์ `src/bot.py` หาฟังก์ชัน `cmd_portfolio` (~L1557) ที่จัดการ SELL
- [ ] **Step 2:** เพิ่ม Test ใน `tests/test_bot_portfolio.py`:
```python
@pytest.mark.asyncio
async def test_portfolio_sell_adjusts_total_cost():
    """SELL should reduce total_cost proportionally, not just shares."""
    # BUY 10 shares @ $100 = total_cost $1000
    # SELL 5 shares → total_cost should be $500, avg_cost still $100
    # NOT: total_cost $1000 / 5 shares = $200 avg_cost (WRONG)
```
- [ ] **Step 3:** แก้โค้ด SELL logic:
```python
elif t.action == "SELL" and portfolio[t.symbol]["shares"] > 0:
    avg_cost = portfolio[t.symbol]["total_cost"] / portfolio[t.symbol]["shares"]
    portfolio[t.symbol]["total_cost"] -= avg_cost * t.shares
    portfolio[t.symbol]["shares"] -= t.shares
```
- [ ] **Step 4:** Run tests: `pytest tests/test_bot_portfolio.py -v`
- [ ] **Step 5:** Commit: `git commit -m "fix(bot): correct SELL cost calculation in portfolio"`

### Sub-task 1.2: แก้ Indicators ไม่ถูก Map กลับ Snapshot

- [ ] **Step 1:** เปิดไฟล์ `src/transform.py` ตรวจสอบ flow: `calculate_indicators()` → `enrich()`
- [ ] **Step 2:** เพิ่ม Test ใน `tests/test_transform.py`:
```python
def test_enriched_signal_contains_rsi():
    """After enrich(), RSI should be present in snapshot, not None."""
```
- [ ] **Step 3:** เพิ่มขั้นตอน map ค่า indicator กลับเข้า Snapshot ก่อน `enrich()`:
```python
# After calculate_indicators(df)
snapshot.rsi = df["rsi"].iloc[-1] if "rsi" in df.columns else None
snapshot.ma_50 = df["ma_50"].iloc[-1] if "ma_50" in df.columns else None
snapshot.is_volume_anomaly = df["is_volume_anomaly"].iloc[-1] if "is_volume_anomaly" in df.columns else None
```
- [ ] **Step 4:** Run tests: `pytest tests/test_transform.py -v`
- [ ] **Step 5:** Commit: `git commit -m "fix(transform): map indicators back to StockSnapshot"`

### Sub-task 1.3: แก้ User ID จาก Callback

- [ ] **Step 1:** เปิดไฟล์ `src/bot.py` หาฟังก์ชัน `insight_btn`
- [ ] **Step 2:** เปลี่ยน `callback.message.from_user` → `callback.from_user` ทุกจุดที่เกี่ยวข้อง
- [ ] **Step 3:** Run tests: `pytest tests/ -v`
- [ ] **Step 4:** Commit: `git commit -m "fix(bot): use callback.from_user for correct user ID"`

### Sub-task 1.4: Robust JSON Extraction จาก LLM

- [ ] **Step 1:** สร้างฟังก์ชัน Utility ใหม่ `src/utils.py`:
```python
import re, json, logging
logger = logging.getLogger(__name__)

def extract_json_from_llm(raw_text: str) -> dict:
    """Safely extract JSON from LLM response, handling markdown fences."""
    text = raw_text.strip()
    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Remove markdown fences
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```\s*$', '', text)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    # Regex fallback: find first {...} or [{...}]
    match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    raise ValueError(f"No valid JSON found in LLM response: {text[:200]}")
```
- [ ] **Step 2:** เพิ่ม Test ใน `tests/test_utils.py`:
```python
def test_extract_json_plain():
def test_extract_json_with_markdown_fence():
def test_extract_json_with_preamble():
def test_extract_json_with_newline_fence():
```
- [ ] **Step 3:** แทนที่ JSON parsing ใน 3 ไฟล์:
  - `src/catalyst/evaluator.py` — ใช้ `extract_json_from_llm()` แทน `json.loads(raw_json)`
  - `src/slip_parser.py` — ใช้ `extract_json_from_llm()` แทน manual string stripping
  - `src/insight_pipeline.py` — ใช้ `extract_json_from_llm()` แทน manual parsing
- [ ] **Step 4:** เพิ่ม `response_mime_type="application/json"` ใน Gemini API calls ที่รองรับ (ตรวจสอบว่า model ที่ใช้รองรับ)
- [ ] **Step 5:** Run all tests: `pytest tests/ -v`
- [ ] **Step 6:** Commit: `git commit -m "fix(llm): add robust JSON extraction utility for all LLM outputs"`

### Checkpoint 1: Critical Bugs Fixed
```bash
pytest tests/ -v  # ทุก test ต้องผ่าน
git tag phase-9-checkpoint-1
```

---

## Task 2: Async Performance Fixes (Tier 1.5 — 1.7)

**ลำดับความสำคัญ:** 🔴 สูงมาก — ระบบค้าง / DB พัง
**ไฟล์ที่แก้ไข:** `src/fetcher.py`, `src/catalyst/evaluator.py`, `src/sniper.py`

### Sub-task 2.1: Async Wrapper สำหรับ yfinance (Fetcher)

- [ ] **Step 1:** เปิดไฟล์ `src/fetcher.py`
- [ ] **Step 2:** แยก sync logic เป็น private method `_fetch_one_sync(symbol) -> StockSnapshot | None`
- [ ] **Step 3:** สร้าง async method ใหม่:
```python
async def fetch_async(self, symbols: list[str]) -> dict[str, StockSnapshot]:
    tasks = [asyncio.to_thread(self._fetch_one_sync, s) for s in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {s: r for s, r in zip(symbols, results) if isinstance(r, StockSnapshot)}
```
- [ ] **Step 4:** อัปเดต `bot.py` ให้เรียก `fetch_async()` แทน `fetch()`
- [ ] **Step 5:** Run tests: `pytest tests/test_fetcher.py -v`
- [ ] **Step 6:** Commit: `git commit -m "perf(fetcher): wrap yfinance in asyncio.to_thread"`

### Sub-task 2.2: Async Gemini Call สำหรับ Catalyst Evaluator

- [ ] **Step 1:** เปิดไฟล์ `src/catalyst/evaluator.py`
- [ ] **Step 2:** เปลี่ยน `_call_gemini(prompt)` จาก Sync เป็น Async:
  - ใช้ `client.aio.models.generate_content` ถ้า SDK รองรับ
  - หรือครอบด้วย `asyncio.to_thread(self._call_gemini_sync, prompt)`
- [ ] **Step 3:** Run tests: `pytest tests/test_catalyst_evaluator.py -v`
- [ ] **Step 4:** Commit: `git commit -m "perf(catalyst): make evaluator Gemini calls async"`

### Sub-task 2.3: Sniper Memory Cache แทน DB-per-Tick

- [ ] **Step 1:** เปิดไฟล์ `src/sniper.py`
- [ ] **Step 2:** เพิ่ม In-Memory Target Cache:
```python
self._target_cache: dict[str, list] = {}
self._cache_ts: float = 0
CACHE_TTL = 60  # refresh every 60 seconds
```
- [ ] **Step 3:** แก้ `check_target_triggers` ให้เช็คจาก Memory Cache
- [ ] **Step 4:** เพิ่ม `_refresh_cache()` ที่ดึงจาก DB เมื่อ cache expired
- [ ] **Step 5:** เพิ่ม Batch Write สำหรับ triggered targets (ทุก 5 วินาทีแทนทุก tick)
- [ ] **Step 6:** Run tests: `pytest tests/test_sniper.py -v`
- [ ] **Step 7:** Commit: `git commit -m "perf(sniper): use memory cache instead of DB-per-tick"`

### Checkpoint 2: Performance Fixed
```bash
pytest tests/ -v
git tag phase-9-checkpoint-2
```

---

## Task 3: Rate Limiting & Reliability (Tier 2)

**ลำดับความสำคัญ:** 🟠 สูง — Rate Limit, UX, ความเสถียร
**ไฟล์ที่แก้ไข:** `src/bot.py`, `src/charting.py`, `src/scrapers/sentiment.py`, `src/insight_pipeline.py`, `src/sniper.py`, `requirements.txt`

### Sub-task 3.1: Throttle Progress Bar Updates

- [ ] **Step 1:** เพิ่ม Rate Limiting สำหรับ `message.edit_text` ใน `cmd_scan`:
```python
# Only update progress bar every 2 seconds max
import time
_last_progress_update = 0
if time.time() - _last_progress_update >= 2.0:
    await message.edit_text(progress_text)
    _last_progress_update = time.time()
```
- [ ] **Step 2:** Commit: `git commit -m "fix(bot): throttle progress bar to avoid Telegram rate limit"`

### Sub-task 3.2: User-level Command Rate Limit

- [ ] **Step 1:** เพิ่ม Simple Rate Limiter ใน `bot.py`:
```python
_user_cooldowns: dict[int, float] = {}
HEAVY_CMD_COOLDOWN = 30  # seconds

async def _check_cooldown(self, user_id: int, message) -> bool:
    last = self._user_cooldowns.get(user_id, 0)
    if time.time() - last < self.HEAVY_CMD_COOLDOWN:
        remaining = int(self.HEAVY_CMD_COOLDOWN - (time.time() - last))
        await message.reply(f"⏳ กรุณารอ {remaining} วินาทีก่อนใช้คำสั่งนี้อีกครั้ง")
        return False
    self._user_cooldowns[user_id] = time.time()
    return True
```
- [ ] **Step 2:** ใส่ `_check_cooldown()` ใน `/scan-details` และ `/advice`
- [ ] **Step 3:** Commit: `git commit -m "feat(bot): add user-level cooldown for heavy commands"`

### Sub-task 3.3: Async Wrapper สำหรับ Charting & Sentiment

- [ ] **Step 1:** `src/charting.py` — ครอบ `generate_chart()` ด้วย `asyncio.to_thread()`
- [ ] **Step 2:** `src/charting.py` — เปลี่ยนให้ดึงข้อมูล `period="1y"` ครั้งเดียวแล้ว slice
- [ ] **Step 3:** `src/scrapers/sentiment.py` — ครอบ `requests.get` ด้วย `asyncio.to_thread()`
- [ ] **Step 4:** Run tests: `pytest tests/ -v`
- [ ] **Step 5:** Commit: `git commit -m "perf(charting,sentiment): wrap blocking calls in asyncio.to_thread"`

### Sub-task 3.4: Insight Pipeline Parallel Execution

- [ ] **Step 1:** เปิด `src/insight_pipeline.py`
- [ ] **Step 2:** แก้ให้ Agent 1 (Fundamental) และ Agent 2 (News) รันพร้อมกัน:
```python
# Before (Sequential)
result1 = await self._safe_run(agent1_fn)
result2 = await self._safe_run(agent2_fn)

# After (Parallel)
result1, result2 = await asyncio.gather(
    self._safe_run(agent1_fn),
    self._safe_run(agent2_fn)
)
```
- [ ] **Step 3:** Run tests: `pytest tests/ -v`
- [ ] **Step 4:** Commit: `git commit -m "perf(pipeline): run independent agents in parallel"`

### Sub-task 3.5: Fix DST Handling in Sniper

- [ ] **Step 1:** ติดตั้ง `exchange_calendars` หรือใช้ `pytz` คำนวณเวลาตลาด US:
```python
from zoneinfo import ZoneInfo
us_eastern = ZoneInfo("America/New_York")
# ใช้เวลา ET แทน hardcode Thai time
```
- [ ] **Step 2:** Commit: `git commit -m "fix(sniper): use US/Eastern timezone instead of hardcoded Thai hours"`

### Sub-task 3.6: Pin Dependencies

- [ ] **Step 1:** รัน `pip freeze > requirements.lock.txt` ใน Production venv
- [ ] **Step 2:** อัปเดต `requirements.txt` ให้มี version ranges:
```
aiogram>=3.2,<4.0
sqlalchemy>=2.0,<3.0
yfinance>=0.2,<1.0
google-genai>=1.0,<2.0
```
- [ ] **Step 3:** Commit: `git commit -m "chore: pin dependency version ranges in requirements.txt"`

### Checkpoint 3: Reliability Improved
```bash
pytest tests/ -v
git tag phase-9-checkpoint-3
```

---

## Task 4: Code Hardening (Tier 3)

**ลำดับความสำคัญ:** 🟡 ปานกลาง — ป้องกันปัญหาอนาคต
**ไฟล์ที่แก้ไข:** `src/database.py`, `src/memory.py`, `src/config.py`, `src/catalyst/hunter.py`, `src/alert_manager.py`, `src/bot.py`, `src/slip_parser.py`

- [ ] **4.1:** `database.py` — แก้ `get_user` ให้ใช้ Upsert: `INSERT ... ON CONFLICT DO NOTHING`
- [ ] **4.2:** หลายไฟล์ — แทนที่ `except Exception: pass` ด้วย `logger.error(...)` (อย่างน้อย 10 จุด)
- [ ] **4.3:** `memory.py` — เปลี่ยน `func.upper(symbol)` เป็น `== symbol.upper()` ตรงๆ
- [ ] **4.4:** `hunter.py` — ดึง Symbols จาก Master Watchlist ใน DB แทน Hardcode
- [ ] **4.5:** `hunter.py` — ย้าย `digest_queue` ไปเก็บใน DB Table แทน RAM
- [ ] **4.6:** `slip_parser.py` — รับ `PipelineConfig` ผ่าน `__init__` แทนสร้างเอง
- [ ] **4.7:** `database.py` — ปรับ Timestamp ให้ใช้ `func.now()` (DB-side) เป็นมาตรฐานเดียว
- [ ] **4.8:** `config.py` — ลบตัวแปรซ้ำซ้อน + เพิ่ม try-except สำหรับ `int()` conversion
- [ ] **4.9:** `bot.py` — ส่งราคาใน `callback_data` แทนการ parse จาก `btn.text.split("$")`
- [ ] **4.10:** `alert_manager.py` — เช็ค `len(prices) > 0` ก่อนเข้าถึง `[0]`

```bash
pytest tests/ -v
git commit -m "fix: harden code against edge cases and silent failures"
git tag phase-9-checkpoint-4
```

---

## Task 5: Quality & Infra (Tier 4)

**ลำดับความสำคัญ:** 🟢 ต่ำ — ทำเมื่อมีเวลา
**ไฟล์ที่แก้ไข:** `src/bot.py`, `src/grader.py`, `src/database.py`, `Dockerfile`, `tests/`, `pytest.ini`, `fly.toml`

- [ ] **5.1:** `grader.py` — ลบ Dead Code: `_parse_response` method และ duplicate import
- [ ] **5.2:** `database.py` — ลบ deprecated functions `get_engine`, `get_session_maker`
- [ ] **5.3:** `Dockerfile` — เพิ่ม Non-root user + HEALTHCHECK
- [ ] **5.4:** `docker-compose.yml` — เพิ่ม Postgres service สำหรับ local dev
- [ ] **5.5:** `tests/` — เพิ่ม Edge Case Tests:
  - Portfolio SELL → avg_cost ถูกต้อง
  - JSON parse กับ Markdown fences
  - Empty DataFrame ใน Charting
  - yfinance Timeout / NaN handling
- [ ] **5.6:** `pytest.ini` — เพิ่ม `asyncio_mode = auto`
- [ ] **5.7:** `fly.toml` — เพิ่ม RAM เป็น 1GB ถ้าพบ OOM

```bash
pytest tests/ -v
git commit -m "chore: clean dead code, improve Dockerfile, add edge case tests"
git tag phase-9-checkpoint-5
```

---

## Final Verification

```bash
# Run full test suite
pytest tests/ -v --tb=short

# Check for remaining broad exception handlers
grep -rn "except Exception.*pass" src/

# Verify no blocking calls remain in async functions
grep -rn "requests.get\|requests.post" src/ --include="*.py"

# Confirm model names unchanged
grep -rn "gemini-" src/ --include="*.py"
```

## Summary

| Task | Tier | Items | Est. Time | Priority |
|---|---|:---:|:---:|---|
| Task 1 | 🔴 Tier 1 | 4 | ~2 ชม. | แก้ทันที |
| Task 2 | 🔴 Tier 1 | 3 | ~2 ชม. | แก้ทันที |
| Task 3 | 🟠 Tier 2 | 6 | ~3 ชม. | แก้ถัดมา |
| Task 4 | 🟡 Tier 3 | 10 | ~4 ชม. | วางแผนแก้ |
| Task 5 | 🟢 Tier 4 | 7 | ~5 ชม. | ทำเมื่อมีเวลา |
