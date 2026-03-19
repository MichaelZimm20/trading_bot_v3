# 🚀 Trading Alert Bot v3

Real-time stock price alerts with **full Telegram control**!

## What's New in v3

- 📱 **Control from Telegram** - Add/remove stocks, set targets, all from your phone
- 📊 **Yahoo Finance option** - Free real-time data (no IBKR subscription needed)
- 🎯 **Dynamic watchlist** - Update your watchlist without restarting the bot

## Telegram Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/watch` | Add stock with price targets | `/watch TSLA 180 200 220` |
| `/unwatch` | Remove stock | `/unwatch TSLA` |
| `/list` | Show watchlist | `/list` |
| `/status` | Get current prices | `/status` |
| `/health` | Show bot runtime health | `/health` |
| `/target` | Add a price target | `/target CRDO 150` |
| `/removetarget` | Remove a target | `/removetarget CRDO 96` |
| `/pct` | Set % move alert | `/pct NVDA 3` |
| `/note` | Add notes to stock | `/note CRDO Watch for earnings` |
| `/ping` | Check if bot is alive | `/ping` |
| `/help` | Show all commands | `/help` |

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# then set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env
```

### 3. Run the Bot

**Option A: With Yahoo Finance (easiest, no IBKR needed)**
```bash
python main.py --yahoo-only
```

**Option B: With IBKR (real-time, requires TWS running)**
```bash
python main.py
```

**Option C: Paper trading mode**
```bash
python main.py --paper
```

### 4. Control via Telegram

Send commands to your bot:
```
/watch AAPL 170 180 190
/watch NVDA 115 125
/status
```

## Features

- **Price Target Alerts** - Get notified when a stock hits your target
- **Percentage Move Alerts** - Alerts when a stock moves X% from open
- **Telegram Control** - Manage everything from your phone
- **Persistent Watchlist** - Telegram edits survive restarts
- **Multiple Data Sources** - IBKR (real-time) or Yahoo Finance (free)
- **Instant Notifications** - Telegram messages arrive in seconds

## Configuration

Set secrets in `.env`:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- optional `HEARTBEAT_INTERVAL_MINUTES`

Edit `config.py` to set:
- IBKR connection settings
- Default watchlist
- Alert cooldown time
- Market hours settings

## File Structure

```
trading_bot_v3/
├── main.py              # Main bot with Telegram commands
├── config.py            # Settings and default watchlist
├── ibkr_connection.py   # IBKR API connection
├── alert_engine.py      # Alert logic
├── telegram_alerts.py   # Outgoing alert messages
├── telegram_commands.py # Incoming command handler
├── requirements.txt     # Dependencies
└── README.md           # This file
```

## Troubleshooting

### Bot not responding to commands?
- Make sure you messaged your bot first
- Check that the chat ID in config.py matches yours
- Verify the bot token is correct

### No price data?
- **IBKR**: Check market data subscriptions, or use `--yahoo` flag
- **Yahoo**: Make sure you're running during market hours

### Connection issues?
- IBKR: Ensure TWS/Gateway is running with API enabled
- Try `--yahoo` flag to bypass IBKR entirely

## Tips

1. **Start simple**: Use `--yahoo` first to test everything works
2. **Set realistic targets**: Don't set targets too close to current price
3. **Use notes**: `/note CRDO IV high, use ITM calls` helps you remember your thesis
4. **Check status**: `/status` before market open to confirm bot is working

## Disclaimer

This bot is for informational purposes only. It does not execute trades. Always do your own research before trading.

---
Made with ❤️ and Claude AI. Good luck trading! 🍀
