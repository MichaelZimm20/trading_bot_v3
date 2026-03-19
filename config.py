# ===========================================
# TRADING ALERT BOT - CONFIGURATION
# ===========================================

import os
from pathlib import Path

from dotenv import load_dotenv


# Load local .env (if present) so secrets are not hardcoded in source.
load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

# Telegram Settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


def validate_telegram_config() -> tuple[bool, str]:
    """Validate Telegram settings before startup."""
    if not TELEGRAM_BOT_TOKEN:
        return False, "Missing TELEGRAM_BOT_TOKEN (set it in .env or environment)."
    if not TELEGRAM_CHAT_ID:
        return False, "Missing TELEGRAM_CHAT_ID (set it in .env or environment)."
    return True, "OK"

# IBKR Settings
IBKR_HOST = "127.0.0.1"  # localhost if running on same machine as TWS
IBKR_PORT = 7496         # 7496 for live, 7497 for paper trading
IBKR_CLIENT_ID = 1       # Can be any number, just keep it consistent

# ===========================================
# YOUR WATCHLIST - EDIT THIS!
# ===========================================
# 
# Each ticker can have multiple alert types:
#   - "price_targets": Alert when price hits these levels
#   - "pct_move": Alert on X% move from market open
#   - "volume_spike": Alert when volume exceeds X times average
#
# ===========================================

WATCHLIST = {
    "CRDO": {
        "price_targets": [96, 120, 148],
        "pct_move": 5,  # Alert on 5% move
        "notes": "Watch for bounce off support, IV high - consider ITM calls"
    },
    "NVDA": {
        "price_targets": [115, 125, 140],
        "pct_move": 3,
        "notes": "AI leader, watch for earnings run-up"
    },
    "AMKR": {
        "price_targets": [48, 52, 55],
        "pct_move": 5,
        "notes": "Semiconductor play, volatile after hours"
    },
    # Add more tickers here...
    # "TICKER": {
    #     "price_targets": [price1, price2, price3],
    #     "pct_move": 5,
    #     "notes": "Your trading notes here"
    # },
}

# Alert Cooldown (seconds) - prevents spam for same alert
ALERT_COOLDOWN = 300  # 5 minutes between repeat alerts

# Market Hours (Eastern Time)
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MINUTE = 0

# Include pre-market and after-hours?
INCLUDE_EXTENDED_HOURS = True
EXTENDED_HOURS_START = 4   # 4 AM ET
EXTENDED_HOURS_END = 20    # 8 PM ET

# Optional periodic heartbeat message in minutes (0 disables).
HEARTBEAT_INTERVAL_MINUTES = int(os.getenv("HEARTBEAT_INTERVAL_MINUTES", "0"))
