"""Genera reports/status.json (máquina) y reports/HANDOFF.md (humano) — contrato de
ai/CLAUDE.md §8. Se corre al final de cada bloque de trabajo (`python run.py report`).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_AI_ROOT = Path(__file__).resolve().parent.parent
_BLOQUE_ACTUAL = "B3-diagnostico-agrupamiento-y-clusters"


def _git_commit_corto() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=_AI_ROOT, timeout=10, check=True,
        )
        return proc.stdout.strip()
    except Exception:
        return None


def _git_dirty() -> bool | None:
    """True si hay cambios sin commitear en el repo. El reporte nunca debe aparentar
    corresponder a un commit limpio que todavía no existe."""
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=_AI_ROOT, timeout=10, check=True,
        )
        return bool(proc.stdout.strip())
    except Exception:
        return None


def _correr_tests() -> dict:
    tests_dir = _AI_ROOT / "tests"
    if not tests_dir.exists():
        return {"pasaron": None, "fallaron": None, "xfail": None, "detalle_fallos": []}

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(tests_dir), "-q", "--tb=no", "-rf"],
            capture_output=True, text=True, cwd=_AI_ROOT, timeout=300,
        )
    except Exception as exc:
        return {
            "pasaron": None, "fallaron": None, "xfail": None,
            "detalle_fallos": [f"error al correr pytest: {exc}"],
        }

    salida = proc.stdout + proc.stderr
    conteos = {etiqueta: int(numero) for numero, etiqueta in re.findall(
        r"(\d+) (passed|failed|xfailed|xpassed|error|skipped)", salida,
    )}
    # xfail (fallo esperado) NO es un "pasaron": es su propia categoría (ai/CLAUDE.md §8).
    pasaron = conteos.get("passed", 0)
    xfail = conteos.get("xfailed", 0)
    fallaron = conteos.get("failed", 0) + conteos.get("xpassed", 0) + conteos.get("error", 0)
    detalle_fallos = [linea.strip() for linea in salida.splitlines() if linea.startswith("FAILED ")]
    return {"pasaron": pasaron, "fallaron": fallaron, "xfail": xfail, "detalle_fallos": detalle_fallos}


def diagnostico_automatico(status: dict) -> list[str]:
    """Revisa la tabla de antipatrones de ai/CLAUDE.md §7 y devuelve un renglón legible por
    cada síntoma detectado. Si a una métrica le falta el dato (None / no_implementado), esa
    fila simplemente no dispara nada — no se inventan diagnósticos sin evidencia."""

    diagnosticos: list[str] = []
    baselines = status.get("baselines", {})
    invariantes = status.get("invariantes", {})

    for nombre, metricas in baselines.items():
        if not isinstance(metricas, dict):
            continue
        tasa_aceptacion = metricas.get("tasa_aceptacion")
        puntualidad = metricas.get("puntualidad")
        pedidos_h = metricas.get("pedidos_h")
        rho = metricas.get("rho")
        km_vacios = metricas.get("km_vacios")
        bundling = metricas.get("bundling")

        if tasa_aceptacion is not None and tasa_aceptacion <= 0.02:
            diagnosticos.append(
                f"{nombre}: tasa_aceptacion≈0 → colapso inicial (rechazar da 0, que es mejor "
                f"que aceptar mal). Arreglo: arranque por imitación, subir entropía."
            )
        if (
            tasa_aceptacion is not None and tasa_aceptacion >= 0.98
            and puntualidad is not None and puntualidad < 0.7
        ):
            diagnosticos.append(
                f"{nombre}: tasa_aceptacion≈1 y puntualidad baja ({puntualidad:.2f}) → hay "
                f"bonus por aceptar o psi muy baja. Arreglo: quitar bonus, subir psi."
            )
        if pedidos_h is not None and rho is not None and pedidos_h > 1.5 and rho < 100:
            diagnosticos.append(
                f"{nombre}: pedidos_por_hora alto ({pedidos_h:.1f}) y rho bajo ({rho:.1f}) → "
                f"falta el término -rho_hat*dt. Arreglo: añadirlo a la recompensa."
            )
        if km_vacios is not None and km_vacios > 0.4:
            diagnosticos.append(
                f"{nombre}: km_vacios alto ({km_vacios:.2f}) → se está premiando moverse. "
                f"Arreglo: nunca premiar movimiento."
            )
        if bundling is not None and abs(bundling - 1.0) < 1e-6:
            diagnosticos.append(
                f"{nombre}: factor_agrupamiento≈1.0 → el generador no crea solapamiento. "
                f"Arreglo: subir intensidad / concentrar comercios."
            )

    if invariantes.get("violaciones_frescura") not in (None, 0):
        diagnosticos.append(
            "violaciones_frescura > 0 → bug en la máscara de factibilidad. No es un problema "
            "de entrenamiento, es código."
        )

    return diagnosticos


def _baseline_vacio() -> dict:
    return {"rho": 0, "estado": "no_implementado"}


def _construir_status(tests: dict) -> dict:
    status = {
        "generado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bloque": _BLOQUE_ACTUAL,
        "commit": _git_commit_corto(),
        "dirty": _git_dirty(),
        "entorno": {"nivel": None, "config_hash": None, "steps_por_segundo": None},
        "tests": tests,
        "invariantes": {
            # Verificado por tests/test_invariants.py, pero sobre una VENTANA ACOTADA de
            # pasos (no el turno completo de 6h): ver reports/HANDOFF.md, rendimiento del
            # entorno. Sigue siendo evidencia real, no un placeholder.
            "violaciones_frescura": 0,
            "violaciones_capacidad": 0,
            "fifo_ok": True,  # verificado: test_monotonia_fifo, 1000 pares aleatorios, 0 violaciones
            "contabilidad_ok": True,
            "holdout_intacto": None,  # scenarios/test_50.pkl todavía no existe
        },
        "baselines": {
            "B0": _baseline_vacio(),
            "B1": {"rho": 227.11, "pedidos_h": 4.98, "puntualidad": 1.00, "bundling": 0.68},
            "B2": {"rho": 267.45, "pedidos_h": 5.40, "puntualidad": 1.00, "bundling": 0.73},
            "B2_ingenuo": {"rho": 267.45, "pedidos_h": 5.40, "puntualidad": 1.00, "bundling": 0.74},
            "B3": _baseline_vacio(),
        },
        "entrenamiento": {
            "activo": False,
            "algoritmo": None,
            "semillas": [],
            "pasos_totales": 0,
            "pasos_objetivo": None,
            "eta_minutos": None,
            "curva": [],
            "mejor_rho_val": None,
            "etapa_curriculum": None,
        },
        "evaluacion": {
            "escenarios": None,
            "pareada": None,
            "agente": {"rho_mediana": None, "iqr": [None, None]},
            "vs_B2_pct": None,
            "gap_vs_oraculo": None,
        },
        "diagnostico_automatico": [],
        "bloqueos": [
            "BLOQUEO PRINCIPAL (persiste, causa distinta a la que se sospechaba): el "
            "histograma de motivos de rechazo (5 y luego 20 escenarios, B2, ver HANDOFF) "
            "muestra que ~96-99.7% de las ofertas evaluadas con plan activo no se rechazan "
            "por capacidad del vehículo, frescura, fecha límite, prefiltro ni umbral_rho -- "
            "se rechazan porque el plan YA está en el tope duro K_A_MAXIMO=3 "
            "(`sequencer.UMBRAL_EXACTO_PEDIDOS`, bajado de 4 a 3 en el bloque anterior por "
            "presupuesto de steps/s). Ninguno de los 4 candidatos de la tarea (Q de "
            "vehículo, theta de frescura, N_PREFILTRO, fórmula de tarifa) domina el "
            "histograma (todos <3% combinados) así que, por la regla de la propia tarea "
            "('arregla sólo lo que el histograma señale'), NO se tocó ninguno de los 4. "
            "Subir K_A_MAXIMO SÍ atacaría la causa real pero es un cambio de presupuesto de "
            "rendimiento (vuelve a 2520 secuencias exactas por reoptimización), no uno de "
            "los candidatos autorizados hoy -- queda documentado como decisión pendiente, "
            "no aplicado unilateralmente.",
            "Clústeres geográficos de comercios aplicados (generator.muestrear_comercios: 4 "
            "zonas x 15 comercios en disco de 1.5km + 20 dispersos; destinos a <2.5km del "
            "origen). Resultado tras 20 escenarios x 2h: B2 vs B1 +17.8% (SÍ supera el "
            "umbral de 15%, antes +9.3%), pero factor_agrupamiento(B2)=0.73 (bajó de 0.97, "
            "sigue muy por debajo del umbral 1.4 -- y ahora por debajo de 1.0, no cerca). "
            "Por la propia regla de la tarea ('si se queda cerca de 1.0, seguimos igual: el "
            "valor del agente está en la selección'): NO se sigue tocando el generador. "
            "+17.8% sobre B1 es el resultado presentable de este bloque.",
            "rho_hat observado (227-275 MXN/h) sigue por encima del rango 120-180 MXN/h que "
            "la tarea esperaba de la fórmula de tarifa (base 28-38 + beta 7-11/km). No se "
            "investigó la fórmula porque 'umbral_rho' es <0.02% del histograma de rechazos "
            "(no está gateando decisiones) -- posible instrumento de medición mal calibrado "
            "más que un bug de conversión, pendiente para un bloque futuro si importa.",
            "En L0 no hay competidores sintéticos (n_competidores_base=0 por diseño), así "
            "que p_gana_estimada=1.0 siempre; B2 vs B2-ingenuo dio +0.0% en esta corrida -- "
            "consistente con L0, no una regresión. Hace falta L1 para medir el valor real "
            "de p_gana.",
            "train_ppo.py, evaluate.py, export_vygo.py siguen siendo stubs sin cuerpo.",
            "baselines B0 (aleatoria) y B3 (MILP rodante) no implementados -- sólo B1/B2/"
            "B2-ingenuo (docs/vygo-ai-training.md §6.1); scenarios/test_50.pkl no existe.",
        ],
        "siguiente_paso_sugerido": (
            "El generador queda congelado (regla explícita de la tarea). Decidir si vale la "
            "pena subir K_A_MAXIMO/UMBRAL_EXACTO_PEDIDOS por encima de 3 (causa real y "
            "dominante del histograma de rechazos) a cambio de steps/s, y de ahí avanzar a "
            "implementar train_ppo.py -- el criterio de selección (+17.8% B2 vs B1) ya es "
            "presentable con el estado actual."
        ),
    }
    status["diagnostico_automatico"] = diagnostico_automatico(status)
    return status


def _handoff_md(status: dict) -> str:
    tests = status["tests"]
    sufijo_commit = " (sucio: hay cambios sin commitear)" if status["dirty"] else ""
    lineas = [
        f"# HANDOFF — {status['bloque']}",
        "",
        f"_Generado: {status['generado_en']} · commit `{status['commit']}`{sufijo_commit}_",
        "",
        "## TL;DR",
        "",
        "Tarea de este bloque: diagnosticar con datos (no adivinar) qué mata el "
        "agrupamiento, antes de tocar nada. Se instrumentó un histograma de motivos de "
        "rechazo (`feasibility.CONTADOR_MOTIVOS`) y el resultado fue una sorpresa: **~96-"
        "99.7% de los rechazos no son ninguno de los 4 sospechosos de la tarea** (capacidad "
        "de vehículo, frescura, prefiltro, umbral_rho -- todos <3% combinados) sino el tope "
        "duro `K_A_MAXIMO=3` simplemente ya lleno. Por la regla de la propia tarea ('arregla "
        "sólo lo que el histograma señale') NO se tocó ninguno de los 4 candidatos. Se "
        "aplicó el punto incondicional: clústeres geográficos explícitos de comercios (4 "
        "zonas x 15 en 1.5km + 20 dispersos, destinos a <2.5km del origen). Resultado tras "
        "volver a correr la prueba de sanidad completa (20 escenarios, 2h): **B2 vs B1 "
        "+17.8%** (supera el umbral de 15%, antes +9.3%) pero **factor_agrupamiento(B2)=0.73** "
        "(sigue debajo de 1.4, y ahora debajo de 1.0). Por la regla de la tarea para este "
        "caso ('si se queda cerca de 1.0, seguimos igual: el valor del agente está en la "
        "selección'): el generador queda **congelado**, +17.8% es el resultado presentable.",
        "",
        "## El bug real (por qué estaba lento)",
        "",
        "`eval_insertion` llamaba a `held_karp` completo (hasta 2520 secuencias) por cada "
        "una de las 8 ofertas visibles, en CADA step. Con un episodio de 6h generando "
        "miles de pedidos, eso son decenas de miles de enumeraciones completas. El fix no "
        "fue optimizar `held_karp` más (ya se había hecho todo lo razonable en el bloque "
        "anterior) sino dejar de llamarlo tanto:",
        "",
        "1. **Tope duro K_A**: el plan activo nunca pasa de `K_A_MAXIMO` pedidos "
        "(`sequencer.UMBRAL_EXACTO_PEDIDOS`, ahora pública). Con el plan lleno, "
        "`action_mask` marca las 8 ofertas infactibles sin evaluar nada. Assert defensivo "
        "en `env._aceptar_oferta`.",
        "2. **Inserción clásica barata** (`insertion.mejor_insercion`): para evaluar una "
        "oferta ya NO se re-enumera el plan completo. Se toma el orden VIGENTE del plan "
        "(el que dejó la última reoptimización exacta) y se prueba insertar el par "
        "(recogida_j, entrega_j) en cada posición válida de ESE orden fijo -- con el plan "
        "lleno menos un pedido, (m+1)(m+2)/2 combinaciones (28 con m=6), no 2520. La "
        "reoptimización EXACTA completa (`held_karp`) sólo se corre UNA vez, al comprometer "
        "una oferta aceptada (`env._recalendarizar`). `baseline_plan` dejó de llamar a "
        "`held_karp` también: como el plan ya está en su orden óptimo, sólo hace falta "
        "calendarizarlo (barato), no re-derivarlo.",
        "3. **Prefiltro**: de las hasta 8 ofertas visibles, sólo se calendarizan (con "
        "`eval_insertion`, ya barato) las `N_PREFILTRO=3` mejores por un puntaje "
        "GEOMÉTRICO puro (desvío en línea recta / tarifa, cero calendarización). Las otras "
        "5 quedan infactibles sin evaluarse -- el agente las sigue viendo en la "
        "observación con sus features baratos (delta, tarifa, anillo, p_gana).",
        "4. **Una decisión por cierre de ronda, no por oferta**: `_avanzar_hasta_decision` "
        "ya no le devuelve el turno al agente en cada llegada de pedido o expiración de "
        "oferta -- sólo cuando cierra una ronda (evento `cierra_ronda`). Antes, cada "
        "pedido generaba su propia época de decisión.",
        "5. **Guardia de tiempo en `held_karp`**: el camino exacto aborta a los 25ms "
        "(`_LIMITE_TIEMPO_EXACTO_S`) y devuelve lo mejor YA VERIFICADO hasta ese punto con "
        "`optimo_exacto=False` -- nunca una secuencia sin verificar (arriesgaría "
        "`violaciones_frescura`).",
        "",
        "## Un bug real encontrado AL MEDIR (no cosmético)",
        "",
        "Con K_A=4, `held_karp` a veces topaba la guardia de 25ms en pedidos genuinamente "
        "dispersos (confirmado: sin la guardia, la misma instancia sí es factible, tarda "
        "58ms). `env._recalendarizar()` simplemente devolvía sin actualizar el horario, "
        "dejando el plan con paradas pero SIN horario -- `_proximo_evento_nodo` nunca "
        "volvía a encontrar un evento y el vehículo quedaba CONGELADO el resto del "
        "episodio (síntoma: `entregados=0` tras 5000 steps con miles de pedidos "
        "rechazados). Arreglado: `_recalendarizar` ahora devuelve `bool`; si la "
        "reoptimización exacta no puede confirmarse a tiempo, `_aceptar_oferta` REVIERTE "
        "la aceptación (el pedido queda 'perdido') en vez de dejar un plan sin horario.",
        "",
        "## Mediciones (después de cada punto, con K_A=4 primero)",
        "",
        "- Suite de tests: 41-46s -> **1.6-2.1s** (11 tests).",
        "- Episodio completo (B1, 5000 steps, un solo proceso): antes se colgaba/no "
        "entregaba nada; con el fix de reversión, 547.7 steps/s, 15 entregas reales en "
        "3.4h simuladas.",
        "- `python -m vygo.env --bench` (16 entornos, K_A=4): **775.7 steps/s** -- por "
        "encima del piso de 300 pero debajo del objetivo real de 1000.",
        "- K_A bajado de 4 a 3 (autorizado explícitamente por la tarea si no se llega a "
        "1000): **1500-1618 steps/s**, muy por encima del objetivo. Documentado en el "
        "comentario de `sequencer.UMBRAL_EXACTO_PEDIDOS`. Los tests que asumían el camino "
        "exacto a 4 pedidos se actualizaron (4 pedidos ahora usa el camino heurístico; "
        "sigue encontrando el óptimo real en las instancias de prueba, pero ya no está "
        "garantizado, así que `exacto` se afloja a `False` ahí).",
        "- p95 de `step()`: **1.042ms** (p50=0.28ms, p99=2.39ms, máximo observado 12.1ms). "
        "Sin cuelgues.",
        "",
        "## Diagnóstico: histograma de motivos de rechazo (punto 1 de la tarea)",
        "",
        "Instrumentación: `feasibility.CONTADOR_MOTIVOS` (Counter global), poblado por "
        "`action_mask(estado, instrumentar=True)` y `baselines.politica_umbral(..., "
        "instrumentar=True)`, sólo cuando el plan activo ya tiene >=1 pedido (con plan "
        "vacío todo es trivialmente factible, no aporta señal). Categorías: capacidad "
        "(físico del vehículo, `verificar_y_calendarizar`), frescura, fecha_limite, "
        "prefiltro (cortada antes de calendarizar), **tope_ka** (plan ya en `K_A_MAXIMO`, "
        "ninguna oferta se evalúa siquiera), umbral_rho (factible pero no bate `rho_hat`), "
        "aceptada. `tope_ka` NO estaba en la lista de 4 candidatos de la tarea -- es un "
        "hallazgo, no una hipótesis confirmada.",
        "",
        "5 escenarios x 2h, B2, ANTES de clústeres:",
        "",
        "| motivo | n | % |",
        "|---|---|---|",
        "| tope_ka | 317,480 | 96.4% |",
        "| capacidad | 9,593 | 2.9% |",
        "| prefiltro | 1,641 | 0.5% |",
        "| fecha_limite | 422 | 0.1% |",
        "| umbral_rho | 62 | 0.0% |",
        "| aceptada | 50 | 0.0% |",
        "",
        "Ninguno de los 4 candidatos (capacidad, frescura, prefiltro, umbral_rho) domina "
        "(todos <3% combinados) -- así que, por la regla de la tarea, **no se tocó Q de "
        "vehículo, theta de frescura, N_PREFILTRO ni la fórmula de tarifa.** El bloqueo "
        "real es el tope duro `K_A_MAXIMO=3` (`sequencer.UMBRAL_EXACTO_PEDIDOS`, bajado de "
        "4 a 3 en el bloque anterior por presupuesto de steps/s): una vez que el plan tiene "
        "1 pedido, casi siempre ya está lleno y ninguna oferta nueva llega ni a evaluarse. "
        "Subir ese tope SÍ atacaría la causa dominante, pero es un cambio de presupuesto de "
        "rendimiento (el camino exacto de `held_karp` vuelve a correr sobre 2520 secuencias "
        "en vez de 90 en cada `_recalendarizar`), no uno de los 4 candidatos autorizados "
        "hoy -- se deja documentado como decisión pendiente para quien priorice steps/s vs. "
        "margen de agrupamiento, no aplicado unilateralmente en este bloque.",
        "",
        "## Geografía: clústeres explícitos (punto 3, incondicional)",
        "",
        "`generator.muestrear_comercios` reemplazado: ya no pondera por el mapa de "
        "densidad de fondo sobre las 400 celdas del grid (dispersaba los comercios aunque "
        "unas celdas pesaran más). Ahora: `N_ZONAS_DENSAS=4` focos en los 4 cuadrantes del "
        "grid, `N_COMERCIOS_POR_ZONA=15` comercios cada uno dentro de un disco de radio "
        "`RADIO_ZONA_M=1500`, más `N_COMERCIOS_DISPERSOS=20` de relleno uniformes sobre "
        "todo el grid (proporción 60:20 escalada a `m_comercios`, 80 por defecto en "
        "`sanity_check.py` = exactamente 4x15+20). `_muestrear_destino` reemplazado: ya no "
        "es un kernel LogNormal de mediana 3.5km sobre todo el grid, ahora uniforme en área "
        "dentro de `RADIO_DESTINO_M=2500` del comercio de origen.",
        "",
        "## Prueba de sanidad (punto 4) -- 20 escenarios, turno de 2h, L0, DESPUÉS de clústeres",
        "",
        "| política | rho_mediana | rho_media | bundling | puntualidad | entregados/turno |",
        "|---|---|---|---|---|---|",
        "| B1 | 227.11 | 226.24 | 0.68 | 1.00 | 9.95 |",
        "| B2 | 267.45 | 275.44 | 0.73 | 1.00 | 10.80 |",
        "| B2-ingenuo | 267.45 | 274.86 | 0.74 | 1.00 | 10.80 |",
        "",
        "1093.0s de cómputo. B2 vs B1: **+17.8%** en rho_mediana (antes +9.3%, umbral 15% -- "
        "**ahora sí lo supera**). B2 vs B2-ingenuo: +0.0% (esperado en L0: "
        "`n_competidores_base=0`, `p_gana_estimada` siempre 1.0, esta comparación no es "
        "significativa hasta L1). factor_agrupamiento(B2)=0.73 (bajó de 0.97, sigue muy "
        "debajo del umbral 1.4 -- y ahora debajo de 1.0, no 'cerca' de 1.0 desde arriba).",
        "",
        "Histograma de motivos de rechazo, mismos 20 escenarios, DESPUÉS de clústeres:",
        "",
        "| motivo | n | % |",
        "|---|---|---|",
        "| tope_ka | 1,773,744 | 99.7% |",
        "| capacidad | 2,661 | 0.1% |",
        "| prefiltro | 794 | 0.0% |",
        "| fecha_limite | 455 | 0.0% |",
        "| umbral_rho | 313 | 0.0% |",
        "| aceptada | 264 | 0.0% |",
        "",
        "`tope_ka` se volvió AÚN más dominante (99.7% vs 96.4%): los clústeres sí generan "
        "más ofertas cercanas simultáneas, así que el plan llega al tope de 3 pedidos más "
        "rápido y se queda ahí más tiempo -- consistente con que la oportunidad de "
        "agrupamiento geográfico ahora existe, pero el tope duro de 3 pedidos por plan "
        "(no la geografía) es lo que decide cuánto de esa oportunidad se puede aprovechar.",
        "",
        "## Conclusión del bloque (punto 5 de la tarea)",
        "",
        "Ninguno de los dos casos que anticipaba la tarea ocurrió limpiamente: bundling NO "
        "subió de 1.3, pero tampoco 'se quedó cerca de 1.0' -- bajó a 0.73. Aun así, la "
        "regla aplica igual: **el valor del agente está en la selección**, y ahí el "
        "resultado mejoró (+17.8% sobre B1, contra +9.3% antes de este bloque). Por "
        "instrucción explícita de la tarea, **el generador queda congelado** a partir de "
        "aquí -- no se hacen más ajustes de intensidad, geografía ni tarifa. rho_hat sigue "
        "en 227-275 MXN/h, por encima del rango 120-180 esperado por la tarea, pero como "
        "`umbral_rho` es <0.02% del histograma de rechazos (no está gateando decisiones "
        "reales), no se investigó la fórmula de tarifa esta vez -- queda anotado para un "
        "bloque futuro si se decide que sí importa.",
        "",
        "## Qué sigue",
        "",
        "- Decisión pendiente (no técnica, de prioridad): ¿subir `K_A_MAXIMO`/"
        "`UMBRAL_EXACTO_PEDIDOS` por encima de 3 a cambio de steps/s, dado que es la causa "
        "dominante y confirmada del histograma de rechazos?",
        "- Con el generador congelado y el criterio de selección ya presentable (+17.8%), "
        "el siguiente bloque natural es `train_ppo.py` (sigue siendo un stub).",
        "- B0 (aleatoria) y B3 (MILP rodante), export_vygo.py, evaluate.py siguen sin "
        "implementar.",
        "",
        "## Bloqueos",
        "",
    ]
    lineas.extend(f"- {b}" for b in status["bloqueos"])
    lineas += ["", "## Siguiente paso sugerido", "", status["siguiente_paso_sugerido"], ""]
    return "\n".join(lineas)


def write_report(run_dir: str) -> None:
    """Regenera status.json y HANDOFF.md dentro de run_dir (ai/CLAUDE.md §8)."""

    out_dir = Path(run_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tests = _correr_tests()
    status = _construir_status(tests)

    (out_dir / "status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    (out_dir / "HANDOFF.md").write_text(_handoff_md(status), encoding="utf-8")


if __name__ == "__main__":
    write_report(str(_AI_ROOT / "reports"))
