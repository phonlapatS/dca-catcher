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

### Tier 1 — ความเสี่ยงสูงมาก (7 รายการ) ⬅️ ทำก่อน
1. ❌ Portfolio SELL คำนวณต้นทุนผิด (`bot.py`)
2. ❌ Technical Indicators ไม่ถูก map กลับ Snapshot (`transform.py`)
3. ❌ User ID หายตอนกดปุ่ม Insight (`bot.py`)
4. ❌ JSON Parse จาก LLM ไม่ Robust (3 ไฟล์)
5. ❌ Event Loop Blocking จาก yfinance (`fetcher.py`)
6. ❌ Blocking Gemini Call (`catalyst/evaluator.py`)
7. ❌ DB Spam จาก Sniper Trade Ticks (`sniper.py`)

### Tier 2 — ความเสี่ยงสูง (8 รายการ)
- Insight Pipeline Sequential → Parallel
- Telegram Rate Limit (Progress Bar)
- User-level Command Rate Limit
- Charting ดึงข้อมูลซ้ำ 3 รอบ
- DST Hardcode ใน Sniper
- requirements.txt ไม่มี Version Pinning
- และอื่นๆ

### Tier 3-4 — ปานกลาง/ต่ำ (17 รายการ)
- Race Condition, Error Handling, Code Quality, Refactoring, Tests

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
