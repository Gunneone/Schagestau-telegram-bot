import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # OpenAI
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    OPENAI_TEMPERATURE = float(os.getenv('OPENAI_TEMPERATURE', '0.3'))
    OPENAI_MAX_TOKENS = int(os.getenv('OPENAI_MAX_TOKENS', '2000'))
    
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')
    ADMIN_USER_ID = os.getenv('ADMIN_USER_ID')  # Optional: Telegram user ID for admin notifications
    
    # Tagesschau API
    TAGESSCHAU_API_URL = os.getenv('TAGESSCHAU_API_URL', 'https://www.tagesschau.de/api2u/homepage/')
    
    # Schedule
    FETCH_TIMES = os.getenv('FETCH_TIMES', '08:00,21:00').split(',')
    TIMEZONE = os.getenv('TIMEZONE', 'Europe/Berlin')
    
    # Storage
    LAST_FETCH_FILE = os.getenv('LAST_FETCH_FILE', 'last_fetch.json')
    LOG_FILE = os.getenv('LOG_FILE', 'bot.log')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # News Selection
    NEWS_COUNT = int(os.getenv('NEWS_COUNT', '3'))
    MAX_SUMMARY_SENTENCES = int(os.getenv('MAX_SUMMARY_SENTENCES', '3'))
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        required = [
            ('OPENAI_API_KEY', cls.OPENAI_API_KEY),
            ('TELEGRAM_BOT_TOKEN', cls.TELEGRAM_BOT_TOKEN),
            ('TELEGRAM_CHANNEL_ID', cls.TELEGRAM_CHANNEL_ID),
        ]
        
        missing = [name for name, value in required if not value]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
