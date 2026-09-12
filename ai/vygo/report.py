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
_BLOQUE_ACTUAL = "B0-andamiaje"


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
            "violaciones_frescura": None,
            "violaciones_capacidad": None,
            "fifo_ok": None,
            "contabilidad_ok": None,
            "holdout_intacto": None,
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
            "vygo/env.py no está implementado: no existe entorno de simulación L0/L1.",
            "vygo/geo.py, weather.py, generator.py son stubs sin cuerpo: no hay generador "
            "de escenarios.",
            "sequencer.held_karp, insertion.eval_insertion y feasibility.action_mask tienen "
            "firma pero levantan NotImplementedError.",
            "baselines B0-B3 no implementados; scenarios/test_50.pkl todavía no existe.",
        ],
        "siguiente_paso_sugerido": (
            "Implementar vygo/geo.py (rejilla L0) y vygo/generator.py (llegada de pedidos) "
            "para tener un VygoEnv mínimo y poder correr python run.py bench."
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
        "- Andamiaje de `ai/`: estructura de carpetas (`config/`, `vygo/`, `tests/`, "
        "`scenarios/`, `reports/`), `requirements.txt`, `run.py` (punto de entrada "
        "multiplataforma) y `Makefile` como envoltura delgada de `run.py` — ver §10.",
        "- `vygo/schema.py`: enums y dataclasses espejo exacto del esquema VYGO (apps, "
        "pedidos, ofertas_pedido, difusiones_pedido, viaje_pedidos, repartidores, "
        "configuracion) — ver `docs/vygo-ai-training.pdf`.",
        "- `vygo/report.py`: este generador de `reports/status.json` y `reports/HANDOFF.md`, "
        "con diagnóstico automático de antipatrones (§7); cuenta pasaron/fallaron/xfail por "
        "separado y marca `dirty` si el repo tiene cambios sin commitear.",
        "- Firmas públicas congeladas (cuerpo `NotImplementedError`): `held_karp`, "
        "`eval_insertion`, `action_mask`, `VygoEnv`, `politica_umbral` — ver §5.",
        "- `tests/test_invariants.py`: 6 pruebas de invariantes, marcadas `xfail` porque el "
        "entorno todavía no existe.",
        "",
        "## Qué se midió",
        "",
        f"- Tests: {tests['pasaron']} pasaron, {tests['xfail']} xfail (fallo esperado, no "
        f"cuentan como éxito), {tests['fallaron']} fallaron.",
        "- No hay entorno, baselines ni entrenamiento corridos todavía — todos los campos "
        "numéricos de `status.json` están en `null` o `\"no_implementado\"`.",
        "",
        "## Qué falló",
        "",
        "- Nada inesperado. Los 6 tests de invariantes quedan en xfail: importan o llaman "
        "módulos (`vygo.env`, `vygo.sequencer`, `vygo.geo`, ...) que aún no tienen cuerpo.",
        "",
        "## Qué sigue",
        "",
        "- Implementar `vygo/geo.py` (rejilla 20×20 L0) y `vygo/generator.py` (llegada de "
        "pedidos + difusión por rondas) para tener un entorno L0 mínimo.",
        "- Con eso, implementar `vygo/env.py` (VygoEnv) y correr `python run.py bench` "
        "(objetivo ≥5000 steps/s con 16 entornos).",
        "- Implementar `vygo/sequencer.py` (Held–Karp) y `vygo/feasibility.py` (máscara "
        "exacta) antes de tocar baselines o entrenamiento.",
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
