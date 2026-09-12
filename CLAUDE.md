# VYGO — Monorepo

Plataforma middleware para repartidores que trabajan con Uber Eats, Rappi y DiDi Food
simultáneamente. El sistema recomienda qué ofertas aceptar y en qué orden entregarlas, para
maximizar la tasa de ganancia del repartidor (MXN/hora).

## Mapa del repositorio

```
/                   frontend: Vite + React + TypeScript + Tailwind
├── src/            ← aplicación web. NO la toques desde tareas de IA.
├── index.html
├── package.json, vite.config.ts, tailwind.config.js
├── docs/           documentación compartida (esquema de BD, modelo matemático)
└── ai/             ← agente de RL en Python. Tiene su propio CLAUDE.md.
```

## Regla de aislamiento (importante)

El trabajo del agente de RL ocurre **exclusivamente dentro de `ai/`**.

- Si estás trabajando en el agente: lee `ai/CLAUDE.md` y no modifiques nada fuera de `ai/`.
- Si estás trabajando en el frontend: no modifiques nada dentro de `ai/`.
- La única superficie de contacto entre ambos es `ai/reports/status.json` y `ai/demo/`, que el
  frontend puede leer pero nunca escribir.

Motivo: son dos stacks distintos (Node/TS vs Python) y dos personas distintas trabajando en
paralelo con un plazo corto. Cruzar la frontera genera conflictos de merge que cuestan más que
cualquier feature.

## Ramas

- `main` — frontend estable. No se hace trabajo de IA aquí.
- `ai/rl-agent` — todo el desarrollo del agente. Se mergea a `main` sólo al final.

## Base de datos

Supabase / PostgreSQL 17 con PostGIS. El esquema completo (9 tablas) está en
`docs/vygo-ai-training.pdf`. Tanto el frontend como el simulador del agente usan **los mismos
nombres de tabla, columnas, enums y estados**. Si cambias el esquema, se actualizan los dos.
