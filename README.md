# 🎯 DCA Catcher

> AI-powered Telegram bot that helps DCA investors find the best time to buy stocks.

ระบบ AI ผู้ช่วยวิเคราะห์หุ้นสำหรับสาย DCA — สแกนตลาด US และไทย, วิเคราะห์ 3 มิติ, ให้คะแนนด้วย Gemini AI พร้อมคำแนะนำภาษาไทย

---

## ✨ Features

- 📊 **Real-time stock data** — Fetch from Yahoo Finance (US + Thai `.BK` markets)
- 🧠 **3-Dimension Analysis** — Score stocks on Price, Flow, and Context
- 🤖 **AI Grading** — Google Gemini rates each stock 1-4 with Thai advice
- 💬 **Telegram Bot** — `/add`, `/list`, `/scan` commands for your watchlist
- 👥 **Multi-user** — Each user has their own watchlist
- 🆓 **100% Free Tier** — All tools are free to use

## 📊 Grade Scale

| Grade | Emoji | Meaning |
|-------|-------|---------|
| 1 | 🔴 | Risky — มีความเสี่ยงสูง |
| 2 | 🟡 | Hold — ถือ/รอดู |
| 3 | 🟢 | Good DCA — เหมาะแก่การ DCA |
| 4 | 🌟 | Strong Buy — สัญญาณซื้อแข็งแกร่ง |

---

## 🚀 Quick Start

### 1. Setup
```bash
git clone https://github.com/phonlapatS/dca-catcher.git
cd dca-catcher
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Set environment variables
```bash
export TELEGRAM_TOKEN="your-telegram-bot-token"
export GEMINI_API_KEY="your-gemini-api-key"
export DATABASE_URL="sqlite+aiosqlite:///dca_catcher.db"
```

### 3. Run
```bash
python -m src.bot
```

### 4. Test
```bash
pytest tests/ -v
```

---

## 🏗️ Architecture

```
User (Telegram)
    │  /scan NVDA
    ▼
DCABot ─── MarketDataFetcher ─── yfinance (Yahoo Finance)
  │              │
  │              ▼ StockSnapshot
  │        DataTransformer
  │              │
  │              ▼ EnrichedSignal (3 dimensions)
  │        SignalGrader ─── Gemini AI
  │              │
  │              ▼ GradeResult (grade 1-4)
  ▼
📱 Telegram reply with 🔴🟡🟢🌟
```

## 📁 Project Structure

```
src/
├── config.py       Config dataclass (env vars)
├── database.py     Database class + User/Watchlist/Signal models
├── fetcher.py      MarketDataFetcher + StockSnapshot
├── transform.py    DataTransformer + 3-dimension scoring
├── grader.py       SignalGrader + GradeResult (Gemini AI)
└── bot.py          DCABot (Telegram commands)
```

## 🛠️ Tech Stack

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.10+ | Runtime |
| SQLAlchemy | 2.0 | Async ORM |
| yfinance | 1.5 | Market data |
| Gemini AI | 2.0-flash | AI grading |
| aiogram | 3.30 | Telegram bot |
| pytest | 9.1 | Testing (21 tests) |

---

## 📋 Telegram Commands

| Command | Example | Description |
|---------|---------|-------------|
| `/start` | `/start` | Welcome + help |
| `/add` | `/add NVDA US` | Add stock to watchlist |
| `/list` | `/list` | View your watchlist |
| `/scan` | `/scan NVDA` | AI analysis for a stock |
| `/scan` | `/scan` | Scan entire watchlist |

---

## 📖 Docs

- [Technical Spec](docs/superpowers/specs/2026-08-06-dca-catcher-design.md) — Full spec with DB schema, API details, all method signatures
- [Development Progress](PROGRESS.md) — Task status, checkpoints, git rollback points

## 📝 License

This project is for personal/educational use.
