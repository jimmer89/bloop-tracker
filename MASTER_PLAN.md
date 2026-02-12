# 🎯 Bloop Tracker — Master Plan

**Objetivo:** Validar el indicador Bloop con datos reales → Optimizar → Automatizar en MT5 → Operar en cuenta real.

**Inicio:** 2026-02-05
**Estado actual:** Fase 1 (Recolección)

---

## 📊 Visión General

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   FASE 1    │───▶│   FASE 2    │───▶│   FASE 3    │───▶│   FASE 4    │───▶│   FASE 5    │
│ Recolección │    │  Análisis   │    │     EA      │    │    Demo     │    │    Live     │
│   (ahora)   │    │ Optimización│    │ Development │    │   Trading   │    │   Trading   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
    ≥300 trades        Edge claro       EA funcional      1-2 meses OK       Escalar
        │                  │
        │    ┌─────────────────────────────┐
        └───▶│   TRACK PARALELO: CLON      │
             │   Ingeniería inversa del    │◀──── 🟡 EN PROGRESO
             │   indicador en PineScript   │
             └─────────────────────────────┘
```

---

## 🔴 FASE 1: Recolección de Datos (ACTUAL)

**Objetivo:** Acumular suficientes trades para análisis estadístico significativo.

**Estado:** 🟢 EN PROGRESO
- Webhook activo en Railway 24/7
- 79 trades capturados (2026-02-12)
- P&L neto actual: +428.5 pts

### Criterios para avanzar a Fase 2

| Métrica | Mínimo | Ideal |
|---------|--------|-------|
| Trades totales | 200 | 300+ |
| Días de datos | 14 | 30+ |
| Cobertura horaria | Todas las sesiones | — |

### Datos que se capturan

- Timestamp entrada/salida
- Precio entrada/salida
- Dirección (LONG/SHORT)
- P&L bruto y neto
- Duración del trade
- Max/Min durante el trade (para análisis de drawdown)

### Acciones

- [x] Webhook funcionando
- [x] Spread real configurado (0.9 pts)
- [ ] Esperar a ≥200 trades
- [ ] Verificar que no hay gaps en los datos

---

## 🟡 FASE 2: Análisis y Optimización

**Objetivo:** Identificar patrones, filtrar señales malas, encontrar el edge real.

**Estado:** ⏳ PENDIENTE

### Preguntas a responder

1. **¿Qué horarios funcionan mejor?**
   - Sesión asiática vs europea vs americana
   - Horas específicas con mejor win rate/P&L

2. **¿Hay días de la semana mejores?**
   - Lunes vs viernes
   - Días de alta volatilidad (NFP, FOMC)

3. **¿Qué señales filtrar?**
   - Trades muy cortos (<5 min)
   - Trades contra tendencia mayor
   - Señales en horarios de spread alto

4. **¿Cuál es el drawdown máximo?**
   - Por trade individual
   - Drawdown acumulado en racha perdedora

5. **¿Se puede mejorar el timing de salida?**
   - Exit en TP parcial
   - Trailing stop óptimo

### Entregables

- [ ] Análisis por horario (heatmap win rate)
- [ ] Análisis por día de semana
- [ ] Propuesta de filtros
- [ ] Backtest de filtros sobre datos históricos
- [ ] Documento con conclusiones

### Criterios para avanzar a Fase 3

| Métrica | Requerido |
|---------|-----------|
| Edge identificado | Sí (documentado) |
| Win rate con filtros | >50% |
| Profit Factor | >1.3 |
| Filtros definidos | Claros y medibles |

---

## 🟡 FASE 3: EA Development

**Objetivo:** Crear Expert Advisor en MQL5 que copie las señales del webhook a MT5.

**Estado:** ⏳ PENDIENTE

### Arquitectura

```
TradingView Alert ──▶ Webhook (Railway) ──▶ Signal File/API ──▶ EA MT5
                                                                   │
                                                                   ▼
                                                            Ejecutar orden
```

### Opciones de comunicación Webhook → MT5

1. **Archivo en disco** (simple)
   - Webhook escribe señal a archivo
   - EA lee archivo cada X segundos
   - Pro: Simple. Con: Requiere MT5 en mismo server

2. **WebRequest desde EA** (mejor)
   - EA hace polling a endpoint /signal
   - Pro: MT5 puede estar en cualquier sitio
   - Con: Latencia del polling

3. **Socket directo** (avanzado)
   - EA mantiene conexión socket
   - Webhook pushea señales
   - Pro: Tiempo real. Con: Más complejo

### Funcionalidades del EA

- [ ] Recibir señales LONG/SHORT
- [ ] Ejecutar orden con SL/TP configurables
- [ ] Filtros de horario (solo operar en horas definidas)
- [ ] Filtro de spread máximo
- [ ] Logging completo
- [ ] Gestión de posición (solo 1 abierta)
- [ ] Trailing stop opcional

### Criterios para avanzar a Fase 4

| Requisito | Estado |
|-----------|--------|
| EA compila sin errores | ⬜ |
| Recibe señales correctamente | ⬜ |
| Ejecuta órdenes en demo | ⬜ |
| No hay bugs críticos | ⬜ |
| Logging funciona | ⬜ |

---

## 🟡 FASE 4: Demo Trading

**Objetivo:** Validar el sistema completo con dinero virtual antes de arriesgar capital real.

**Estado:** ⏳ PENDIENTE

### Setup

- Cuenta demo IC Markets (mismo broker que análisis de spread)
- EA corriendo 24/5
- Monitorización diaria

### Métricas a trackear

| Métrica | Target |
|---------|--------|
| Duración mínima | 4-8 semanas |
| Trades ejecutados | ≥50 |
| Win rate | >50% |
| Profit Factor | >1.3 |
| Max drawdown | <15% |
| Slippage promedio | <2 pts |
| Errores de ejecución | 0 |

### Checklist

- [ ] EA corriendo sin intervención manual
- [ ] Trades coinciden con señales del webhook
- [ ] No hay trades fantasma ni duplicados
- [ ] Resultados similares al backtest

### Criterios para avanzar a Fase 5

| Requisito | Estado |
|-----------|--------|
| 4+ semanas sin bugs | ⬜ |
| Resultados consistentes con análisis | ⬜ |
| Drawdown controlado | ⬜ |
| Confianza personal (gut check) | ⬜ |

---

## 🟡 FASE 5: Live Trading

**Objetivo:** Operar con dinero real, empezando pequeño y escalando.

**Estado:** ⏳ PENDIENTE

### Gestión de riesgo

| Parámetro | Inicio | Escalado |
|-----------|--------|----------|
| Capital inicial | €500-1000 | — |
| Riesgo por trade | 0.5-1% | Hasta 2% |
| Lotaje | 0.1 | Incrementar gradual |
| Drawdown máximo | 10% | Pausar si se supera |

### Reglas de escalado

1. **Mes 1:** Lotaje mínimo (0.1), observar
2. **Mes 2:** Si rentable, subir a 0.2
3. **Mes 3+:** Incrementar gradualmente si consistente
4. **Si drawdown >10%:** Pausar, revisar, ajustar

### Reglas de pausa

- 5 pérdidas consecutivas → Pausar 24h
- Drawdown >10% → Pausar hasta revisión
- Bug detectado → Pausar inmediatamente

---

## 📅 Timeline Estimado

| Fase | Duración | Fecha estimada |
|------|----------|----------------|
| Fase 1 (Recolección) | 2-4 semanas | Feb-Mar 2026 |
| Fase 2 (Análisis) | 1-2 semanas | Mar 2026 |
| Fase 3 (EA) | 1-2 semanas | Mar-Abr 2026 |
| Fase 4 (Demo) | 4-8 semanas | Abr-May 2026 |
| Fase 5 (Live) | Ongoing | Jun 2026+ |

**Total hasta live:** ~3-4 meses

---

## ⚠️ Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Indicador deja de funcionar | Media | Alto | Tener backup, no depender 100% |
| Overfitting en optimización | Alta | Medio | Walk-forward, out-of-sample test |
| Spread aumenta | Baja | Medio | Monitorear, pausar si >2 pts |
| Bugs en EA | Media | Alto | Testing exhaustivo en demo |
| Slippage en real | Media | Medio | Asumir 1-2 pts extra en cálculos |
| Pérdida de capital | Media | Alto | Empezar pequeño, SL siempre |

---

## 📁 Recursos

| Recurso | Ubicación |
|---------|-----------|
| Webhook server | `bloop-tracker/webhook_server.py` |
| Datos en vivo | https://web-production-62bc.up.railway.app/stats |
| Análisis spread | `edge-research/analysis/USTEC_spread_analysis_2026-02-10.md` |
| SpreadMonitor EA | `mql5/SpreadMonitor_USTEC.mq5` |

---

---

## 🔬 TRACK PARALELO: Clon del Indicador

**Objetivo:** Clonar el indicador Bloop para no depender de suscripción de pago.

**Estado:** 🟡 EN PROGRESO

### Parámetros capturados del original

| Parámetro | Valor |
|-----------|-------|
| SmoothRNG Sensitivity | 8 |
| HTF Timeframe | 15 min |
| HTF MA Type | HMA |
| HTF MA Length | 20 |
| ATR Length (Trailing) | 10 |
| ATR Mult (Trailing) | 1.5 |
| ATR Length (Targets) | 14 |
| TP1/TP2 ATR Multiple | 2 / 4 |

### Versiones

| Versión | Estado | Problema |
|---------|--------|----------|
| v1 | ❌ Descartada | Demasiado sensible |
| v2 | 🟡 En ajuste | Range Multiplier incorrecto |

### Algoritmo usado (v2)

- **DonovanWall's Range Filter** (Type 1)
- Source: https://www.tradingview.com/script/lut7sBgG-Range-Filter-DW/
- Default multiplier: 2.618 → **Probando 3.5+**

### Próximos pasos

1. Probar Range Multiplier: 4.0, 4.5, 5.0
2. Comparar valores numéricos del Range Filter
3. Si no converge: buscar otros algoritmos

### Archivos

| Archivo | Descripción |
|---------|-------------|
| `pinescript/BloopClone_v1.pine` | Primera versión (descartada) |
| `pinescript/BloopClone_v2.pine` | Versión actual |
| `pinescript/REVERSE_ENGINEERING.md` | Documentación detallada |

---

## 📝 Changelog

| Fecha | Cambio |
|-------|--------|
| 2026-02-12 | Ingeniería inversa iniciada, v2 del clon creada |
| 2026-02-12 | Master Plan creado |
| 2026-02-12 | Bug spread corregido (90→0.9), sistema ahora rentable |
| 2026-02-10 | Análisis spread completado |
| 2026-02-05 | Proyecto iniciado |

---

*Última actualización: 2026-02-12*
