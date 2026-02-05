import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME = "Scalping Stock Selector"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GPT_MODEL = os.getenv("GPT_MODEL", "gpt-5-nano")
    
    # Gemini Settings
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite-preview-02-05")
    
    # KIS Settings
    KIS_APP_KEY = os.getenv("KIS_APP_KEY")
    KIS_APP_SECRET = os.getenv("KIS_APP_SECRET")
    KIS_CANO = os.getenv("KIS_CANO")
    KIS_ACCOUNT_NO = os.getenv("KIS_ACCOUNT_NO")
    KIS_ACNT_PRDT_CD = os.getenv("KIS_ACNT_PRDT_CD")
    KIS_BASE_URL = os.getenv("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443")
    
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

settings = Settings()
