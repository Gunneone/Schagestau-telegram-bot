#!/usr/bin/env python3
import sys
import argparse
from datetime import datetime
import pytz
import schedule
import time
import threading

from src.config import Config
from src.utils import setup_logging
from src.storage import Storage
from src.fetcher import NewsFetcher
from src.ranker import NewsRanker
from src.summarizer import NewsSummarizer
from src.telegram_bot import TelegramPublisher
from src.command_handler import CommandListener

logger = None


def run_digest_cycle(force=False, dry_run=False):
    """
    Run a complete digest cycle
    
    Args:
        force: If True, ignore last fetch timestamp
        dry_run: If True, don't send to Telegram
    """
    logger.info("=" * 50)
    logger.info("Starting scheduled news fetch")
    
    try:
        # Get last fetch time
        last_fetch = None if force else Storage.get_last_fetch_time()
        
        # Fetch news
        fetcher = NewsFetcher()
        articles = fetcher.fetch_news(since=last_fetch)
        
        if not articles:
            logger.info("No new articles found")
            return
        
        logger.info(f"Fetched {len(articles)} articles from Tagesschau API")
        
        # Extract content for each article
        content_texts = [fetcher.extract_article_content(article) for article in articles]
        
        # Rank articles
        ranker = NewsRanker()
        top_articles = ranker.rank_articles(articles)
        
        if not top_articles:
            logger.warning("No articles selected after ranking")
            return
        
        logger.info(f"Ranked articles, selected top {len(top_articles)}")
        
        # Get content for selected articles
        top_content = []
        for article in top_articles:
            # Find the content for this article
            try:
                idx = articles.index(article)
                top_content.append(content_texts[idx])
            except ValueError:
                top_content.append(fetcher.extract_article_content(article))
        
        # Generate summaries
        summarizer = NewsSummarizer()
        summaries = summarizer.summarize_articles(top_articles, top_content)
        
        logger.info(f"Generated summaries for {len(summaries)} articles")
        
        # Send to Telegram
        if not dry_run:
            publisher = TelegramPublisher()
            current_time = datetime.now(pytz.timezone(Config.TIMEZONE))
            success = publisher.send_digest(top_articles, summaries, current_time)
            
            if success:
                logger.info("Successfully sent digest to Telegram")
                # Update last fetch timestamp
                Storage.save_last_fetch_time(current_time)
                logger.info("Updated last fetch timestamp")
            else:
                logger.error("Failed to send digest to Telegram")
        else:
            logger.info("DRY RUN - Skipping Telegram send")
            # Print digest to console
            publisher = TelegramPublisher()
            current_time = datetime.now(pytz.timezone(Config.TIMEZONE))
            message = publisher.format_digest(top_articles, summaries, current_time)
            print("\n" + "=" * 50)
            print("DIGEST PREVIEW:")
            print("=" * 50)
            print(message)
            print("=" * 50 + "\n")
        
    except Exception as e:
        logger.error(f"Error in digest cycle: {e}", exc_info=True)


def schedule_jobs():
    """Schedule the digest jobs and start command listener"""
    tz = pytz.timezone(Config.TIMEZONE)
    
    for fetch_time in Config.FETCH_TIMES:
        fetch_time = fetch_time.strip()
        # Convert configured time from target timezone to UTC (system time)
        hour, minute = map(int, fetch_time.split(':'))
        # Create a datetime in the target timezone for today
        target_tz_time = datetime.now(tz).replace(hour=hour, minute=minute, second=0, microsecond=0)
        # Convert to UTC
        utc_time = target_tz_time.astimezone(pytz.UTC)
        utc_time_str = utc_time.strftime('%H:%M')
        
        schedule.every().day.at(utc_time_str).do(run_digest_cycle)
        logger.info(f"Scheduled job for {fetch_time} {Config.TIMEZONE} (runs at {utc_time_str} UTC)")
    
    # Start command listener in a separate thread
    logger.info("Starting command listener in background...")
    command_listener = CommandListener()
    command_listener.setup()
    
    # Run command listener in separate thread
    listener_thread = threading.Thread(
        target=command_listener.run,
        daemon=True,
        name="CommandListener"
    )
    listener_thread.start()
    logger.info("Command listener started. You can now use /fire command")
    
    logger.info("Bot is running. Press Ctrl+C to stop.")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")


def main():
    global logger
    
    parser = argparse.ArgumentParser(description='Schagestau Telegram News Bot')
    parser.add_argument('--run-once', action='store_true', help='Run a single digest cycle and exit')
    parser.add_argument('--force', action='store_true', help='Ignore last fetch timestamp')
    parser.add_argument('--dry-run', action='store_true', help='Don\'t send to Telegram, just print')
    parser.add_argument('--listen-only', action='store_true', help='Only run command listener, no scheduled jobs')
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging()
    logger.info("Starting Schagestau Telegram Bot")
    
    # Validate configuration
    try:
        Config.validate()
        logger.info("Configuration validated successfully")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    if args.run_once:
        logger.info("Running in single-cycle mode")
        run_digest_cycle(force=args.force, dry_run=args.dry_run)
    elif args.listen_only:
        logger.info("Running in command listener only mode")
        command_listener = CommandListener()
        command_listener.setup()
        logger.info("Command listener started. Send /fire to trigger digest")
        try:
            command_listener.run()
        except KeyboardInterrupt:
            logger.info("Command listener stopped by user")
    else:
        logger.info("Running in scheduled mode with command listener")
        schedule_jobs()


if __name__ == '__main__':
    main()
