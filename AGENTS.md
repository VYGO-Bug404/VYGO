# Workspace Rules: Antigravity / Vygo

## Preservación de Geometría de Ruteo Vial (GIS & MapLibre)

1. **Fuente Única de Verdad**: Las polilíneas viales de alta resolución generadas por algoritmos de ruteo (A*, OSMnx) del backend deben tratarse como inmutables en el cliente.
2. **Prohibido el Fallback Destructivo**: Nunca sobreescribir una geometría vial válida existente en el store con líneas rectas o interpolaciones euclidianas cuando una petición secundaria falle o esté fuera de rango GPS.
3. **No Slicing Manual en MapLibre**: No recortar vértices geométricos en el hilo de renderizado del mapa basándose en proximidad euclidiana de GPS, ya que decapita paradas y genera parpadeos con el ciclo de vida de React.
4. **Renderizado Declarativo**: El componente de mapa (`MockMap`) debe limitarse a recibir `routeGeoJSON` y aplicarlo mediante `src.setData()`, manteniendo exactamente 2 capas limpias: halo blanco (`#FFFFFF`, 8px, 0.5) debajo y trazo verde (`#6FA800`, 4px) encima.
