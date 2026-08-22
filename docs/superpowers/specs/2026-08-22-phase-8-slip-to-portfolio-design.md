# Phase 8: Slip-to-Portfolio Tracker Design Spec

## 1. Executive Summary
Phase 8 introduces a **Slip-to-Portfolio Tracker** focused exclusively on the US Market. The system allows users to seamlessly track their DCA average costs by simply uploading a screenshot of their trade execution slip (optimized for the **Dime** app, but flexible enough for others). The system relies on Gemini Multimodal AI for OCR and data extraction, maintaining an accurate forward-looking portfolio ledger without requiring manual data entry.

## 2. Core Features
1. **Multimodal Slip OCR (Vision Extraction):** 
   - Users send a photo of their trade execution receipt.
   - The bot forwards the image to Gemini (Multimodal) to extract structured JSON data (Symbol, Buy/Sell, Execution Price, Shares).
   - *Constraint:* The prompt is strictly optimized for US Stocks and USD currency.
2. **Fast Interactive Confirmation (1-Click):**
   - The bot replies with the extracted data and a simple confirmation inline keyboard (`[✅ ยืนยันบันทึก]`, `[❌ ยกเลิก]`).
   - If incorrect, the user cancels and retries (no complex inline editing).
3. **Forward-Looking Ledger (Supabase):**
   - Stores transactions in `portfolio_transactions`.
   - *Constraint:* No manual `/setport` command is provided. The portfolio builds organically purely from uploaded slips moving forward.
4. **Portfolio Analytics Command (`/portfolio`):**
   - Generates a real-time summary comparing the user's Average Cost against live market prices (via `yfinance`).
   - Displays Unrealized PnL (%) for active holdings.

## 3. Technical Architecture

### 3.1 Telegram Handlers
- Add a new handler in `bot.py` using `F.photo` to catch image uploads.
- Download the highest resolution photo (`bot.download(photo[-1])`) into memory (`io.BytesIO`).
- Pass image bytes directly to the Vision Agent.

### 3.2 Vision Agent (`slip_parser.py`)
- Model: `gemini-3.6-flash` (or equivalent multimodal endpoint).
- Instruction: "You are a financial OCR agent specializing in Thai broker apps like Dime. Read this US stock trade slip. Extract the ticker, action (BUY/SELL), execution price in USD, and volume. Output strict JSON."
- Output Schema:
  ```json
  {
    "symbol": "NVDA",
    "action": "BUY",
    "price": 115.50,
    "volume": 5.0
  }
  ```

### 3.3 Database Schema Updates (`models.py` / `database.py`)
```python
class PortfolioTransaction(Base):
    __tablename__ = "portfolio_transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    action: Mapped[str] = mapped_column(String)  # 'BUY' or 'SELL'
    price: Mapped[float] = mapped_column(Float)
    shares: Mapped[float] = mapped_column(Float)
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
```

### 3.4 Edge Cases & Error Handling
- **Non-Slip Images:** If the user uploads a picture of a cat, the AI returns an empty/invalid schema. The bot catches this and replies: "❌ ไม่พบข้อมูลการซื้อขายหุ้นในรูปนี้ครับ".
- **Database Locks:** Uses `asyncpg` existing transaction pool, ensuring concurrent slip uploads don't block the UI.

## 4. Implementation Phasing
1. **Data Layer:** Create `PortfolioTransaction` model and run Supabase schema updates.
2. **AI Layer:** Develop the Vision Agent (`slip_parser.py`) and test it with a sample Dime slip.
3. **UI Layer:** Implement Telegram `F.photo` handlers and the Fast Confirm FSM.
4. **Analytics Layer:** Build the `/portfolio` command calculation logic.
