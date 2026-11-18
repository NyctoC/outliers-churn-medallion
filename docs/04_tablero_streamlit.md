# Tablero en Streamlit: guía de las vistas

Tablero interactivo del proyecto de churn de The Outliers (curso *Visualización de Datos*). Complementa la
presentación: en lugar de repetir el modelo, permite **explorar dónde está el valor en riesgo y bajar hasta un
cliente** para entender su riesgo y simular cambios con la API del modelo.

| Vista | Pregunta que responde | Fuente de datos |
|---|---|---|
| 1 · Valor en riesgo | ¿Cuánto dinero se puede perder, dónde está y a quién llamar? | Consultas SQL a Amazon Athena (capa oro) |
| 2 · Ficha y simulador | ¿Por qué este cliente está en riesgo y qué lo sacaría del riesgo? | API del modelo en Amazon EC2 + Athena |
| 3 · Efecto de las variables | ¿Cómo responde el modelo cuando cambia una sola cosa del cliente? | API del modelo en Amazon EC2 |

El argumento central del proyecto aparece en la barra lateral: *el churn no depende de quién es el cliente sino de
cómo compra; con pedidos, gasto y devoluciones, el modelo encuentra 3,5 veces más clientes que se van que el azar y le
dice a cada uno qué campaña necesita.* La barra lateral también muestra si la API del modelo está en línea.

## Cómo ejecutarlo

```powershell
.venv\Scripts\Activate.ps1
streamlit run dashboard/app.py      # desde la raíz del repo; abre http://localhost:8501
```

Requiere un `.env` con las llaves del usuario **de solo lectura**, `ATHENA_S3_OUTPUT` y `API_URL`
(ver `.env.example` y `docs/02_conexion_aws.md`). En Streamlit Cloud los mismos valores van en *Settings → Secrets*.

```
dashboard/
├── app.py                 # navegación, barra lateral y estado de la API
├── requirements.txt       # dependencias del tablero (no carga el modelo: lo consulta en la API)
├── componentes/
│   ├── config.py          # .env / Secrets de Streamlit y certificados
│   ├── datos.py           # consultas a Athena con caché (6 h) y SQL visible
│   ├── api.py             # cliente de la API; los errores se muestran tal cual, sin respaldo
│   ├── graficos.py        # estilo de los gráficos y paleta apta para daltonismo
│   └── textos.py          # etiquetas en español, argumento y casos de ejemplo
└── paginas/
    ├── valor.py           # vista 1
    ├── simulador.py       # vista 2
    └── efectos.py         # vista 3
```

---

## Vista 1 · Valor en riesgo

### Para qué existe

La presentación responde **"¿quién se va a ir?"**. Esta vista responde lo que la presentación no toca:
**"¿cuánto dinero se puede perder, dónde está y a quién llamar para protegerlo?"**

**Mensaje central:** los clientes que más se van son los que menos valen. Por eso, priorizar por probabilidad y
priorizar por dinero producen listas distintas, y la vista permite explorar esa diferencia.

### Conceptos

| Concepto | Qué es | De dónde sale |
|---|---|---|
| **CLV** (valor de vida del cliente) | Cuánto vale un cliente para la empresa, en rupias | `lifetime_value` de `customer_summary`, en `churn_gold.customer_360` |
| **Probabilidad de churn** | Qué tan probable es que se vaya, según el modelo EBM | `churn_gold.churn_predicciones` (puntuación por lotes de los 500.000 clientes) |
| **Pérdida esperada** | **Probabilidad × CLV**: lo que en promedio se perdería si no se hace nada | Se calcula en Athena |

Ejemplo: un cliente con CLV de ₹500.000 y 60 % de probabilidad de irse tiene una pérdida esperada de ₹300.000.

### Secciones

#### 1. Filtros

Cinco filtros en una fila: **Membresía, Ciudad, Dispositivo, Canal de llegada y Campaña sugerida**.

- Vacío significa "todos", y se pueden combinar (por ejemplo, Gold en Mumbai). **Limpiar** los borra todos.
- **Afectan a toda la página**: KPIs, matriz, barras, dilema y lista.
- Cada combinación nueva lanza consultas a Athena (~5 s cada una). Una combinación ya vista sale de la caché al
  instante.

#### 2. KPIs

| KPI | Sin filtros | Cómo leerlo |
|---|---|---|
| **Clientes** | 500.000 | Cuántos cumplen los filtros |
| **Pérdida esperada** | ₹43,2 mil M (12,7 % del CLV) | El dinero en juego si no se hace nada |
| **CLV de los marcados en riesgo** | ₹4,9 mil M · 43.375 clientes | Valor de los clientes con p ≥ 0,5. Es poco: casi todo el dinero en riesgo está en clientes que **no** superan el umbral |
| **Churners esperados** | 103.578 (20,7 %) | Suma de las probabilidades. Coincide con el 20,7 % real: el modelo está bien calibrado |

Bajo cada cifra hay una frase que dice qué es y cómo leerla, y el ícono **?** da la fórmula. Se recalculan con los
filtros. Sin filtros dicen:

- **Pérdida esperada:** el 12,7 % del CLV total de estos clientes (₹339,9 mil M) se espera perder si no se actúa. Es
  menos que la tasa de churn del 20,7 % porque los clientes con más riesgo son, en general, los de menor valor.
- **CLV de los marcados en riesgo:** lo que valen los 43.375 clientes (8,7 %) con p ≥ 0,5. Al menos el **89 %** de la
  pérdida esperada viene de clientes que el modelo **no** marca. Es una cota: la pérdida esperada de los marcados no
  puede superar su CLV completo, ₹4,9 mil M de ₹43,2 mil M.

Debajo de las tarjetas, el desplegable **"¿Por qué el modelo marca a 43.375 clientes si se espera que se vayan
103.578?"** aclara la confusión más común de esta vista:

- **Marcados** es un conteo con corte: cuántos clientes tienen p ≥ 0,5.
- **Churners esperados** es la suma de las probabilidades de todos los clientes.
- **Ejemplo:** 10 clientes con 30 % cada uno no quedan marcados, pero en promedio se van 3.
- Con cientos de miles de clientes de probabilidad moderada (15–40 %), la mayoría de quienes se van no supera el
  umbral. Por eso la vista prioriza por pérdida esperada y no solo por la lista de marcados.

No se usan las flechas de "delta" de Streamlit porque sugerían que la cifra había subido, cuando no se compara con
nada.

#### 3. Matriz riesgo × valor

- **Qué muestra:** los 500.000 clientes en 100 grupos.
  - **Filas:** decil de riesgo. D1, arriba, es el 10 % con mayor probabilidad de irse.
  - **Columnas:** decil de CLV. A la derecha, más valor.
  - **Color de cada cuadro:** su pérdida esperada; más oscuro, más dinero en juego.
- **Título (el hallazgo):** *"El 10 % de mayor riesgo solo carga el 9 % de la pérdida esperada: quien más se va,
  menos vale."* La fila de arriba es clara, porque son clientes muy riesgosos pero de bajo valor, y lo oscuro aparece
  en el medio.
- **Interacción:**
  - **Hover:** clientes, probabilidad media, CLV medio y pérdida esperada del cuadro.
  - **Clic en un cuadro:** queda marcado con borde naranja y **la lista del final muestra solo esos clientes**. Es el
    drill-down de 500.000 clientes a un grupo concreto, por ejemplo "riesgo D3 × valor D5".
- Los deciles se calculan sobre los 500.000 clientes **antes** de filtrar, así un cuadro significa lo mismo con o sin
  filtros.

#### 4. Desglose por dimensión

- **Qué muestra:** barras con la pérdida esperada por la dimensión elegida en el selector (membresía, ciudad,
  dispositivo, canal o campaña).
- **Título:** dice quién concentra más, por ejemplo *"Basic concentra ₹23,7 mil M (55 %) de la pérdida esperada"*.
- **Interacción:** **clic en una barra = agregar ese filtro** a toda la página. Es una segunda forma de profundizar.
- **Ojo:** que Basic concentre más se debe en buena parte a que tiene más clientes. Para comparar segmentos de tamaño
  distinto, el hover muestra la probabilidad media y el CLV medio.

#### 5. Nota de cautela

*"El CLV casi es el gasto total (correlación 0,94), y el gasto bajo es una de las variables que sube el riesgo."*
Que "alto riesgo = bajo valor" es, en parte, una consecuencia de cómo funciona el modelo y no solo del negocio.
Conviene decirlo en la sustentación antes de que lo pregunten.

#### 6. El dilema: ¿priorizar por probabilidad o por pérdida esperada?

Es la sección más importante de la vista.

- **Control:** slider con el % de clientes que la empresa puede contactar (1 % a 50 %).
- **Dos gráficos**, cada uno con las dos estrategias y la línea del azar:
  - **Churners encontrados:** de los clientes que realmente se fueron, ¿qué % estaba en la lista?
  - **Valor de esos churners:** de todo el CLV que se fue, ¿qué % se encontró?
- **Lectura al 10 %:**

  | Estrategia | Churners encontrados | Valor encontrado |
  |---|---|---|
  | **Priorizar por probabilidad** (azul) | **35 %** | 9 % |
  | **Priorizar por pérdida esperada** (naranja) | 11 % | **26 %** |

- **Conclusión:** ninguna estrategia gana en las dos. Si la empresa quiere **reducir la cantidad** de clientes que se
  van, ordena por probabilidad; si quiere **proteger ingresos**, ordena por pérdida esperada. El tablero no decide:
  muestra el costo de cada opción.
- **Rigor:** solo usa los **150.000 clientes de test**, que el modelo no vio al entrenar, y los compara con lo que
  realmente pasó. Es evidencia, no una simulación.

#### 7. Lista de clientes

- **Qué muestra:** los 200 primeros clientes según los filtros y la celda elegida. Columnas: probabilidad, CLV,
  pérdida esperada, motivo, campaña, membresía, ciudad, pedidos, devoluciones y conjunto.
- **Ordenar por:** pérdida esperada (por defecto) o probabilidad. Son las dos estrategias del dilema convertidas en
  una lista concreta.
- **Descargar CSV:** la lista para el equipo de mercadeo o el CRM.
- **Seleccionar una fila abre la ficha del cliente** (vista 2). Es el puente de lo agregado a lo individual.

#### 8. "Consulta a Athena"

Bajo cada sección hay un desplegable con el **SQL exacto**, el tiempo y los MB escaneados de cada consulta. Cada
consulta escanea unos pocos MB, así que el costo es de centavos. Demuestra que **el tablero consume la capa oro en
vivo**.

### Recorridos sugeridos

1. **El hallazgo general.** Sin filtros, mira la matriz (la fila de arriba es clara) y mueve el slider del dilema.
2. **Un segmento.** Clic en la barra "Platinum" o elige una ciudad: los KPIs y el dilema cambian, y se ve si el
   patrón se mantiene.
3. **De la celda al cliente.** Clic en un cuadro oscuro de la matriz, ordena por pérdida esperada y selecciona el
   primer cliente para pasar a su ficha.

### Relación con las rúbricas

| Rúbrica | Qué cubre la vista |
|---|---|
| Visualización: dashboard interactivo (30 %) | Filtros, drill-down (matriz → lista → ficha), clic en barras, hover y descarga |
| Visualización: construcción del mensaje (20 %) | Títulos declarativos que cambian con los filtros y dicen el hallazgo |
| Aprendizaje Automático: métrica de negocio (15 %) | Traduce el modelo a dinero y discute el criterio de priorización con evidencia de test |
| Almacenamiento: despliegue y consumo (20 %) | Consultas a la capa oro con Athena, con el SQL visible |

### Limitaciones

- **Datos sintéticos:** las rupias ilustran el método, no son cifras reales.
- **El CLV del dataset no está documentado:** no se sabe cómo se calculó, solo que casi es el gasto total.
- **La pérdida esperada no incluye** el costo de retener a cada cliente ni si la campaña funcionaría. Es dinero en
  riesgo, no dinero recuperable.

---

## Vista 2 · Ficha y simulador de un cliente

### Para qué existe

La vista 1 dice **a quién** mirar. La vista 2 explica **un cliente concreto**:

- por qué el modelo lo considera en riesgo;
- cuánto valor se perdería si se va;
- qué campaña le corresponde;
- qué cambio mínimo lo sacaría del riesgo.

Todo se calcula **en vivo con la API del modelo** desplegada en EC2. Es la demostración de "un modelo consumido por
API desde un dashboard", y cubre el **caso aplicado** de la rúbrica de Aprendizaje Automático: predicciones sobre
casos concretos, interpretadas y conectadas con la decisión.

### Endpoints de la API que usa

| Endpoint | Para qué | Cuándo se llama |
|---|---|---|
| `GET /clientes/{id}` | La predicción guardada por lotes en la capa oro | Al abrir un cliente existente |
| `POST /explicar` | Probabilidad, contribución de cada término del modelo, motivo y campaña | Al abrir el cliente y **cada vez que se mueve un control** |
| `POST /contrafactuales` | El cambio mínimo que deja al cliente bajo el umbral de 0,5 | Igual que `/explicar` |
| `GET /modelo` | Ficha técnica del modelo que responde | Al abrir el desplegable correspondiente |

Además, el perfil del cliente, sus 4 variables y su CLV se leen de `customer_360` con Athena.

Las respuestas se guardan en caché: volver a una combinación de valores ya consultada no llama de nuevo a la API.
**No hay respaldo:** si la API falla, la vista muestra el error exacto (sin conexión, timeout, datos rechazados…)
para saber qué corregir.

### Secciones

#### 1. Elegir el cliente

Dos modos:

- **Cliente existente** (por defecto):
  - **Seis casos de ejemplo** en botones, todos clientes de `test`, que el modelo no vio al entrenar (tabla abajo).
  - **Un campo para escribir cualquier `customer_id`**, de 1.000.001 a 1.500.000.
  - También se llega aquí **seleccionando una fila en la lista de la vista 1**.
  - Bajo los botones aparece el perfil: membresía, ciudad, dispositivo, edad, antigüedad y conjunto (train o test).
- **Cliente nuevo (valores libres):** parte de 10 pedidos, ₹6.000 de valor promedio y 3 devoluciones. Sirve para
  preguntar "¿qué diría el modelo de un cliente así?". No tiene CLV, predicción guardada ni resultado real.

| Caso | Cliente | Qué muestra |
|---|---|---|
| Riesgo alto por pocos pedidos (el del PPT) | 1340006 | 2 pedidos, 1 devolución → p = 0,83. Con 1 pedido más bajaría a 0,47. Se fue: acierto |
| Alto valor en riesgo | 1070128 | Gold, CLV ₹521.271, p = 0,67 → pérdida esperada ₹351.121. Con 7 pedidos más saldría del riesgo. Se fue: acierto |
| Riesgo por devoluciones | 1000863 | 19 pedidos y 10 devoluciones → p = 0,62, campaña de atención posventa. Se fue: acierto |
| Riesgo bajo, cliente fiel | 1113773 | Platinum, 69 pedidos → p = 0,11. Se quedó: acierto |
| Falsa alarma | 1002569 | 8 pedidos y 5 devoluciones → p = 0,79, pero se quedó |
| Se escapó | 1000074 | 94 pedidos → p = 0,09, pero se fue |

Los dos últimos casos muestran **por qué el modelo falla**, algo que la rúbrica pide explícitamente.

#### 2. "¿Y si cambiara…?": el simulador

- **Controles:**
  - **Pedidos:** slider de 1 a 120.
  - **Devoluciones:** slider de 0 a 10.
  - **Valor promedio por pedido:** campo numérico de ₹500 a ₹12.000, en pasos de ₹250.
  - **"Volver a los valores reales"** (o "Restablecer" en un cliente nuevo).
- Arrancan con los valores reales del cliente. **Cada cambio es una llamada nueva a `POST /explicar` y
  `POST /contrafactuales`**, y la página se actualiza en menos de un segundo.
- **El gasto total se recalcula solo** como pedidos × valor promedio, igual que en el modelado (las dos variables
  tienen correlación 1,0). Con los valores reales se usa el gasto real del cliente, para que la predicción coincida
  exactamente con la guardada.
- **No puede haber más devoluciones que pedidos:** la API lo rechazaría. Si se eligen más, se limitan a los pedidos y
  la vista lo avisa.
- Los rangos son los del entrenamiento: fuera de ellos el modelo repite el valor del extremo.

#### 3. El resultado

- **Titular:** cambia con la respuesta de la API. Por ejemplo: *"Probabilidad de churn 83 %: en riesgo, sobre todo
  porque tiene pocos pedidos → campaña de reactivación"*. Bajo 0,5 dice que no requiere campaña.
- **Medidor:** barra de 0 a 100 % con el umbral de 0,5. Naranja si está en riesgo, azul si no.
- **CLV y pérdida esperada:**

  | Métrica | Qué es |
  |---|---|
  | **CLV del cliente** | Su valor de vida real (`lifetime_value`), con los valores reales del cliente |
  | **CLV estimado** | Aparece al mover pedidos o valor promedio: el CLV se ajusta con el gasto (ver abajo) |
  | **Pérdida esperada (p × CLV)** | Cuánto se espera perder. Al mover un control muestra cuánto cambia frente a los valores reales |

  **Por qué el CLV se estima y no se recalcula.** El CLV no lo calcula el proyecto ni el modelo: viene ya hecho en
  `customer_summary` y el dataset no documenta su fórmula. La API tampoco lo devuelve, porque no es una de las 4
  variables del modelo. Lo que sí se midió en Athena es que **CLV ≈ 1,8 × gasto total** (R² = 0,89; cada cliente tiene
  su propia relación, entre 1,2 y 2,4 en el 90 % central). Por eso:

  - **Cliente existente:** al cambiar pedidos o valor promedio cambia el gasto, y el CLV se ajusta en la misma
    proporción, conservando la relación CLV ÷ gasto de ese cliente.
  - **Cliente nuevo:** CLV estimado = 1,8 × gasto, la relación promedio.
  - **Devoluciones:** no cambian el gasto, así que no cambian el CLV estimado.

  **Hallazgo que muestra esto:** subir los pedidos baja la probabilidad, pero sube el CLV, y la pérdida esperada
  **puede subir**. El cliente 1340006 con 10 pedidos en lugar de 2 pasa de 83 % a 24 % de probabilidad, pero su CLV
  estimado pasa de ₹21.985 a ₹109.923. Su pérdida esperada sube de ₹18.231 a ₹25.938: ahora vale más y, aunque es
  menos probable que se vaya, hay más dinero en juego. Es el mismo dilema de la vista 1, visto en un solo cliente.

- **"Con los valores reales era":** aparece solo al cambiar valores en el simulador. Muestra la probabilidad
  original del cliente (la guardada en oro, `GET /clientes/{id}`) y cuántos puntos cambió.
- **Resultado real** (solo clientes de `test`):
  - **Verde:** el modelo acertó.
  - **Amarillo:** se equivocó, con su explicación. Falsa alarma: lo marcó y no se fue. Se escapó: no lo marcó y sí se
    fue, quizá por señales en variables retiradas por fuga, como la recencia de compra.
- **Advertencias de la API:** si un valor está fuera del rango de entrenamiento o el gasto no cuadra, la API lo
  avisa y la vista lo muestra.

#### 4. "Por qué": la explicación en cascada

- **Qué muestra:** cómo se construye la probabilidad del cliente:

  ```
  punto de partida (intercepto) + pedidos + gasto + valor promedio + devoluciones + pedidos × devoluciones = log-odds
  ```

  - **Naranja:** el término suma riesgo.
  - **Azul:** el término resta riesgo.
  - **Línea en 0:** equivale a probabilidad 0,5. Si el total queda arriba, el cliente está en riesgo.
- **Ejemplo** (cliente 1340006): parte de −1,56, los pocos pedidos suman +2,06, la combinación pedidos × devoluciones
  +0,84, el gasto +0,78 y el valor promedio +0,18, y la devolución resta −0,72. El total es +1,58 log-odds, es decir,
  p = 0,83.
- **Por qué funciona:** el EBM es **aditivo**, así que la suma reproduce exactamente la probabilidad. No es una
  aproximación como en otros métodos de explicabilidad.
- **El motivo principal** es el término que más riesgo suma, y define la campaña:
  - pocos pedidos o poco gasto → **reactivación**;
  - devoluciones o su combinación con los pedidos → **atención posventa**.
- **Advertencia en pantalla:** la explicación describe **cómo decide el modelo**, no por qué se van los clientes.
- Bajo el gráfico, el desplegable **"¿Qué son los log-odds y el punto de partida?"** resume lo que sigue.

##### Qué son los log-odds

- **Odds** = probabilidad de irse ÷ probabilidad de quedarse. Con p = 0,8 las odds son 0,8 ÷ 0,2 = 4 ("4 a 1").
- **Log-odds** = logaritmo natural de las odds. El modelo trabaja en esta escala porque en ella **los efectos se
  suman**. La probabilidad no se puede sumar, porque está atrapada entre 0 y 1: si un efecto suma 30 puntos y otro
  40, a un cliente de 50 % lo llevaría a 120 %. Los log-odds van de −∞ a +∞, y siempre se pueden volver a convertir
  en una probabilidad válida.

| Log-odds | −3 | −2 | −1 | **0** | +1 | +2 | +3 |
|---|---|---|---|---|---|---|---|
| Probabilidad | 5 % | 12 % | 27 % | **50 %** | 73 % | 88 % | 95 % |

- **0 log-odds = 50 %**, el umbral del modelo. Positivo es más probable irse que quedarse; negativo, lo contrario.
- **+1 log-odds multiplica las odds por e ≈ 2,72.** En probabilidad el efecto depende de dónde se parte: de 50 % a
  73 % son +23 puntos, pero de 88 % a 95 % solo +7.
- **Conversión:** p = 1 ÷ (1 + e^(−log-odds)).

##### El punto de partida (intercepto)

Es lo que el modelo diría de un **cliente "típico" antes de mirar sus datos**. Vale **−1,56 log-odds ≈ 17 %**.

- Es igual para todos los clientes: lo único que cambia entre clientes son las barras.
- Está cerca de la tasa de churn del 20,7 % (−1,34 log-odds), pero no es exactamente igual. El EBM centra cada
  término para que su efecto promedio en el entrenamiento sea cero, y promediar en log-odds no da lo mismo que
  promediar probabilidades.

##### Las barras de cada variable

Cada barra dice **cuánto mueve a este cliente su valor en esa variable, frente al cliente típico**. El EBM aprendió,
para cada variable, una curva "valor → contribución" (su *función de forma*). La barra es el punto de esa curva que
corresponde al cliente. El quinto término, **pedidos × devoluciones**, es el efecto extra de la combinación: las
devoluciones pesan distinto según cuántos pedidos tenga el cliente.

##### Ejemplo completo: cliente 1340006 (el del PPT)

Tiene 2 pedidos, gasto de ₹18.244, valor promedio de ₹9.122 y 1 devolución.

| Paso | Log-odds | Acumulado | Lectura |
|---|---|---|---|
| Punto de partida | −1,56 | −1,56 (≈ 17 %) | El cliente típico |
| Pedidos (2) | **+2,06** | +0,50 | Muy pocos pedidos: la mayor fuente de riesgo |
| Pedidos × devoluciones | +0,84 | +1,34 | Una devolución pesa más en quien compra tan poco |
| Gasto total (₹18.244) | +0,78 | +2,12 | Gasto muy bajo: suma riesgo |
| Valor promedio (₹9.122) | +0,18 | +2,30 | Casi neutro |
| Devoluciones (1) | **−0,72** | **+1,58** | Una sola devolución es menos que el promedio: por sí sola baja el riesgo |
| **Total** | | **+1,58** | p = 1 ÷ (1 + e^(−1,58)) = **0,83** |

- **Motivo principal:** el término que más suma, *Pedidos* (+2,06), así que la campaña es **reactivación**.
- **El contrafactual** se lee en la misma escala. Con 3 pedidos, la barra de pedidos casi no cambia (+2,06 → +2,02)
  y el gasto baja un poco (+0,78 → +0,71). El salto lo da la **interacción pedidos × devoluciones**, que pasa de
  **+0,84 a −0,74**: para el modelo, una devolución en quien tiene 2 pedidos es una señal fuerte de riesgo, y con 3 deja
  de serlo. El total queda en **−0,12 log-odds**, es decir, p = **0,47**, bajo el umbral.
- **Cuidado al leer las barras en probabilidad:** no se pueden restar puntos porcentuales. Sin la barra de pedidos,
  el total sería −0,48, es decir 38 %. No es "83 % menos algo": siempre hay que sumar en log-odds y convertir al
  final.

#### 5. Contrafactuales: qué lo sacaría del riesgo

Solo aplica si la probabilidad es ≥ 0,5. Si no, la vista dice *"Ya está bajo el umbral: no hace falta un cambio"*.

- **Titular:** el cambio más pequeño de una sola variable. Ejemplo: *"El cambio más pequeño que lo saca del riesgo:
  pedidos +1 (de 2 a 3) → probabilidad 47 %"*.
- **Botón "Aplicar este cambio en el simulador":** mueve el control a ese valor y la API recalcula. Se ve en vivo que
  el cliente queda bajo el umbral.
- **Tabla por variable:** valor actual, valor más cercano que lo deja bajo 50 %, probabilidad con ese valor y la
  mínima alcanzable moviendo solo esa variable. Muestra qué palanca funciona y cuál no:
  - **"Ninguno lo logra"** significa que, aunque esa variable recorra todo su rango de entrenamiento, la probabilidad
    nunca baja de 50 %. Le pasa casi siempre al **valor promedio por pedido**, cuyo efecto en el modelo es pequeño: al
    cliente 1340006 moverlo de ₹500 a ₹12.000 solo lo lleva, como mínimo, a 80 %. La columna "Mínima alcanzable" dice
    hasta dónde llega.
  - Las probabilidades bajo el umbral se muestran con un decimal y truncadas (0,4996 → 49,9 %), para que un valor
    apenas debajo del umbral no aparezca como "50 %".
- **Dos variables a la vez:** la API toma las dos variables que más mueven la probabilidad y busca la combinación
  más cercana al cliente. Muchas veces esa combinación deja una de las dos igual, es decir, el cambio de una sola
  variable sigue siendo el mínimo. En ese caso la vista lo dice ("no aparece nada más cercano: lo mínimo sigue siendo
  cambiar solo pedidos de 2 a 3") en lugar de mostrar un cambio "de 1 a 1". Si ambas cambian, muestra las dos.
- **Uso en el negocio:** el contrafactual es la **meta de la campaña**, por ejemplo "lograr un pedido más". No
  garantiza que el cliente se quede.

#### 6. Transparencia

Dos desplegables al final:

- **"Ver la petición y la respuesta de la API":** el JSON exacto enviado a `POST /explicar` y las respuestas de
  `/explicar`, `/contrafactuales` y `/clientes/{id}`. Sirve para mostrar en la sustentación que el tablero realmente
  llama a la API.
- **"Qué modelo está respondiendo" (`GET /modelo`):** modelo EBM; sus 4 variables; las 3 retiradas por fuga;
  ROC-AUC de 0,780 en validación cruzada y 0,781 en test; hiperparámetros y versiones de las librerías.

### Recorridos sugeridos

1. **El caso del PPT.** Abre "Riesgo alto por pocos pedidos" y presiona "Aplicar este cambio": la probabilidad pasa de
   83 % a 47 % con un solo pedido más.
2. **El valor.** Abre "Alto valor en riesgo" (CLV ₹521 mil, pérdida esperada ₹351 mil):
   - **Baja las devoluciones** de 10 a 6: la probabilidad cae a 46 % y la pérdida esperada a unos ₹240 mil, porque las
     devoluciones no cambian el gasto ni el CLV.
   - **Sube los pedidos:** la probabilidad también baja, pero el CLV estimado sube y la pérdida esperada puede quedar
     igual o subir. Retener al cliente vale más cuanto más compra.
3. **Cuándo falla.** Abre "Se escapó" y "Falsa alarma" y lee las explicaciones: el modelo solo ve pedidos, gasto y
   devoluciones.
4. **Desde la vista 1.** Selecciona un cliente en la lista y llega aquí con sus datos cargados.

### Relación con las rúbricas

| Rúbrica | Qué cubre la vista |
|---|---|
| Aprendizaje Automático: caso aplicado (10 %) | Predicciones sobre casos concretos, qué variables pesan, por qué acierta o falla y cómo lo usaría quien decide |
| Almacenamiento: despliegue y consumo (20 %) | Modelo publicado mediante API y consumido desde el dashboard, con la petición y la respuesta visibles |
| Visualización: dashboard interactivo (30 %) | Simulador what-if, botón que aplica el contrafactual y detalle bajo demanda |

### Limitaciones

- **Explicaciones y contrafactuales describen al modelo**, no causas reales: un cliente no se queda solo porque se le
  pida un pedido más.
- **El CLV del simulador es una estimación** (proporcional al gasto): el dataset no documenta cómo se calculó, así que
  no se puede recalcular exactamente.
- **La API no tiene autenticación ni HTTPS:** es una demostración.
- **Si la instancia EC2 está apagada,** esta vista no funciona: muestra el error y hay que encender la instancia.

---

## Vista 3 · Efecto de las variables

### Para qué existe

La vista 2 explica **un punto**: el cliente tal como está, o con un cambio. La vista 3 muestra **todo el recorrido**:
cómo cambia la probabilidad cuando una variable va de su mínimo a su máximo, y cómo se combinan pedidos y
devoluciones. Responde preguntas de negocio:

- ¿Cuántos pedidos necesita un cliente para salir del riesgo?
- ¿Cuánto daño hace cada devolución?
- ¿Sirve subir el ticket promedio?

Es la versión interactiva de las funciones de forma del EBM que aparecen en el notebook `03_xai`. La diferencia es
que aquí **se calculan en vivo con la API** y sobre el cliente que el usuario elija.

### Endpoint de la API que usa

Solo **`POST /predecir`**, en lotes de hasta 1.000 clientes "inventados": copias del cliente base donde cambia una
variable o una combinación de dos. Por cada configuración del cliente base se hacen unas **1.340 predicciones**:

| Bloque | Predicciones |
|---|---|
| Cliente base | 1 |
| Curva de pedidos (1 a 120) | 120 |
| Curva de devoluciones (0 hasta el número de pedidos, máximo 10) | hasta 11 |
| Curva de valor promedio (₹500 a ₹12.000) | 47 |
| Mapa pedidos × devoluciones (combinaciones válidas) | 1.155 |

Todo tarda unos segundos y queda en caché: volver a un cliente base ya visto es instantáneo. Si la API falla, se
muestra el error, sin respaldo.

### Secciones

#### 1. Cliente base

- **Tres controles:** pedidos (1 a 120), devoluciones (0 a 10) y valor promedio (₹500 a ₹12.000, en pasos de ₹250).
  Por defecto: 20 pedidos, 3 devoluciones y ₹6.000.
- **Botón "Usar el cliente X de la ficha":** carga los valores del cliente abierto en la vista 2, con el valor promedio
  redondeado al paso de ₹250. El encabezado dice "tomado del cliente X" hasta que se mueva un control.
- Si se eligen más devoluciones que pedidos, se usan tantas devoluciones como pedidos: la API no acepta lo contrario.

#### 2. Las tres curvas

- **Qué son:** cada curva mueve **una** variable y deja las otras fijas en el cliente base. La línea gris es el umbral
  de 50 % y el punto marca dónde está el cliente base.
- **El gasto se recalcula** como pedidos × valor promedio, igual que en el modelado. Por eso la curva de pedidos y la
  de valor promedio incluyen también el efecto del gasto: muestran lo que pasaría en la realidad si el cliente
  comprara más, no el término aislado del modelo.
- **La línea va en escalones** porque el EBM aprende funciones por tramos ("de 8 a 12 pedidos, suma tanto"). Por eso a
  veces sube un poco al aumentar los pedidos: son saltos pequeños de la función aprendida, no un error.
- **El título** resume la vista para el cliente base, por ejemplo: *"Para este cliente (probabilidad 26 %), los
  pedidos mueven el riesgo de 85 % a 6 % y las devoluciones entre 11 % y 61 %; el valor promedio casi no lo cambia
  (3 %)"*.

| Curva | Qué muestra (cliente por defecto) | Lectura |
|---|---|---|
| **Pedidos** | De 85 % con 1 pedido a 6 % con 120. Si el cliente base está en riesgo, una anotación marca desde cuántos pedidos baja de 50 % | La palanca más fuerte: más pedidos, menos riesgo |
| **Devoluciones** | De 11 % con 0 a 61 % con 10 | Cada devolución sube el riesgo. Con pocos pedidos el efecto es brutal: al cliente 1340006 (2 pedidos) lo lleva de 13 % sin devoluciones a 100 % con 2 |
| **Valor promedio** | Solo 3 puntos de diferencia entre ₹500 y ₹12.000 | Casi no influye: subir el ticket promedio no reduce el riesgo |

#### 3. Mapa pedidos × devoluciones

- **Qué muestra:** la probabilidad de **cada combinación válida** de 1 a 120 pedidos y 0 a 10 devoluciones, con el
  valor promedio del cliente base.
  - **Un solo color (azul) en tonos:** más claro = menos probabilidad de churn; más oscuro = más probabilidad.
  - **Celdas vacías** (arriba a la izquierda): más devoluciones que pedidos, algo que la API rechaza.
  - **La X blanca** marca al cliente base.
- **La frontera** (línea naranja en escalera): para cada número de devoluciones, el mínimo de pedidos con el que el
  cliente queda bajo 50 %. A su derecha el cliente queda bajo el umbral; a su izquierda, en riesgo. El hover dice el
  número exacto. Es la única marca de otro color, para que se distinga sobre los tonos de azul.
- **Título (el hallazgo):** *"Pedidos y devoluciones se combinan: sin devoluciones basta 1 pedido para quedar bajo
  50 %; con 10 devoluciones hacen falta 25"*. Con valor promedio de ₹6.000 la frontera es:

  | Devoluciones | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
  |---|---|---|---|---|---|---|---|---|---|---|---|
  | Pedidos mínimos para quedar bajo 50 % | 1 | 3 | 6 | 8 | 12 | 13 | 15 | 19 | 21 | 23 | 25 |

- **Por qué importa:** es el término de **interacción** del modelo (pedidos × devoluciones, el 19 % de la importancia
  del EBM) hecho visible. Una devolución no pesa igual en todos: en quien compra poco es una alarma, en quien compra
  mucho casi no importa. Es la misma razón por la que, en la vista 2, al cliente 1340006 le bastaba **un** pedido más
  para salir del riesgo.
- **Uso en el negocio:** da una regla simple para la campaña de posventa. Un cliente con 5 devoluciones necesita al
  menos 13 pedidos para dejar de estar en riesgo; si tiene menos, es prioridad para el equipo de servicio.

### Recorridos sugeridos

1. **Por defecto.** Lee el título del mapa y pasa el cursor por la frontera.
2. **Desde la ficha.** En la vista 2 abre "Riesgo alto por pocos pedidos", ven aquí y presiona "Usar el cliente
   1340006": la X queda a la izquierda de la frontera, en tono oscuro, a un pedido de cruzarla.
3. **El ticket promedio.** Mueve el valor promedio de ₹500 a ₹12.000: la curva casi no cambia y la frontera apenas se
   mueve.

### Relación con las rúbricas

| Rúbrica | Qué cubre la vista |
|---|---|
| Visualización: dashboard interactivo (30 %) | Exploración del comportamiento del modelo con controles y detalle en el hover |
| Visualización: construcción del mensaje (20 %) | Títulos calculados con el hallazgo y la frontera dibujada como anotación |
| Aprendizaje Automático: caso aplicado (10 %) | Qué variables pesan y cómo, sobre el cliente elegido |
| Almacenamiento: despliegue y consumo (20 %) | Más de 1.300 predicciones por configuración servidas por la API |

### Limitaciones

- **Describe al modelo, no causas:** que más pedidos bajen el riesgo no significa que pedirle un pedido a un cliente
  lo vaya a retener.
- **Las variables no se mueven solas en la realidad:** un cliente con más pedidos probablemente también tiene otro
  valor promedio. Las curvas aíslan cada variable para entender al modelo.
- **Fuera del rango de entrenamiento** (más de 120 pedidos o 10 devoluciones) el EBM repite el valor del extremo; por
  eso los controles no van más allá.
