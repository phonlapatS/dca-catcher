# 🎯 DCA Catcher

**Your Personal AI Quant & Automated Sniper for Long-Term Investing.**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Aiogram](https://img.shields.io/badge/Aiogram-3.x-green.svg)](https://docs.aiogram.dev/)
[![Gemini](https://img.shields.io/badge/Google_Gemini-1.5-orange.svg)](https://aistudio.google.com/)
[![Deployed on Fly.io](https://img.shields.io/badge/Deployed_on-Fly.io-purple.svg)](https://fly.io)

---

## 💡 Concept & Vision (แนวคิดของระบบ)

ตลาดหุ้นในปัจจุบันมีความผันผวนสูงและข้อมูลมหาศาล **DCA Catcher** ถูกออกแบบมาเพื่อตอบโจทย์นักลงทุนสายถือยาว (DCA / Value Investor) ที่ต้องการ **"สะสมหุ้นคุณภาพดี ในราคาที่เหมาะสม"** แต่ไม่มีเวลาเฝ้าหน้าจอหรือวิเคราะห์งบการเงินทุกวัน

ระบบนี้ไม่ได้เป็นแค่บอทแจ้งเตือนราคา แต่ทำหน้าที่เป็น **"ทีมวิเคราะห์ Quant ส่วนตัว"** ที่ผสานพลังของข้อมูลสถิติ (Data) เข้ากับปัญญาประดิษฐ์ (Generative AI) เพื่อประเมินสุขภาพหุ้น หาจุดเข้าซื้อที่ปลอดภัยที่สุด และคอยเฝ้าราคาให้คุณตลอด 24 ชั่วโมงผ่าน Telegram

---

## 🧠 Core Systems (หัวใจหลักของการทำงาน)

ระบบถูกออกแบบให้ทำงานสอดประสานกัน 4 โมดูลหลัก ดังนี้:

### 1. 🤖 AI Quant Evaluator (สมองวิเคราะห์เชิงปริมาณ)
- รวบรวมข้อมูลทั้ง **Fundamental** (ROE, ยอดขายเติบโต, กระแสเงินสด, ปันผล, P/E) และ **Technical** (RSI, เส้นค่าเฉลี่ย SMA200, ความผิดปกติของ Volume)
- ใช้เทคนิควิศวกรรม Prompt ขั้นสูง (Chain-of-Thought & XML-Tagged Data) บังคับให้ AI ประเมินหุ้นด้วยตรรกะแบบ Quant Engineer
- สร้าง **AI Score** (คะแนนความน่าลงทุน) และคำนวณ **"ราคาเป้าหมาย (Buy Targets)"** หรือแนวรับที่ควรแบ่งไม้เข้าซื้อ

### 2. 🎯 Real-Time Price Sniper (พลซุ่มยิงเฝ้าราคา)
- เชื่อมต่อสัญญาณสดระดับวินาที (Tick-level) ผ่าน **Alpaca WebSocket** 
- บอทจะนำ "ราคาเป้าหมาย" ที่ AI คำนวณไว้มาเฝ้าระวังอยู่เบื้องหลัง (Background Loop)
- ทันทีที่ราคาหุ้นตกลงมาถึงโซนปลอดภัย ระบบจะส่งแจ้งเตือนเข้า Telegram ของคุณแบบ Real-time ไม่ให้คุณพลาดโอกาสทอง

### 3. 📰 Multi-Agent Insight & Catalyst Radar (ทีมวิจัยและเรดาร์ข่าว)
- หากต้องการเจาะลึก ระบบจะแยกสมอง AI ออกเป็นหลายบทบาท (Multi-Agent) เช่น *นักวิเคราะห์พื้นฐาน, นักวิเคราะห์กราฟ, นักประเมินความเสี่ยง* เพื่อถกเถียงและสรุปรายงานเชิงลึก (`/scan-details`)
- มีระบบ **Market Catalyst** คอยตรวจจับข่าวสาร ดึงข้อมูลความเคลื่อนไหวตลาดแบบอัตโนมัติ และกรองเฉพาะข่าวกระทบแรง (High Impact) มาแจ้งเตือน

### 4. 📸 Vision AI Portfolio (บันทึกพอร์ตอัตโนมัติผ่านรูปภาพ)
- ลืมการจดบันทึกพอร์ตแบบ Manual ไปได้เลย เพียงแค่ส่ง **"รูปสลิปเทรด" (Trade Slip)** เข้ามาในแชท
- Vision AI จะอ่านชื่อหุ้น, ราคาที่แมตช์, และจำนวนหุ้น เพื่ออัปเดตเข้า Portfolio ทันที พร้อมคำนวณ PnL กำไร/ขาดทุนให้แบบ Real-time

---

## ⚙️ Architecture (สถาปัตยกรรมระบบ)

DCA Catcher ถูกรันบนสถาปัตยกรรมแบบ **Stateless & Cloud-Native** เพื่อความเสถียร 100%:

- **Interface:** Telegram App (ติดต่อสื่อสารผ่าน Aiogram 3)
- **AI Engine:** Google Gemini 1.5 Flash / Pro (รองรับ JSON Schema แบบจำกัดโครงสร้างเพื่อความแม่นยำขั้นสุด)
- **Market Data:** yfinance (สำหรับข้อมูลสถิติรายวัน) + Alpaca (สำหรับ Streaming ราคาแบบเรียลไทม์)
- **Compute Server:** Fly.io (รัน Background Task 24/7 พร้อมระบบจัดการ Memory Leak)
- **Database:** Supabase PostgreSQL (เชื่อมต่อแบบ Async ป้องกันปัญหา Database Locked)

---
*Developed by Phonlapat S. (Automated Quant Pipeline)*
