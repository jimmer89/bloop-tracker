# Bloop Tracker v5

Webhook server for capturing signals from the Bloop Indicator (TradingView) and calculating P&L with real broker spread data.

## Overview

Receives trading signals via webhook, tracks open positions, and calculates both gross and net P&L accounting for broker spread. Designed for USTEC.

## Stack

- **Backend:** Flask + Gunicorn
- **Database:** PostgreSQL
- **Hosting:** Hetzner VPS, managed via systemd + nginx
- **Spread monitoring:** MQL5 EA on MetaTrader 5

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook` | POST | Receive signals from TradingView |
| `/stats` | GET | Statistics (gross vs net P&L) |
| `/trades` | GET | Trade history with net P&L (auth required) |
| `/signals` | GET | Raw signals (auth required) |
| `/position` | GET | Current open position (auth required) |
| `/spread` | GET/POST | View/update spread config |
| `/recalculate` | POST | Recalculate historical net P&L |
| `/health` | GET | Health check + version |

## TradingView Alert Setup

Set the webhook URL to your deployment endpoint. Include the `secret` field in the JSON body for authentication.

```json
{"signal": "LONG", "price": {{close}}, "symbol": "USTEC"}
{"signal": "SHORT", "price": {{close}}, "symbol": "USTEC"}
```

Optional optimization fields:

```json
{
  "signal": "LONG",
  "price": {{close}},
  "symbol": "USTEC",
  "atr": {{plot("ATR")}},
  "tp1": {{plot("TP1")}},
  "tp2": {{plot("TP2")}},
  "sl": {{plot("SL")}}
}
```

## Changelog

- **v5.1** — VPS migration, auth on read endpoints, security hardening
- **v5** — Real spread integration, gross vs net P&L, `/recalculate` endpoint
- **v4** — Optimization data support (ATR, TP, SL)
- **v3** — PostgreSQL migration
- **v2** — P&L tracking
- **v1** — Basic webhook with signal capture

## License

MIT
