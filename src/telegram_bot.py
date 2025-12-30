import asyncio
from telegram import Bot
from telegram.error import TelegramError
from src.config import Config
from src.utils import format_timestamp
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TelegramPublisher:
    """Publishes news digests to Telegram channel"""
    
    def __init__(self):
        self.bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)
        self.channel_id = Config.TELEGRAM_CHANNEL_ID
    
    def format_digest(self, articles, summaries, timestamp):
        """
        Format the news digest for Telegram
        
        Args:
            articles: List of article dictionaries
            summaries: List of summary strings
            timestamp: datetime of digest creation
            
        Returns:
            str: Formatted message
        """
        # Determine if morning or evening news based on hour
        hour = timestamp.hour
        if hour < 14:
            time_of_day = "Morgen"
            emoji = "☕"
        else:
            time_of_day = "Abend"
            emoji = "🍷"
        formatted_date = timestamp.strftime('%d.%m.%Y')
        
        # Header with greeting
        message = f"Guten {time_of_day}. Hier sind die News vom *{formatted_date}*. {emoji}\n\n"
        
        # Headlines separated by | (make them bold)
        headlines = [f"*{article.get('title', 'Ohne Titel')}*" for article in articles]
        message += ' | '.join(headlines) + "\n\n"
        
        # Separator
        message += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Individual articles with summaries
        for idx, (article, summary) in enumerate(zip(articles, summaries)):
            url = article.get('shareURL') or article.get('detailsweb', '')
            
            # Remove any internal line breaks from summary
            summary = summary.replace('\n', ' ').strip()
            
            # Make first sentence bold
            sentences = summary.split('. ', 1)
            if len(sentences) > 1:
                formatted_summary = f"*{sentences[0]}.* {sentences[1]}"
            else:
                formatted_summary = f"*{summary}*"
            
            message += f"🔵 {formatted_summary}\n"
            if url:
                message += f"{url}\n"
            
            # Add spacing between articles (but not after the last one)
            if idx < len(articles) - 1:
                message += "\n"
        
        return message
    
    async def send_digest_async(self, articles, summaries, timestamp):
        """
        Send digest to Telegram channel (async)
        
        Args:
            articles: List of article dictionaries
            summaries: List of summary strings
            timestamp: datetime of digest creation
            
        Returns:
            bool: True if successful, False otherwise
        """
        message = self.format_digest(articles, summaries, timestamp)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Sending digest to Telegram channel {self.channel_id} (attempt {attempt + 1}/{max_retries})")
                
                await self.bot.send_message(
                    chat_id=self.channel_id,
                    text=message,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
                
                logger.info("Successfully sent digest to Telegram")
                return True
                
            except TelegramError as e:
                logger.error(f"Telegram error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(5 * (attempt + 1))  # Exponential backoff
                else:
                    logger.error("Failed to send digest after all retries")
                    return False
            except Exception as e:
                logger.error(f"Unexpected error sending to Telegram: {e}")
                return False
        
        return False
    
    def send_digest(self, articles, summaries, timestamp=None):
        """
        Send digest to Telegram channel (sync wrapper)
        
        Args:
            articles: List of article dictionaries
            summaries: List of summary strings
            timestamp: datetime of digest creation
            
        Returns:
            bool: True if successful, False otherwise
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Run async function in event loop
        return asyncio.run(self.send_digest_async(articles, summaries, timestamp))
