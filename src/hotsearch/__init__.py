from pathlib import Path

from dotenv import load_dotenv

# src/hotsearch/__init__.py -> src/hotsearch/ -> src/ -> project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
CACHE_API_DIR = CACHE_DIR / "api"
CACHE_FEEDS_DIR = CACHE_DIR / "feeds"
CACHE_SEARCH_DIR = CACHE_DIR / "search"
CACHE_TRENDS_DIR = CACHE_DIR / "trends"
VOICES_CONFIG = CONFIG_DIR / "feishu_voice.json"
PLATFORMS_CONFIG = CONFIG_DIR / "hotsearch.json"
BOT_CONFIG = CONFIG_DIR / "bot.json"
SCHEDULER_CONFIG = CONFIG_DIR / "trends.json"
