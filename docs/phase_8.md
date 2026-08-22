# Phase 8: Slip-to-Portfolio Tracker

## 🎯 Overview
ระบบติดตามพอร์ตการลงทุน (Portfolio Tracking) ผ่านการสแกนสลิปซื้อขายด้วย AI โดยผู้ใช้ไม่จำเป็นต้องพิมพ์ข้อมูลหุ้น ราคา หรือจำนวนหุ้นเอง เพียงแค่ส่งภาพสลิปจากแอปเทรด (เช่น Dime, Streaming) ให้กับบอท ระบบจะใช้ Vision AI อ่านค่าและบันทึกลงฐานข้อมูลให้อัตโนมัติ พร้อมแสดงผลกำไร/ขาดทุน (PnL) แบบ Real-time ผ่านคำสั่ง `/portfolio`

## ✨ Key Features
1. **Gemini Vision Extraction (`src/slip_parser.py`)**
   - ประมวลผลภาพสลิปเพื่อดึงข้อมูลสำคัญ: หุ้น (Symbol), ฝั่ง (BUY/SELL), ราคา (Price), ปริมาณ (Volume)
   - รองรับภาษาไทยและภาษาอังกฤษ (เช่น แปลงคำว่า "ซื้อ" เป็น "BUY")
   - มีระบบ Fallback ไปยังโมเดลตัวรองหากโมเดลหลักติด Rate Limit (ควบคุมโดย `PipelineConfig`)

2. **Interactive Confirmation (FSM Handlers)**
   - สรุปยอดรวม (Total Value) และแสดงผลให้ผู้ใช้ตรวจสอบความถูกต้องก่อนบันทึกลงระบบ
   - UI ปุ่มกด `[✅ ยืนยันบันทึก]` หรือ `[❌ ยกเลิก]`

3. **Real-time Portfolio PnL (`/portfolio`)**
   - จัดกลุ่มการซื้อขายตามรายชื่อหุ้นเพื่อคำนวณ "ต้นทุนเฉลี่ย" (Average Cost) และ "จำนวนหุ้นรวม"
   - ดึงราคาตลาดล่าสุดผ่าน `yfinance` มาประเมินร่วมกับต้นทุน เพื่อแสดงผลกำไร/ขาดทุนแบบ % (Realized/Unrealized PnL)
   - จัดรูปแบบการแสดงผลแบบตารางผ่าน Markdown ที่อ่านง่าย

## 🛠️ Architecture & Implementation
- **AI Model:** ใช้ `google-genai` SDK ในการเรียกใช้โมเดล (แนะนำ: `gemini-3.5-flash` หรือตามที่กำหนดใน `PipelineConfig.smart_models`)
- **Database (`PortfolioTransaction`):** เก็บประวัติการทำธุรกรรมทั้งหมดแยกตาม User ID โดยผูกกับ SQLAlchemy
- **Integration:** เพิ่ม Handler ตรวจจับ `F.photo` ใน `bot.py` โดยทำงานสอดประสานกับ `GeminiSlipParser` อย่างไร้รอยต่อ

## 🚧 Known Limitations (ที่ควรพัฒนาต่อ)
- **Rate Limits:** หากส่งสลิปพร้อมกันจำนวนมาก อาจเกิดการหน่วงจากการติดต่อ API ของ Google (ปรับแก้โดยใช้ Bulk Processing ในอนาคต)
- **Sell Logic:** การคำนวณบัญชีสำหรับฝั่งขาย (SELL) ยังใช้วิธีหักลบจำนวนหุ้นง่ายๆ (Simple Subtraction) ซึ่งเหมาะกับการทำ DCA มากกว่า Day Trade
