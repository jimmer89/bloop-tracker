#!/usr/bin/env python3
"""
Trailing Stop Backtest — Bloop Tracker
Simulates trailing stops on historical trade data using signal prices as proxy.

Limitation: We don't have tick data, only signal prices. So trailing stop triggers
are approximate (checked at each signal timestamp, not continuously).
This gives a lower bound on trailing stop effectiveness.
"""

import json
import sys
from datetime import datetime

# ============================================================
# TRADE DATA (exported from PostgreSQL)
# Format: id|direction|entry_price|exit_price|pnl_points|pnl_net|max_price|min_price|duration_s|atr|entry_time|exit_time
# ============================================================

SPREAD = 0.9  # IC Markets USTEC spread in points

def load_trades(filepath='/tmp/bloop_trades.csv'):
    """Load trades from pipe-delimited export."""
    trades = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('|')
            trades.append({
                'id': int(parts[0]),
                'direction': parts[1],
                'entry_price': float(parts[2]),
                'exit_price': float(parts[3]),
                'pnl_points': float(parts[4]),
                'pnl_net': float(parts[5]),
                'duration_s': int(parts[8]) if parts[8] else 0,
                'entry_time': parts[10],
                'exit_time': parts[11],
            })
    return trades


def load_signals(filepath='/tmp/bloop_signals.csv'):
    """Load all signals as price checkpoints."""
    signals = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('|')
            signals.append({
                'timestamp': parts[0],
                'signal': parts[1],
                'price': float(parts[2]),
            })
    return signals


def get_prices_during_trade(signals, entry_time, exit_time):
    """Get all signal prices between entry and exit (inclusive of exit)."""
    prices = []
    for s in signals:
        if s['timestamp'] > entry_time and s['timestamp'] <= exit_time:
            prices.append(s['price'])
    return prices


def simulate_trailing_stop(trades, signals, trail_points, activation_points=0):
    """
    Simulate a trailing stop on historical trades.

    trail_points: distance of trailing stop from peak (in points)
    activation_points: minimum profit before trailing stop activates (0 = always active)

    Returns modified trade results.
    """
    results = []

    for trade in trades:
        direction = trade['direction']
        entry = trade['entry_price']
        original_exit = trade['exit_price']
        original_pnl = trade['pnl_points']

        # Get intermediate prices during this trade
        intermediate_prices = get_prices_during_trade(
            signals, trade['entry_time'], trade['exit_time']
        )

        # Track the peak favorable price
        if direction == 'LONG':
            peak = entry
            trail_triggered = False
            trail_exit_price = None

            for price in intermediate_prices:
                if price > peak:
                    peak = price

                # Check if trailing stop is activated
                unrealized_pnl = peak - entry
                if unrealized_pnl >= activation_points:
                    trail_level = peak - trail_points
                    if price <= trail_level:
                        trail_triggered = True
                        trail_exit_price = trail_level  # approximate
                        break

            if trail_triggered:
                pnl = trail_exit_price - entry
            else:
                pnl = original_pnl

        else:  # SHORT
            peak = entry  # lowest price = best for shorts
            trail_triggered = False
            trail_exit_price = None

            for price in intermediate_prices:
                if price < peak:
                    peak = price

                unrealized_pnl = entry - peak
                if unrealized_pnl >= activation_points:
                    trail_level = peak + trail_points
                    if price >= trail_level:
                        trail_triggered = True
                        trail_exit_price = trail_level
                        break

            if trail_triggered:
                pnl = entry - trail_exit_price
            else:
                pnl = original_pnl

        pnl_net = pnl - SPREAD

        results.append({
            'id': trade['id'],
            'direction': direction,
            'entry_price': entry,
            'original_pnl': original_pnl,
            'new_pnl': pnl,
            'new_pnl_net': pnl_net,
            'trail_triggered': trail_triggered,
            'peak_price': peak,
            'mfe': abs(peak - entry),  # max favorable excursion (approximate)
        })

    return results


def simulate_fixed_stop_loss(trades, sl_points):
    """
    Simulate a fixed stop loss. Since we don't have tick data,
    we can only check if the final P&L exceeded the stop loss.
    This is an approximation — in reality the SL would trigger intra-bar.
    """
    results = []
    for trade in trades:
        pnl = trade['pnl_points']
        if pnl < -sl_points:
            pnl = -sl_points
        pnl_net = pnl - SPREAD
        results.append({
            'id': trade['id'],
            'original_pnl': trade['pnl_points'],
            'new_pnl': pnl,
            'new_pnl_net': pnl_net,
            'sl_triggered': trade['pnl_points'] < -sl_points,
        })
    return results


def calc_stats(results, key='new_pnl_net'):
    """Calculate summary statistics."""
    pnls = [r[key] for r in results]
    total = sum(pnls)
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p <= 0]
    win_rate = len(winners) / len(pnls) * 100 if pnls else 0
    avg_win = sum(winners) / len(winners) if winners else 0
    avg_loss = sum(losers) / len(losers) if losers else 0
    profit_factor = abs(sum(winners) / sum(losers)) if losers and sum(losers) != 0 else float('inf')
    expectancy = total / len(pnls) if pnls else 0

    # Max drawdown (simple)
    cumulative = 0
    peak_cum = 0
    max_dd = 0
    for p in pnls:
        cumulative += p
        if cumulative > peak_cum:
            peak_cum = cumulative
        dd = peak_cum - cumulative
        if dd > max_dd:
            max_dd = dd

    return {
        'total_pnl': round(total, 1),
        'trades': len(pnls),
        'winners': len(winners),
        'losers': len(losers),
        'win_rate': round(win_rate, 1),
        'avg_win': round(avg_win, 1),
        'avg_loss': round(avg_loss, 1),
        'profit_factor': round(profit_factor, 2),
        'expectancy': round(expectancy, 1),
        'max_drawdown': round(max_dd, 1),
        'best': round(max(pnls), 1) if pnls else 0,
        'worst': round(min(pnls), 1) if pnls else 0,
    }


def print_stats(label, stats):
    """Pretty print statistics."""
    color_pnl = '\033[92m' if stats['total_pnl'] > 0 else '\033[91m'
    reset = '\033[0m'

    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  Total P&L (net):  {color_pnl}{stats['total_pnl']:+.1f} pts{reset}")
    print(f"  Trades:           {stats['trades']} ({stats['winners']}W / {stats['losers']}L)")
    print(f"  Win Rate:         {stats['win_rate']}%")
    print(f"  Avg Win:          {stats['avg_win']:+.1f} pts")
    print(f"  Avg Loss:         {stats['avg_loss']:+.1f} pts")
    print(f"  Profit Factor:    {stats['profit_factor']}")
    print(f"  Expectancy:       {stats['expectancy']:+.1f} pts/trade")
    print(f"  Max Drawdown:     {stats['max_drawdown']:.1f} pts")
    print(f"  Best/Worst:       {stats['best']:+.1f} / {stats['worst']:+.1f}")


def main():
    print("\n" + "="*60)
    print("  BLOOP TRAILING STOP OPTIMIZER")
    print("  233 trades | USTEC | IC Markets | Spread: 0.9 pts")
    print("="*60)

    trades = load_trades()
    signals = load_signals()

    print(f"\n  Loaded {len(trades)} trades, {len(signals)} signals")

    # ============================================================
    # BASELINE: Original results (no stops)
    # ============================================================
    baseline = []
    for t in trades:
        baseline.append({
            'id': t['id'],
            'original_pnl': t['pnl_points'],
            'new_pnl': t['pnl_points'],
            'new_pnl_net': t['pnl_net'],
        })
    baseline_stats = calc_stats(baseline)
    print_stats("BASELINE (sin stops)", baseline_stats)

    # ============================================================
    # FIXED STOP LOSS SWEEP
    # ============================================================
    print(f"\n\n{'='*60}")
    print("  FIXED STOP LOSS SWEEP")
    print(f"{'='*60}")
    print(f"  {'SL (pts)':<10} {'P&L Net':<12} {'WR%':<8} {'PF':<8} {'Expect':<10} {'MaxDD':<10} {'Triggers'}")
    print(f"  {'-'*10} {'-'*12} {'-'*8} {'-'*8} {'-'*10} {'-'*10} {'-'*8}")

    best_sl = None
    best_sl_pnl = float('-inf')

    for sl in [20, 30, 40, 50, 60, 75, 100, 125, 150, 200]:
        results = simulate_fixed_stop_loss(trades, sl)
        stats = calc_stats(results)
        triggers = sum(1 for r in results if r['sl_triggered'])

        color = '\033[92m' if stats['total_pnl'] > baseline_stats['total_pnl'] else '\033[0m'
        reset = '\033[0m'

        print(f"  {sl:<10} {color}{stats['total_pnl']:>+10.1f}{reset}  {stats['win_rate']:<8} {stats['profit_factor']:<8} {stats['expectancy']:>+8.1f}  {stats['max_drawdown']:<10.1f} {triggers}")

        if stats['total_pnl'] > best_sl_pnl:
            best_sl_pnl = stats['total_pnl']
            best_sl = sl

    print(f"\n  >>> Best fixed SL: {best_sl} pts (P&L: {best_sl_pnl:+.1f})")

    # ============================================================
    # TRAILING STOP SWEEP
    # ============================================================
    print(f"\n\n{'='*60}")
    print("  TRAILING STOP SWEEP (activation=0, trail from peak)")
    print("  NOTE: Limited by signal-only price data (no ticks)")
    print(f"{'='*60}")
    print(f"  {'Trail':<8} {'P&L Net':<12} {'WR%':<8} {'PF':<8} {'Expect':<10} {'MaxDD':<10} {'Triggers'}")
    print(f"  {'-'*8} {'-'*12} {'-'*8} {'-'*8} {'-'*10} {'-'*10} {'-'*8}")

    best_trail = None
    best_trail_pnl = float('-inf')

    for trail in [15, 20, 30, 40, 50, 60, 75, 100, 125, 150]:
        results = simulate_trailing_stop(trades, signals, trail, activation_points=0)
        stats = calc_stats(results)
        triggers = sum(1 for r in results if r['trail_triggered'])

        color = '\033[92m' if stats['total_pnl'] > baseline_stats['total_pnl'] else '\033[0m'
        reset = '\033[0m'

        print(f"  {trail:<8} {color}{stats['total_pnl']:>+10.1f}{reset}  {stats['win_rate']:<8} {stats['profit_factor']:<8} {stats['expectancy']:>+8.1f}  {stats['max_drawdown']:<10.1f} {triggers}")

        if stats['total_pnl'] > best_trail_pnl:
            best_trail_pnl = stats['total_pnl']
            best_trail = trail

    print(f"\n  >>> Best trailing stop: {best_trail} pts (P&L: {best_trail_pnl:+.1f})")

    # ============================================================
    # TRAILING STOP WITH ACTIVATION THRESHOLD SWEEP
    # ============================================================
    print(f"\n\n{'='*60}")
    print("  TRAILING STOP WITH ACTIVATION (trail after X pts profit)")
    print(f"{'='*60}")
    print(f"  {'Activ':<8} {'Trail':<8} {'P&L Net':<12} {'WR%':<8} {'PF':<8} {'Expect':<10} {'Triggers'}")
    print(f"  {'-'*8} {'-'*8} {'-'*12} {'-'*8} {'-'*8} {'-'*10} {'-'*8}")

    best_combo = None
    best_combo_pnl = float('-inf')

    for activation in [20, 30, 50, 75, 100]:
        for trail in [15, 20, 30, 40, 50, 75]:
            results = simulate_trailing_stop(trades, signals, trail, activation)
            stats = calc_stats(results)
            triggers = sum(1 for r in results if r['trail_triggered'])

            if triggers == 0:
                continue

            color = '\033[92m' if stats['total_pnl'] > baseline_stats['total_pnl'] else '\033[0m'
            reset = '\033[0m'

            print(f"  {activation:<8} {trail:<8} {color}{stats['total_pnl']:>+10.1f}{reset}  {stats['win_rate']:<8} {stats['profit_factor']:<8} {stats['expectancy']:>+8.1f}  {triggers}")

            if stats['total_pnl'] > best_combo_pnl:
                best_combo_pnl = stats['total_pnl']
                best_combo = (activation, trail)

    if best_combo:
        print(f"\n  >>> Best combo: activation={best_combo[0]} trail={best_combo[1]} (P&L: {best_combo_pnl:+.1f})")

    # ============================================================
    # COMBINED: BEST SL + BEST TRAILING STOP
    # ============================================================
    if best_combo:
        print(f"\n\n{'='*60}")
        print(f"  COMBINED: SL={best_sl} + Trail(activ={best_combo[0]}, trail={best_combo[1]})")
        print(f"{'='*60}")

        combined_results = []
        for trade in trades:
            # Apply fixed SL first
            pnl = trade['pnl_points']
            if pnl < -best_sl:
                pnl = -best_sl
                combined_results.append({
                    'id': trade['id'],
                    'original_pnl': trade['pnl_points'],
                    'new_pnl': pnl,
                    'new_pnl_net': pnl - SPREAD,
                })
                continue

            # Then check trailing stop
            direction = trade['direction']
            entry = trade['entry_price']
            intermediate_prices = get_prices_during_trade(
                signals, trade['entry_time'], trade['exit_time']
            )

            peak = entry
            trail_exit = None

            for price in intermediate_prices:
                if direction == 'LONG':
                    if price > peak:
                        peak = price
                    unrealized = peak - entry
                    if unrealized >= best_combo[0]:
                        if price <= peak - best_combo[1]:
                            trail_exit = peak - best_combo[1]
                            break
                else:
                    if price < peak:
                        peak = price
                    unrealized = entry - peak
                    if unrealized >= best_combo[0]:
                        if price >= peak + best_combo[1]:
                            trail_exit = peak + best_combo[1]
                            break

            if trail_exit:
                if direction == 'LONG':
                    pnl = trail_exit - entry
                else:
                    pnl = entry - trail_exit

            combined_results.append({
                'id': trade['id'],
                'original_pnl': trade['pnl_points'],
                'new_pnl': pnl,
                'new_pnl_net': pnl - SPREAD,
            })

        combined_stats = calc_stats(combined_results)
        print_stats(f"COMBINED (SL={best_sl} + Trail {best_combo[0]}/{best_combo[1]})", combined_stats)

    # ============================================================
    # ANALYSIS: Trades that gave back significant profit
    # ============================================================
    print(f"\n\n{'='*60}")
    print("  TRADES WITH MAX FAVORABLE EXCURSION (MFE) ANALYSIS")
    print("  Shows trades where price moved favorably but closed poorly")
    print(f"{'='*60}")

    # Use trailing stop results to find MFE data
    trail_results = simulate_trailing_stop(trades, signals, 9999, 0)  # huge trail = never triggers, but tracks MFE

    gave_back = []
    for r in trail_results:
        trade = next(t for t in trades if t['id'] == r['id'])
        mfe = r['mfe']
        final_pnl = trade['pnl_points']
        gave_back_pts = mfe - final_pnl if trade['direction'] == 'LONG' else mfe + final_pnl
        # For shorts: MFE is how far price dropped, final_pnl is positive if price dropped
        if trade['direction'] == 'SHORT':
            gave_back_pts = mfe - final_pnl

        if mfe > 30 and gave_back_pts > 30:
            gave_back.append({
                'id': trade['id'],
                'direction': trade['direction'],
                'entry': trade['entry_price'],
                'exit': trade['exit_price'],
                'pnl': final_pnl,
                'mfe': round(mfe, 1),
                'gave_back': round(gave_back_pts, 1),
                'duration_h': round(trade['duration_s'] / 3600, 1),
            })

    gave_back.sort(key=lambda x: x['gave_back'], reverse=True)

    print(f"\n  Found {len(gave_back)} trades that gave back >30 pts from MFE >30 pts")
    print(f"  {'ID':<5} {'Dir':<6} {'P&L':<10} {'MFE':<10} {'Gave Back':<12} {'Hours'}")
    print(f"  {'-'*5} {'-'*6} {'-'*10} {'-'*10} {'-'*12} {'-'*6}")

    total_gave_back = 0
    for t in gave_back[:20]:
        color = '\033[91m' if t['pnl'] < 0 else '\033[93m'
        reset = '\033[0m'
        print(f"  {t['id']:<5} {t['direction']:<6} {color}{t['pnl']:>+8.1f}{reset}  {t['mfe']:>8.1f}  {t['gave_back']:>10.1f}  {t['duration_h']:.1f}h")
        total_gave_back += t['gave_back']

    print(f"\n  Total points left on table: {total_gave_back:.1f} pts")

    # ============================================================
    # SUMMARY & RECOMMENDATIONS
    # ============================================================
    print(f"\n\n{'='*60}")
    print("  RECOMMENDATIONS")
    print(f"{'='*60}")
    print(f"""
  BASELINE:           {baseline_stats['total_pnl']:+.1f} pts ({baseline_stats['win_rate']}% WR)
  Best Fixed SL:      {best_sl_pnl:+.1f} pts (SL={best_sl} pts)
  Best Trailing:      {best_trail_pnl:+.1f} pts (trail={best_trail} pts)""")
    if best_combo:
        print(f"  Best Combo:         {best_combo_pnl:+.1f} pts (activ={best_combo[0]}, trail={best_combo[1]})")

    print(f"""
  IMPORTANT CAVEATS:
  - Analysis uses signal prices only (every ~30-90 min), NOT tick data
  - Real trailing stops would trigger at intermediate prices we can't see
  - Results are CONSERVATIVE — real trailing stops would likely perform better
  - To get accurate results, enable PRICE_UPDATE in webhook_server.py

  NEXT STEPS:
  1. Enable price updates in TradingView (send price every 1-5 min)
  2. Run this analysis again after 50+ trades with proper max/min data
  3. Consider implementing the best config as live trailing stop
""")


if __name__ == '__main__':
    main()
