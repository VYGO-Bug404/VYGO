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

El equipo trabaja en Windows 10, donde `make` no está disponible. El punto de entrada es
`run.py` (funciona igual en Windows, macOS y Linux); `Makefile` es sólo una envoltura delgada
de los mismos subcomandos para quien sí tenga `make`.

```bash
python run.py test        # pytest tests/ -q
python run.py bench       # steps/s del entorno
python run.py baselines   # B0..B2 sobre escenarios congelados
python run.py train --seed 0
python run.py eval        # evaluación pareada final
python run.py report      # regenera reports/
```

## Contrato con el frontend

El frontend (`src/`, fuera de este directorio) **sólo lee** `ai/reports/status.json` y los
archivos de `ai/demo/`. Nunca los escribe. Ese es el único punto de contacto entre ambos stacks;
ver `../CLAUDE.md` y `CLAUDE.md` (este directorio) para el detalle completo de la regla de
aislamiento.
