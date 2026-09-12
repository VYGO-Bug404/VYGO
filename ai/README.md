# VYGO-RL — Agente de RL

Agente de reinforcement learning que decide **aceptar / rechazar / reposicionar** ofertas de
reparto de Uber Eats, Rappi y DiDi Food, para maximizar la tasa de ganancia del repartidor
(MXN/hora). Es middleware: no genera datos, sólo optimiza decisiones sobre ofertas ya emitidas
por las plataformas. La secuenciación de paradas y las restricciones duras (frescura, capacidad)
no se aprenden: se resuelven exacto (Held–Karp) y con máscara de factibilidad.

## Instalación

```bash
cd ai
python -m venv .venv
.venv/Scripts/activate   # o source .venv/bin/activate en Unix
pip install -r requirements.txt
```

## Uso

```bash
make test       # pytest tests/ -q
make bench      # steps/s del entorno
make baselines  # B0..B2 sobre escenarios congelados
make train SEED=0
make eval       # evaluación pareada final
make report     # regenera reports/
```

## Contrato con el frontend

El frontend (`src/`, fuera de este directorio) **sólo lee** `ai/reports/status.json` y los
archivos de `ai/demo/`. Nunca los escribe. Ese es el único punto de contacto entre ambos stacks;
ver `../CLAUDE.md` y `CLAUDE.md` (este directorio) para el detalle completo de la regla de
aislamiento.
