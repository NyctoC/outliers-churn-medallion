# Bitácora de decisiones del EDA

> Cada decisión de `notebooks/01_eda_calidad.ipynb` queda aquí con su evidencia, para justificarla en el documento
> final y para que el modelado (`02_modelado.ipynb`) y la API apliquen lo mismo. Las reglas deterministas se
> implementan en `src/churn/features.py` (`crear_pipeline_limpieza()`).

**Datos analizados:** `churn_gold.customer_360` (tabla prevista para el modelado) y las 6 tablas de `churn_silver`
(diagnóstico de calidad) · **Fecha de corte:** 2026-07-31, última modificación del dataset en Kaggle, versión 2
(consultada el 2026-11-02) · **Partición:** 70/30 estratificada por `churn`, semilla 42, ordenando antes por `customer_id`
(`data/particion.parquet`).

## Reglas del pipeline de limpieza

Ninguna regla elimina clientes ni corrige valores, y ninguna aprende de los datos. `customer_360` pasa de 70 a 68
columnas: se agrega 1 y se quitan 3.

| Regla | Problema | Dimensión | Acción |
|---|---|---|---|
| 1 | `tenure_months` no cuadra con `signup_date` | Consistencia | Agrega `antiguedad_meses`, calculada desde `signup_date`, y conserva ambas columnas |
| 2 | `last_payment_date` posterior al corte | Temporalidad | Descarta `last_payment_date` y `payment_date_in_future` |
| 3 | `summary_total_orders` no coincide con `orders_n` | Consistencia | Descarta `summary_vs_orders_mismatch` |

## Hallazgos heredados de la capa de plata (handoff)

| # | Hallazgo | Evidencia | Dimensión | Decisión | Sección | Se decide con |
|---|---|---|---|---|---|---|
| 1 | `tenure_months` no cuadra con `signup_date` | 89,36 % de clientes (`flag_tenure_no_cuadra_con_signup_date`); correlación 0,0016 | Consistencia | Regla 1. Ninguna medida se trata como la verdadera | 3.4 / 3.7 | Todos los datos (regla lógica) |
| 2 | `last_payment_date` posterior al corte | 41,66 % de clientes (`payment_date_in_future`); cerca de 8,3 % de clientes en cada mes de 2026 | Temporalidad | Regla 2. No se corrige ni se calculan días desde el último pago | 3.6 / 3.7 | Todos los datos (regla lógica) |
| 3 | Pedidos devueltos sin motivo; `return_reason` vacío | 73,4 % vacío, pero 666.992 pedidos no aplican. Faltante real: 66.792 pedidos (6,68 %) | Completitud | Sin regla: la columna no está en `customer_360` | 3.1 | Todos los datos |
| 4 | `summary_total_orders` ≠ `orders_n` | 99,3 % de clientes (`summary_vs_orders_mismatch`); correlación −0,0015; 67.419 clientes sin pedidos en `orders` tienen pedidos en `customer_summary` | Consistencia | Regla 3. Se conservan las columnas de `customer_summary` y `orders_*`, sin mezclarlas. El grupo a usar se decidió después de la auditoría (decisión 28) | 3.4 / 3.7 / 5.2 / 5.3 | Calidad: todos los datos. Grupo a usar: solo train |
| 5 | Sin pedidos / sin tickets → variables derivadas en NULL | 13,5 % / 74,1 % (`has_orders`, `has_tickets`). Faltantes reales en `customer_360`: 0 | Completitud | Se conservan, sin eliminar clientes ni rellenar valores. Si un modelo no admite nulos, su pipeline define cómo representarlos | 3.1 | Ajuste solo con train (modelado) |
| 6 | `churn_risk_score` y `customer_segment` pueden derivarse de la etiqueta | `churn` es exactamente `churn_risk_score >= 60` (AUC 1,0000). `customer_segment` se reproduce en todos los clientes con una regla sobre otras columnas, hallada con un árbol de decisión (AUC 0,8123). Agregado a las 52 variables sin `customer_summary`, sube su AUC de 0,4990 a 0,8093 | Fuga | Se excluyen ambas: el puntaje por fuga directa; el segmento porque no aporta nada propio y reintroduce señal | 5.3 | Solo train |
| 7 | `first_name`, `country` constantes; `last_name` código único | Excluidas en oro | — | Excluidas | — | — |

## Decisiones nuevas del EDA

| # | Hallazgo | Evidencia | Dimensión / sección | Decisión | Justificación |
|---|---|---|---|---|---|
| 8 | Sin duplicados | Sin llaves duplicadas ni clientes idénticos en `customer_360` | Duplicidad / 3.2 | Sin regla | No hay nada que limpiar |
| 9 | Valores conformes | 34 variables revisadas sin incumplimientos; 20 categóricas sin variantes | Conformidad / 3.3 | Sin regla | No hay nada que limpiar |
| 10 | `signup_date` no es coherente con la actividad | Primer pedido anterior al registro en 58,22 % de los clientes con pedidos; último pedido en 31,06 %; último pago en 1,45 % de los clientes | Consistencia / 3.4 | No se trata como dato primario | Las fechas se contradicen y no se sabe cuál es correcta |
| 11 | `city` y `state` no corresponden | Coinciden en 12,56 % de los clientes | Consistencia / 3.4 | Se conservan, sin variables geográficas combinadas | No se pueden interpretar juntas como una ubicación |
| 12 | `tickets_last_year_max` y `tickets_n` difieren | Coinciden en 11,19 % de los clientes con tickets | Consistencia / 3.4 | Se conservan, sin regla | La documentación no aclara si miden lo mismo |
| 13 | `escalated` e `issue_status` no son coherentes | 18.480 tickets con estado `Escalated` y `escalated` falso | Consistencia / 3.4 | Ninguna está en `customer_360`. `tickets_escalated_n` se conserva, sin regla | No se puede saber cuál es correcta |
| 14 | Atípicos según la regla de 1,5 × IQR | 19 variables, explicadas por valores frecuentes, conteos o colas | Precisión / 3.5 | Se conservan, sin eliminar ni recortar. Si un modelo es sensible a las colas, la transformación se decide en el modelado, solo con train | Ninguno se puede identificar como error |
| 15 | `purchase_frequency` sin unidad documentada | Mediana 1,99; máximo 116,75; el diccionario no indica la unidad | Precisión / 3.5 | Se conserva, sin atribuirle una unidad de tiempo | No se puede juzgar si los valores son plausibles |
| 16 | Valor promedio por pedido en escalas distintas | Mediana de 6.239,45 en `average_order_value` y 58.149,94 en `orders_amount_avg` | Precisión / 3.5 | Se conservan, sin mezclarlas ni convertir una a la escala de la otra | Una no puede reemplazar a la otra |
| 17 | `refund_amount` mayor que `total_spent` | 103 clientes (0,0206 %); las otras 10 relaciones revisadas se cumplen | Precisión / 3.5 | Se conservan, sin regla | Son pocos casos y no se sabe cuál columna está mal |
| 18 | `refund_amount` y `last_payment_status` se contradicen | 33.503 de 40.117 clientes con reembolso no tienen estado `Refunded`; 92,04 % de los `Refunded` tiene `refund_amount` en 0 | Precisión / 3.5 | Se conservan, sin regla | No se puede saber cuál es correcta |
| 19 | La recencia y la antigüedad usan fechas distintas | `days_since_last_order` se mide contra 2026-05-24, y la antigüedad calculada contra 2026-07-31 | Temporalidad / 3.6 | `days_since_last_order` se conserva sin recalcular | Se documenta contra qué fecha se mide cada una |
| 20 | No se sabe cuándo ocurrió el abandono | Ninguna fecha lo indica | Temporalidad / 3.6 | Partición aleatoria y estratificada, no temporal | No evita que una variable se haya medido después del abandono ni permite evaluar con clientes futuros; el riesgo de fuga se audita en la sección 5.3 |
| 21 | La partición dependía del orden de las filas | Con la misma semilla y otro orden de filas, solo 70 % del `train` coincidía; ordenando por `customer_id`, 3 órdenes distintos dan la misma partición | Partición / 4 | Se ordena por `customer_id` antes de partir | Athena no garantiza el orden de las filas, y todo el equipo debe usar los mismos clientes en cada conjunto |
| 22 | Variables asimétricas | 14 de 46 numéricas con asimetría alta, todas hacia la derecha | Análisis univariado / 5.1 | No se transforman en el pipeline de limpieza; se decide en el modelado según el modelo | Depende del modelo, y muchas tienen ceros, así que un logaritmo simple no serviría |
| 23 | Variables casi uniformes | 21 de 46 numéricas con `cv_frecuencias` menor a 0,2 | Análisis univariado / 5.1 | Se conservan | Su forma no indica por sí sola si se relacionan con `churn` |
| 24 | Categorías poco frecuentes | Ninguna por debajo de 1 %; la menor es `Other` en `gender` (1,97 %) | Análisis univariado / 5.1 | No se agrupan | Ninguna tiene tan pocos clientes como para requerirlo |
| 25 | 8 variables con relación fuerte con `churn` | AUC univariado de 0,55 o más, todas de Resumen de cliente; la mayor es `last_purchase_days` (0,8647) | Relación con `churn` / 5.2 | No se eligen todavía; se auditan en la sección 5.3 | Una relación tan fuerte puede indicar fuga de información |
| 26 | 53 variables sin relación individual | AUC menor a 0,51; fuera de Resumen de cliente, la tasa cambia como máximo 2 puntos porcentuales | Relación con `churn` / 5.2 | No se descartan todavía | El AUC univariado no mide combinaciones de variables |
| 27 | `has_orders` y `has_tickets` casi no cambian el churn | Diferencias de 0,15 y 0,05 puntos porcentuales | Relación con `churn` / 5.2 | Se conservan | Indican por qué hay nulos estructurales |
| 28 | Toda la señal está en `customer_summary` | Sin esa tabla: AUC 0,4990 y PR-AUC 0,2064 (52 variables). Solo con sus 9 variables, sin puntaje ni segmento: AUC 0,9999 | Fuga / 5.3 | El escenario principal usa sus variables, sin puntaje ni segmento. El escenario con las variables de fuera de `customer_summary` se reporta como comparación. La decisión 30 los deja en 7 y 51 variables. Revisada en las decisiones 38 y 43 | Están disponibles y Kaggle presenta la tabla como lista para modelar. El AUC es tan alto porque `churn` parece calculado a partir de estas variables |
| 29 | El puntaje sale de 3 variables | `last_purchase_days`, `return_rate` y `purchase_frequency` lo explican con R² de 0,9994 y error de 0,22 sobre 100; dan AUC de 0,9999 para `churn`. Las otras 6 variables de `customer_summary` dan AUC de 0,7766 | Fuga / 5.3 | Sustenta las decisiones 28 y 38 | Apoya la cadena 3 variables → puntaje → `churn`. Sin el código del generador no queda demostrado |
| 30 | Variables redundantes | `loyalty_points` tiene correlación de 1,00 con `total_spent`, igual que `orders_status_returned_n` con `orders_returned_flag_n`. `lifetime_value` tiene correlación de 0,97 con `total_spent` y parcial de −0,002 con `churn`. Sin ellas: AUC 0,9999 con 7 variables y 0,4990 con 51 | Multivariado / 5.4 | No se usan como predictoras (`COLUMNAS_REDUNDANTES`). El escenario principal queda en `VARIABLES_ESCENARIO_PRINCIPAL`. El modelo final usa 4 de ellas (decisión 38) | No se pierde señal. `lifetime_value` se conserva en `customer_360` para priorizar clientes por valor |
| 31 | Multicolinealidad moderada restante | VIF máximo de 7,61 en `total_spent`, porque el gasto es el producto de `summary_total_orders` y `average_order_value` | Multivariado / 5.4 | Se conservan; se revisa en el modelado si afecta la lectura de coeficientes | Importa sobre todo para los modelos lineales |
| 32 | Ratios y tendencias no aportan | 4 variables nuevas con AUC univariado de 0,5003 a 0,5034; al agregarlas, la comparación da AUC 0,4975 | Propuestas / 7 | No se proponen más variables en esta etapa | Tampoco se necesitan en el escenario principal |
| 33 | Probabilidades casi binarias en el escenario principal | Solo 2,04 % de los clientes entre 0,1 y 0,9 | Propuestas / 7 | Priorizar combinando probabilidad y `lifetime_value`, y revisar la calibración en el modelado. Revisada en la decisión 41 | En la práctica, el orden lo definirá sobre todo `lifetime_value` entre los clientes de riesgo alto |
| 34 | La documentación del dataset no explica la etiqueta | Kaggle presenta `customer_summary` como "ML-ready", pero no indica cómo se calcularon `churn_risk_score` ni `churn`, ni advierte sobre fuga | Fuga / 5.3 | La exclusión de `churn_risk_score` se sustenta en los datos | La documentación no la confirma ni la descarta |
| 35 | La regresión logística también separa las clases casi perfectamente | ROC-AUC y PR-AUC de 1,0000 (redondeados) con las 7 variables | Multivariado / 5.4 | Comparar modelos también por interpretabilidad y parsimonia. Revisada en la decisión 40 | Habrá poco margen para elegir un modelo por rendimiento |
| 36 | `tickets_satisfaction_avg` y `tickets_satisfaction_min` son muy parecidas | Correlación de 0,96 | Multivariado / 5.4 | Se conservan; se revisa en el modelado si un modelo lineal lo requiere | Su correlación es alta, pero no son iguales |
| 37 | Interpretabilidad pedida en la retroalimentación del profesor | Coeficientes de regresión logística, importancia en modelos de árboles y valores SHAP | Propuestas / 7 | En el escenario principal, no leer los resultados como causa del abandono. En el de comparación, no interpretarlos como factores. Revisada en la decisión 42 | En el principal, la etiqueta parece calculada a partir de las variables. En el de comparación, no hay señal |

## Señal predictiva

| Prueba | Resultado | Conclusión |
|---|---|---|
| Referencias (aleatorio, tasa por grupo) | ROC-AUC de 0,5000 a 0,5011 | Las categorías por sí solas no superan el azar |
| Referencia con `last_purchase_days` | ROC-AUC 0,8647 y PR-AUC 0,6776 | Era la referencia del escenario principal con 7 variables. Revisada en la decisión 39 |
| Línea base pública (Kaggle) | Notebook End-to-End ML del autor, con XGBoost y partición 80/20: ROC-AUC 0,5035 y PR-AUC 0,2088 (consulta: 2026-11-05). De `customer_summary` solo toma `churn` para modelar. Los otros 3 usan otro archivo | Solo este es comparable, como referencia. Coincide con el escenario de comparación (AUC 0,4990) |
| Criterio de selección | Mayor ROC-AUC en validación cruzada; empate si la diferencia es menor a 0,001; luego interpretabilidad y parsimonia, y por último calibración | Se aplica en cada escenario |
| Prueba de permutación (100 permutaciones, muestra de 30.000) | Principal: AUC 0,9998, p-valor 0,0099, el menor posible. Comparación: AUC 0,4979, p-valor 0,7030 | El escenario principal tiene señal, y el de comparación no muestra señal |

## Decisiones revisadas en el modelado

Decisiones del EDA que `02_modelado.ipynb` y `03_xai.ipynb` cambiaron con evidencia nueva, validadas con el equipo el
2026-11-10. Las filas de arriba se conservan como registro del EDA.

| # | Revisa | Evidencia | Sección | Decisión | Justificación |
|---|---|---|---|---|---|
| 38 | 28, 29 y 30 | Con las 7 variables la logística da ROC-AUC de 1,0 en entrenamiento y validación, y 0,5020 con la etiqueta permutada. `last_purchase_days`, `return_rate` y `purchase_frequency` bastan para llegar a 1,0000. Sin ellas, el random forest baja de 0,9998 a 0,7651 | 02: 5.6 / 5.7. 03: 6.2 | Se retiran por fuga (`COLUMNAS_FUGA_ETIQUETA`). El modelo final usa `summary_total_orders`, `total_spent`, `average_order_value` y `total_returns` (`VARIABLES_MODELO_FINAL`). `VARIABLES_ESCENARIO_PRINCIPAL` conserva las 7 del EDA | Con ellas el modelo reproduce la regla con la que parece construida la etiqueta, y su ROC-AUC no mide la capacidad de predecir el abandono. Al agregarlas al EBM final concentran el 99,2 % de la importancia. Sin el código del generador no queda demostrado |
| 39 | Referencia con `last_purchase_days` | La variable ya no está en el modelo final | 02: 5.7 | El escenario principal se contrasta con el azar (ROC-AUC de 0,50 y PR-AUC de 0,207) | No se puede exigir superar una referencia hecha con una variable retirada por fuga |
| 40 | 35 | Con las 4 variables, las logísticas quedan 0,009 de ROC-AUC por debajo del mejor modelo. EBM, XGBoost y random forest empatan | 02: 6.3 | Se elige el EBM (ROC-AUC de 0,7801 en validación cruzada y 0,7811 en `test`) | Ya no hay separación casi perfecta. Entre los empatados decide la interpretabilidad, como fija el criterio de selección |
| 41 | 33 | Al contactar al 10 % de los clientes, priorizar por valor en riesgo captura el 25,9 % del valor perdido pero solo el 11,1 % del churn. Solo con la probabilidad captura el 35,0 % del churn | 02: 9.1 | Se prioriza solo con la probabilidad de churn y no se revisa la calibración | El valor en riesgo termina ordenando casi solo por `lifetime_value`, que no se relaciona con el churn, y no responde al objetivo de reducir el abandono. Para ordenar por probabilidad no hace falta calibrarla |
| 42 | 37 | El modelo final es un EBM, interpretable por construcción | 03 | Las explicaciones salen solo del EBM, sin comparar con coeficientes, importancia de árboles ni SHAP | Explican el modelo que se usa. Sigue sin poder leerse como causa del abandono |
| 43 | 28 | Ningún modelo supera el azar en el escenario de comparación | 02: 6.1 | Se deja de usar desde la optimización de hiperparámetros | Ya cumplió su función de mostrar que fuera de `customer_summary` no hay señal |
