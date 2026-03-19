"""
Alert Engine
Monitors real-time prices and triggers alerts based on your rules
"""

from datetime import datetime, timedelta
from typing import Dict, Set, Optional
from config import WATCHLIST, ALERT_COOLDOWN
from telegram_alerts import (
    send_price_target_alert,
    send_percent_move_alert,
    send_volume_spike_alert,
    send_error_alert
)


class AlertEngine:
    """
    Monitors price data and triggers alerts when conditions are met.
    """
    
    def __init__(self, watchlist: dict = WATCHLIST):
        self.watchlist = watchlist
        
        # Track which alerts have been triggered (to prevent spam)
        # Format: {("SYMBOL", "alert_type", "value"): last_triggered_time}
        self.triggered_alerts: Dict[tuple, datetime] = {}
        
        # Track open prices for % move calculations
        self.open_prices: Dict[str, float] = {}
        
        # Track if we've captured the open yet
        self.captured_open: Set[str] = set()

        # Track previous seen price to detect target crossings reliably.
        self.last_prices: Dict[str, float] = {}
    
    def process_price_update(self, symbol: str, data: dict):
        """
        Process a price update and check all alert conditions.
        
        data format: {
            "symbol": str,
            "last": float,
            "bid": float,
            "ask": float,
            "open": float,
            "high": float,
            "low": float,
            "close": float,  # previous day close
            "volume": int
        }
        """
        if symbol not in self.watchlist:
            return
        
        config = self.watchlist[symbol]
        current_price = data.get("last", 0)
        
        if current_price <= 0:
            return  # No valid price yet
        
        # Capture the open price
        open_price = data.get("open", 0)
        if open_price > 0 and symbol not in self.captured_open:
            self.open_prices[symbol] = open_price
            self.captured_open.add(symbol)
        
        # Get notes for this symbol
        notes = config.get("notes", "")
        
        # Check price targets
        self._check_price_targets(symbol, current_price, config, notes)
        
        # Check percentage moves
        self._check_percent_move(symbol, current_price, config, notes)
        
        # Check volume spikes (if we have volume data)
        # self._check_volume_spike(symbol, data, config, notes)

        # Save latest price after checks so crossing detection compares consecutive ticks.
        self.last_prices[symbol] = current_price
    
    def _check_price_targets(self, symbol: str, current_price: float, config: dict, notes: str):
        """Check if any price targets have been hit."""
        price_targets = config.get("price_targets", [])
        prev_price = self.last_prices.get(symbol)
        
        for target in price_targets:
            alert_key = (symbol, "price_target", target)
            
            # Trigger if price crossed target between updates, or is currently near target.
            tolerance = target * 0.005  # 0.5%
            crossed = (
                prev_price is not None
                and ((prev_price < target <= current_price) or (prev_price > target >= current_price))
            )
            near_target = abs(current_price - target) <= tolerance

            if crossed or near_target:
                if self._can_trigger_alert(alert_key):
                    # Calculate change from previous close
                    prev_close = config.get("prev_close", current_price)
                    change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close else 0
                    
                    print(f"🎯 Price target hit: {symbol} @ ${current_price:.2f} (target: ${target:.2f})")
                    send_price_target_alert(symbol, target, current_price, change_pct, notes)
                    self._mark_alert_triggered(alert_key)
    
    def _check_percent_move(self, symbol: str, current_price: float, config: dict, notes: str):
        """Check if the stock has moved more than X% from open."""
        threshold = config.get("pct_move")
        if not threshold:
            return
        
        open_price = self.open_prices.get(symbol)
        if not open_price or open_price <= 0:
            return
        
        change_pct = ((current_price - open_price) / open_price) * 100
        
        # Check if move exceeds threshold (in either direction)
        if abs(change_pct) >= threshold:
            # Create unique key for this threshold breach
            direction = "up" if change_pct > 0 else "down"
            alert_key = (symbol, "pct_move", f"{direction}_{threshold}")
            
            if self._can_trigger_alert(alert_key):
                print(f"🚀 Big move: {symbol} {change_pct:+.2f}% (threshold: {threshold}%)")
                send_percent_move_alert(symbol, current_price, open_price, change_pct, threshold, notes)
                self._mark_alert_triggered(alert_key)
    
    def _check_volume_spike(self, symbol: str, data: dict, config: dict, notes: str):
        """Check if volume is spiking."""
        spike_threshold = config.get("volume_spike")
        if not spike_threshold:
            return
        
        current_volume = data.get("volume", 0)
        avg_volume = config.get("avg_volume", 0)
        
        if not avg_volume or avg_volume <= 0:
            return
        
        spike_ratio = current_volume / avg_volume
        
        if spike_ratio >= spike_threshold:
            alert_key = (symbol, "volume_spike", int(spike_ratio))
            
            if self._can_trigger_alert(alert_key):
                current_price = data.get("last", 0)
                print(f"📊 Volume spike: {symbol} {spike_ratio:.1f}x average")
                send_volume_spike_alert(symbol, current_volume, avg_volume, spike_ratio, current_price, notes)
                self._mark_alert_triggered(alert_key)
    
    def _can_trigger_alert(self, alert_key: tuple) -> bool:
        """Check if enough time has passed since last alert of this type."""
        if alert_key not in self.triggered_alerts:
            return True
        
        last_triggered = self.triggered_alerts[alert_key]
        cooldown = timedelta(seconds=ALERT_COOLDOWN)
        
        return datetime.now() - last_triggered > cooldown
    
    def _mark_alert_triggered(self, alert_key: tuple):
        """Record that an alert was triggered."""
        self.triggered_alerts[alert_key] = datetime.now()
    
    def reset_daily(self):
        """Reset daily tracking (call at market open)."""
        self.triggered_alerts.clear()
        self.open_prices.clear()
        self.captured_open.clear()
        self.last_prices.clear()
        print("📅 Daily reset complete")
    
    def update_watchlist(self, new_watchlist: dict):
        """Update the watchlist dynamically."""
        self.watchlist = new_watchlist
        print(f"📝 Watchlist updated: {list(new_watchlist.keys())}")
    
    def add_symbol(self, symbol: str, config: dict):
        """Add a symbol to the watchlist."""
        self.watchlist[symbol] = config
        print(f"➕ Added {symbol} to watchlist")
    
    def remove_symbol(self, symbol: str):
        """Remove a symbol from the watchlist."""
        if symbol in self.watchlist:
            del self.watchlist[symbol]
            print(f"➖ Removed {symbol} from watchlist")


# Test
if __name__ == "__main__":
    engine = AlertEngine()
    
    # Simulate a price update
    test_data = {
        "symbol": "CRDO",
        "last": 96.05,  # Near price target
        "open": 92.00,
        "high": 97.00,
        "low": 91.50,
        "close": 93.00,
        "volume": 1500000
    }
    
    print("Testing alert engine with CRDO @ $96.05...")
    engine.open_prices["CRDO"] = 92.00
    engine.captured_open.add("CRDO")
    engine.process_price_update("CRDO", test_data)
