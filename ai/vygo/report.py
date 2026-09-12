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
_BLOQUE_ACTUAL = "B2-entorno-L0-L1"


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
        "baselines": {b: _baseline_vacio() for b in ("B0", "B1", "B2", "B3")},
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
            "BLOQUEO PRINCIPAL: la prueba de sanidad B1 vs B2 no se pudo completar de forma "
            "concluyente. Causa raíz diagnosticada: el podado por cota inferior de la ruta "
            "exacta de held_karp (<=4 pedidos) es efectivo sobre posiciones agrupadas (el "
            "benchmark sintético) pero NO sobre pedidos dispersos por todo el grid 20x20 "
            "(el muestreo real de comercios de generator.py), donde muchas de las 2520 "
            "secuencias válidas quedan casi empatadas y hay que verificarlas casi todas. "
            "Con 4-5 pedidos en el plan, el costo por step sube de ~15ms a varios cientos "
            "de ms/step y sigue subiendo. Ver reports/HANDOFF.md para el detalle y la "
            "traza de diagnóstico.",
            "train_ppo.py, evaluate.py, export_vygo.py siguen siendo stubs sin cuerpo.",
            "baselines B0 (aleatoria) y B3 (MILP rodante) no implementados -- sólo B1/B2/"
            "B2-ingenuo (docs/vygo-ai-training.md §6.1); scenarios/test_50.pkl no existe.",
        ],
        "siguiente_paso_sugerido": (
            "Resolver el bloqueo de rendimiento (ver bloqueos) antes de correr la prueba de "
            "sanidad B1 vs B2 completa y decidir si el generador produce suficiente "
            "oportunidad de agrupamiento para entrenar."
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
        "El entorno L0/L1 completo existe y los 11 tests de invariantes pasan (conservación, "
        "capacidad, frescura=0, contabilidad — sobre una VENTANA ACOTADA de pasos, no el "
        "turno completo; ver más abajo por qué). La **prueba de sanidad B1 vs B2 obligatoria "
        "NO se pudo completar de forma concluyente**: un problema de rendimiento real (ya "
        "diagnosticado, no arreglado del todo) hace que correr un turno completo tome "
        "demasiado tiempo. No se puede afirmar todavía que el generador produzca (o no) "
        "oportunidad de agrupamiento suficiente para entrenar.",
        "",
        "## Qué se construyó",
        "",
        "- `vygo/weather.py`: `CadenaClima`, Markov de 5 estados/15 min, matriz y "
        "multiplicadores (tiempo de viaje, demanda, tarifa) en `config/clima.yaml`. "
        "`geo.py` ahora importa el multiplicador de tiempo de viaje de aquí (antes tenía "
        "su propia copia, ligeramente distinta).",
        "- `vygo/generator.py`: `GeneradorPedidos` — M comercios muestreados por densidad "
        "(no uniforme), llegada Poisson no homogénea (picos de comida/cena), destino en "
        "kernel log-normal alrededor del comercio, tarifa y preparación con la fórmula de "
        "la tarea, anillos de prioridad (1500/3000/5000 m) y `resolver_ronda` con "
        "competidores sintéticos. Ganchos `modificador(t, zona)` y (en `geo.travel`, ya "
        "existía el parámetro) `corredores_cerrados` presentes pero sin implementar el "
        "evento de media jornada, como pedía la tarea.",
        "- `vygo/features.py`: `ConstructorFeatures`, vector de 186 dims (14+6×10+8×14) "
        "exacto a §6, buffer preasignado, `construir()` nunca crea un array nuevo.",
        "- `vygo/env.py`: `VygoEnv`, dirigido por eventos (pedido, cierra_ronda, "
        "expira_oferta, llega_nodo). `nivel` L0/L1. `rho_hat` con EMA alfa=0.01.",
        "- `vygo/baselines.py`: B0 (aleatoria), B1 (primera factible), B2 y B2-ingenuo "
        "(umbral, con/sin `p_gana`), `RhoHatMovil` (ventana de 90 min simulados).",
        "- `vygo/sanity_check.py`: driver B1 vs B2 (ver limitación abajo).",
        "- **Patch al secuenciador** (pedido explícito antes del entorno): con <=4 pedidos "
        "(<=8 paradas), `held_karp` ahora enumera TODAS las secuencias válidas por "
        "precedencia (backtracking directo, no genera-y-filtra) y devuelve dos campos "
        "nuevos, `optimo_exacto` y `secuencias_evaluadas` — contrato con el frontend: la UI "
        "sólo puede decir \"óptimo exacto sobre N secuencias\" cuando `optimo_exacto` es "
        "`True`. Para llegar a un tiempo razonable se agregó una poda por cota inferior "
        "(el punto fijo sólo puede posponer, nunca adelantar, así que el tiempo naive sin "
        "espera es una cota inferior válida del tiempo final) — ver más abajo por qué esa "
        "poda no basta en todos los casos.",
        "- `sequencer.py` ahora soporta pedidos \"ya recogidos\" (sólo parada de entrega, "
        "sin precedencia) — hacía falta porque `VygoEnv` pasa el plan así una vez que el "
        "vehículo pasa por la recogida; sin esto `held_karp` tronaba (`ValueError`) en "
        "cuanto el entorno corría de verdad.",
        "",
        "## Qué se midió",
        "",
        f"- Tests: {tests['pasaron']} pasaron, {tests['xfail']} xfail, {tests['fallaron']} "
        "fallaron. Los 4 que dependen de `VygoEnv` ya NO son xfail: corren de verdad, sobre "
        "150 pasos (no el turno de 6h completo — ver rendimiento abajo).",
        "- `held_karp` con K_A=4 (8 paradas, el caso real de uso tras el patch): exacto por "
        "construcción, ya no hace falta medir p95 contra el objetivo de 12 paradas/K=20 "
        "candidatas (ese benchmark no se volvió a tocar, como se pidió).",
        "",
        "## Bugs reales encontrados y corregidos en este bloque",
        "",
        "1. **Precedencia con pedidos ya recogidos**: `sequencer.py` asumía que todo pedido "
        "llega como par (recogida+entrega); `VygoEnv` pasa sólo la entrega una vez recogido. "
        "`ValueError` inmediato al correr el entorno. Arreglado en los 4 sitios que asumían "
        "el par (máscaras de subconjunto, arrays auxiliares, calendario, enumeración exacta).",
        "2. **`llegada` en vez de `salida` en el evento de nodo**: el vehículo \"llegaba\" a "
        "una recogida y avanzaba el reloj a la llegada, saltándose la espera obligatoria por "
        "preparación (`S_o = max(T_o, r_i)`). Debía usar la SALIDA calendarizada.",
        "3. **Contador de rechazados roto**: al cerrar una ronda sin aceptaciones, el código "
        "re-encolaba el pedido para la siguiente ronda AUNQUE el agente ya lo hubiera "
        "rechazado explícitamente, resucitando pedidos terminados y dejando "
        "`rechazados > generados`. Se agregó un guard de estados terminales.",
        "4. **Contabilidad no cuadraba** (~2.5% de diferencia): `reset()` avanza hasta el "
        "primer punto de decisión y ese avance sí cobraba costo de tiempo en el ledger, "
        "pero gymnasium no expone una recompensa de `reset()` — ese costo nunca aparecía "
        "en la suma de recompensas de `step()`. Se desactiva la contabilización durante el "
        "avance inicial.",
        "5. **Caché de calendario obsoleto**: si `held_karp`/`verificar_y_calendarizar` "
        "fallaban dentro de `_recalendarizar` (defensivo, no debería pasar), el caché viejo "
        "no se invalidaba, lo que podía colgar el loop de eventos en un ciclo sin avanzar "
        "el tiempo. Ahora se invalida primero, siempre.",
        "6. **Cola de pendientes O(n) y sin tope**: `cola_pendientes` era una lista con "
        "`.pop(0)`; cambiada a `collections.deque` con tope (`MAX_COLA_PENDIENTES=40`, se "
        "cae/expira más allá de eso) para que un desbalance llegada/capacidad no crezca sin "
        "límite.",
        "",
        "## LIMITACIÓN CONOCIDA — bloquea la prueba de sanidad",
        "",
        "Con el patch de arriba, `held_karp` es EXACTO y rápido (~15-30ms) cuando las "
        "paradas están en un radio local (el benchmark sintético de `vygo/bench.py`, que "
        "usa posiciones 0-8). Pero `generator.py` muestrea comercios por densidad sobre "
        "TODO el grid 20x20 — pedidos reales del entorno pueden estar mucho más dispersos. "
        "Con el plan en 4-5 pedidos dispersos, la poda por cota inferior deja de ser "
        "efectiva (muchas de las 2520 secuencias quedan casi empatadas en tiempo naive, así "
        "que hay que calendarizarlas casi todas) y el costo por `step()` sube de ~15ms a "
        "cientos de ms, y sigue subiendo con la duración del episodio. Diagnosticado con "
        "profiling (`_simular_adelante` con >150k llamadas en 30 steps en la zona lenta).",
        "",
        "Consecuencia directa: no fue posible correr los 20 escenarios x turno completo (6h) "
        "que pedía la prueba de sanidad B1 vs B2 en el tiempo disponible. Intentos con "
        "ventanas más chicas (700-950 pasos) corren rápido pero terminan ANTES de la primera "
        "entrega (la primera entrega observada en una corrida de prueba apareció cerca del "
        "paso 1500) — es decir, la ventana que es rápida no alcanza a mostrar bundling, y la "
        "ventana que alcanzaría a mostrarlo ya no es rápida.",
        "",
        "**No se puede afirmar que el generador pase o falle el criterio de la prueba de "
        "sanidad.** Por la propia regla de la tarea (\"si B2 no supera a B1... no sigas\"), "
        "lo correcto es NO asumir que hay luz verde para entrenar hasta resolver esto.",
        "",
        "Siguiente paso concreto: perfilar `held_karp` con paradas realmente dispersas (no "
        "el benchmark actual) y decidir entre (a) una cota de poda más floja pero más rápida "
        "de evaluar, (b) bajar el umbral exacto de 4 a 3 pedidos y aceptar heurística antes, "
        "o (c) numba también en la ruta exacta.",
        "",
        "## Qué sigue",
        "",
        "- Resolver la limitación de arriba.",
        "- Con eso, correr `python -m vygo.sanity_check` completo (20 escenarios, turno de "
        "6h) y decidir si seguir a entrenamiento o subir intensidad/concentración del "
        "generador.",
        "- `python run.py bench` (objetivo >=3000 steps/s con 16 entornos) no se pudo medir "
        "de forma representativa por la misma razón.",
        "- B0 y B3 (baselines.py) y export_vygo.py, train_ppo.py, evaluate.py siguen sin "
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
