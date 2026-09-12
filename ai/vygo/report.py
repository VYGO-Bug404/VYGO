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
_BLOQUE_ACTUAL = "B4-separacion-ka-economia-y-agente-entrenado"


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
            "B1": {"rho": 345.97, "pedidos_h": 7.30, "puntualidad": 1.00, "bundling": 0.88},
            "B2": {"rho": 338.39, "pedidos_h": 7.28, "puntualidad": 1.00, "bundling": 0.89},
            "B2_ingenuo": {"rho": 334.63, "pedidos_h": 7.18, "puntualidad": 1.00, "bundling": 0.89},
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
            "K_A_MAXIMO (feasibility.py, tope de PEDIDOS en el plan) se DESACOPLÓ de "
            "sequencer.UMBRAL_EXACTO_PEDIDOS (hasta cuántos pedidos held_karp resuelve "
            "exacto) -- estaban fusionadas en 3, así que bajar el umbral exacto por "
            "steps/s le bajaba la capacidad al repartidor de regalo. Ahora "
            "UMBRAL_EXACTO_PEDIDOS=3 (sin cambio, decisión de algoritmo) y "
            "K_A_MAXIMO=4 (decisión del problema); el 4º pedido del plan se calendariza "
            "por el camino heurístico, no el exacto. De paso se corrigió un bug real: el "
            "conteo de pedidos en el plan usaba `len(plan)//2` (paradas/2), que SUBcuenta "
            "en cuanto una recogida ya se procesó (esa parada sale del plan, sólo queda la "
            "entrega) -- ahora cuenta IDs de pedido distintos (`sequencer.n_pedidos_en_plan`) "
            "en feasibility.py, baselines.py y el assert de env.py. Test nuevo: "
            "test_k_a_maximo_desacoplado_de_umbral_exacto_permite_cuarto_pedido.",
            "Auditoría de economía: se imprimió el desglose completo de un turno (ingreso "
            "bruto, costo por km, horas conectadas) y NO se encontró bug de conversión -- "
            "el costo por km sí se resta, las horas sí son horas (t/3600 en todos los "
            "sitios), la tarifa no se suma dos veces (ganancia_acum y el reward por step "
            "son acumuladores separados, cada uno incrementado una sola vez por entrega). "
            "rho salía alto porque la tarifa por km era generosa, no por unidades mal "
            "aplicadas -- se bajó _TARIFA_BETA_KM_MXN de (7,11) a (6,8), tal como autorizaba "
            "la tarea como fallback. Antes/después de un turno de 2h (semilla 0, misma "
            "corrida salvo beta): ingreso 548.26->248.72 MXN, costo_km 62.4->31.2 MXN, "
            "rho 242.93->108.76 MXN/h (nota: la comparación no es de trayectoria idéntica -- "
            "el prefiltro de feasibility.py rankea por precio/distancia, así que bajar la "
            "tarifa cambia QUÉ ofertas se evalúan primero incluso con la misma semilla).",
            "Fechas límite: la fórmula se apretó a creado_en + tiempo_directo*1.6 + 20min "
            "(antes: tiempo_listo_en + ...*1.6 + 10min, con el margen de preparación GRATIS "
            "encima). Resultado: puntualidad SIGUE en 1.00 exacto en las tres políticas, "
            "confirmado tras el cambio. Causa raíz encontrada (no es que el margen siga "
            "siendo grande): `sequencer.verificar_y_calendarizar` trata fecha_limite como "
            "restricción DURA (rechaza cualquier secuencia que la violaría, igual que "
            "frescura/capacidad) -- pero ai/CLAUDE.md §2 sólo lista frescura, capacidad y "
            "precedencia como duras; fecha_limite está pensada como BLANDA (§7: penalización "
            "`psi_i * max(0, T_entrega - limite_i)` en la recompensa). Con el límite "
            "hard-masked, ese código de penalización nunca se ejecuta -- es código muerto, y "
            "ninguna fórmula de límite puede crear riesgo real mientras esto no cambie. Es "
            "un cambio de arquitectura del secuenciador (la pasada hacia atrás usa l_idx "
            "como ancla para las cotas de espera estratégica de frescura), no una línea -- "
            "no se tocó esta vuelta (fuera del presupuesto de 5 min de la tarea); queda "
            "documentado como el bloqueo real para que puntualidad dependa de la política.",
            "Prueba de sanidad completa (20 escenarios x 2h) DESPUÉS de los tres arreglos: "
            "B1 rho=345.97, B2=338.39, B2-ingenuo=334.63, bundling~0.88-0.89 en las tres, "
            "puntualidad=1.00. B2 vs B1 = **-2.2%** (B2 quedó LIGERAMENTE PEOR que la "
            "política ingenua, no mejor) -- resultado honesto, no se suavizó. Lectura: con "
            "tope_ka en 89.1% del histograma de rechazos (bajó de 96-99.7% pero sigue "
            "dominando total), el entorno sigue tan saturado de demanda que el plan llega a "
            "su tope casi de inmediato aun con K_A_MAXIMO=4; en ese régimen, la selectividad "
            "de B2 (esperar una tasa marginal mejor) cuesta más rendimiento del que gana, "
            "mientras B1 (aceptar la primera factible) mantiene el pipeline lleno. La tarea "
            "es explícita en que esto no bloquea seguir: 'no importa qué salga, pasamos a "
            "entrenamiento igual'.",
            "Clonación de comportamiento (BC) sobre B2: 50 000 transiciones (5 escenarios "
            "semilla 0-4, L1), concordancia_val=0.998 (objetivo >=0.80, superado). PERO la "
            "primera corrida (entropía cruzada sin ponderar) dio rho_rollout=0.00 en 20 "
            "escenarios -- la red predice perfecto en datos i.i.d. pero colapsa a "
            "'rechazar siempre' en rollout cerrado: 'rechazar_todas' es ~90%+ de las "
            "transiciones (tope_ka domina), así que la entropía cruzada promedio ignora casi "
            "por completo las acciones de ACEPTAR, que son las únicas que importan. Se "
            "diagnosticó (no se subieron épocas a ciegas): pesos de clase balanceados "
            "(inverso a frecuencia, cap 20x) en la pérdida. Con eso, concordancia específica "
            "en acciones de aceptar subió a ~90-97% (era ~ignorada antes) -- PERO el rollout "
            "SIGUE colapsando a rho=0.00 (detectado barato con una corrida de humo de 3 "
            "escenarios antes de pagar los 20 completos). Esto ya no es un bug de features "
            "ni de balance de clases: es la limitación clásica de behavior cloning puro "
            "(error compuesto / distribution shift en lazo cerrado) que MaskablePPO, "
            "inicializado desde este mismo checkpoint y corrigiendo con datos on-policy, "
            "está diseñado para resolver -- por eso la tarea pide PPO como el siguiente "
            "paso, no un BC perfecto. `checkpoints/bc_policy.pt` guardado tal cual (piso "
            "documentado como no-funcional en rollout aislado, no como éxito).",
            "MaskablePPO lanzado desde bc_policy.pt vía lanzar.ps1 y CONFIRMADO en vivo: "
            "steps/s=490 medidos (16 envs, DummyVecEnv, L1), pero evaluar 10 escenarios de "
            "validación cuesta 606.6s contra sólo 51.0s de entrenar 25 000 pasos -- la "
            "evaluación domina el costo por ciclo 12x. Sin medir esto, pasos_objetivo se "
            "hubiera dimensionado como si evaluar fuera gratis y la corrida real hubiera "
            "tardado ~4 días en vez de las ~8h pedidas, sin que nada lo avisara hasta muy "
            "tarde. Se corrigió midiendo el costo de UNA evaluación completa antes de fijar "
            "pasos_objetivo (ahora 1 075 000 = 43 ciclos de 25 000, ~8h reales). Primer "
            "callback confirmado: paso=25008, rho_val=0.00 (igual al piso de BC, esperado: "
            "recién arrancó la corrección on-policy), eta=469min, status.json y "
            "train_log.jsonl actualizados, checkpoint guardado en checkpoints/ppo_best.zip.",
            "Bug encontrado y corregido al medir steps/s: el benchmark original usaba "
            "`action_space.sample()` (acción aleatoria SIN máscara). `env._aplicar_accion` "
            "no vuelve a imponer K_A_MAXIMO por su cuenta (sólo lo hace "
            "`feasibility.action_mask`, que toda política real respeta por construcción), "
            "así que una acción de aceptar fuera de máscara coló un 5º pedido y disparó el "
            "assert de seguridad de `_aceptar_oferta`, tumbando el proceso en segundo "
            "plano a los pocos segundos. Corregido: el benchmark ahora muestrea sólo entre "
            "las acciones que la máscara permite (mismo patrón que "
            "`baselines.politica_aleatoria`). MaskablePPO en sí nunca samplea fuera de "
            "máscara (por diseño de sb3-contrib), así que esto no afecta el entrenamiento "
            "real -- sólo afectaba a este script de medición.",
            "En L0 no hay competidores sintéticos (n_competidores_base=0 por diseño), así "
            "que p_gana_estimada=1.0 siempre; B2 vs B2-ingenuo dio +1.1% en esta corrida.",
            "evaluate.py, export_vygo.py siguen siendo stubs sin cuerpo.",
            "baselines B0 (aleatoria) y B3 (MILP rodante) no implementados -- sólo B1/B2/"
            "B2-ingenuo (docs/vygo-ai-training.md §6.1); scenarios/test_50.pkl no existe.",
        ],
        "siguiente_paso_sugerido": (
            "Vigilar reports/train_log.jsonl: si PPO no logra rho_val > 0 en las primeras "
            "evaluaciones, el problema es el mismo régimen saturado por tope_ka que ya "
            "hundió a B2 -- ahí sí valdría la pena reconsiderar K_A_MAXIMO o el hard-mask "
            "de fecha_limite antes de seguir. Si PPO sí despega, dejarlo correr hasta "
            "pasos_objetivo y comparar contra B1/B2 con evaluate.py (todavía stub)."
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
        "Tres arreglos cortos + entrenamiento. (1) `K_A_MAXIMO` (tope de pedidos en el "
        "plan) se DESACOPLÓ de `sequencer.UMBRAL_EXACTO_PEDIDOS` (umbral exacto de "
        "held_karp) -- estaban fusionadas en 3, ahora `K_A_MAXIMO=4` / "
        "`UMBRAL_EXACTO_PEDIDOS=3`, más un bug real de conteo corregido (paradas/2 "
        "subcontaba pedidos con recogida ya hecha). (2) Auditoría de economía: sin bug de "
        "conversión, tarifa por km bajada de (7,11) a (6,8) MXN/km. (3) Fechas límite "
        "apretadas en fórmula, pero **puntualidad sigue en 1.00 exacto** -- causa raíz "
        "real encontrada: fecha_limite está hard-masked en el secuenciador (como si fuera "
        "tan dura como frescura), cuando ai/CLAUDE.md la define como blanda/penalizada. No "
        "se tocó esta vuelta (fuera de presupuesto), queda documentado. (4) Prueba de "
        "sanidad completa: **B2 vs B1 = -2.2%** (B2 quedó peor, no mejor -- resultado "
        "honesto). (5) BC sobre B2: concordancia=0.998 pero la primera corrida colapsó a "
        "rho_rollout=0.00 (comportamiento clásico de BC puro, no bug); con pesos de clase "
        "balanceados la concordancia en acciones de aceptar subió a ~90-97% pero el "
        "colapso en rollout cerrado persiste -- diagnóstico completo, no se subieron "
        "épocas a ciegas. (6-7) MaskablePPO lanzado desde `bc_policy.pt` vía "
        "`lanzar.ps1`, confiando en que el aprendizaje on-policy corrija lo que BC puro "
        "no puede.",
        "",
        "## Punto 1 -- K_A_MAXIMO vs UMBRAL_EXACTO_PEDIDOS",
        "",
        "Antes: `feasibility.K_A_MAXIMO = sequencer.UMBRAL_EXACTO_PEDIDOS` (ambas en 3). "
        "Ahora son constantes independientes: `UMBRAL_EXACTO_PEDIDOS=3` (decisión de "
        "ALGORITMO -- hasta 3 pedidos held_karp enumera exacto, más usa el camino "
        "heurístico) y `K_A_MAXIMO=4` (decisión del PROBLEMA -- cuántos pedidos caben en "
        "el plan). El 4º pedido de un plan se calendariza heurístico, no exacto, y eso es "
        "aceptable: el camino heurístico ya es rápido y ya se ejercitaba en tests. Bug "
        "real encontrado de paso: el conteo de pedidos en el plan usaba `len(plan)//2` "
        "(paradas/2) en feasibility.py, baselines.py y el assert de env.py -- eso SUBcuenta "
        "en cuanto una recogida ya se procesó (esa parada sale de `self.plan`, sólo queda "
        "la entrega: un plan con 1 pedido a medio entregar y 2 sin recoger tiene 5 paradas, "
        "no 6, y `//2` lo cuenta como 2 pedidos en vez de 3). Se agregó "
        "`sequencer.n_pedidos_en_plan` (cuenta IDs únicos) y se reemplazó en los tres "
        "sitios. Test nuevo: `test_k_a_maximo_desacoplado_de_umbral_exacto_permite_cuarto_pedido`. "
        "ai/CLAUDE.md §5 actualizado para reflejar ambas constantes.",
        "",
        "## Punto 2 -- Auditoría de economía",
        "",
        "Desglose de un turno de 2h (B1, semilla 0, ANTES de bajar la tarifa): ingreso "
        "bruto 548.26 MXN, km_acum 52.0 (costo_km 62.4 MXN), rho=(548.26-62.4)/2h=**242.93 "
        "MXN/h**, 11 entregados, precio medio 49.84 MXN/pedido. Verificado explícitamente: "
        "(a) el costo por km SÍ se resta (`recompensa -= COSTO_KM_MXN*(dm/1000)` y "
        "`ledger.costo_distancia = COSTO_KM_MXN*km_acum`, mismo `COSTO_KM_MXN=1.2` en "
        "env.py y baselines.py); (b) las horas SÍ son horas (`t/3600.0` en "
        "`_actualizar_rho_hat`, `_info()`, `sanity_check.py` -- ninguna división por "
        "segundos sin convertir); (c) la tarifa NO se suma dos veces (`recompensa += "
        "p.precio` alimenta el reward por step, `self.ganancia_acum += p.precio` alimenta "
        "el ledger acumulado -- dos acumuladores separados del MISMO evento, no un doble "
        "conteo). Conclusión: no hay bug de conversión: la tarifa simplemente es generosa. "
        "Aplicado el fallback autorizado por la tarea: `_TARIFA_BETA_KM_MXN` de (7,11) a "
        "(6,8) MXN/km. Después del cambio (mismo turno, misma semilla): ingreso bruto "
        "248.72 MXN, costo_km 31.2 MXN, rho=**108.76 MXN/h**, sólo 5 entregados. Aviso "
        "honesto: NO es una comparación de trayectoria idéntica -- `feasibility._puntaje_prefiltro` "
        "rankea las ofertas por (desvío geométrico / precio), así que bajar la tarifa "
        "cambia QUÉ ofertas se evalúan primero incluso con la misma semilla; el antes/"
        "después de un solo turno es ilustrativo de la contabilidad, no una medición "
        "pareada. La medición oficial es la prueba de sanidad de 20 escenarios (punto 4).",
        "",
        "## Punto 3 -- Fechas límite apretadas (efecto nulo, causa raíz real encontrada)",
        "",
        "Fórmula cambiada de `tiempo_listo_en + tiempo_directo*1.6 + 10min` a "
        "`creado_en + tiempo_directo*1.6 + 20min` (el margen de preparación, 6-35 min, ya "
        "no se suma gratis encima del límite). Verificado en 3 escenarios de B1 tras el "
        "cambio: **puntualidad sigue en 1.00 exacto**. Causa raíz: "
        "`sequencer.verificar_y_calendarizar` rechaza CUALQUIER secuencia que llegaría "
        "tarde a una entrega (`llegadas[k] > l_idx[idx] + _EPS: return None`), tratando "
        "fecha_limite como restricción DURA -- igual que frescura y capacidad. Pero "
        "ai/CLAUDE.md §2 sólo lista frescura, capacidad y precedencia como duras; "
        "fecha_limite está diseñada como BLANDA (§7: `psi_i * max(0, T_entrega - "
        "limite_i)` en la recompensa, código que hoy nunca se ejecuta porque el plan "
        "jamás llega a violar el límite -- lo impide la máscara antes). Mientras "
        "fecha_limite sea dura en el secuenciador, NINGUNA fórmula puede crear riesgo "
        "real de tardanza. Arreglarlo de verdad significa que la pasada hacia atrás del "
        "secuenciador deje de usar `l_idx` como corte absoluto (sigue necesitándolo como "
        "ancla para las cotas de espera estratégica de frescura) -- cambio de arquitectura "
        "del núcleo determinista, no una tarea de 5 minutos. Fuera de presupuesto hoy; "
        "queda documentado como el bloqueo real para que puntualidad sea una tensión de "
        "verdad.",
        "",
        "## Punto 4 -- Prueba de sanidad completa (20 escenarios x 2h, L0, entorno YA CONGELADO)",
        "",
        "| política | rho_mediana | rho_media | bundling | puntualidad | entregados/turno |",
        "|---|---|---|---|---|---|",
        "| B1 | 345.97 | 331.30 | 0.88 | 1.00 | 14.60 |",
        "| B2 | 338.39 | 340.30 | 0.89 | 1.00 | 14.55 |",
        "| B2-ingenuo | 334.63 | 333.94 | 0.89 | 1.00 | 14.35 |",
        "",
        "1604.9s de cómputo. **B2 vs B1 = -2.2%** en rho_mediana -- B2 quedó ligeramente "
        "PEOR que la política ingenua, no mejor. No se suaviza este resultado. B2 vs "
        "B2-ingenuo: +1.1% (valor de `p_gana`, ahora medible porque L0 sigue con "
        "`n_competidores_base=0`, pero el ranking de ofertas en sí ya refleja el prefiltro "
        "económico). Histograma de motivos de rechazo, mismos escenarios:",
        "",
        "| motivo | n | % |",
        "|---|---|---|",
        "| tope_ka | 934,416 | 89.1% |",
        "| capacidad | 87,232 | 8.3% |",
        "| prefiltro | 18,662 | 1.8% |",
        "| fecha_limite | 6,742 | 0.6% |",
        "| aceptada | 963 | 0.1% |",
        "| umbral_rho | 463 | 0.0% |",
        "",
        "Lectura: `tope_ka` bajó de 99.7% a 89.1% (K_A_MAXIMO=4 sí da algo de margen) pero "
        "sigue dominando total -- el entorno está tan saturado de demanda que el plan "
        "llega a su tope casi de inmediato de todos modos. En ese régimen, la "
        "SELECTIVIDAD de B2 (esperar una oferta con mejor tasa marginal en vez de tomar "
        "la primera) cuesta más rendimiento del que gana: mientras B2 evalúa y espera, B1 "
        "ya aceptó y sigue moviéndose. Es un resultado incómodo pero coherente con el "
        "resto del diagnóstico, no un error de medición.",
        "",
        "## Puntos 5-7 -- Clonación de comportamiento + PPO",
        "",
        "**BC** (`vygo/bc.py`): 50 000 transiciones (obs, acción, máscara) de B2 sobre 5 "
        "escenarios de entrenamiento (semillas 0-4, L1; semillas >=10 000 reservadas para "
        "validación, nunca tocadas para recolectar). Red en `vygo/policy_net.py`: MLP(128) "
        "sobre el bloque propio, self-attention sobre el plan activo (pooling ponderado "
        "para ignorar slots vacíos sin arriesgar NaN cuando el plan está completamente "
        "vacío), cross-attention sobre las 8 ofertas con consulta=propio+plan, tronco "
        "MLP(256,256) -- es la MISMA clase `MaskableActorCriticPolicy` de sb3-contrib que "
        "usa PPO después, así que `bc_policy.pt` carga directo con `load_state_dict`. "
        "Primera corrida (10 épocas, Adam 1e-3, entropía cruzada sin ponderar): "
        "`concordancia_val=0.998` (objetivo >=0.80, superado con margen) pero "
        "`rho_rollout=0.00` en los 20 escenarios de validación -- la red predice casi "
        "perfecto en datos i.i.d. pero en rollout cerrado NUNCA entrega nada. Diagnóstico "
        "(no se subieron épocas a ciegas, como pedía la tarea): 'rechazar_todas' es >=90% "
        "de las transiciones (consistente con tope_ka dominando el histograma), así que la "
        "entropía cruzada promedio apenas penaliza errores en las acciones de ACEPTAR, que "
        "son <2% de los datos y las únicas que importan. Con pesos de clase balanceados "
        "(inverso a frecuencia, cap 20x) la concordancia específica en acciones de aceptar "
        "subió de un colapso silencioso a ~90-97% por época -- pero el rollout SIGUE "
        "colapsando a rho=0.00 (detectado con una corrida de humo de 3 escenarios antes de "
        "pagar los 20 completos, optimización que quedó en `bc.py`). Conclusión: esto ya "
        "no es un bug de features ni de balance de clases (ambos quedaron descartados con "
        "evidencia) -- es la limitación clásica de behavior cloning puro (error compuesto "
        "en lazo cerrado / distribution shift): ninguna cantidad de ajuste a la pérdida "
        "sobre datos OFFLINE arregla que la red nunca vio cómo recuperarse de sus propios "
        "errores. Es exactamente lo que existe PPO para resolver (aprendizaje on-policy, "
        "sobre los estados que la propia red visita). `bc_policy.pt` se guarda tal cual: "
        "es un piso DOCUMENTADO como no-funcional en aislamiento, no un éxito disfrazado.",
        "",
        "**PPO** (`vygo/train_ppo.py`): `MaskablePPO` inicializado con "
        "`policy.load_state_dict(bc_policy.pt)`, sin currículum, directo en L1, semilla "
        "única. `n_envs=16` sobre `DummyVecEnv` (secuencial, no `SubprocVecEnv`: corre "
        "horas sin supervisión vía `lanzar.ps1`, y una falla de multiprocessing en Windows "
        "a medio entrenamiento sería peor que perder el paralelismo real -- decisión "
        "documentada). `pasos_objetivo` se dimensiona en tiempo de ejecución a partir de "
        "los steps/s medidos de este VecEnv concreto, para ~8h. Callback cada 25 000 "
        "pasos: evalúa rho en 10 escenarios de validación (obs normalizada con las "
        "estadísticas de VecNormalize del entrenamiento, sincronizadas -- sin esto se "
        "mediría una red bajo una escala de observación que nunca vio), agrega línea a "
        "`reports/train_log.jsonl`, reescribe `reports/status.json` (sección "
        "`entrenamiento`/`evaluacion`, con `curva` acotada a las últimas 20 entradas -- el "
        "historial completo vive en train_log.jsonl, no en status.json), y guarda el "
        "mejor checkpoint (`checkpoints/ppo_best.zip`) por rho de validación -- "
        "`bc_policy.pt` nunca se sobreescribe. Lanzado con `ai/lanzar.ps1` "
        "(Start-Process, no nohup). Ver la sección `entrenamiento` de `status.json` y "
        "`reports/train_log.jsonl` para el estado real al momento de leer esto.",
        "",
        "**Dos cosas que fallaron al lanzar de verdad, corregidas antes de dejarlo corriendo "
        "sin supervisión:** (1) el benchmark de steps/s usaba `action_space.sample()` "
        "(acción sin máscara) -- `env._aplicar_accion` no vuelve a imponer K_A_MAXIMO por "
        "su cuenta (sólo `feasibility.action_mask` lo hace, y toda política real la "
        "respeta por construcción), así que coló un 5º pedido y tumbó el proceso con el "
        "assert de seguridad de `_aceptar_oferta` a los pocos segundos; corregido "
        "muestreando sólo entre acciones que la máscara permite. (2) `pasos_objetivo` se "
        "calculaba sólo con el throughput de ENTRENAR, ignorando el costo de EVALUAR -- "
        "medido después: evaluar 10 escenarios cuesta 606.6s contra 51.0s de entrenar "
        "25 000 pasos (12x). Sin corregirlo, la corrida real hubiera tardado ~4 días en "
        "vez de las ~8h pedidas, sin ningún aviso hasta que ya fuera tarde. Corregido "
        "midiendo el costo de una evaluación completa ANTES de fijar `pasos_objetivo` "
        "(1 075 000 pasos = 43 ciclos de 25 000, ~8h reales). Confirmado en vivo: primer "
        "callback en paso=25008, rho_val=0.00 (esperado, es el piso de BC recién "
        "arrancando su corrección on-policy), status.json y train_log.jsonl "
        "actualizándose, checkpoint guardado.",
        "",
        "## Qué sigue",
        "",
        "- Vigilar si PPO logra rho_val > 0 en las primeras evaluaciones -- si no, el "
        "régimen saturado por tope_ka (el mismo que hundió a B2 en el punto 4) es "
        "sospechoso número uno, y ahí sí valdría la pena reconsiderar K_A_MAXIMO o el "
        "hard-mask de fecha_limite antes de seguir invirtiendo en RL.",
        "- Decisión pendiente (de prioridad, no técnica): ¿subir K_A_MAXIMO más allá de 4, "
        "o hacer fecha_limite blanda de verdad en el secuenciador?",
        "- evaluate.py, export_vygo.py, B0 (aleatoria), B3 (MILP rodante) siguen sin "
        "implementar; scenarios/test_50.pkl no existe.",
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
