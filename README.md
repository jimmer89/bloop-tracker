# 🎯 Bloop Tracker

Webhook server para capturar señales del **Bloop Indicator** (TradingView) y calcular P&L automáticamente.

## 🚀 Setup

**Producción (Railway):**
- URL: `https://web-production-62bc.up.railway.app`
- Database: PostgreSQL (persistente)
- Auto-deploy desde GitHub

**Local:**
```bash
cd bloop-tracker
source venv/bin/activate
python webhook_server.py
```

## 📡 Endpoints

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/webhook` | POST | Recibe señales de TradingView |
| `/stats` | GET | Estadísticas completas |
| `/trades` | GET | Historial de trades cerrados |
| `/signals` | GET | Señales raw |
| `/position` | GET | Posición abierta actual |
| `/reset` | POST | Resetear todos los datos |
| `/health` | GET | Health check |

## 📊 Lógica de Trading

1. Llega señal **LONG** → Abre posición LONG
2. Llega señal **SHORT** → Cierra LONG (calcula P&L) → Abre SHORT
3. Llega señal **LONG** → Cierra SHORT (calcula P&L) → Abre LONG
4. ...y así sucesivamente

**Cada trade se guarda con:**
- Entry/exit time y price
- P&L en puntos y porcentaje
- Duración en segundos

## 🔧 TradingView Alert Setup

**Webhook URL:**
```
https://web-production-62bc.up.railway.app/webhook
```

**Alert Message (JSON):**
```json
{"signal": "{{strategy.order.action}}", "price": {{close}}, "symbol": "{{ticker}}", "timeframe": "{{interval}}"}
```

O para el Bloop:
```json
{"signal": "LONG", "price": {{close}}}
{"signal": "SHORT", "price": {{close}}}
```

## 📈 Datos Capturados

### Tabla `signals`
- timestamp, signal, price, symbol, timeframe, raw_payload

### Tabla `trades`
- symbol, direction, entry_time, entry_price, exit_time, exit_price
- pnl_points, pnl_percent, duration_seconds

### Tabla `open_position`
- direction, entry_time, entry_price, symbol

## 🔮 Roadmap

### Fase 1: Análisis Avanzado (datos)
- [ ] Capturar high/low de la vela de entrada
- [ ] Capturar ATR en el momento de la señal
- [ ] Capturar TP1/TP2 levels del indicador
- [ ] Tracking de max favorable/adverse excursion (MFE/MAE)
- [ ] Múltiples estrategias de salida en paralelo

### Fase 2: Auto-Ejecución en MT5 ⏳ PENDIENTE
**Prerrequisito:** Backtesting demuestra rentabilidad

**Implementación propuesta:**
```
EA (WebRequest) → Railway /position → Compara → Ejecuta
```

**Componentes:**
- `BloopSignalExecutor.mq5` - EA que consulta Railway cada 5-10 seg
- Parsea JSON de `/position`
- Si señal ≠ posición actual → cierra y abre nueva
- Panel visual con estado de conexión
- Log de operaciones

**Configuración requerida:**
- MT5: Añadir URL a lista permitida (`Herramientas → Opciones → Expert Advisors`)
- Railway URL: `https://web-production-62bc.up.railway.app`

**Delay esperado:** 5-10 segundos (aceptable para señales M1+)

**Tiempo estimado de desarrollo:** 2-3 horas

**Estado:** 🔴 No iniciado - esperando validación de rentabilidad

## 🛠️ Stack

- **Backend:** Flask + Gunicorn
- **Database:** PostgreSQL (Railway) / SQLite (local)
- **Hosting:** Railway (free tier)
- **Source:** TradingView webhooks

## 📝 Changelog

- **v3** (2026-02-06): Migración a PostgreSQL, deploy en Railway
- **v2** (2026-02-05): Tracking de P&L, SQLite
- **v1** (2026-02-05): Webhook básico con Serveo

---

**Repo:** https://github.com/jimmer89/bloop-tracker
