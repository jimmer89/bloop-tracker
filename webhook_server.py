#!/usr/bin/env python3
"""
Bloop Indicator Webhook Server
Captura señales de TradingView y calcula P&L
Lógica: posición se cierra cuando llega señal opuesta
"""

from flask import Flask, request, jsonify
import sqlite3
import json
from datetime import datetime
import os

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), 'signals.db')

def init_db():
    """Crear tablas si no existen"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Tabla de señales raw
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
    
    # Tabla de trades cerrados
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
    
    # Tabla de posición abierta
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
    print("✅ Database initialized")

def get_open_position(conn):
    """Obtener posición abierta si existe"""
    c = conn.cursor()
    c.execute('SELECT direction, entry_time, entry_price, symbol FROM open_position WHERE id = 1')
    row = c.fetchone()
    if row:
        return {'direction': row[0], 'entry_time': row[1], 'entry_price': row[2], 'symbol': row[3]}
    return None

def set_open_position(conn, direction, entry_time, entry_price, symbol):
    """Guardar posición abierta"""
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO open_position (id, direction, entry_time, entry_price, symbol)
        VALUES (1, ?, ?, ?, ?)
    ''', (direction, entry_time, entry_price, symbol))
    conn.commit()

def close_position(conn, exit_time, exit_price):
    """Cerrar posición y calcular P&L"""
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
    
    # Guardar trade cerrado
    c = conn.cursor()
    c.execute('''
        INSERT INTO trades (symbol, direction, entry_time, entry_price, exit_time, exit_price, 
                           pnl_points, pnl_percent, duration_seconds)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (pos['symbol'], pos['direction'], pos['entry_time'], pos['entry_price'],
          exit_time, exit_price, pnl_points, pnl_percent, duration))
    
    # Limpiar posición abierta
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
    """Recibir señales de TradingView"""
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
        timestamp = datetime.utcnow().isoformat()
        
        conn = sqlite3.connect(DB_PATH)
        
        # Guardar señal raw
        c = conn.cursor()
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
        c.execute('SELECT COUNT(*), SUM(pnl_points), SUM(CASE WHEN pnl_points > 0 THEN 1 ELSE 0 END) FROM trades')
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
            'total_pnl': trade_stats[1] or 0
        }), 200
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/signals', methods=['GET'])
def get_signals():
    """Ver señales raw"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM signals ORDER BY timestamp DESC LIMIT 100')
    rows = c.fetchall()
    conn.close()
    
    return jsonify([{
        'id': r[0], 'timestamp': r[1], 'signal': r[2], 
        'price': r[3], 'symbol': r[4], 'timeframe': r[5]
    } for r in rows])

@app.route('/trades', methods=['GET'])
def get_trades():
    """Ver trades cerrados"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM trades ORDER BY exit_time DESC LIMIT 100')
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
    """Estadísticas completas"""
    conn = sqlite3.connect(DB_PATH)
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
               SUM(pnl_points), 
               AVG(pnl_points),
               SUM(CASE WHEN pnl_points > 0 THEN 1 ELSE 0 END),
               MAX(pnl_points),
               MIN(pnl_points)
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
            'winners': t[3] or 0,
            'win_rate': round(win_rate, 1),
            'total_pnl': round(t[1] or 0, 2),
            'avg_pnl': round(t[2] or 0, 2),
            'best_trade': round(t[4] or 0, 2),
            'worst_trade': round(t[5] or 0, 2)
        },
        'open_position': pos
    })

@app.route('/position', methods=['GET'])
def get_position():
    """Ver posición abierta actual"""
    conn = sqlite3.connect(DB_PATH)
    pos = get_open_position(conn)
    conn.close()
    return jsonify(pos or {'status': 'no open position'})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'bloop-tracker'})

@app.route('/', methods=['GET'])
def index():
    return """
    <h1>🎯 Bloop Tracker</h1>
    <ul>
        <li><a href="/stats">📊 Estadísticas</a></li>
        <li><a href="/trades">📈 Trades cerrados</a></li>
        <li><a href="/signals">📡 Señales raw</a></li>
        <li><a href="/position">🎯 Posición abierta</a></li>
    </ul>
    """

if __name__ == '__main__':
    init_db()
    print("🎯 Bloop Tracker v2 - Con tracking de P&L")
    print("📡 Webhook: http://localhost:5555/webhook")
    print("📊 Stats: http://localhost:5555/stats")
    import os; app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5555)), debug=False)
