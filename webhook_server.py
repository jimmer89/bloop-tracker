#!/usr/bin/env python3
"""
Bloop Indicator Webhook Server
Captura señales de TradingView y calcula P&L
Lógica: posición se cierra cuando llega señal opuesta
Usa PostgreSQL para persistencia en Railway
"""

from flask import Flask, request, jsonify
import json
import os
from datetime import datetime, timezone

app = Flask(__name__)

# Database setup - PostgreSQL on Railway, SQLite for local dev
# Try DATABASE_URL first, then DATABASE_PUBLIC_URL
DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('DATABASE_PUBLIC_URL')

if DATABASE_URL:
    # PostgreSQL (Railway)
    import psycopg2
    from psycopg2.extras import RealDictCursor
    USE_POSTGRES = True
else:
    # SQLite (local development)
    import sqlite3
    USE_POSTGRES = False
    DB_PATH = os.path.join(os.path.dirname(__file__), 'signals.db')


def get_db_connection():
    """Get database connection based on environment."""
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        return conn


def init_db():
    """Crear tablas si no existen."""
    conn = get_db_connection()
    c = conn.cursor()
    
    if USE_POSTGRES:
        # PostgreSQL syntax
        c.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id SERIAL PRIMARY KEY,
                timestamp TEXT NOT NULL,
                signal TEXT NOT NULL,
                price REAL,
                symbol TEXT,
                timeframe TEXT,
                raw_payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id SERIAL PRIMARY KEY,
                symbol TEXT,
                direction TEXT,
                entry_time TEXT,
                entry_price REAL,
                exit_time TEXT,
                exit_price REAL,
                pnl_points REAL,
                pnl_percent REAL,
                duration_seconds INTEGER
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS open_position (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                direction TEXT,
                entry_time TEXT,
                entry_price REAL,
                symbol TEXT
            )
        ''')
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
                exit_time TEXT,
                exit_price REAL,
                pnl_points REAL,
                pnl_percent REAL,
                duration_seconds INTEGER
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS open_position (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                direction TEXT,
                entry_time TEXT,
                entry_price REAL,
                symbol TEXT
            )
        ''')
    
    conn.commit()
    conn.close()
    db_type = "PostgreSQL" if USE_POSTGRES else "SQLite"
    print(f"✅ Database initialized ({db_type})")


def get_open_position(conn):
    """Obtener posición abierta si existe."""
    c = conn.cursor()
    c.execute('SELECT direction, entry_time, entry_price, symbol FROM open_position WHERE id = 1')
    row = c.fetchone()
    if row:
        if USE_POSTGRES:
            return {'direction': row[0], 'entry_time': row[1], 'entry_price': row[2], 'symbol': row[3]}
        else:
            return {'direction': row[0], 'entry_time': row[1], 'entry_price': row[2], 'symbol': row[3]}
    return None


def set_open_position(conn, direction, entry_time, entry_price, symbol):
    """Guardar posición abierta."""
    c = conn.cursor()
    if USE_POSTGRES:
        c.execute('''
            INSERT INTO open_position (id, direction, entry_time, entry_price, symbol)
            VALUES (1, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                direction = EXCLUDED.direction,
                entry_time = EXCLUDED.entry_time,
                entry_price = EXCLUDED.entry_price,
                symbol = EXCLUDED.symbol
        ''', (direction, entry_time, entry_price, symbol))
    else:
        c.execute('''
            INSERT OR REPLACE INTO open_position (id, direction, entry_time, entry_price, symbol)
            VALUES (1, ?, ?, ?, ?)
        ''', (direction, entry_time, entry_price, symbol))
    conn.commit()


def close_position(conn, exit_time, exit_price):
    """Cerrar posición y calcular P&L."""
    pos = get_open_position(conn)
    if not pos:
        return None
    
    # Calcular P&L
    if pos['direction'] == 'LONG':
        pnl_points = exit_price - pos['entry_price']
    else:  # SHORT
        pnl_points = pos['entry_price'] - exit_price
    
    pnl_percent = (pnl_points / pos['entry_price']) * 100
    
    # Calcular duración
    entry_dt = datetime.fromisoformat(pos['entry_time'])
    exit_dt = datetime.fromisoformat(exit_time)
    duration = int((exit_dt - entry_dt).total_seconds())
    
    c = conn.cursor()
    
    # Guardar trade cerrado
    if USE_POSTGRES:
        c.execute('''
            INSERT INTO trades (symbol, direction, entry_time, entry_price, exit_time, exit_price, 
                               pnl_points, pnl_percent, duration_seconds)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (pos['symbol'], pos['direction'], pos['entry_time'], pos['entry_price'],
              exit_time, exit_price, pnl_points, pnl_percent, duration))
        c.execute('DELETE FROM open_position WHERE id = 1')
    else:
        c.execute('''
            INSERT INTO trades (symbol, direction, entry_time, entry_price, exit_time, exit_price, 
                               pnl_points, pnl_percent, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (pos['symbol'], pos['direction'], pos['entry_time'], pos['entry_price'],
              exit_time, exit_price, pnl_points, pnl_percent, duration))
        c.execute('DELETE FROM open_position WHERE id = 1')
    
    conn.commit()
    
    return {
        'direction': pos['direction'],
        'entry_price': pos['entry_price'],
        'exit_price': exit_price,
        'pnl_points': pnl_points,
        'pnl_percent': pnl_percent,
        'duration_seconds': duration
    }


@app.route('/webhook', methods=['POST'])
def webhook():
    """Recibir señales de TradingView."""
    try:
        # Parsear JSON
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
        timestamp = datetime.now(timezone.utc).isoformat()
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Guardar señal raw
        if USE_POSTGRES:
            c.execute('''
                INSERT INTO signals (timestamp, signal, price, symbol, timeframe, raw_payload)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (timestamp, signal, price, symbol, timeframe, json.dumps(data)))
        else:
            c.execute('''
                INSERT INTO signals (timestamp, signal, price, symbol, timeframe, raw_payload)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (timestamp, signal, price, symbol, timeframe, json.dumps(data)))
        conn.commit()
        
        # Procesar lógica de trading
        pos = get_open_position(conn)
        closed_trade = None
        
        if signal in ['LONG', 'SHORT']:
            # Si hay posición opuesta abierta, cerrarla
            if pos and pos['direction'] != signal:
                closed_trade = close_position(conn, timestamp, price)
            
            # Abrir nueva posición (si no había o si cerramos la anterior)
            if not pos or closed_trade:
                set_open_position(conn, signal, timestamp, price, symbol)
        
        # Stats
        c.execute('SELECT COUNT(*) FROM signals')
        total_signals = c.fetchone()[0]
        c.execute('SELECT COUNT(*), COALESCE(SUM(pnl_points), 0), COALESCE(SUM(CASE WHEN pnl_points > 0 THEN 1 ELSE 0 END), 0) FROM trades')
        trade_stats = c.fetchone()
        
        conn.close()
        
        # Log
        emoji = "🟢" if signal == "LONG" else "🔴" if signal == "SHORT" else "⚪"
        print(f"\n{emoji} [{timestamp}] {signal} @ {price:.2f}")
        
        if closed_trade:
            pnl_emoji = "✅" if closed_trade['pnl_points'] > 0 else "❌"
            print(f"   {pnl_emoji} Closed {closed_trade['direction']}: {closed_trade['pnl_points']:+.2f} pts ({closed_trade['pnl_percent']:+.2f}%)")
        
        print(f"   📊 Signals: {total_signals} | Trades: {trade_stats[0]} | Total P&L: {trade_stats[1] or 0:.2f} pts")
        
        return jsonify({
            'status': 'ok',
            'signal': signal,
            'price': price,
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
    """Ver señales raw."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT id, timestamp, signal, price, symbol, timeframe FROM signals ORDER BY timestamp DESC LIMIT 100')
    rows = c.fetchall()
    conn.close()
    
    return jsonify([{
        'id': r[0], 'timestamp': r[1], 'signal': r[2], 
        'price': r[3], 'symbol': r[4], 'timeframe': r[5]
    } for r in rows])


@app.route('/trades', methods=['GET'])
def get_trades():
    """Ver trades cerrados."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT id, symbol, direction, entry_time, entry_price, exit_time, exit_price, pnl_points, pnl_percent, duration_seconds FROM trades ORDER BY exit_time DESC LIMIT 100')
    rows = c.fetchall()
    conn.close()
    
    return jsonify([{
        'id': r[0], 'symbol': r[1], 'direction': r[2],
        'entry_time': r[3], 'entry_price': r[4],
        'exit_time': r[5], 'exit_price': r[6],
        'pnl_points': r[7], 'pnl_percent': r[8],
        'duration_seconds': r[9]
    } for r in rows])


@app.route('/stats', methods=['GET'])
def get_stats():
    """Estadísticas completas."""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Señales
    c.execute('SELECT COUNT(*) FROM signals')
    total_signals = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM signals WHERE signal = 'LONG'")
    longs = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM signals WHERE signal = 'SHORT'")
    shorts = c.fetchone()[0]
    
    # Trades
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
    
    # Posición abierta
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
    """Ver posición abierta actual."""
    conn = get_db_connection()
    pos = get_open_position(conn)
    conn.close()
    return jsonify(pos or {'status': 'no open position'})


@app.route('/reset', methods=['POST'])
def reset_db():
    """Reset all data - use with caution!"""
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
    return jsonify({'status': 'ok', 'service': 'bloop-tracker', 'database': db_type})


@app.route('/', methods=['GET'])
def index():
    return """
    <h1>🎯 Bloop Tracker</h1>
    <ul>
        <li><a href="/stats">📊 Estadísticas</a></li>
        <li><a href="/trades">📈 Trades cerrados</a></li>
        <li><a href="/signals">📡 Señales raw</a></li>
        <li><a href="/position">🎯 Posición abierta</a></li>
        <li><a href="/health">💚 Health check</a></li>
    </ul>
    """


# Inicializar DB siempre (para gunicorn y ejecución directa)
init_db()

if __name__ == '__main__':
    print("🎯 Bloop Tracker v3 - PostgreSQL Edition")
    print("📡 Webhook: http://localhost:5555/webhook")
    print("📊 Stats: http://localhost:5555/stats")
    port = int(os.environ.get('PORT', 5555))
    app.run(host='0.0.0.0', port=port, debug=False)
