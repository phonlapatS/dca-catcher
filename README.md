# DCA Catcher (Phase 3) 🚀

DCA Catcher เป็น Telegram Bot พลัง AI (Google Gemini) ที่ช่วยให้คำแนะนำในการทยอยซื้อหุ้น (DCA) สำหรับตลาดหุ้นสหรัฐฯ และตลาดหุ้นไทย (ผ่าน `yfinance`) 

**สถานะของ Branch นี้:** สิ้นสุดที่ **Phase 3 (Deployment & Schedulers)**

---

## 🌟 ฟีเจอร์ที่ทำงานได้ใน Phase 3
1. **เพิ่มและลบหุ้นใน Watchlist:** จัดการพอร์ตติดตามหุ้นของคุณผ่าน Telegram Command
2. **ระบบสแกนหุ้นด้วย AI:** พิมพ์ `/scan` เพื่อให้ระบบนำข้อมูลราคา (Drawdown) ไปบวกกับปัจจัยอื่นๆ แล้วส่งให้ Gemini สรุปว่าหุ้นน่าซื้อหรือไม่ โดยออกเกรดให้ 1-4 (🔴, 🟡, 🟢, 🌟)
3. **แจ้งเตือนกลุ่ม (Daily Broadcast):** 
   - ตั้งเวลาส่งข้อความอัตโนมัติ (APScheduler) เข้า Channel ทุกเช้า (07:00), สาย (09:30), และค่ำ (20:00) 
   - ระบบจะรวบรวมหุ้นทั้งหมดที่ผู้ใช้งานทุกคนติดตาม (Unique Symbols) มาสแกนรวมกัน เพื่อประหยัด API Quota!
4. **Interactive Keyboard (Deep Linking):** ใน Channel จะมีปุ่ม `[+ Add to Watchlist]` ใต้หุ้นทุกตัว เมื่อกดแล้วจะเปิดบอทพร้อมเพิ่มหุ้นตัวนั้นให้ทันที
5. **Docker Ready:** รองรับการรันผ่าน Docker และ `docker-compose` ได้ทันที

---

## 🛠️ วิธีติดตั้งและรันโปรแกรม (Phase 3)

### แบบรันตรงด้วย Python (Local)
1. ติดตั้ง Packages:
   ```bash
   pip install -r requirements.txt
   ```
2. ตั้งค่า Environment Variables (สร้างไฟล์ `.env`):
   ```env
   TELEGRAM_TOKEN=your-bot-token
   GEMINI_API_KEY=your-gemini-key
   DATABASE_URL=sqlite+aiosqlite:///dca_catcher.db
   BROADCAST_CHANNEL_ID=-100xxxxxxxxxx
   ```
3. รันโปรแกรม:
   ```bash
   python -m src.bot
   ```

### แบบรันด้วย Docker (Production)
```bash
docker-compose up -d --build
```

---

## 📌 โครงสร้างคำสั่ง (Telegram Commands)
- `/start` - แสดงข้อความต้อนรับและวิธีใช้งาน
- `/add <symbol> [market]` - เพิ่มหุ้น (เช่น `/add NVDA US`)
- `/remove <symbol>` - ลบหุ้น
- `/list` - ดูรายชื่อหุ้นที่ติดตามอยู่
- `/scan [symbol]` - สั่งสแกนหุ้นแบบ Manual ทันที
