"""Prueba de sanidad B1 vs B2 (ai/CLAUDE.md tarea "entorno L0/L1"): si B2 no supera a B1
por >=15% o el factor de agrupamiento de B2 es < 1.4, el generador no produce oportunidad
de agrupamiento y no hay nada que aprender.

Turnos de 2 HORAS simuladas (no 6h): el agrupamiento ya se manifiesta en esa ventana y el
resultado llega ~3x más rápido. Cada escenario corre hasta su terminación NATURAL (turno
completo), no un número de pasos acotado -- el patch de inserción barata + decisión por
ronda + K_A=3 (ver reports/HANDOFF.md) dejó el entorno lo bastante rápido para esto.

Uso: python -m vygo.sanity_check
"""

from __future__ import annotations

import sys
import time

import numpy as np

from vygo.baselines import RhoHatMovil, politica_primera_factible, politica_umbral
from vygo.env import VygoEnv
from vygo.feasibility import CONTADOR_MOTIVOS, reset_contador_motivos

N_ESCENARIOS = 20
DURACION_TURNO_S = 2 * 3600.0
MAX_PASOS_SEGURIDAD = 20_000  # red de seguridad; un turno de 2h no debería necesitar tantos


def _correr(seed: int, politica: str, instrumentar: bool = False) -> dict:
    # m_comercios=80 = 4 zonas x 15 comercios + 20 dispersos (generator.muestrear_comercios).
    env = VygoEnv(nivel="L0", m_comercios=80, duracion_turno_s=DURACION_TURNO_S)
    obs, info = env.reset(seed=seed)
    rho_movil = RhoHatMovil()

    for _ in range(MAX_PASOS_SEGURIDAD):
        estado = env._estado_ruta()
        if politica == "B1":
            a = politica_primera_factible(estado)
        elif politica == "B2":
            a = politica_umbral(estado, rho_movil.valor, con_p_gana=True, instrumentar=instrumentar)
        elif politica == "B2_ingenuo":
            a = politica_umbral(estado, rho_movil.valor, con_p_gana=False)
        else:
            raise ValueError(politica)

        obs, r, term, trunc, info = env.step(a)
        rho_movil.actualizar(env.t, r)
        if term or trunc:
            break

    horas = max(env.t / 3600.0, 1e-9)
    return {
        "rho": (env.ganancia_acum - 1.2 * env.km_acum) / horas,
        "pedidos_h": info["pedidos_entregados"] / horas,
        "puntualidad": info["puntualidad"],
        "bundling": info["factor_agrupamiento"],
        "entregados": info["pedidos_entregados"],
        "turno_completo": env.t >= DURACION_TURNO_S,
    }


def imprimir_histograma(titulo: str) -> None:
    """Histograma de motivos de rechazo acumulados en CONTADOR_MOTIVOS (sólo ofertas
    evaluadas con el plan activo ya con >=1 pedido, ver feasibility.py). Categorías:
    capacidad | frescura | fecha_limite | prefiltro | tope_ka | umbral_rho | aceptada."""

    total = sum(CONTADOR_MOTIVOS.values())
    print(f"\n{titulo} (total={total})")
    if total == 0:
        print("  (sin datos: ningún caso con plan activo >=1 pedido)")
        return
    for motivo, n in CONTADOR_MOTIVOS.most_common():
        pct = 100.0 * n / total
        print(f"  {motivo:12s} {n:7d}  ({pct:5.1f}%)")


def diagnostico_motivos(n_escenarios: int = 5) -> None:
    """Punto 1 de la tarea 'diagnostico de agrupamiento': corre N escenarios de 2h con B2
    (instrumentado) y muestra la distribución de motivos de rechazo. NO cambiar nada del
    generador/entorno hasta ver esta distribución -- eso decide qué arreglar."""

    reset_contador_motivos()
    t0 = time.perf_counter()
    for seed in range(n_escenarios):
        _correr(seed, "B2", instrumentar=True)
    dt = time.perf_counter() - t0
    print(f"Diagnóstico -- {n_escenarios} escenarios x turno de 2h (L0, B2), {dt:.1f}s de cómputo")
    imprimir_histograma("Histograma de motivos de rechazo -- B2")


def main() -> None:
    reset_contador_motivos()
    resultados = {"B1": [], "B2": [], "B2_ingenuo": []}
    t0 = time.perf_counter()
    for seed in range(N_ESCENARIOS):
        for politica in resultados:
            resultados[politica].append(_correr(seed, politica, instrumentar=(politica == "B2")))
    dt = time.perf_counter() - t0

    resumen = {}
    for politica, corridas in resultados.items():
        rhos = np.array([c["rho"] for c in corridas])
        bundling = np.array([c["bundling"] for c in corridas])
        puntualidad = np.array([c["puntualidad"] for c in corridas])
        entregados = np.array([c["entregados"] for c in corridas])
        incompletos = sum(1 for c in corridas if not c["turno_completo"])
        resumen[politica] = {
            "rho_mediana": float(np.median(rhos)),
            "rho_media": float(np.mean(rhos)),
            "bundling_medio": float(np.mean(bundling)),
            "puntualidad_media": float(np.mean(puntualidad)),
            "entregados_medio": float(np.mean(entregados)),
            "incompletos": incompletos,
        }

    print(f"Prueba de sanidad -- {N_ESCENARIOS} escenarios x turno de 2h (L0), {dt:.1f}s de cómputo\n")
    for politica, r in resumen.items():
        aviso = f"  [{r['incompletos']}/{N_ESCENARIOS} NO llegaron a las 2h]" if r["incompletos"] else ""
        print(
            f"{politica:12s} rho_mediana={r['rho_mediana']:8.2f}  rho_media={r['rho_media']:8.2f}  "
            f"bundling={r['bundling_medio']:.2f}  puntualidad={r['puntualidad_media']:.2f}  "
            f"entregados={r['entregados_medio']:.2f}{aviso}",
        )

    rho_b1 = resumen["B1"]["rho_mediana"]
    rho_b2 = resumen["B2"]["rho_mediana"]
    rho_b2i = resumen["B2_ingenuo"]["rho_mediana"]
    mejora_b2_vs_b1 = ((rho_b2 - rho_b1) / abs(rho_b1) * 100.0) if rho_b1 != 0 else float("inf")
    mejora_b2_vs_ingenuo = ((rho_b2 - rho_b2i) / abs(rho_b2i) * 100.0) if rho_b2i != 0 else float("inf")
    bundling_b2 = resumen["B2"]["bundling_medio"]

    print(f"\nB2 vs B1:         {mejora_b2_vs_b1:+.1f}% en rho_mediana")
    print(f"B2 vs B2-ingenuo: {mejora_b2_vs_ingenuo:+.1f}% en rho_mediana (valor de entender p_gana)")
    print(f"factor_agrupamiento(B2): {bundling_b2:.2f}")

    if mejora_b2_vs_b1 < 15.0 or bundling_b2 < 1.4:
        print(
            "\n*** ALERTA: el generador NO produce oportunidad de agrupamiento suficiente "
            "(mejora<15% o bundling<1.4). Según la tarea: no seguir con entrenamiento hasta "
            "subir intensidad/concentración de comercios o alargar preparación. ***",
        )
    else:
        print("\nOK: B2 supera a B1 por >=15% y bundling(B2)>=1.4.")

    imprimir_histograma("Histograma de motivos de rechazo -- B2 (mismos escenarios de arriba)")


if __name__ == "__main__":
    if "--diagnostico" in sys.argv:
        diagnostico_motivos(5)
    else:
        main()
