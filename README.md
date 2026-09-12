# VYGO — Frontend

**HACK MTY 2026 · Reto Infosys "The Courier"**

Aplicación móbil web para repartidores que trabajan en múltiples plataformas (Uber Eats, Rappi, DiDi Food). VYGO es la capa intermedia: recibe ofertas de trabajo de cada plataforma, consulta un agente de RL que decide qué conviene aceptar y por qué, y presenta al repartidor una recomendación clara con justificación numérica.

---

## La meta

Un repartidor que trabaja solo con Rappi gana $102/hr. Un repartidor que usa VYGO con el agente PPO gana $169/hr sobre el mismo turno, recorriendo 35% menos kilómetros.

La diferencia viene de dos cosas:
1. **Agrupamiento (bundling):** mientras esperas que un restaurante termine de preparar, el agente detecta si existe otro pedido que cabe dentro de ese tiempo muerto y lo acepta antes de que la espera sea un costo.
2. **Filtrado por tasa:** rechazar pedidos que pagan menos de tu promedio actual no parece intuitivo, pero es la decisión correcta cuando el tiempo tiene costo de oportunidad.

El frontend no calcula nada de esto. Lo presenta. Todo el razonamiento viene del agente.

---

## Stack

| Capa | Tecnología |
|------|-----------|
| UI | React 18 + TypeScript + Vite |
| Estilos | Tailwind CSS v3 (tokens de marca custom) |
| Estado | Zustand (auth, driver, orders, route) |
| Rutas | React Router v6 |
| Mapa | MapLibre GL JS v6 + MapTiler Dark |
| Backend/Auth | Supabase (Auth + PostgreSQL + PostGIS) |
| Agente RL | REST `POST /decidir` (ver §Contrato del agente) |
| Deploy | Vercel |

---

## Correr en local

```bash
npm install
npm run dev        # http://localhost:5173
```

Variables de entorno necesarias en `.env.local`:

```env
VITE_MAPTILER_KEY=<tu_key_de_maptiler>
VITE_SUPABASE_URL=https://ihmadvmoenkxanoxrwcy.supabase.co
VITE_SUPABASE_ANON_KEY=<anon_key>
VITE_AGENT_URL=http://localhost:8000   # opcional — si no está, usa fallback B2
```

Si `VITE_AGENT_URL` no está configurado, el frontend calcula la decisión localmente con la regla de umbral (B2). El agente real solo cambia esa URL.

---

## Pantallas y flujo del repartidor

```
[Login / Register]
        │
        ▼
[Inicio] ─────────────────────────────────────────────────────────────
  │  Mapa en tiempo real con ubicación GPS del repartidor
  │  Si offline: botón "Comenzar jornada"
  │  Si online: métricas del turno + botón "Terminar jornada"
  │  Al llegar un pedido → aparece NewOrderSheet (slide-up)
        │
        ▼
[NewOrderSheet — la pantalla más importante]
  │  Explicación del agente: "+$187/h vs tu $141/h"
  │  Los 3 números del criterio:
  │    - tasa_marginal_mxn_h  (lo que paga este pedido)
  │    - rho_actual_mxn_h     (lo que ganas tú ahora)
  │    - ajuste_aprendido     (corrección de valor posicional del RL)
  │  Ruta pickup → dropoff
  │  Barras de frescura y probabilidad de entrega a tiempo
  │  Botón "Aceptar" / "Rechazar"
        │
        ▼
[Ruta activa /route]
  │  Mapa full-screen siguiendo al repartidor con GPS
  │  Markers: círculo verde = pickup #1, triángulo = pickups extra, óvalo naranja = entregas
  │  Banner superior: "Dirígete al restaurante / Dirígete a entregar"
  │  Card inferior: plataforma + número + botón de avance + siguiente pedido
  │  Al recoger el paquete: marker de pickup desaparece, queda el óvalo de entrega
  │  Al entregar todos: pantalla de resumen de jornada
        │
        ▼
[Sin pedidos activos — resumen de jornada]
  │  Total ganado, tiempo trabajado, entregas, pedidos/hr
  │  Proyección: "+1h más → $X total"
  │  Botón "Seguir trabajando" o "Terminar jornada"
        │
        ├──▶ [Pedidos /orders]  — historial con tabs En curso / Completados
        ├──▶ [Ganancias /earnings]  — gráfica por hora, por plataforma
        └──▶ [Perfil /profile]  — datos, plataformas, logout
```

---

## Mapa — Marcadores

| Shape | Color | Significa |
|-------|-------|-----------|
| Círculo | Verde | Punto de recolección del primer pedido |
| Triángulo | Verde | Punto de recolección de pedidos extra (2, 3…) |
| Óvalo | Naranja | Punto de entrega (cualquier pedido) |
| Punto pulsante | Verde | Posición actual del repartidor (GPS real) |

Los números son **estables**: el pedido 2 siempre es "2" aunque el 1 ya se haya entregado. Al recoger un pedido su marker desaparece; solo queda el óvalo del destino.

---

## Contrato del agente (v1.0)

El agente expone tres superficies. Para el pitch se usa la C.

### A — Decisión puntual

```
POST /decidir
Content-Type: application/json
```

El frontend manda el estado actual (posición, plan activo, ofertas pendientes, contexto) y recibe una `RespuestaDecidir`. Timeout: 2 segundos. Si falla, cae a B2.

**Campos que el frontend muestra obligatoriamente:**

```
decisiones[0].explicacion_corta     "+$187/h vs tu $141/h"
decisiones[0].economia.tasa_marginal_mxn_h
decisiones[0].economia.rho_actual_mxn_h
decisiones[0].economia.ajuste_aprendido_mxn_h
plan.resumen.optimo_exacto          true/false
plan.resumen.secuencias_evaluadas   número de rutas evaluadas
```

### B — Turno en vivo (SSE)

```
GET /turno/stream?escenario=12&politica=agente_ppo&velocidad=4
```

Server-Sent Events. Cada mensaje es un `Frame` con campo `tipo` y tiempo `t` en segundos desde inicio del turno. El frontend aplica cada frame como mutación sobre su estado.

### C — Replay pareado (demo del pitch)

Archivo estático `public/replay_12.json`. Contiene el mismo turno resuelto por tres políticas:

| Política | Etiqueta | Resultado |
|----------|----------|-----------|
| `B1_simple` | Sin VYGO | $612 · $102/hr · 11 entregas |
| `B2_umbral` | VYGO (regla) | $948 · $158/hr · 17 entregas |
| `agente_ppo` | VYGO (agente RL) | $1,014 · $169/hr · 18 entregas |

La comparación es válida porque las tres pistas comparten el mismo escenario: mismas órdenes, mismo clima, mismo evento surge a las 3h de turno.

### Fallback en cascada

```
agente_ppo via /decidir
    │ timeout 2s o HTTP error
    ▼
B2_umbral calculado localmente
    │ VITE_AGENT_URL no definida
    ▼
Datos mock (public/replay_12.json)
```

El campo `politica` de la respuesta siempre indica qué se usó. Se muestra en la UI como badge pequeño.

### Tipos TypeScript

Todos los tipos están en `src/lib/vygoAgent.ts`. Son la fuente de verdad de la interfaz entre el agente y el frontend. Si un campo cambia, se actualiza ahí y se sube la versión del contrato.

```ts
import type { RespuestaDecidir, DecisionOferta, Plan, Frame } from '@/lib/vygoAgent'
```

---

## Base de datos (Supabase)

**Proyecto:** `vygo app` · `ihmadvmoenkxanoxrwcy.supabase.co`

### Tablas principales

| Tabla | Descripción |
|-------|-------------|
| `apps` | Plataformas: uber, didi, rappi |
| `usuarios` | Clientes y repartidores |
| `repartidores` | Perfil operativo del repartidor |
| `pedidos` | Pedido con origen/destino PostGIS |
| `viajes_repartidor` | Viaje activo con ruta LineString |
| `viaje_pedidos` | Pedidos dentro de un viaje (orden) |
| `ofertas_pedido` | Oferta a repartidor (pendiente/aceptada/rechazada) |
| `difusiones_pedido` | Rondas de búsqueda por radio |
| `ubicaciones_conductores` | Posición GPS en tiempo real (RLS por auth.uid) |

### Ciclo de vida de un pedido

```
[app externa] → pedidos (buscando)
             → difusiones_pedido (ronda 1, radio 500m)
             → ofertas_pedido (pendiente → repartidor responde)
             → pedidos (asignado)
             → viaje_pedidos (orden en la ruta)
             → pedidos (en_camino → entregado)
```

### Lo que actualmente usa el frontend

- **Auth real:** `supabase.auth.signInWithPassword / signUp / signOut`
- **GPS en tiempo real:** `ubicaciones_conductores` — actualización cada 8s o cada 15m de movimiento
- **Pending:** pedidos, viajes, ofertas — todavía mock en el frontend, listos para conectar

---

## Estado global (Zustand)

```
auth.store      isAuthenticated, email, userId
driver.store    status (offline→online→active_route), shiftStartedAt, earnings
orders.store    activeOrders, completedOrders, pendingOffer, _nextRouteNumber
route.store     stops[], currentStopIndex
```

### Flujo de estados del driver

```
offline  ──startShift()──▶  online  ──acceptOffer()──▶  active_route
                                                              │
                         ◀──last order delivered───────────────
                         ◀──endShift() desde cualquier estado
```

---

## Estructura del proyecto

```
src/
├── lib/
│   ├── vygoAgent.ts      ← tipos del contrato del agente (fuente de verdad)
│   └── supabase.ts       ← cliente de Supabase
├── services/
│   ├── agent.service.ts  ← POST /decidir con fallback B2
│   ├── mock-data.ts      ← datos mock para desarrollo
│   └── orders.service.ts
├── stores/               ← Zustand (auth, driver, orders, route)
├── hooks/
│   ├── useNewOrder.ts    ← simula llegada de pedidos cada ~15s
│   ├── useLocationTracking.ts ← GPS → Supabase
│   ├── useEndShift.ts    ← terminar jornada con confirmación
│   └── useActiveRoute.ts ← parada actual del viaje
├── components/
│   ├── maps/MockMap.tsx  ← MapLibre GL + GPS + markers + ruta
│   ├── orders/NewOrderSheet.tsx ← tarjeta de oferta con datos del agente
│   └── layout/           ← AppLayout, BottomNavigation, AuthLayout
└── pages/
    ├── Home/             ← mapa + métricas + estado de jornada
    ├── ActiveRoute/      ← conducción + resumen sin pedidos
    ├── Orders/           ← historial
    ├── Earnings/         ← gráficas
    ├── Profile/          ← perfil + logout
    └── Login / Register/
```

---

## Convenciones de coordenadas

Del contrato del agente — el error más frecuente:

| Contexto | Orden | Ejemplo |
|----------|-------|---------|
| JSON general | `{ lat, lon }` | `{ lat: 25.67, lon: -100.31 }` |
| GeoJSON (`geometria`) | `[lon, lat]` | `[-100.31, 25.67]` |
| MapLibre `setLngLat` | `[lng, lat]` | `[-100.31, 25.67]` |
| Supabase PostGIS | `ST_MakePoint(lon, lat)` | longitud primero |

Si los marcadores aparecen en el océano Índico, está invertido el orden.

---

## Deploy

La app está desplegada en **Vercel**: [vygo-ten.vercel.app](https://vygo-ten.vercel.app)

Variables configuradas en Vercel:
- `VITE_MAPTILER_KEY`
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_AGENT_URL` ← vacío hasta que el agente esté disponible

Cuando el equipo de IA entregue el servidor, solo hay que actualizar `VITE_AGENT_URL` en Vercel y hacer redeploy. Ningún otro cambio en el frontend.

---

## Lista de verificación del pitch

- [ ] Replay estático abre sin servidor ni internet (`public/replay_12.json`)
- [ ] Marcadores caen en Monterrey (no en el océano)
- [ ] `explicacion_corta` visible en la tarjeta de oferta
- [ ] Los tres números del criterio visibles: tasa\_marginal, rho\_actual, ajuste\_aprendido
- [ ] `optimo_exacto` + `secuencias_evaluadas` visibles
- [ ] Badge de `politica` muestra qué política respondió
- [ ] GPS muestra ubicación real al abrir la app
- [ ] Mapa sigue al repartidor mientras conduce
- [ ] Al entregar todos los pedidos aparece resumen de jornada
- [ ] Terminar jornada con pedidos activos pide confirmación

---

*VYGO · Muévete mejor. Gana más.*
