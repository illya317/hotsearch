from pathlib import Path

from dotenv import load_dotenv

# src/hotsearch/__init__.py -> src/hotsearch/ -> src/ -> project root
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

CONFIG_DIR: Path = PROJECT_ROOT / "config"
DATA_DIR: Path = PROJECT_ROOT / "data"
CACHE_DIR: Path = DATA_DIR / "cache"
CACHE_API_DIR: Path = CACHE_DIR / "api"
CACHE_FEEDS_DIR: Path = CACHE_DIR / "feeds"
CACHE_SEARCH_DIR: Path = CACHE_DIR / "search"
CACHE_TRENDS_DIR: Path = CACHE_DIR / "trends"
VOICES_CONFIG: Path = CONFIG_DIR / "feishu_voice.json"
PLATFORMS_CONFIG: Path = CONFIG_DIR / "hotsearch.json"
BOT_CONFIG: Path = CONFIG_DIR / "bot.json"
SCHEDULER_CONFIG: Path = CONFIG_DIR / "trends.json"
