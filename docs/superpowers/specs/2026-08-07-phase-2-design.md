# DCA Catcher — Phase 2 Design Specification

> Date: 2026-08-07
> Topic: Phase 2 (Data Scrapers, Indicators, and Smart Notifications)

## 1. Goal
Upgrade the DCA Catcher bot from a basic price-checker into a highly intelligent, silent assistant for busy investors. The bot will deliver deep analytical buy plans (Menu of Choices) in concise, easy-to-understand Thai language.

## 2. Core Philosophy
*   **Assistant, not Broker:** The bot does not ask the user what to do. It provides a detailed, data-backed plan (3 Buy Targets) and gets out of the way.
*   **Concise Thai Language:** All explanations, reasons, and advice must be in Thai, straight to the point, and easy for a busy person to scan.
*   **Silent Monitoring:** The backend monitors stocks every 30 minutes to preserve API quota, but only notifies the user when a stock hits a calculated buy target.

## 3. Architecture & Data Flow

### A. The "Menu of Choices" (Buy Targets)
The AI (`gemini-3.5-flash`) will generate 3 specific buy targets for each stock. These targets are not random percentages; they are calculated based on deep technical and contextual data.
*   Format: `[Price] ([Risk Level / Action in Thai])`
*   Example: `170 (มีความเสี่ยงเล็กน้อย - เริ่มทยอยสะสม)`, `150 (ปลอดภัย - แนวรับหลัก)`

### B. New Data Dimensions (Phase 2 Implementations)
To empower the AI to calculate these targets accurately, we must feed it more data in the prompt:
1.  **PRICE Dimension (Upgraded):**
    *   Current: Drawdown from ATH.
    *   New: Add **RSI (Relative Strength Index)** via the `ta` library to detect mathematically Oversold (<30) or Overbought (>70) conditions.
    *   New: Add **Moving Averages (e.g., 50-day MA)** to detect actual support levels.
2.  **FLOW Dimension:**
    *   Current: Placeholder.
    *   New: Compare the current daily volume against the **20-day Average Volume** to detect sudden buying/selling pressure.
3.  **CONTEXT Dimension:**
    *   Current: Placeholder.
    *   New: Scrape the **CNN Fear & Greed Index** to gauge macro market sentiment.
    *   New: Pull recent headlines via **Google News RSS**.
    *   **NER (Named Entity Recognition) Filter:** Gemini will first verify that the news is *truly* about the target stock (filtering out noise). For true news, it will extract 2-3 key NER entities (e.g., `[iPhone 16]`, `[Interest Rates]`) to include in the Morning Briefing so the user instantly knows *why* the stock is moving.

### C. Quota Management & Fallbacks
*   **Model Tiering:**
    *   `gemini-3.5-flash`: Used for heavy analysis (e.g., the Morning Briefing or manual `/scan`).
    *   `gemini-3.5-flash-lite`: Used for the silent 30-minute background polling (to preserve the 500 RPD quota).
*   **Fallback Logic:** Implemented in `SignalGrader`. If a model hits a 429 Quota limit, it automatically fails over to the next model in the list.

## 4. Smart Notification Triggers & Anti-Spam Logic
1.  **Morning Briefing (09:30 TH / 20:00 US):**
    *   The bot generates a full summary of the watchlist, including overnight news, technical indicators, and the day's Buy Targets.
2.  **Intraday Target Alerts (Event-Driven):**
    *   The bot silently polls prices every 30 minutes.
    *   If the price enters a "Target Zone" (e.g., Target is 180, price enters 181-186), it sends an immediate, concise Thai alert.
3.  **Anti-Spam State Machine (Hysteresis):**
    *   To prevent spamming the user when the price hovers in the same zone for hours, the bot will save the `last_notified_zone` in the database.
    *   If the price stays in the 181-186 zone during the next 30-minute check, the bot sees it already sent the notification and **skips** sending a duplicate.
    *   If the price violently bounces back up to a previous safe zone (e.g., 195-200), the bot resets the state and notifies the user *once* that the price has rebounded.

## 5. Implementation Steps
1.  Implement `ta` library calculations in `DataTransformer` (RSI, MA).
2.  Implement Volume anomaly logic in `DataTransformer`.
3.  Build web scrapers for CNN Fear & Greed and Google News.
4.  Update the Gemini prompt schema to mandate concise Thai summaries.
5.  *(Phase 3)* Build the APScheduler background jobs for 30-minute polling and Morning Briefings.
