# 🔍 Dead Code Audit Report
**Audited on:** 2026-09-22
**Status:** จดไว้เพื่อรอเอาออกในอนาคต (Documented for future cleanup)

---

## 🔴 Dead Code ที่ไม่ถูกเรียกใช้จากที่ใดเลย

### 1. `src/fetcher.py`
- **`fetch_async()` (L43)** — ระบบหลักใช้ `fetch()` ผ่าน `run_in_executor` แทน
- **`_fetch_one_sync()` (L60)** — เป็น helper ของ `fetch_async` เมื่อตัวหลักไม่ถูกใช้ ตัวนี้จึงตายด้วย

### 2. `src/grader.py`
- **`_parse_response()` (L187)** — ตกค้างจากเวอร์ชันเก่า (backward compat helper) ปัจจุบันใช้ `call_json` + `_parse_data` แทน
- **`generate_insight_report()` (L206)** — ถูก deprecated และถูกแทนที่โดย `InsightPipeline.generate()` โดยสิ้นเชิง
- **`dims_str` และ `indicators_text` (L77-93)** — ถูกคำนวณใน `_build_prompt` แต่ไม่ได้ถูกใส่เข้าไปใน prompt จริง (ถูกแทนที่ด้วย `<MARKET_DATA>` XML block)

### 3. `src/insight_pipeline.py`
- **`QualityVerdict` class (L111)** — ถูก instantiate ที่ L475 แต่ตัวแปร `verdict` ไม่เคยถูกนำไปใช้งานหรือ return ต่อ

### 4. `src/database.py`
- **`get_engine()` (L352)** — standalone helper ที่ไม่มีใคร import ไปใช้
- **`get_session_maker()` (L356)** — standalone helper ที่ไม่มีใคร import ไปใช้
- **`Database.engine` property (L151)** — ไม่มีการเข้าถึง property นี้จากที่ใดเลย

### 5. `src/handlers/mixins/scanning.py`
- **`global_error_handler()` (L22)** — ไม่ได้ลงทะเบียน เพราะ `bot.py:149` มีอันของตัวเอง

### 6. `src/handlers/mixins/watchlist.py`
- **`global_error_handler()` (L22)** — เหตุผลเดียวกับ scanning.py
- **`create_add_watchlist_keyboard()` (L54)** — ไม่ถูกเรียกใช้เลยจากไฟล์นี้

---

## 🟡 Copy-Paste Leftovers (ขยะจากการแยกไฟล์ Mixin)

### `scanning.py` และ `watchlist.py`
- `GRADE_LABELS`, `GRADE_EMOJIS` — ไม่ได้ใช้ในไฟล์เหล่านี้
- `RiskSurvey`, `AdviceSurvey` State classes — ไม่ได้ใช้ (ของจริงอยู่ใน `survey.py`)
- `ALL_SECTORS`, `SUBSECTORS` dicts — ไม่ได้ใช้ (ของจริงอยู่ใน `survey.py`)

---

## 📌 หมายเหตุ
รายการเหล่านี้ถูกตรวจสอบแล้วว่าไม่กระทบต่อระบบหากลบออก แต่ยังไม่ลบเพราะต้องการดูอีกรอบก่อน cleanup
