import yaml
import os
import logging

logger = logging.getLogger(__name__)


class PromptLoader:
    """Loads and manages LLM prompts from YAML configuration"""
    
    _prompts = None
    _prompts_file = 'prompts.yml'
    
    @classmethod
    def load_prompts(cls):
        """Load prompts from YAML file"""
        if cls._prompts is None:
            prompts_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), cls._prompts_file)
            try:
                with open(prompts_path, 'r', encoding='utf-8') as f:
                    cls._prompts = yaml.safe_load(f)
                logger.info(f"Loaded prompts from {prompts_path}")
            except Exception as e:
                logger.error(f"Error loading prompts file: {e}")
                raise
        return cls._prompts
    
    @classmethod
    def get_ranking_prompts(cls):
        """Get ranking system and user prompts and max tokens"""
        prompts = cls.load_prompts()
        return (
            prompts['ranking']['system'],
            prompts['ranking']['user_template'],
            prompts['ranking'].get('max_completion_tokens', 2000)
        )
    
    @classmethod
    def get_summarization_prompts(cls):
        """Get summarization system and user prompts and max tokens"""
        prompts = cls.load_prompts()
        return (
            prompts['summarization']['system'],
            prompts['summarization']['user_template'],
            prompts['summarization'].get('max_completion_tokens', 500)
        )
    
    @classmethod
    def get_title_improvement_prompts(cls):
        """Get title improvement system and user prompts and max tokens"""
        prompts = cls.load_prompts()
        return (
            prompts['title_improvement']['system'],
            prompts['title_improvement']['user_template'],
            prompts['title_improvement'].get('max_completion_tokens', 50)
        )
    
    @classmethod
    def reload_prompts(cls):
        """Force reload of prompts from file (useful for testing)"""
        cls._prompts = None
        return cls.load_prompts()
