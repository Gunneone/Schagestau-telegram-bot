import logging
from src.config import Config


def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(Config.LOG_FILE),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def format_timestamp(dt):
    """Format datetime for German display"""
    return dt.strftime('%d.%m.%Y %H:%M')
