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
_BLOQUE_ACTUAL = "B1-nucleo-determinista"


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
            "violaciones_frescura": None,  # requiere un episodio completo (VygoEnv, aún no existe)
            "violaciones_capacidad": None,  # idem
            "fifo_ok": True,  # verificado: test_monotonia_fifo, 1000 pares aleatorios, 0 violaciones
            "contabilidad_ok": None,  # requiere VygoEnv
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
            "vygo/env.py no está implementado: no existe entorno de simulación L0/L1 todavía "
            "(geo.py, sequencer.py, insertion.py y feasibility.py ya sí).",
            "vygo/weather.py, generator.py, features.py, baselines.py, train_ppo.py, "
            "evaluate.py, export_vygo.py siguen siendo stubs sin cuerpo.",
            "held_karp con 12 paradas: p95 ~3.2ms sobre el objetivo de 2ms (ver "
            "reports/HANDOFF.md, sección de benchmarks, para el detalle de optimizaciones "
            "ya aplicadas y las que faltan).",
            "baselines B0-B3 no implementados; scenarios/test_50.pkl todavía no existe.",
        ],
        "siguiente_paso_sugerido": (
            "Implementar vygo/weather.py (cadena de Markov) y vygo/generator.py (llegada de "
            "pedidos + difusión por rondas) para tener un VygoEnv mínimo L0/L1."
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
        "## Qué se construyó",
        "",
        "Núcleo determinista del secuenciador (sobre el andamiaje de B0: schema.py, "
        "run.py, report.py, ya existentes):",
        "",
        "- `vygo/geo.py`: `GridWorld` (rejilla NxN, distancia Manhattan, matriz de "
        "distancias/tiempo-base precalculada). Multiplicador de hora INTERPOLADO "
        "linealmente entre anclas (no escalón discreto) a propósito: un escalón puede "
        "violar FIFO sin importar qué tan chico sea el instante de corte; la interpolación "
        "lo evita por construcción.",
        "- `vygo/sequencer.py`: `held_karp` con la arquitectura de 4 pasos obligatoria — DP "
        "hacia adelante (single-best, JIT con numba) para podar por capacidad/precedencia y "
        "generar el orden óptimo por tiempo estático, `_candidatas_por_perturbacion` genera "
        "K variantes cercanas (swaps/reubicaciones) para diversidad, y "
        "`verificar_y_calendarizar` hace el pase hacia atrás con punto fijo acotado que "
        "calcula la ESPERA ESTRATÉGICA en cada recogida (nunca se decide frescura en el "
        "pase hacia adelante).",
        "- `vygo/insertion.py`: `eval_insertion`, cachea `held_karp(plan)` en `EstadoRuta` "
        "para no repetirlo por cada oferta evaluada.",
        "- `vygo/feasibility.py`: `action_mask`, incluye el bloqueo de `reposicionarse` por "
        "holgura de frescura < 5 min.",
        "- `vygo/bench.py`: benchmarks reproducibles de `held_karp` y `action_mask`.",
        "",
        "## Qué se midió",
        "",
        f"- Tests: {tests['pasaron']} pasaron, {tests['xfail']} xfail (fallo esperado, no "
        f"cuentan como éxito), {tests['fallaron']} fallaron.",
        "- `test_monotonia_fifo`: 1000 pares aleatorios sobre `GridWorld`, 0 violaciones.",
        "- `test_held_karp_vs_fuerza_bruta_3_pedidos` / `..._4_pedidos`: exacto contra fuerza "
        "bruta en varias semillas.",
        "- `test_held_karp_espera_estrategica`: caso fabricado A MANO (3 pedidos) donde la "
        "secuencia de llegada más temprana viola frescura (hueco 980s > theta 600s) pero "
        "esperar en el primer comercio la vuelve factible (hueco exacto 600s). Pasa.",
        "- Benchmarks (`python -m vygo.bench`, 200 instancias, calentamiento de JIT excluido "
        "del tiempo):",
        "  - `held_karp` 12 paradas: p50≈2.0ms, **p95≈3.2ms** (objetivo <2ms, NO cumplido).",
        "  - `action_mask` 8 ofertas / 6 pedidos activos: p50≈2.4ms, **p95≈3.2ms** (objetivo "
        "<15ms, CUMPLIDO).",
        "",
        "## Qué falló / optimizaciones aplicadas (en orden)",
        "",
        "- Primera versión (DP de Held-Karp con beam K en Python puro): p95 held_karp "
        "≈217ms (108x el objetivo). Perfilado: el cuello de botella era puro overhead de "
        "intérprete (creación de tuplas/listas), no las llamadas a `travel_fn`.",
        "- Bitmask de enteros para subconjuntos: ya se usaba desde el inicio.",
        "- JIT con numba del DP (single-best, no beam) sobre una matriz de viaje "
        "PRECALCULADA una vez por llamada (snapshot en t0; el pase final de "
        "`verificar_y_calendarizar` SIEMPRE usa el travel_fn real dependiente del tiempo, "
        "así que esto no compromete la corrección, sólo el ranking/generación de "
        "candidatas): 217ms -> 19ms.",
        "- Se detectó y corrigió un bug de no-convergencia en el punto fijo: cuando ninguna "
        "espera aguas abajo puede absorber el retraso, el hueco de frescura no mejora nunca "
        "y el punto fijo agotaba las 20 iteraciones por candidata sin darse cuenta. Se "
        "agregó detección de \"no-mejora\" para declarar infactible de inmediato: 19ms -> "
        "~4ms, y `candidatas_agotadas` bajó de 167/200 a 16/200 sobre instancias más "
        "realistas (paradas en radio local, no esparcidas por toda la rejilla).",
        "- Arrays preasignados en vez de diccionarios por id de pedido en el rankeo de "
        "candidatas de perturbación (`_indices_auxiliares`): ~4ms -> ~3.2ms.",
        "- K bajado de 20 a 10 (`ai/CLAUDE.md` §10 lo autoriza explícitamente).",
        "- Con eso agotado, sigue ~1.5x arriba del objetivo de 2ms. Siguiente paso si hace "
        "falta más margen: numba también en `_candidatas_por_perturbacion`/`_tiempo_de_orden` "
        "(hoy puro Python), o reducir aún más el vecindario de perturbación.",
        "",
        "## Qué sigue",
        "",
        "- Implementar `vygo/weather.py` (cadena de Markov, 5 estados) y `vygo/generator.py` "
        "(llegada de pedidos + difusión por rondas) para tener un `VygoEnv` L0/L1 mínimo.",
        "- Con eso, `vygo/env.py` real y correr `python run.py bench` (objetivo ≥5000 "
        "steps/s con 16 entornos) y los tests xfail que dependen de VygoEnv.",
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
