# Phase 10: Context-Aware News System (Design Spec)

**Status:** Planned
**Objective:** ยกระดับการนำเสนอข่าวสารในระบบให้มีความฉลาด, รวดเร็ว, คัดกรองข่าวขยะ, และใช้สถาปัตยกรรมแบบ Free-Tier 100%

## 🎯 1. Core Concepts (แนวคิดหลัก)
* **Pre-Scoring & Categorization:** ข่าวทุกชิ้นต้องถูกประเมินความสำคัญ (S, A, B, C) และแยกหมวดหมู่ (Macro, Sector, Micro) ไว้ล่วงหน้า
* **Strict Relevance & Spillovers:** ระบบจะดักจับข่าวที่ระบุ Ticker ตรงๆ (เช่น NVDA) และข่าวความเชื่อมโยงระดับ Supply Chain (เช่น TSM ผลิตชิปให้ NVDA)
* **Anti-Empty State:** หากไม่มีข่าวบริษัทโดยตรง ระบบจะ Pivot ไปดึงข่าว Sector หรือ Macro มาแสดงแทน เพื่อไม่ให้หน้าจอว่างเปล่า

## 🔀 2. Dynamic Routing (การกระจายข่าวตามบริบทคำสั่ง)
1. **`/scan` (The Quick Teaser):**
   * เน้นความเร็ว แสดงผลพาดหัวข่าว 1-3 บรรทัด
   * **ลอจิก:** หาข่าว S-Tier ก่อน ถ้าไม่มีให้ใช้ A-Tier (Adaptive Threshold) พร้อมระบุว่า Impact ต่ำ
2. **`🔍 Deep Dive` (The Strategist):**
   * เน้นประเมินจุดซื้อ DCA 
   * **ลอจิก:** นำข่าว S และ A มาผสมผสานแบบ Top-Down (Macro -> Sector -> Micro) เพื่อเขียนเป็น Story ประเมินผลกระทบ
3. **`/news <SYMBOL>` (The Explorer):**
   * เน้นความเข้าใจรอบด้าน
   * **ลอจิก:** กางข่าวทุกระดับ (S, A, B) จัดหมวดหมู่ชัดเจน แสดงทั้งมุมมองเชิงบวกและลบ

## 🛡️ 3. UX Enhancements
* **Confidence & Impact Score:** พาดหัวข่าวที่ผ่าน AI ต้องแนบ "ระดับความน่าเชื่อถือ (%)" และ "การประเมินผลกระทบ (บวก/ลบ/ไม่มีผล)" เสมอ
* **Visual Tags:** ใช้ Emoji แบ่งแยกข่าวตรงตัว (🔸) และข่าว Supply Chain (🔗)

## 🤖 4. Model Architecture (100% Free-Tier Constraint)
เพื่อประหยัด RAM บนเครื่อง 1GB (Fly.io) และลดค่าใช้จ่าย ระบบจะใช้หลักการ **Division of Labor** ผ่าน Free API:
* **The Filter (ด่านหน้าร่อนข่าวขยะ):** 
  * *ตัวเลือกหลัก:* **Gemini 1.5 Flash** (เร็ว, ฟรีโควต้าเดิม, ไม่ต้องเพิ่ม API Key)
  * *ทางเลือกเสริม:* **Groq API (Llama-3)** หรือ **Hugging Face API (FinBERT)**
  * *หน้าที่:* รับข่าว 50 ข่าว -> ตัดขยะ -> ประเมินความน่าเชื่อถือ -> ส่ง Top 3 ไปให้ด่านต่อไป
* **The Brain (ด่านวิเคราะห์กลยุทธ์):**
  * *โมเดล:* **Gemini Pro**
  * *หน้าที่:* รับข่าวเนื้อๆ จากด่านแรก ไปวิเคราะห์แผนการตั้งรับ DCA ใน Deep Dive
