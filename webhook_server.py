#!/usr/bin/env python3
"""
Bloop Indicator Webhook Server v4
Captura señales de TradingView y calcula P&L
Incluye datos para optimización: ATR, TP1, TP2, SL, High, Low
"""

from flask import Flask, request, jsonify
import json
import os
from datetime import datetime, timezone

app = Flask(__name__)

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
            except:
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
    
    # Calcular P&L
    if pos['direction'] == 'LONG':
        pnl_points = exit_price - pos['entry_price']
    else:
        pnl_points = pos['entry_price'] - exit_price
    
    pnl_percent = (pnl_points / pos['entry_price']) * 100
    
    entry_dt = datetime.fromisoformat(pos['entry_time'])
    exit_dt = datetime.fromisoformat(exit_time)
    duration = int((exit_dt - entry_dt).total_seconds())
    
    c = conn.cursor()
    
    if USE_POSTGRES:
        c.execute('''
            INSERT INTO trades (symbol, direction, entry_time, entry_price,
                               entry_atr, entry_tp1, entry_tp2, entry_sl,
                               exit_time, exit_price, exit_reason,
                               pnl_points, pnl_percent, duration_seconds,
                               max_price, min_price)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (pos['symbol'], pos['direction'], pos['entry_time'], pos['entry_price'],
              pos['atr'], pos['tp1'], pos['tp2'], pos['sl'],
              exit_time, exit_price, exit_reason,
              pnl_points, pnl_percent, duration,
              pos['max_price'], pos['min_price']))
        c.execute('DELETE FROM open_position WHERE id = 1')
    else:
        c.execute('''
            INSERT INTO trades (symbol, direction, entry_time, entry_price,
                               entry_atr, entry_tp1, entry_tp2, entry_sl,
                               exit_time, exit_price, exit_reason,
                               pnl_points, pnl_percent, duration_seconds,
                               max_price, min_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (pos['symbol'], pos['direction'], pos['entry_time'], pos['entry_price'],
              pos['atr'], pos['tp1'], pos['tp2'], pos['sl'],
              exit_time, exit_price, exit_reason,
              pnl_points, pnl_percent, duration,
              pos['max_price'], pos['min_price']))
        c.execute('DELETE FROM open_position WHERE id = 1')
    
    conn.commit()
    
    return {
        'direction': pos['direction'],
        'entry_price': pos['entry_price'],
        'exit_price': exit_price,
        'exit_reason': exit_reason,
        'pnl_points': pnl_points,
        'pnl_percent': pnl_percent,
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
    """Recibir señales de TradingView."""
    try:
        if request.is_json:
            data = request.get_json()
        else:
            try:
                data = json.loads(request.data.decode('utf-8'))
            except:
                data = {'raw': request.data.decode('utf-8')}
        
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
        
        if signal in ['LONG', 'SHORT']:
            if pos and pos['direction'] != signal:
                closed_trade = close_position(conn, timestamp, price, 'signal')
            
            if not pos or closed_trade:
                set_open_position(conn, signal, timestamp, price, symbol,
                                 atr, tp1, tp2, sl)
        
        # Stats
        c.execute('SELECT COUNT(*) FROM signals')
        total_signals = c.fetchone()[0]
        c.execute('SELECT COUNT(*), COALESCE(SUM(pnl_points), 0) FROM trades')
        trade_stats = c.fetchone()
        
        conn.close()
        
        # Log
        emoji = "🟢" if signal == "LONG" else "🔴" if signal == "SHORT" else "⚪"
        opt_info = f" [ATR:{atr:.1f}]" if atr else ""
        print(f"\n{emoji} [{timestamp[:19]}] {signal} @ {price:.2f}{opt_info}")
        
        if closed_trade:
            pnl_emoji = "✅" if closed_trade['pnl_points'] > 0 else "❌"
            print(f"   {pnl_emoji} Closed {closed_trade['direction']}: {closed_trade['pnl_points']:+.2f} pts ({closed_trade['pnl_percent']:+.2f}%)")
        
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
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/signals', methods=['GET'])
def get_signals():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''SELECT id, timestamp, signal, price, symbol, timeframe, 
                        atr, tp1, tp2, sl, high, low
                 FROM signals ORDER BY timestamp DESC LIMIT 100''')
    rows = c.fetchall()
    conn.close()
    
    return jsonify([{
        'id': r[0], 'timestamp': r[1], 'signal': r[2], 'price': r[3],
        'symbol': r[4], 'timeframe': r[5], 'atr': r[6], 'tp1': r[7],
        'tp2': r[8], 'sl': r[9], 'high': r[10], 'low': r[11]
    } for r in rows])


@app.route('/trades', methods=['GET'])
def get_trades():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''SELECT id, symbol, direction, entry_time, entry_price,
                        entry_atr, entry_tp1, entry_tp2, entry_sl,
                        exit_time, exit_price, exit_reason,
                        pnl_points, pnl_percent, duration_seconds,
                        max_price, min_price
                 FROM trades ORDER BY exit_time DESC LIMIT 100''')
    rows = c.fetchall()
    conn.close()
    
    return jsonify([{
        'id': r[0], 'symbol': r[1], 'direction': r[2],
        'entry_time': r[3], 'entry_price': r[4],
        'entry_atr': r[5], 'entry_tp1': r[6], 'entry_tp2': r[7], 'entry_sl': r[8],
        'exit_time': r[9], 'exit_price': r[10], 'exit_reason': r[11],
        'pnl_points': r[12], 'pnl_percent': r[13], 'duration_seconds': r[14],
        'max_price': r[15], 'min_price': r[16]
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
    
    pos = get_open_position(conn)
    conn.close()
    
    win_rate = (t[3] / t[0] * 100) if t[0] and t[0] > 0 else 0
    
    return jsonify({
        'signals': {'total': total_signals, 'longs': longs, 'shorts': shorts},
        'trades': {
            'total': t[0] or 0,
            'winners': int(t[3] or 0),
            'win_rate': round(win_rate, 1),
            'total_pnl': round(float(t[1] or 0), 2),
            'avg_pnl': round(float(t[2] or 0), 2),
            'best_trade': round(float(t[4] or 0), 2),
            'worst_trade': round(float(t[5] or 0), 2)
        },
        'open_position': pos
    })


@app.route('/position', methods=['GET'])
def get_position():
    conn = get_db_connection()
    pos = get_open_position(conn)
    conn.close()
    return jsonify(pos or {'status': 'no open position'})


@app.route('/reset', methods=['POST'])
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
    return jsonify({'status': 'ok', 'service': 'bloop-tracker', 'database': db_type, 'version': 'v4'})


@app.route('/', methods=['GET'])
def index():
    return """
    <h1>🎯 Bloop Tracker v4</h1>
    <p>Con datos de optimización (ATR, TP, SL)</p>
    <ul>
        <li><a href="/stats">📊 Estadísticas</a></li>
        <li><a href="/trades">📈 Trades</a></li>
        <li><a href="/signals">📡 Señales</a></li>
        <li><a href="/position">🎯 Posición</a></li>
        <li><a href="/health">💚 Health</a></li>
    </ul>
    """


# Inicializar DB
init_db()

if __name__ == '__main__':
    print("🎯 Bloop Tracker v4 - Con datos de optimización")
    port = int(os.environ.get('PORT', 5555))
    app.run(host='0.0.0.0', port=port, debug=False)
