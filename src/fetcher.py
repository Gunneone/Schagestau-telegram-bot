import requests
from datetime import datetime
from src.config import Config
import logging
import time

logger = logging.getLogger(__name__)


class NewsFetcher:
    """Fetches news from Tagesschau API"""
    
    def __init__(self):
        self.api_url = Config.TAGESSCHAU_API_URL
    
    def fetch_news(self, since=None):
        """
        Fetch news articles from Tagesschau API
        
        Args:
            since: datetime - Only fetch articles newer than this timestamp
            
        Returns:
            list: List of news articles
        """
        try:
            logger.info(f"Fetching news from {self.api_url}")
            response = requests.get(self.api_url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            all_news = data.get('news', [])
            
            logger.info(f"Received {len(all_news)} articles from API")
            
            # Filter by timestamp if provided
            if since:
                filtered_news = []
                for article in all_news:
                    article_date_str = article.get('date')
                    if article_date_str:
                        try:
                            # Parse ISO format date
                            article_date = datetime.fromisoformat(article_date_str.replace('Z', '+00:00'))
                            # Make since timezone aware if it isn't
                            if since.tzinfo is None:
                                from pytz import UTC
                                since = since.replace(tzinfo=UTC)
                            
                            if article_date > since:
                                filtered_news.append(article)
                        except Exception as e:
                            logger.warning(f"Error parsing date for article: {e}")
                            # Include article if date parsing fails
                            filtered_news.append(article)
                
                logger.info(f"Filtered to {len(filtered_news)} articles since {since}")
                return filtered_news
            
            return all_news
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching news from API: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching news: {e}")
            return []
    
    def extract_article_content(self, article):
        """Extract text content from article"""
        content_parts = article.get('content', [])
        if not content_parts:
            return article.get('title', '')
        
        # Combine all text content
        text_parts = []
        for part in content_parts:
            if part.get('type') == 'text' or 'value' in part:
                text_parts.append(part.get('value', ''))
        
        return ' '.join(text_parts) if text_parts else article.get('title', '')
