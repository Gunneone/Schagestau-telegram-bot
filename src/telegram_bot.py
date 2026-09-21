import asyncio
from telegram import Bot
from telegram.error import TelegramError
from src.config import Config
from src.utils import format_timestamp
from datetime import datetime
import logging
import re

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
        # Use improved title if available, otherwise use original
        headlines = [f"*{article.get('improved_title', article.get('title', 'Ohne Titel'))}*" for article in articles]
        message += ' | '.join(headlines) + "\n\n"
        
        # Separator
        message += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Individual articles with summaries
        for idx, (article, summary) in enumerate(zip(articles, summaries)):
            url = article.get('shareURL') or article.get('detailsweb', '')
            
            # Remove any internal line breaks from summary and normalize spaces
            summary = summary.replace('\n', ' ')
            summary = re.sub(r'\s+', ' ', summary).strip()
            
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
    
    async def send_admin_overview_async(self, all_articles, top_articles, timestamp,
                                        topic_map=None):
        """
        Send article overview to admin user
        
        Args:
            all_articles: List of all article dictionaries in timeframe
            top_articles: List of top ranked article dictionaries
            timestamp: datetime of digest creation
            topic_map: Optional {sophoraId: {'topic': slug, 'status': ...}} from
                       the ranker, used to show topics and duplicates
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not Config.ADMIN_USER_ID:
            logger.info("No ADMIN_USER_ID configured, skipping admin overview")
            return True
        
        try:
            admin_user_id = int(Config.ADMIN_USER_ID)
        except (ValueError, TypeError):
            logger.warning(f"Invalid ADMIN_USER_ID: {Config.ADMIN_USER_ID}")
            return False
        
        # Format overview message
        hour = timestamp.hour
        time_of_day = "Morgen" if hour < 14 else "Abend"
        formatted_date = timestamp.strftime('%d.%m.%Y')
        formatted_time = timestamp.strftime('%H:%M')
        
        # Calculate time filter - articles are from last fetch to now
        from src.storage import Storage
        last_fetch = Storage.get_last_fetch_time()
        if last_fetch:
            time_filter_start = last_fetch.strftime('%H:%M')
        else:
            time_filter_start = "N/A"
        
        message = f"📊 *Artikel-Übersicht {time_of_day} ({formatted_date})*\n\n"
        message += f"⏰ Zeitfilter: {time_filter_start} - {formatted_time}\n"
        message += f"📰 Insgesamt {len(all_articles)} Artikel gefunden\n"
        message += f"✅ Top {len(top_articles)} ausgewählt für den Digest\n"
        if topic_map:
            message += "🔁 = gleiches Thema wie ein bereits gewählter Artikel\n"
        if any(a.get('carried_over') for a in all_articles):
            message += "♻️ = Übertrag aus einem früheren Lauf\n"
        message += "\n"
        
        # List all articles with time and URL
        message += "━━━━━━━━━━━━━━━━━━━━━━\n"
        message += "*Alle Artikel:*\n\n"
        
        top_article_ids = [a.get('sophoraId') for a in top_articles]
        
        for idx, article in enumerate(all_articles, 1):
            article_id = article.get('sophoraId')
            title = article.get('title', 'Ohne Titel')
            article_date_str = article.get('date', '')
            url = article.get('shareURL') or article.get('detailsweb', '')
            
            # Parse and format time
            try:
                article_date = datetime.fromisoformat(article_date_str.replace('Z', '+00:00'))
                time_str = article_date.strftime('%H:%M')
            except:
                time_str = "??"
            
            # Mark selected articles with ✅, topic duplicates with 🔁
            topic_info = (topic_map or {}).get(article_id) or {}
            if article_id in top_article_ids:
                marker = "✅"
            elif topic_info.get('status') == 'dropped':
                marker = "🔁"
            else:
                marker = "  "
            
            carried = " ♻️" if article.get('carried_over') else ""
            
            message += f"{marker} `{time_str}` {title}{carried}\n"
            if topic_info.get('topic'):
                message += f"   _{topic_info['topic']}_\n"
            if url:
                message += f"   {url}\n"
            message += "\n"
        
        # Send message
        try:
            logger.info(f"Sending article overview to admin user {admin_user_id}")
            await self.bot.send_message(
                chat_id=admin_user_id,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            logger.info("Successfully sent overview to admin")
            return True
        except TelegramError as e:
            logger.error(f"Telegram error sending admin overview: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending admin overview: {e}")
            return False
    
    def send_admin_overview(self, all_articles, top_articles, timestamp=None,
                            topic_map=None):
        """
        Send article overview to admin (sync wrapper)
        
        Args:
            all_articles: List of all article dictionaries in timeframe
            top_articles: List of top ranked article dictionaries
            timestamp: datetime of digest creation
            topic_map: Optional topic/status map from the ranker
            
        Returns:
            bool: True if successful, False otherwise
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        return asyncio.run(self.send_admin_overview_async(
            all_articles, top_articles, timestamp, topic_map
        ))
    
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
