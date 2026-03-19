#!/usr/bin/env python3
"""
===========================================
TRADING ALERT BOT v3 - with Telegram Commands!
Real-time price alerts via IBKR + Telegram
===========================================

Usage:
    python main.py              # Run the bot (IBKR with Yahoo fallback)
    python main.py --test       # Test Telegram connection only
    python main.py --paper      # Use paper trading port (7497)
    python main.py --yahoo-only # Use only Yahoo Finance (no IBKR)

Telegram Commands:
    /watch SYMBOL PRICE1 PRICE2   - Add stock with targets
    /unwatch SYMBOL               - Remove stock
    /list                         - Show watchlist
    /status                       - Get current prices
    /help                         - Show all commands

Requirements:
    pip install ib_insync requests pytz yfinance

"""

import sys
import time
import signal
import argparse
from datetime import datetime, time as dt_time
from threading import Lock
import pytz

from config import (
    IBKR_HOST, IBKR_PORT, IBKR_CLIENT_ID,
    WATCHLIST, INCLUDE_EXTENDED_HOURS,
    MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE,
    MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE,
    EXTENDED_HOURS_START, EXTENDED_HOURS_END,
    HEARTBEAT_INTERVAL_MINUTES, validate_telegram_config
)
from alert_engine import AlertEngine
from telegram_alerts import (
    send_startup_message,
    send_shutdown_message,
    send_error_alert,
    send_telegram_message
)
from telegram_commands import WatchlistManager


class TradingAlertBot:
    """Main bot that coordinates IBKR/Yahoo connection, alerts, and Telegram commands."""
    
    def __init__(self, paper_trading: bool = False, yahoo_only: bool = False):
        self.paper_trading = paper_trading
        self.yahoo_only = yahoo_only
        self.running = False
        
        # Initialize watchlist manager (handles Telegram commands)
        self.watchlist_manager = WatchlistManager(
            WATCHLIST, 
            on_update=self._on_watchlist_update
        )
        
        # Initialize alert engine
        self.alert_engine = AlertEngine(self.watchlist_manager.get_watchlist())
        
        # Data source
        self.ibkr = None
        self.ibkr_connected = False
        
        # Track subscriptions and pending changes
        self.subscribed_symbols = set()
        self.pending_subscriptions = []
        self.pending_unsubscriptions = []
        self.subscription_lock = Lock()
        
        # Track which symbols failed IBKR and need Yahoo fallback
        self.yahoo_fallback_symbols = set()
        
        # Yahoo price cache
        self.yahoo_cache = {}
        self.yahoo_cache_time = {}
        
        # Override and re-register /status so Telegram uses live status from main bot.
        self.watchlist_manager.cmd_status = self._cmd_status
        self.watchlist_manager.telegram.register_command("status", self._cmd_status)
        self.watchlist_manager.cmd_health = self._cmd_health
        self.watchlist_manager.telegram.register_command("health", self._cmd_health)
        
        # Eastern timezone
        self.et_tz = pytz.timezone('US/Eastern')
    
    def _on_watchlist_update(self, new_watchlist: dict):
        """Called when watchlist is updated via Telegram command."""
        print(f"📝 Watchlist updated via Telegram: {list(new_watchlist.keys())}")
        
        # Update alert engine
        self.alert_engine.update_watchlist(new_watchlist)
        
        # Track changes for the main loop to process
        with self.subscription_lock:
            current = self.subscribed_symbols.copy()
            new_symbols = set(new_watchlist.keys())
            
            self.pending_subscriptions = list(new_symbols - current)
            self.pending_unsubscriptions = list(current - new_symbols)
    
    def _process_pending_subscriptions(self):
        """Process any pending subscription changes (called from main loop)."""
        with self.subscription_lock:
            # Handle new subscriptions
            for symbol in self.pending_subscriptions:
                if self.ibkr and self.ibkr_connected and not self.yahoo_only:
                    try:
                        self.ibkr.subscribe_to_stock(symbol)
                        self.subscribed_symbols.add(symbol)
                        print(f"📊 Subscribed to {symbol} via IBKR")
                        self.ibkr.sleep(0.5)
                        
                        # Check if we got data, otherwise fallback to Yahoo
                        time.sleep(1)
                        data = self.ibkr.get_price(symbol)
                        if not data or data.get("last", 0) == 0:
                            print(f"⚠️ No IBKR data for {symbol}, using Yahoo fallback")
                            self.yahoo_fallback_symbols.add(symbol)
                    except Exception as e:
                        print(f"⚠️ IBKR subscription failed for {symbol}: {e}")
                        self.yahoo_fallback_symbols.add(symbol)
                        self.subscribed_symbols.add(symbol)
                else:
                    # Yahoo only mode or IBKR not connected
                    self.yahoo_fallback_symbols.add(symbol)
                    self.subscribed_symbols.add(symbol)
                    print(f"📊 Tracking {symbol} via Yahoo Finance")
            
            # Handle unsubscriptions
            for symbol in self.pending_unsubscriptions:
                if self.ibkr and symbol not in self.yahoo_fallback_symbols:
                    try:
                        self.ibkr.unsubscribe_from_stock(symbol)
                    except:
                        pass
                self.subscribed_symbols.discard(symbol)
                self.yahoo_fallback_symbols.discard(symbol)
                print(f"🚫 Unsubscribed from {symbol}")
            
            self.pending_subscriptions = []
            self.pending_unsubscriptions = []
    
    def _cmd_status(self, args: list) -> str:
        """Get current prices for all watched stocks."""
        watchlist = self.watchlist_manager.get_watchlist()
        
        if not watchlist:
            return "📋 Watchlist is empty. Use /watch to add stocks."
        
        lines = ["📊 <b>Current Status</b>", "━━━━━━━━━━━━━━━━━━━━━━"]
        
        for symbol in watchlist.keys():
            price_data = self._get_price(symbol)
            
            if price_data and price_data.get("last", 0) > 0:
                price = price_data["last"]
                source = price_data.get("source", "")
                open_price = self.alert_engine.open_prices.get(symbol, price_data.get("open", 0))
                
                if open_price > 0:
                    change = ((price - open_price) / open_price) * 100
                    lines.append(f"<b>{symbol}</b>: ${price:.2f} ({change:+.2f}%) {source}")
                else:
                    lines.append(f"<b>{symbol}</b>: ${price:.2f} {source}")
            else:
                lines.append(f"<b>{symbol}</b>: Waiting for data...")
        
        lines.append(f"\n🕐 {datetime.now(self.et_tz).strftime('%I:%M:%S %p ET')}")
        return "\n".join(lines)

    def _cmd_health(self, args: list) -> str:
        """Return bot health and runtime state."""
        watchlist = self.watchlist_manager.get_watchlist()
        source = "Yahoo Only" if self.yahoo_only else ("IBKR + Yahoo Fallback" if self.ibkr_connected else "Yahoo Fallback")
        return (
            "✅ <b>Bot Health</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Running: <b>{'Yes' if self.running else 'Starting'}</b>\n"
            f"Data Source: <b>{source}</b>\n"
            f"Tracked Symbols: <b>{len(self.subscribed_symbols) or len(watchlist)}</b>\n"
            f"Yahoo Fallback: <b>{len(self.yahoo_fallback_symbols)}</b>\n"
            f"Time: {datetime.now(self.et_tz).strftime('%I:%M:%S %p ET')}"
        )
    
    def _get_price(self, symbol: str) -> dict:
        """Get price from IBKR or Yahoo (with automatic fallback)."""
        # Try IBKR first (if connected and not in fallback list)
        if self.ibkr and self.ibkr_connected and symbol not in self.yahoo_fallback_symbols:
            data = self.ibkr.get_price(symbol)
            if data and data.get("last", 0) > 0:
                data["source"] = "📡"  # IBKR indicator
                return data
            else:
                # No data from IBKR, add to Yahoo fallback
                self.yahoo_fallback_symbols.add(symbol)
        
        # Fallback to Yahoo
        return self._get_yahoo_price(symbol)
    
    def _get_yahoo_price(self, symbol: str) -> dict:
        """Get price from Yahoo Finance with caching."""
        # Check cache (valid for 5 seconds)
        cache_age = time.time() - self.yahoo_cache_time.get(symbol, 0)
        if cache_age < 5 and symbol in self.yahoo_cache:
            return self.yahoo_cache[symbol]
        
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            
            # Try fast info first
            try:
                info = ticker.fast_info
                price = info.last_price
                if price and price > 0:
                    data = {
                        "symbol": symbol,
                        "last": float(price),
                        "open": float(info.open) if hasattr(info, 'open') and info.open else 0,
                        "high": float(info.day_high) if hasattr(info, 'day_high') and info.day_high else 0,
                        "low": float(info.day_low) if hasattr(info, 'day_low') and info.day_low else 0,
                        "volume": int(info.last_volume) if hasattr(info, 'last_volume') and info.last_volume else 0,
                        "source": "🌐"  # Yahoo indicator
                    }
                    self.yahoo_cache[symbol] = data
                    self.yahoo_cache_time[symbol] = time.time()
                    return data
            except:
                pass
            
            # Fallback to history
            hist = ticker.history(period="1d", interval="1m")
            if len(hist) > 0:
                last_row = hist.iloc[-1]
                result = {
                    "symbol": symbol,
                    "last": float(last_row["Close"]),
                    "open": float(hist.iloc[0]["Open"]),
                    "high": float(hist["High"].max()),
                    "low": float(hist["Low"].min()),
                    "volume": int(hist["Volume"].sum()),
                    "source": "🌐"  # Yahoo indicator
                }
                self.yahoo_cache[symbol] = result
                self.yahoo_cache_time[symbol] = time.time()
                return result
                
        except Exception as e:
            print(f"Yahoo error for {symbol}: {e}")
        
        return {"symbol": symbol, "last": 0, "source": ""}
    
    def on_ibkr_price_update(self, symbol: str, data: dict):
        """Called whenever we receive a price update from IBKR."""
        data["source"] = "📡"
        self.alert_engine.process_price_update(symbol, data)
    
    def is_market_hours(self) -> bool:
        """Check if we're within trading hours."""
        now = datetime.now(self.et_tz)
        current_time = now.time()
        
        if INCLUDE_EXTENDED_HOURS:
            start = dt_time(EXTENDED_HOURS_START, 0)
            end = dt_time(EXTENDED_HOURS_END, 0)
        else:
            start = dt_time(MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE)
            end = dt_time(MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE)
        
        if now.weekday() >= 5:
            return False
        
        return start <= current_time <= end
    
    def start(self):
        """Start the bot."""
        valid, reason = validate_telegram_config()
        if not valid:
            print(f"❌ Telegram config error: {reason}")
            print("Create .env from .env.example and set TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")
            return False

        print("=" * 50)
        print("TRADING ALERT BOT v3")
        print("=" * 50)
        
        mode = "PAPER" if self.paper_trading else "LIVE"
        data_mode = "Yahoo Only" if self.yahoo_only else "IBKR + Yahoo Fallback"
        watchlist = self.watchlist_manager.get_watchlist()
        
        print(f"Mode: {mode}")
        print(f"Data: {data_mode}")
        print(f"Watchlist: {list(watchlist.keys())}")
        print("=" * 50)
        
        # Start Telegram command listener
        print("\n📱 Starting Telegram command listener...")
        self.watchlist_manager.start()
        
        # Try to connect to IBKR (unless yahoo_only)
        if not self.yahoo_only:
            print("\n📡 Connecting to IBKR...")
            try:
                from ibkr_connection import IBKRConnection
                
                port = 7497 if self.paper_trading else IBKR_PORT
                self.ibkr = IBKRConnection(IBKR_HOST, port, IBKR_CLIENT_ID)
                self.ibkr.on_price_update = self.on_ibkr_price_update
                
                if self.ibkr.connect_and_run():
                    self.ibkr_connected = True
                    print("✅ IBKR connected! Will use Yahoo as fallback for unavailable data.")
                    
                    # Subscribe to all watchlist symbols
                    print("\n📊 Subscribing to market data...")
                    for symbol in watchlist.keys():
                        try:
                            self.ibkr.subscribe_to_stock(symbol)
                            self.subscribed_symbols.add(symbol)
                            self.ibkr.sleep(0.5)
                        except Exception as e:
                            print(f"⚠️ IBKR failed for {symbol}, using Yahoo fallback")
                            self.yahoo_fallback_symbols.add(symbol)
                            self.subscribed_symbols.add(symbol)
                else:
                    print("⚠️ IBKR connection failed. Using Yahoo Finance for all data.")
                    self.yahoo_fallback_symbols = set(watchlist.keys())
                    self.subscribed_symbols = set(watchlist.keys())
                    
            except Exception as e:
                print(f"⚠️ IBKR error: {e}. Using Yahoo Finance for all data.")
                self.yahoo_fallback_symbols = set(watchlist.keys())
                self.subscribed_symbols = set(watchlist.keys())
        else:
            print("\n📊 Using Yahoo Finance for all market data")
            self.yahoo_fallback_symbols = set(watchlist.keys())
            self.subscribed_symbols = set(watchlist.keys())
        
        # Wait a moment then check which symbols need Yahoo fallback
        if self.ibkr and self.ibkr_connected:
            print("\n🔍 Checking data availability...")
            time.sleep(3)
            for symbol in list(self.subscribed_symbols):
                if symbol not in self.yahoo_fallback_symbols:
                    data = self.ibkr.get_price(symbol)
                    if not data or data.get("last", 0) == 0:
                        print(f"   ⚠️ {symbol}: No IBKR data → Yahoo fallback")
                        self.yahoo_fallback_symbols.add(symbol)
                    else:
                        print(f"   ✅ {symbol}: IBKR data OK")
        
        # Summary
        if self.yahoo_fallback_symbols:
            print(f"\n📊 Using Yahoo for: {', '.join(self.yahoo_fallback_symbols)}")
        
        # Send startup notification
        send_startup_message(watchlist)
        
        self.running = True
        print("\n" + "=" * 50)
        print("✅ Bot is running!")
        print("📱 Send /help to your Telegram bot for commands")
        print("Press Ctrl+C to stop.")
        print("=" * 50 + "\n")
        
        return True
    
    def run_forever(self):
        """Main loop."""
        last_status_time = datetime.now()
        last_yahoo_update = datetime.now()
        last_heartbeat_time = datetime.now()
        status_interval = 3600  # Print status every hour
        yahoo_interval = 10    # Update Yahoo prices every 10 seconds
        
        try:
            while self.running:
                # Process any pending subscription changes from Telegram commands
                self._process_pending_subscriptions()
                
                # Process IBKR messages if connected
                if self.ibkr and self.ibkr_connected:
                    try:
                        self.ibkr.sleep(0.1)
                    except:
                        self.ibkr_connected = False
                
                # Update Yahoo prices periodically for fallback symbols
                if (datetime.now() - last_yahoo_update).seconds >= yahoo_interval:
                    if self.yahoo_fallback_symbols:
                        self._update_yahoo_prices()
                    last_yahoo_update = datetime.now()
                
                # Periodic status update (to console)
                if (datetime.now() - last_status_time).seconds >= status_interval:
                    self._print_status()
                    last_status_time = datetime.now()

                # Optional Telegram heartbeat for uptime visibility.
                if HEARTBEAT_INTERVAL_MINUTES > 0:
                    elapsed = (datetime.now() - last_heartbeat_time).total_seconds()
                    if elapsed >= HEARTBEAT_INTERVAL_MINUTES * 60:
                        send_telegram_message(self._cmd_health([]))
                        last_heartbeat_time = datetime.now()
                
                # Small sleep to prevent CPU spinning
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Shutdown requested...")
        finally:
            self.stop()
    
    def _update_yahoo_prices(self):
        """Fetch latest prices from Yahoo for fallback symbols and process alerts."""
        for symbol in self.yahoo_fallback_symbols:
            if symbol in self.subscribed_symbols:
                data = self._get_yahoo_price(symbol)
                if data.get("last", 0) > 0:
                    self.alert_engine.process_price_update(symbol, data)
    
    def _print_status(self):
        """Print current status to console."""
        watchlist = self.watchlist_manager.get_watchlist()
        
        print("\n" + "=" * 50)
        print(f"STATUS UPDATE - {datetime.now().strftime('%I:%M:%S %p ET')}")
        print("=" * 50)
        
        for symbol in watchlist.keys():
            data = self._get_price(symbol)
            
            if data and data.get("last", 0) > 0:
                price = data["last"]
                source = data.get("source", "")
                print(f"  {symbol}: ${price:.2f} {source}")
            else:
                print(f"  {symbol}: Waiting for data...")
        
        print("=" * 50 + "\n")
    
    def stop(self):
        """Stop the bot gracefully."""
        self.running = False
        
        print("📱 Stopping Telegram listener...")
        self.watchlist_manager.stop()
        
        print("📤 Sending shutdown notification...")
        send_shutdown_message("Manual shutdown")
        
        if self.ibkr and self.ibkr_connected:
            print("🔌 Disconnecting from IBKR...")
            try:
                self.ibkr.disconnect_all()
            except:
                pass
        
        print("👋 Goodbye!")


def test_telegram():
    """Test Telegram connection."""
    print("Testing Telegram connection...")
    
    success = send_telegram_message(
        "🧪 <b>Test Message</b>\n\n"
        "If you see this, your Telegram bot is working!\n"
        f"Time: {datetime.now().strftime('%I:%M:%S %p')}"
    )
    
    if success:
        print("✅ Telegram test successful! Check your phone.")
    else:
        print("❌ Telegram test failed!")
        print("   Check your bot token and chat ID in config.py")


def main():
    parser = argparse.ArgumentParser(description="Trading Alert Bot v3")
    parser.add_argument("--test", action="store_true", help="Test Telegram connection only")
    parser.add_argument("--paper", action="store_true", help="Use paper trading port (7497)")
    parser.add_argument("--yahoo-only", action="store_true", help="Use only Yahoo Finance (no IBKR)")
    args = parser.parse_args()
    
    if args.test:
        test_telegram()
        return
    
    # Create and run the bot
    bot = TradingAlertBot(paper_trading=args.paper, yahoo_only=args.yahoo_only)
    
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        bot.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start the bot
    if bot.start():
        bot.run_forever()


if __name__ == "__main__":
    main()
