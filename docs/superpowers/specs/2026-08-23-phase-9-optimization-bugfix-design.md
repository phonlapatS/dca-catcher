# Phase 9: Optimization & Bug Fixes — Design Spec

## 1. Executive Summary

Phase 9 เป็น **Hardening Phase** ที่มุ่งเน้นการแก้ไข Critical Bugs, ปรับปรุง Performance, เพิ่มความเสถียร และยกระดับคุณภาพโค้ดของระบบ DCA Catcher ทั้งหมด หลังจากที่ Phase 1-8 เน้นการเพิ่มฟีเจอร์ใหม่ Phase นี้จะเน้นที่การทำให้ฟีเจอร์ที่มีอยู่ **ทำงานถูกต้อง, เร็ว, และเสถียร** สำหรับ Production

**ที่มา:** จากการตรวจสอบโค้ดทั้งโปรเจกต์ (Code Audit) พบปัญหา 32 รายการ แบ่งเป็น 4 ระดับความเสี่ยง

## 2. ปัญหาที่ค้นพบ (Audit Findings)

### 2.1 ระดับความเสี่ยงสูงมาก (Tier 1) — 7 รายการ

#### 2.1.1 Portfolio SELL คำนวณต้นทุนผิด
- **ไฟล์:** `bot.py` — `cmd_portfolio`
- **สาเหตุ:** ตอนขายหุ้น (`SELL`) ลบแค่จำนวนหุ้น (`shares -= t.shares`) แต่ไม่ได้หักลบ `total_cost` ตามสัดส่วน
- **ผลกระทบ:** ต้นทุนเฉลี่ย (avg_cost) พุ่งสูงผิดปกติ → ผู้ใช้เห็นข้อมูล PnL ผิด
- **แนวทางแก้ไข:** คำนวณ avg_cost ก่อนหักลบ → `total_cost -= avg_cost * sold_shares`

#### 2.1.2 Technical Indicators ไม่ถูก Map กลับ Snapshot
- **ไฟล์:** `transform.py` → `grader.py`
- **สาเหตุ:** `calculate_indicators()` คำนวณ RSI, MA50, Volume Anomaly ได้ แต่ไม่ map กลับเข้า `StockSnapshot` ก่อนส่งไป `enrich()`
- **ผลกระทบ:** AI Grader ได้ Prompt ที่ขาดข้อมูล Technical → คะแนนและคำแนะนำผิดทุกครั้ง
- **แนวทางแก้ไข:** เพิ่มขั้นตอน map ค่า indicator กลับเข้า Snapshot หลังเรียก `calculate_indicators()`

#### 2.1.3 User ID หายตอนกดปุ่ม Insight
- **ไฟล์:** `bot.py` — `insight_btn`
- **สาเหตุ:** ใช้ `callback.message.from_user` (ชี้ไปที่บอท) แทน `callback.from_user` (ผู้ใช้จริง)
- **ผลกระทบ:** Memory Snapshot ไม่ถูกบันทึก → ระบบ Adaptive Memory ไม่ทำงาน
- **แนวทางแก้ไข:** เปลี่ยนเป็น `callback.from_user`

#### 2.1.4 JSON Parse จาก LLM ไม่ Robust
- **ไฟล์:** `evaluator.py`, `slip_parser.py`, `insight_pipeline.py`
- **สาเหตุ:** LLM อาจตอบกลับมาครอบด้วย Markdown fences หรือมีข้อความนำ แต่โค้ด parse แบบ string matching ธรรมดา
- **ผลกระทบ:** `json.JSONDecodeError` แบบ Random → Crash/Fallback ผิด
- **แนวทางแก้ไข:**
  1. ใช้ Gemini `response_mime_type="application/json"` บังคับ JSON output
  2. ใช้ Regex fallback: `re.search(r'\{.*\}', raw_text, re.DOTALL)`

#### 2.1.5 Event Loop Blocking จาก yfinance (Fetcher)
- **ไฟล์:** `fetcher.py`
- **สาเหตุ:** `yfinance` เป็น Synchronous Library ทำงานบน Async Event Loop → Block ทั้งระบบ
- **ผลกระทบ:** ทุกคำสั่ง `/scan` ทำให้ผู้ใช้คนอื่นต้องรอ
- **แนวทางแก้ไข:** ครอบด้วย `asyncio.to_thread()` หรือ `loop.run_in_executor()`

#### 2.1.6 Blocking Gemini Call ใน Catalyst Evaluator
- **ไฟล์:** `catalyst/evaluator.py`
- **สาเหตุ:** เรียก Gemini SDK แบบ Sync ภายใน `async def`
- **ผลกระทบ:** ฟรีซระบบทั้งหมดระหว่างรอ AI ตอบ (หลายวินาทีต่อข่าว)
- **แนวทางแก้ไข:** เปลี่ยนเป็น `client.aio.models.generate_content` หรือครอบด้วย `asyncio.to_thread()`

#### 2.1.7 Database Spam จาก Sniper Trade Ticks
- **ไฟล์:** `sniper.py` — `check_target_triggers`
- **สาเหตุ:** Query DB ทุก Trade Tick (หลักพันต่อวินาที)
- **ผลกระทบ:** DB Lock / Connection Pool หมด / Crash
- **แนวทางแก้ไข:** โหลด Watchlist ขึ้น Memory → เช็คจาก Memory → Batch Update กลับ DB

### 2.2 ระดับความเสี่ยงสูง (Tier 2) — 8 รายการ

1. **Insight Pipeline รัน Sequential** — Agent 1 & 2 ไม่พึ่งพากันแต่รันทีละตัว → ช้า 2 เท่า
2. **Blocking Calls ใน Charting & Sentiment** — `yfinance` + `requests.get` แบบ Sync
3. **Telegram Rate Limit (Progress Bar)** — `message.edit_text` ถี่เกินไป → HTTP 429
4. **ไม่มี User-level Rate Limit** — `/scan-details` ใช้ API เยอะ → ผู้ใช้รัวได้
5. **Charting ดึงข้อมูลซ้ำ 3 รอบ** — เรียก `ticker.history()` 3 ครั้งแทนที่จะ slice
6. **N+1 Query ใน cmd_remove** — วนลูป Delete ทีละ symbol
7. **Timezone/DST Hardcode ใน Sniper** — ฟิกซ์เวลา 20:30-04:00 ไม่รองรับ DST
8. **requirements.txt ไม่มี Version Pinning** — Breaking Change = พัง

### 2.3 ระดับความเสี่ยงปานกลาง (Tier 3) — 10 รายการ

1. Race Condition ตอนสร้าง User (IntegrityError)
2. `except Exception: pass` ทั่วโปรเจกต์ (ซ่อน Error)
3. `memory.py` ใช้ `func.upper()` → Full Table Scan
4. Catalyst `digest_queue` อยู่ใน RAM (หายตอน Restart)
5. Catalyst Symbols Hardcoded
6. `slip_parser.py` สร้าง `PipelineConfig()` เอง (ไม่ DI)
7. Timestamp ไม่สอดคล้อง (`func.now()` vs `datetime.now(UTC)`)
8. `config.py` — `int()` ไม่มี Fallback / ตัวแปรซ้ำ
9. Button price parsing ด้วย `split("$")` (Brittle)
10. `alert_manager.py` — `IndexError` ถ้า `to_prices()` คืน List ว่าง

### 2.4 ระดับความเสี่ยงต่ำ (Tier 4) — 7 รายการ

1. แยก `bot.py` (82KB God Object) เป็น Router ย่อยๆ
2. ลบ Dead Code (`_parse_response`, deprecated functions)
3. Dockerfile: Non-root user + HEALTHCHECK
4. docker-compose: เพิ่ม Postgres service
5. เพิ่ม Tests (Edge cases, Error handling, Reconnection)
6. `pytest.ini`: เพิ่ม `asyncio_mode = auto`
7. `fly.toml`: พิจารณาเพิ่ม RAM เป็น 1GB

## 3. Technical Architecture Changes

### 3.1 Async Wrapper Pattern (ใช้ทั่วโปรเจกต์)
```python
# Before (Blocking)
def fetch(symbols):
    for s in symbols:
        data = yf.Ticker(s).history(period="max")  # BLOCKS Event Loop

# After (Non-blocking)
async def fetch(symbols):
    results = await asyncio.gather(*[
        asyncio.to_thread(self._fetch_one, s) for s in symbols
    ])
```

### 3.2 Robust JSON Extraction (ใช้ทุกไฟล์ที่ Parse LLM Output)
```python
import re, json

def extract_json(raw_text: str) -> dict:
    """Extract JSON from LLM response, handling markdown fences."""
    # Try direct parse first
    try:
        return json.loads(raw_text.strip())
    except json.JSONDecodeError:
        pass
    # Regex fallback: find first {...} block
    match = re.search(r'\{.*\}', raw_text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No valid JSON found in: {raw_text[:200]}")
```

### 3.3 Sniper Memory Cache Pattern
```python
class AlpacaSniper:
    def __init__(self):
        self._target_cache: dict[str, list[TargetZone]] = {}
        self._last_cache_refresh: float = 0
        self._CACHE_TTL = 60  # seconds

    async def _refresh_cache_if_needed(self):
        if time.time() - self._last_cache_refresh > self._CACHE_TTL:
            # Load from DB once
            self._target_cache = await self._load_all_targets()
            self._last_cache_refresh = time.time()

    def check_target_triggers(self, symbol: str, price: float):
        # Check from memory — no DB call
        targets = self._target_cache.get(symbol, [])
        ...
```

### 3.4 Portfolio SELL Cost Correction
```python
# Corrected logic
if t.action == "SELL" and portfolio[t.symbol]["shares"] > 0:
    avg_cost = portfolio[t.symbol]["total_cost"] / portfolio[t.symbol]["shares"]
    portfolio[t.symbol]["total_cost"] -= avg_cost * t.shares
    portfolio[t.symbol]["shares"] -= t.shares
```

## 4. Scope & Constraints

- **ไม่เพิ่มฟีเจอร์ใหม่** — Phase นี้เน้นแก้ไขและปรับปรุงของเดิมเท่านั้น
- **ไม่เปลี่ยน Gemini Model Names** — ปฏิบัติตาม `docs/superpowers/specs/models.md` อย่างเคร่งครัด
- **ไม่เปลี่ยน Database Schema** — ไม่มีการเพิ่ม/ลบ Table (ยกเว้นการเพิ่ม Index ถ้าจำเป็น)
- **Backward Compatible** — ผู้ใช้ไม่ต้องเปลี่ยนแปลงอะไร คำสั่งทุกอย่างยังทำงานเหมือนเดิม
- **ภาษาไทย** — ข้อความแสดงผลทั้งหมดยังคงเป็นภาษาไทย

## 5. Implementation Phasing

| Task Group | เนื้อหา | ไฟล์หลัก | เวลาโดยประมาณ |
|---|---|---|---|
| Task 1 | Critical Bug Fixes (Tier 1.1 - 1.4) | `bot.py`, `transform.py`, `evaluator.py`, `slip_parser.py`, `insight_pipeline.py` | ~2 ชม. |
| Task 2 | Async Performance (Tier 1.5 - 1.7) | `fetcher.py`, `evaluator.py`, `sniper.py` | ~2 ชม. |
| Task 3 | Rate Limiting & Reliability (Tier 2) | `bot.py`, `charting.py`, `sentiment.py`, `sniper.py`, `requirements.txt` | ~3 ชม. |
| Task 4 | Code Hardening (Tier 3) | `database.py`, `memory.py`, `config.py`, `hunter.py`, `alert_manager.py` | ~4 ชม. |
| Task 5 | Quality & Infra (Tier 4) | `bot.py`, `Dockerfile`, `tests/`, `pytest.ini` | ~5 ชม. |

## 6. Success Criteria

- [ ] ทุก Critical Bug (Tier 1) ถูกแก้ไขและมี Test ยืนยัน
- [ ] `/scan` ไม่ Block Event Loop (ทดสอบด้วยการสั่ง `/scan` พร้อมกัน 2 ผู้ใช้)
- [ ] `/portfolio` แสดงต้นทุนเฉลี่ยถูกต้องหลังมีทั้ง BUY และ SELL
- [ ] JSON Parse ไม่พังเมื่อ LLM ตอบกลับมาพร้อม Markdown fences
- [ ] All existing tests pass (69 tests)
- [ ] ไม่มี Breaking Changes ต่อผู้ใช้
