"""
Telegram Command Handler
Receives and processes commands from Telegram
"""

import requests
import json
import time
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from threading import Thread
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


class TelegramCommandHandler:
    """
    Handles incoming Telegram commands via polling.
    """
    
    def __init__(self, bot_token: str = TELEGRAM_BOT_TOKEN, chat_id: str = TELEGRAM_CHAT_ID):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        
        self.last_update_id = 0
        self.running = False
        self.poll_thread: Optional[Thread] = None
        
        # Command handlers: command_name -> callback function
        self.commands: Dict[str, Callable] = {}
        
        # Register built-in commands
        self._register_builtin_commands()
    
    def _register_builtin_commands(self):
        """Register the help command."""
        self.register_command("help", self._help_command)
        self.register_command("start", self._help_command)
    
    def _help_command(self, args: list) -> str:
        """Show available commands."""
        return """
🤖 <b>Trading Alert Bot Commands</b>
━━━━━━━━━━━━━━━━━━━━━━

<b>Watchlist Management:</b>
/watch SYMBOL PRICE1 PRICE2 ...
  → Add stock with price targets
  → Example: /watch TSLA 180 200 220

/unwatch SYMBOL
  → Remove stock from watchlist
  → Example: /unwatch TSLA

/list
  → Show current watchlist

/clear
  → Remove all stocks from watchlist

<b>Price Targets:</b>
/target SYMBOL PRICE
  → Add a price target
  → Example: /target CRDO 150

/removetarget SYMBOL PRICE
  → Remove a price target
  → Example: /removetarget CRDO 96

<b>Status:</b>
/status
  → Get current prices

/ping
  → Check if bot is alive

<b>Settings:</b>
/pct SYMBOL PERCENT
  → Set % move alert threshold
  → Example: /pct NVDA 3

/note SYMBOL Your notes here
  → Add notes to a stock
  → Example: /note CRDO Watch for earnings
"""
    
    def register_command(self, command: str, callback: Callable):
        """
        Register a command handler.
        
        callback should accept a list of arguments and return a response string.
        """
        self.commands[command.lower()] = callback
    
    def send_message(self, text: str) -> bool:
        """Send a message to the user."""
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        try:
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Failed to send message: {e}")
            return False
    
    def get_updates(self) -> list:
        """Get new messages from Telegram."""
        url = f"{self.base_url}/getUpdates"
        params = {
            "offset": self.last_update_id + 1,
            "timeout": 30,  # Long polling
            "allowed_updates": ["message"]
        }
        
        try:
            response = requests.get(url, params=params, timeout=35)
            if response.status_code == 200:
                data = response.json()
                return data.get("result", [])
            print(f"Telegram getUpdates failed [{response.status_code}]: {response.text}")
        except Exception as e:
            print(f"Error getting updates: {e}")
        
        return []
    
    def process_message(self, message: dict):
        """Process an incoming message."""
        # Only process messages from our chat
        chat_id = str(message.get("chat", {}).get("id", ""))
        if chat_id != self.chat_id:
            return
        
        text = message.get("text", "").strip()
        if not text:
            return
        
        # Check if it's a command
        if text.startswith("/"):
            self._handle_command(text)
        else:
            # Echo back for non-commands (optional)
            pass
    
    def _handle_command(self, text: str):
        """Parse and execute a command."""
        parts = text.split()
        command = parts[0][1:].lower()  # Remove the "/" and lowercase
        args = parts[1:] if len(parts) > 1 else []
        
        # Remove @botname if present (e.g., /watch@mybot)
        if "@" in command:
            command = command.split("@")[0]
        
        if command in self.commands:
            try:
                response = self.commands[command](args)
                if response:
                    self.send_message(response)
            except Exception as e:
                self.send_message(f"❌ Error: {str(e)}")
        else:
            self.send_message(f"❓ Unknown command: /{command}\n\nType /help for available commands.")
    
    def _poll_loop(self):
        """Main polling loop - runs in a separate thread."""
        print("📱 Telegram command listener started")
        
        while self.running:
            try:
                updates = self.get_updates()
                
                for update in updates:
                    self.last_update_id = update.get("update_id", self.last_update_id)
                    
                    if "message" in update:
                        self.process_message(update["message"])
                
            except Exception as e:
                print(f"Polling error: {e}")
                time.sleep(5)  # Wait before retrying
    
    def start_polling(self):
        """Start the polling thread."""
        if self.running:
            return
        
        self.running = True
        self.poll_thread = Thread(target=self._poll_loop, daemon=True)
        self.poll_thread.start()
    
    def stop_polling(self):
        """Stop the polling thread."""
        self.running = False
        if self.poll_thread:
            self.poll_thread.join(timeout=5)


class WatchlistManager:
    """
    Manages the watchlist and integrates with Telegram commands.
    """
    
    def __init__(self, initial_watchlist: dict, on_update: Optional[Callable] = None,
                 state_file: str = "watchlist_state.json"):
        self.state_file = Path(state_file)
        self.watchlist = self._load_watchlist(initial_watchlist)
        self.on_update = on_update  # Called when watchlist changes
        
        self.telegram = TelegramCommandHandler()
        self._register_commands()

        # Ensure state file exists and reflects initial loaded state.
        self._save_watchlist()

    def _load_watchlist(self, default_watchlist: dict) -> dict:
        """Load saved watchlist from disk; fallback to config defaults."""
        if not self.state_file.exists():
            return default_watchlist.copy()

        try:
            with self.state_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                print(f"📂 Loaded watchlist state from {self.state_file}")
                return data
        except Exception as e:
            print(f"⚠️ Failed to load watchlist state: {e}")

        return default_watchlist.copy()

    def _save_watchlist(self):
        """Persist watchlist updates so restarts keep Telegram changes."""
        try:
            with self.state_file.open("w", encoding="utf-8") as f:
                json.dump(self.watchlist, f, indent=2)
        except Exception as e:
            print(f"⚠️ Failed to save watchlist state: {e}")
    
    def _register_commands(self):
        """Register all watchlist commands."""
        self.telegram.register_command("watch", self.cmd_watch)
        self.telegram.register_command("unwatch", self.cmd_unwatch)
        self.telegram.register_command("list", self.cmd_list)
        self.telegram.register_command("clear", self.cmd_clear)
        self.telegram.register_command("target", self.cmd_add_target)
        self.telegram.register_command("removetarget", self.cmd_remove_target)
        self.telegram.register_command("pct", self.cmd_set_pct)
        self.telegram.register_command("note", self.cmd_set_note)
        self.telegram.register_command("status", self.cmd_status)
        self.telegram.register_command("health", self.cmd_health)
        self.telegram.register_command("ping", self.cmd_ping)
    
    def cmd_watch(self, args: list) -> str:
        """Add a stock to watchlist: /watch SYMBOL PRICE1 PRICE2 ..."""
        if len(args) < 1:
            return "❌ Usage: /watch SYMBOL [PRICE1] [PRICE2] ...\nExample: /watch TSLA 180 200 220"
        
        symbol = args[0].upper()
        
        # Parse price targets
        price_targets = []
        for arg in args[1:]:
            try:
                price_targets.append(float(arg))
            except ValueError:
                pass
        
        self.watchlist[symbol] = {
            "price_targets": price_targets,
            "pct_move": 5,  # Default 5%
            "notes": ""
        }
        
        self._notify_update()
        
        targets_str = ", ".join([f"${p:.2f}" for p in price_targets]) if price_targets else "None"
        return f"✅ Added <b>{symbol}</b> to watchlist\nPrice targets: {targets_str}"
    
    def cmd_unwatch(self, args: list) -> str:
        """Remove a stock: /unwatch SYMBOL"""
        if len(args) < 1:
            return "❌ Usage: /unwatch SYMBOL"
        
        symbol = args[0].upper()
        
        if symbol in self.watchlist:
            del self.watchlist[symbol]
            self._notify_update()
            return f"✅ Removed <b>{symbol}</b> from watchlist"
        else:
            return f"❌ {symbol} is not in your watchlist"
    
    def cmd_list(self, args: list) -> str:
        """Show current watchlist: /list"""
        if not self.watchlist:
            return "📋 Your watchlist is empty.\n\nUse /watch SYMBOL to add stocks."
        
        lines = ["📋 <b>Current Watchlist</b>", "━━━━━━━━━━━━━━━━━━━━━━"]
        
        for symbol, config in self.watchlist.items():
            targets = config.get("price_targets", [])
            pct = config.get("pct_move", 0)
            notes = config.get("notes", "")
            
            targets_str = ", ".join([f"${p:.0f}" for p in targets]) if targets else "None"
            
            lines.append(f"\n<b>{symbol}</b>")
            lines.append(f"  Targets: {targets_str}")
            if pct:
                lines.append(f"  Alert on: ±{pct}% move")
            if notes:
                lines.append(f"  📝 {notes}")
        
        return "\n".join(lines)
    
    def cmd_clear(self, args: list) -> str:
        """Clear all stocks: /clear"""
        count = len(self.watchlist)
        self.watchlist.clear()
        self._notify_update()
        return f"🗑️ Cleared {count} stocks from watchlist"
    
    def cmd_add_target(self, args: list) -> str:
        """Add a price target: /target SYMBOL PRICE"""
        if len(args) < 2:
            return "❌ Usage: /target SYMBOL PRICE\nExample: /target CRDO 150"
        
        symbol = args[0].upper()
        try:
            price = float(args[1])
        except ValueError:
            return "❌ Invalid price"
        
        if symbol not in self.watchlist:
            self.watchlist[symbol] = {"price_targets": [], "pct_move": 5, "notes": ""}
        
        if price not in self.watchlist[symbol].get("price_targets", []):
            self.watchlist[symbol].setdefault("price_targets", []).append(price)
            self.watchlist[symbol]["price_targets"].sort()
            self._notify_update()
        
        return f"✅ Added ${price:.2f} target for <b>{symbol}</b>"
    
    def cmd_remove_target(self, args: list) -> str:
        """Remove a price target: /removetarget SYMBOL PRICE"""
        if len(args) < 2:
            return "❌ Usage: /removetarget SYMBOL PRICE"
        
        symbol = args[0].upper()
        try:
            price = float(args[1])
        except ValueError:
            return "❌ Invalid price"
        
        if symbol in self.watchlist:
            targets = self.watchlist[symbol].get("price_targets", [])
            if price in targets:
                targets.remove(price)
                self._notify_update()
                return f"✅ Removed ${price:.2f} target from <b>{symbol}</b>"
        
        return f"❌ Target ${price:.2f} not found for {symbol}"
    
    def cmd_set_pct(self, args: list) -> str:
        """Set % move threshold: /pct SYMBOL PERCENT"""
        if len(args) < 2:
            return "❌ Usage: /pct SYMBOL PERCENT\nExample: /pct NVDA 3"
        
        symbol = args[0].upper()
        try:
            pct = float(args[1])
        except ValueError:
            return "❌ Invalid percentage"
        
        if symbol not in self.watchlist:
            return f"❌ {symbol} is not in your watchlist. Add it first with /watch"
        
        self.watchlist[symbol]["pct_move"] = pct
        self._notify_update()
        return f"✅ Set <b>{symbol}</b> alert to ±{pct}% move"
    
    def cmd_set_note(self, args: list) -> str:
        """Set notes for a stock: /note SYMBOL Your notes here"""
        if len(args) < 2:
            return "❌ Usage: /note SYMBOL Your notes here"
        
        symbol = args[0].upper()
        note = " ".join(args[1:])
        
        if symbol not in self.watchlist:
            return f"❌ {symbol} is not in your watchlist. Add it first with /watch"
        
        self.watchlist[symbol]["notes"] = note
        self._notify_update()
        return f"✅ Updated notes for <b>{symbol}</b>"
    
    def cmd_status(self, args: list) -> str:
        """Get current status - this will be overridden by main.py"""
        return "📊 Status check... (prices updated when market is open)"

    def cmd_health(self, args: list) -> str:
        """Get basic health status - this will be overridden by main.py."""
        return "✅ Bot is running. Use /status for prices."
    
    def cmd_ping(self, args: list) -> str:
        """Check if bot is alive: /ping"""
        from datetime import datetime
        return f"🏓 Pong! Bot is running.\nTime: {datetime.now().strftime('%I:%M:%S %p ET')}"
    
    def _notify_update(self):
        """Notify that the watchlist has changed."""
        self._save_watchlist()
        if self.on_update:
            self.on_update(self.watchlist)
    
    def start(self):
        """Start listening for commands."""
        self.telegram.start_polling()
    
    def stop(self):
        """Stop listening for commands."""
        self.telegram.stop_polling()
    
    def get_watchlist(self) -> dict:
        """Get current watchlist."""
        return self.watchlist


# Test
if __name__ == "__main__":
    print("Testing Telegram command handler...")
    
    def on_watchlist_change(new_watchlist):
        print(f"Watchlist updated: {list(new_watchlist.keys())}")
    
    manager = WatchlistManager({}, on_update=on_watchlist_change)
    manager.start()
    
    print("Listening for commands... Send /help to your bot!")
    print("Press Ctrl+C to stop.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        manager.stop()
        print("Stopped.")
