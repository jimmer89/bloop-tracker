# AGENTS.md — Bloop Tracker

Webhook server that captures signals from the Bloop indicator (TradingView) for USTEC and calculates P&L with real spread.

## Stack

- **Runtime:** Python 3.11+, Flask, Gunicorn
- **Database:** PostgreSQL (via psycopg2)
- **Hosting:** Hetzner VPS at bloop.jimmer89.xyz (migrated from Railway 2026-02-17)

## Project Structure

```
bloop-tracker/
├── webhook_server.py   # Main app — Flask endpoints, P&L logic
├── requirements.txt    # flask, gunicorn, psycopg2-binary
├── start.sh           # Gunicorn launch script
├── Procfile           # Railway/Heroku process definition
├── railway.json       # Railway deploy config
├── pinescript/        # Bloop clone attempts (PineScript v5)
├── MASTER_PLAN.md
└── REVERSE_ENGINEERING.md
```

## Setup

```bash
cd ~/bloop-tracker
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## Running

### Development
```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/bloop"
export WEBHOOK_SECRET="your-secret"
python webhook_server.py
```

### Production
```bash
gunicorn webhook_server:app --bind 0.0.0.0:$PORT
```

## Environment Variables

- `DATABASE_URL` — PostgreSQL connection string (required)
- `WEBHOOK_SECRET` — Auth token for write endpoints (required, sent in `X-Webhook-Secret` header)
- `PORT` — Server port (default: 5000)

## API Endpoints

All write endpoints require `X-Webhook-Secret` header matching `WEBHOOK_SECRET`.

- `POST /webhook` — Receive TradingView alert (signal data)
- `GET /trades` — List all captured trades
- `GET /stats` — P&L summary with spread calculations
- `GET /health` — Health check

## Key Context

- **Spread:** IC Markets Standard USTEC = 0.9 pts in price scale (90 "points" in broker notation). Already accounted for in P&L calculations.
- **Data insights:** Trades < 15 min are 100% losers (flip-flops). Best hours: 13-14 UTC. Worst: 17-18, 23 UTC.
- **TradingView alert** sends JSON to `/webhook` with signal direction, price, and indicator data.

## Code Style

- Single-file Flask app. Keep it that way — this is a simple webhook server, not a framework.
- Auth via decorator `@require_auth` on write endpoints.
- P&L includes spread cost in calculations (fixed at 0.9 pts).

## What NOT to Do

- Don't add an ORM. Raw SQL with psycopg2 is fine for this scale.
- Don't split into multiple files unless it exceeds 500 lines.
- Don't add a frontend. Data analysis happens externally.
