#!/usr/bin/env python3
"""
Bloop Indicator Webhook Server v5
Captura señales de TradingView y calcula P&L
Incluye datos para optimización: ATR, TP1, TP2, SL, High, Low
Incluye coste de spread en cálculos de P&L
"""

from flask import Flask, request, jsonify
from functools import wraps
import json
import os
from datetime import datetime, timezone

app = Flask(__name__)

# ============================================================
# AUTHENTICATION
# ============================================================
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', '')


def require_auth(f):
    """Require WEBHOOK_SECRET in X-Webhook-Secret header for write endpoints."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not WEBHOOK_SECRET:
            return jsonify({'status': 'error', 'message': 'WEBHOOK_SECRET not configured on server'}), 500
        token = request.headers.get('X-Webhook-Secret', '')
        if token != WEBHOOK_SECRET:
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

# ============================================================
# CONFIGURACIÓN DE SPREAD (IC Markets USTEC)
# Basado en monitoreo real: 2026-02-09/10 (~22 horas de datos)
# ============================================================
SPREAD_CONFIG = {
    'USTEC': {
        'spread_points': 0.9,     # Spread en escala de precio (90 puntos broker = 0.9)
        'spread_avg': 97,         # Spread promedio
        'spread_max': 220,        # Spread máximo (picos de volatilidad)
        'best_hours': (17, 22),   # Horario con mejor spread (GMT+1)
        'source': 'SpreadMonitor_USTEC.mq5 - IC Markets',
        'last_updated': '2026-02-10'
    }
}

# ============================================================
# TRAILING STOP CONFIG
# Set trail_points=0 to disable. Enable via POST /trailing-stop
# ============================================================
TRAILING_STOP_CONFIG = {
    'enabled': False,
    'trail_points': 20,           # Distance from peak to trigger (in price points)
    'activation_points': 0,       # Min profit before trail activates (0 = immediate)
    'fixed_sl_points': 0,         # Fixed stop loss (0 = disabled)
}

def get_spread_for_symbol(symbol='USTEC'):
    """Obtiene el spread configurado para un símbolo."""
    config = SPREAD_CONFIG.get(symbol, SPREAD_CONFIG.get('USTEC'))
    return config['spread_points']

# Database setup
DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('DATABASE_PUBLIC_URL')

if DATABASE_URL:
    import psycopg2
    USE_POSTGRES = True
else:
    import sqlite3
    USE_POSTGRES = False
    DB_PATH = os.path.join(os.path.dirname(__file__), 'signals.db')


def get_db_connection():
    if USE_POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    else:
        return sqlite3.connect(DB_PATH)


def init_db():
    """Crear tablas si no existen."""
    conn = get_db_connection()
    c = conn.cursor()
    
    if USE_POSTGRES:
        # Signals con datos de optimización
        c.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id SERIAL PRIMARY KEY,
                timestamp TEXT NOT NULL,
                signal TEXT NOT NULL,
                price REAL,
                symbol TEXT,
                timeframe TEXT,
                atr REAL,
                tp1 REAL,
                tp2 REAL,
                sl REAL,
                high REAL,
                low REAL,
                raw_payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Trades con datos para análisis
        c.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id SERIAL PRIMARY KEY,
                symbol TEXT,
                direction TEXT,
                entry_time TEXT,
                entry_price REAL,
                entry_atr REAL,
                entry_tp1 REAL,
                entry_tp2 REAL,
                entry_sl REAL,
                exit_time TEXT,
                exit_price REAL,
                exit_reason TEXT,
                pnl_points REAL,
                pnl_percent REAL,
                spread_cost REAL,
                pnl_net_points REAL,
                pnl_net_percent REAL,
                duration_seconds INTEGER,
                max_price REAL,
                min_price REAL
            )
        ''')
        
        # Posición abierta con datos de optimización
        c.execute('''
            CREATE TABLE IF NOT EXISTS open_position (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                direction TEXT,
                entry_time TEXT,
                entry_price REAL,
                symbol TEXT,
                atr REAL,
                tp1 REAL,
                tp2 REAL,
                sl REAL,
                max_price REAL,
                min_price REAL
            )
        ''')
        
        # Añadir columnas si no existen (migración)
        migration_columns = [
            ('signals', 'atr', 'REAL'),
            ('signals', 'tp1', 'REAL'),
            ('signals', 'tp2', 'REAL'),
            ('signals', 'sl', 'REAL'),
            ('signals', 'high', 'REAL'),
            ('signals', 'low', 'REAL'),
            ('trades', 'entry_atr', 'REAL'),
            ('trades', 'entry_tp1', 'REAL'),
            ('trades', 'entry_tp2', 'REAL'),
            ('trades', 'entry_sl', 'REAL'),
            ('trades', 'exit_reason', 'TEXT'),
            ('trades', 'max_price', 'REAL'),
            ('trades', 'min_price', 'REAL'),
            ('trades', 'spread_cost', 'REAL'),
            ('trades', 'pnl_net_points', 'REAL'),
            ('trades', 'pnl_net_percent', 'REAL'),
            ('open_position', 'atr', 'REAL'),
            ('open_position', 'tp1', 'REAL'),
            ('open_position', 'tp2', 'REAL'),
            ('open_position', 'sl', 'REAL'),
            ('open_position', 'max_price', 'REAL'),
            ('open_position', 'min_price', 'REAL'),
        ]
        for table, col, dtype in migration_columns:
            try:
                c.execute(f'ALTER TABLE {table} ADD COLUMN {col} {dtype}')
                conn.commit()
            except Exception as e:
                conn.rollback()  # Rollback para evitar transacción abortada
                pass  # Column already exists
    else:
        # SQLite syntax
        c.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                signal TEXT NOT NULL,
                price REAL,
                symbol TEXT,
                timeframe TEXT,
                atr REAL,
                tp1 REAL,
                tp2 REAL,
                sl REAL,
                high REAL,
                low REAL,
                raw_payload TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                direction TEXT,
                entry_time TEXT,
                entry_price REAL,
                entry_atr REAL,
                entry_tp1 REAL,
                entry_tp2 REAL,
                entry_sl REAL,
                exit_time TEXT,
                exit_price REAL,
                exit_reason TEXT,
                pnl_points REAL,
                pnl_percent REAL,
                spread_cost REAL,
                pnl_net_points REAL,
                pnl_net_percent REAL,
                duration_seconds INTEGER,
                max_price REAL,
                min_price REAL
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS open_position (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                direction TEXT,
                entry_time TEXT,
                entry_price REAL,
                symbol TEXT,
                atr REAL,
                tp1 REAL,
                tp2 REAL,
                sl REAL,
                max_price REAL,
                min_price REAL
            )
        ''')
    
    conn.commit()
    conn.close()
    db_type = "PostgreSQL" if USE_POSTGRES else "SQLite"
    print(f"✅ Database initialized ({db_type})")


def get_open_position(conn):
    c = conn.cursor()
    c.execute('''SELECT direction, entry_time, entry_price, symbol, 
                        atr, tp1, tp2, sl, max_price, min_price 
                 FROM open_position WHERE id = 1''')
    row = c.fetchone()
    if row:
        return {
            'direction': row[0], 'entry_time': row[1], 'entry_price': row[2], 
            'symbol': row[3], 'atr': row[4], 'tp1': row[5], 'tp2': row[6], 
            'sl': row[7], 'max_price': row[8], 'min_price': row[9]
        }
    return None


def update_position_extremes(conn, price):
    """Update max/min price for the open position. Returns updated position."""
    pos = get_open_position(conn)
    if not pos:
        return None

    max_p = max(pos['max_price'] or price, price)
    min_p = min(pos['min_price'] or price, price)

    c = conn.cursor()
    if USE_POSTGRES:
        c.execute('UPDATE open_position SET max_price = %s, min_price = %s WHERE id = 1',
                  (max_p, min_p))
    else:
        c.execute('UPDATE open_position SET max_price = ?, min_price = ? WHERE id = 1',
                  (max_p, min_p))
    conn.commit()

    pos['max_price'] = max_p
    pos['min_price'] = min_p
    return pos


def check_trailing_stop(pos, current_price):
    """Check if trailing stop or fixed SL should trigger.
    Returns (should_close, reason) tuple."""
    cfg = TRAILING_STOP_CONFIG
    if not cfg['enabled']:
        return False, None

    direction = pos['direction']
    entry = pos['entry_price']

    # Fixed stop loss check
    if cfg['fixed_sl_points'] > 0:
        if direction == 'LONG':
            unrealized = current_price - entry
        else:
            unrealized = entry - current_price
        if unrealized <= -cfg['fixed_sl_points']:
            return True, f"fixed_sl ({cfg['fixed_sl_points']}pts)"

    # Trailing stop check
    if cfg['trail_points'] > 0:
        if direction == 'LONG':
            peak = pos['max_price'] or entry
            unrealized_from_entry = peak - entry
            if unrealized_from_entry >= cfg['activation_points']:
                trail_level = peak - cfg['trail_points']
                if current_price <= trail_level:
                    return True, f"trailing_stop (peak={peak:.1f}, trail={cfg['trail_points']}pts)"
        else:  # SHORT
            trough = pos['min_price'] or entry
            unrealized_from_entry = entry - trough
            if unrealized_from_entry >= cfg['activation_points']:
                trail_level = trough + cfg['trail_points']
                if current_price >= trail_level:
                    return True, f"trailing_stop (trough={trough:.1f}, trail={cfg['trail_points']}pts)"

    return False, None


def set_open_position(conn, direction, entry_time, entry_price, symbol,
                      atr=None, tp1=None, tp2=None, sl=None):
    c = conn.cursor()
    if USE_POSTGRES:
        c.execute('''
            INSERT INTO open_position (id, direction, entry_time, entry_price, symbol,
                                       atr, tp1, tp2, sl, max_price, min_price)
            VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                direction = EXCLUDED.direction,
                entry_time = EXCLUDED.entry_time,
                entry_price = EXCLUDED.entry_price,
                symbol = EXCLUDED.symbol,
                atr = EXCLUDED.atr,
                tp1 = EXCLUDED.tp1,
                tp2 = EXCLUDED.tp2,
                sl = EXCLUDED.sl,
                max_price = EXCLUDED.max_price,
                min_price = EXCLUDED.min_price
        ''', (direction, entry_time, entry_price, symbol, atr, tp1, tp2, sl, 
              entry_price, entry_price))
    else:
        c.execute('''
            INSERT OR REPLACE INTO open_position 
            (id, direction, entry_time, entry_price, symbol, atr, tp1, tp2, sl, max_price, min_price)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (direction, entry_time, entry_price, symbol, atr, tp1, tp2, sl,
              entry_price, entry_price))
    conn.commit()


def close_position(conn, exit_time, exit_price, exit_reason='signal'):
    pos = get_open_position(conn)
    if not pos:
        return None
    
    # Calcular P&L bruto
    if pos['direction'] == 'LONG':
        pnl_points = exit_price - pos['entry_price']
    else:
        pnl_points = pos['entry_price'] - exit_price
    
    pnl_percent = (pnl_points / pos['entry_price']) * 100
    
    # Calcular spread cost y P&L neto
    symbol = pos['symbol'] or 'USTEC'
    spread_cost = get_spread_for_symbol(symbol)
    pnl_net_points = pnl_points - spread_cost
    pnl_net_percent = (pnl_net_points / pos['entry_price']) * 100
    
    entry_dt = datetime.fromisoformat(pos['entry_time'])
    exit_dt = datetime.fromisoformat(exit_time)
    duration = int((exit_dt - entry_dt).total_seconds())
    
    c = conn.cursor()
    
    if USE_POSTGRES:
        c.execute('''
            INSERT INTO trades (symbol, direction, entry_time, entry_price,
                               entry_atr, entry_tp1, entry_tp2, entry_sl,
                               exit_time, exit_price, exit_reason,
                               pnl_points, pnl_percent, 
                               spread_cost, pnl_net_points, pnl_net_percent,
                               duration_seconds, max_price, min_price)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (pos['symbol'], pos['direction'], pos['entry_time'], pos['entry_price'],
              pos['atr'], pos['tp1'], pos['tp2'], pos['sl'],
              exit_time, exit_price, exit_reason,
              pnl_points, pnl_percent,
              spread_cost, pnl_net_points, pnl_net_percent,
              duration, pos['max_price'], pos['min_price']))
        c.execute('DELETE FROM open_position WHERE id = 1')
    else:
        c.execute('''
            INSERT INTO trades (symbol, direction, entry_time, entry_price,
                               entry_atr, entry_tp1, entry_tp2, entry_sl,
                               exit_time, exit_price, exit_reason,
                               pnl_points, pnl_percent,
                               spread_cost, pnl_net_points, pnl_net_percent,
                               duration_seconds, max_price, min_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (pos['symbol'], pos['direction'], pos['entry_time'], pos['entry_price'],
              pos['atr'], pos['tp1'], pos['tp2'], pos['sl'],
              exit_time, exit_price, exit_reason,
              pnl_points, pnl_percent,
              spread_cost, pnl_net_points, pnl_net_percent,
              duration, pos['max_price'], pos['min_price']))
        c.execute('DELETE FROM open_position WHERE id = 1')
    
    conn.commit()
    
    return {
        'direction': pos['direction'],
        'entry_price': pos['entry_price'],
        'exit_price': exit_price,
        'exit_reason': exit_reason,
        'pnl_points': pnl_points,
        'pnl_percent': pnl_percent,
        'spread_cost': spread_cost,
        'pnl_net_points': pnl_net_points,
        'pnl_net_percent': pnl_net_percent,
        'duration_seconds': duration,
        'max_price': pos['max_price'],
        'min_price': pos['min_price'],
        'atr': pos['atr'],
        'tp1': pos['tp1'],
        'tp2': pos['tp2'],
        'sl': pos['sl']
    }


@app.route('/webhook', methods=['POST'])
def webhook():
    """Recibir señales de TradingView.
    
    Auth: Accepts secret in JSON body (for TradingView compatibility)
    since TradingView webhooks can't send custom headers.
    """
    try:
        if request.is_json:
            data = request.get_json()
        else:
            try:
                data = json.loads(request.data.decode('utf-8'))
            except:
                data = {'raw': request.data.decode('utf-8')}
        
        # Validate secret from body (TradingView can't send headers)
        if not WEBHOOK_SECRET:
            return jsonify({'status': 'error', 'message': 'WEBHOOK_SECRET not configured on server'}), 500
        body_secret = data.get('secret', '')
        if body_secret != WEBHOOK_SECRET:
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        
        signal = data.get('signal', 'UNKNOWN').upper()
        price = float(data.get('price', 0))
        symbol = data.get('symbol', 'USTEC')
        timeframe = data.get('timeframe', '1m')
        
        # Datos de optimización (opcionales)
        atr = float(data.get('atr', 0)) if data.get('atr') else None
        tp1 = float(data.get('tp1', 0)) if data.get('tp1') else None
        tp2 = float(data.get('tp2', 0)) if data.get('tp2') else None
        sl = float(data.get('sl', 0)) if data.get('sl') else None
        high = float(data.get('high', 0)) if data.get('high') else None
        low = float(data.get('low', 0)) if data.get('low') else None
        
        timestamp = datetime.now(timezone.utc).isoformat()
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Guardar señal
        if USE_POSTGRES:
            c.execute('''
                INSERT INTO signals (timestamp, signal, price, symbol, timeframe,
                                    atr, tp1, tp2, sl, high, low, raw_payload)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (timestamp, signal, price, symbol, timeframe,
                  atr, tp1, tp2, sl, high, low, json.dumps(data)))
        else:
            c.execute('''
                INSERT INTO signals (timestamp, signal, price, symbol, timeframe,
                                    atr, tp1, tp2, sl, high, low, raw_payload)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (timestamp, signal, price, symbol, timeframe,
                  atr, tp1, tp2, sl, high, low, json.dumps(data)))
        conn.commit()
        
        # Procesar lógica de trading
        pos = get_open_position(conn)
        closed_trade = None

        # Update max/min price on every signal (for trailing stop tracking)
        if pos:
            pos = update_position_extremes(conn, price)

        if signal == 'PRICE_UPDATE':
            # Price update only — check trailing stop, don't open/close on signal
            if pos:
                should_close, reason = check_trailing_stop(pos, price)
                if should_close:
                    closed_trade = close_position(conn, timestamp, price, reason)
                    print(f"   TRAILING STOP triggered: {reason}")
        elif signal in ['LONG', 'SHORT']:
            if pos and pos['direction'] != signal:
                closed_trade = close_position(conn, timestamp, price, 'signal')

            if not pos or closed_trade:
                set_open_position(conn, signal, timestamp, price, symbol,
                                 atr, tp1, tp2, sl)

        # Also check trailing stop on regular signals (before opening new position)
        if signal in ['LONG', 'SHORT'] and not closed_trade:
            pos = get_open_position(conn)
            if pos:
                should_close, reason = check_trailing_stop(pos, price)
                if should_close:
                    closed_trade = close_position(conn, timestamp, price, reason)
        
        # Stats
        c.execute('SELECT COUNT(*) FROM signals')
        total_signals = c.fetchone()[0]
        c.execute('SELECT COUNT(*), COALESCE(SUM(pnl_points), 0) FROM trades')
        trade_stats = c.fetchone()
        
        conn.close()
        
        # Log
        emoji = "🟢" if signal == "LONG" else "🔴" if signal == "SHORT" else "📡" if signal == "PRICE_UPDATE" else "⚪"
        opt_info = f" [ATR:{atr:.1f}]" if atr else ""
        print(f"\n{emoji} [{timestamp[:19]}] {signal} @ {price:.2f}{opt_info}")
        
        if closed_trade:
            pnl_emoji = "✅" if closed_trade['pnl_net_points'] > 0 else "❌"
            print(f"   {pnl_emoji} Closed {closed_trade['direction']}: {closed_trade['pnl_points']:+.1f} pts bruto → {closed_trade['pnl_net_points']:+.1f} pts neto (spread: -{closed_trade['spread_cost']:.0f})")
        
        print(f"   📊 Signals: {total_signals} | Trades: {trade_stats[0]} | P&L: {trade_stats[1] or 0:.2f} pts")
        
        return jsonify({
            'status': 'ok',
            'signal': signal,
            'price': price,
            'optimization_data': {'atr': atr, 'tp1': tp1, 'tp2': tp2, 'sl': sl},
            'closed_trade': closed_trade,
            'total_signals': total_signals,
            'total_trades': trade_stats[0],
            'total_pnl': float(trade_stats[1] or 0)
        }), 200
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500


@app.route('/signals', methods=['GET'])
@require_auth
def get_signals():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''SELECT id, timestamp, signal, price, symbol, timeframe, 
                        atr, tp1, tp2, sl, high, low
                 FROM signals ORDER BY timestamp DESC LIMIT 10000''')
    rows = c.fetchall()
    conn.close()
    
    return jsonify([{
        'id': r[0], 'timestamp': r[1], 'signal': r[2], 'price': r[3],
        'symbol': r[4], 'timeframe': r[5], 'atr': r[6], 'tp1': r[7],
        'tp2': r[8], 'sl': r[9], 'high': r[10], 'low': r[11]
    } for r in rows])


@app.route('/trades', methods=['GET'])
@require_auth
def get_trades():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''SELECT id, symbol, direction, entry_time, entry_price,
                        entry_atr, entry_tp1, entry_tp2, entry_sl,
                        exit_time, exit_price, exit_reason,
                        pnl_points, pnl_percent, 
                        spread_cost, pnl_net_points, pnl_net_percent,
                        duration_seconds, max_price, min_price
                 FROM trades ORDER BY exit_time DESC LIMIT 10000''')
    rows = c.fetchall()
    conn.close()
    
    return jsonify([{
        'id': r[0], 'symbol': r[1], 'direction': r[2],
        'entry_time': r[3], 'entry_price': r[4],
        'entry_atr': r[5], 'entry_tp1': r[6], 'entry_tp2': r[7], 'entry_sl': r[8],
        'exit_time': r[9], 'exit_price': r[10], 'exit_reason': r[11],
        'pnl_points': r[12], 'pnl_percent': r[13],
        'spread_cost': r[14], 'pnl_net_points': r[15], 'pnl_net_percent': r[16],
        'duration_seconds': r[17], 'max_price': r[18], 'min_price': r[19]
    } for r in rows])


@app.route('/stats', methods=['GET'])
def get_stats():
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) FROM signals')
    total_signals = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM signals WHERE signal = 'LONG'")
    longs = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM signals WHERE signal = 'SHORT'")
    shorts = c.fetchone()[0]
    
    # Stats con P&L bruto
    c.execute('''
        SELECT COUNT(*), 
               COALESCE(SUM(pnl_points), 0), 
               COALESCE(AVG(pnl_points), 0),
               COALESCE(SUM(CASE WHEN pnl_points > 0 THEN 1 ELSE 0 END), 0),
               COALESCE(MAX(pnl_points), 0),
               COALESCE(MIN(pnl_points), 0)
        FROM trades
    ''')
    t = c.fetchone()
    
    # Stats con P&L neto (después de spread)
    c.execute('''
        SELECT COALESCE(SUM(pnl_net_points), 0),
               COALESCE(AVG(pnl_net_points), 0),
               COALESCE(SUM(CASE WHEN pnl_net_points > 0 THEN 1 ELSE 0 END), 0),
               COALESCE(MAX(pnl_net_points), 0),
               COALESCE(MIN(pnl_net_points), 0),
               COALESCE(SUM(spread_cost), 0)
        FROM trades
    ''')
    net = c.fetchone()
    
    pos = get_open_position(conn)
    conn.close()
    
    total_trades = t[0] or 0
    win_rate_gross = (t[3] / total_trades * 100) if total_trades > 0 else 0
    win_rate_net = (net[2] / total_trades * 100) if total_trades > 0 else 0
    
    # Spread config para mostrar
    spread_info = SPREAD_CONFIG.get('USTEC', {})
    
    return jsonify({
        'signals': {'total': total_signals, 'longs': longs, 'shorts': shorts},
        'trades': {
            'total': total_trades,
            # P&L Bruto (sin spread)
            'gross': {
                'total_pnl': round(float(t[1] or 0), 2),
                'avg_pnl': round(float(t[2] or 0), 2),
                'winners': int(t[3] or 0),
                'win_rate': round(win_rate_gross, 1),
                'best_trade': round(float(t[4] or 0), 2),
                'worst_trade': round(float(t[5] or 0), 2)
            },
            # P&L Neto (con spread)
            'net': {
                'total_pnl': round(float(net[0] or 0), 2),
                'avg_pnl': round(float(net[1] or 0), 2),
                'winners': int(net[2] or 0),
                'win_rate': round(win_rate_net, 1),
                'best_trade': round(float(net[3] or 0), 2),
                'worst_trade': round(float(net[4] or 0), 2),
                'total_spread_cost': round(float(net[5] or 0), 2)
            },
            # Legacy (mantener compatibilidad) - usa bruto
            'winners': int(t[3] or 0),
            'win_rate': round(win_rate_gross, 1),
            'total_pnl': round(float(t[1] or 0), 2),
            'avg_pnl': round(float(t[2] or 0), 2),
            'best_trade': round(float(t[4] or 0), 2),
            'worst_trade': round(float(t[5] or 0), 2)
        },
        'spread_config': {
            'symbol': 'USTEC',
            'spread_points': spread_info.get('spread_points', 90),
            'source': spread_info.get('source', 'SpreadMonitor EA'),
            'last_updated': spread_info.get('last_updated', 'N/A')
        },
        'open_position': pos
    })


@app.route('/position', methods=['GET'])
@require_auth
def get_position():
    conn = get_db_connection()
    pos = get_open_position(conn)
    conn.close()
    return jsonify(pos or {'status': 'no open position'})


@app.route('/reset', methods=['POST'])
@require_auth
def reset_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('DELETE FROM signals')
    c.execute('DELETE FROM trades')
    c.execute('DELETE FROM open_position')
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok', 'message': 'All data reset'})


@app.route('/health', methods=['GET'])
def health():
    db_type = "PostgreSQL" if USE_POSTGRES else "SQLite"
    spread_info = SPREAD_CONFIG.get('USTEC', {})
    return jsonify({
        'status': 'ok', 
        'service': 'bloop-tracker', 
        'database': db_type, 
        'version': 'v5',
        'spread_config': {
            'USTEC': spread_info.get('spread_points', 90)
        }
    })


@app.route('/spread', methods=['GET', 'POST'])
def spread_config():
    """Ver o actualizar configuración de spread."""
    if request.method == 'GET':
        return jsonify(SPREAD_CONFIG)

    # POST: require auth for write operations
    if not WEBHOOK_SECRET:
        return jsonify({'status': 'error', 'message': 'WEBHOOK_SECRET not configured'}), 500
    token = request.headers.get('X-Webhook-Secret', '')
    if token != WEBHOOK_SECRET:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    # POST: actualizar spread
    try:
        data = request.get_json()
        symbol = data.get('symbol', 'USTEC')
        spread = data.get('spread_points')
        
        if spread is not None:
            if symbol not in SPREAD_CONFIG:
                SPREAD_CONFIG[symbol] = {}
            SPREAD_CONFIG[symbol]['spread_points'] = float(spread)
            SPREAD_CONFIG[symbol]['last_updated'] = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            
            return jsonify({
                'status': 'ok',
                'message': f'Spread for {symbol} updated to {spread} points',
                'config': SPREAD_CONFIG[symbol]
            })
        else:
            return jsonify({'status': 'error', 'message': 'spread_points required'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/trailing-stop', methods=['GET', 'POST'])
def trailing_stop_config():
    """View or update trailing stop configuration."""
    if request.method == 'GET':
        return jsonify(TRAILING_STOP_CONFIG)

    # POST: require auth
    if not WEBHOOK_SECRET:
        return jsonify({'status': 'error', 'message': 'WEBHOOK_SECRET not configured'}), 500
    token = request.headers.get('X-Webhook-Secret', '')
    if token != WEBHOOK_SECRET:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        if 'enabled' in data:
            TRAILING_STOP_CONFIG['enabled'] = bool(data['enabled'])
        if 'trail_points' in data:
            TRAILING_STOP_CONFIG['trail_points'] = float(data['trail_points'])
        if 'activation_points' in data:
            TRAILING_STOP_CONFIG['activation_points'] = float(data['activation_points'])
        if 'fixed_sl_points' in data:
            TRAILING_STOP_CONFIG['fixed_sl_points'] = float(data['fixed_sl_points'])

        status = "ENABLED" if TRAILING_STOP_CONFIG['enabled'] else "DISABLED"
        print(f"   Trailing stop config updated: {status} | trail={TRAILING_STOP_CONFIG['trail_points']} activ={TRAILING_STOP_CONFIG['activation_points']} sl={TRAILING_STOP_CONFIG['fixed_sl_points']}")

        return jsonify({
            'status': 'ok',
            'message': f'Trailing stop {status}',
            'config': TRAILING_STOP_CONFIG
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/recalculate', methods=['POST'])
@require_auth
def recalculate_pnl():
    """Recalcular P&L neto de todos los trades con el spread actual."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Obtener todos los trades
        c.execute('SELECT id, symbol, pnl_points, entry_price FROM trades')
        rows = c.fetchall()
        
        updated = 0
        for row in rows:
            trade_id, symbol, pnl_points, entry_price = row
            if pnl_points is None:
                continue
                
            spread = get_spread_for_symbol(symbol or 'USTEC')
            pnl_net = pnl_points - spread
            pnl_net_pct = (pnl_net / entry_price * 100) if entry_price else 0
            
            if USE_POSTGRES:
                c.execute('''
                    UPDATE trades 
                    SET spread_cost = %s, pnl_net_points = %s, pnl_net_percent = %s
                    WHERE id = %s
                ''', (spread, pnl_net, pnl_net_pct, trade_id))
            else:
                c.execute('''
                    UPDATE trades 
                    SET spread_cost = ?, pnl_net_points = ?, pnl_net_percent = ?
                    WHERE id = ?
                ''', (spread, pnl_net, pnl_net_pct, trade_id))
            updated += 1
        
        conn.commit()
        conn.close()
        
        spread_used = get_spread_for_symbol('USTEC')
        return jsonify({
            'status': 'ok',
            'trades_updated': updated,
            'spread_used': spread_used,
            'message': f'Recalculated {updated} trades with spread {spread_used} pts'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/', methods=['GET'])
def index():
    spread = get_spread_for_symbol('USTEC')
    return f"""
    <h1>🎯 Bloop Tracker v5</h1>
    <p>Con spread real de IC Markets ({spread} pts para USTEC)</p>
    <ul>
        <li><a href="/stats">📊 Estadísticas (Bruto vs Neto)</a></li>
        <li><a href="/trades">📈 Trades</a></li>
        <li><a href="/signals">📡 Señales</a></li>
        <li><a href="/position">🎯 Posición</a></li>
        <li><a href="/spread">💰 Config Spread</a></li>
        <li><a href="/trailing-stop">🎯 Trailing Stop Config</a></li>
        <li><a href="/health">💚 Health</a></li>
    </ul>
    <p><small>POST /recalculate para recalcular P&L con nuevo spread</small></p>
    """


# Inicializar DB
init_db()

if __name__ == '__main__':
    spread = get_spread_for_symbol('USTEC')
    print(f"🎯 Bloop Tracker v5 - Con spread real ({spread} pts USTEC)")
    port = int(os.environ.get('PORT', 5555))
    app.run(host='127.0.0.1', port=port, debug=False)
