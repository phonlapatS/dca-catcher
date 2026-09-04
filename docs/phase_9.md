# Phase 9: Optimization & Bug Fixes

## 🎯 Overview
Phase 9 เป็น Hardening Phase ที่เน้นแก้ไข Critical Bugs, ปรับปรุง Performance, เพิ่มความเสถียร และยกระดับคุณภาพโค้ดของระบบ DCA Catcher ทั้งหมด ไม่มีการเพิ่มฟีเจอร์ใหม่ — เน้นทำให้ฟีเจอร์ที่มีอยู่ทำงาน **ถูกต้อง, เร็ว, และเสถียร** สำหรับ Production

## 📊 สิ่งที่ค้นพบจาก Code Audit
จากการตรวจสอบโค้ดทั้งโปรเจกต์ พบปัญหา **32 รายการ** แบ่งเป็น:

| ระดับ | จำนวน | ตัวอย่างปัญหา |
|---|:---:|---|
| 🔴 สูงมาก (Tier 1) | 7 | Portfolio PnL คำนวณผิด, Indicators ไม่ถึง AI, Event Loop Blocking |
| 🟠 สูง (Tier 2) | 8 | Pipeline ช้า 2x, Telegram Rate Limit, DST Hardcode |
| 🟡 ปานกลาง (Tier 3) | 10 | Race Condition, Error ถูกซ่อน, Memory Queue หาย |
| 🟢 ต่ำ (Tier 4) | 7 | Refactoring, Dead Code, Docker Best Practice |

## ✨ Key Fixes (Completed)

### Critical Bugs (Tier 1) ✅
1. **Portfolio SELL Cost** — ต้นทุนเฉลี่ยพุ่งผิดปกติเมื่อขายหุ้น → แก้ให้หักลบ `total_cost` ตามสัดส่วน
2. **Indicators → AI Pipeline** — RSI/MA50/Volume Anomaly คำนวณแล้วแต่ไม่ map กลับ Snapshot → AI ได้ข้อมูลไม่ครบ
3. **User ID Callback** — กดปุ่ม Insight แล้ว Memory ไม่ถูกบันทึก เพราะ `from_user` ชี้ไปที่บอท
4. **JSON Parse** — LLM ตอบกลับมาพร้อม Markdown fences → Crash → สร้าง `extract_json_from_llm()` utility
5. **Event Loop Blocking** — yfinance/Gemini เป็น Sync → ครอบด้วย `asyncio.to_thread()`
6. **DB Spam (Sniper)** — Query ทุก Trade Tick → ใช้ Memory Cache + Batch Update
7. **Signal Timezone Crash** — แก้ปัญหา timezone mismatch ของคอลัมน์ `created_at` ในตาราง `signals`

### Performance (Tier 2) ✅
- **Insight Pipeline Parallel:** Agent 1 & 2 รันพร้อมกันด้วย `ThreadPoolExecutor` (ลดเวลา 2x)
- **Async Charting:** ดึงข้อมูล 1 ครั้ง + slice แทนดึง 3 ครั้ง
- **Rate Limiting:** เพิ่ม `_throttled_edit()` (ลด Telegram 429 Error) และ `_check_cooldown()` 30 วินาที
- **N+1 Query Fix:** `cmd_remove` ใช้ `WHERE IN` แทนการ query วนลูป
- **DST Handling:** ใช้ timezone `America/New_York` จัดการ Daylight Saving Time อัตโนมัติ
- **Dependencies Pinning:** เพิ่ม version ranges ใน `requirements.txt` ป้องกันแพ็คเกจอัปเดตแล้วพัง

### Code Hardening (Tier 3) ✅ 8/10
- **Race Condition Fix:** `get_user` ใช้ IntegrityError upsert ป้องกัน duplicate user
- **Silent Error Logging:** เปลี่ยน `except: pass` → `logger.debug/warning` ในทุก provider
- **Memory Query Index:** ลบ `func.upper()` ใน `memory.py` — ใช้ index ได้ตรงๆ
- **Catalyst Dynamic Symbols:** ลบ hardcode symbols — ดึงจาก watchlist แทน
- **Timestamp Consistency:** ทุก model ใช้ `DateTime(timezone=True)` + `default` + `server_default`
- **Config Fail-Fast:** `Config.from_env()` raise ValueError ทันทีถ้า API keys หายไป
- **Safe Button Parsing:** guard `callback.data.split("_")` ป้องกัน IndexError
- **Defensive Access:** `.get()` สำหรับ CNN API, `getattr`/`hasattr` สำหรับ feedparser
- **Catalyst Retention:** เพิ่ม `cleanup_old_catalysts(30 days)` ป้องกัน table โตไม่จำกัด

#### Deferred Items (2 รายการ)
- **3.5 DI สำหรับ LLM clients** — เป็น refactor ระดับ architecture ที่ต้องแยก pipeline, bot, evaluator ออกจาก client instantiation → ควรทำเป็น phase แยกต่างหาก ไม่เหมาะกับ bugfix phase

## 🛠️ Architecture Changes
- **Async Wrapper Pattern:** ครอบ Blocking Calls ทั้งหมดด้วย `asyncio.to_thread()`
- **Robust JSON Extraction:** สร้าง `src/utils.py` สำหรับ parse LLM output อย่างปลอดภัย
- **Sniper Memory Cache:** โหลด Watchlist ขึ้น RAM → เช็คจาก Memory → Batch Write กลับ DB

## 📁 Documentation
- **Design Spec:** `docs/superpowers/specs/2026-08-23-phase-9-optimization-bugfix-design.md`
- **Implementation Plan:** `docs/superpowers/plans/2026-08-23-phase-9-optimization-bugfix-plan.md`

## 🚧 Upcoming (Tier 4)
- Dead code cleanup, Dockerfile optimization, Tests, pytest.ini, fly.toml RAM, Type hints, README update
- ไม่ได้ Refactor `bot.py` ออกเป็น Router ย่อยใน Phase นี้ (เก็บไว้ Phase ถัดไป)
