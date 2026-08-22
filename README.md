# DCA Catcher (Phase 4) 🚀

DCA Catcher เป็น Telegram Bot พลัง AI (Google Gemini) เสมือน **"ผู้จัดการกองทุนส่วนตัว"** ที่ช่วยดูแล วิเคราะห์ และแนะนำการทยอยซื้อหุ้น (DCA) แบบอัตโนมัติ สำหรับตลาดหุ้นสหรัฐฯ และตลาดหุ้นไทย (ผ่าน `yfinance`)

**สถานะของ Branch นี้:** อยู่ในระหว่าง **Phase 4 (Production Ready & Advanced UX)**


## 🚀 What's New in Phase 4 (พัฒนาต่อยอดจาก Phase 3 อย่างไร?)

ใน Phase 3 เราทำระบบบันทึกฐานข้อมูลและปุ่มโต้ตอบสำเร็จ สำหรับ **Phase 4** นี้ ระบบได้รับการอัปเกรดความสามารถด้าน "Visual Analytics" อย่างก้าวกระโดด:
1. **Candlestick Charting:** ระบบสามารถเจนรูปกราฟแท่งเทียน (Candlestick) ที่มีเส้นเป้าหมาย DCA 3 ไม้พาดทับให้เห็นชัดเจน โดยทำงานบน RAM (In-Memory) ไม่ต้องเซฟไฟล์ลงเครื่อง
2. **Adaptive Timeframe:** กราฟจะปรับขยายช่วงเวลา (Timeframe) อัตโนมัติ เพื่อให้แน่ใจว่าราคาแนวรับในอดีต (Historical Supports) จะถูกแสดงในภาพให้ AI และผู้ใช้เห็นเสมอ
3. **UI Polish:** การส่งข้อมูลวิเคราะห์พร้อมกราฟดูเป็นมืออาชีพและเข้าใจง่ายขึ้น

---

---

## 🌟 ฟีเจอร์สุดล้ำใน Phase 4 (อัปเกรดล่าสุด)

1. **Personalized Stock Matchmaker (`/advice`)** 💡
   - บอทจะสอบถามเป้าหมายการลงทุน, ระยะเวลา, งบประมาณต่อเดือน (Budget)
   - เจาะลึกอุตสาหกรรมด้วย GICS Standard ทั้ง 10 กลุ่ม และหมวดย่อยแบบเจาะลึก
   - ส่งข้อมูลทั้งหมดให้ Gemini AI เพื่อจัด Custom Portfolio หุ้นเด็ดให้โดยเฉพาะ พร้อมประเมินการเติบโตเทียบกับเงินเฟ้อ!
   - ⚡ **New:** หลังจากจัดพอร์ตเสร็จ มีปุ่มคลิกเพิ่มหุ้นทั้งหมดลง Watchlist ได้ทันที

2. **Hybrid Gemini 3 Models & API Rotation** 🧠
   - อัปเกรดไปใช้ SDK ล่าสุด `google-genai` และรองรับ **Gemini 3 Series** (`gemini-3.5-flash`)
   - นำกลยุทธ์ **Hybrid Models** มาใช้: เน้นความเร็ว (Fast Models) สำหรับการสแกนรายวัน และเน้นความฉลาดลึกซึ้ง (Pro Models) สำหรับการจัดพอร์ต
   - 🔄 **API Key Rotation:** รองรับการใส่ API Keys หลายตัวพร้อมกัน หากตัวใดติด Rate Limit/Quota ระบบจะสลับคีย์และวิเคราะห์ต่อทันที (ไม่มีสะดุด!)

3. **Interactive Risk Survey (`/survey`)** 📋
   - แทนที่จะรอราคาตกระดับ 30% แบบแข็งทื่อ ระบบนี้จะให้คุณทำแบบสอบถามหาระดับความเสี่ยง (Risk Profile)
   - AI จะใช้ Risk Profile นี้เพื่อประเมินความเหมาะสมของการซื้อหุ้นให้เข้ากับแต่ละบุคคล
   
4. **AI Score & UX Enhancements** 🎨
   - เปลี่ยนจากการให้เกรด 1-4 ธรรมดา เป็น **AI Score (1-10)** พร้อมกราฟแท่งแบบบล็อก (`█░`) เพื่อความเป็นมืออาชีพและลดอาการค้างจาก Markdown ของ Telegram
   - โชว์หลอดเปรียบเทียบความมั่นใจ (Confidence Score) ของ AI
   
5. **Personalized Daily Broadcast (Smart Group Chat)** 🗣️
   - ระบบตั้งเวลาเตือน (เช้า/เย็น) ไม่ได้แค่ส่งข้อมูลหุ้นเฉยๆ อีกต่อไป! 
   - ระบบจะดึง "Risk Profile" ของแต่ละคนมาวิเคราะห์แยกกัน และแท็กชื่อ (`@username`) พร้อมส่งคำแนะนำที่ตรงกับความเสี่ยงของคนๆ นั้นให้โดยอัตโนมัติ!

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
   # สามารถใส่ API Keys หลายตัวคั่นด้วยลูกน้ำ (,) สำหรับระบบ Rotation ได้
   GEMINI_API_KEYS=your-gemini-key-1,your-gemini-key-2
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

### ☁️ คำแนะนำการ Deploy บน Cloud (ฟรี 24/7)
เพื่อให้บอท Alpaca Sniper สามารถเปิดเฝ้าตลาดหุ้น US ให้คุณได้ตลอดทั้งคืน (20:30 - 04:00 น.) โดยที่คุณไม่ต้องเปิดคอมพิวเตอร์ทิ้งไว้ ขอแนะนำให้นำโปรเจกต์ไปรันบน Cloud Server

**ทางเลือกที่แนะนำ (ฟรีตลอดชีพ): Google Cloud Platform (GCP)**
1. สมัครใช้งาน [Google Cloud Console](https://console.cloud.google.com/)
2. สร้าง VM Instance ใหม่ เลือกสเปค **`e2-micro`** (อยู่ในโควต้า Always Free)
3. เลือก Region เป็น `us-west1`, `us-central1` หรือ `us-east1` เพื่อรับสิทธิ์ใช้ฟรี
4. เลือก OS เป็น Ubuntu
5. SSH เข้าไปใน Server และทำตามขั้นตอนนี้:
   ```bash
   # ติดตั้ง Docker
   sudo apt update && sudo apt install -y docker.io docker-compose
   
   # โคลนโปรเจกต์ (หรือโยนไฟล์ขึ้นไป)
   git clone <your-repo-url>
   cd dca-catcher
   
   # สร้างไฟล์ .env และใส่ค่าให้ครบ
   nano .env 
   
   # สั่งรันบอทให้อยู่ยงคงกระพัน 24/7
   sudo docker-compose up -d
   ```

---

## 📌 โครงสร้างคำสั่ง (Telegram Commands)
เรียงลำดับตาม Priority การใช้งานที่แนะนำ:
- `/survey` - ทำแบบประเมินความเสี่ยงเพื่อปรับแต่ง AI (📝 ควรทำก่อน!)
- `/advice` - ให้ AI จัดพอร์ตและแนะนำหุ้น (🌟 ไฮไลต์!)
- `/add <symbol> [market]` - เพิ่มหุ้นลง Watchlist (เช่น `/add NVDA US`)
- `/list` - ดูรายชื่อหุ้นที่ติดตามอยู่
- `/scan [symbol]` - สั่งสแกนหุ้นแบบ Manual ทันที (บอทจะแท็กชื่อคุณด้วย!)
- `/remove <symbol>` - ลบหุ้น
- `/help` - ดูคำสั่งทั้งหมด
- `/start` - เริ่มต้นใช้งาน
