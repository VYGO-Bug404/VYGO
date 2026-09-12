"""Combina la plantilla `demo/_plantilla_turno.html` con los datos de
`demo/turno_datos.json` (generados por `vygo/generar_demo.py`) en `demo/turno.html` --
UN SOLO archivo autocontenido, sin CDN, que abre directo en el navegador sin servidor.

Uso: python -m vygo.empaquetar_demo
"""

from __future__ import annotations

import json
from pathlib import Path

_AI_ROOT = Path(__file__).resolve().parent.parent
RUTA_PLANTILLA = _AI_ROOT / "demo" / "_plantilla_turno.html"
RUTA_DATOS = _AI_ROOT / "demo" / "turno_datos.json"
RUTA_SALIDA = _AI_ROOT / "demo" / "turno.html"


def empaquetar() -> None:
    if not RUTA_DATOS.exists():
        raise SystemExit(f"falta {RUTA_DATOS} -- correr primero: python -m vygo.generar_demo")

    datos = json.loads(RUTA_DATOS.read_text(encoding="utf-8"))
    # Re-serializar (no sólo copiar el texto) para poder escapar "</" de forma segura --
    # si algún string embebido llevara literalmente "</script>", cerraría el bloque a la
    # mitad y rompería el HTML.
    datos_json = json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")

    plantilla = RUTA_PLANTILLA.read_text(encoding="utf-8")
    if "__DATOS_JSON__" not in plantilla:
        raise SystemExit(f"{RUTA_PLANTILLA} no tiene el marcador __DATOS_JSON__")
    html = plantilla.replace("__DATOS_JSON__", datos_json)

    RUTA_SALIDA.write_text(html, encoding="utf-8")
    print(f"escrito {RUTA_SALIDA} ({len(html) / 1024:.0f} KiB)")


if __name__ == "__main__":
    empaquetar()
