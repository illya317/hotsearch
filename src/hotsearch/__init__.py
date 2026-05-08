from pathlib import Path

from dotenv import load_dotenv

# src/hotsearch/__init__.py -> src/hotsearch/ -> src/ -> project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")
