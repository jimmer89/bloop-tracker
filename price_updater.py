#!/usr/bin/env python3
"""
Price Updater Daemon — Bloop Tracker
Tracks NQ=F price deltas from Yahoo Finance and applies them to the last known
IC Markets USTEC price, so max/min tracking stays in the correct price scale.

The problem: Yahoo NQ=F and IC Markets USTEC have a ~190pt offset.
The solution: Only use Yahoo for MOVEMENT (delta), apply it to the last
IC Markets price from the webhook (LONG/SHORT signal entry/exit prices).
"""

import json
import os
import time
import urllib.request
import sys
from datetime import datetime, timezone

WEBHOOK_URL = "http://127.0.0.1:5555/webhook"
STATS_URL = "http://127.0.0.1:5555/stats"
SYMBOL = "USTEC"
INTERVAL_SECONDS = 60

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/NQ=F?interval=1m&range=1m"


def get_webhook_secret():
    """Read secret from .env file."""
    try:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        with open(env_path) as f:
            for line in f:
                if line.startswith("WEBHOOK_SECRET="):
                    return line.strip().split("=", 1)[1]
    except FileNotFoundError:
        pass
    return os.environ.get("WEBHOOK_SECRET", "")


def fetch_nq_price():
    """Fetch current NQ futures price from Yahoo Finance."""
    req = urllib.request.Request(YAHOO_URL, headers={
        "User-Agent": "Mozilla/5.0 (compatible; BloopTracker/1.0)"
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())

    result = data["chart"]["result"][0]
    price = result["meta"]["regularMarketPrice"]
    return round(price, 2)


def get_last_ic_price():
    """Get the last known IC Markets price from the open position or last trade."""
    with urllib.request.urlopen(STATS_URL, timeout=10) as resp:
        data = json.loads(resp.read().decode())

    pos = data.get("open_position")
    if pos and pos.get("entry_price"):
        return pos["entry_price"]
    return None


def send_price_update(price, secret):
    """Send PRICE_UPDATE to local webhook."""
    payload = json.dumps({
        "signal": "PRICE_UPDATE",
        "price": price,
        "symbol": SYMBOL,
        "secret": secret,
    }).encode()

    req = urllib.request.Request(
        WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def main():
    secret = get_webhook_secret()
    if not secret:
        print("ERROR: No WEBHOOK_SECRET found")
        sys.exit(1)

    print(f"Bloop Price Updater (delta mode) — polling every {INTERVAL_SECONDS}s")
    print(f"Webhook: {WEBHOOK_URL}")

    consecutive_errors = 0
    prev_nq = None       # Previous NQ=F price for delta calculation
    ic_baseline = None   # Last known IC Markets price (anchor point)

    while True:
        try:
            nq_price = fetch_nq_price()
            now = datetime.now(timezone.utc).strftime("%H:%M:%S")

            if prev_nq is None:
                # First tick: calibrate against IC Markets price
                ic_baseline = get_last_ic_price()
                if ic_baseline is None:
                    print(f"[{now}] No open position, waiting for IC Markets price...")
                    prev_nq = nq_price
                    time.sleep(INTERVAL_SECONDS)
                    continue
                prev_nq = nq_price
                estimated_price = ic_baseline
                print(f"[{now}] Calibrated: NQ={nq_price:.2f}, IC baseline={ic_baseline:.2f}")
            else:
                # Calculate delta from NQ movement
                delta = nq_price - prev_nq
                prev_nq = nq_price

                # Check if IC Markets sent a new signal (recalibrate)
                current_ic = get_last_ic_price()
                if current_ic and current_ic != ic_baseline:
                    ic_baseline = current_ic
                    estimated_price = ic_baseline
                    print(f"[{now}] Recalibrated: new IC price={ic_baseline:.2f}")
                else:
                    ic_baseline += delta
                    estimated_price = ic_baseline

            result = send_price_update(round(estimated_price, 2), secret)
            print(f"[{now}] PRICE_UPDATE @ {estimated_price:.2f} (NQ={nq_price:.2f}, delta={nq_price - (prev_nq or nq_price):+.2f}) — signals: {result.get('total_signals', '?')}")
            consecutive_errors = 0

        except Exception as e:
            consecutive_errors += 1
            now = datetime.now(timezone.utc).strftime("%H:%M:%S")
            print(f"[{now}] ERROR ({consecutive_errors}): {e}")
            if consecutive_errors >= 10:
                print("Too many consecutive errors, sleeping 5 min")
                time.sleep(300)
                consecutive_errors = 0

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
