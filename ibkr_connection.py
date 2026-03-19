"""
IBKR Connection Module (using ib_insync)
Handles real-time price streaming from Interactive Brokers
"""

from ib_insync import IB, Stock, util
from typing import Dict, Callable, Optional
import threading


class IBKRConnection:
    """
    Handles connection to IBKR TWS/Gateway and streams real-time market data.
    Uses ib_insync for cleaner API.
    """
    
    def __init__(self, host: str, port: int, client_id: int):
        self.host = host
        self.port = port
        self.client_id = client_id
        
        self.ib = IB()
        
        # Store market data
        self.market_data: Dict[str, dict] = {}  # symbol -> {price data}
        self.tickers: Dict[str, object] = {}     # symbol -> ticker object
        
        # Callbacks
        self.on_price_update: Optional[Callable] = None
        
        # Connection status
        self.is_connected = False
    
    def connect_and_run(self) -> bool:
        """Connect to IBKR."""
        try:
            self.ib.connect(self.host, self.port, clientId=self.client_id)
            self.is_connected = self.ib.isConnected()
            
            if self.is_connected:
                print(f"✅ Connected to IBKR at {self.host}:{self.port}")
                
                # Set up disconnect handler
                self.ib.disconnectedEvent += self._on_disconnect
                
            return self.is_connected
            
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def _on_disconnect(self):
        """Handle disconnection."""
        self.is_connected = False
        print("❌ IBKR connection lost")
    
    def _on_pending_tickers(self, tickers):
        """Called when ticker data updates."""
        for ticker in tickers:
            symbol = ticker.contract.symbol
            
            data = {
                "symbol": symbol,
                "last": ticker.last if ticker.last == ticker.last else 0,  # NaN check
                "bid": ticker.bid if ticker.bid == ticker.bid else 0,
                "ask": ticker.ask if ticker.ask == ticker.ask else 0,
                "open": ticker.open if ticker.open == ticker.open else 0,
                "high": ticker.high if ticker.high == ticker.high else 0,
                "low": ticker.low if ticker.low == ticker.low else 0,
                "close": ticker.close if ticker.close == ticker.close else 0,
                "volume": int(ticker.volume) if ticker.volume == ticker.volume else 0,
            }
            
            # Use mid price if last is not available
            if data["last"] == 0 and data["bid"] > 0 and data["ask"] > 0:
                data["last"] = (data["bid"] + data["ask"]) / 2
            
            self.market_data[symbol] = data
            
            # Trigger callback
            if self.on_price_update and data["last"] > 0:
                self.on_price_update(symbol, data)
    
    def subscribe_to_stock(self, symbol: str):
        """Subscribe to real-time data for a stock."""
        contract = Stock(symbol, 'SMART', 'USD')
        
        # Qualify the contract (gets full details from IBKR)
        self.ib.qualifyContracts(contract)
        
        # Request market data
        ticker = self.ib.reqMktData(contract, '', False, False)
        
        # Set up callback for this ticker
        ticker.updateEvent += lambda t: self._on_pending_tickers([t])
        
        self.tickers[symbol] = ticker
        self.market_data[symbol] = {
            "symbol": symbol,
            "last": 0, "bid": 0, "ask": 0,
            "open": 0, "high": 0, "low": 0, "close": 0,
            "volume": 0
        }
        
        print(f"📊 Subscribed to {symbol}")
    
    def unsubscribe_from_stock(self, symbol: str):
        """Unsubscribe from a stock's market data."""
        if symbol in self.tickers:
            self.ib.cancelMktData(self.tickers[symbol].contract)
            del self.tickers[symbol]
            if symbol in self.market_data:
                del self.market_data[symbol]
            print(f"🚫 Unsubscribed from {symbol}")
    
    def get_price(self, symbol: str) -> Optional[dict]:
        """Get current price data for a symbol."""
        return self.market_data.get(symbol)
    
    def sleep(self, seconds: float = 0.1):
        """Process IBKR messages for a duration."""
        self.ib.sleep(seconds)
    
    def disconnect_all(self):
        """Disconnect from IBKR."""
        if self.ib.isConnected():
            self.ib.disconnect()
        self.is_connected = False
        print("🔌 Disconnected from IBKR")


# Quick test
if __name__ == "__main__":
    from config import IBKR_HOST, IBKR_PORT, IBKR_CLIENT_ID
    
    print("Testing IBKR connection...")
    
    def on_update(symbol, data):
        print(f"{symbol}: ${data['last']:.2f} (bid: {data['bid']:.2f}, ask: {data['ask']:.2f})")
    
    conn = IBKRConnection(IBKR_HOST, IBKR_PORT, IBKR_CLIENT_ID)
    conn.on_price_update = on_update
    
    if conn.connect_and_run():
        print("Connected! Subscribing to AAPL...")
        conn.subscribe_to_stock("AAPL")
        
        # Run for 30 seconds
        for _ in range(300):
            conn.sleep(0.1)
        
        conn.disconnect_all()
    else:
        print("Failed to connect to IBKR. Make sure TWS/Gateway is running.")
