#!/usr/bin/env python3
"""
Initialize the bot's storage
"""
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config


def init_storage():
    """Initialize storage files if they don't exist"""
    
    # Check if last_fetch.json exists
    if not os.path.exists(Config.LAST_FETCH_FILE):
        print(f"Creating {Config.LAST_FETCH_FILE}...")
        with open(Config.LAST_FETCH_FILE, 'w') as f:
            json.dump({'last_fetch': None}, f)
        print(f"✓ Created {Config.LAST_FETCH_FILE}")
    else:
        print(f"✓ {Config.LAST_FETCH_FILE} already exists")
    
    # Check if the carry-over article pool exists
    if not os.path.exists(Config.ARTICLE_POOL_FILE):
        print(f"Creating {Config.ARTICLE_POOL_FILE}...")
        with open(Config.ARTICLE_POOL_FILE, 'w') as f:
            json.dump({'pool': [], 'posted': {}}, f)
        print(f"✓ Created {Config.ARTICLE_POOL_FILE}")
    else:
        print(f"✓ {Config.ARTICLE_POOL_FILE} already exists")
    
    # Create log file if it doesn't exist
    if not os.path.exists(Config.LOG_FILE):
        print(f"Creating {Config.LOG_FILE}...")
        with open(Config.LOG_FILE, 'w') as f:
            f.write('')
        print(f"✓ Created {Config.LOG_FILE}")
    else:
        print(f"✓ {Config.LOG_FILE} already exists")
    
    print("\nInitialization complete!")
    print("\nNext steps:")
    print("1. Copy .env.example to .env")
    print("2. Edit .env with your credentials")
    print("3. Run: python main.py")


if __name__ == '__main__':
    init_storage()
