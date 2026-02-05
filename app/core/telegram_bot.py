import requests
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_message(self, text: str):
        """
        Send a text message to the configured Telegram chat.
        """
        if not self.token or not self.chat_id:
            logger.warning("Telegram token or chat_id is missing. Skipping notification.")
            return

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text
            # "parse_mode": "Markdown" # Removed to avoid error with special chars
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                logger.error(f"Failed to send Telegram message: {response.text}")
            else:
                logger.debug("Telegram message sent successfully.")
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")

bot = TelegramBot()
