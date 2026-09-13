# Optimización de rutas multiplataforma para repartidores
## Modelo matemático, ambiente de simulación y diseño de agentes

**Proyecto:** capa intermediaria (*middleware*) de agregación y ruteo entre un repartidor y múltiples plataformas de entrega (Uber Eats, Rappi, DiDi Food, paquetería).
**Alcance geográfico del caso de estudio:** Zona Metropolitana de Monterrey, Nuevo León.
**Naturaleza del documento:** investigación y planteamiento formal. No se generan datos nuevos; se optimizan decisiones sobre datos que las plataformas ya entregan.
**Fecha:** septiembre 2026.

---

## 0. Resumen ejecutivo

El problema que estamos planteando **no es un problema de ruteo clásico**. Un VRP normal recibe un conjunto conocido de clientes y pregunta "¿en qué orden los visito para minimizar distancia?". Aquí ocurren cuatro cosas distintas al mismo tiempo:

1. **Los pedidos aparecen mientras ya vas manejando** (problema dinámico, no estático).
2. **Puedes rechazar pedidos**, y rechazar suele ser la decisión correcta (problema *selectivo* / de recolección de premios, no de cobertura obligatoria).
3. **El objetivo no es minimizar distancia sino maximizar una tasa de ganancia** (pesos por hora neta), lo que cambia la estructura matemática del óptimo.
4. **El agrupamiento (*bundling*) es la fuente real de valor**: el tiempo muerto esperando que una cocina termine de preparar es tiempo que puede pagar por sí mismo si en ese intervalo recoges otro pedido. La restricción que limita cuántos pedidos puedes acumular no es la capacidad de la mochila sino la **degradación del producto** (comida que se enfría) y las fechas límite prometidas por cada app.

El documento formaliza esto en tres capas:

- **Capa 1 — Modelo determinista de referencia (MILP).** Un "oráculo clarividente" que conoce todos los pedidos del turno por adelantado. No es implementable en producción, pero es la **cota superior** contra la cual se mide cualquier agente. Sin esta cota no se puede afirmar que un agente de RL sea bueno. (§3)
- **Capa 2 — Modelo dinámico real (SMDP con criterio de recompensa promedio).** Es la formulación honesta del problema: decisiones dirigidas por eventos, tiempos de preparación aleatorios, tráfico y clima estocásticos. De aquí se deriva analíticamente una **regla de aceptación por umbral** (aceptar sólo si la tasa marginal de ganancia del pedido supera tu tasa actual de ganancia) que ya es un algoritmo competitivo por sí sola. (§4)
- **Capa 3 — Sandbox y agentes.** Especificación del simulador por niveles de fidelidad (L0→L3), espacios de observación/acción con enmascaramiento de factibilidad, cinco familias de agentes con su tabla de costo/beneficio, y las técnicas concretas para que el entrenamiento quepa en el tiempo de un hackathón. (§5, §6, §7)

**Recomendación técnica principal (adelantada):** no intentar que un solo agente de RL aprenda a la vez *qué aceptar* y *en qué orden visitar*. La arquitectura con mejor relación resultado/riesgo es **híbrida**: una política aprendida (PPO) decide **aceptar/rechazar** — que es donde vive la incertidumbre del futuro y donde el RL gana — y un solver exacto o casi exacto de inserción decide **la secuencia** del conjunto ya aceptado, que es un subproblema pequeño (rara vez más de 8–12 paradas) y resoluble a optimalidad en milisegundos. Ver §6.5.

---

## 1. Definición del problema

### 1.1 El rol del sistema

El sistema es un intermediario informacional. No contrata, no cobra al cliente final, no fija tarifas, no contacta al comensal. Recibe de cada plataforma conectada la oferta de un trabajo y devuelve al repartidor una recomendación de acción. Formalmente es un **agente de decisión secuencial bajo incertidumbre** que actúa en nombre de un solo trabajador.

Esto tiene dos consecuencias de modelado que conviene fijar desde el principio:

- **Un solo vehículo.** No es un VRP multi-vehículo. Es un problema de **ruta única selectiva** (*single-vehicle profitable pickup and delivery problem with time windows*). Esto reduce enormemente la dificultad combinatoria: la explosión no viene del número de vehículos sino del número de secuencias posibles del conjunto activo, y ese conjunto es pequeño.
- **El repartidor tiene veto.** La política produce recomendaciones, no comandos. Implicación práctica: el agente debe emitir no sólo una acción sino una **justificación cuantitativa** (ganancia marginal esperada, riesgo de retraso, minutos añadidos), y debe ser robusto a que el humano ignore la sugerencia. Eso obliga a que el agente sea *reactivo al estado*, no ejecutor de un plan fijo (§6.7, punto sobre robustez a desviaciones).

### 1.2 Contrato de datos con las plataformas externas

Todo el modelo se apoya en lo que la app externa entrega en el momento de la oferta. Fijamos esto como un **contrato de datos** explícito; si un campo no está disponible, el modelo tiene que estimarlo y esa estimación se vuelve una fuente de error que hay que medir.

| Campo | Símbolo | Origen | Si no viene, ¿qué hacemos? |
|---|---|---|---|
| Plataforma de origen | $p(i)$ | dado | — |
| Nodo de recolección | $o_i$ | dado (lat/lon → nodo de red) | — |
| Zona/nodo de entrega | $d_i$ | dado (a veces sólo zona) | usar el centroide de la zona y modelar la varianza |
| Tarifa ofrecida | $f_i$ | dado | — |
| Distancia estimada | $\hat{\delta}_i$ | dado | calcular sobre la red vial |
| Tiempo de preparación / listo | $r_i$ | a veces sólo un promedio | modelar como variable aleatoria $R_i$ (§5.6) |
| Fecha límite prometida | $\ell_i$ | a veces implícita | derivar de $a_i + \text{ETA}$ de la app |
| Tipo de producto | $\text{tipo}(i)$ | dado o inferible | clasificar en caliente / frío / no perecedero |
| Propina | — | desconocida *ex ante* | tratar como ruido; **no** optimizar contra ella |

> **Nota metodológica importante.** La propina es, en el mundo real, una fracción sustancial del ingreso y es desconocida al momento de decidir. Si se la incluye como si fuera conocida, el modelo se vuelve ilusoriamente bueno. Se modela como una variable aleatoria de media condicionada a la zona de entrega y se optimiza el valor esperado, nunca el realizado.

### 1.3 El fenómeno a capturar: la ventana de holgura

La intuición del planteamiento original, formalizada: cuando el repartidor acepta el pedido $i$ y viaja hacia $o_i$, llega en el instante $T_{o_i}$ pero no puede salir antes de que el producto esté listo, en $r_i$. La **holgura de recolección** es

$$
\sigma_i \;=\; \big(r_i - T_{o_i}\big)^{+} \;=\; \max\{0,\; r_i - T_{o_i}\}
$$

Ese $\sigma_i$ es tiempo pagado por nadie. La tesis del sistema es que existen pedidos $j$ cuya recolección cabe dentro de esa holgura, o cuya trayectoria $o_j \to d_j$ se solapa geométricamente con $o_i \to d_i$, de modo que atenderlos cuesta un tiempo incremental mucho menor que atenderlos por separado. El valor del producto es exactamente la suma de esas holguras convertidas en ingreso.

El límite a la acumulación es doble y ambos límites son **duros**:

- **Frescura / integridad del producto.** Un pedido caliente $i$ recogido en $s_i$ y entregado en $T_{d_i}$ tolera a lo más $\theta_i$ minutos en tránsito. Esto es lo que impide recoger $n$ pedidos arbitrariamente.
- **Fecha límite de la plataforma.** Rebasar $\ell_i$ degrada la calificación del repartidor, lo que tiene un costo económico diferido (menos ofertas futuras, riesgo de desactivación).

---

## 2. Trabajo relacionado y posicionamiento

El problema no es nuevo en su núcleo; lo nuevo es el punto de vista. **Toda la literatura de *meal delivery* está escrita desde la plataforma**, que asigna pedidos a una flota de repartidores para minimizar retrasos o costo total. Nosotros escribimos desde **el repartidor**, que selecciona entre ofertas de varias plataformas competidoras para maximizar su propia tasa de ganancia. Es el problema dual y, hasta donde alcanza la revisión, está muy poco tratado formalmente.

**Mapeo a problemas canónicos.** Nuestro problema es la intersección de:

| Problema canónico | Qué aporta | Qué le falta para ser el nuestro |
|---|---|---|
| PDPTW (*Pickup and Delivery Problem with Time Windows*) | precedencia recolección→entrega, emparejamiento, ventanas | obliga a servir a todos; no hay selección |
| TOPTW / *Profitable Tour Problem* | **selección** de clientes con premio, presupuesto de tiempo | no tiene pares recolección-entrega ni perecibilidad |
| MDRP (*Meal Delivery Routing Problem*) | tiempos de preparación, agrupamiento, *click-to-door* | perspectiva de plataforma, multi-vehículo |
| SDVRP (*Stochastic & Dynamic VRP*) | llegada dinámica de pedidos, formulación MDP | objetivo de costo, no de tasa de ganancia |
| SMDP de recompensa promedio | criterio $/hora, regla de umbral | no trae la estructura de ruteo |

Nuestro problema = PDPTW **+** selección de TOPTW **+** perecibilidad del MDRP **+** dinamismo del SDVRP **+** criterio de tasa promedio, con **un** vehículo y **múltiples fuentes de oferta no coordinadas**.

**Referencias ancla** (detalle bibliográfico completo en §9):

- *The Meal Delivery Routing Problem* (Reyes, Erera, Savelsbergh, Sahasrabudhe, O'Neil, 2018) — introduce el problema y el concepto de *bundling* de pedidos; es la referencia de la que tomamos la estructura de preparación/recolección.
- *Provably High-Quality Solutions for the Meal Delivery Routing Problem* (Yildiz & Savelsbergh, *Transportation Science*) — cotas de optimalidad; metodológicamente es el modelo de cómo justificar que una heurística es buena, que es justo lo que necesitamos con la cota MILP.
- *The Restaurant Meal Delivery Problem: Dynamic Pickup and Delivery with Deadlines and Random Ready Times* (Ulmer, Thomas, Campbell, Woyak, *Transportation Science* 55(1), 2021) — la fuente más cercana a nuestra capa 2: tiempos de preparación **aleatorios** + fechas límite, resuelto con anticipación.
- *Opportunities for reinforcement learning in stochastic dynamic vehicle routing* (Hildebrandt, Thomas, Ulmer, *Computers & OR*, 2023) — encuadre crítico de cuándo el RL realmente aporta sobre ruteo clásico; leerlo antes de comprometerse con RL.
- *Heterogeneous Attentions for Solving Pickup and Delivery Problem via Deep Reinforcement Learning* (Li et al., arXiv:2110.02634) — arquitectura de atención que respeta la relación recolección-entrega; base directa de nuestra opción §6.4.
- *A Closer Look at Invalid Action Masking in Policy Gradient Algorithms* (Huang & Ontañón, arXiv:2006.14171) — justifica teóricamente el enmascaramiento de acciones inválidas, que en nuestro caso es indispensable.
- Literatura cualitativa sobre *multi-apping* (Popan, 2024, *Environment and Planning A*) — evidencia empírica de que los repartidores ya hacen esto manualmente; es la justificación de que el producto responde a una práctica real y no a una hipótesis.

---
## 3. Capa 1 — Modelo determinista de referencia (MILP)

Propósito: **cota superior y generador de etiquetas**. Un modelo que, conociendo el turno completo *a posteriori*, calcula la ganancia máxima alcanzable. Sirve para (a) medir la brecha de optimalidad de cualquier agente, y (b) generar demostraciones expertas para pre-entrenar por imitación (§6.7).

### 3.1 Red física

Sea $G=(\mathcal{V},\mathcal{E})$ la red vial dirigida de la zona metropolitana, con $\mathcal{V}$ intersecciones y $\mathcal{E}$ segmentos. Cada arco $e\in\mathcal{E}$ tiene longitud $\lambda_e$ (km), capacidad $c_e$, velocidad de flujo libre $v_e^0$, y una penalización de giro/control $\pi_e$ (semáforo, rotonda, vuelta continua permitida).

El **tiempo de viaje** es dependiente del tiempo y del clima:

$$
\tau_e(t, w) \;=\; \underbrace{\frac{\lambda_e}{v_e^{0}}\Big(1+\alpha\big(\tfrac{q_e(t)}{c_e}\big)^{\beta}\Big)}_{\text{BPR: congestión}} \;\cdot\; \underbrace{\gamma_w}_{\substack{\text{multiplicador}\\\text{climático}}} \;+\; \underbrace{\pi_e(t)}_{\text{control}}
$$

con $\alpha\approx0.15$, $\beta\approx4$ (parámetros estándar de la función *Bureau of Public Roads*), $q_e(t)$ el flujo en el arco y $\gamma_w \ge 1$ según el estado climático $w$. Definimos $\tau(u,v,t,w)$ como el tiempo del camino más corto dependiente del tiempo entre nodos $u,v$ saliendo en $t$ bajo clima $w$; análogamente $\delta(u,v,t,w)$ para la distancia del camino elegido.

> **Consistencia FIFO.** Para que el camino más corto dependiente del tiempo sea bien comportado (y calculable con Dijkstra modificado) exigimos la propiedad **no-passing / FIFO**: $t_1 \le t_2 \Rightarrow t_1+\tau_e(t_1,w) \le t_2+\tau_e(t_2,w)$. Salir más tarde nunca hace que llegues antes. El simulador debe construirse de forma que esto se cumpla; si no, la formulación pierde validez y aparecen "atajos temporales" espurios.

### 3.2 Conjuntos e índices

- $\mathcal{P}$: conjunto de plataformas conectadas.
- $\mathcal{O}$: conjunto de pedidos ofrecidos durante el turno, $i \in \mathcal{O}$.
- $P = \{o_i : i \in \mathcal{O}\}$ nodos de recolección; $D = \{d_i : i \in \mathcal{O}\}$ nodos de entrega.
- $N = \{0\} \cup P \cup D \cup \{0'\}$, donde $0$ es el origen del repartidor y $0'$ el fin de turno.
- $\mathcal{O}^{\text{cal}} \subseteq \mathcal{O}$: pedidos perecederos (comida caliente).
- $H$: duración del turno; el repartidor trabaja en $[0,H]$.

### 3.3 Parámetros

| Símbolo | Significado |
|---|---|
| $a_i$ | instante en que la oferta $i$ aparece |
| $f_i$ | tarifa ofrecida por la plataforma |
| $\tilde{g}_i$ | propina esperada, $\mathbb{E}[g_i \mid d_i]$ |
| $r_i$ | instante en que el producto está listo |
| $\ell_i$ | fecha límite prometida de entrega |
| $\theta_i$ | tolerancia máxima en tránsito (frescura), $i\in\mathcal{O}^{\text{cal}}$ |
| $\mu_i^{P}, \mu_i^{D}$ | tiempo de servicio en recolección y entrega (estacionarse, esperar, entregar) |
| $\kappa_i$ | volumen ocupado por el pedido |
| $Q$ | capacidad del vehículo (mochila/caja) |
| $c_\kappa$ | costo por km: combustible + mantenimiento + depreciación |
| $\varepsilon$ | rendimiento del vehículo (km/l) |
| $\rho_{\text{comb}}$ | precio del combustible ($/l) |
| $c_\tau$ | costo de oportunidad del tiempo ($/min) |
| $\psi_i$ | penalización por unidad de tiempo de retraso sobre $\ell_i$ |
| $\Psi_p$ | penalización por rechazo/cancelación en la plataforma $p$ (efecto reputacional) |

El costo por kilómetro se descompone así:

$$
c_\kappa(t,w) \;=\; \frac{\rho_{\text{comb}}}{\varepsilon\big(\bar v(t,w)\big)} \;+\; c_{\text{mant}} \;+\; c_{\text{dep}}
$$

donde $\varepsilon(\bar v)$ es el rendimiento **en función de la velocidad promedio**: el tráfico no sólo te cuesta tiempo, te cuesta combustible. Una parametrización razonable es una curva unimodal con máximo alrededor de 45–60 km/h, de modo que el arrastre en tráfico detenido y la velocidad alta en periférico ambos penalizan. Este es el término que hace que la "capa de mapa de costos" tenga contenido real y no sea sólo distancia.

### 3.4 Variables de decisión

$$
\begin{aligned}
y_i &\in \{0,1\} && \text{1 si se acepta el pedido } i\\
x_{mn} &\in \{0,1\} && \text{1 si el repartidor viaja directo del nodo } m \text{ al nodo } n,\; (m,n)\in N^2\\
T_n &\ge 0 && \text{instante de llegada al nodo } n\\
S_n &\ge 0 && \text{instante de inicio de servicio en } n\\
u_n &\ge 0 && \text{carga a bordo tras servir } n\\
z_i &\ge 0 && \text{retraso de entrega, } z_i = (T_{d_i}-\ell_i)^{+}
\end{aligned}
$$

### 3.5 Restricciones

**(C1) Visita condicionada a la aceptación.** Un nodo se visita si y sólo si su pedido fue aceptado:

$$
\sum_{n \in N} x_{o_i n} = y_i,\qquad \sum_{n \in N} x_{d_i n} = y_i \qquad \forall i \in \mathcal{O}
$$

**(C2) Conservación de flujo.** Entra lo que sale, en cada nodo intermedio:

$$
\sum_{m\in N} x_{mn} \;=\; \sum_{m\in N} x_{nm} \qquad \forall n \in P\cup D
$$

**(C3) Ruta única con extremos.** Un solo camino hamiltoniano sobre los nodos activos:

$$
\sum_{n\in N} x_{0n} = 1, \qquad \sum_{m\in N} x_{m0'} = 1, \qquad x_{nn}=0
$$

**(C4) Disponibilidad de la oferta.** No se puede recoger antes de que la oferta exista:

$$
S_{o_i} \;\ge\; a_i \, y_i
$$

**(C5) Consistencia temporal en los arcos** (linealización de Miller–Tucker–Zemlin dependiente del tiempo, con $M$ grande):

$$
T_n \;\ge\; S_m + \mu_m + \tau\big(m,n,S_m+\mu_m, w\big) \;-\; M\,(1 - x_{mn}) \qquad \forall (m,n)
$$

**(C6) Espera por preparación.** El servicio de recolección no arranca antes de que el producto esté listo. Esta es la restricción que **genera la holgura** $\sigma_i$ del §1.3:

$$
S_{o_i} \;\ge\; \max\{T_{o_i},\, r_i\} \quad\Longrightarrow\quad S_{o_i}\ge T_{o_i},\qquad S_{o_i} \ge r_i\,y_i
$$

**(C7) Precedencia recolección→entrega.**

$$
T_{d_i} \;\ge\; S_{o_i} + \mu_i^{P} + \tau\big(o_i, d_i, S_{o_i}+\mu_i^{P}, w\big)\cdot y_i
$$

y, estructuralmente, $o_i$ y $d_i$ deben caer en el mismo recorrido con $o_i$ antes que $d_i$ (se impone con las variables MTZ de posición $\phi_n$: $\phi_{o_i} + 1 \le \phi_{d_i} + M(1-y_i)$).

**(C8) Capacidad.**

$$
u_n = u_m + \kappa_n \quad\text{si } n \in P,\qquad u_n = u_m - \kappa_n \quad\text{si } n \in D,\qquad 0 \le u_n \le Q
$$

**(C9) Frescura — la restricción central del problema.** Para todo pedido perecedero, el tiempo total en posesión del repartidor está acotado:

$$
\boxed{\;T_{d_i} - \big(S_{o_i}+\mu_i^{P}\big) \;\le\; \theta_i \;+\; M\,(1-y_i) \qquad \forall i \in \mathcal{O}^{\text{cal}} \;}
$$

Esta desigualdad es la que impide el agrupamiento ilimitado. No es una ventana de tiempo ordinaria: acopla el instante de recolección con el de entrega del *mismo* pedido, y por tanto **cada pedido caliente que se recoge reduce el presupuesto de desvío disponible para todos los demás**. Es también la formalización exacta de la prioridad que el planteamiento original describía: "si recoges comida primero, no puedes acumular $n$ paquetes que te tomen más de lo que la comida tarda en enfriarse".

**(C10) Retraso medible (fecha límite suave).**

$$
z_i \;\ge\; T_{d_i} - \ell_i, \qquad z_i \ge 0
$$

Se modela **suave** y no dura, deliberadamente: en la práctica entregar 3 minutos tarde es preferible a rechazar el pedido, y un modelo con fecha límite dura vuelve infactible casi todo agrupamiento interesante. La dureza se recupera haciendo $\psi_i$ grande.

**(C11) Compatibilidad multiplataforma.** Algunas plataformas prohíben contractualmente tener dos pedidos activos, o el dispositivo sólo permite un estado "en viaje" a la vez. Se codifica como un conjunto de pares incompatibles $\mathcal{I}$:

$$
y_i + y_j \le 1 \qquad \forall (i,j)\in\mathcal{I} \text{ con solapamiento temporal}
$$

Es una restricción que conviene tener parametrizada y **desactivable**, porque es política de negocio y cambia; el modelo debe poder cuantificar cuánta ganancia cuesta esa política.

**(C12) Horizonte del turno.** $T_{0'} \le H$.

### 3.6 Función objetivo

$$
\max \quad
\underbrace{\sum_{i\in\mathcal{O}} \big(f_i + \tilde g_i\big)\, y_i}_{\text{ingreso}}
\;-\;\underbrace{\sum_{(m,n)} c_\kappa \,\delta(m,n,\cdot)\, x_{mn}}_{\text{costo de distancia}}
\;-\;\underbrace{c_\tau \big(T_{0'} - T_0\big)}_{\text{costo del tiempo}}
\;-\;\underbrace{\sum_{i} \psi_i z_i}_{\text{retrasos}}
\;-\;\underbrace{\sum_{i} \Psi_{p(i)}(1-y_i)}_{\text{reputación}}
$$

### 3.7 Lo que este modelo no es

Tres advertencias que conviene escribir en el documento final del hackathón para no sobrevender:

1. **Es no lineal disfrazado de lineal.** $\tau(\cdot,S_m+\mu_m,\cdot)$ depende de una variable de decisión. La linealización estándar es discretizar el horizonte en intervalos $[t_k,t_{k+1})$ y agregar variables binarias $x_{mn}^{k}$ (el arco se recorre en el intervalo $k$), con matrices de tiempo de viaje precalculadas por intervalo. Esto multiplica el número de binarias por $|K|$; con $|K|=12$ intervalos de 15 min y 30 pedidos el modelo ya es pesado pero resoluble con Gurobi/CBC en minutos para instancias de referencia.
2. **La ganancia óptima de este modelo es inalcanzable en línea.** La diferencia entre el óptimo clarividente y el óptimo en línea es el **precio de la información**, y medirlo es un resultado valioso en sí mismo (es la parte más publicable del trabajo).
3. **La escala de uso es de decenas de pedidos, no de miles.** Se usa para instancias de *benchmark* de 1 turno, no en producción.

### 3.8 Complejidad

El caso $|\mathcal{O}^{\text{cal}}|=0$, $\psi=0$, $\Psi=0$, tiempos constantes y $y_i$ libres se reduce al **Single-Vehicle Profitable Pickup and Delivery Problem with Time Windows**, que contiene al TSP con ventanas de tiempo como caso particular y es por tanto **NP-difícil en sentido fuerte**. Añadir (C9) no lo facilita. La versión dinámica, al ser un problema de control estocástico sobre este espacio, es al menos igual de difícil y no admite solución exacta: **de ahí la motivación del agente aprendido**, no al revés. Vale la pena decirlo en ese orden en la presentación.

---

## 4. Capa 2 — Modelo dinámico: SMDP de recompensa promedio

Esta es la formulación que describe el problema real y la que el agente resuelve.

### 4.1 Por qué un SMDP y no un MDP

Las decisiones no ocurren en pasos de reloj uniformes, sino **cuando pasa algo**: llega una oferta, llegas a un nodo, el producto queda listo, una oferta expira. Y las acciones consumen **cantidades distintas de tiempo real**. Un MDP de paso fijo o (a) desperdicia cómputo simulando miles de pasos sin decisión, o (b) distorsiona el objetivo porque descontar por paso no equivale a descontar por minuto. El marco correcto es un **Proceso de Decisión Semi-Markoviano** (SMDP) dirigido por eventos.

### 4.2 Épocas de decisión

$$
t_k \in \mathcal{T} = \{\text{llegada de oferta}\} \cup \{\text{llegada a nodo}\} \cup \{\text{producto listo}\} \cup \{\text{expiración de oferta}\}
$$

### 4.3 Estado

$$
S_k = \Big(\, t_k,\; \underbrace{(v_k,\, \mathbf{u}_k)}_{\text{repartidor}},\; \underbrace{\mathcal{A}_k}_{\text{plan activo}},\; \underbrace{\mathcal{F}_k}_{\text{ofertas pendientes}},\; \underbrace{W_k}_{\text{clima}},\; \underbrace{\Theta_k}_{\text{tráfico}},\; \underbrace{\rho_k}_{\substack{\text{tasa de ganancia}\\\text{acumulada}}} \,\Big)
$$

- $v_k$: nodo o posición interpolada en arco; $\mathbf{u}_k$ carga a bordo.
- $\mathcal{A}_k$: **plan activo** = lista ordenada de paradas comprometidas, cada una con su tipo (recoger/entregar), su pedido, su estado (pendiente/recogido), su $\hat r_i$ (estimación actualizada del tiempo de listo) y su $\ell_i$, $\theta_i$ restantes.
- $\mathcal{F}_k$: ofertas visibles no decididas, cada una con el vector del contrato de datos (§1.2) y un **tiempo de expiración** (las apps dan segundos para aceptar — este detalle es lo que hace el problema genuinamente difícil).
- $\rho_k$: tasa de ganancia realizada hasta $t_k$. Se incluye en el estado porque la política óptima depende del costo de oportunidad actual (§4.7).

**Observabilidad parcial.** $r_i$ y el tráfico futuro no son observables. El estado es en rigor un POMDP; se aborda con (a) creencias explícitas $\hat r_i \sim \text{LogNormal}$ actualizadas bayesianamente al llegar al comercio, y (b) una ventana de historia reciente como entrada a la red. No se recomienda meter una LSTM en un hackathón: la creencia explícita más un *frame stacking* corto cubre casi todo el beneficio con una fracción del riesgo.

### 4.4 Acción

Espacio de acción **jerárquico**, que es lo que hace tratable el problema:

$$
A_k = \big(\, \underbrace{\mathbf{b}_k}_{\text{aceptar}},\; \underbrace{\pi_k}_{\text{secuenciar}} \,\big),
\qquad
\mathbf{b}_k \in \{0,1\}^{|\mathcal{F}_k|},\quad
\pi_k \in \Pi\big(\mathcal{A}_k \cup \{\text{nuevos}\}\big)
$$

En la práctica se descompone en dos decisiones que ocurren en niveles distintos:

- **Nivel alto (aprendido):** para cada oferta pendiente, aceptar, rechazar o diferir.
- **Nivel bajo (calculado):** dado el conjunto comprometido, la secuencia óptima de visitas. Con $|\mathcal{A}_k| \le 6$ pedidos ($\le 12$ paradas), el número de secuencias factibles tras aplicar precedencia y frescura es de cientos, no de millones: **se enumera o se resuelve con programación dinámica de Held–Karp** en microsegundos. No hay razón para aprender esto.

**Desacoplamiento entre Navegación y Decisión (Actualización v2.0):**
Es fundamental clarificar el desacoplamiento entre la capa de navegación y la capa de decisión:
1. **Navegación (en vivo sobre red vial real):** Ya no opera "en tiempo de construcción" ni mediante rutas sintéticas fijas. El motor A* corre en tiempo real en el backend expuesto a través de `POST /ruta` sobre la red vial real de OpenStreetMap (OSMnx, 14,690 nodos de Monterrey), resolviendo trayectos multienlace en ~71 ms (4 tramos) con caché LRU de ~11 ms. La geometría producida se proyecta y recorta en vivo en el frontend anclada al repartidor.
2. **Decisión (geometría del entorno de simulación):** La capa de decisión (evaluación de inserción en `POST /decidir`) continúa utilizando la geometría y función de transición del entorno de simulación (distancias analíticas L0/L1). La integración de la matriz de costos y tiempos reales de la red vial a la capa de decisión queda como paso futuro. **Advertencia metodológica:** incorporar la matriz de costos real a la decisión alterará la función de transición que optimizó el agente y REQUIERE re-evaluar los 30 escenarios congelados (`scenarios/test_30.pkl`) antes de cantar victoria o comparar formalmente contra las líneas base.

**Máscara de factibilidad.** Antes de exponer acciones a la política se calcula $\mathcal{M}(S_k) \subseteq A$, el conjunto de acciones que admiten **al menos una** secuencia factible respecto de (C7)–(C9), (C11)–(C12). El chequeo es una prueba de factibilidad de inserción: aceptar $j$ es factible si existe posición de inserción del par $(o_j,d_j)$ en $\mathcal{A}_k$ que no viole frescura ni capacidad. Enmascarar (en vez de penalizar) acciones inválidas es la diferencia entre un agente que aprende y uno que no: el gradiente de la acción enmascarada es exactamente cero, sin sesgo, a diferencia de la penalización, que contamina la estimación de ventaja (Huang & Ontañón).

### 4.5 Transición

Dado $(S_k, A_k)$, el simulador avanza hasta el siguiente evento y muestrea:

$$
\begin{aligned}
\text{tiempo de viaje:}\quad & \tilde\tau = \tau(\cdot)\cdot \xi, \quad \xi \sim \text{LogNormal}(-\tfrac{\varsigma^2}{2}, \varsigma^2) \;\; (\mathbb{E}[\xi]=1)\\
\text{listo:}\quad & R_i \sim \text{LogNormal}(\mu_{r},\varsigma_r^2)\ \text{condicionado al comercio}\\
\text{ofertas:}\quad & \text{proceso de Poisson no homogéneo de intensidad } \Lambda_p(t, \text{zona}, W_t)\\
\text{clima:}\quad & W_{t} \ \text{cadena de Markov en } \{\text{seco, lluvia ligera, tormenta}\}\\
\text{incidentes:}\quad & \text{Poisson con intensidad creciente en lluvia; cierran arcos por } \text{Exp}(\cdot)
\end{aligned}
$$

El uso de LogNormal con media unitaria para el multiplicador de viaje es importante: el ruido de tiempo de viaje es **multiplicativo y asimétrico a la derecha** (puedes tardar el doble, nunca la mitad), y un ruido gaussiano aditivo da un agente sistemáticamente optimista.

### 4.6 Recompensa

Recompensa por transición, atribuida en el instante en que ocurre el flujo de dinero:

$$
r(S_k,A_k) \;=\; \sum_{i \in \text{entregados en } [t_k,t_{k+1})} \big(f_i + g_i\big)
\;-\; c_\kappa\,\Delta\delta_k
\;-\; \sum_i \psi_i\,\big(T_{d_i}-\ell_i\big)^{+}
\;-\; \Phi_k
$$

donde $\Delta\delta_k$ es la distancia recorrida en el intervalo y $\Phi_k$ agrupa penalizaciones de reputación/cancelación. El tiempo transcurrido es $\Delta t_k = t_{k+1}-t_k$.

### 4.7 Criterio de optimalidad: tasa de ganancia, no ganancia descontada

**Esta es la decisión de modelado más consecuente del documento.** El repartidor no quiere maximizar pesos por turno; quiere maximizar **pesos por hora** (si no, la política degenera a "acepta todo lo que sea rentable marginalmente", incluidos viajes que ocupan 50 minutos por 40 pesos). Se adopta el criterio de **recompensa promedio**:

$$
\rho^{\pi} \;=\; \lim_{K\to\infty} \frac{\mathbb{E}^{\pi}\!\big[\sum_{k=0}^{K} r(S_k,A_k)\big]}{\mathbb{E}^{\pi}\!\big[\sum_{k=0}^{K} \Delta t_k\big]}, \qquad \pi^{*} = \arg\max_\pi \rho^{\pi}
$$

La ecuación de optimalidad de Bellman correspondiente (SMDP, recompensa promedio) es

$$
h^{*}(S) \;=\; \max_{A \in \mathcal{M}(S)} \Big\{\, r(S,A) \;-\; \rho^{*}\,\mathbb{E}[\Delta t \mid S,A] \;+\; \mathbb{E}\big[h^{*}(S')\mid S,A\big] \Big\}
$$

con $h^{*}$ la función de sesgo (*bias*) y $\rho^{*}$ la tasa óptima. La interpretación es directa y muy útil para el producto: **el término $\rho^{*}\Delta t$ es el precio del tiempo**. Cada minuto que el agente gasta le cuesta $\rho^*$ pesos de oportunidad.

### 4.8 Consecuencia analítica: la regla de aceptación por umbral

De la ecuación anterior se obtiene el criterio que el sistema debería mostrar al repartidor. Sea $\mathcal{A}$ el plan activo y $\mathcal{A}\oplus j$ el mejor plan factible que incorpora la oferta $j$. Definimos

$$
\Delta f_j = f_j + \tilde g_j, \qquad
\Delta t_j = t(\mathcal{A}\oplus j) - t(\mathcal{A}), \qquad
\Delta \delta_j = \delta(\mathcal{A}\oplus j) - \delta(\mathcal{A})
$$

Entonces **aceptar $j$ conviene si y sólo si su tasa marginal de ganancia supera la tasa actual**:

$$
\boxed{\;
\frac{\Delta f_j - c_\kappa\,\Delta\delta_j - \Delta\Psi_j}{\Delta t_j} \;>\; \rho^{*}
\;}
$$

Tres razones por las que este resultado vale su peso en oro en un hackathón:

1. **Es un algoritmo listo para usar.** Con $\hat\rho$ estimado del historial del repartidor (o de los últimos 90 minutos) ya se tiene una política defendible, explicable, sin entrenar nada. Es el baseline B2 de §6.1 y es difícil de batir por margen amplio.
2. **Es interpretable para el usuario final.** La app puede decir literalmente: *"este pedido te paga a razón de $128/h; tu promedio hoy es $141/h → rechazar"*. Ningún modelo profundo comunica así.
3. **Explica el valor del agrupamiento en una línea.** Cuando $j$ cabe en la holgura $\sigma_i$, el denominador $\Delta t_j$ se vuelve pequeño y la fracción explota. El *bundling* no es más que la explotación sistemática de ofertas con $\Delta t_j \approx 0$.

Lo que la regla de umbral **no** captura, y que es justamente el espacio donde el RL debe ganar:

- **Valor de posición.** Aceptar un pedido que te deja en una zona de alta densidad de ofertas vale más que su tasa marginal. La regla es miope en el espacio.
- **Valor de opción / espera.** A veces conviene rechazar un pedido decente y esperar 4 minutos porque la distribución de ofertas en ese punto y hora es favorable. La regla nunca espera voluntariamente.
- **Riesgo de cascada.** Un agrupamiento con $\Delta t_j$ pequeño en valor esperado puede tener varianza alta: si el comercio se retrasa, todos los pedidos del paquete caen tarde a la vez. La regla optimiza la media e ignora la correlación de riesgos.

Formalmente, estos tres huecos son exactamente el término $\mathbb{E}[h^{*}(S')]$ de la ecuación de Bellman, que la regla de umbral aproxima por cero. **El objetivo científico del proyecto se puede enunciar así: aprender $h^{*}$.** Ese es un enunciado de tesis mucho más fuerte que "usamos RL para optimizar rutas".

---
## 5. Capa 3a — El sandbox de aprendizaje

### 5.1 Principio de diseño: fidelidad escalonada

El error más común en proyectos así es construir primero el simulador realista y descubrir a 6 horas del cierre que el agente no aprende nada y no hay forma de saber si la culpa es del simulador, de la recompensa o del algoritmo. La disciplina es construir **cuatro niveles de fidelidad**, cada uno con su propio criterio de éxito, y **no avanzar de nivel hasta que un agente supere al baseline en el nivel actual**.

| Nivel | Geometría | Tiempo de viaje | Órdenes | Clima/incidentes | Propósito | Costo |
|---|---|---|---|---|---|---|
| **L0** | rejilla $20\times20$, Manhattan | velocidad constante | Poisson homogéneo, sin preparación | no | depurar código, verificar que el RL aprende *algo* | segundos/episodio |
| **L1** | rejilla + zonas de densidad | multiplicador por zona/hora | Poisson no homogéneo + $R_i$ aleatorio | no | validar que emerge el *bundling* | segundos |
| **L2** | red vial real de MTY (OSMnx) | matriz precalculada por franja horaria | calibrado a horas pico reales | clima markoviano | resultado presentable | ~1 s/episodio |
| **L3** | red vial + microsimulación | SUMO / tiempos dependientes del tiempo | + incidentes, cierres | completo | validación final, no entrenamiento | minutos |

**L0 y L1 son donde se entrena.** L2 es donde se evalúa y se hace la demo. L3 es opcional y probablemente no se alcanza en un hackathón — y está bien: se menciona como trabajo futuro en lugar de intentarlo y fallar.

> **Criterio de avance de nivel.** No pasar a L$(n{+}1)$ hasta que el agente entrenado en L$n$ supere al baseline de umbral (§6.1, B2) por al menos 5 % en tasa de ganancia, con intervalos de confianza no solapados sobre ≥200 episodios de evaluación con semillas fijas.

### 5.2 Capa 0 — Red vial

Fuente: OpenStreetMap vía **OSMnx** (Boeing, 2017), grafo de tipo `drive` para el área metropolitana (Monterrey, San Pedro, San Nicolás, Guadalupe, Apodaca, Escobedo, Santa Catarina, Juárez). Orden de magnitud esperado: $10^4$–$10^5$ nodos.

```python
import osmnx as ox
G = ox.graph_from_place(
    ["Monterrey, Nuevo León, Mexico", "San Pedro Garza García, Nuevo León, Mexico",
     "San Nicolás de los Garza, Nuevo León, Mexico", "Guadalupe, Nuevo León, Mexico",
     "Apodaca, Nuevo León, Mexico", "General Escobedo, Nuevo León, Mexico",
     "Santa Catarina, Nuevo León, Mexico"],
    network_type="drive", simplify=True,
)
G = ox.add_edge_speeds(G)       # maxspeed de OSM, con imputación por tipo de vía
G = ox.add_edge_travel_times(G) # tiempo de flujo libre
```

**Decisión crítica de rendimiento:** *no* correr Dijkstra dentro del ciclo de entrenamiento. Se define un conjunto de $M \approx 1500$–$3000$ **nodos de interés** (comercios, centroides de colonia, puntos de entrega muestreados de la distribución de demanda) y se precalcula la **matriz de tiempos y distancias** $M\times M$ por franja horaria (p. ej. 8 franjas). Con $M=2000$ y 8 franjas son ~$3.2\times10^{7}$ entradas en `float32` ≈ 128 MB: cabe en RAM y convierte cada consulta en un acceso a arreglo. Esto es la diferencia entre 1 000 y 1 000 000 de pasos de entrenamiento por hora.

Precalcular con Dijkstra desde cada nodo de interés (`scipy.sparse.csgraph.dijkstra` sobre la matriz de adyacencia, paralelizado) toma minutos, una sola vez, y se cachea en disco.

### 5.3 Capa de tráfico

Tres mecanismos, en orden de importancia:

1. **Multiplicador espacio-temporal de congestión** $\gamma_{\text{traf}}(\text{zona}, t)$: una superficie calibrada a mano con perfiles de hora pico (07:00–09:30, 13:00–15:00, 18:00–20:30) y corredores conocidos (Constitución, Morones Prieto, Gonzalitos, Lázaro Cárdenas, Miguel Alemán). Se aplica multiplicativamente a la matriz de tiempos. **Esto es el 80 % del realismo por el 5 % del esfuerzo.**
2. **Control de intersecciones:** penalización aditiva $\pi_e$ por nodo según su grado y tipo — semáforo ($\mathbb{E}$ ≈ media del ciclo/2), rotonda, giro a la derecha continuo (≈ 0). Se incorpora al precálculo, no en tiempo de ejecución.
3. **Incidentes:** proceso de Poisson que multiplica por $\in[2,8]$ el tiempo de un corredor durante $\text{Exp}(\bar d)$ minutos, o lo cierra. Invalida entradas de la matriz temporalmente → requiere un camino de respaldo (tiempo de la matriz × factor de desvío) para no recalcular caminos en línea.

> **Honestidad sobre la calibración.** Sin datos reales de velocidad (una API de tráfico o datos de GPS), estos perfiles son *plausibles*, no *calibrados*. Debe decirse así en el documento. La forma correcta de presentarlo es: el simulador está **parametrizado** de modo que, si aparecen datos reales, se ajustan los parámetros sin rehacer el modelo, y se reporta un análisis de sensibilidad del desempeño del agente respecto de esos parámetros.

### 5.4 Capa climática

Cadena de Markov de tiempo discreto (paso de 15 min) sobre $\{$seco, lluvia ligera, lluvia fuerte/tormenta$\}$, con matriz de transición estacional (en Monterrey esto importa sobre todo entre junio y septiembre). Efectos acoplados:

$$
\gamma_{w}: \; 1.0 \;/\; 1.15 \;/\; 1.45, \qquad
\lambda_{\text{inc}}(w) = \lambda_0\cdot\{1, 2, 5\}, \qquad
\Lambda_p(w) = \Lambda_0\cdot\{1, 1.3, 1.6\}
$$

El último factor es el que hace el ambiente interesante: **la lluvia aumenta la demanda a la vez que aumenta el costo de servirla**, y algunas plataformas suben tarifas. Es el escenario donde una política aprendida puede diferenciarse claramente de una heurística fija, y por lo tanto es el escenario que conviene usar en la demo.

Además: cierre de vialidades por encharcamiento en puntos conocidos de la ciudad (pasos a desnivel, cruces de arroyos) — modelado como un conjunto de arcos con probabilidad de cierre condicionada a lluvia acumulada.

### 5.5 Capa de costos

$$
\text{costo}(\text{arco}, t, w) = \underbrace{\frac{\lambda_e\,\rho_{\text{comb}}}{\varepsilon(\bar v_e)}}_{\text{combustible}} + \underbrace{\lambda_e\, c_{\text{mant}}}_{\text{desgaste}} + \underbrace{\tau_e \, c_\tau}_{\text{tiempo}} + \underbrace{\lambda_e\,c_{\text{riesgo}}(w)}_{\text{riesgo}}
$$

Parametrización de $\varepsilon(\bar v)$ sugerida (moto o auto compacto):

$$
\varepsilon(\bar v) \;=\; \varepsilon_{\max}\exp\!\Big(-\tfrac{(\bar v - v^{\star})^2}{2\varsigma_v^2}\Big), \quad v^{\star}\approx 50 \text{ km/h}
$$

Con esto, un trayecto en tráfico detenido a 12 km/h consume del orden de 2–3 veces más combustible por km que el mismo trayecto a 50 km/h, lo que es cualitativamente correcto y hace que el agente aprenda a evitar corredores congestionados **incluso cuando el tiempo no es el cuello de botella**. Es un resultado que se ve bonito en la demo y que un modelo de costo puramente por distancia jamás produce.

### 5.6 Generador de órdenes

El generador es la pieza que determina si el *bundling* es posible o no; si está mal hecho, no hay nada que aprender.

$$
\text{Ofertas de la plataforma } p: \quad N_p([t,t+dt)) \sim \text{Poisson}\big(\Lambda_p(t,\mathbf{x},W_t)\,dt\big)
$$

con $\Lambda_p$ factorizada como intensidad temporal × densidad espacial de comercios × factor climático. Los comercios se muestrean de los POIs reales de OSM (`amenity=restaurant|fast_food|cafe`, `shop=convenience|supermarket`), lo que da automáticamente la **agrupación geográfica** de la oferta (plazas comerciales, corredores gastronómicos) — y la agrupación geográfica es *precisamente* el fenómeno que hace que el *bundling* sea rentable. Muestrear comercios uniformemente en el plano destruiría el problema.

Tiempo de preparación, por tipo de comercio:

$$
R_i = a_i + \text{LogNormal}(\mu_{\text{tipo}}, \varsigma^2_{\text{tipo}}), \qquad
\mathbb{E}[R_i - a_i] \in [6, 25]\ \text{min}
$$

Tarifa, calibrada a la realidad mexicana y correlacionada con distancia (con ruido, porque las apps no son transparentes):

$$
f_i = \big(f_{\text{base},p} + \beta_p\,\hat\delta_i\big)\cdot\eta_i, \qquad \eta_i\sim\text{LogNormal}(0,\varsigma_f^2)
$$

Y el detalle que más impacto tiene en el realismo: **las ofertas expiran**. Cada oferta tiene una ventana de aceptación $[a_i, a_i+\omega]$ con $\omega \in [20, 60]$ s. Sin expiración, el agente puede diferir indefinidamente y el problema se vuelve trivialmente más fácil (y el agente aprende a ser un acumulador irreal).

**Prueba de sanidad obligatoria del generador.** Antes de entrenar, verificar que existe oportunidad de agrupamiento: correr el baseline "aceptar-uno-a-la-vez" contra el oráculo MILP en instancias pequeñas. Si la brecha es menor al ~10 %, el generador no produce solapamiento suficiente y hay que subir la intensidad o concentrar más la geografía. **Si no hay brecha, no hay producto.** Esta verificación es de las primeras cosas que hay que hacer, no de las últimas.

### 5.7 Espacio de observación

Vector de tamaño fijo (indispensable para entrenar rápido), con tres bloques:

**a) Estado propio (≈ 14 dims):** posición normalizada (x, y), velocidad, carga/$Q$, minutos transcurridos del turno, minutos restantes, $\hat\rho$ actual, ganancia acumulada, km acumulados, clima *one-hot* (3), índice de congestión local.

**b) Plan activo (hasta $K_A=6$ pedidos × 10 dims, con máscara de relleno):** por pedido — desplazamiento relativo a recolección, desplazamiento relativo a entrega, tarifa normalizada, holgura de frescura restante $\theta_i - (\text{tiempo en posesión})$, holgura de fecha límite $\ell_i - t$, $\hat r_i - t$, estado (recogido / pendiente), plataforma *one-hot* comprimida, indicador de riesgo de retraso.

**c) Ofertas pendientes (hasta $K_F=8$ × 12 dims):** por oferta — desplazamientos relativos a $o_j$ y $d_j$, tarifa, tarifa/km, tarifa/min estimada, $\hat r_j$, $\ell_j$, **desvío incremental $\Delta t_j$ y $\Delta\delta_j$ calculados por el módulo de inserción**, factibilidad (máscara), segundos hasta expirar.

> **Las características derivadas ($\Delta t_j$, $\Delta\delta_j$, tarifa/min marginal) son la decisión de ingeniería con mayor retorno de todo el proyecto.** Le están dando a la red, ya masticado, el numerador y el denominador de la regla de umbral del §4.8. Sin ellas la red tendría que aprender geometría de rutas desde coordenadas crudas, lo que cuesta órdenes de magnitud más muestras. Con ellas, la red sólo tiene que aprender la *corrección de valor futuro* $h^{*}$, que es el problema realmente interesante. Esta es la forma disciplinada de inyectar conocimiento del dominio sin resolver el problema a mano.

**d) Contexto espacial (opcional, 1 canal de rejilla 16×16):** densidad histórica de ofertas alrededor de la posición actual, para que el agente pueda aprender valor de posición. Si se incluye, requiere un encoder convolucional pequeño; evaluar si el beneficio justifica el costo antes de agregarlo.

### 5.8 Espacio de acción y enmascaramiento

Discreto, de tamaño $K_F + 2$:

$$
\mathcal{A} = \{\,\underbrace{\text{aceptar oferta } 1..K_F}_{K_F},\; \underbrace{\text{rechazar/ignorar todas}}_{1},\; \underbrace{\text{reposicionarse}}_{1}\,\}
$$

Tras cada aceptación, el módulo de secuenciación (§6.5) recalcula el plan óptimo y el episodio continúa. La acción "reposicionarse" mueve al repartidor hacia el centroide de la zona de mayor densidad esperada — es la que permite al agente **esperar productivamente**, capacidad que la regla de umbral no tiene.

Máscara $m \in \{0,1\}^{K_F+2}$: se anula toda oferta inexistente, expirada, o cuya inserción es infactible bajo (C7)–(C9). Implementación en la política: sumar $-10^{8}$ a los *logits* enmascarados antes del *softmax*.

### 5.9 Función de recompensa y *shaping*

**Recompensa base (la que corresponde al objetivo real):**

$$
r_k = \Big(\textstyle\sum_{i \text{ entregado}} (f_i+g_i)\Big) - c_\kappa \Delta\delta_k - \sum_i \psi_i (T_{d_i}-\ell_i)^{+} - \hat\rho\,\Delta t_k
$$

El último término, $-\hat\rho\,\Delta t_k$, es la implementación práctica del criterio de recompensa promedio dentro de un algoritmo de recompensa descontada: se **penaliza explícitamente el paso del tiempo** al precio de oportunidad estimado. Es lo que convierte un agente maximizador de pesos en un maximizador de pesos/hora. Se puede estimar $\hat\rho$ con una media móvil de la tasa del propio agente durante el entrenamiento (esquema tipo *R-learning*), o fijarlo a un valor de referencia y hacer *annealing*.

**Shaping basado en potencial (seguro, no altera la política óptima).** Por el resultado de Ng, Harada & Russell, cualquier término de la forma $F(S,S') = \gamma\,\Phi(S')-\Phi(S)$ preserva el orden de las políticas óptimas. Potenciales útiles:

$$
\Phi(S) = w_1\!\!\sum_{i\in\mathcal{A}}\!\big(f_i\cdot\text{prob. de entrega a tiempo}\big) \;-\; w_2\!\!\sum_{i\in\mathcal{A}}\!\big(\text{riesgo de frescura}\big)
$$

Esto le da señal densa al agente sobre "tienes valor a bordo y lo estás protegiendo", en vez de esperar la recompensa dispersa de la entrega. **Sólo usar shaping con esta forma**; cualquier bonificación arbitraria por "recoger" o "moverse" produce agentes que explotan la recompensa (p. ej. recoger sin entregar, o dar vueltas).

**Antipatrones de recompensa que hay que vigilar explícitamente:**

| Antipatrón | Síntoma observable | Mitigación |
|---|---|---|
| Bonificación por aceptar | acepta todo, entrega tarde | quitarla; que el valor venga sólo de entregar |
| Penalización de retraso demasiado baja | ignora fechas límite | subir $\psi$ hasta que la tasa de puntualidad ≥ 90 % |
| Penalización de retraso demasiado alta | rechaza casi todo, agente cobarde | bajar $\psi$; medir tasa de aceptación |
| Sin costo de tiempo | acepta pedidos de tasa horaria pésima | término $-\hat\rho\Delta t$ |
| Bonificación por distancia recorrida | vagabundea | nunca premiar movimiento |

### 5.10 Métricas y protocolo de evaluación

**Métrica primaria:** tasa de ganancia neta $\rho = \dfrac{\text{ingreso} - \text{costos}}{\text{horas conectadas}}$ (pesos/hora).

**Métricas secundarias, todas necesarias para que el resultado sea creíble:**

- Brecha respecto del oráculo MILP: $\text{gap} = 1 - \rho^{\pi}/\rho^{\text{MILP}}$.
- Pedidos entregados por hora; tasa de puntualidad (% entregados antes de $\ell_i$).
- Violaciones de frescura (debe ser 0 si el enmascaramiento funciona — es una prueba de corrección, no una métrica de desempeño).
- Factor de agrupamiento: pedidos promedio simultáneamente a bordo.
- Km por pedido y km vacíos (sin carga) — es la métrica que mejor comunica el ahorro.
- Utilización: % de tiempo en tránsito con carga vs esperando vs vacío.

**Protocolo.** Semillas fijas y separadas para entrenamiento / validación / prueba. Un conjunto de **50 escenarios de prueba congelados** desde el inicio (turnos completos con su realización de clima y órdenes), nunca usados para entrenar ni para elegir hiperparámetros. Reportar media ± IC del 95 % vía *bootstrap* sobre esos 50, y **comparar contra baselines sobre los mismos escenarios** (comparación pareada, que reduce muchísimo la varianza del contraste). Un resultado sin baseline sobre escenarios idénticos no es un resultado.

---
## 6. Capa 3b — Familias de agentes

### 6.1 Baselines (obligatorios, no opcionales)

Sin baselines fuertes, un agente de RL no se puede evaluar. Y hay una razón incómoda para insistir: **en ruteo dinámico las heurísticas bien diseñadas frecuentemente empatan o superan al RL**, y la literatura reciente (Hildebrandt, Thomas & Ulmer) es explícita al respecto. Construir los baselines primero protege el proyecto: si el RL no gana, los baselines *son* el producto y se presenta el RL como análisis comparativo honesto.

| ID | Política | Costo de implementación | Qué mide |
|---|---|---|---|
| **B0** | Aleatoria factible | trivial | piso absoluto |
| **B1** | Aceptar todo lo factible (FIFO) | trivial | comportamiento del repartidor novato; suele ser malo por retrasos |
| **B2** | **Regla de umbral (§4.8)** con $\hat\rho$ móvil + inserción más barata | ~2 h | **el baseline serio**; políticas de umbral son fuertes |
| **B3** | Reoptimización en horizonte rodante: cada época, MILP/CP-SAT sobre las ofertas visibles con horizonte de 30 min | ~5 h | límite de lo alcanzable *sin anticipación* |
| **B4** | Oráculo clarividente (MILP §3, información completa *a posteriori*) | ~6 h | **cota superior**; el denominador de la brecha |

La cadena B1 < B2 < B3 < B4 es la escala de medición de todo el proyecto. B3 es especialmente informativo: la diferencia B4 − B3 es el **valor de la anticipación**, es decir, el techo máximo de lo que un agente aprendido puede aportar sobre reoptimización clásica. Si esa diferencia es pequeña, el RL no tiene espacio y conviene saberlo el día uno, no el día tres.

Herramientas: **Google OR-Tools** (CP-SAT o su solucionador de ruteo) para B3 — permite definir *dimensiones* de tiempo y capacidad, ventanas de tiempo, y penalizaciones por nodos no visitados (*disjunctions*), que es exactamente la estructura selectiva de nuestro problema.

### 6.2 Familia A — Basada en valor: DQN enmascarado

$$
Q_\phi(S, a),\quad a \in \{0,\dots,K_F+1\}, \qquad
\mathcal{L} = \mathbb{E}\Big[\big(r + \gamma^{\Delta t}\max_{a'\in\mathcal{M}(S')} Q_{\phi^-}(S',a') - Q_\phi(S,a)\big)^2\Big]
$$

Nótese $\gamma^{\Delta t}$ y no $\gamma$: el descuento es **por tiempo transcurrido**, que es la adaptación correcta del descuento a un SMDP. Extensiones recomendadas: Double DQN + Dueling + *replay* priorizado; n-step returns con $n=3$.

- **Pros:** eficiente en muestras, sencillo de depurar, el valor $Q$ es directamente interpretable como "pesos esperados si acepto esta oferta" — lo cual es *exactamente* lo que la interfaz de la app quiere mostrar. Esa interpretabilidad es una ventaja de producto, no sólo técnica.
- **Contras:** sensible a hiperparámetros, tendencia a sobreestimar, peor con espacios de acción grandes o variables.
- **Cuándo elegirlo:** si $K_F \le 8$ y se quiere una demo con números explicables al lado de cada oferta.

### 6.3 Familia B — Gradiente de política: PPO enmascarado (recomendado como base)

Arquitectura sugerida:

```
Estado propio (14)  ──► MLP(128)         ─┐
Plan activo (6×10)  ──► Self-Attention   ─┤
                        (d=128, 2 heads)  ├─► concat ─► MLP(256,256) ─┬─► π (K_F+2, enmascarado)
Ofertas (8×12)      ──► Cross-Attention  ─┘                           └─► V (1)
                        (consulta = estado+plan)
```

La atención cruzada entre el estado/plan (consulta) y las ofertas (claves/valores) es la elección arquitectónica adecuada: es **invariante a permutaciones** en el conjunto de ofertas (el orden en que llegaron no debe importar) y maneja naturalmente un número variable de ofertas mediante la máscara. Un MLP sobre el vector concatenado tendría que aprender, redundantemente, la misma función en cada posición de la entrada.

- **Pros:** estable, tolera recompensas ruidosas y episodios largos, paraleliza trivialmente con entornos vectorizados, el enmascaramiento está bien fundamentado teóricamente y disponible (`sb3-contrib.MaskablePPO`).
- **Contras:** menos eficiente en muestras que DQN (necesita entornos rápidos — de ahí la insistencia en las matrices precalculadas del §5.2).
- **Hiperparámetros de partida** (valores de referencia razonables, no mágicos): $\gamma=0.99$, GAE $\lambda=0.95$, `clip`$=0.2$, lr $3\times10^{-4}$ con decaimiento lineal, `n_envs`$=16$, `n_steps`$=512$, `batch`$=2048$, `epochs`$=4$, coef. de entropía $0.01 \to 0.001$ con *annealing*, `vf_coef`$=0.5$, recorte de gradiente $0.5$, normalización de observaciones y de recompensa.

### 6.4 Familia C — Construcción neuronal tipo *Attention Model* / POMO

Para el **subproblema de secuenciación**: codificador tipo *transformer* sobre las paradas y decodificador autorregresivo que construye la ruta parada por parada, entrenado con REINFORCE y línea base de *rollout* (Kool et al.) o con el truco de simetría de **POMO** (múltiples *rollouts* desde inicios distintos, usando su promedio como línea base — elimina la red crítica y mejora mucho la varianza). La variante con **atenciones heterogéneas** para pares recolección-entrega (Li et al., arXiv:2110.02634) es la que respeta la precedencia por construcción.

**Veredicto pragmático: no hacerlo en un hackathón.** El subproblema de secuenciación con ≤12 paradas se resuelve **a optimalidad** con Held–Karp ($O(2^{n}n^{2})$, con $n=12$ son ~590 k operaciones, submilisegundo en C/NumPy) o con enumeración podada. Entrenar una red para aproximar algo que un algoritmo exacto resuelve en microsegundos es un mal uso del tiempo. Se documenta como trabajo futuro para el caso en que el plan activo crezca (repartidores en bicicleta con muchos pedidos pequeños, o extensión multi-repartidor).

### 6.5 Familia D — Híbrido jerárquico (RECOMENDADO)

```
                 ┌──────────────────────────────────────────┐
   ofertas  ───► │ FILTRO DE FACTIBILIDAD (exacto)          │
                 │ prueba de inserción vs (C7)(C8)(C9)(C11) │
                 └────────────────┬─────────────────────────┘
                                  ▼
                 ┌──────────────────────────────────────────┐
                 │ EVALUADOR DE INSERCIÓN (exacto)          │
                 │ Held–Karp → Δt_j, Δδ_j óptimos por oferta│
                 └────────────────┬─────────────────────────┘
                                  ▼
                 ┌──────────────────────────────────────────┐
                 │ POLÍTICA APRENDIDA (PPO + atención)      │
                 │ decide: aceptar / rechazar / reposicionar│
                 │ aprende h*(S): valor de posición,        │
                 │ valor de espera, riesgo de cascada       │
                 └────────────────┬─────────────────────────┘
                                  ▼
                 ┌──────────────────────────────────────────┐
                 │ SECUENCIADOR (exacto) → plan ejecutable  │
                 └──────────────────────────────────────────┘
```

**Por qué esta es la arquitectura correcta.** Divide el problema por la naturaleza de su dificultad, no por conveniencia:

- La **secuenciación** es combinatoria pero *pequeña y determinista dado el conjunto*. Los métodos exactos la dominan. Aprenderla es regalar desempeño.
- La **aceptación** es un problema de decisión bajo incertidumbre sobre el futuro: qué ofertas vendrán, dónde, cuándo. Ningún solver la resuelve porque el futuro no está en la instancia. **Aquí y sólo aquí el RL tiene ventaja estructural.**

Beneficios colaterales que importan en la práctica: el espacio de acción se reduce a ~10 acciones discretas (aprende mucho más rápido), las violaciones de frescura son **imposibles por construcción** (el filtro es exacto, no aprendido — nunca hay que confiar en que la red aprendió una restricción dura), y el sistema degrada con gracia: si la red falla o no converge, se sustituye por la regla de umbral B2 y el producto sigue funcionando.

### 6.6 Tabla comparativa de agentes

| Agente | Esfuerzo | Tiempo de entrenamiento (CPU/1 GPU) | Muestras requeridas | Techo de desempeño | Riesgo | Interpretable |
|---|---|---|---|---|---|---|
| B2 umbral | 2 h | — | 0 | medio-alto | muy bajo | sí, total |
| B3 MILP rodante | 5 h | — | 0 | alto | bajo | sí |
| DQN enmascarado | 6 h | 1–3 h | $\sim3\times10^{5}$ | alto | medio | sí ($Q$ = pesos) |
| PPO + atención | 8 h | 2–6 h | $\sim2\times10^{6}$ | alto | medio | parcial |
| **Híbrido (D)** | **10 h** | **1–4 h** | $\sim5\times10^{5}$ | **muy alto** | **bajo** | **sí** |
| AM/POMO completo | 25 h+ | 12–48 h | $\sim10^{7}$ | alto | alto | no |

### 6.7 Optimización del entrenamiento

Ordenado por retorno sobre esfuerzo. Los tres primeros puntos valen más que cualquier ajuste de hiperparámetros.

**1. Hacer el entorno rápido antes de tocar el algoritmo.** El cuello de botella casi siempre es el simulador, no la red. Objetivo: **≥ 5 000 pasos/segundo** con 16 entornos en paralelo.
- Matrices de tiempo/distancia precalculadas (§5.2) — el factor 100×.
- Cero asignación de memoria en el ciclo: arreglos NumPy preasignados, sin `dict`, sin `pandas` dentro de `step()`.
- Perfilar con `cProfile` **antes** de entrenar. Una hora de perfilado ahorra diez de espera.
- `SubprocVecEnv` (no `DummyVecEnv`) para paralelismo real.
- Si el entorno sigue lento, reimplementar `step()` con `numba.njit` o migrar a un entorno vectorizado en JAX. Esto último sólo si sobra tiempo.

**2. Currículum de aprendizaje.** Aumentar la dificultad progresivamente en lugar de arrancar en el escenario completo:

| Etapa | Configuración | Criterio de paso |
|---|---|---|
| 1 | 1 oferta a la vez, sin preparación, sin clima | tasa ≥ 90 % de B2 |
| 2 | ofertas concurrentes, $R_i$ aleatorio | aparece agrupamiento (≥1.5 pedidos a bordo) |
| 3 | + frescura y fechas límite | puntualidad ≥ 85 % |
| 4 | + tráfico y clima | tasa > B2 |
| 5 | aleatorización de dominio completa (parámetros muestreados por episodio) | generaliza a escenarios de prueba |

La etapa 5 (*domain randomization*: muestrear por episodio el rendimiento del vehículo, los parámetros de tarifa, la intensidad de demanda, el perfil de tráfico) es lo que evita que el agente memorice un único mundo simulado. Es la diferencia entre un agente que se ve bien en la demo y uno que sería desplegable.

**3. Arranque por imitación.** Generar ~50 000 transiciones con B3 (MILP rodante) o B2, pre-entrenar la política por entropía cruzada sobre esas acciones, y luego continuar con PPO. Reduce típicamente entre 3 y 10 veces las muestras necesarias y **evita el colapso inicial** en el que el agente rechaza todo (porque rechazar todo tiene recompensa 0, que es mejor que aceptar mal, y es un mínimo local muy atractivo al principio). Si sólo se puede hacer una técnica de esta sección además de la primera, que sea ésta.

**4. Enmascaramiento en lugar de penalización.** Ya argumentado en §4.4. Vale repetirlo porque es el error más frecuente: penalizar acciones inválidas hace que el agente gaste su capacidad en aprender qué es factible, cosa que ya sabemos calcular exactamente.

**5. Normalización.** `VecNormalize` para observaciones y recompensas, con las estadísticas **congeladas en evaluación**. Las magnitudes del problema (pesos ~100, minutos ~1000, metros ~10⁴) difieren en varios órdenes; sin normalizar, la red dedica su capacidad a compensar escalas.

**6. Reducción de varianza en la evaluación.** Números pseudoaleatorios comunes: evaluar todas las políticas sobre **las mismas realizaciones** de órdenes, clima y tiempos de viaje. Convierte una comparación ruidosa en una comparación pareada; con 50 escenarios pareados se detectan diferencias que, sin pareo, requerirían cientos.

**7. Cordura estadística.** Entrenar con **≥3 semillas** y reportar la mediana con rango intercuartílico. Una sola semilla de RL no es evidencia de nada; es la crítica metodológica más fácil de recibir y la más fácil de prevenir.

**8. Robustez a la desviación humana.** Durante el entrenamiento, con probabilidad $\epsilon\approx0.1$, ignorar la acción de la política y ejecutar otra factible (simulando que el repartidor desobedeció). Produce una política reactiva al estado real en lugar de una que depende de que su plan se cumpla. Es un detalle pequeño que cambia por completo la utilidad del sistema en el mundo real, y es fácil de explicar como diferenciador en la presentación.

**9. Presupuesto de cómputo.** El modelo cabe en unos pocos millones de parámetros; **el cuello de botella es el entorno, no la red**. Una CPU de 8–16 hilos con entornos vectorizados es suficiente y probablemente mejor que una GPU con un entorno lento. No gastar tiempo del hackathón consiguiendo GPU.

---

## 7. Plan de ejecución para el hackathón

Suponiendo ~48 horas y un equipo pequeño. El orden importa más que el contenido: cada bloque deja un entregable presentable, de modo que a cualquier hora de corte existe una demo.

| Bloque | Horas | Entregable | Quién queda desbloqueado |
|---|---|---|---|
| 1 | 0–4 | Entorno L0 (rejilla) funcionando, `Gymnasium` API, B0/B1 corriendo | todos |
| 2 | 4–8 | Generador de órdenes + **prueba de sanidad de agrupamiento** (§5.6) | decide si el proyecto tiene sustancia |
| 3 | 6–10 | Módulos exactos: filtro de factibilidad, Held–Karp, evaluador de inserción | B2, B3 y el agente D |
| 4 | 8–12 | **B2 (regla de umbral)** — *ya hay demo defendible aquí* | punto de seguridad del proyecto |
| 5 | 10–16 | Grafo real de MTY + matrices precalculadas (L2) | realismo visual |
| 6 | 12–20 | B4 oráculo MILP en instancias pequeñas → primera medición de brecha | la narrativa cuantitativa |
| 7 | 16–28 | PPO enmascarado + arranque por imitación; currículum etapas 1–3 | el resultado principal |
| 8 | 24–36 | Capas de tráfico y clima (L2 completo); currículum 4–5 | robustez |
| 9 | 30–40 | Evaluación pareada sobre 50 escenarios, 3 semillas, todas las métricas | credibilidad |
| 10 | 36–44 | Visualización: mapa animado del turno, comparación lado a lado de políticas | la demo |
| 11 | 44–48 | Documento, gráficas, presentación | entrega |

**Ruta crítica:** bloques 1 → 2 → 3 → 4. Si el bloque 2 revela que no hay oportunidad de agrupamiento, hay que recalibrar el generador antes de seguir; todo lo demás carece de sentido sin esa comprobación.

**Paralelizable:** el bloque 5 (grafo real) y el 6 (MILP) son independientes del 7 (RL) y pueden asignarse a personas distintas.

**Reducciones de alcance predefinidas**, en el orden en que hay que sacrificarlas: L3/SUMO → incidentes → contexto espacial convolucional (§5.7d) → aleatorización de dominio → clima. Decidir esto por adelantado evita discusiones a las 3 de la mañana.

---

## 8. Riesgos y verificación

| Riesgo | Probabilidad | Detección | Mitigación |
|---|---|---|---|
| El generador no crea oportunidad de agrupamiento | media | prueba de sanidad, bloque 2 | subir intensidad, concentrar comercios, alargar preparación |
| El RL no supera a B2 | **alta** | evaluación pareada | presentar B2 como producto y el RL como análisis; reportar la brecha honestamente |
| Entorno demasiado lento | alta | perfilado | matrices precalculadas, `numba`, bajar a L1 para entrenar |
| Agente colapsa a "rechazar todo" | alta | tasa de aceptación ≈ 0 | arranque por imitación, *annealing* de entropía, revisar $\hat\rho$ |
| Recompensa explotada | media | inspección de trayectorias | sólo *shaping* por potencial; revisar la tabla de antipatrones §5.9 |
| Sobreajuste al simulador | segura | evaluar en escenarios con parámetros distintos | aleatorización de dominio; declarar la limitación |
| MILP no resuelve a tiempo | media | tiempo límite del solver | instancias más pequeñas, reportar cota dual en lugar del óptimo |

**Verificaciones de corrección del simulador** (hacerlas como pruebas automatizadas, no a ojo):

1. **Conservación:** todo pedido recogido termina entregado o cancelado explícitamente; la carga a bordo nunca es negativa ni excede $Q$.
2. **Monotonía FIFO:** salir más tarde nunca produce llegada más temprana (§3.1).
3. **Desigualdad triangular:** en las matrices precalculadas, $\tau(a,c) \le \tau(a,b)+\tau(b,c)$ salvo tolerancia por dependencia temporal. Las violaciones sistemáticas indican un error en el precálculo.
4. **Frescura:** contador de violaciones idénticamente 0 en todos los episodios (prueba del enmascaramiento).
5. **Coherencia contable:** ganancia reportada = Σ tarifas − Σ costos, recalculado de forma independiente al final del episodio a partir del registro de eventos.
6. **Concordancia con el oráculo:** en instancias con 3 pedidos, resolver por fuerza bruta la mejor secuencia y confirmar que Held–Karp devuelve el mismo valor.

---

## 9. Fuentes externas

**Problema de reparto de comida (perspectiva de plataforma)**

1. Reyes, D., Erera, A., Savelsbergh, M., Sahasrabudhe, S., O'Neil, R. (2018). *The Meal Delivery Routing Problem*. Optimization Online. https://optimization-online.org/wp-content/uploads/2018/04/6571.pdf
2. Yildiz, B., Savelsbergh, M. *Provably High-Quality Solutions for the Meal Delivery Routing Problem*. Optimization Online / Transportation Science. https://optimization-online.org/wp-content/uploads/2018/05/6624.pdf
3. Ulmer, M. W., Thomas, B. W., Campbell, A. M., Woyak, N. (2021). *The Restaurant Meal Delivery Problem: Dynamic Pickup and Delivery with Deadlines and Random Ready Times*. Transportation Science 55(1), 75–100. https://pubsonline.informs.org/doi/abs/10.1287/trsc.2020.1000
4. *Meal Delivery Routing Problem with Stochastic Meal Preparation Times and Customer Locations* (2024). Networks and Spatial Economics. https://link.springer.com/article/10.1007/s11067-024-09643-1

**Ruteo dinámico y estocástico / formulación MDP**

5. Ulmer, M. W., Goodson, J. C., Mattfeld, D. C., Thomas, B. W. *On Modeling Stochastic Dynamic Vehicle Routing Problems*. EURO Journal on Transportation and Logistics. https://www.sciencedirect.com/science/article/pii/S219243762030008X
6. Hildebrandt, F. D., Thomas, B. W., Ulmer, M. W. (2023). *Opportunities for Reinforcement Learning in Stochastic Dynamic Vehicle Routing*. Computers & Operations Research. https://www.sciencedirect.com/science/article/abs/pii/S030505482200301X
7. Ulmer, M. W. *Anticipation in Dynamic Vehicle Routing*. Springer. https://link.springer.com/chapter/10.1007/978-3-319-89920-6_2

**Ruteo selectivo (fundamento de la decisión aceptar/rechazar)**

8. Vansteenwegen, P., Souffriau, W., Van Oudheusden, D. *The Team Orienteering Problem with Time Windows: An LP-based Granular Variable Neighborhood Search*. European Journal of Operational Research. https://www.sciencedirect.com/science/article/abs/pii/S0377221712000653
9. Archetti, C. et al. *The Capacitated Team Orienteering and Profitable Tour Problems*. https://www.researchgate.net/publication/220636563_The_Capacitated_Team_Orienteering_and_Profitable_Tour_Problems

**Aprendizaje profundo por refuerzo para ruteo**

10. Li, J. et al. (2021). *Heterogeneous Attentions for Solving Pickup and Delivery Problem via Deep Reinforcement Learning*. arXiv:2110.02634. https://arxiv.org/abs/2110.02634
11. Huang, S., Ontañón, S. (2020). *A Closer Look at Invalid Action Masking in Policy Gradient Algorithms*. arXiv:2006.14171. https://arxiv.org/abs/2006.14171
12. *Integrated Order Dispatching and Routing for Last-Mile Pickup via Deep Reinforcement Learning*. arXiv:2607.22356. https://arxiv.org/abs/2607.22356
13. Maskable PPO — documentación de Stable-Baselines3 Contrib. https://sb3-contrib.readthedocs.io/en/master/modules/ppo_mask.html

**Entrega colaborativa y multiplataforma**

14. *Joint Optimization of Parcel Allocation and Crowd Routing for Crowdsourced Last-Mile Delivery*. Transportation Research Part B. https://www.sciencedirect.com/science/article/abs/pii/S0191261523000504
15. *The Pickup and Delivery Problem with Multiple Depots and Dynamic Occasional Drivers in Crowdshipping Delivery*. Computers & Industrial Engineering. https://www.sciencedirect.com/science/article/abs/pii/S0360835223004643
16. Popan, C. (2024). *The Fragile 'Art' of Multi-Apping: Resilience and Snapping in the Gig Economy*. Environment and Planning A. https://journals.sagepub.com/doi/10.1177/0308518X231209984
17. *Pricing and Wage Decisions for On-Demand Food Delivery Platforms with Multiple Customer Classes and Courier Pools*. International Journal of Production Economics. https://www.sciencedirect.com/science/article/abs/pii/S0925527325002804

**Referencias clásicas citadas en el texto** (fundamentos estándar, sin enlace):

18. Kool, W., van Hoof, H., Welling, M. (2019). *Attention, Learn to Solve Routing Problems!* ICLR.
19. Kwon, Y.-D. et al. (2020). *POMO: Policy Optimization with Multiple Optima for Reinforcement Learning*. NeurIPS.
20. Ng, A. Y., Harada, D., Russell, S. (1999). *Policy Invariance Under Reward Transformations: Theory and Application to Reward Shaping*. ICML. — base del *shaping* por potencial (§5.9).
21. Puterman, M. L. (1994). *Markov Decision Processes*. Wiley. — capítulo de SMDP y criterio de recompensa promedio (§4.7).
22. Held, M., Karp, R. M. (1962). *A Dynamic Programming Approach to Sequencing Problems*. — el secuenciador exacto (§6.5).
23. Boeing, G. (2017). *OSMnx: New Methods for Acquiring, Constructing, Analyzing, and Visualizing Complex Street Networks*. Computers, Environment and Urban Systems. — construcción del grafo vial (§5.2).
24. Lopez, P. A. et al. (2018). *Microscopic Traffic Simulation using SUMO*. IEEE ITSC. — nivel L3 (§5.1).

---

## Apéndice A — Glosario de notación

| Símbolo | Significado |
|---|---|
| $G=(\mathcal{V},\mathcal{E})$ | red vial dirigida |
| $\tau(u,v,t,w)$ | tiempo de viaje $u\to v$ saliendo en $t$ bajo clima $w$ |
| $\delta(u,v,t,w)$ | distancia del camino elegido |
| $i, \mathcal{O}$ | pedido, conjunto de pedidos ofrecidos |
| $o_i, d_i$ | nodos de recolección y entrega del pedido $i$ |
| $a_i, r_i, \ell_i, \theta_i$ | aparición de la oferta, listo, fecha límite, tolerancia de frescura |
| $f_i, g_i$ | tarifa, propina |
| $y_i$ | binaria de aceptación |
| $x_{mn}$ | binaria de arco en la ruta |
| $T_n, S_n$ | llegada e inicio de servicio en el nodo $n$ |
| $\sigma_i$ | holgura de recolección (espera por preparación) |
| $S_k, A_k, \mathcal{M}(S_k)$ | estado, acción, conjunto de acciones factibles enmascarado |
| $\mathcal{A}_k, \mathcal{F}_k$ | plan activo, ofertas pendientes |
| $\rho, \rho^{*}, \hat\rho$ | tasa de ganancia (pesos/hora): de una política, óptima, estimada |
| $h^{*}(S)$ | función de sesgo del SMDP de recompensa promedio |
| $\mu_n$ ($\mu_i^{P},\mu_i^{D}$) | tiempo de servicio en el nodo $n$ (recolección, entrega) |
| $c_\kappa, c_\tau$ | costo por km, costo por minuto |
| $\varepsilon(\bar v)$ | rendimiento del vehículo en función de la velocidad |
| $\gamma_w$ | multiplicador climático del tiempo de viaje |
| $\Lambda_p$ | intensidad del proceso de llegada de ofertas de la plataforma $p$ |
| $K_A, K_F$ | cotas del plan activo y de ofertas visibles en la observación |

---

## Apéndice B — El resultado de una línea

Si hubiera que resumir el aporte matemático del sistema en una sola expresión para mostrar en una diapositiva:

$$
\text{Aceptar la oferta } j \iff \underbrace{\frac{\Delta f_j - c_\kappa\,\Delta\delta_j}{\Delta t_j}}_{\substack{\text{tasa marginal}\\ \text{(calculable exacto)}}} \;+\; \underbrace{\frac{\mathbb{E}\big[h^{*}(S')\big]-h^{*}(S)}{\Delta t_j}}_{\substack{\text{valor posicional y de opción}\\ \text{(esto es lo que aprende el agente)}}} \;>\; \underbrace{\rho^{*}}_{\substack{\text{tu tasa}\\ \text{de ganancia}}}
$$

El primer término es lo que un repartidor experimentado ya calcula mentalmente. El segundo es lo que no puede calcular, y es lo que el sistema aporta. El tercero es lo que el sistema debe mostrarle para que confíe en la recomendación.
