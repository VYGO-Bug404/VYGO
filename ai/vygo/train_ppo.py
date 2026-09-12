"""MaskablePPO sobre VygoEnv, inicializado desde `checkpoints/bc_policy.pt` (tarea "agente
entrenado", punto 6). SIN currículum -- directo en L1, UNA sola semilla: autorizado
explícitamente por esta tarea (el currículum de 5 etapas de docs/vygo-ai-training.md §7
queda para un bloque futuro, no éste).

`n_envs=16` corre sobre `DummyVecEnv` (secuencial, un solo proceso), no `SubprocVecEnv`:
esto entrena en segundo plano durante horas sin supervisión (vía `lanzar.ps1`), y una falla
de multiprocessing en Windows a media corrida sería peor que perder el paralelismo real.
Decisión documentada, no un descuido.

`pasos_objetivo` se dimensiona en tiempo de ejecución a partir de los steps/s medidos de
ESTE `VecEnv` concreto (L1, 16 envs), para llegar a ~8h de entrenamiento -- no un número
fijo adivinado.

Uso: python -m vygo.train_ppo
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy
from sb3_contrib.common.maskable.utils import get_action_masks
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

from vygo.env import VygoEnv
from vygo.policy_net import VygoFeaturesExtractor

_AI_ROOT = Path(__file__).resolve().parent.parent
_CHECKPOINTS = _AI_ROOT / "checkpoints"
_REPORTS = _AI_ROOT / "reports"

SEMILLA_ENTRENAMIENTO = 0  # UNA semilla, autorizado por la tarea (sin currículum)
SEMILLA_VAL_INICIO = 10_000  # misma reserva que bc.py: nunca se entrena sobre estas
N_ENVS = 16
M_COMERCIOS = 80  # congelado desde la tarea "diagnostico de agrupamiento"
DURACION_TURNO_S = 2 * 3600.0  # mismo criterio que sanity_check.py/bc.py: rápido, representativo
MAX_PASOS_ESCENARIO_VAL = 20_000
N_ESCENARIOS_VAL = 10
CADA_PASOS = 25_000
HORAS_OBJETIVO = 8.0
PASOS_BENCHMARK = 2_000


def _crear_env(seed: int):
    def _fn():
        env = VygoEnv(nivel="L1", m_comercios=M_COMERCIOS, duracion_turno_s=DURACION_TURNO_S)
        env.reset(seed=seed)
        return env
    return _fn


def _medir_steps_por_segundo(vec_env: VecNormalize) -> float:
    """Acción aleatoria ENTRE LAS QUE LA MÁSCARA PERMITE (como `baselines.politica_aleatoria`),
    no `action_space.sample()` puro: `_aplicar_accion`/`eval_insertion` no vuelven a
    imponer el tope `K_A_MAXIMO` (sólo lo hace `feasibility.action_mask`, que toda política
    real -- B0/B1/B2/MaskablePPO -- respeta por construcción), así que una acción de
    aceptar fuera de máscara puede colar un 5º pedido y disparar el assert de seguridad de
    `env._aceptar_oferta`. Se descubrió exactamente así al medir aquí."""

    vec_env.reset()
    t0 = time.perf_counter()
    for _ in range(PASOS_BENCHMARK):
        masks = get_action_masks(vec_env)
        accion = np.array([np.random.choice(np.flatnonzero(masks[i])) for i in range(N_ENVS)])
        vec_env.step(accion)
    dt = time.perf_counter() - t0
    return (PASOS_BENCHMARK * N_ENVS) / dt


def _rho_de_escenario(model: MaskablePPO, vecnorm: VecNormalize, seed: int) -> float:
    env = VygoEnv(nivel="L1", m_comercios=M_COMERCIOS, duracion_turno_s=DURACION_TURNO_S)
    obs, info = env.reset(seed=seed)
    for _ in range(MAX_PASOS_ESCENARIO_VAL):
        mask = info["action_mask"]
        obs_norm = vecnorm.normalize_obs(obs)
        accion, _estado = model.predict(obs_norm, action_masks=mask, deterministic=True)
        obs, _r, term, trunc, info = env.step(int(accion))
        if term or trunc:
            break
    horas = max(env.t / 3600.0, 1e-9)
    return (env.ganancia_acum - 1.2 * env.km_acum) / horas


def _evaluar_rho_validacion(model: MaskablePPO, vecnorm: VecNormalize) -> float:
    """rho_mediana sobre N_ESCENARIOS_VAL escenarios de VALIDACIÓN (semillas >=
    SEMILLA_VAL_INICIO, nunca vistas en entrenamiento) -- acción determinista (moda de la
    distribución enmascarada), obs normalizada con las estadísticas de `vecnorm` (las MISMAS
    que ve la red durante el rollout de entrenamiento; sin esto la evaluación mediría una
    red que nunca vio observaciones en esa escala)."""

    rhos = [_rho_de_escenario(model, vecnorm, SEMILLA_VAL_INICIO + i) for i in range(N_ESCENARIOS_VAL)]
    return float(np.median(rhos))


_MAX_CURVA_EN_STATUS = 20  # ai/CLAUDE.md §8: status.json debe caber en ~150 líneas;
# el historial completo vive en reports/train_log.jsonl (append-only), no aquí.


def _actualizar_status_json(paso: int, pasos_objetivo: int, rho_val: float, mejor_rho: float, eta_minutos: float | None) -> None:
    ruta = _REPORTS / "status.json"
    status = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    status["generado_en"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    curva_previa = status.get("entrenamiento", {}).get("curva", [])
    curva = (curva_previa + [{"paso": int(paso), "rho_val": rho_val}])[-_MAX_CURVA_EN_STATUS:]
    status["entrenamiento"] = {
        "activo": paso < pasos_objetivo,
        "algoritmo": "MaskablePPO (bc_policy.pt como inicialización)",
        "semillas": [SEMILLA_ENTRENAMIENTO],
        "pasos_totales": int(paso),
        "pasos_objetivo": int(pasos_objetivo),
        "eta_minutos": eta_minutos,
        "curva": curva,  # últimas _MAX_CURVA_EN_STATUS; historial completo en train_log.jsonl
        "mejor_rho_val": mejor_rho,
        "etapa_curriculum": None,  # sin currículum, autorizado por la tarea
    }
    status["evaluacion"] = {
        "escenarios": N_ESCENARIOS_VAL,
        "pareada": False,
        "agente": {"rho_mediana": rho_val, "iqr": [None, None]},
        "vs_B2_pct": None,
        "gap_vs_oraculo": None,
    }
    ruta.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class ReporteCallback(BaseCallback):
    """Cada `CADA_PASOS` timesteps: evalúa rho en escenarios de validación, agrega línea a
    `reports/train_log.jsonl`, reescribe `reports/status.json` completo, y guarda el mejor
    checkpoint (`checkpoints/ppo_best.zip`) por rho de validación -- NUNCA
    `checkpoints/bc_policy.pt`, que se preserva intacto como piso garantizado (tarea)."""

    def __init__(self, vecnorm: VecNormalize, pasos_objetivo: int, verbose: int = 1) -> None:
        super().__init__(verbose)
        self.vecnorm = vecnorm
        self.pasos_objetivo = pasos_objetivo
        self._ultimo_eval_en = 0
        self.mejor_rho = -math.inf
        self._t_inicio = time.perf_counter()

    def _on_step(self) -> bool:
        if self.num_timesteps - self._ultimo_eval_en >= CADA_PASOS:
            self._ultimo_eval_en = self.num_timesteps
            self._evaluar_y_reportar()
        return True

    def _evaluar_y_reportar(self) -> None:
        rho_val = _evaluar_rho_validacion(self.model, self.vecnorm)
        es_mejor = rho_val > self.mejor_rho
        if es_mejor:
            self.mejor_rho = rho_val
            _CHECKPOINTS.mkdir(exist_ok=True)
            self.model.save(str(_CHECKPOINTS / "ppo_best"))

        transcurrido_s = time.perf_counter() - self._t_inicio
        progreso = self.num_timesteps / self.pasos_objetivo
        eta_minutos = ((transcurrido_s / progreso) - transcurrido_s) / 60.0 if progreso > 1e-9 else None

        entrada = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "paso": int(self.num_timesteps),
            "pasos_objetivo": int(self.pasos_objetivo),
            "rho_val": rho_val,
            "mejor_rho_val": self.mejor_rho,
            "nuevo_mejor": es_mejor,
            "eta_minutos": eta_minutos,
        }
        with open(_REPORTS / "train_log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entrada, ensure_ascii=False) + "\n")

        _actualizar_status_json(self.num_timesteps, self.pasos_objetivo, rho_val, self.mejor_rho, eta_minutos)

        if self.verbose:
            eta_txt = f"{eta_minutos:.0f}min" if eta_minutos is not None else "?"
            print(
                f"[paso {self.num_timesteps}/{self.pasos_objetivo}] rho_val={rho_val:.2f} "
                f"mejor={self.mejor_rho:.2f} eta={eta_txt}"
                + ("  <- nuevo mejor" if es_mejor else ""),
            )


def main() -> None:
    _CHECKPOINTS.mkdir(exist_ok=True)
    _REPORTS.mkdir(exist_ok=True)

    bc_path = _CHECKPOINTS / "bc_policy.pt"
    if not bc_path.exists():
        raise SystemExit(f"falta {bc_path}: correr `python -m vygo.bc` primero (tarea, punto 5)")

    vec_env = DummyVecEnv([_crear_env(SEMILLA_ENTRENAMIENTO + i) for i in range(N_ENVS)])
    vec_env = VecNormalize(vec_env, norm_obs=True, norm_reward=True)

    print("midiendo steps/s de este VecEnv (L1, 16 envs, DummyVecEnv)...")
    steps_por_segundo = _medir_steps_por_segundo(vec_env)
    vec_env.reset()  # el benchmark dejó los envs a medio episodio; arrancar entrenamiento limpio

    model = MaskablePPO(
        policy=MaskableActorCriticPolicy,
        env=vec_env,
        policy_kwargs=dict(features_extractor_class=VygoFeaturesExtractor, net_arch=[]),
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        learning_rate=1e-4,
        n_steps=512,
        batch_size=2048,
        n_epochs=4,
        ent_coef=0.005,
        seed=SEMILLA_ENTRENAMIENTO,
        verbose=1,
    )
    model.policy.load_state_dict(torch.load(bc_path, map_location="cpu"))
    print(f"pesos de {bc_path} cargados en MaskablePPO -- arranca desde el piso de BC, no desde cero")

    # pasos_objetivo debe contar el costo de EVALUAR, no sólo el de entrenar: la evaluación
    # de N_ESCENARIOS_VAL escenarios completos (turnos de 2h, paso a paso en Python con la
    # red) puede costar varias veces más que recolectar CADA_PASOS de rollout -- medirlo
    # aquí en vez de asumir que es gratis, o el "~8h" del objetivo real de la tarea se
    # convierte en varias veces más sin que nada lo avise.
    print(f"midiendo costo de UNA evaluación completa ({N_ESCENARIOS_VAL} escenarios)...")
    t0 = time.perf_counter()
    _evaluar_rho_validacion(model, vec_env)
    t_eval_s = time.perf_counter() - t0
    tiempo_entrenar_por_ciclo_s = CADA_PASOS / steps_por_segundo
    tiempo_por_ciclo_s = tiempo_entrenar_por_ciclo_s + t_eval_s
    n_ciclos = max(1, int((HORAS_OBJETIVO * 3600.0) / tiempo_por_ciclo_s))
    pasos_objetivo = n_ciclos * CADA_PASOS
    print(
        f"steps/s={steps_por_segundo:.1f}  entrenar/ciclo={tiempo_entrenar_por_ciclo_s:.1f}s  "
        f"evaluar/ciclo={t_eval_s:.1f}s  -> pasos_objetivo={pasos_objetivo} "
        f"({n_ciclos} ciclos de {CADA_PASOS}, ~{HORAS_OBJETIVO:.0f}h reales)",
    )

    callback = ReporteCallback(vecnorm=vec_env, pasos_objetivo=pasos_objetivo)
    model.learn(total_timesteps=pasos_objetivo, callback=callback)

    model.save(str(_CHECKPOINTS / "ppo_final"))
    vec_env.save(str(_CHECKPOINTS / "vecnormalize.pkl"))
    print("entrenamiento terminado -- ppo_final.zip y vecnormalize.pkl guardados (bc_policy.pt intacto)")


if __name__ == "__main__":
    main()
