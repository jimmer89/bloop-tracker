# 🎯 Bloop Tracker v5

Webhook server para capturar señales del **Bloop Indicator** (TradingView) y calcular P&L con **spread real** de IC Markets.

## 🚀 Estado Actual

**Producción (Railway):** https://web-production-62bc.up.railway.app

### Backtest Results (2026-02-12)

| Métrica | Bruto | Neto (con spread) |
|---------|-------|-------------------|
| Total P&L | +499.6 pts | **+428.5 pts** |
| Win Rate | 49.4% | **46.8%** |
| Winners | 39/79 | 37/79 |
| P&L promedio | +6.32 pts | +5.42 pts |

**✅ Conclusión:** La estrategia ES RENTABLE con spread real de IC Markets (0.9 pts).

---

## 📊 Configuración de Spread

Basado en monitoreo real con `SpreadMonitor_USTEC.mq5` (22 horas de datos):

| Parámetro | Valor (escala precio) |
|-----------|----------------------|
| Spread mínimo | 0.9 pts |
| Spread promedio | ~1.0 pts |
| Spread máximo | 2.2 pts (picos) |
| Mejor horario | 17:00-22:00 GMT+1 |

**Nota:** IC Markets muestra "90 puntos" pero USTEC tiene 2 decimales, así que 90 puntos = 0.90 en escala del precio.

**Fuente:** IC Markets, cuenta Standard, USTEC

---

## 📡 Endpoints

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/webhook` | POST | Recibe señales de TradingView |
| `/stats` | GET | Estadísticas (bruto vs neto) |
| `/trades` | GET | Historial de trades con P&L neto |
| `/signals` | GET | Señales raw |
| `/position` | GET | Posición abierta actual |
| `/spread` | GET/POST | Ver/actualizar config de spread |
| `/recalculate` | POST | Recalcular P&L neto histórico |
| `/reset` | POST | Resetear todos los datos |
| `/health` | GET | Health check + versión |

---

## 📈 Respuesta de /stats

```json
{
  "trades": {
    "total": 30,
    "gross": {
      "total_pnl": 148.1,
      "win_rate": 50.0,
      "winners": 15,
      "avg_pnl": 4.94
    },
    "net": {
      "total_pnl": -2551.9,
      "win_rate": 10.0,
      "winners": 3,
      "avg_pnl": -85.06,
      "total_spread_cost": 2700.0
    }
  },
  "spread_config": {
    "symbol": "USTEC",
    "spread_points": 90,
    "source": "SpreadMonitor_USTEC.mq5 - IC Markets"
  }
}
```

---

## 🔧 TradingView Alert Setup

**Webhook URL:**
```
https://web-production-62bc.up.railway.app/webhook
```

**Alert Message:**
```json
{"signal": "LONG", "price": {{close}}, "symbol": "USTEC"}
{"signal": "SHORT", "price": {{close}}, "symbol": "USTEC"}
```

**Con datos de optimización (opcional):**
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

---

## 🔄 Actualizar Spread

```bash
# Ver configuración actual
curl https://web-production-62bc.up.railway.app/spread

# Actualizar spread (ej: nuevo spread de 50 pts)
curl -X POST https://web-production-62bc.up.railway.app/spread \
  -H "Content-Type: application/json" \
  -d '{"symbol": "USTEC", "spread_points": 50}'

# Recalcular todos los trades con nuevo spread
curl -X POST https://web-production-62bc.up.railway.app/recalculate
```

---

## 📁 Archivos Relacionados

| Archivo | Ubicación | Descripción |
|---------|-----------|-------------|
| SpreadMonitor EA | `~/clawd/mql5/SpreadMonitor_USTEC.mq5` | EA para monitorear spread |
| Datos de spread | `~/clawd/edge-research/data/USTEC_spread_2026-02-09_raw.csv` | CSV con 2604 muestras |
| Análisis spread | `~/clawd/edge-research/analysis/USTEC_spread_analysis_2026-02-10.md` | Análisis completo |

---

## 🔮 Roadmap

### ✅ Completado
- [x] Webhook básico con captura de señales
- [x] Cálculo de P&L por trade
- [x] Deploy en Railway con PostgreSQL
- [x] Datos de optimización (ATR, TP, SL)
- [x] **Spread real de IC Markets integrado**
- [x] **P&L bruto vs neto**
- [x] **Endpoint /recalculate para actualizar histórico**

### 🔄 En Progreso
- [ ] Monitoreo de spread en tiempo real (EA corriendo)
- [ ] Más días de datos para análisis

### ⏳ Pendiente
- [ ] Comparar spreads de otros brokers
- [ ] Filtros de señales (solo trades con potencial > spread)
- [ ] Auto-ejecución en MT5 (requiere viabilidad demostrada)

---

## 🎯 Para Hacer Viable la Estrategia

1. **Cambiar broker** → Spread < 5 pts (Pepperstone Razor, IC Markets Raw)
2. **Filtrar señales** → Solo trades con potencial > 150 pts
3. **Aumentar timeframe** → H1/H4 en vez de M1/M5
4. **Cambiar activo** → Forex majors tienen spread ~0.5 pts

---

## 🛠️ Stack

- **Backend:** Flask + Gunicorn
- **Database:** PostgreSQL (Railway)
- **Hosting:** Railway (auto-deploy desde GitHub)
- **Monitoreo spread:** MQL5 EA en MT5

---

## 📝 Changelog

- **v5** (2026-02-10): Spread real de IC Markets, P&L bruto vs neto, /recalculate
- **v4** (2026-02-07): Datos de optimización (ATR, TP, SL)
- **v3** (2026-02-06): Migración a PostgreSQL, deploy en Railway
- **v2** (2026-02-05): Tracking de P&L, SQLite
- **v1** (2026-02-05): Webhook básico con Serveo

---

**Repo:** https://github.com/jimmer89/bloop-tracker
