# DCA Catcher: Production Stateless Architecture (August 2026)

## 1. Overview
As the system scaled to handle 24/7 background worker operations (Real-Time Catalyst Hunter) and deeper AI evaluations, the original architecture (Local SQLite + Synchronous Event Loops) became a bottleneck. 
This document outlines the transition to a **Stateless Production Architecture**, ensuring high availability, zero data loss, and non-blocking Telegram UI responsiveness.

## 2. Infrastructure Separation (Stateless Design)

### 2.1 Compute Layer (Fly.io)
- **Role:** Executes Python application logic, AI evaluation pipelines, and Telegram WebSockets.
- **Nature:** Ephemeral / Stateless. The container can be restarted, scaled, or redeployed at any time without losing any user data.
- **Constraints Handled:** Limited RAM (512MB) is managed by safely offloading charting tasks and closing matplotlib figures to prevent memory leaks (`plt.close(fig)`).

### 2.2 Database Layer (Supabase PostgreSQL)
- **Role:** Single Source of Truth for Users, Watchlists, Memory Snapshots, and Seen Catalysts.
- **Connection Driver:** Migrated from `aiosqlite` to `asyncpg`.
- **Connection Pooling:** Connects via Supabase Transaction Pooler (Port 6543) with `pgbouncer=true`. This allows the application to open hundreds of concurrent async connections without running into connection limits or `Database is locked` errors previously seen with SQLite.

## 3. Asynchronous Execution & Bottleneck Resolution

### 3.1 Unblocking the Telegram Event Loop
**Previous Issue:** Network I/O such as `yfinance.download()` and `feedparser.parse()` were synchronous. When a user requested `/scan-details`, these functions blocked the entire `aiogram` event loop, causing the bot to "freeze" and stop responding to other users.

**Solution (Executor Delegation):**
All synchronous network boundaries are now wrapped in `asyncio.get_running_loop().run_in_executor()`.
This offloads the heavy blocking operations to background worker threads, keeping the main async event loop completely free to handle Telegram UI updates (e.g., Dynamic Progress Bars) and concurrent user requests.

### 3.2 Dynamic UI Updates (Thread-Safe)
**Issue:** Attempting to update Telegram messages from inside the background executor raised `RuntimeError: no running event loop`.
**Solution:** The main event loop is captured prior to delegation, and progress callbacks use `asyncio.run_coroutine_threadsafe(update_progress(), main_loop)` to safely bridge updates from worker threads back to the Telegram UI.

## 4. Concurrency & Overlap Safeguards (Race Conditions)

### 4.1 Zero-Token Deduplication Race Conditions
**Scenario:** Multiple identical catalyst news articles arrive at the exact same millisecond across different providers.
**Protection:** The `seen_catalysts` table utilizes a `UNIQUE` constraint on the `headline_hash`. If two threads attempt to insert the same hash concurrently, PostgreSQL triggers an `IntegrityError`. The Python database manager catches this via a `try...except` block and safely issues an `await session.rollback()`, discarding the duplicate without crashing the thread.

### 4.2 Scheduler Overlap (APScheduler)
**Scenario:** A Catalyst Hunter cycle is scheduled every 2 minutes. During intense market activity, AI evaluation takes 3 minutes.
**Protection:** `APScheduler` is inherently configured with `max_instances=1` per job. If a new trigger time is reached while the previous cycle is still running, the scheduler explicitly skips (misfires) the new cycle, preventing exponential task pile-up and memory exhaustion (OOM).

## 5. Conclusion
The transition from a monolithic local setup to a decoupled, stateless cloud architecture successfully fortifies the DCA Catcher bot for production-grade reliability. By implementing strict async boundary delegation and connection pooling, the system is now highly concurrent and immune to the UI freezing and data loss issues that characterized the earlier phases.
