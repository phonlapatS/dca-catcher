# DCA Catcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an asynchronous Python Telegram bot that scans stocks, analyzes market data and news across 3 dimensions, and uses Gemini to send automated DCA recommendations.

**Architecture:** Async Python application utilizing LangGraph for the evaluation pipeline, SQLAlchemy for PostgreSQL persistence, `yfinance` for market data, and `aiogram` for the Telegram interface.

**Tech Stack:** Python 3.11+, LangGraph, SQLAlchemy (async), aiogram, yfinance, ta, google-generativeai, pytest

## Global Constraints
- Target market data: US and TH stocks (yfinance format `.BK`)
- LLM Provider: Google Gemini (Free Tier)
- Infrastructure: Docker-ready (single container)
- Database: PostgreSQL

---

### Task 1: Project Scaffolding & Database Setup

**Files:**
- Create: `requirements.txt`
- Create: `src/database.py`
- Create: `tests/test_database.py`

**Interfaces:**
- Produces: SQLAlchemy async engine and declarative base models (`User`, `Watchlist`, `Signal`).

- [ ] **Step 1: Write requirements and failing test**

Create `requirements.txt`:
```text
sqlalchemy[asyncio]
aiosqlite  # For local testing
pytest
pytest-asyncio
```

Create `tests/test_database.py`:
```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_engine, Base

@pytest.mark.asyncio
async def test_engine_creation():
    engine = get_engine("sqlite+aiosqlite:///:memory:")
    assert engine is not None
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_database.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src'"

- [ ] **Step 3: Write minimal implementation**

Create `src/database.py`:
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import Integer, String, DateTime
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True)
    username: Mapped[str] = mapped_column(String, nullable=True)

class Watchlist(Base):
    __tablename__ = "watchlists"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer)
    symbol: Mapped[str] = mapped_column(String)
    market: Mapped[str] = mapped_column(String)

def get_engine(url: str):
    return create_async_engine(url, echo=False)

def get_session_maker(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pip install -r requirements.txt && pytest tests/test_database.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt src/database.py tests/test_database.py
git commit -m "feat: setup database models and sqlalchemy engine"
```

---

### Task 2: Data Fetching Module (yfinance)

**Files:**
- Modify: `requirements.txt`
- Create: `src/fetcher.py`
- Create: `tests/test_fetcher.py`

**Interfaces:**
- Consumes: Stock symbols
- Produces: `fetch_market_data(symbols: list[str]) -> dict` containing price, volume, and ATH data.

- [ ] **Step 1: Write the failing test**

Modify `requirements.txt` to add `yfinance` and `pandas`.

Create `tests/test_fetcher.py`:
```python
import pytest
from src.fetcher import fetch_market_data

def test_fetch_market_data():
    data = fetch_market_data(["AAPL"])
    assert "AAPL" in data
    assert "current_price" in data["AAPL"]
    assert "volume" in data["AAPL"]
    assert "ath_price" in data["AAPL"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fetcher.py -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Write minimal implementation**

Create `src/fetcher.py`:
```python
import yfinance as yf
import pandas as pd

def fetch_market_data(symbols: list[str]) -> dict:
    result = {}
    for sym in symbols:
        ticker = yf.Ticker(sym)
        hist = ticker.history(period="max")
        if hist.empty:
            continue
        
        latest = hist.iloc[-1]
        ath = hist['High'].max()
        
        result[sym] = {
            "current_price": float(latest['Close']),
            "volume": int(latest['Volume']),
            "ath_price": float(ath),
            "drawdown_pct": ((float(latest['Close']) - float(ath)) / float(ath)) * 100
        }
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pip install yfinance pandas && pytest tests/test_fetcher.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt src/fetcher.py tests/test_fetcher.py
git commit -m "feat: add market data fetcher using yfinance"
```

---

### Task 3: Technical Indicators & Transformation

**Files:**
- Modify: `requirements.txt`
- Create: `src/transform.py`
- Create: `tests/test_transform.py`

**Interfaces:**
- Consumes: Data from `fetch_market_data`
- Produces: `enrich_data(symbol_data: dict) -> dict` grouped into Dimensions (PRICE, FLOW).

- [ ] **Step 1: Write the failing test**

Create `tests/test_transform.py`:
```python
import pytest
from src.transform import enrich_data

def test_enrich_data():
    raw_data = {
        "NVDA": {
            "current_price": 100.0,
            "volume": 500000,
            "ath_price": 125.0,
            "drawdown_pct": -20.0
        }
    }
    enriched = enrich_data(raw_data)
    assert "NVDA" in enriched
    assert "dimensions" in enriched["NVDA"]
    assert "PRICE" in enriched["NVDA"]["dimensions"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_transform.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Create `src/transform.py`:
```python
def enrich_data(raw_data: dict) -> dict:
    enriched = {}
    for sym, data in raw_data.items():
        # Minimal mock of grouping logic for MVP
        price_signal = "BUY" if data["drawdown_pct"] <= -20 else "HOLD"
        
        enriched[sym] = {
            "raw": data,
            "dimensions": {
                "PRICE": price_signal,
                "FLOW": "HOLD",  # Placeholder for moving avg volume
                "CONTEXT": "HOLD" # Placeholder for news sentiment
            }
        }
    return enriched
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_transform.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/transform.py tests/test_transform.py
git commit -m "feat: add initial data transformer and dimension grouper"
```

---

### Task 4: AI Grading (Gemini Integration)

**Files:**
- Modify: `requirements.txt`
- Create: `src/grader.py`
- Create: `tests/test_grader.py`

**Interfaces:**
- Consumes: Enriched data dimensions.
- Produces: `grade_signal(enriched_data: dict, api_key: str) -> dict` containing the grade (1-4), confidence, and Thai advice.

- [ ] **Step 1: Write the failing test**

Add `google-generativeai` to `requirements.txt`.

Create `tests/test_grader.py`:
```python
import pytest
from unittest.mock import patch
from src.grader import grade_signal

@patch("src.grader.genai.GenerativeModel.generate_content")
def test_grade_signal(mock_generate):
    # Mock LLM JSON response
    mock_generate.return_value.text = '{"grade": 4, "confidence": 95, "advice": "#ควรซื้อตอนนี้"}'
    
    data = {"dimensions": {"PRICE": "BUY", "FLOW": "BUY", "CONTEXT": "BUY"}}
    result = grade_signal(data, api_key="dummy")
    
    assert result["grade"] == 4
    assert result["confidence"] == 95
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_grader.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Create `src/grader.py`:
```python
import google.generativeai as genai
import json

def grade_signal(enriched_data: dict, api_key: str) -> dict:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    prompt = f"""
    Analyze these dimensions: {enriched_data['dimensions']}
    Respond ONLY with a JSON object containing:
    - grade (int 1-4)
    - confidence (int 0-100)
    - advice (str)
    """
    
    response = model.generate_content(prompt)
    try:
        # Strip potential markdown formatting from LLM response
        text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception:
        return {"grade": 2, "confidence": 0, "advice": "Error parsing LLM response"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pip install google-generativeai && pytest tests/test_grader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt src/grader.py tests/test_grader.py
git commit -m "feat: add AI grading module via Gemini"
```

---

### Task 5: Telegram Bot Interface

**Files:**
- Modify: `requirements.txt`
- Create: `src/bot.py`

**Interfaces:**
- Setup the `/start` and `/add` commands using `aiogram`.

- [ ] **Step 1: Setup aiogram bot stub**

Add `aiogram` to `requirements.txt`.

Create `src/bot.py`:
```python
import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

bot = Bot(token=os.environ.get("TELEGRAM_TOKEN", "dummy"))
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("ยินดีต้อนรับสู่ DCA Catcher! พิมพ์ /add <ชื่อหุ้น> <ตลาด> เพื่อเริ่มติดตาม")

async def main():
    if os.environ.get("TELEGRAM_TOKEN") != "dummy":
        await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Commit**

```bash
git add requirements.txt src/bot.py
git commit -m "feat: setup basic telegram bot with aiogram"
```
