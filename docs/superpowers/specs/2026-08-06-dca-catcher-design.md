# DCA Catcher — Technical Specification

> Version: 1.0.0-mvp | Date: 2026-08-07 | Branch: `feat/oop-implementation`

---

## 1. Project Overview

ระบบ AI Agent ผู้ช่วยสแกนตลาด สรุปข่าวสาร และวิเคราะห์สัญญาณเข้าซื้อหุ้นเป้าหมายสำหรับสาย DCA
โดยดึงข้อมูลราคา ปริมาณการซื้อขาย และข่าวสาร มาสังเคราะห์และประเมินความเสี่ยง
แจ้งเตือนผ่าน Telegram Bot ในจังหวะเวลาที่เหมาะสม (Smart Notification)
โครงการนี้เน้นใช้เครื่องมือฟรี (Free Tier) ทั้งหมด

**In English:** An AI-powered Telegram bot that helps DCA investors decide when to buy stocks.
It scans US and Thai markets, analyzes data across 3 dimensions (Price, Flow, Context),
and uses Google Gemini AI to grade buy signals from 1 to 4 with Thai-language advice.

---

## 2. Runtime & Language

| Item | Value |
|------|-------|
| Language | Python 3.10.14 (compatible with 3.10+) |
| Package Manager | pip (with venv) |
| Virtual Environment | `./venv` (created via `python3 -m venv venv`) |
| OS Developed On | macOS |
| Async Runtime | asyncio (built-in) |
| Target Deployment | Single Docker Container |

---

## 3. Dependencies (Pinned Versions)

### Core Dependencies (`requirements.txt`)

| Package | Version | Purpose |
|---------|---------|---------|
| `sqlalchemy[asyncio]` | 2.0.51 | Async ORM — models, engine, sessions |
| `asyncpg` | 0.31.0 | PostgreSQL async driver (production) |
| `aiosqlite` | 0.22.1 | SQLite async driver (local dev/testing) |
| `yfinance` | 1.5.2 | Yahoo Finance market data (OHLCV, ATH) |
| `pandas` | 2.3.3 | DataFrame processing for yfinance data |
| `ta` | 0.11.0 | Technical analysis indicators (RSI, etc.) — *installed, not yet used in MVP* |
| `google-generativeai` | 0.8.6 | Google Gemini AI API client |
| `aiogram` | 3.30.0 | Telegram Bot framework (async, v3) |
| `pytest` | 9.1.1 | Test framework |
| `pytest-asyncio` | 1.4.0 | Async test support |

### Key Transitive Dependencies

| Package | Version | Pulled By |
|---------|---------|-----------|
| `pydantic` | 2.13.4 | aiogram |
| `aiohttp` | 3.14.3 | aiogram |
| `google-api-core` | 2.33.0 | google-generativeai |
| `protobuf` | 5.29.6 | google-generativeai |
| `grpcio` | 1.83.0 | google-generativeai |
| `numpy` | 2.2.6 | pandas, ta |
| `beautifulsoup4` | 4.15.0 | yfinance |
| `requests` | 2.34.2 | yfinance |
| `greenlet` | 3.5.4 | sqlalchemy |

---

## 4. System Architecture

### 4.1 Current MVP Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                        DCABot (src/bot.py)                       │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────┐ │
│  │ Database  │  │MarketData    │  │DataTransformer│  │Signal   │ │
│  │          │  │Fetcher       │  │              │  │Grader   │ │
│  │ (SQLAlchemy│  │ (yfinance)   │  │ (3 dimensions)│  │(Gemini) │ │
│  └─────┬────┘  └──────┬───────┘  └──────┬───────┘  └────┬────┘ │
│        │              │                 │                │      │
│        ▼              ▼                 ▼                ▼      │
│   PostgreSQL    Yahoo Finance     Python Logic      Gemini API  │
└─────────────────────────────────────────────────────────────────┘
         ▲                                                  │
         │              Telegram API (aiogram)              │
         └──────────────────────────────────────────────────┘
                              ▲
                              │
                         User (Telegram)
```

### 4.2 Data Flow Pipeline
```
User sends /scan NVDA
    │
    ▼
DCABot.cmd_scan()
    │
    ▼
MarketDataFetcher.fetch(["NVDA"])
    │ Returns: {"NVDA": StockSnapshot(price, volume, ath, drawdown)}
    ▼
DataTransformer.enrich(snapshots)
    │ Returns: {"NVDA": EnrichedSignal(dimensions={PRICE, FLOW, CONTEXT})}
    ▼
SignalGrader.grade(enriched_signal)
    │ Returns: GradeResult(grade=1-4, confidence=0-100, advice="...", reasons=[...])
    ▼
Save Signal to database + Format Telegram message
    │
    ▼
Reply to user with 🔴🟡🟢🌟 graded report
```

### 4.3 Future Architecture (Original Vision)
- **Core Workflow**: LangGraph Agent (Fetch → Transform → Analyze → Grade → Notify)
- **Triggers**:
  1. **Scheduler**: Daily Summary (07:00) & Pre-market (09:30 TH / 20:00 US)
  2. **Real-time Monitor**: Polling every 15 mins during market hours (alerts on >= 5% drop)
  3. **Manual**: User `/scan` command via Telegram ✅ **Implemented**

---

## 5. Data Sources

### 5.1 Implemented (MVP)

| Source | Library | Data | Status |
|--------|---------|------|--------|
| Yahoo Finance | `yfinance 1.5.2` | OHLCV, ATH price, volume, drawdown % | ✅ Working |
| Google Gemini | `google-generativeai 0.8.6` | AI grading, Thai advice, reason tags | ✅ Working (model: `gemini-2.0-flash`) |

### 5.2 Planned (Future)

| Source | Method | Data | Status |
|--------|--------|------|--------|
| Google News RSS | Web scraping | News headlines + sentiment | ⬜ Not started |
| CNN Fear & Greed Index | Web scraping | Market sentiment score | ⬜ Not started |
| `ta` library | Python computation | RSI, MACD, Bollinger Bands | ⬜ Installed, not wired |

---

## 6. Analysis Logic — The 3 Dimensions

เพื่อป้องกันปัญหา Overfitting และ Outliers ข้อมูลจะถูกประมวลผลผ่าน `DataTransformer` (ตรวจสอบความถูกต้อง/กรองข้อมูลขยะ)
แล้วจัดกลุ่มตัวชี้วัดเป็น 3 มิติ ก่อนส่งให้ AI ประเมิน:

### Dimension 1: PRICE (ราคา) — ✅ Fully Implemented

**Question:** ราคาน่าสนใจหรือไม่?

| Drawdown from ATH | Label | Score | Reason |
|-------------------|-------|-------|--------|
| ≤ -30% | BUY | 90 | "Deep discount from ATH" |
| ≤ -20% | BUY | 70 | "Significant pullback from ATH" |
| ≤ -10% | HOLD | 50 | "Moderate pullback" |
| > -10% | HOLD | 30 | "Near ATH, limited upside" |

**Implementation:** `DataTransformer._score_price(snapshot)` in `src/transform.py`

### Dimension 2: FLOW (แรงซื้อขาย) — ⬜ Placeholder

**Question:** มีแรงซื้อกลับหรือไม่?

**Current:** Always returns HOLD, score 50 — "Volume analysis requires historical data"

**Future plan:**
- Compare current volume vs 20-day moving average
- Volume Anomaly detection (spike = buying pressure returning)
- Use `ta` library for volume-based indicators

**Implementation:** `DataTransformer._score_flow(snapshot)` in `src/transform.py`

### Dimension 3: CONTEXT (บริบท) — ⬜ Placeholder

**Question:** สถานการณ์โดยรวมเอื้อต่อการฟื้นตัวหรือไม่?

**Current:** Always returns HOLD, score 50 — "Context analysis will be added in future iteration"

**Future plan:**
- News Sentiment via Google News RSS scraping
- CNN Fear & Greed Index scraping
- Historical Recovery pattern analysis

**Implementation:** `DataTransformer._score_context(snapshot)` in `src/transform.py`

---

## 7. AI Grading & Signal Format

`SignalGrader` (Gemini) จะวิเคราะห์ข้อมูลทั้ง 3 มิติและสังเคราะห์ออกมาในรูปแบบ JSON:

### Grade Scale

| Grade | Emoji | Thai Label | English Label |
|-------|-------|------------|---------------|
| 1 | 🔴 | มีความเสี่ยงสูง | Risky / High Risk |
| 2 | 🟡 | ถือ/รอดู | Moderate / Hold |
| 3 | 🟢 | เหมาะแก่การ DCA | Low Risk / Good DCA |
| 4 | 🌟 | สัญญาณซื้อแข็งแกร่ง | Strong Buy / Now |

### Gemini Response Schema
```json
{
    "grade": 4,
    "confidence": 95,
    "advice": "#ควรซื้อตอนนี้ ราคาลดลงมากจาก ATH แต่ปริมาณการซื้อขายยังปกติ",
    "reasons": ["✅ RSI ต่ำกว่า 30", "✅ ราคาลดลง 35% จาก ATH", "⚠️ ปริมาณซื้อขายปกติ"]
}
```

### Reason Tags
- `✅` = เหตุผลเชิงบวก (positive signal)
- `⚠️` = เหตุผลเชิงลบ/ข้อระวัง (warning/negative signal)

### Cross-Analysis
Gemini is prompted to detect and explain conflicts between dimensions:
- Example: "ราคาลดลง RSI Oversold แต่ปริมาณการซื้อขายต่ำมาก แนะนำให้รอดูสถานการณ์"

### Error Handling
- On Gemini API failure → fallback: `grade=2, confidence=0, advice="Gemini API error: ..."`
- On JSON parse failure → fallback: `grade=2, confidence=0, advice="Failed to parse response: ..."`
- **Never crashes** — always returns a valid GradeResult

---

## 8. Database Schema

### 8.1 Current MVP Schema (SQLAlchemy ORM)

**Engine:** PostgreSQL via `asyncpg` (production) / SQLite via `aiosqlite` (dev/test)

#### Table: `users`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PRIMARY KEY, auto-increment | Internal user ID |
| `telegram_id` | BigInteger | UNIQUE, NOT NULL | Telegram's 64-bit user ID |
| `username` | String | NULLABLE | Telegram username |

#### Table: `watchlists`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PRIMARY KEY, auto-increment | Internal watchlist entry ID |
| `user_id` | Integer | FOREIGN KEY → `users.id`, NOT NULL | Which user owns this entry |
| `symbol` | String | NOT NULL | Stock ticker (e.g., "NVDA", "PTT.BK") |
| `market` | String | NOT NULL | Market identifier: "US" or "TH" |

#### Table: `signals`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PRIMARY KEY, auto-increment | Internal signal ID |
| `symbol` | String | NOT NULL | Stock ticker that was analyzed |
| `grade` | Integer | NOT NULL | AI grade: 1 (risky) to 4 (strong buy) |
| `confidence` | Integer | NOT NULL | AI confidence: 0-100 |
| `advice` | String | NULLABLE | Thai-language AI advice text |
| `created_at` | DateTime | DEFAULT `now(UTC)` | When the signal was generated |

### 8.2 Entity Relationship
```
┌──────────┐       ┌──────────────┐       ┌──────────┐
│  users   │       │  watchlists  │       │ signals  │
├──────────┤       ├──────────────┤       ├──────────┤
│ id (PK)  │──1:N──│ id (PK)      │       │ id (PK)  │
│ telegram │       │ user_id (FK) │       │ symbol   │
│ username │       │ symbol       │       │ grade    │
└──────────┘       │ market       │       │ confid.  │
                   └──────────────┘       │ advice   │
                                          │ created  │
                                          └──────────┘
```

### 8.3 Future Tables (Original Vision, Not Yet Implemented)

#### Table: `market_data` (planned)
| Column | Type | Description |
|--------|------|-------------|
| `symbol` | String | Stock ticker |
| `date` | Date | Trading date |
| `open`, `high`, `low`, `close` | Float | OHLC prices |
| `volume` | BigInteger | Trading volume |
| `rsi` | Float | RSI indicator value |
| `ath_price` | Float | All-time high price |
| `drawdown_pct` | Float | % drawdown from ATH |
| `fetched_at` | DateTime | When data was fetched |

#### Table: `news_cache` (planned)
| Column | Type | Description |
|--------|------|-------------|
| `symbol` | String | Related stock ticker |
| `headline` | String | News headline |
| `source_url` | String | Original article URL |
| `summary` | String | AI-generated summary |
| `sentiment` | String | Positive/Negative/Neutral |
| `published_at` | DateTime | When article was published |
| `scraped_at` | DateTime | When we scraped it |

---

## 9. OOP Architecture & Module Map

### 9.1 Module Responsibilities

| Module | Class(es) | Responsibility |
|--------|-----------|----------------|
| `src/config.py` | `Config` | Load env vars (`TELEGRAM_TOKEN`, `GEMINI_API_KEY`, `DATABASE_URL`) |
| `src/database.py` | `Database`, `User`, `Watchlist`, `Signal` | Async DB engine, session management, ORM models |
| `src/fetcher.py` | `MarketDataFetcher`, `StockSnapshot` | Fetch stock data from Yahoo Finance |
| `src/transform.py` | `DataTransformer`, `DimensionScore`, `EnrichedSignal` | Score stocks across 3 dimensions |
| `src/grader.py` | `SignalGrader`, `GradeResult` | AI grading via Gemini |
| `src/bot.py` | `DCABot` | Wire everything + Telegram commands |

### 9.2 Dataclass Definitions

```python
# src/config.py
@dataclass
class Config:
    telegram_token: str
    gemini_api_key: str
    database_url: str                    # default: "sqlite+aiosqlite:///dca_catcher.db"

# src/fetcher.py
@dataclass
class StockSnapshot:
    symbol: str                          # e.g., "NVDA"
    current_price: float                 # e.g., 198.50
    volume: int                          # e.g., 52340000
    ath_price: float                     # e.g., 237.23
    drawdown_pct: float                  # e.g., -16.32 (always ≤ 0)

# src/transform.py
@dataclass
class DimensionScore:
    label: str                           # "BUY", "HOLD", or "SELL"
    reason: str                          # Human-readable explanation
    score: float                         # 0-100 numeric score

@dataclass
class EnrichedSignal:
    symbol: str
    snapshot: StockSnapshot
    dimensions: dict[str, DimensionScore]  # keys: "PRICE", "FLOW", "CONTEXT"

# src/grader.py
@dataclass
class GradeResult:
    symbol: str
    grade: int                           # 1-4
    confidence: int                      # 0-100
    advice: str                          # Thai-language advice
    reasons: list[str]                   # Reason tags with ✅/⚠️
```

### 9.3 Class Method Signatures

```python
# Database (src/database.py)
class Database:
    def __init__(self, url: str): ...
    async def create_tables(self): ...
    def session(self) -> AsyncSession: ...
    async def close(self): ...

# MarketDataFetcher (src/fetcher.py)
class MarketDataFetcher:
    def fetch(self, symbols: list[str]) -> dict[str, StockSnapshot]: ...

# DataTransformer (src/transform.py)
class DataTransformer:
    def enrich(self, snapshots: dict[str, StockSnapshot]) -> dict[str, EnrichedSignal]: ...
    def _score_price(self, snapshot: StockSnapshot) -> DimensionScore: ...
    def _score_flow(self, snapshot: StockSnapshot) -> DimensionScore: ...
    def _score_context(self, snapshot: StockSnapshot) -> DimensionScore: ...

# SignalGrader (src/grader.py)
class SignalGrader:
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"): ...
    def grade(self, signal: EnrichedSignal) -> GradeResult: ...
    def _build_prompt(self, signal: EnrichedSignal) -> str: ...
    def _parse_response(self, text: str, symbol: str) -> GradeResult: ...

# DCABot (src/bot.py)
class DCABot:
    def __init__(self, config: Config): ...
    async def cmd_start(self, message: types.Message): ...
    async def cmd_add(self, message: types.Message): ...
    async def cmd_list(self, message: types.Message): ...
    async def cmd_scan(self, message: types.Message): ...
    async def start(self): ...
    async def stop(self): ...
```

---

## 10. Telegram Commands

### 10.1 Implemented (MVP)

| Command | Usage | Description |
|---------|-------|-------------|
| `/start` | `/start` | ยินดีต้อนรับ + แนะนำระบบ (bilingual Thai/English) |
| `/add` | `/add NVDA US` or `/add PTT.BK TH` | เพิ่มหุ้นเข้า watchlist (default market: US) |
| `/list` | `/list` | ดูรายชื่อหุ้นที่ติดตาม |
| `/scan` | `/scan NVDA` or `/scan` (all watchlist) | วิเคราะห์ทันที ด้วย AI pipeline |

### 10.2 Planned (Future)

| Command | Description | Status |
|---------|-------------|--------|
| `/remove <symbol>` | ลบหุ้นออกจาก watchlist | ⬜ Not implemented |
| `/settings` | ตั้งค่าการแจ้งเตือน (เปิด/ปิด) | ⬜ Not implemented |
| Interactive Inline Keyboards | ปุ่มกดในแชทสำหรับ Action ด่วน | ⬜ Not implemented |

---

## 11. Smart Notification Strategy (Original Vision — Not Yet Implemented)

ลดการแจ้งเตือนที่น่ารำคาญ ส่งเมื่อผู้ใช้สามารถตัดสินใจได้จริง:

| Time (ICT) | Type | Description |
|------------|------|-------------|
| 07:00 | Daily Summary | ภาพรวมตลาดสั้นๆ, สรุป Fear/Greed, จัดอันดับหุ้นน่าสนใจ |
| 09:30 | SET Pre-market | Deep signal สำหรับหุ้นไทย |
| 20:00 | US Pre-market | Deep signal สำหรับหุ้นอเมริกา (อิงเวลาเปิดตลาด US) |
| Intraday | Emergency Alert | แจ้งเตือนฉุกเฉินเฉพาะเมื่อราคาร่วง >= 5% ในระหว่างวัน |

---

## 12. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_TOKEN` | Yes (for production) | `""` | Telegram Bot API token from @BotFather |
| `GEMINI_API_KEY` | Yes (for AI grading) | `""` | Google Gemini API key (free tier) |
| `DATABASE_URL` | No | `sqlite+aiosqlite:///dca_catcher.db` | Database connection string |

### Example `.env` setup
```bash
export TELEGRAM_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
export GEMINI_API_KEY="AIzaSy..."
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/dca_catcher"
```

---

## 13. Testing

### 13.1 Test Framework
- `pytest 9.1.1` with `pytest-asyncio 1.4.0`
- Async mode: `strict` (requires explicit `@pytest.mark.asyncio`)
- Python path configured in `pytest.ini`: `pythonpath = .`

### 13.2 Test Summary (21 tests, all passing)

| File | Tests | What's Tested |
|------|-------|---------------|
| `tests/test_database.py` | 4 | Engine creation, model CRUD with async session, FK validation, requirements check |
| `tests/test_fetcher.py` | 4 | Valid US symbol (AAPL), valid TH symbol (.BK), invalid symbol skip, multi-symbol batch |
| `tests/test_transform.py` | 7 | 4 drawdown threshold tiers, FLOW placeholder, CONTEXT placeholder, full enrichment structure |
| `tests/test_grader.py` | 6 | Happy path, markdown-fenced JSON, invalid JSON fallback, prompt content, missing fields, API error fallback |

### 13.3 Test Strategy
- **Database tests:** Use `aiosqlite` in-memory database (`sqlite+aiosqlite:///:memory:`)
- **Fetcher tests:** Real yfinance API calls (integration tests)
- **Transform tests:** Pure unit tests with synthetic `StockSnapshot` data
- **Grader tests:** Mock Gemini API via `unittest.mock.patch` — no real API calls
- **Bot tests:** None (integration boundary) — verified via import check

### 13.4 Running Tests
```bash
source venv/bin/activate
pytest tests/ -v                    # run all 21 tests
pytest tests/test_fetcher.py -v     # run specific module
pytest tests/ -v --tb=short         # shorter traceback
```

---

## 14. File Structure

```
dca-catcher/
├── PROGRESS.md                         ← Development progress + checkpoints
├── requirements.txt                    ← Python dependencies
├── pytest.ini                          ← Pytest config (pythonpath = .)
├── .gitignore                          ← venv/, __pycache__/, .pytest_cache/
│
├── src/
│   ├── __init__.py                     ← Package marker
│   ├── config.py                       ← Config dataclass (19 lines)
│   ├── database.py                     ← Database class + ORM models (67 lines)
│   ├── fetcher.py                      ← MarketDataFetcher + StockSnapshot (63 lines)
│   ├── transform.py                    ← DataTransformer + DimensionScore + EnrichedSignal (96 lines)
│   ├── grader.py                       ← SignalGrader + GradeResult (130 lines)
│   └── bot.py                          ← DCABot + Telegram commands (257 lines)
│
├── tests/
│   ├── test_database.py                ← 4 tests
│   ├── test_fetcher.py                 ← 4 tests
│   ├── test_transform.py               ← 7 tests
│   └── test_grader.py                  ← 6 tests
│
├── docs/
│   └── superpowers/
│       ├── specs/
│       │   └── 2026-08-06-dca-catcher-design.md    ← Original design vision (Thai)
│       └── plans/
│           └── 2026-08-06-dca-catcher-plan.md      ← Original implementation plan
│
└── venv/                               ← Python virtual environment (gitignored)
```

---

## 15. How to Run

### 15.1 Development Setup
```bash
cd /Users/rocket/Desktop/Python/dca-catcher
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pytest tests/ -v                    # verify everything works
```

### 15.2 Running the Bot
```bash
source venv/bin/activate
export TELEGRAM_TOKEN="your-token"
export GEMINI_API_KEY="your-key"
export DATABASE_URL="sqlite+aiosqlite:///dca_catcher.db"  # or PostgreSQL
python -m src.bot
```

### 15.3 Docker (Planned)
```dockerfile
# Not yet implemented — planned for future
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
CMD ["python", "-m", "src.bot"]
```

---

## 16. Known Warnings

| Warning | Source | Impact | Fix |
|---------|--------|--------|-----|
| `google-generativeai` deprecated | Google | Package works but won't get updates | Migrate to `google-genai` package |
| Python 3.10 EOL for `google.api_core` | Google | Will lose support after 2026-10-04 | Upgrade to Python 3.11+ |

---

## 17. Future Roadmap (Original Vision)

### Phase 2: Full Dimension Implementation
- [ ] FLOW dimension: Volume vs 20-day moving average using `ta` library
- [ ] CONTEXT dimension: CNN Fear & Greed Index scraping
- [ ] CONTEXT dimension: Google News RSS sentiment analysis
- [ ] PRICE dimension: Add RSI indicator via `ta` library
- [ ] Add `market_data` table for historical price caching
- [ ] Add `news_cache` table for scraped news storage

### Phase 3: Smart Notifications
- [ ] Scheduler: Daily Summary at 07:00 ICT
- [ ] Scheduler: SET Pre-market signal at 09:30 ICT
- [ ] Scheduler: US Pre-market signal at 20:00 ICT
- [ ] Intraday: Poll every 15 mins during market hours
- [ ] Intraday: Alert on >= 5% intraday drop

### Phase 4: Enhanced UX
- [ ] `/remove <symbol>` command
- [ ] `/settings` command for notification preferences
- [ ] Interactive Inline Keyboards (quick action buttons)
- [ ] LangGraph Agent pipeline (replace manual orchestration)

### Phase 5: Deployment
- [ ] Dockerfile + docker-compose.yml
- [ ] PostgreSQL container for production
- [ ] Environment-based config (dev/staging/prod)
