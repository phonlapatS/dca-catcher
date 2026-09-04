# DCA Catcher — Development Progress

> Last updated: 2026-08-07 10:37 (ICT)
> Branch: `feat/oop-implementation`
> Python: 3.10+ | Venv: `./venv`

## 🎯 Project Overview

**DCA Catcher** is an AI-powered Telegram bot that helps DCA (Dollar-Cost Averaging) investors
decide when to buy stocks. It scans US and Thai (.BK) stock markets, analyzes data across
3 dimensions (Price, Flow, Context), and uses Google Gemini AI to grade buy signals from 1-4.

**Key features:**
- Fetch real-time stock data via yfinance (US + Thai markets)
- Analyze stocks across 3 dimensions: PRICE (drawdown), FLOW (volume), CONTEXT (news/sentiment)
- AI grading via Google Gemini (grade 1-4 with Thai-language advice)
- Telegram bot interface for users to manage watchlists and trigger scans
- Multi-user support with PostgreSQL database
- All free-tier tools (yfinance, Gemini Free, etc.)

**Architecture pattern:** OOP with dataclasses, dependency injection, async SQLAlchemy.
Each module has a single-responsibility class with clean interfaces between them.

---

## 🏁 Checkpoints (Git Rollback Points)

Use these to reset to any stable point if something goes wrong.
Each checkpoint is a **known-good state** where all tests pass.

| # | Checkpoint | Commit | What's working | Tests | Rollback command |
|---|-----------|--------|----------------|-------|-----------------|
| 0 | Project init | `23b3993` | Empty project + design docs only | 0 | `git reset --hard 23b3993` |
| 1 | Database (functional) | `4dedda7` | SQLAlchemy models + loose functions | 4 | `git reset --hard 4dedda7` |
| 2 | Database (OOP) | `c7cb0eb` | `Database` class wrapping engine/session | 4 | `git reset --hard c7cb0eb` |
| 3 | + Fetcher | `a63f916` | + `MarketDataFetcher` with real yfinance | 8 | `git reset --hard a63f916` |
| 4 | + Transformer | `537d9c1` | + `DataTransformer` with 3-dimension scoring | 15 | `git reset --hard 537d9c1` |
| 5 | + Grader | `ed07385` | + `SignalGrader` with Gemini (mocked tests) | 21 | `git reset --hard ed07385` |
| 6 | + Telegram Bot | `38c9162` | Full app wired, 21 tests | `git reset --hard 38c9162` |

### How to use checkpoints

```bash
# See all checkpoints
git log --oneline

# Reset to a checkpoint (DESTRUCTIVE — loses everything after that commit)
git reset --hard <commit-sha>

# Safer: create a backup branch first, then reset
git branch backup-before-reset
git reset --hard <commit-sha>

# Undo a reset (if you didn't delete the backup)
git reset --hard backup-before-reset

# Just peek at a checkpoint without losing anything
git stash              # save current work
git checkout <sha>     # look around
git checkout feat/oop-implementation  # come back
git stash pop          # restore work
```

---

## ✅ Completed Tasks

### Task 1: Project Scaffolding & Database Setup
- **Checkpoint:** `4dedda7`
- **Files:** `src/database.py`, `tests/test_database.py`, `requirements.txt`, `pytest.ini`
- **Description:**
  Set up the foundation — SQLAlchemy async models for the 3 core tables:
  - `User` — stores Telegram users (`telegram_id` as BigInteger for 64-bit IDs, `username`)
  - `Watchlist` — tracks which stocks each user follows (`user_id` FK → `users.id`, `symbol`, `market` US/TH)
  - `Signal` — stores AI-generated analysis results (`symbol`, `grade` 1-4, `confidence` 0-100, `advice`, `created_at` with UTC timezone)
  - Uses `async_sessionmaker` + `create_async_engine` for non-blocking DB access
  - `aiosqlite` for local testing, `asyncpg` for production PostgreSQL
- **Tests:** 4 passing — engine creation, full model CRUD, foreign key validation, requirements check

### Task 1.5: Refactor Database to OOP
- **Checkpoint:** `c7cb0eb`
- **Files:** `src/database.py`, `tests/test_database.py`
- **Description:**
  Wrapped the two loose functions (`get_engine`, `get_session_maker`) into a `Database` class:
  ```python
  db = Database("sqlite+aiosqlite:///:memory:")
  await db.create_tables()        # creates all tables from Base.metadata
  async with db.session() as s:   # returns AsyncSession from session factory
      s.add(User(...))
  await db.close()                # disposes engine cleanly
  ```
  - Models (`User`, `Watchlist`, `Signal`, `Base`) stay at module level — this is idiomatic SQLAlchemy
  - Old functions kept as deprecated aliases for backward compatibility
  - Constructor creates both engine and session factory in one shot
- **Tests:** 4 passing (all updated to use `Database` class API)

### Task 2: Data Fetching Module (yfinance) — OOP
- **Checkpoint:** `a63f916`
- **Files:** `src/fetcher.py`, `tests/test_fetcher.py`, `requirements.txt`
- **Description:**
  Built the market data layer with two components:

  **`StockSnapshot` dataclass** — immutable container for one stock's data:
  ```python
  StockSnapshot(symbol="AAPL", current_price=198.50, volume=52340000,
                ath_price=237.23, drawdown_pct=-16.32)
  ```
  Fields: `symbol`, `current_price`, `volume`, `ath_price`, `drawdown_pct` (always ≤ 0)

  **`MarketDataFetcher` class** — fetches real data from Yahoo Finance:
  ```python
  fetcher = MarketDataFetcher()
  snapshots = fetcher.fetch(["AAPL", "NVDA", "PTT.BK"])
  # Returns: {"AAPL": StockSnapshot(...), "NVDA": StockSnapshot(...), ...}
  ```
  - Uses `yfinance.Ticker.history(period="max")` to calculate true ATH
  - Drawdown = `((current - ATH) / ATH) * 100`, always ≤ 0, rounded to 2 decimals
  - Invalid/missing symbols are **silently skipped** (logged via `logging.warning`)
  - Handles NaN data, empty dataframes, and edge cases gracefully
  - Supports both US tickers (`AAPL`) and Thai `.BK` tickers (`PTT.BK`)
- **Deps added:** `yfinance`, `pandas`
- **Tests:** 4 fetcher tests — valid US symbol, valid TH symbol, invalid symbol skip, multi-symbol batch

### Task 3: Technical Indicators & Data Transformation — OOP
- **Checkpoint:** `537d9c1`
- **Files:** `src/transform.py`, `tests/test_transform.py`, `requirements.txt`
- **Description:**
  Built the analysis layer that transforms raw snapshots into 3-dimension scored signals:

  **`DimensionScore` dataclass** — one dimension's verdict:
  ```python
  DimensionScore(label="BUY", reason="Deep discount from ATH", score=90.0)
  ```
  Fields: `label` ("BUY"/"HOLD"/"SELL"), `reason` (human-readable), `score` (0-100)

  **`EnrichedSignal` dataclass** — bundles snapshot + all 3 dimension scores:
  ```python
  EnrichedSignal(symbol="NVDA", snapshot=StockSnapshot(...),
                 dimensions={"PRICE": DimensionScore(...), "FLOW": ..., "CONTEXT": ...})
  ```

  **`DataTransformer` class** — the scoring engine:
  ```python
  transformer = DataTransformer()
  enriched = transformer.enrich(snapshots)  # dict[str, EnrichedSignal]
  ```
  - **PRICE dimension** (fully implemented) — scores based on ATH drawdown:
    - ≤ -30%: BUY, score 90, "Deep discount from ATH"
    - ≤ -20%: BUY, score 70, "Significant pullback from ATH"
    - ≤ -10%: HOLD, score 50, "Moderate pullback"
    - else: HOLD, score 30, "Near ATH, limited upside"
  - **FLOW dimension** (MVP placeholder) — always returns HOLD, score 50
    - Future: compare current volume vs 20-day moving average
  - **CONTEXT dimension** (MVP placeholder) — always returns HOLD, score 50
    - Future: news sentiment, Fear & Greed Index, historical recovery patterns
  - Each scorer is a private method (`_score_price`, `_score_flow`, `_score_context`) — easy to extend
- **Deps added:** `ta` (for future RSI/technical indicator support)
- **Tests:** 7 transform tests — 4 drawdown threshold tiers, flow placeholder, context placeholder, full enrichment structure

### Task 4: AI Grading (Gemini Integration) — OOP
- **Checkpoint:** `ed07385`
- **Files:** `src/grader.py`, `tests/test_grader.py`, `requirements.txt`
- **Description:**
  Built the AI grading layer that sends enriched signals to Google Gemini for final assessment:

  **`GradeResult` dataclass** — the AI's verdict:
  ```python
  GradeResult(symbol="NVDA", grade=4, confidence=95,
              advice="#ควรซื้อตอนนี้ ราคาลดลงมากจาก ATH",
              reasons=["✅ RSI ต่ำกว่า 30", "✅ ราคาลดลง 35%"])
  ```
  - `grade`: 1=🔴 risky, 2=🟡 moderate, 3=🟢 low risk, 4=🌟 buy now
  - `confidence`: 0-100 (how sure the AI is)
  - `advice`: Thai-language investment advice string
  - `reasons`: list of reason tags with ✅/⚠️ indicators

  **`SignalGrader` class** — dependency-injected Gemini wrapper:
  ```python
  grader = SignalGrader(api_key="your-key", model_name="gemini-2.0-flash")
  result = grader.grade(enriched_signal)  # -> GradeResult
  ```
  - `__init__(api_key, model_name)` — configures Gemini, supports DI for testing
  - `grade(signal)` — builds prompt → calls Gemini → parses JSON response
  - `_build_prompt(signal)` — constructs detailed prompt with market snapshot + all 3 dimensions
  - `_parse_response(text, symbol)` — handles `\`\`\`json` fences, validates fields, returns fallback on failure
  - **Never crashes** — all errors return a safe fallback `GradeResult(grade=2, confidence=0)`
  - Prompt asks Gemini to cross-analyze conflicts between dimensions (e.g., cheap price but low volume)
- **Deps added:** `google-generativeai`
- **Tests:** 6 grader tests — all mock the Gemini API (no real API calls):
  - Happy path with valid JSON response
  - JSON wrapped in markdown fences
  - Invalid/broken JSON (fallback test)
  - Prompt content verification (contains dimension labels)
  - Parse response with missing fields
  - API exception fallback

### Task 5: Telegram Bot Interface — OOP
- **Checkpoint:** `38c9162`
- **Files created:** `src/bot.py` (257 lines), `src/config.py` (19 lines)
- **Files modified:** `requirements.txt` (added `aiogram`)
- **Description:**
  The final module that wires all components into a working Telegram bot:

  **`Config` dataclass** (`src/config.py`) — centralized configuration:
  ```python
  config = Config.from_env()
  # Reads: TELEGRAM_TOKEN, GEMINI_API_KEY, DATABASE_URL
  # Defaults DATABASE_URL to sqlite+aiosqlite:///dca_catcher.db for local dev
  ```

  **`DCABot` class** (`src/bot.py`) — main application orchestrator:
  ```python
  bot = DCABot(config)
  await bot.start()   # creates DB tables + starts Telegram polling
  await bot.stop()    # closes DB + bot session cleanly
  ```
  - Constructor creates all dependencies: `Database`, `MarketDataFetcher`, `DataTransformer`, `SignalGrader`
  - Validates Telegram token on init (falls back to dummy token if invalid)
  - `_register_handlers()` — registers all 4 command handlers on the Dispatcher

  **Commands:**
  - `/start` — bilingual welcome message (Thai + English) listing all available commands
  - `/add <symbol> [market]` — upserts user by `telegram_id`, adds symbol to watchlist, defaults market to "US", checks for duplicates
  - `/list` — queries user's watchlist via JOIN, shows formatted list or "empty" message
  - `/scan [symbol]` — the core pipeline:
    1. If symbol given → scan that one; if not → scan all from user's watchlist
    2. `fetcher.fetch(symbols)` → get real market data
    3. `transformer.enrich(snapshots)` → score across 3 dimensions
    4. `grader.grade(enriched)` → get AI grade from Gemini
    5. Save `Signal` to database for history
    6. Format rich report message with:
       - Grade emoji (🔴🟡🟢🌟) + label in Thai
       - Confidence percentage
       - Market snapshot (price, drawdown, ATH)
       - AI advice in Thai
       - Reason tags list

  **Grade display mapping:**
  - 1 = 🔴 "Risky (มีความเสี่ยงสูง)"
  - 2 = 🟡 "Moderate (ถือ/รอดู)"
  - 3 = 🟢 "Low Risk (เหมาะแก่การ DCA)"
  - 4 = 🌟 "Strong Buy (สัญญาณซื้อแข็งแกร่ง)"

  **Entry point:** `if __name__ == "__main__"` runs `Config.from_env()` → `DCABot(config)` → `bot.start()`
- **Deps added:** `aiogram`
- **Tests:** 21 passing (no new tests for bot — it's an integration boundary; verified via import check + all existing tests pass)

---

## ✅ All Tasks Complete!

## 📁 Architecture Overview

### Data Flow Pipeline
```
User sends /scan NVDA
    ↓
DCABot.cmd_scan()
    ↓
MarketDataFetcher.fetch(["NVDA"])  →  {"NVDA": StockSnapshot(...)}
    ↓
DataTransformer.enrich(snapshots)  →  {"NVDA": EnrichedSignal(dimensions={PRICE, FLOW, CONTEXT})}
    ↓
SignalGrader.grade(enriched)       →  GradeResult(grade=4, confidence=95, advice="...")
    ↓
Format message with 🔴🟡🟢🌟 emoji  →  Send to Telegram
```

### Class Dependency Graph
```
Config (env vars)
  └─→ DCABot
        ├─→ Database (SQLAlchemy async)
        │     ├── User model
        │     ├── Watchlist model
        │     └── Signal model
        ├─→ MarketDataFetcher (yfinance)
        │     └── returns StockSnapshot
        ├─→ DataTransformer
        │     ├── _score_price (drawdown thresholds)
        │     ├── _score_flow (placeholder)
        │     ├── _score_context (placeholder)
        │     └── returns EnrichedSignal (with DimensionScores)
        └─→ SignalGrader (Gemini AI)
              ├── _build_prompt
              ├── _parse_response
              └── returns GradeResult
```

### File Structure
```
src/
├── __init__.py       ← Package marker
├── config.py         ← Config dataclass (TELEGRAM_TOKEN, GEMINI_API_KEY, DATABASE_URL)
├── database.py       ← Database class (engine, sessions) + User/Watchlist/Signal models
├── fetcher.py        ← MarketDataFetcher class + StockSnapshot dataclass
├── transform.py      ← DataTransformer class + DimensionScore/EnrichedSignal dataclasses
├── grader.py         ← SignalGrader class + GradeResult dataclass
└── bot.py            ← DCABot class (wires everything, handles Telegram commands)

tests/
├── test_database.py  ← 4 tests: engine, CRUD, FK, requirements
├── test_fetcher.py   ← 4 tests: valid US/TH symbol, invalid skip, multi-symbol
├── test_transform.py ← 7 tests: 4 price tiers, flow/context placeholder, enrichment
└── test_grader.py    ← 6 tests: happy path, fenced JSON, invalid JSON, prompt, fallback
```

### OOP Patterns Used
- **Dataclasses** for all data containers (`StockSnapshot`, `DimensionScore`, `EnrichedSignal`, `GradeResult`, `Config`)
- **Dependency Injection** — `SignalGrader(api_key)`, `Database(url)`, `DCABot(config)`
- **Single Responsibility** — each class does one thing (fetch, transform, grade, wire)
- **Graceful Degradation** — errors return safe fallbacks, never crash
- **Private Methods** for internal logic (`_score_price`, `_build_prompt`, `_parse_response`)

---

## 🔧 How to Continue Development

1. Check which branch: `git branch --show-current` (should be `feat/oop-implementation`)
2. Check current state: `git log --oneline -10`
3. Run all tests: `source venv/bin/activate && pytest tests/ -v`
4. Read this file to see what's done and what's next
5. Look at task briefs in `.superpowers/sdd/2026-08-06-dca-catcher-plan/` for detailed specs
6. Pick the next ⬜ task and implement it

### Quick Resume Commands
```bash
cd /Users/rocket/Desktop/Python/dca-catcher
git branch --show-current          # should be: feat/oop-implementation
git log --oneline -10              # see recent commits
source venv/bin/activate           # activate venv
pytest tests/ -v                   # verify everything works
cat PROGRESS.md                    # read this file
```

### Environment Variables Needed (for running the bot)
```bash
export TELEGRAM_TOKEN="your-telegram-bot-token"
export GEMINI_API_KEY="your-gemini-api-key"
export DATABASE_URL="postgresql+asyncpg://user:pass@host/dbname"
# or for local testing:
export DATABASE_URL="sqlite+aiosqlite:///dca_catcher.db"
```

---

## 📋 Reference Docs
- **Full Design Spec (Thai):** `docs/superpowers/specs/2026-08-06-dca-catcher-design.md`
- **Original Implementation Plan:** `docs/superpowers/plans/2026-08-06-dca-catcher-plan.md`
- **Detailed Task Briefs (OOP):** `.superpowers/sdd/2026-08-06-dca-catcher-plan/task-*-brief.md`
- **Task Reports:** `.superpowers/sdd/2026-08-06-dca-catcher-plan/task-*-report.md`

## 🚀 Phase 2: Smart Notifications & Deep Analytics (COMPLETE)
- [x] **Design & Planning:** Finalized architecture for Anti-Spam state machine, Buy Targets, and NER news filtering.
- [x] **Design Doc:** `docs/superpowers/specs/2026-08-07-phase-2-design.md`
- [x] **Plan Doc:** `docs/superpowers/plans/2026-08-07-phase-2-plan.md`
- [x] **Task 1: Technical Indicators** (RSI, MA_50, Bollinger Bands, Volume Anomalies)
- [x] **Task 2: Market Sentiment Scrapers** (CNN Fear & Greed, Google News RSS)
- [x] **Task 3: Grader Prompt Upgrade** (Extract NER keywords & generate 3 explicit Buy Targets)
- [x] **Task 4: Anti-Spam Alert State Machine** (Database tracking for `last_notified_zone`)

## 🚀 Phase 3: Deployment & Schedulers (COMPLETE)
- [x] **Task 1: Dynamic Master Watchlist Query** (Optimize API quotas across all users)
- [x] **Task 2: Interactive Keyboards** (Add deep linking to broadcasts)
- [x] **Task 3: APScheduler Integration** (Daily broadcast at 07:00, 09:30, 20:00)
- [x] **Task 4: Docker Deployment** (`Dockerfile` and `docker-compose.yml`)

### Phase 4: Production Ready & Advanced UX (Current)
- [x] **Help Menu & Security (bot.py):** Added `/help` to list commands and removed the `/token` command for a cleaner, safer UX.
- [x] **Interactive Risk Survey (`/survey`):** 
  - **What:** Replaced manual settings with an AI-driven FSM (Finite State Machine) survey to collect the user's investment style and bank-standard drawdown tolerance (1-10%, 11-30%, etc.).
  - **Reason:** Old "wait for -30%" rule was rigid and took too long for some users. The interactive survey provides a modern Telegram UX, mimicking a wealth manager, and allows the bot to tailor recommendations.
- [x] **Personalized Stock Matchmaker (`/advice`):**
  - **What:** An advanced FSM survey where users answer: Time Horizon, Goal, Top 3 Sectors (from 10 GICS main sectors), Sub-sector drilldowns, Stock Count (3, 5, 7, 10), and Monthly DCA Budget. The bot passes this to Gemini to recommend a Custom Portfolio matching their exact profile, including a Growth vs. Inflation projection based on their budget.
  - **Reason:** Solves the "I want to DCA but don't know what to buy" problem. Extremely comprehensive and mimics a real wealth manager.
- [x] **UX Enhancements:**
  - **AI Score:** Changed grading system from 1-4 to 1-10 AI Score (คะแนนความน่าลงทุน) for better UX and readability.
  - **User Tagging:** `/scan` and `/advice` now explicitly tag the user (`@username` or inline mention) so group chats remain organized.
- [ ] **Personalized Daily Broadcast:** Update the Morning/Evening broadcasts to tag users based on their watchlist and provide individualized buy targets according to their risk profiles.
- [ ] **Deployment:** Host on Railway/Render for 24/7 uptime.

## 🚀 Phase 9: Optimization & Bug Fixes (Current)

> **Date:** 2026-08-23 | **Design Spec:** `docs/superpowers/specs/2026-08-23-phase-9-optimization-bugfix-design.md`
> **Plan:** `docs/superpowers/plans/2026-08-23-phase-9-optimization-bugfix-plan.md`

### Tier 1 — ความเสี่ยงสูงมาก (แก้ก่อนเลย) ✅ COMPLETE
- [x] **1.1 Portfolio SELL Cost Calculation:** แก้ให้หักลบ `total_cost` ตามสัดส่วนก่อนลดจำนวนหุ้น
- [x] **1.2 Indicators → AI Pipeline:** Map RSI/MA50/Volume Anomaly กลับเข้า StockSnapshot ใน fetcher.py
- [x] **1.3 User ID Callback:** ใช้ `callback.from_user` แทน `callback.message.from_user` ใน insight_btn
- [x] **1.4 Robust JSON Extraction:** สร้าง `src/utils.py` + ปรับ slip_parser, insight_pipeline, evaluator ใช้ `extract_json_from_llm()`
- [x] **1.5 Async yfinance (Fetcher):** เพิ่ม `fetch_async()` ด้วย `asyncio.to_thread()` + `asyncio.gather()`
- [x] **1.6 Async Gemini (Evaluator):** เปลี่ยน `_call_gemini` เป็น Async ด้วย `client.aio.models.generate_content`
- [x] **1.7 Sniper Memory Cache:** เพิ่ม `_watchlist_cache` + `_refresh_cache_if_needed()` + Batch DB update
- [x] **HOTFIX: Signal.created_at Timezone Crash:** เปลี่ยน `DateTime` → `DateTime(timezone=True)` แก้ asyncpg crash

### Tier 2 — ความเสี่ยงสูง (แก้ถัดมา) ✅ COMPLETE
- [x] **2.1 Insight Pipeline Parallel:** รัน Agent 1 & 2 พร้อมกันด้วย `concurrent.futures.ThreadPoolExecutor`
- [x] **2.2 Async Charting:** ดึงข้อมูล 1y ครั้งเดียวแล้ว slice (ลดจาก 3 network calls เหลือ 1)
- [x] **2.3 Throttle Progress Bar:** เพิ่ม `_throttled_edit()` จำกัด `edit_text` ทุก 2 วินาที
- [x] **2.4 User Rate Limit:** เพิ่ม `_check_cooldown()` Cooldown 30 วินาทีสำหรับ `/scan-details`
- [x] **2.5 N+1 Query Fix:** `cmd_remove` ใช้ `Watchlist.symbol.in_(symbols)` แทนลูป
- [x] **2.6 DST Handling:** ใช้ `America/New_York` timezone + weekend check แทน Hardcode BKK times
- [x] **2.7 Pin Dependencies:** ใส่ Version Ranges (>=min,<max) ใน `requirements.txt`

### Tier 3 — ความเสี่ยงปานกลาง (วางแผนแก้)
- [ ] **3.1:** Race Condition `get_user` → Upsert
- [ ] **3.2:** แทนที่ `except Exception: pass` ด้วย `logger.error()`
- [ ] **3.3:** `memory.py` Full Table Scan → ใช้ `== symbol.upper()` ตรงๆ
- [ ] **3.4-3.10:** Catalyst hardcode, DI, Timestamps, Config, Button parsing, IndexError guard

### Tier 4 — ความเสี่ยงต่ำ (ทำเมื่อมีเวลา)
- [ ] **4.1-4.7:** Dead Code cleanup, Dockerfile, Tests, pytest.ini, fly.toml RAM
