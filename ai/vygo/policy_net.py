"""Red de política/valor para BC + PPO (tarea "agente entrenado", ai/CLAUDE.md §6).

Arquitectura fija sobre el layout EXACTO de `features.py` (186 = 14 propio + 6x10 plan +
8x14 ofertas): MLP(128) sobre el bloque propio, self-attention sobre el plan activo,
cross-attention sobre las ofertas (consulta = propio+plan), tronco MLP(256,256), cabezas de
política (10 salidas, enmascarada por sb3-contrib) y valor a cargo de
`MaskableActorCriticPolicy` con `net_arch=[]` (el tronco ya deja 256 dims listas).

Se usa la MISMA clase de política en bc.py (entrena por entropía cruzada, guarda
checkpoints/bc_policy.pt) y en train_ppo.py (MaskablePPO carga ese checkpoint con
`policy.load_state_dict(...)`) -- por eso vive aquí, no duplicada en los dos scripts.
"""

from __future__ import annotations

from typing import Callable

import gymnasium
import torch
from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from torch import nn

from vygo.features import DIM_OFERTA, DIM_PLAN_POR_PEDIDO, DIM_PROPIO, K_A, K_F

D_MODELO = 64
N_CABEZAS = 4
DIM_PROPIO_EMBED = 128
FEATURES_DIM = 256


class VygoFeaturesExtractor(BaseFeaturesExtractor):
    def __init__(self, observation_space: gymnasium.Space) -> None:
        super().__init__(observation_space, features_dim=FEATURES_DIM)

        self.mlp_propio = nn.Sequential(
            nn.Linear(DIM_PROPIO, DIM_PROPIO_EMBED), nn.ReLU(),
            nn.Linear(DIM_PROPIO_EMBED, DIM_PROPIO_EMBED), nn.ReLU(),
        )
        self.proy_plan = nn.Linear(DIM_PLAN_POR_PEDIDO, D_MODELO)
        self.atn_plan = nn.MultiheadAttention(D_MODELO, N_CABEZAS, batch_first=True)

        self.proy_consulta = nn.Linear(DIM_PROPIO_EMBED + D_MODELO, D_MODELO)
        self.proy_ofertas = nn.Linear(DIM_OFERTA, D_MODELO)
        self.atn_ofertas = nn.MultiheadAttention(D_MODELO, N_CABEZAS, batch_first=True)

        self.tronco = nn.Sequential(
            nn.Linear(DIM_PROPIO_EMBED + D_MODELO + D_MODELO, 256), nn.ReLU(),
            nn.Linear(256, 256), nn.ReLU(),
        )

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        off_plan = DIM_PROPIO
        off_ofertas = DIM_PROPIO + K_A * DIM_PLAN_POR_PEDIDO

        propio = observations[:, :DIM_PROPIO]
        plan = observations[:, off_plan:off_ofertas].reshape(-1, K_A, DIM_PLAN_POR_PEDIDO)
        ofertas = observations[:, off_ofertas:].reshape(-1, K_F, DIM_OFERTA)

        h_propio = self.mlp_propio(propio)  # (B, 128)

        # Self-attention sobre el plan activo. Slots vacíos (pedido inexistente, todo en
        # cero) se descuentan del pooling con un promedio ponderado -- key_padding_mask
        # directo arriesgaría NaN cuando el plan entero está vacío (softmax sobre puros
        # -inf), que es exactamente el estado inicial de cada episodio.
        plan_tok = self.proy_plan(plan)  # (B, K_A, D)
        plan_attn, _ = self.atn_plan(plan_tok, plan_tok, plan_tok)
        plan_valido = (plan.abs().sum(dim=-1, keepdim=True) > 0).float()  # (B, K_A, 1)
        h_plan = (plan_attn * plan_valido).sum(dim=1) / plan_valido.sum(dim=1).clamp(min=1.0)

        # Cross-attention: la consulta es propio+plan (1 token), las llaves/valores son las
        # K_F ofertas visibles -- exactamente lo que pide la tarea.
        consulta = self.proy_consulta(torch.cat([h_propio, h_plan], dim=-1)).unsqueeze(1)  # (B,1,D)
        ofertas_tok = self.proy_ofertas(ofertas)  # (B, K_F, D)
        ofertas_attn, _ = self.atn_ofertas(consulta, ofertas_tok, ofertas_tok)
        h_ofertas = ofertas_attn.squeeze(1)  # (B, D)

        h = torch.cat([h_propio, h_plan, h_ofertas], dim=-1)
        return self.tronco(h)


def crear_policy(
    observation_space: gymnasium.Space,
    action_space: gymnasium.Space,
    lr_schedule: Callable[[float], float],
) -> MaskableActorCriticPolicy:
    """Misma política para BC y PPO -- `net_arch=[]` porque el tronco de
    `VygoFeaturesExtractor` ya entrega 256 dims listas para las cabezas de política/valor
    de sb3-contrib (nada de MLP extra antes de ellas)."""

    return MaskableActorCriticPolicy(
        observation_space, action_space, lr_schedule,
        net_arch=[],
        features_extractor_class=VygoFeaturesExtractor,
    )
