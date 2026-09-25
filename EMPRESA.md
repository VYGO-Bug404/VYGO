# VYGO — Plan de Empresa

> Documento interno del equipo fundador. Cubre estructura legal, obligaciones fiscales, estudio de mercado y presupuesto operativo.

---

## Tabla de contenidos

1. [Prioridades antes de recibir inversión](#1-prioridades-antes-de-recibir-inversión)
2. [Oferta de inversión activa](#2-oferta-de-inversión-activa)
3. [Estructura legal y fiscal](#3-estructura-legal-y-fiscal)
4. [Privacidad, datos y cumplimiento](#4-privacidad-datos-y-cumplimiento)
5. [Contratos necesarios](#5-contratos-necesarios)
6. [Estudio de mercado — entrevistas con repartidores](#6-estudio-de-mercado--entrevistas-con-repartidores)
7. [Presupuesto operativo](#7-presupuesto-operativo)

---

## 1. Prioridades antes de recibir inversión

| # | Acción | Urgencia |
|---|--------|----------|
| 1 | Identificar a todos los que aportaron código, diseño, modelo y datos durante y después de HackMTY. Revisar reglas de propiedad del evento. | **AHORA** |
| 2 | Firmar acuerdo entre fundadores: porcentajes, vesting, salidas, cesión de PI a la empresa, confidencialidad. | **AHORA** |
| 3 | Probar el mecanismo de lectura de notificaciones en teléfonos reales de producción (3+ modelos). | **ESTA SEMANA** |
| 4 | Completar 25–30 entrevistas con repartidores y arrancar piloto medible. | **ESTA SEMANA** |
| 5 | Constituir la empresa y abrir cuenta bancaria empresarial. | **ANTES DE LA INVERSIÓN** |
| 6 | Revisar term sheet con abogado y negociar condiciones del deal. | **ANTES DE FIRMAR** |

> **Criterio de avance:** acuerdo de fundadores firmado + mecanismo de datos probado + entrevistas completadas + presupuesto con métricas de uso. Con eso se negocia sobre riesgo medido, no sobre el premio del hackathon.

---

## 2. Oferta de inversión activa

### Parámetros del deal

| Concepto | Valor |
|----------|-------|
| Inversión propuesta | $400,000 MXN |
| Equity ofrecido | 20% |
| Valuación post-money implícita | $2,000,000 MXN (~$114,000 USD) |
| Valuación pre-money implícita | $1,600,000 MXN (~$91,000 USD) |
| Equity que retienen los fundadores | 80% (16% c/u si son 5 con participación igual) |

### Por qué 20% es negociable

El rango estándar para una ronda angel pre-revenue en México es **5–15%**. Ceder 20% en la primera ronda comprime el margen para futuras rondas sin perder el control mayoritario de los fundadores.

**Dos posiciones alternativas a proponer:**

- **Opción A:** Reducir a 15% por el mismo monto → valuación post-money implícita de $2,670,000 MXN.
- **Opción B:** Mantener el 20% y solicitar un monto mayor (~$600,000 MXN).

### Proyección de dilución

```
Hoy (pre-inversión):       Fundadores 100%
Post $400k / 20%:          Fundadores 80%  │  Inv. Ángel 20%
Ronda A hipotética (25%):  Fundadores 60%  │  Inv. A 25%  │  Ángel ~15%
Ronda B hipotética (20%):  Fundadores 48%  │  ...
```

Con 20% cedido en la primera ronda, los fundadores quedan por debajo del 50% colectivo antes de completar una Ronda B. Con 15% inicial se mantiene ese margen significativamente más tiempo.

### Qué revisar en el term sheet

**Cláusulas aceptables:**
- Preferencia de liquidación 1× no participante
- Derecho de primera oferta en futuras rondas (pro-rata)
- Derechos de información: estados financieros trimestrales
- Seat de observador en consejo (sin voto)

**Cláusulas a rechazar o acotar:**
- Anti-dilución ratchet completo — solo aceptar promedio ponderado base amplia
- Veto sobre decisiones operativas (contrataciones, gasto, estrategia de producto)
- Drag-along sin umbral mínimo de aprobación de fundadores
- Exclusividad con el inversionista por más de 30 días

> **Regla de oro:** no firmar ningún documento vinculante antes de que el abogado corporativo revise los términos completos.

---

## 3. Estructura legal y fiscal

> Hoja de trabajo para llevar con abogado corporativo y contador. Los documentos finales dependen de quiénes serán socios y de cómo cobrarán.

### Tipo de sociedad

| Tipo | Características | Recomendación |
|------|----------------|---------------|
| **S.A.P.I. de C.V.** | Permite distintas clases de acciones, ideal para inversión con condiciones diferenciadas | Pedir cotización y estatutos comparados |
| **S.A. de C.V.** | Opción clásica, bien conocida por inversionistas y notarios | Pedir cotización y comparar con S.A.P.I. |
| **S.A.S.** | Constitución electrónica más rápida, pero límite de ingresos ~$7.6M MXN/año | No elegir solo por el trámite; limitante si la inversión es próxima |

### Constitución y administración

- Denominación social — buscar "VYGO" y variantes en IMPI antes de usarla
- Estatutos con cláusulas de vesting, salidas y propiedad intelectual
- Definir accionistas, porcentajes y poderes del administrador
- Libros corporativos
- Cuenta bancaria empresarial (nunca mezclar con cuentas personales)
- Reglas escritas para aprobar gastos y acceso a repositorios y dominios
- Registrar beneficiario controlador

### Impuestos y contabilidad

- Inscripción en RFC de la persona moral; definir régimen y actividades
- ISR personas morales: **30% sobre resultado fiscal** (no sobre ingresos brutos)
- Emisión de CFDI para cobros de suscripciones
- Registro de aportaciones de socios y pagos a proveedores extranjeros
- IVA, acreditamientos y retenciones — confirmar tratamiento con contador
- Declaraciones mensuales al SAT
- Conciliación mensual: banco + pasarela de pago + facturas

> Los servicios contratados al extranjero (AWS, Google, Anthropic) requieren tratamiento fiscal específico. Definirlo antes de la primera factura.

### Marca y propiedad intelectual

- Buscar "VYGO" y variantes en el portal del IMPI **antes** de invertir en publicidad
- Solicitar registro de marca por las clases aplicables
- Referencia de tarifa IMPI: $2,695 MXN + IVA por solicitud en línea (confirmar al generar línea de captura)
- Repositorios, dominio y contratos de desarrollo bajo titularidad de la empresa, no de personas físicas
- Código generado durante HackMTY: revisar reglas de propiedad intelectual del evento antes de constituir

---

## 4. Privacidad, datos y cumplimiento

**Ley aplicable:** Ley Federal de Protección de Datos Personales en Posesión de los Particulares (México).

### Inventario de datos que se recopilan

- Ubicación en tiempo real
- Historial de turnos y pedidos
- Ingresos estimados por pedido
- Identificadores de dispositivo
- Contenido de notificaciones de plataformas (Uber, Rappi, DiDi)

### Obligaciones

- Definir qué se guarda, por cuánto tiempo y quién accede
- Documentar qué proveedores reciben datos (AWS, Google, Anthropic)
- Establecer proceso para atender derechos ARCO (acceso, rectificación, cancelación, oposición)
- Implementar proceso de borrado completo de cuenta y datos
- Redactar aviso de privacidad que describa el funcionamiento **real**, no uno hipotético

### Riesgos específicos de VYGO

Que un repartidor autorice la lectura de sus notificaciones **no equivale** a tener una alianza con Uber, Rappi o DiDi. Revisar por separado los términos de cada plataforma y las políticas de distribución de Google Play. Google Play clasifica ubicación y datos de dispositivo como información sensible y exige divulgación y consentimiento explícito.

---

## 5. Contratos necesarios

- [ ] Acuerdo entre fundadores ← **prioridad inmediata**
- [ ] Términos de uso para repartidores (estimaciones, errores, disponibilidad, cancelación)
- [ ] Política de privacidad
- [ ] Contratos con desarrolladores y colaboradores externos
- [ ] Revisión de condiciones de Google Maps, AWS, Anthropic y todos los SDKs
- [ ] Validar si las colaboraciones son relación laboral (IMSS) o prestación de servicios — caso por caso con asesor laboral

---

## 6. Estudio de mercado — entrevistas con repartidores

### Metodología

- **Meta:** 25–30 entrevistas en Monterrey
- **Perfil:** mezclar una sola app y varias; moto, auto y bicicleta; turnos y zonas distintas
- **Reclutamiento:** fuera del círculo de conocidos
- **Instrucción clave:** no mostrar VYGO hasta haber entendido el problema actual del repartidor

### Preguntas de entrevista

**Contexto y última jornada**

1. ¿Con qué plataformas trabajaste la semana pasada y cuántas horas estuviste conectado?
2. Cuéntame tu último turno, desde que empezaste hasta que terminaste.

**Decisiones y datos**

3. En tu última oferta que rechazaste, ¿qué viste y por qué la rechazaste?
4. ¿Cuándo aceptaste un pedido que después resultó malo? ¿Qué dato te faltó?
5. ¿Cómo calculas hoy si te conviene un pedido? Muéstrame tu método, si tienes uno.

**Costos y tiempos reales**

6. ¿Cuánto gastaste en gasolina, comisiones, estacionamiento y mantenimiento la semana pasada? ¿Cómo lo sabes?
7. ¿Qué tanto tiempo esperas en restaurantes y cómo afecta tus decisiones?
8. ¿Qué haces cuando llegan ofertas de dos apps casi al mismo tiempo?

**Herramientas actuales y fricción**

9. ¿Usas alguna app, hoja de cálculo o grupo para decidir o registrar ganancias? ¿Qué te cuesta usarla?
10. ¿En qué momento consultarías otra pantalla y en cuál sería peligroso o imposible?

**Privacidad y disposición a pagar**

11. ¿Qué información aceptarías compartir para recibir recomendaciones? ¿Cuál no?
12. ¿Qué tendría que pasar durante una semana para que dijeras "esto me ayudó"?
13. ¿Has pagado por alguna herramienta para trabajar? ¿Cuál y cuánto?
14. *(Mostrar VYGO)* ¿Puedes interpretar esta recomendación en 5 segundos? ¿Qué cambiarías? Si comprobara una mejora verificable, ¿cómo preferirías pagarla? *(pedir precio concreto)*

### Métricas del piloto

Definir antes de iniciar, no después de ver resultados:

| Métrica | Descripción |
|---------|-------------|
| Ganancia neta/hora | Después de gasolina, comisiones y tiempo de espera |
| Costo/km recorrido | — |
| Tasa de seguimiento | % de recomendaciones que el repartidor siguió |
| Retención semanal | ¿Siguen usando VYGO en semana 2 y 3? |
| Errores de lectura | Notificaciones mal interpretadas |
| Tiempo de espera promedio | En restaurantes |

> Comparar jornadas suficientemente parecidas de los **mismos** repartidores. Documentar día, clima y zona. La mejora debe superar el costo de la suscripción y la fricción de usar otra app.

### Errores que invalidan el estudio

- Entrevistar solo a amigos o conocidos que quieren apoyar el proyecto
- Pedir contraseñas o capturas que muestren datos de clientes de las plataformas
- Mostrar VYGO antes de entender el problema actual del repartidor
- Preguntar "¿cuánto pagarías?" antes de describir el beneficio concreto
- Interpretar "sí me interesa" como intención real de compra

---

## 7. Presupuesto operativo

> Precios en USD son referencias públicas (sept 2025). Verificar en México antes de presupuestar.

### Herramientas del equipo

| Partida | Referencia | Notas |
|---------|-----------|-------|
| Claude Team (5 personas) | ~$125 USD/mes | $25/persona/mes. Pago anual ~$20/persona/mes. Verificar precio en México. |
| Google Maps Routes Essentials | 0 hasta 10k req/mes, luego $5 USD/1,000 | SKUs Pro y matrices cuestan más. |
| AWS | desde $5–10 USD/mes (Lightsail referencia) | Usar calculadora de AWS para la arquitectura real. |
| Google Play Developer | $25 USD pago único | Para publicar en Android. |
| Apple Developer (si aplica) | $99 USD/año | Evaluar viabilidad técnica del notification listener en iOS primero. |

### Gastos de constitución

| Partida | Referencia |
|---------|-----------|
| Abogado corporativo | Cotizar (varía según tipo societario y complejidad) |
| Notario | Incluido en el proceso de constitución |
| Contador / setup fiscal | Cotizar |
| Marca VYGO — IMPI | ~$2,695 MXN + IVA por solicitud (confirmar al generar línea de captura) |
| Dominio y correo corporativo | ~$20–50 USD/año |

### Partidas adicionales a presupuestar

- Base de datos (Supabase Free o desde $25 USD/mes)
- Monitoreo y respaldos
- Pasarela de pago (comisión por transacción)
- Comisión de tiendas si cobran en app (15–30%)
- Incentivos para el piloto con repartidores
- Atención a usuarios
- Publicidad y adquisición
- Sueldos o compensación a fundadores
- Contabilidad mensual
- Asesoría de privacidad

### Fórmula de costo mensual

```
costo_mes =
    herramientas_equipo
  + infraestructura_fija
  + (usuarios_activos × consultas_por_usuario × costo_unitario)
  + personal
  + administración
```

Para calcular el costo real se requiere:
- Usuarios esperados en piloto, mes 6 y mes 12
- Ofertas evaluadas por usuario al día
- Llamadas a Google Maps por oferta evaluada
- Horas de ubicación activa por usuario
- Arquitectura AWS definida

---

*Documento interno del equipo VYGO · Actualizado sept 2025*
