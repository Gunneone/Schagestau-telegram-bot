import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime, timedelta
import pytz
import logging

from src.config import Config
from src.fetcher import NewsFetcher
from src.ranker import NewsRanker
from src.summarizer import NewsSummarizer
from src.telegram_bot import TelegramPublisher

logger = logging.getLogger(__name__)

# Authorized users (username without @)
AUTHORIZED_USERS = ['Gunneone']


class CommandListener:
    """Listens for bot commands from authorized users"""
    
    def __init__(self):
        self.application = None
        self.digest_callback = None
    
    async def fire_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /fire command - manually trigger news digest for last 12 hours
        
        Only authorized users can trigger this command
        """
        user = update.effective_user
        username = user.username
        
        logger.info(f"Received /fire command from user: {username} (ID: {user.id})")
        
        # Check authorization
        if username not in AUTHORIZED_USERS:
            logger.warning(f"Unauthorized user {username} tried to use /fire command")
            await update.message.reply_text(
                "⛔ Du bist nicht autorisiert, diesen Befehl zu verwenden."
            )
            return
        
        logger.info(f"Authorized user {username} triggered manual digest")
        
        # Send acknowledgment
        await update.message.reply_text(
            "🔥 Nachrichten-Digest wird erstellt...\n"
            "Hole Nachrichten der letzten 12 Stunden..."
        )
        
        try:
            # Calculate time 12 hours ago
            tz = pytz.timezone(Config.TIMEZONE)
            now = datetime.now(tz)
            twenty_four_hours_ago = now - timedelta(hours=12)
            
            logger.info(f"Fetching news since {twenty_four_hours_ago}")
            
            # Fetch news
            fetcher = NewsFetcher()
            articles = fetcher.fetch_news(since=twenty_four_hours_ago)
            
            if not articles:
                logger.info("No articles found in last 12 hours")
                await update.message.reply_text(
                    "ℹ️ Keine neuen Artikel in den letzten 12 Stunden gefunden."
                )
                return
            
            logger.info(f"Found {len(articles)} articles")
            await update.message.reply_text(
                f"📊 {len(articles)} Artikel gefunden. Analysiere Wichtigkeit..."
            )
            
            # Show article list from last 12 hours
            twelve_hours_ago = now - timedelta(hours=12)
            recent_articles = []
            for article in articles:
                article_date_str = article.get('date')
                if article_date_str:
                    try:
                        article_date = datetime.fromisoformat(article_date_str.replace('Z', '+00:00'))
                        if article_date >= twelve_hours_ago:
                            time_str = article_date.strftime('%H:%M')
                            title = article.get('title', 'Ohne Titel')
                            title_short = title[:30] + '...' if len(title) > 30 else title
                            recent_articles.append(f"{time_str} - {title_short}")
                    except:
                        pass
            
            if recent_articles:
                articles_list = "\n".join(recent_articles)
                await update.message.reply_text(
                    f"📰 *Artikel der letzten 12h:*\n```\n{articles_list}\n```",
                    parse_mode='Markdown'
                )
            
            # Extract content
            content_texts = [fetcher.extract_article_content(article) for article in articles]
            
            # Rank articles
            ranker = NewsRanker()
            top_articles = ranker.rank_articles(articles)
            
            if not top_articles:
                logger.warning("No articles selected after ranking")
                await update.message.reply_text(
                    "⚠️ Keine Artikel nach Ranking ausgewählt."
                )
                return
            
            logger.info(f"Ranked and selected top {len(top_articles)} articles")
            await update.message.reply_text(
                f"✅ Top {len(top_articles)} Artikel ausgewählt. Erstelle Zusammenfassungen..."
            )
            
            # Get content for selected articles
            top_content = []
            for article in top_articles:
                try:
                    idx = articles.index(article)
                    top_content.append(content_texts[idx])
                except ValueError:
                    top_content.append(fetcher.extract_article_content(article))
            
            # Debug: Send prompts info to user
            try:
                from src.prompt_loader import PromptLoader
                system_prompt, user_template, max_tokens = PromptLoader.get_summarization_prompts()
                
                debug_msg = f"🔍 *Debug: Prompts Being Used*\n\n"
                debug_msg += f"*OpenAI Model:* `{Config.OPENAI_MODEL}`\n"
                debug_msg += f"*System Prompt:*\n`{system_prompt}`\n\n"
                debug_msg += f"*User Template:*\n```\n{user_template[:500]}...```\n\n"
                debug_msg += f"*Max Tokens:* {max_tokens}\n"
                debug_msg += f"*Content length for first article:* {len(top_content[0]) if top_content else 0} chars"
                
                await update.message.reply_text(debug_msg, parse_mode='Markdown')
            except Exception as e:
                await update.message.reply_text(f"⚠️ Debug error: {str(e)}")
            
            # Generate summaries
            summarizer = NewsSummarizer()
            summaries = summarizer.summarize_articles(top_articles, top_content)
            
            logger.info(f"Generated {len(summaries)} summaries")
            await update.message.reply_text(
                f"📝 Zusammenfassungen erstellt. Sende Digest an Kanal..."
            )
            
            # Send to channel
            publisher = TelegramPublisher()
            success = await publisher.send_digest_async(top_articles, summaries, now)
            
            if success:
                logger.info("Successfully sent manual digest to channel")
                await update.message.reply_text(
                    "✅ Nachrichten-Digest erfolgreich gesendet!"
                )
            else:
                logger.error("Failed to send manual digest to channel")
                await update.message.reply_text(
                    "❌ Fehler beim Senden des Digests. Siehe Logs für Details."
                )
                
        except Exception as e:
            logger.error(f"Error processing /fire command: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Fehler bei der Verarbeitung: {str(e)}"
            )
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        await update.message.reply_text(
            "🤖 Schagestau Telegram Bot\n\n"
            "Verfügbare Befehle:\n"
            "/fire - Manuell Nachrichten-Digest der letzten 12 Stunden erstellen (nur autorisierte Nutzer)\n"
            "/start - Diese Hilfe anzeigen"
        )
    
    def setup(self):
        """Setup the Telegram bot command listener"""
        self.application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
        
        # Add command handlers
        self.application.add_handler(CommandHandler("fire", self.fire_command))
        self.application.add_handler(CommandHandler("start", self.start_command))
        
        logger.info("Command listener setup complete")
    
    def run(self):
        """Run the bot command listener"""
        if not self.application:
            self.setup()
        
        logger.info("Starting command listener...")
        
        # Run in new event loop without signal handlers
        async def start_bot():
            async with self.application:
                await self.application.initialize()
                await self.application.start()
                await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
                # Keep running
                await asyncio.Event().wait()
        
        # Run the bot
        try:
            asyncio.run(start_bot())
        except Exception as e:
            logger.error(f"Command listener error: {e}", exc_info=True)
