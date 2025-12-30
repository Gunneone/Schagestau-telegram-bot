import json
from openai import OpenAI
from src.config import Config
from src.prompt_loader import PromptLoader
import logging

logger = logging.getLogger(__name__)


class NewsRanker:
    """Ranks news articles by importance using OpenAI"""
    
    def __init__(self):
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.OPENAI_MODEL
        self.temperature = Config.OPENAI_TEMPERATURE
        self.max_tokens = Config.OPENAI_MAX_TOKENS
    
    def rank_articles(self, articles):
        """
        Rank articles by importance and return top N
        
        Args:
            articles: List of article dictionaries
            
        Returns:
            list: Top N most important articles
        """
        if not articles:
            logger.warning("No articles to rank")
            return []
        
        if len(articles) <= Config.NEWS_COUNT:
            logger.info(f"Only {len(articles)} articles, returning all")
            return articles[:Config.NEWS_COUNT]
        
        try:
            # Prepare articles for ranking
            articles_for_prompt = []
            for idx, article in enumerate(articles):
                articles_for_prompt.append({
                    'id': idx,
                    'title': article.get('title', ''),
                    'date': article.get('date', ''),
                    'topline': article.get('topline', ''),
                    'firstSentence': article.get('firstSentence', '')
                })
            
            prompt = self._build_ranking_prompt(articles_for_prompt)
            
            logger.info(f"Sending {len(articles)} articles to OpenAI for ranking")
            
            system_prompt, _, max_tokens = PromptLoader.get_ranking_prompts()
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_completion_tokens=max_tokens
            )
            
            result_text = response.choices[0].message.content.strip()
            logger.debug(f"OpenAI ranking response: {result_text}")
            
            # Parse JSON response
            ranked_ids = self._parse_ranking_response(result_text)
            
            # Get top N articles
            top_articles = []
            for article_id in ranked_ids[:Config.NEWS_COUNT]:
                if 0 <= article_id < len(articles):
                    top_articles.append(articles[article_id])
            
            logger.info(f"Selected top {len(top_articles)} articles")
            return top_articles
            
        except Exception as e:
            logger.error(f"Error ranking articles: {e}")
            # Fallback: return first N articles
            logger.info(f"Falling back to first {Config.NEWS_COUNT} articles")
            return articles[:Config.NEWS_COUNT]
    
    def _build_ranking_prompt(self, articles):
        """Build the ranking prompt in German"""
        articles_text = json.dumps(articles, ensure_ascii=False, indent=2)
        
        _, user_template, _ = PromptLoader.get_ranking_prompts()
        
        prompt = user_template.format(
            news_count=Config.NEWS_COUNT,
            articles_json=articles_text
        )
        
        return prompt
    
    def _parse_ranking_response(self, response_text):
        """Parse the ranking response from OpenAI"""
        try:
            # Try to find JSON array in response
            start = response_text.find('[')
            end = response_text.rfind(']') + 1
            
            if start != -1 and end > start:
                json_str = response_text[start:end]
                ranked_ids = json.loads(json_str)
                return ranked_ids
            else:
                raise ValueError("No JSON array found in response")
                
        except Exception as e:
            logger.error(f"Error parsing ranking response: {e}")
            # Return sequential IDs as fallback
            return list(range(Config.NEWS_COUNT))
