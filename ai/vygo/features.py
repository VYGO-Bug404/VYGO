"""Vector de observación EXACTO de ai/CLAUDE.md §6: propio (14) + plan activo (6x10) +
ofertas (8x14) = 186 dims, float32. Buffer preasignado en __init__, cero allocations por
step: `construir()` reescribe el mismo array en vez de crear uno nuevo.

Los slots de features que todavía no tienen valor real (por ejemplo, mientras generator.py
no calcula alguna cantidad) van en 0.0 pero PRESENTES en el layout: la dimensión total no
cambia nunca, para no invalidar VecNormalize ni checkpoints ya entrenados.
"""

from __future__ import annotations

import numpy as np

from vygo.schema import CLIMA_SIMULABLE

K_A = 6  # pedidos del plan activo (ai/CLAUDE.md §6)
K_F = 8  # ofertas visibles

DIM_PROPIO = 14
DIM_PLAN_POR_PEDIDO = 10
DIM_OFERTA = 14
DIM_TOTAL = DIM_PROPIO + K_A * DIM_PLAN_POR_PEDIDO + K_F * DIM_OFERTA  # 186

_OFF_PLAN = DIM_PROPIO
_OFF_OFERTAS = DIM_PROPIO + K_A * DIM_PLAN_POR_PEDIDO


class ConstructorFeatures:
    """`construir(propio, plan, ofertas)` rellena y devuelve SIEMPRE el mismo buffer
    (`self.buffer`): quien lo consume debe copiarlo si necesita conservarlo entre pasos."""

    __slots__ = ("buffer",)

    def __init__(self) -> None:
        self.buffer = np.zeros(DIM_TOTAL, dtype=np.float32)

    def construir(self, propio: dict, plan: list[dict], ofertas: list[dict | None]) -> np.ndarray:
        self.buffer.fill(0.0)
        self._llenar_propio(propio)
        self._llenar_plan(plan)
        self._llenar_ofertas(ofertas)
        return self.buffer

    def _llenar_propio(self, p: dict) -> None:
        b = self.buffer
        b[0] = p["x_norm"]
        b[1] = p["y_norm"]
        b[2] = p["carga_frac"]
        b[3] = p["t_transcurrido_norm"]
        b[4] = p["t_restante_norm"]
        b[5] = p["rho_hat_norm"]
        b[6] = p["ganancia_acum_norm"]
        b[7] = p["km_acum_norm"]
        clima = p["clima"]
        if clima in CLIMA_SIMULABLE:
            b[8 + CLIMA_SIMULABLE.index(clima)] = 1.0
        b[13] = p["densidad_local"]

    def _llenar_plan(self, plan: list[dict]) -> None:
        b = self.buffer
        for i in range(min(K_A, len(plan))):
            off = _OFF_PLAN + i * DIM_PLAN_POR_PEDIDO
            item = plan[i]
            b[off + 0] = item["delta_origen_x"]
            b[off + 1] = item["delta_origen_y"]
            b[off + 2] = item["delta_destino_x"]
            b[off + 3] = item["delta_destino_y"]
            b[off + 4] = item["tarifa_norm"]
            b[off + 5] = item["holgura_frescura_norm"]
            b[off + 6] = item["holgura_fecha_limite_norm"]
            b[off + 7] = item["r_menos_t_norm"]
            b[off + 8] = item["recogido"]
            b[off + 9] = item["app_idx_norm"]

    def _llenar_ofertas(self, ofertas: list[dict | None]) -> None:
        b = self.buffer
        for i in range(min(K_F, len(ofertas))):
            o = ofertas[i]
            if o is None:
                continue
            off = _OFF_OFERTAS + i * DIM_OFERTA
            b[off + 0] = o["delta_origen_x"]
            b[off + 1] = o["delta_origen_y"]
            b[off + 2] = o["delta_destino_x"]
            b[off + 3] = o["delta_destino_y"]
            b[off + 4] = o["tarifa_norm"]
            b[off + 5] = o["tarifa_por_km"]
            b[off + 6] = o["delta_t_norm"]
            b[off + 7] = o["delta_dist_norm"]
            b[off + 8] = o["tasa_marginal_norm"]
            b[off + 9] = o["anillo_norm"]
            b[off + 10] = o["p_gana_estimada"]
            b[off + 11] = o["r_menos_t_norm"]
            b[off + 12] = o["segundos_para_expirar_norm"]
            b[off + 13] = o["factible"]
