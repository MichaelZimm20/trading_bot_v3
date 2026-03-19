"""
Telegram Alert Module
Sends formatted trading alerts to your Telegram
"""

import requests
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def send_telegram_message(message: str) -> bool:
    """Send a message to Telegram. Returns True if successful."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"Telegram send failed [{response.status_code}]: {response.text}")
            return False
        return True
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")
        return False


def send_price_target_alert(symbol: str, target_price: float, current_price: float, 
                            change_pct: float, notes: str = "") -> bool:
    """Send a price target hit alert."""
    
    direction = "📈" if change_pct >= 0 else "📉"
    sign = "+" if change_pct >= 0 else ""
    
    message = f"""
🎯 <b>PRICE TARGET HIT: {symbol}</b>
━━━━━━━━━━━━━━━━━━━━━━
Target: <b>${target_price:.2f}</b>
Current: <b>${current_price:.2f}</b> ({sign}{change_pct:.2f}%)
Time: {datetime.now().strftime("%I:%M:%S %p ET")}
{f"📝 {notes}" if notes else ""}
"""
    return send_telegram_message(message.strip())


def send_percent_move_alert(symbol: str, current_price: float, open_price: float,
                            change_pct: float, threshold_pct: float, notes: str = "") -> bool:
    """Send a percentage move alert."""
    
    direction = "🚀" if change_pct >= 0 else "💥"
    sign = "+" if change_pct >= 0 else ""
    
    message = f"""
{direction} <b>BIG MOVE: {symbol}</b>
━━━━━━━━━━━━━━━━━━━━━━
Move: <b>{sign}{change_pct:.2f}%</b> (threshold: {threshold_pct}%)
Current: <b>${current_price:.2f}</b>
Open: ${open_price:.2f}
Time: {datetime.now().strftime("%I:%M:%S %p ET")}
{f"📝 {notes}" if notes else ""}
"""
    return send_telegram_message(message.strip())


def send_volume_spike_alert(symbol: str, current_volume: int, avg_volume: int,
                            spike_ratio: float, current_price: float, notes: str = "") -> bool:
    """Send a volume spike alert."""
    
    message = f"""
📊 <b>VOLUME SPIKE: {symbol}</b>
━━━━━━━━━━━━━━━━━━━━━━
Volume: <b>{current_volume:,}</b> ({spike_ratio:.1f}x avg)
Avg Volume: {avg_volume:,}
Price: <b>${current_price:.2f}</b>
Time: {datetime.now().strftime("%I:%M:%S %p ET")}
{f"📝 {notes}" if notes else ""}
"""
    return send_telegram_message(message.strip())


def send_startup_message(watchlist: dict) -> bool:
    """Send a message when the bot starts up."""
    
    symbols = ", ".join(watchlist.keys())
    
    message = f"""
🤖 <b>Trading Alert Bot Started</b>
━━━━━━━━━━━━━━━━━━━━━━
Monitoring: {symbols}
Time: {datetime.now().strftime("%I:%M:%S %p ET")}

You will receive alerts for:
• Price targets hit
• Large % moves
• Volume spikes

<i>Good luck trading! 🍀</i>
"""
    return send_telegram_message(message.strip())


def send_shutdown_message(reason: str = "Manual shutdown") -> bool:
    """Send a message when the bot shuts down."""
    
    message = f"""
🔴 <b>Trading Alert Bot Stopped</b>
━━━━━━━━━━━━━━━━━━━━━━
Reason: {reason}
Time: {datetime.now().strftime("%I:%M:%S %p ET")}
"""
    return send_telegram_message(message.strip())


def send_error_alert(error_message: str) -> bool:
    """Send an error alert."""
    
    message = f"""
⚠️ <b>Bot Error</b>
━━━━━━━━━━━━━━━━━━━━━━
{error_message}
Time: {datetime.now().strftime("%I:%M:%S %p ET")}
"""
    return send_telegram_message(message.strip())


# Quick test function
if __name__ == "__main__":
    print("Testing Telegram connection...")
    success = send_telegram_message("🧪 Test message from Trading Alert Bot!")
    if success:
        print("✅ Telegram test successful!")
    else:
        print("❌ Telegram test failed. Check your token and chat ID.")
