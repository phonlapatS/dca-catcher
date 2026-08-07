# Implementation Plan: Alpaca WebSocket Sniper

## Global Constraints
- Target Timezone: Asia/Bangkok
- Only run the websocket between 20:30 and 04:00 BKK time.
- Use `websockets` library.
- The `AlpacaSniper` must read target prices from `target_zones_str` in the database.

## Task 1: Create the Sniper Module
- Create `src/sniper.py`.
- Define an `AlpacaSniper` class that connects to `wss://stream.data.alpaca.markets/v2/iex`.
- Implement `start()` and `stop()` methods.
- Implement a loop that authenticates and subscribes to active US tickers in the database.

## Task 2: Integrate Sniper with Database and Trigger
- Update `AlpacaSniper` to query the database for all `Watchlist` items where `market == "US"`.
- Parse `target_zones_str` to extract the target price.
- When a live tick price drops <= target price, trigger a log message and update a `last_notified` timestamp in DB to prevent spam.

## Task 3: Integrate with Bot Lifecycle
- Update `src/bot.py` to import `AlpacaSniper`.
- In `on_startup`, instantiate the sniper and run it as an asyncio background task if the current time is within market hours.
