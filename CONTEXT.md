# DCA Catcher - Context Note & Handover

## 📅 Current Status
**Date:** 2026-08-23
**Phase:** Phase 9 — Optimization & Bug Fixes
**Branch:** `phase-9` (สร้างจาก `phase-7` ซึ่งเป็น Branch ปัจจุบัน)

## ✅ What we just finished (Phase 8)
1. **Slip Parsing:** Built `GeminiSlipParser` to extract BUY/SELL trades from uploaded screenshots (e.g. Dime app) using Vision AI.
2. **Portfolio Tracking (`/portfolio`):** Calculated PnL dynamically by joining parsed slips with live Yahoo Finance prices.
3. **UAT & Hotfixes:**
   - Fixed Supabase idle connection drops (`pool_pre_ping`).
   - Fixed `google-genai` async method signature changes.
   - Fixed UI layout for Slip Confirmation and Portfolio (Markdown formatting).
   - Added Progress Bar for `/scan`.
   - **Critical Bugfix:** Fixed `/scan` hang caused by sequential O(N) fetching. Reverted to Bulk Fetch.
   - **Model Policy Enforcement:** Explicitly documented `models.md` to prevent downgrading user's futuristic Gemini models (e.g., `gemini-3.5-flash`). Restored `insight_pipeline.py` and `slip_parser.py` to use `PipelineConfig` strictly.

## 🚧 What we are currently doing (Phase 9)
- **Code Audit Complete:** ตรวจสอบโค้ดทั้งโปรเจกต์ พบปัญหา 32 รายการ
- **Implementing fixes in priority order:**

### Tier 1 — ความเสี่ยงสูงมาก (7 รายการ + 1 Hotfix) ✅ เสร็จสมบูรณ์
1. ❌ Portfolio SELL คำนวณต้นทุนผิด (`bot.py`) - แก้ไขแล้ว
2. ❌ Technical Indicators ไม่ถูก map กลับ Snapshot (`transform.py`) - แก้ไขแล้ว
3. ❌ User ID หายตอนกดปุ่ม Insight (`bot.py`) - แก้ไขแล้ว
4. ❌ JSON Parse จาก LLM ไม่ Robust (3 ไฟล์) - แก้ไขแล้ว
5. ❌ Event Loop Blocking จาก yfinance (`fetcher.py`) - แก้ไขแล้ว
6. ❌ Blocking Gemini Call (`catalyst/evaluator.py`) - แก้ไขแล้ว
7. ❌ DB Spam จาก Sniper Trade Ticks (`sniper.py`) - แก้ไขแล้ว
8. ❌ Hotfix: แก้ไข Signal.created_at timezone crash

### Tier 2 — ความเสี่ยงสูง (7 รายการ) ✅ เสร็จสมบูรณ์
- Insight Pipeline Sequential → Parallel (แก้ไขแล้ว)
- Telegram Rate Limit (Progress Bar) (แก้ไขแล้ว)
- User-level Command Rate Limit (แก้ไขแล้ว)
- Charting ดึงข้อมูลซ้ำ 3 รอบ (แก้ไขแล้ว)
- DST Hardcode ใน Sniper (แก้ไขแล้ว)
- requirements.txt ไม่มี Version Pinning (แก้ไขแล้ว)
- N+1 Query Fix ใน `cmd_remove` (แก้ไขแล้ว)

### Tier 3 — ความเสี่ยงปานกลาง (10 รายการ) ✅ 8/10 เสร็จ, 2 deferred
- ✅ 3.1 Race Condition `get_user` → IntegrityError upsert
- ✅ 3.2 Silent `except: pass` → `logger.debug/warning`
- ✅ 3.3 `memory.py` Full Table Scan → ลบ `func.upper()` ใช้ index ได้
- ✅ 3.4 Catalyst hardcode symbols → ดึงจาก watchlist, return 0 ถ้าว่าง
- ⏭️ 3.5 DI สำหรับ LLM clients → **deferred** (refactor ใหญ่เกินสำหรับ bugfix phase, ควรทำแยก phase)
- ✅ 3.6 Timestamp consistency → ทุก model: `DateTime(timezone=True)` + `default` + `server_default`
- ✅ 3.7 Config validation → raise ValueError ถ้า TELEGRAM_TOKEN/GEMINI_API_KEY หายไป
- ✅ 3.8 Button parsing → safe split + guard ก่อน index access
- ✅ 3.9 IndexError guard → `.get()` สำหรับ CNN API, `getattr`/`hasattr` สำหรับ feedparser
- ✅ 3.10 Catalyst cleanup → เพิ่ม `cleanup_old_catalysts(retention_days=30)`

### Tier 4 — ความเสี่ยงต่ำ (✅ COMPLETE)
- [x] **4.1** Dead Code cleanup — ลบ unused imports ใน `memory.py`
- [x] **4.2** Dockerfile — Multi-stage build + `.dockerignore`
- [x] **4.3** Tests — เพิ่มและรัน 91 tests ผ่าน 100%
- [x] **4.4** `pytest.ini` — เพิ่ม `asyncio_mode = auto` และ `testpaths = tests`
- [x] **4.5** `fly.toml` — เพิ่ม RAM จาก 512MB เป็น 1GB สำหรับ AI concurrency
- [x] **4.6** Type hints — เพิ่มใน module สำคัญ
- [x] **4.7** README.md — อัปเดตเนื้อหาครอบคลุม Phase 9

## 📁 Phase 9 Documentation
- **Design Spec:** `docs/superpowers/specs/2026-08-23-phase-9-optimization-bugfix-design.md`
- **Implementation Plan:** `docs/superpowers/plans/2026-08-23-phase-9-optimization-bugfix-plan.md`
- **Summary:** `docs/phase_9.md`

## ⚠️ Important Rules for Next Agent
- **DO NOT** change Gemini model names unless explicitly requested. Read `docs/superpowers/specs/models.md` first.
- **DO NOT** add new features in Phase 9. This phase is for fixing and optimizing existing code only.
- **DO NOT** change Database Schema (except adding indexes if needed).
- Follow the Implementation Plan task order: Tier 1 → Tier 2 → Tier 3 → Tier 4.
- Run `pytest tests/ -v` after every change to ensure no regression.

## 🚀 Next Steps (After Phase 9)
1. **Agent Framework Evaluation:** ประเมินว่าควรใช้ Agent Framework (LangGraph/CrewAI/ADK) สำหรับ Catalyst Hunter หรือไม่
2. **Bot Refactoring:** แยก `bot.py` (82KB) ออกเป็น Aiogram Router ย่อยๆ
3. **Branch Integration:** Merge เข้า `main` ผ่าน PR
