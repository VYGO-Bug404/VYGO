"""Clonación de comportamiento (BC) sobre B2 -- el piso garantizado antes de PPO (tarea
"agente entrenado"). Genera transiciones (obs, accion, mascara) ejecutando la política de
umbral B2 sobre escenarios de ENTRENAMIENTO (semillas < `SEMILLA_VAL_INICIO`; 10 000+ quedan
reservadas para validación/test y nunca se usan aquí para recolectar), entrena la red de
`policy_net.py` por entropía cruzada con la máscara aplicada, guarda
`checkpoints/bc_policy.pt` y `reports/bc_curva.json`.

Uso: python -m vygo.bc
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import gymnasium as gym
import numpy as np
import torch

from vygo.baselines import RhoHatMovil, politica_umbral
from vygo.env import VygoEnv
from vygo.features import DIM_TOTAL
from vygo.policy_net import crear_policy

_AI_ROOT = Path(__file__).resolve().parent.parent

N_TRANSICIONES = 50_000
SEMILLA_VAL_INICIO = 10_000  # ai/CLAUDE.md §2.7: semillas de test/val separadas de train
M_COMERCIOS = 80  # 4 zonas x 15 + 20 dispersos (generator.muestrear_comercios), congelado
# Turnos de 2h, no las 6h por defecto: mismo criterio que sanity_check.py -- el
# agrupamiento/las decisiones que importan ya se manifiestan en esa ventana y recolectar/
# evaluar corre ~3x más rápido, crítico con el presupuesto de tiempo de este bloque.
DURACION_TURNO_S = 2 * 3600.0
MAX_PASOS_POR_ESCENARIO = 20_000
N_EPOCAS = 10
LR = 1e-3
BATCH = 256
SPLIT_VAL = 0.2
N_ACCIONES = 10  # K_F + 2
K_F_ACCIONES = 8  # índices 0..7 = aceptar oferta; 8 = rechazar_todas; 9 = reposicionarse


def _recolectar(n_transiciones: int, semilla_inicio: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Rollouts de B2 (con p_gana) en L1 -- el mismo nivel de fidelidad en el que corre PPO
    después (punto 6 de la tarea), para que la política clonada arranque en la distribución
    de estados correcta."""

    obs_buf = np.zeros((n_transiciones, DIM_TOTAL), dtype=np.float32)
    acc_buf = np.zeros(n_transiciones, dtype=np.int64)
    mask_buf = np.zeros((n_transiciones, N_ACCIONES), dtype=bool)

    n = 0
    seed = semilla_inicio
    t0 = time.perf_counter()
    while n < n_transiciones:
        assert seed < SEMILLA_VAL_INICIO, "agotadas las semillas de entrenamiento sin llegar a N_TRANSICIONES"
        env = VygoEnv(nivel="L1", m_comercios=M_COMERCIOS, duracion_turno_s=DURACION_TURNO_S)
        obs, info = env.reset(seed=seed)
        rho_movil = RhoHatMovil()
        while n < n_transiciones:
            estado = env._estado_ruta()
            mask = info["action_mask"]
            accion = politica_umbral(estado, rho_movil.valor, con_p_gana=True)

            obs_buf[n] = obs
            acc_buf[n] = accion
            mask_buf[n] = mask
            n += 1

            obs, r, term, trunc, info = env.step(accion)
            rho_movil.actualizar(env.t, r)
            if term or trunc:
                break
        seed += 1
    dt = time.perf_counter() - t0
    print(f"recolectadas {n} transiciones de {seed - semilla_inicio} escenarios en {dt:.1f}s")
    return obs_buf, acc_buf, mask_buf


def _rho_de_politica(policy, n_escenarios: int, semilla_inicio: int) -> float:
    """rho_mediana de la red (acción = moda de la distribución enmascarada, determinista)
    sobre `n_escenarios` de VALIDACIÓN (semillas >= SEMILLA_VAL_INICIO)."""

    rhos = []
    for i in range(n_escenarios):
        seed = semilla_inicio + i
        assert seed >= SEMILLA_VAL_INICIO
        env = VygoEnv(nivel="L1", m_comercios=M_COMERCIOS, duracion_turno_s=DURACION_TURNO_S)
        obs, info = env.reset(seed=seed)
        for _ in range(MAX_PASOS_POR_ESCENARIO):
            mask = info["action_mask"][None, :]
            with torch.no_grad():
                obs_t = torch.as_tensor(obs, dtype=torch.float32).unsqueeze(0)
                accion = int(policy.get_distribution(obs_t, action_masks=mask).mode().item())
            obs, _r, term, trunc, info = env.step(accion)
            if term or trunc:
                break
        horas = max(env.t / 3600.0, 1e-9)
        rhos.append((env.ganancia_acum - 1.2 * env.km_acum) / horas)
    return float(np.median(rhos))


def _pesos_por_clase(acciones: np.ndarray) -> torch.Tensor:
    """Peso balanceado inverso a la frecuencia (n_total / (N_ACCIONES * conteo_clase)),
    capado a 20x -- SIN esto, la entropía cruzada promedio queda dominada por
    "rechazar_todas" (~90%+ de las transiciones, ver ai/reports/HANDOFF.md): la red logra
    concordancia >99% ignorando casi por completo las clases de ACEPTAR (~1% de los datos),
    que son justo las únicas accionables. Sin peso, esto pasó de largo un rho_rollout=0.00
    con concordancia_val=0.999 -- exactamente el bug que la tarea pedía diagnosticar en vez
    de subir épocas a ciegas."""

    conteo = np.bincount(acciones, minlength=N_ACCIONES).astype(np.float64)
    conteo[conteo == 0] = np.inf  # clase ausente en los datos: peso 0, nunca aparece de todos modos
    pesos = len(acciones) / (N_ACCIONES * conteo)
    pesos = np.clip(pesos, 0.0, 20.0)
    return torch.as_tensor(pesos, dtype=torch.float32)


def entrenar() -> dict:
    obs, acciones, mascaras = _recolectar(N_TRANSICIONES)

    rng = np.random.default_rng(0)
    idx = rng.permutation(len(obs))
    n_val = int(len(obs) * SPLIT_VAL)
    idx_val, idx_train = idx[:n_val], idx[n_val:]

    pesos_clase = _pesos_por_clase(acciones[idx_train])
    print("distribución de acciones (train):", np.bincount(acciones[idx_train], minlength=N_ACCIONES))
    print("pesos de clase (balanceados, cap 20x):", pesos_clase.numpy())

    obs_space = gym.spaces.Box(low=-np.inf, high=np.inf, shape=(DIM_TOTAL,), dtype=np.float32)
    act_space = gym.spaces.Discrete(N_ACCIONES)
    policy = crear_policy(obs_space, act_space, lambda _progreso: LR)
    optimizador = torch.optim.Adam(policy.parameters(), lr=LR)

    obs_t = torch.as_tensor(obs)
    acc_t = torch.as_tensor(acciones)

    curva = []
    for epoca in range(N_EPOCAS):
        perm = rng.permutation(idx_train)
        perdida_acum, n_batches = 0.0, 0
        for i in range(0, len(perm), BATCH):
            lote = perm[i:i + BATCH]
            optimizador.zero_grad()
            _valores, log_prob, _entropia = policy.evaluate_actions(
                obs_t[lote], acc_t[lote], action_masks=mascaras[lote],
            )
            peso_lote = pesos_clase[acc_t[lote]]
            perdida = -(log_prob * peso_lote).sum() / peso_lote.sum()
            perdida.backward()
            optimizador.step()
            perdida_acum += float(perdida.detach())
            n_batches += 1

        with torch.no_grad():
            _valores, log_prob_val, _entropia = policy.evaluate_actions(
                obs_t[idx_val], acc_t[idx_val], action_masks=mascaras[idx_val],
            )
            perdida_val = float(-log_prob_val.mean())
            dist_val = policy.get_distribution(obs_t[idx_val], action_masks=mascaras[idx_val])
            pred_val = dist_val.mode()
            concordancia_val = float((pred_val == acc_t[idx_val]).float().mean())
            acc_t_val = acc_t[idx_val]
            es_aceptar = acc_t_val < K_F_ACCIONES
            concordancia_aceptar = (
                float((pred_val[es_aceptar] == acc_t_val[es_aceptar]).float().mean())
                if es_aceptar.any() else None
            )

        curva.append({
            "epoca": epoca + 1,
            "perdida_train": perdida_acum / max(n_batches, 1),
            "perdida_val": perdida_val,
            "concordancia_val": concordancia_val,
            "concordancia_aceptar_val": concordancia_aceptar,
        })
        print(
            f"epoca {epoca + 1}/{N_EPOCAS}  perdida_train={curva[-1]['perdida_train']:.4f}  "
            f"perdida_val={perdida_val:.4f}  concordancia_val={concordancia_val:.3f}  "
            f"concordancia_aceptar_val={concordancia_aceptar}",
        )

    checkpoints_dir = _AI_ROOT / "checkpoints"
    checkpoints_dir.mkdir(exist_ok=True)
    torch.save(policy.state_dict(), checkpoints_dir / "bc_policy.pt")

    concordancia_final = curva[-1]["concordancia_val"]
    rho_red = None
    if concordancia_final >= 0.70:
        # Concordancia alta NO basta (ver docstring de _pesos_por_clase): antes de pagar
        # los 20 escenarios completos, una corrida CORTA de humo detecta un colapso a
        # "rechazar siempre" mucho más barato -- eso fue justo lo que pasó sin el peso por
        # clase (concordancia_val=0.999, rho_rollout=0.00 en los 20 escenarios completos).
        rho_humo = _rho_de_politica(policy, n_escenarios=3, semilla_inicio=SEMILLA_VAL_INICIO)
        print(f"rho de humo (3 escenarios): {rho_humo:.2f} MXN/h")
        if rho_humo > 0:
            rho_red = _rho_de_politica(policy, n_escenarios=20, semilla_inicio=SEMILLA_VAL_INICIO)
            print(f"rho de la red BC sobre 20 escenarios de validación: {rho_red:.2f} MXN/h")
        else:
            print(
                "rho de humo <= 0: la red colapsó a no-entregar-nada pese a concordancia alta "
                "-- no se gasta el eval completo de 20 escenarios, ver reports/HANDOFF.md",
            )

    resultado = {
        "n_transiciones": int(len(obs)),
        "n_train": int(len(idx_train)),
        "n_val": int(len(idx_val)),
        "curva": curva,
        "concordancia_final": concordancia_final,
        "concordancia_aceptar_final": curva[-1]["concordancia_aceptar_val"],
        "rho_red_20_escenarios": rho_red,
    }
    (_AI_ROOT / "reports" / "bc_curva.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return resultado


if __name__ == "__main__":
    entrenar()
