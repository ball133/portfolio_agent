"""Telegram integration for sending portfolio reports."""
import os
from dotenv import load_dotenv
import requests
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

load_dotenv()


def _convert_markdown_to_html(text: str) -> str:
    """Escape reserved HTML characters (except valid <b> tags."""
    # First escape &, then unescape <b> and </b>
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace("&lt;b&gt;", "<b>")
    text = text.replace("&lt;/b&gt;", "</b>")
    return text


def send_telegram_message(text: str) -> dict:
    """
    Send a message to the configured Telegram chat.
    
    Args:
        text: The message text to send
        
    Returns:
        dict with success status and any error message
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {
            "success": False,
            "error": "Telegram credentials not set (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)"
        }
    
    try:
        # Convert to safe HTML for Telegram
        html_text = _convert_markdown_to_html(text)
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": html_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
