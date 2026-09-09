import traceback
import logging
import asyncio
from typing import Optional
from aiogram import Bot

logger = logging.getLogger(__name__)

class AdminAlertManager:
    ADMIN_CHAT_ID = 8942457900

    @staticmethod
    async def send_alert(bot: Bot, gemini_api_key: str, error: Exception, context: str):
        """Send LLM-analyzed error alert directly to Admin."""
        try:
            tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            error_type = type(error).__name__
            
            ai_analysis = "ไม่สามารถวิเคราะห์ได้ในขณะนี้"
            if gemini_api_key:
                from google import genai
                try:
                    client = genai.Client(api_key=gemini_api_key)
                    prompt = f"""
You are an expert Python Backend Developer monitoring a DCA Trading Bot.
A background task crashed.
Context: {context}
Error Type: {error_type}
Traceback:
{tb_str[-2000:]}

Please explain this error in simple, highly technical Thai for the admin. Explain exactly what went wrong and how to fix it in 2-3 short, clear sentences. Do not use markdown backticks in your response.
"""
                    response = await asyncio.to_thread(client.models.generate_content, model='gemini-3.5-flash', contents=prompt)
                    if response.text:
                        ai_analysis = response.text.strip()
                except Exception as llm_e:
                    logger.error(f"LLM Alert generation failed: {llm_e}")

            msg = (
                f"🚨 **ADMIN ALERT (Background Watchdog)** 🚨\n"
                f"**โมดูล:** `{context}`\n"
                f"**Error:** `{error_type}`\n"
                f"**Details:** `{str(error)[:300]}`\n\n"
                f"🤖 **AI Analysis:**\n{ai_analysis}"
            )
            
            await bot.send_message(chat_id=AdminAlertManager.ADMIN_CHAT_ID, text=msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to send Admin Alert: {e}", exc_info=True)
