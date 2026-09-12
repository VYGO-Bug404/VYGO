"""Prueba de sanidad B1 vs B2 (ai/CLAUDE.md tarea "entorno L0/L1"): si B2 no supera a B1
por >=15% o el factor de agrupamiento de B2 es < 1.4, el generador no produce oportunidad
de agrupamiento y no hay nada que aprender.

LÍMITE CONOCIDO: por presupuesto de tiempo, cada escenario corre un número ACOTADO de
steps (no el turno completo de 6h) -- ver reports/HANDOFF.md, sección de rendimiento del
entorno: el costo de action_mask/held_karp crece con el tamaño del plan activo (hasta K_A=6
pedidos), y con eso los steps/s bajan de lo necesario para completar un turno completo en
un tiempo razonable de desarrollo. Los resultados aquí son direccionales (ventana inicial
del turno), no la medición final de rho sobre el turno completo.

Uso: python -m vygo.sanity_check
"""

from __future__ import annotations

import numpy as np

from vygo.baselines import RhoHatMovil, politica_primera_factible, politica_umbral
from vygo.env import VygoEnv

N_ESCENARIOS = 20
PASOS_POR_ESCENARIO = 300


def _correr(seed: int, politica: str) -> dict:
    env = VygoEnv(nivel="L0", m_comercios=50)
    obs, info = env.reset(seed=seed)
    rho_movil = RhoHatMovil()

    for _ in range(PASOS_POR_ESCENARIO):
        estado = env._estado_ruta()
        if politica == "B1":
            a = politica_primera_factible(estado)
        elif politica == "B2":
            a = politica_umbral(estado, rho_movil.valor, con_p_gana=True)
        elif politica == "B2_ingenuo":
            a = politica_umbral(estado, rho_movil.valor, con_p_gana=False)
        else:
            raise ValueError(politica)

        obs, r, term, trunc, info = env.step(a)
        rho_movil.actualizar(env.t, r)
        if term:
            break

    horas = max(env.t / 3600.0, 1e-9)
    return {
        "rho": (env.ganancia_acum - 1.2 * env.km_acum) / horas,
        "pedidos_h": info["pedidos_entregados"] / horas,
        "puntualidad": info["puntualidad"],
        "bundling": info["factor_agrupamiento"],
        "entregados": info["pedidos_entregados"],
    }


def main() -> None:
    resultados = {"B1": [], "B2": [], "B2_ingenuo": []}
    for seed in range(N_ESCENARIOS):
        for politica in resultados:
            resultados[politica].append(_correr(seed, politica))

    resumen = {}
    for politica, corridas in resultados.items():
        rhos = np.array([c["rho"] for c in corridas])
        bundling = np.array([c["bundling"] for c in corridas])
        puntualidad = np.array([c["puntualidad"] for c in corridas])
        entregados = np.array([c["entregados"] for c in corridas])
        resumen[politica] = {
            "rho_mediana": float(np.median(rhos)),
            "rho_media": float(np.mean(rhos)),
            "bundling_medio": float(np.mean(bundling)),
            "puntualidad_media": float(np.mean(puntualidad)),
            "entregados_medio": float(np.mean(entregados)),
        }

    print(f"Prueba de sanidad B1 vs B2 -- {N_ESCENARIOS} escenarios x {PASOS_POR_ESCENARIO} pasos (L0)")
    print("(ventana acotada por presupuesto de tiempo -- ver docstring del módulo)\n")
    for politica, r in resumen.items():
        print(
            f"{politica:12s} rho_mediana={r['rho_mediana']:8.2f}  rho_media={r['rho_media']:8.2f}  "
            f"bundling={r['bundling_medio']:.2f}  puntualidad={r['puntualidad_media']:.2f}  "
            f"entregados={r['entregados_medio']:.2f}",
        )

    rho_b1 = resumen["B1"]["rho_mediana"]
    rho_b2 = resumen["B2"]["rho_mediana"]
    mejora_pct = ((rho_b2 - rho_b1) / abs(rho_b1) * 100.0) if rho_b1 != 0 else float("inf")
    bundling_b2 = resumen["B2"]["bundling_medio"]

    print(f"\nB2 vs B1: {mejora_pct:+.1f}% en rho_mediana. bundling(B2)={bundling_b2:.2f}")

    if mejora_pct < 15.0 or bundling_b2 < 1.4:
        print(
            "\n*** ALERTA: el generador NO produce oportunidad de agrupamiento suficiente "
            "(mejora<15% o bundling<1.4). Según la tarea: no seguir con entrenamiento hasta "
            "subir intensidad/concentración de comercios o alargar preparación. ***",
        )
    else:
        print("\nOK: B2 supera a B1 por >=15% y bundling(B2)>=1.4.")


if __name__ == "__main__":
    main()
