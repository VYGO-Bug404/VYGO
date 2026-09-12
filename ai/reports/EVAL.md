# Evaluación pareada -- reto Infosys "The Courier"

Generado: 2026-09-12T18:32:00+00:00
Escenarios: 30 congelados en `scenarios/test_30.pkl` (ver `scenarios/test_30.sha256`), 15 con SURGE y 15 con CIERRE_VIAL, evento siempre a partir del minuto 60. Evaluación PAREADA: cada política corre EXACTAMENTE los mismos 30 escenarios.
Políticas evaluadas: B1, B2, agente(PPO)

## TOTAL

| Política | rho mediana | rho IQR | entregados | pedidos/h | tasa aceptación | puntualidad | km/pedido | bundling |
|---|---|---|---|---|---|---|---|---|
| B1 | 213.19 | [162.48, 361.75] | 10.20 | 5.10 | 0.01 | 0.97 | 3.75 | 0.90 |
| B2 | 245.94 | [128.56, 356.44] | 9.77 | 4.88 | 0.00 | 1.00 | 3.85 | 0.87 |
| agente(PPO) | 208.98 | [153.67, 340.36] | 9.93 | 4.97 | 0.00 | 0.97 | 3.71 | 0.89 |

## ANTES del evento

| Política | rho mediana | rho IQR | entregados | pedidos/h | tasa aceptación | puntualidad | km/pedido | bundling |
|---|---|---|---|---|---|---|---|---|
| B1 | 310.84 | [261.50, 343.46] | 6.17 | 6.17 | 0.01 | 0.97 | 3.64 | 0.93 |
| B2 | 300.93 | [219.97, 347.97] | 6.00 | 6.00 | 0.00 | 1.00 | 3.83 | 0.91 |
| agente(PPO) | 303.44 | [275.80, 349.50] | 6.43 | 6.43 | 0.00 | 0.97 | 3.47 | 0.91 |

## DESPUÉS del evento

| Política | rho mediana | rho IQR | entregados | pedidos/h | tasa aceptación | puntualidad | km/pedido | bundling |
|---|---|---|---|---|---|---|---|---|
| B1 | 130.08 | [0.00, 355.36] | 4.03 | 4.03 | 0.00 | 0.67 | 2.98 | 0.84 |
| B2 | 129.53 | [0.00, 360.14] | 3.77 | 3.77 | 0.00 | 0.67 | 2.61 | 0.78 |
| agente(PPO) | 84.56 | [8.60, 340.24] | 3.50 | 3.50 | 0.00 | 0.73 | 3.66 | 0.77 |

## % de mejora sobre B1 (rho mediana, total, bootstrap pareado)

- **B2 vs B1**: +15.4% (IC 95%, 10000 remuestreos: [-39.4%, +49.1%])
- **agente(PPO) vs B1**: -2.0% (IC 95%, 10000 remuestreos: [-38.8%, +39.7%])

## Reacción al evento -- ejemplo concreto (emergente, no programado)

### SURGE

SURGE en (0,4), x1.4 tarifa / x1.6 intensidad de llegada, minuto 60-105. Misma oferta (recoger en (0,4), entregar en (0,10), 596s de viaje), misma `politica_umbral`, mismo `rho_hat`=150 MXN/h:  
  - Antes del surge: precio=22.36 MXN -> tasa_marginal=98.8 MXN/h < rho_hat -> decisión = rechazar_todas.  
  - Con el surge activo: precio=31.30 MXN (x1.4) -> tasa_marginal=152.8 MXN/h > rho_hat -> decisión = aceptar oferta 0.  
  Nada en `politica_umbral` sabe que existe un evento: sólo ve un precio más alto y la MISMA regla de umbral cruza de rechazar a aceptar.

### CIERRE_VIAL

CIERRE_VIAL en la columna 10 (factor_detour=1.7x), minuto 60-100. Mismos 4 stops (A y B, recogida/entrega a los dos lados de la columna 10), mismo `held_karp`:  
  - Antes del cierre: tiempo_total=1423s, dist_total=12000m, orden=[0, 2, 1, 3].  
  - Con el cierre activo: tiempo_total=1828s (+405s, +28%), dist_total=15500m, orden=[0, 2, 1, 3].  
  `held_karp` no sabe que hay un evento: sólo ve un `travel_fn` que ahora cobra 1.7x al cruzar la columna 10, y recalcula el óptimo con esa única diferencia.
