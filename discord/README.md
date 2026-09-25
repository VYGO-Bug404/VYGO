# Discord Webhooks — VYGO

Mensajes listos para enviar al servidor de Discord del equipo.

## Archivos

| Archivo | Contenido | Canal sugerido |
|---------|-----------|----------------|
| `01_bienvenida.json` | Introducción al canal y secciones | `#empresa` |
| `02_prioridades.json` | 6 prioridades antes de la inversión | `#empresa` |
| `03_deal.json` | Análisis del deal $400k MXN / 20% | `#empresa` |
| `04_mercado.json` | Guía de entrevistas + métricas del piloto | `#mercado` |
| `05_tareas.json` | Asignación de tareas por prioridad | `#tareas` |

## Cómo enviarlos

### Opción 1 — curl (terminal)

```bash
curl -X POST "TU_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d @01_bienvenida.json
```

Reemplazar `TU_WEBHOOK_URL` con la URL del webhook de Discord.  
Repetir para cada archivo en orden (01 → 05).

### Opción 2 — Script para enviar todos de una vez

```bash
WEBHOOK="TU_WEBHOOK_URL"

for file in 01_bienvenida.json 02_prioridades.json 03_deal.json 04_mercado.json 05_tareas.json; do
  curl -s -X POST "$WEBHOOK" -H "Content-Type: application/json" -d @"$file"
  sleep 1
done
```

### Cómo obtener la URL del webhook

1. Discord → servidor → canal → Editar canal → Integraciones → Webhooks → Nuevo webhook
2. Copiar la URL del webhook
3. Pegarla donde dice `TU_WEBHOOK_URL`

## Flujo sugerido de canales en Discord

```
📁 VYGO — Empresa
 ├── #empresa          → mensajes 01, 02, 03 (fijados)
 ├── #mercado          → mensaje 04 (fijado)
 └── #tareas           → mensaje 05 (fijado, actualizar al asignar responsables)
```
