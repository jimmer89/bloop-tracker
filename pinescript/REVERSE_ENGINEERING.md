# 🔬 Bloop Indicator — Reverse Engineering

**Objetivo:** Clonar el indicador Bloop de TradingView para no depender de suscripción de pago.

**Estado:** 🟡 EN PROGRESO (v2 funcional, ajuste de parámetros pendiente)

---

## 📊 Parámetros del Indicador Original

Capturados de TradingView el 2026-02-12:

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| SmoothRNG Sensitivity | 8 | Período del Range Filter |
| HTF Timeframe | 15 min | Timeframe para tendencia HTF |
| HTF MA Type | HMA | Hull Moving Average |
| HTF MA Length | 20 | Longitud del HMA |
| ATR Length (Trailing Stop) | 10 | ATR para trailing stop |
| ATR Multiplier (Trailing Stop) | 1.5 | Multiplicador trailing |
| ATR Length (Targets) | 14 | ATR para TP levels |
| TP1 ATR Multiple | 2 | TP1 = entry ± 2×ATR |
| TP2 ATR Multiple | 4 | TP2 = entry ± 4×ATR |
| ORB Window | 15 min | Opening Range Breakout (no implementado) |
| Session | 0930-1600 | Horario de sesión (no implementado) |

---

## 🔧 Versiones del Clon

### v1 (BloopClone_v1.pine) — DESCARTADO

**Problema:** Range Filter demasiado sensible, generaba muchas más señales que el original.

**Algoritmo usado:** Intento de SmoothRNG básico basado en EMA de cambios de precio.

### v2 (BloopClone_v2.pine) — ACTUAL

**Algoritmo usado:** DonovanWall's Range Filter
- Source: https://www.tradingview.com/script/lut7sBgG-Range-Filter-DW/
- Tipo: Filter Type 1 (smooth average range)
- Smoothing: EMA doble con `wper = period * 2 - 1`

**Estado:** Funciona pero aún más sensible que el original.

---

## 🧪 Experimentos Realizados

### Experimento 1: Range Multiplier por defecto (2.618)

**Resultado:** Clon genera ~2-3x más señales que el original.

**Valores comparados:**
| Métrica | Original | Clon v2 |
|---------|----------|---------|
| Range Filter | 24.725,39 | 24.749,50 |
| Trailing Stop | 24.751,31 | 24.747,80 |

### Experimento 2: Range Multiplier = 3.5

**Resultado:** Range Filter más suave, menos señales, pero aún más que el original.

**Próximo paso:** Probar valores más altos (4.0, 4.5, 5.0).

---

## 🤔 Hipótesis sobre el "SmoothRNG Sensitivity"

El parámetro "SmoothRNG Sensitivity" del Bloop original probablemente **no es un simple período de EMA**. 

Posibilidades:
1. **Fórmula propietaria** que combina varios factores
2. **Multiplier implícito** diferente al estándar 2.618 de DonovanWall
3. **Smoothing adicional** no visible en los parámetros

**Test propuesto:** Encontrar el valor de Range Multiplier que hace que el valor del Range Filter coincida con el original.

---

## 📁 Archivos

| Archivo | Descripción |
|---------|-------------|
| `BloopClone_v1.pine` | Primera versión (descartada) |
| `BloopClone_v2.pine` | Versión actual con DonovanWall algorithm |
| `REVERSE_ENGINEERING.md` | Este archivo |

---

## ✅ Lo que funciona

- ✅ HTF MA (HMA 20 en 15min) — coincide perfectamente
- ✅ Trailing Stop con ATR — muy similar
- ✅ TP Levels — idéntico al original
- ✅ Señales LONG/SHORT — lógica correcta
- ✅ Dashboard — similar al original

## ❌ Lo que falta ajustar

- ❌ Range Filter sensitivity — demasiado reactivo
- ❌ ORB (Opening Range Breakout) — no implementado
- ❌ Session filter — no implementado (no crítico para el clon)

---

## 🎯 Próximos Pasos

1. **Ajustar Range Multiplier** hasta que señales coincidan
   - Probar: 4.0, 4.5, 5.0, 6.0
   - Criterio: Mismo número de señales en ventana de 1 día

2. **Comparación bar-by-bar** del valor del Range Filter
   - Objetivo: que `RangeFilter_clon ≈ RangeFilter_original` (±0.1%)

3. **Si no funciona:** Buscar otros algoritmos de Range Filter
   - LazyBear's version
   - Otros smoothing methods

4. **Implementar ORB** (opcional, no crítico para trading)

---

## 📚 Referencias

- [DonovanWall Range Filter](https://www.tradingview.com/script/lut7sBgG-Range-Filter-DW/)
- [Bloop Indicator TradingView](https://www.tradingview.com/script/YOUR_BLOOP_ID/) (privado/pago)
- [Hull Moving Average](https://school.stockcharts.com/doku.php?id=technical_indicators:hull_moving_average)

---

*Última actualización: 2026-02-12*
