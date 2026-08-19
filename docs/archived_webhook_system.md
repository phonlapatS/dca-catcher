# 📦 บันทึกสถาปัตยกรรมและเหตุผลการถอดระบบ Webhook (Archived Webhook System Documentation)

**วันที่บันทึก:** 2026-08-20  
**สถานะ:** ปลดระวางชั่วคราว (Archived & Removed from Active Runtime)  
**เหตุผลหลัก:** ไม่สอดคล้องกับปรัชญาและกลุ่มผู้ใช้หลักของ DCA Catcher (Paywall Constraint)

---

## 🎯 1. ทำไมถึงตัดสินใจถอดระบบ Webhook ออก? (Rationale & Motivation)

### ❌ ปัญหาและข้อจำกัดที่พบ (Key Constraints):
1. **ติด Paywall ของ TradingView (ต้องจ่ายเงินรายเดือน):**
   * ทาง TradingView บังคับให้ผู้ใช้ต้องสมัครสมาชิกแบบเสียเงิน (**TradingView Essential / Plus / Premium** ราคา ~$15 – $60 USD ต่อเดือน หรือราว 500 – 2,000 บาท/เดือน) จึงจะสามารถกรอก **Webhook URL** ได้ บัญชี Free Plan ไม่สามารถส่ง Webhook ออกมาได้
2. **ขัดแย้งกับปรัชญาของโปรเจกต์ DCA Catcher (100% Free & Accessible):**
   * โปรเจกต์ DCA Catcher ถูกสร้างขึ้นเพื่อให้นักลงทุนรายย่อยเข้าถึงระบบช่วยสะสมหุ้น DCA แบบอัตโนมัติ **โดยไม่มีค่าใช้จ่ายแอบแฝง (Zero Cost Stack)**
   * ระบบหลักของเราเลือกใช้ **Alpaca Real-time WebSocket (ฟรี)** + **yfinance (ฟรี)** + **Google Gemini Free Tier** + **Telegram Bot API (ฟรี)** อยู่แล้ว
3. **ลดความยุ่งยากของผู้ใช้ (User Experience Friction):**
   * การใช้ Webhook บังคับให้ผู้ใช้ต้องมีความรู้ในการเปิดหน้ากราฟ TradingView, เขียน Pine Script หรือตั้งค่า Alert ทีละตัวด้วยตัวเอง
   * ในขณะที่ระบบ In-House ของเรา ผู้ใช้แค่พิมพ์คำสั่งใน Telegram เช่น `/scan NVDA` แล้วกดปุ่ม `[✓]` เพื่อเลือกราคาเป้าหมาย บอทจะเฝ้าราคาและแจ้งเตือนให้ทันทีจากในระบบ

---

## 🏛️ 2. สิ่งที่เคยพัฒนาไว้และโครงสร้างการทำงาน (What Was Built)

ระบบ Webhook ที่พัฒนาไว้เป็นระบบ **Asynchronous HTTP Server คุณภาพสูง** ที่มีคุณสมบัติดังนี้:

### สถาปัตยกรรม:
* **โมดูล:** `src/webhook.py` (ใช้ `aiohttp.web`)
* **Endpoint:** `POST /webhook/{secret}`
* **ความเร็วในการตอบสนอง (Latency):** ตอบกลับ `HTTP 200 OK` ภายใน **<0.05 วินาที** เพื่อให้สอดคล้องกับ Timeout Limit (3 วินาที) ของ TradingView
* **Background Task Dispatching:** โยนงานวิเคราะห์ข้อมูลตลาด (Fetching), การให้คะแนน AI (Grading), และการวาดกราฟ (Charting) เข้าสู่ `asyncio.create_task` เพื่อไม่ให้บล็อกการรับ Request ถัดไป
* **Symbol Normalization:** รองรับการตัดคำนำหน้า Exchange อัตโนมัติ (เช่น `NASDAQ:NVDA` ➔ `NVDA`, `SET:PTT` ➔ `PTT.BK`)

### ตัวอย่างโค้ดระบบ `WebhookServer` เดิมที่เคยทำงาน:
```python
class WebhookServer:
    def __init__(self, config, pipeline, bot, broadcast_channel_id):
        self.config = config
        self.pipeline = pipeline
        self.bot = bot
        self.broadcast_channel_id = broadcast_channel_id

    async def handle_webhook(self, request: web.Request):
        secret = request.match_info.get('secret')
        if secret != self.config.webhook_secret:
            return web.Response(status=403, text="Forbidden")

        try:
            data = await request.json()
            raw_symbol = data.get("symbol") or data.get("ticker") or data.get("sym")
            message = data.get("message") or data.get("action") or "TradingView Signal"
            
            if not raw_symbol:
                return web.Response(status=400, text="Missing symbol")

            symbol = str(raw_symbol).split(":")[-1].upper()
            asyncio.create_task(self.process_alert(symbol, message))
            return web.Response(status=200, text="OK")
        except Exception:
            return web.Response(status=400, text="Bad Request")
```

### ตัวอย่างโค้ด TradingView Pine Script v5 ที่เคยเตรียมไว้:
```pinescript
//@version=5
indicator("DCA Catcher Webhook Trigger", overlay=true)
rsi_length = input.int(14, "RSI Length")
rsi_oversold = input.int(30, "RSI Oversold Level")
current_rsi = ta.rsi(close, rsi_length)

dca_trigger = ta.crossunder(current_rsi, rsi_oversold) // Crossing Down

if dca_trigger
    alert('{"ticker": "' + syminfo.ticker + '", "action": "RSI Oversold Dip (<30)", "price": ' + str.tostring(close) + '}', alert.freq_once_per_bar_close)
```

---

## 🔄 3. แนวทางหากต้องการนำกลับมาเปิดใช้งานในอนาคต (How to Re-enable in the Future)

หากในอนาคตมี Use Case ที่ต้องการเปิดระบบ Webhook สำหรับผู้ใช้ Premium หรือสำหรับเชื่อมต่อกับระบบภายนอกอื่น (เช่น Custom Alert Server, Python Algo Bot อื่นๆ):

1. กู้คืนไฟล์ `src/webhook.py` จากบันทึกนี้ หรือจาก Git Commit `2d823f3`
2. ใน `src/bot.py` ฟังก์ชัน `main()` ให้เชื่อมต่อ `WebhookServer` เข้ากับ `aiohttp.web.Application`
3. ตั้งค่า `WEBHOOK_PORT=8080` และ `WEBHOOK_SECRET` ใน `.env`
4. ทำการทดสอบผ่านชุดทดสอบ `tests/test_webhook.py`
