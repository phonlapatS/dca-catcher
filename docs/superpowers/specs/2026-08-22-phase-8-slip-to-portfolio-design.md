# Phase 8: Slip-to-Portfolio Tracker Design Spec

## 1. Executive Summary
Phase 8 introduces a **Slip-to-Portfolio Tracker** focused exclusively on the US Market. It aligns with the user's preference to maintain manual trade execution (no auto-trading) while automating the tedious process of tracking average costs. Users will upload screenshots of their trade slips (e.g., from Dime, InnovestX), and the system's Multimodal AI will extract the data, maintain a ledger, and provide real-time portfolio PnL tracking.

## 2. Core Features
1. **Multimodal Slip OCR (Vision Extraction):** 
   - Users send a photo of their trade execution receipt.
   - The bot forwards the image to Gemini (Multimodal) to extract structured JSON data (Symbol, Buy/Sell, Execution Price, Shares).
2. **Interactive Ledger Confirmation:**
   - The bot replies with the extracted data and a confirmation inline keyboard (`[✅ Confirm]`, `[❌ Cancel]`).
3. **Database Integration (Supabase):**
   - New `portfolio_transactions` table to store atomic trades.
   - Aggregate view to calculate total holdings and Average Cost (DCA Cost) per symbol.
4. **Portfolio Analytics Command (`/portfolio`):**
   - Generates a real-time summary comparing the user's Average Cost against live market prices (via `yfinance`).
   - Displays Unrealized PnL (%) and dynamically integrates with the existing Catalyst AI to suggest next DCA steps based on actual cost basis.

## 3. Technical Architecture

### 3.1 Telegram Handlers
- Add a new handler for `content_types=[ContentType.PHOTO]` in `bot.py`.
- Download the highest resolution photo using `bot.download(photo[-1])`.
- Pass image bytes to the Vision Agent.

### 3.2 Vision Agent (Prompt Engineering)
- Model: `gemini-3.6-flash` (supports fast multimodal inference).
- Instruction: "You are a financial OCR agent. Read this trade slip. Extract the US stock ticker, execution price, and volume. Output strict JSON."
- Output Schema:
  ```json
  {
    "symbol": "NVDA",
    "action": "BUY",
    "price": 115.50,
    "volume": 5.0
  }
  ```

### 3.3 Database Schema Updates
```python
class PortfolioTransaction(Base):
    __tablename__ = "portfolio_transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    action: Mapped[str] = mapped_column(String)  # 'BUY' or 'SELL'
    price: Mapped[float] = mapped_column(Float)
    shares: Mapped[float] = mapped_column(Float)
    transaction_date: Mapped[datetime] = mapped_column(DateTime, default=func.now())
```

### 3.4 Concurrency & Edge Cases
- **Wrong Image:** If the image is not a trade slip, the Vision Agent must gracefully return an empty/error schema, and the bot will reply: "ไม่พบข้อมูลการซื้อขายในภาพนี้ครับ".
- **Currency:** Ensure the prompt forces USD parsing for US stocks to prevent parsing THB total amounts as execution prices.

## 4. Rollout Strategy
1. **Task 1:** Create `PortfolioTransaction` model and apply Supabase migration.
2. **Task 2:** Develop the Vision Agent (`slip_parser.py`) using Google GenAI SDK.
3. **Task 3:** Implement Telegram `F.photo` handlers and FSM confirmation flow.
4. **Task 4:** Build the `/portfolio` command to calculate Average Cost and live PnL.
