import json
import os
from datetime import datetime
from src.config import Config
import logging

logger = logging.getLogger(__name__)


class Storage:
    """Handles persistence of last fetch timestamp"""
    
    @staticmethod
    def get_last_fetch_time():
        """Get the last fetch timestamp"""
        if not os.path.exists(Config.LAST_FETCH_FILE):
            logger.info("No previous fetch timestamp found")
            return None
        
        try:
            with open(Config.LAST_FETCH_FILE, 'r') as f:
                data = json.load(f)
                timestamp_str = data.get('last_fetch')
                if timestamp_str:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    logger.info(f"Last fetch was at: {timestamp}")
                    return timestamp
        except Exception as e:
            logger.error(f"Error reading last fetch time: {e}")
        
        return None
    
    @staticmethod
    def save_last_fetch_time(timestamp):
        """Save the last fetch timestamp"""
        try:
            with open(Config.LAST_FETCH_FILE, 'w') as f:
                json.dump({
                    'last_fetch': timestamp.isoformat()
                }, f)
            logger.info(f"Updated last fetch timestamp to: {timestamp}")
        except Exception as e:
            logger.error(f"Error saving last fetch time: {e}")
