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
    
    def _check_and_improve_title(self, article, content_text):
        """
        Check if title needs improvement and generate better one if needed.
        Uses LLM to judge title quality and improve if necessary.
        
        Args:
            article: Article dictionary
            content_text: Full text content of the article
            
        Returns:
            str: Original title or improved title
        """
        original_title = article.get('title', '')
        
        try:
            system_prompt, user_template, max_tokens = PromptLoader.get_title_improvement_prompts()
            
            prompt = user_template.format(
                title=original_title,
                content=content_text
            )
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_completion_tokens=max_tokens
            )
            
            result_title = response.choices[0].message.content.strip()
            # Remove quotes and ++ markers
            result_title = result_title.strip('"\'').strip('+').strip()
            
            if result_title != original_title:
                logger.info(f"✨ Improved title: '{original_title}' → '{result_title}'")
                article['improved_title'] = result_title
                return result_title
            else:
                logger.debug(f"✓ Title is good: '{original_title}'")
                return original_title
            
        except Exception as e:
            logger.error(f"Error checking/improving title: {e}")
            logger.warning(f"Keeping original title: '{original_title}'")
            return original_title
    
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
            # Check and potentially improve title
            title_to_use = self._check_and_improve_title(article, content_text)
            
            prompt = self._build_summary_prompt(title_to_use, content_text)
            
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
    
    def _build_summary_prompt(self, title, content_text):
        """Build the summarization prompt in German"""
        _, user_template, _ = PromptLoader.get_summarization_prompts()
        
        prompt = user_template.format(
            title=title,
            content=content_text
        )
        
        return prompt
