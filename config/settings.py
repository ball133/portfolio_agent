"""Configuration constants and paths for the portfolio agent."""
import os
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Base directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(BASE_DIR, "state")
LOG_DIR = os.path.join(BASE_DIR, "logs")

# File paths
PORTFOLIO_FILE = os.path.join(STATE_DIR, "portfolio.json")
HISTORY_FILE = os.path.join(STATE_DIR, "portfolio_history.json")
ARCHIVE_FILE = os.path.join(STATE_DIR, "performance_history_archive.json")
LOOP_STATE_FILE = os.path.join(STATE_DIR, "loop_state.json")

# Default portfolio
DEFAULT_PORTFOLIO = {
    "AAPL": 10,
    "NVDA": 5,
    "TSM": 3,
    "MSFT": 2
}

# Risk thresholds
MAX_SINGLE_WEIGHT_THRESHOLD = 0.3
HHI_MODERATE_CONCENTRATION = 0.15
HHI_HIGH_CONCENTRATION = 0.25

# Price freshness
FRESH_PRICE_THRESHOLD_MINUTES = 15

# AI trend stocks list
AI_TREND_STOCKS = [
    {"ticker": "NVDA", "company": "NVIDIA Corporation"},
    {"ticker": "SMCI", "company": "Super Micro Computer"},
    {"ticker": "AMD", "company": "Advanced Micro Devices"},
    {"ticker": "MSFT", "company": "Microsoft"},
    {"ticker": "GOOGL", "company": "Alphabet (Google)"},
    {"ticker": "META", "company": "Meta Platforms"},
    {"ticker": "TSM", "company": "Taiwan Semiconductor"},
    {"ticker": "PLTR", "company": "Palantir Technologies"},
    {"ticker": "SNOW", "company": "Snowflake"},
    {"ticker": "CRM", "company": "Salesforce"}
]

# Loop framework settings
MAX_ITERATIONS = 3
TOKEN_BUDGET_WARNING = 50000

# Telegram integration settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
