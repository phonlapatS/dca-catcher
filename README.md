# DCA Catcher (Phase 4) 🚀

DCA Catcher เป็น Telegram Bot พลัง AI (Google Gemini) เสมือน **"ผู้จัดการกองทุนส่วนตัว"** ที่ช่วยดูแล วิเคราะห์ และแนะนำการทยอยซื้อหุ้น (DCA) แบบอัตโนมัติ สำหรับตลาดหุ้นสหรัฐฯ และตลาดหุ้นไทย (ผ่าน `yfinance`)

**สถานะของ Branch นี้:** อยู่ในระหว่าง **Phase 4 (Production Ready & Advanced UX)**

---

## 🌟 ฟีเจอร์สุดล้ำใน Phase 4 (อัปเกรดจาก Phase 3)

1. **Personalized Stock Matchmaker (`/advice`)** 💡
   - บอทจะสอบถามเป้าหมายการลงทุน, ระยะเวลา, งบประมาณต่อเดือน (Budget)
   - เจาะลึกอุตสาหกรรมด้วย GICS Standard ทั้ง 10 กลุ่ม และหมวดย่อยแบบเจาะลึก
   - ส่งข้อมูลทั้งหมดให้ Gemini AI เพื่อจัด Custom Portfolio หุ้นเด็ดให้โดยเฉพาะ พร้อมประเมินการเติบโตเทียบกับเงินเฟ้อ!
   
2. **Interactive Risk Survey (`/survey`)** 📋
   - แทนที่จะรอราคาตกระดับ 30% แบบแข็งทื่อ ระบบนี้จะให้คุณทำแบบสอบถามหาระดับความเสี่ยง (Risk Profile) สไตล์ธนาคาร (เช่น 1-10%, 11-30%)
   - AI จะใช้ Risk Profile นี้เพื่อประเมินความเหมาะสมของการซื้อหุ้นให้เข้ากับแต่ละบุคคล
   
3. **AI Score & UX Enhancements** 🎨
   - เปลี่ยนจากการให้เกรด 1-4 ธรรมดา เป็น **AI Score (1-10)** พร้อมกราฟแท่งแบบบล็อก (`█░`) เพื่อความเป็นมืออาชีพ
   - โชว์หลอดเปรียบเทียบความมั่นใจ (Confidence Score) ของ AI
   
4. **Personalized Daily Broadcast (Smart Group Chat)** 🗣️
   - ระบบตั้งเวลาเตือน (เช้า/เย็น) ไม่ได้แค่ส่งข้อมูลหุ้นเฉยๆ อีกต่อไป! 
   - ระบบจะเช็กว่าผู้ใช้คนไหนเพิ่มหุ้นตัวนี้ใน Watchlist บ้าง และดึง "Risk Profile" ของแต่ละคนมาวิเคราะห์แยกกัน 
   - จากนั้นบอทจะแท็กชื่อ (`@username`) พร้อมส่งคำแนะนำที่ตรงกับโปรไฟล์ความเสี่ยงของคนๆ นั้นให้โดยอัตโนมัติ!

5. **Security & Management** 🛡️
   - ลบคำสั่งจัดการคีย์ที่ไม่ปลอดภัยออก
   - สรุปรวมคำสั่งทั้งหมดไว้ที่ `/help`

---

## 🛠️ วิธีติดตั้งและรันโปรแกรม (Phase 4)

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
- `/start` - เริ่มต้นใช้งาน
- `/help` - ดูคำสั่งทั้งหมด
- `/advice` - ให้ AI จัดพอร์ตและแนะนำหุ้น (🌟 ไฮไลต์!)
- `/survey` - ทำแบบประเมินความเสี่ยงเพื่อปรับแต่ง AI
- `/add <symbol> [market]` - เพิ่มหุ้น (เช่น `/add NVDA US`)
- `/remove <symbol>` - ลบหุ้น
- `/list` - ดูรายชื่อหุ้นที่ติดตามอยู่
- `/scan [symbol]` - สั่งสแกนหุ้นแบบ Manual ทันที (บอทจะแท็กชื่อคุณด้วย!)
