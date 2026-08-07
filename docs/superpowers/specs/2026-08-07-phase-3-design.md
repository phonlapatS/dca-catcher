# DCA Catcher: Phase 3 Design (Deployment & Engagement)

## Overview
Phase 3 transitions the DCA Catcher from a manual, reactive bot into an automated, proactive system. It introduces background task scheduling, dynamic channel broadcasting, interactive Telegram keyboards, and Docker deployment.

---

## 1. The Scheduling Engine
**Goal:** Automate market analysis without requiring user intervention.
**Implementation:** `APScheduler` (specifically `AsyncIOScheduler`) will be integrated directly into `bot.py` alongside the `aiogram` dispatcher.

**Schedules:**
- `07:00 AM (ICT)`: **Daily Master Broadcast** (Scans all unique stocks across all users).
- `09:30 AM (ICT)`: **Thai Pre-Market Alert** (Scans only stocks ending in `.BK`).
- `08:00 PM (ICT)`: **US Pre-Market Alert** (Scans only US stocks).

---

## 2. The Dynamic Broadcast System
**Goal:** Spread information to a community channel efficiently while avoiding API rate limits.
**Implementation:**
- A new environment variable `BROADCAST_CHANNEL_ID` will be added.
- **Dynamic Master Watchlist:** The bot runs `SELECT DISTINCT symbol FROM watchlists` to generate the list of stocks to scan. This ensures that *any* stock added by *any* user is automatically included in the morning broadcast.
- **Hashtags:** The output message will append hashtags for easy searching (e.g., `#NVDA #USMarket #StrongBuy`).

---

## 3. Interactive Keyboards (Growth Loop)
**Goal:** Drive channel subscribers into the bot's private DMs to build their personal watchlists.
**Implementation:**
- Use `aiogram.types.InlineKeyboardMarkup` and `InlineKeyboardButton`.
- Below each broadcasted stock, a button will appear: `[+ Add to Watchlist]`.
- **Deep Linking:** The button's URL will use Telegram's deep linking feature: `https://t.me/<BOT_USERNAME>?start=add_<SYMBOL>`.
- When a user clicks it, it opens a private chat with the bot, passes the `add_<SYMBOL>` payload, and the bot automatically adds the stock to their personal watchlist.

---

## 4. Docker Deployment
**Goal:** Ensure 24/7 uptime and easy server deployment.
**Implementation:**
- **`Dockerfile`:** Standard Python 3.10 slim image. Installs dependencies from `requirements.txt`.
- **`docker-compose.yml`:** Manages environment variables and maps the SQLite database volume (`dca_catcher.db`) to the host machine to prevent data loss when the container restarts.

---

## Error Handling & Constraints
- **API Quotas:** The dynamic Master Watchlist ensures we only scan a symbol *once* per broadcast, regardless of how many users have it on their personal watchlists.
- **Timezones:** APScheduler must be explicitly configured to use the `Asia/Bangkok` timezone so the schedules trigger accurately.
