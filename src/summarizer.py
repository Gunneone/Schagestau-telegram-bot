from openai import OpenAI
from src.config import Config
from src.prompt_loader import PromptLoader
import logging

logger = logging.getLogger(__name__)


class NewsSummarizer:
    """Generates summaries for news articles using OpenAI"""
    
    def __init__(self):
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.OPENAI_MODEL
        self.temperature = Config.OPENAI_TEMPERATURE
        self.max_tokens = Config.OPENAI_MAX_TOKENS
    
    def summarize_article(self, article, content_text):
        """
        Generate a summary for a single article
        
        Args:
            article: Article dictionary
            content_text: Full text content of the article
            
        Returns:
            str: Summary text (max 3 sentences)
        """
        try:
            prompt = self._build_summary_prompt(article, content_text)
            
            logger.debug(f"Generating summary for: {article.get('title', 'Unknown')}")
            
            system_prompt, _, max_tokens = PromptLoader.get_summarization_prompts()
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_completion_tokens=max_tokens
            )
            
            summary = response.choices[0].message.content.strip()
            logger.debug(f"Generated summary: {summary[:100]}...")
            logger.info(f"✅ Successfully generated summary for: {article.get('title', 'Unknown')[:50]}")
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            logger.error(f"Article title: {article.get('title', 'Unknown')}")
            logger.error(f"Content length: {len(content_text) if content_text else 0}")
            # Fallback to first sentence or topline
            fallback = article.get('firstSentence') or article.get('topline') or article.get('title', '')
            logger.warning(f"Using fallback summary: {fallback[:100]}")
            return fallback
    
    def summarize_articles(self, articles, content_texts):
        """
        Generate summaries for multiple articles
        
        Args:
            articles: List of article dictionaries
            content_texts: List of content texts corresponding to articles
            
        Returns:
            list: List of summaries
        """
        summaries = []
        
        for idx, article in enumerate(articles):
            content = content_texts[idx] if idx < len(content_texts) else ''
            summary = self.summarize_article(article, content)
            summaries.append(summary)
        
        logger.info(f"Generated {len(summaries)} summaries")
        return summaries
    
    def _build_summary_prompt(self, article, content_text):
        """Build the summarization prompt in German"""
        title = article.get('title', '')
        
        # Use content_text if available, otherwise use what we have
        text = content_text or article.get('firstSentence', '') or article.get('topline', '')
        
        _, user_template, _ = PromptLoader.get_summarization_prompts()
        
        prompt = user_template.format(
            title=title,
            content=text
        )
        
        return prompt
