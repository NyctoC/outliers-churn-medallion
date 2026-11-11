# Bitácora de decisiones del modelado y la explicabilidad

> Cada decisión de `notebooks/02_modelado.ipynb` y `notebooks/03_xai.ipynb` queda aquí con su evidencia, para
> justificarla en el documento final y para que la API y el tablero apliquen lo mismo. Parte de las decisiones de
> `docs/eda_decisiones.md`, y las que cambiaron allí están en la sección "Decisiones revisadas en el modelado"
> (decisiones 38 a 43 del EDA).

**Datos:** `churn_gold.customer_360` con el pipeline de limpieza del EDA (`features.crear_pipeline_limpieza()`) ·
**Partición:** la del EDA (`data.cargar_particion`), 350.000 clientes en `train` y 150.000 en `test`, tasa de churn
de 20,70 % en ambos · **Semilla:** 42 · **Resultados compartidos:** `data/modelado/` en el bucket
(`data.descargar_modelado()` y `data.subir_modelado()`).

## Validación y referencias

| # | Decisión | Evidencia | Sección de 02 |
|---|---|---|---|
| 1 | Validación cruzada estratificada por `churn`, 5 folds, solo sobre `train` | Cada fold entrena con 280.000 clientes y valida con 70.000, con 20,70 % de churn en todos. Ningún cliente queda a la vez en entrenamiento y validación | 2 |
| 2 | Ordenar `train` por `customer_id` antes de generar los folds | Sin ordenar, al cambiar el orden de las filas solo coincide cerca del 20 % de cada validación. Ordenando, coinciden todas | 2 |
| 3 | `test` se usa una sola vez, con el modelo final | Ninguna decisión de variables, hiperparámetros ni modelo usa `test` | 8 |
| 4 | Referencias: azar, tasa por `membership_tier`, tasa por `occupation` × `education` y solo `last_purchase_days` | ROC-AUC de 0,5000, 0,5003, 0,5002 y 0,8647. Desde la decisión 38 del EDA, el escenario principal se contrasta con el azar | 3 |

## Preparación de las variables

| # | Decisión | Evidencia | Sección de 02 |
|---|---|---|---|
| 5 | Una preparación por tipo de modelo, dentro del pipeline y ajustada solo con el entrenamiento de cada fold | Logística: nulos a 0, one-hot sin la primera categoría y estandarización. Random forest y XGBoost: categóricas a enteros y nulos sin cambios. EBM: sin cambios | 5.1 / 5.5 |
| 6 | Los nulos estructurales de la logística se rellenan con 0 | Frente a la mediana, la probabilidad cambia como máximo 0,0030 (media 0,00033), porque `has_orders` y `has_tickets` ya están entre las variables | 5.2 |
| 7 | Se estandarizan las numéricas de la logística y no se transforman las asimétricas | Con 7 variables, el ROC-AUC casi no cambia (1,00000 y 0,99998), pero sin estandarizar necesita hasta 1.729 iteraciones en lugar de 23. En la comparación no converge en ningún fold | 5.3 |
| 8 | Se conservan las variables colineales y se interpretan juntas como el efecto del gasto | Sin penalización, los coeficientes de `total_spent`, `summary_total_orders` y `average_order_value` varían entre folds y uno cambia de signo. Con ridge se estabilizan, pero su reparto depende de C | 5.4 |

## Fuga de la etiqueta

| # | Decisión | Evidencia | Sección de 02 |
|---|---|---|---|
| 9 | El ROC-AUC de 1,0 con 7 variables no es sobreajuste ni un error de validación | Entrenamiento y validación dan 1,0000. Con la etiqueta permutada cae a 0,5020 | 5.6 |
| 10 | Se retiran `last_purchase_days`, `return_rate` y `purchase_frequency` (decisión 38 del EDA) | Las 3 dan el mismo 1,0000 que las 7. Lasso las conserva junto con `summary_total_orders` hasta C = 0,0001. Sin ellas, el random forest baja de 0,9998 a 0,7651 | 5.6 / 5.7 |
| 11 | Se conservan `total_returns` y `summary_total_orders`, aunque permiten reconstruir `return_rate` | Su cociente tiene correlación de 1,0000 con `return_rate`. Las devoluciones son de interés para el negocio | 5.7 |

## Desbalance

| # | Decisión | Evidencia | Sección de 02 |
|---|---|---|---|
| 12 | No se remuestrea | Con 7 variables, las 24 configuraciones quedan a menos de 0,001 de ROC-AUC de no remuestrear. Con 4 variables, la ventaja de random undersampling (0,0057) desaparece al regularizar los árboles (0,7791 frente a 0,7789 con `min_samples_leaf` = 500) y empeora el Brier (0,179 frente a 0,124) | 4 / 5.8 |
| 13 | Remuestrear tampoco le da señal al escenario de comparación | Todas las estrategias quedan entre 0,497 y 0,502 de ROC-AUC | 4.2 |

## Modelos y selección

| # | Decisión | Evidencia | Sección de 02 |
|---|---|---|---|
| 14 | Candidatos: logística sin penalización, logística ridge, random forest, XGBoost y EBM | Con hiperparámetros por defecto, en el principal: EBM 0,7799, XGBoost 0,7753, logísticas 0,7707 y random forest 0,7099 | 6.1 |
| 15 | El EBM no se entrena en el escenario de comparación, y ese escenario se deja de usar desde la sección 6.2 (decisión 43 del EDA) | Ningún modelo supera el azar (0,4975 a 0,5005). Con 51 variables el EBM es muy costoso y no aportaría información | 6.1 |
| 16 | Optuna maximiza el ROC-AUC promedio de los 5 folds, solo en el principal | Ensayos: 15 en la logística ridge, 25 en el random forest, 40 en XGBoost y 10 en el EBM | 6.2 |
| 17 | Criterio de selección: mayor ROC-AUC. Una diferencia menor a 0,001 es empate, y lo decide la interpretabilidad | Es el criterio del EDA (sección "Señal predictiva"). Orden de interpretabilidad: logística ridge, logística sin penalización, EBM, XGBoost y random forest | 6.3 |
| 18 | **Modelo final: EBM** (decisión 40 del EDA) | EBM 0,7802, XGBoost 0,7799 y random forest 0,7797 empatan. Las logísticas quedan 0,009 por debajo. El EBM tiene el mayor ROC-AUC, o empata con XGBoost, en los 5 folds | 6.3 |

Hiperparámetros del EBM: `interactions` = 1, `learning_rate` = 0,0340, `max_leaves` = 2 y `min_samples_leaf` = 4.

## Evaluación

| # | Decisión | Evidencia | Sección de 02 |
|---|---|---|---|
| 19 | Solo métricas que no dependen de un umbral: ROC-AUC, PR-AUC, ganancia acumulada y lift. Sin matriz de confusión | El modelo se usa para ordenar clientes por riesgo, no para clasificarlos con un umbral fijo | 7 |
| 20 | El modelo mantiene su desempeño en `test` | ROC-AUC de 0,7811 en `test` frente a 0,7801 en validación cruzada, y PR-AUC de 0,5963 frente a 0,5958. El churn capturado difiere como máximo 0,13 puntos | 8 |
| 21 | Lectura de la ganancia acumulada en `test` | Contactar al 10 % de mayor riesgo captura el 35,0 % del churn (lift de 3,50), al 20 % el 52,2 % y al 30 % el 63,6 % | 8 |

## Uso en el negocio

| # | Decisión | Evidencia | Sección |
|---|---|---|---|
| 22 | Se prioriza solo con la probabilidad de churn, sin calibrarla (decisión 41 del EDA) | Al 10 % de los clientes, el valor en riesgo captura el 11,1 % del churn, casi lo mismo que el azar, y la probabilidad sola el 35,0 %. En ese tramo el `lifetime_value` medio duplica el general, pero la tasa de churn apenas sube (23,0 % frente a 20,7 %) | 02: 9.1 |
| 23 | Campaña para los clientes con probabilidad de 0,5 o más, o con el umbral que defina el negocio, empezando por los de mayor riesgo | Con 0,5 se marca al 8,7 % de `test`, con precision de 0,763 y recall de 0,320 | 03: 4.1 / 8 |
| 24 | La campaña de cada cliente se elige según el término que más le suma riesgo | Pocos pedidos o poco gasto: reactivación. Devoluciones o la interacción: atención posventa. `average_order_value` casi nunca es el motivo principal | 03: 8 |

## Explicabilidad (03_xai)

| # | Decisión | Evidencia | Sección de 03 |
|---|---|---|---|
| 25 | Las explicaciones salen solo del EBM, sin comparar con otros métodos (decisión 42 del EDA) | El EBM es interpretable por construcción: la suma del intercepto y los términos reproduce exactamente la probabilidad del modelo | 1 / 4 |
| 26 | Importancia global de los términos | `summary_total_orders` 29,2 %, `total_returns` 29,1 %, su interacción 18,6 %, `total_spent` 14,4 % y `average_order_value` 8,7 % | 3.1 |
| 27 | Las explicaciones individuales y los contrafactuales usan el umbral de 0,5 del EBM | Es el umbral por defecto del modelo. Los clientes de ejemplo se toman de `test`, sin usarlo para decidir nada | 4 / 5 |
| 28 | En los contrafactuales se mueven `summary_total_orders`, `average_order_value` y `total_returns` dentro de su rango observado, y `total_spent` se recalcula | `total_spent` es el producto de pedidos y valor promedio (correlación de 1,0000) | 5.1 |
| 29 | El detective de sesgos audita la variable que aún guarda señal y las 3 retiradas, en el primer fold de `train` | Al agregar las 3 retiradas, el ROC-AUC llega a 1 y concentran el 99,2 % de la importancia. Quitar `summary_total_orders` casi no cambia el resultado (0,776), y quitarla junto con `total_spent` lo baja a 0,587 | 6 |
| 30 | Las explicaciones describen cómo decide el modelo, no por qué abandonan los clientes | Decisión 37 del EDA. Parte de la señal puede venir de la forma en que se construyó la etiqueta (decisión 11) | 7 |

## Modelo guardado

| # | Decisión | Evidencia | Sección de 02 |
|---|---|---|---|
| 31 | Se guarda el EBM entrenado con todo `train`, sin `test`, en `data/modelado/modelo_final/` | `modelo.joblib` y `configuracion.json` con las variables, las retiradas por fuga, los hiperparámetros, las métricas y las versiones de las librerías. El modelo cargado da las mismas probabilidades que el evaluado (diferencia máxima de 0) | 10 |
| 32 | La API recibe las 4 variables de `features.VARIABLES_MODELO_FINAL`, después de aplicar `crear_pipeline_limpieza()` | Coinciden con `variables` y `variables_retiradas_por_fuga` del `configuracion.json`. `src/churn/modelos.py` carga el modelo desde S3, predice, prioriza, explica y genera los contrafactuales igual que los notebooks | 10 |

## Limitaciones

- La etiqueta parece construida con 3 variables, y retirarlas es un supuesto. Sin el código del generador no queda demostrado (02, sección 9.2).
- Puede quedar fuga residual, así que el ROC-AUC de 0,78 puede sobrestimar la capacidad real del modelo (decisión 11).
- No se sabe cuándo ocurrió el abandono, y el modelo no se evaluó con clientes futuros (decisión 20 del EDA).
- El EBM se eligió por interpretabilidad dentro de un empate, y su búsqueda de hiperparámetros fue de solo 10 ensayos.
