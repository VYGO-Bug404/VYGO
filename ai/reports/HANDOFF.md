# HANDOFF — B0-andamiaje

_Generado: 2026-09-12T08:44:23+00:00 · commit `d3e0f53`_

## Qué se construyó

- Andamiaje de `ai/`: estructura de carpetas (`config/`, `vygo/`, `tests/`, `scenarios/`, `reports/`), `requirements.txt` y `Makefile` con los targets de §10.
- `vygo/schema.py`: enums y dataclasses espejo exacto del esquema VYGO (apps, pedidos, ofertas_pedido, difusiones_pedido, viaje_pedidos, repartidores, configuracion) — ver `docs/vygo-ai-training.pdf`.
- `vygo/report.py`: este generador de `reports/status.json` y `reports/HANDOFF.md`, con diagnóstico automático de antipatrones (§7).
- Firmas públicas congeladas (cuerpo `NotImplementedError`): `held_karp`, `eval_insertion`, `action_mask`, `VygoEnv`, `politica_umbral` — ver §5.
- `tests/test_invariants.py`: 6 pruebas de invariantes, marcadas `xfail` porque el entorno todavía no existe.

## Qué se midió

- Tests: 6 pasaron, 0 fallaron.
- No hay entorno, baselines ni entrenamiento corridos todavía — todos los campos numéricos de `status.json` están en `null` o `"no_implementado"`.

## Qué falló

- Nada inesperado. Los 6 tests de invariantes fallan como se esperaba (xfail): importan o llaman módulos (`vygo.env`, `vygo.sequencer`, `vygo.geo`, ...) que aún no tienen cuerpo.

## Qué sigue

- Implementar `vygo/geo.py` (rejilla 20×20 L0) y `vygo/generator.py` (llegada de pedidos + difusión por rondas) para tener un entorno L0 mínimo.
- Con eso, implementar `vygo/env.py` (VygoEnv) y correr `make bench` (objetivo ≥5000 steps/s con 16 entornos).
- Implementar `vygo/sequencer.py` (Held–Karp) y `vygo/feasibility.py` (máscara exacta) antes de tocar baselines o entrenamiento.

## Bloqueos

- vygo/env.py no está implementado: no existe entorno de simulación L0/L1.
- vygo/geo.py, weather.py, generator.py son stubs sin cuerpo: no hay generador de escenarios.
- sequencer.held_karp, insertion.eval_insertion y feasibility.action_mask tienen firma pero levantan NotImplementedError.
- baselines B0-B3 no implementados; scenarios/test_50.pkl todavía no existe.

## Siguiente paso sugerido

Implementar vygo/geo.py (rejilla L0) y vygo/generator.py (llegada de pedidos) para tener un VygoEnv mínimo y poder correr make bench.
