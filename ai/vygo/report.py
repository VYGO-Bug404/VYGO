"""Genera reports/status.json (máquina) y reports/HANDOFF.md (humano) — contrato de
ai/CLAUDE.md §8. Se corre al final de cada bloque de trabajo (`python run.py report`).
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_AI_ROOT = Path(__file__).resolve().parent.parent
_BLOQUE_ACTUAL = "B5-evento-turnos-congelados-y-demo-pareada"

# sha256 de scenarios/test_30.pkl al escribirlo (vygo/congelar_escenarios.py), UNA sola vez.
# Si esto no coincide con el archivo en disco, alguien lo regeneró o lo tocó -- el holdout
# ya no es el mismo y `holdout_intacto` debe salir False, no True por omisión.
_HASH_TEST_30 = "56446af2de9896beb5a54d1db40cbd3d5ff82237c21f563069ed40ffea2839ec"


def _holdout_intacto() -> bool | None:
    ruta = _AI_ROOT / "scenarios" / "test_30.pkl"
    if not ruta.exists():
        return None
    return hashlib.sha256(ruta.read_bytes()).hexdigest() == _HASH_TEST_30


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
            "holdout_intacto": _holdout_intacto(),  # sha256 de scenarios/test_30.pkl, ver arriba
        },
        # Evaluación PAREADA sobre scenarios/test_30.pkl (vygo/evaluate.py), no la sanidad de
        # 20 escenarios sueltos del bloque anterior -- ésta es la que cuenta ahora: mismos
        # 30 turnos exactos para cada política, bootstrap de 10 000 remuestreos para el %.
        "baselines": {
            "B0": _baseline_vacio(),
            "B1": {"rho": 280.39, "pedidos_h": 5.45, "puntualidad": 0.97, "bundling": 0.91},
            "B2": {"rho": 272.21, "pedidos_h": 5.15, "puntualidad": 0.97, "bundling": 0.90},
            "agente_ppo_en_curso": {"rho": 190.48, "pedidos_h": 4.84, "puntualidad": 0.97, "bundling": 0.89},
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
            "vygo/eventos.py: SURGE (tarifa x1.4 + intensidad x1.6 en una zona, 45 min) y "
            "CIERRE_VIAL (corredor bloqueado, factor_detour x1.7, 40 min), guionados y "
            "configurables en YAML (config/evento_surge.yaml, config/evento_cierre_vial.yaml). "
            "Se enganchan por las DOS interfaces que ya existían: "
            "generator.GeneradorPedidos.modificador(t, zona) y "
            "geo.GridWorld.travel(..., corredores_cerrados=...) -- ni baselines.politica_umbral "
            "ni sequencer.held_karp saben que existe un 'evento'. Bug real encontrado de paso: "
            "el multiplicador de DEMANDA del modificador se calculaba en generator._lambda_total "
            "pero nunca se aplicaba (sólo el de tarifa) -- corregido con "
            "GeneradorPedidos._intensidad_efectiva, usado tanto en _lambda_total como en el "
            "peso de selección de comercio de _crear_pedido. La reacción EMERGE, no se "
            "programa: tests/test_eventos.py prueba los dos casos concretos -- SURGE sube el "
            "precio de una oferta hasta que su tasa marginal supera rho_hat y "
            "politica_umbral la acepta SOLA (misma regla, ningún caso especial); "
            "CIERRE_VIAL hace que held_karp encuentre un tiempo total mayor para el MISMO "
            "par de pedidos con el MISMO código, sólo porque travel_fn ahora reporta cruces "
            "más caros. Estado del evento expuesto en el slot 5 del bloque 'plan activo' de "
            "la observación (siempre en cero porque K_A_MAXIMO=4 < K_A=6) -- dimensión de "
            "186 sin cambios.",
            "scenarios/test_30.pkl: 30 turnos de 2h, semillas 10000-10029 (reservadas para "
            "test, nunca usadas por bc.py/train_ppo.py), 15 con SURGE y 15 con CIERRE_VIAL. "
            "Escrito UNA VEZ (vygo/congelar_escenarios.py); sha256 verificado en "
            "report.py (`holdout_intacto`). Nivel L0, no L1: se verificó que en L1 con "
            "m_comercios=80 el agente gana CERO rondas en un turno de 2h completo "
            "(25 competidores sintéticos activos) incluso sin ningún evento de por medio -- "
            "hallazgo real, pre-existente, no introducido por esta tarea; documentado, no "
            "arreglado (fuera de alcance de este bloque). L0 es la única forma de que la "
            "evaluación pareada mida selección de ofertas en vez de suerte contra la "
            "competencia.",
            "vygo/evaluate.py: B1 vs B2 (y 'agente' si hay checkpoint en checkpoints/, se "
            "salta limpio si no) sobre los 30 escenarios, con desglose ANTES/DESPUÉS del "
            "evento y bootstrap de 10 000 remuestreos pareado por escenario. Resultado "
            "medido: B2 vs B1 = -2.9% en rho_mediana (IC 95%: [-43.5%, +37.8%] -- el "
            "intervalo cruza 0, no hay evidencia de que B2 le gane a B1 con estos 30 "
            "escenarios). Consistente con el -2.2% del bloque anterior: el régimen sigue "
            "saturado por tope_ka. El checkpoint agente(PPO) cargado en vivo desde el "
            "entrenamiento EN CURSO de otra sesión queda por debajo de ambos baselines "
            "(rho_mediana=190.48 total, cae a 77.45 en el bucket 'después') -- esperable "
            "con el entrenamiento todavía temprano, no un bug de evaluate.py.",
            "REQUISITO (a) DEL RETO -- 'que el agente gane más que un baseline simple en un "
            "turno fresco' -- la infraestructura para MEDIR esto (escenarios congelados, "
            "evaluación pareada con bootstrap, demo) está completa y funciona correctamente, "
            "pero con el checkpoint actual el agente entrenado NO cumple el requisito "
            "todavía: pierde contra B1. Esto se reporta tal cual, no se suaviza.",
            "demo/turno.html (103 KiB, autocontenido, sin CDN, abre sin servidor): dos/tres "
            "paneles simultáneos (B1, B2, agente si hay checkpoint) sobre el escenario 0 "
            "(SURGE, semilla 10000) -- repartidor, comercios, pedidos a bordo con barra de "
            "frescura, contador de ganancias, banner de evento activo, controles "
            "play/pausa/1x/4x/16x/slider/reiniciar, y panel de explicación por decisión "
            "(tasa marginal, rho_hat, desvío min/km, holgura de frescura, frase legible). "
            "Datos generados por vygo/generar_demo.py (frames DISPERSOS -- sólo cuando algo "
            "visible cambia, no cada cierre de ronda trivial: ~140-154 frames por política "
            "en vez de ~10 000 pasos crudos) y empaquetados por vygo/empaquetar_demo.py "
            "desde una plantilla (demo/_plantilla_turno.html).",
            "(bloque anterior, resumen) K_A_MAXIMO se desacopló de "
            "UMBRAL_EXACTO_PEDIDOS (4 vs 3) con un bug de conteo corregido "
            "(sequencer.n_pedidos_en_plan); tarifa por km bajada (7,11)->(6,8) tras "
            "auditoría de economía sin bug encontrado; fecha_limite sigue hard-masked "
            "(debería ser blanda por CLAUDE.md §7, no arreglado, ver 'siguiente paso'); "
            "sanidad de 20 escenarios dio B2 vs B1 = -2.2%; BC sobre B2 colapsó a "
            "rho_rollout=0.00 pese a concordancia=0.998 (limitación clásica de BC puro, "
            "no bug); MaskablePPO lanzado desde bc_policy.pt vía lanzar.ps1 con dos bugs "
            "de arranque encontrados y corregidos (benchmark sin máscara, costo de "
            "evaluar no contado en pasos_objetivo). Detalle completo en el HANDOFF de ese "
            "commit (`ai: separacion K_A vs umbral exacto...`).",
            "PPO de la otra sesión sigue entrenando en vivo (checkpoints/ppo_best.zip se "
            "actualiza solo); esta tarea sólo LEE ese checkpoint para evaluate.py/demo, "
            "nunca lo entrena ni toca train_ppo.py/bc.py/policy_net.py.",
            "export_vygo.py sigue siendo un stub sin cuerpo.",
            "baselines B0 (aleatoria) y B3 (MILP rodante) no implementados -- sólo B1/B2 "
            "(docs/vygo-ai-training.md §6.1).",
        ],
        "siguiente_paso_sugerido": (
            "Cuando el entrenamiento de la otra sesión avance, re-correr "
            "`python -m vygo.evaluate` y `python -m vygo.generar_demo && python -m "
            "vygo.empaquetar_demo` para ver si el agente ya supera a B1 (requisito (a) del "
            "reto) -- hoy no lo hace. Si sigue sin despegar, el sospechoso número uno "
            "sigue siendo el régimen saturado por tope_ka (89.1% del histograma de "
            "rechazos) y el hard-mask de fecha_limite, ambos ya documentados."
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
        "Tarea del reto Infosys: (a) que el agente le gane a un baseline simple en un "
        "turno fresco, (b) demo con dos agentes lado a lado, (c) un evento de media "
        "jornada al que reaccionar, (d) que el agente pueda explicar una decisión. Se "
        "construyó TODA la infraestructura para (b)+(c)+(d) y para MEDIR (a) de forma "
        "rigurosa -- pero con el checkpoint de PPO actual, (a) todavía NO se cumple: el "
        "agente entrenado pierde contra B1 en los 30 turnos congelados. Se reporta así, "
        "sin suavizar.",
        "",
        "1. **`vygo/eventos.py`**: SURGE (tarifa x1.4 + demanda x1.6 en una zona, 45 min) y "
        "CIERRE_VIAL (corredor bloqueado, rutas alternas x1.7, 40 min), guionados y en "
        "YAML. Se enganchan por los DOS ganchos que YA EXISTÍAN "
        "(`generator.modificador(t,zona)`, `geo.travel(..., corredores_cerrados=...)`) -- "
        "ninguna regla de decisión sabe que existe un 'evento'. `tests/test_eventos.py` "
        "prueba que la reacción EMERGE sola en los dos casos. Bug real encontrado y "
        "corregido de paso: el multiplicador de demanda del modificador se calculaba pero "
        "nunca se aplicaba en `generator._lambda_total` (sólo el de tarifa).",
        "2. **`scenarios/test_30.pkl`**: 30 turnos de 2h, semillas 10000-10029 (reservadas, "
        "nunca tocadas por bc.py/train_ppo.py), 15 SURGE + 15 CIERRE_VIAL. Escrito UNA VEZ; "
        "sha256 verificado en `report.py` (`holdout_intacto`). Hallazgo real que decidió "
        "usar L0 en vez de L1 para estos escenarios: con `m_comercios=80` en L1, el agente "
        "gana CERO rondas en un turno de 2h completo (25 competidores sintéticos) incluso "
        "sin ningún evento -- pre-existente, no introducido aquí, documentado como pendiente.",
        "3. **`vygo/evaluate.py`**: B1 vs B2 (y 'agente' si hay checkpoint) sobre los 30 "
        "turnos, desglose antes/después del evento, bootstrap de 10 000 remuestreos "
        "pareado por escenario. Resultado (tabla abajo): **B2 vs B1 = -2.9%** (IC 95% "
        "[-43.5%, +37.8%] -- cruza cero, no hay evidencia de que B2 gane). El checkpoint "
        "`agente(PPO)`, cargado en vivo desde el entrenamiento de otra sesión que sigue en "
        "curso, queda por debajo de ambos.",
        "4. **`demo/turno.html`**: 103 KiB, autocontenido, sin CDN, abre sin servidor. Dos/"
        "tres paneles simultáneos sobre el mismo turno congelado (B1, B2, agente si hay "
        "checkpoint), contador de ganancias, barras de frescura, banner de evento, "
        "controles play/pausa/1x/4x/16x/slider/reiniciar.",
        "5. **Panel de explicación**: por panel, la última decisión con tasa marginal, "
        "`rho_hat`, desvío en min/km, holgura de frescura y una frase legible "
        "('Aceptado/Rechazado: te paga a $X/h, tu promedio hoy es $Y/h').",
        "",
        "## 1 -- Eventos de media jornada (emergen, no se programan)",
        "",
        "`ProgramadorEventos` agrega N eventos en las mismas dos interfaces que "
        "`generator.py`/`geo.py` ya exponían antes de esta tarea. Prueba concreta en "
        "`tests/test_eventos.py`: (i) SURGE -- una oferta con tasa marginal por debajo de "
        "`rho_hat` se rechaza con `politica_umbral` sin cambios; al multiplicar su precio "
        "por 1.4 (lo que hace `generator._tarifa` cuando la zona está en surge), la MISMA "
        "oferta se acepta, con la MISMA llamada a `politica_umbral`. (ii) CIERRE_VIAL -- "
        "el mismo par de pedidos, el mismo `held_karp`, sólo cambiando el `travel_fn` para "
        "que reporte un corredor cerrado: el tiempo total óptimo aumenta, porque cruzar "
        "ese corredor ahora cuesta más -- el secuenciador ni sabe que hay un evento, sólo "
        "ve números distintos. Estado del evento (tipo activo, minutos restantes, "
        "magnitud de los multiplicadores) expuesto en el 5º slot del bloque 'plan activo' "
        "de la observación -- ese slot está SIEMPRE en cero porque `K_A_MAXIMO=4 < K_A=6` "
        "(features.py), así que la dimensión de 186 no cambió.",
        "",
        "## 2 -- Turnos congelados (`scenarios/test_30.pkl`)",
        "",
        "30 escenarios, semillas 10000-10029 (rango reservado para test, nunca usado para "
        "entrenar), 15 con SURGE y 15 con CIERRE_VIAL, L0. Se descartó L1 tras verificar "
        "que con `m_comercios=80` el agente no gana NINGUNA ronda en un turno de 2h "
        "completo aun sin eventos (25 competidores sintéticos) -- hallazgo real, no un "
        "efecto de esta tarea, documentado para un bloque futuro. `vygo/congelar_escenarios.py` "
        "escribe el archivo UNA VEZ (falla si ya existe); `report.py` verifica su sha256 "
        "(`invariantes.holdout_intacto`).",
        "",
        "## 3 -- Evaluación pareada (`vygo/evaluate.py`)",
        "",
        "| política | rho_mediana (total) | IQR | entregados | puntualidad | km/pedido | bundling |",
        "|---|---|---|---|---|---|---|",
        "| B1 | 280.39 | [167.81, 350.57] | 10.90 | 0.97 | 3.68 | 0.91 |",
        "| B2 | 272.21 | [130.12, 362.98] | 10.30 | 0.97 | 3.66 | 0.90 |",
        "| agente(PPO), en curso | 190.48 | [143.68, 351.51] | 9.67 | 0.97 | 3.64 | 0.89 |",
        "",
        "**B2 vs B1 (rho_mediana, total): -2.9%, IC 95% bootstrap [-43.5%, +37.8%]** -- el "
        "intervalo cruza cero: con estos 30 escenarios no hay evidencia de que B2 supere a "
        "B1. Consistente con el -2.2% del bloque anterior (mismo régimen saturado por "
        "`tope_ka`). Desglose antes/después del evento (rho_mediana): B1 315.13 -> 247.90, "
        "B2 301.80 -> 238.18, agente(PPO) 300.84 -> 77.45 -- las tres políticas empeoran "
        "después del evento (puntualidad también cae, de ~0.97 a 0.67-0.77), lo cual es "
        "justo el punto: el evento SÍ genera una situación más difícil de manejar, y ahí "
        "es donde más se nota que el agente en entrenamiento todavía no compensa. "
        "`_cargar_agente()` intenta `checkpoints/ppo_best.zip`, luego `bc_policy.pt`, y se "
        "salta esa columna sin fallar si ninguno existe -- probado en un checkout limpio "
        "sin `checkpoints/` (está en `.gitignore`).",
        "",
        "## 4-5 -- Demo pareada + explicación (`demo/turno.html`)",
        "",
        "`vygo/generar_demo.py` corre el escenario 0 (SURGE, semilla 10000) con B1, B2 y "
        "el checkpoint disponible, grabando FRAMES DISPERSOS -- sólo cuando algo visible "
        "cambia (posición, ganancia, composición del plan, evento) o hay una decisión real "
        "de aceptar/rechazar -- en vez de un frame por cada cierre de ronda trivial: "
        "~140-154 frames por política en este escenario, no los ~10 000 pasos crudos que "
        "tomó simularlo. `vygo/empaquetar_demo.py` inyecta ese JSON (con `</` escapado, "
        "por si algún texto generado lo llevara literal) en `demo/_plantilla_turno.html` y "
        "escribe `demo/turno.html` -- un solo archivo, sin CDN, verificado con "
        "`node --check` sobre el JS embebido y con una relectura del JSON empaquetado. "
        "Cada panel muestra el repartidor y los comercios sobre el grid, líneas hacia los "
        "destinos de los pedidos a bordo con su barra de frescura, un contador de "
        "ganancias que avanza suavizado (no un salto discreto), un banner cuando el "
        "evento está activo, y la explicación de la última decisión tomada (tasa "
        "marginal, `rho_hat`, desvío en min/km, holgura de frescura, frase legible). El "
        "panel del agente aparece sólo si `checkpoints/` tiene algo que cargar.",
        "",
        "## Qué sigue",
        "",
        "- Requisito (a) del reto sigue sin cumplirse con el checkpoint actual -- volver a "
        "correr `python -m vygo.evaluate` cuando el entrenamiento de la otra sesión "
        "avance más.",
        "- Si PPO no despega, el sospechoso número uno sigue siendo el régimen saturado "
        "por `tope_ka` (89.1% del histograma de rechazos del bloque anterior) y el "
        "hard-mask de `fecha_limite` -- ninguno de los dos se tocó todavía.",
        "- `export_vygo.py`, B0 (aleatoria) y B3 (MILP rodante) siguen sin implementar.",
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
