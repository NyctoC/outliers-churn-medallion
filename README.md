# outliers-churn-medallion

Arquitectura **Medallion (bronce → plata → oro)** sobre **AWS S3 + Athena + Apache Iceberg** para el
*Customer Churn Prediction Dataset V2 (500K)* de Kaggle. Proyecto Integrador 1 · Maestría en Ciencia de Datos y
Analítica · Universidad EAFIT · equipo **The Outliers**.

Esta base deja los datos limpios, auditados y consolidados para el **EDA** y el modelado de churn.
También cubre la **Parte A** del Trabajo 1 (capas Medallion) del curso *Almacenamiento y Procesamiento de Grandes Datos*.

> Datos sintéticos (licencia Apache 2.0). Autor: Kuldeep Jangra. Los CSV **no** se versionan en este repo.

## Arquitectura

```mermaid
flowchart LR
    K[Kaggle: 6 CSV] -->|subida manual| B
    subgraph S3[Bucket S3]
      B[(bronze/<br/>CSV crudos)]
      S[(silver/<br/>Iceberg válidas + rechazadas)]
      G[(gold/<br/>Iceberg para EDA/BI)]
    end
    B -->|"Athena: tipado + reglas de calidad"| S
    S -->|"Athena: joins + agregaciones"| G
    G --> E[EDA / modelo / tablero]
```

| Capa | Qué contiene | Formato | Base en Athena |
|---|---|---|---|
| **Bronce** | Los 6 CSV tal cual, **todas las columnas como texto** | CSV (tabla externa) | `churn_bronze` |
| **Plata** | Por cada tabla: filas **válidas** tipadas (+ columnas `flag_*`) y filas **rechazadas** con su motivo | Iceberg / Parquet | `churn_silver` |
| **Oro** | `customer_360` (1 fila por cliente) + agregados de negocio | Iceberg / Parquet | `churn_gold` |

## Estructura del repositorio

```
outliers-churn-medallion/
├── README.md
├── docs/
│   ├── 01_aws_setup_paso_a_paso.md       # guía de la consola de AWS desde cero
│   ├── 02_conexion_aws.md                # conectarse desde Python con el usuario compartido
│   ├── reglas_de_calidad.md              # catálogo de reglas (generado) para justificar con hallazgos
│   └── comparacion_bronce_plata_oro.md   # plantilla de bytes escaneados y tiempos
├── sql/
│   ├── 00_setup/        # crea las 3 bases de datos
│   ├── 01_bronze/       # tablas externas + verificación de conteos
│   ├── 02_hallazgos/    # tabla de defectos de calidad medidos en bronce
│   ├── 03_silver/       # 6 scripts: vista de validación + válidas + rechazadas
│   ├── 04_gold/         # customer_360, orders_monthly_category, churn_by_dimension
│   ├── 05_checks/       # conteos que cuadran, motivos, banderas, comparación de capas
│   └── 99_reset/        # borra plata/oro para repetir
├── tools/
│   ├── generate_sql.py  # genera bronce/hallazgos/plata/checks desde UNA especificación
│   ├── render_sql.py    # pone tu bucket en los .sql -> sql_rendered/ (ignorado por git)
│   └── verificar_conexion.py  # comprueba .env, credenciales y Athena
├── .env.example         # plantilla de la conexión a AWS: cópiala como .env (ignorado por git)
├── notebooks/
│   └── 01_eda_calidad.ipynb   # EDA y 6 dimensiones de calidad (02_modelado y 03_xai: modelado)
├── src/churn/           # código compartido por notebooks y API
│   ├── data.py          # Athena -> caché parquet, tipos y partición train/test compartida
│   ├── eda.py           # funciones del análisis exploratorio y de calidad
│   └── features.py      # diccionario por grupo + pipeline de limpieza (reglas deterministas)
├── reports/figures/     # figuras exportadas para el documento y la presentación
├── requirements.txt
└── data/                # CSV y cachés parquet locales (ignorados por git)
```

## Cómo replicarlo

1. Configura AWS (cuenta segura, región `us-east-1`, bucket, carpetas, Athena): **`docs/01_aws_setup_paso_a_paso.md`**.
2. Descarga los 6 CSV de Kaggle y súbelos a `s3://<bucket>/bronze/<tabla>/`.
3. `python tools/render_sql.py --bucket <tu-bucket>` (solo Python 3, sin dependencias).
4. En Athena ejecuta los scripts de `sql_rendered/` **en este orden**, una sentencia a la vez:

| # | Script | Qué hace | Verificación |
|---|---|---|---|
| 1 | `00_setup/00_create_databases.sql` | Crea `churn_bronze/silver/gold` | `SHOW DATABASES` |
| 2 | `01_bronze/01_create_bronze_tables.sql` | 6 tablas externas, todo `string` | `02_bronze_sanity_checks.sql` (500K/1M/500K/500K/150K/500K) |
| 3 | `02_hallazgos/01_dq_findings.sql` | Mide los defectos y crea `dq_findings` | Revisa las 2 consultas finales del script |
| 4 | `03_silver/01_customers.sql` **primero**, luego `02`…`06` | Valida y separa válidas/rechazadas | `05_checks/01_reconciliation.sql` → `cuadra = OK` |
| 5 | `04_gold/01_customer_360.sql`, `02_…`, `03_…` | Capa de consumo | `05_checks/04_comparison_queries.sql` (sanidad) |
| 6 | `05_checks/02_reject_reasons.sql`, `03_flags_summary.sql` | Motivos de rechazo y banderas | — |

Si algo sale mal a medias: `99_reset/reset_silver_gold.sql` y borra las carpetas correspondientes en S3.

## Decisiones de diseño (léelas antes del EDA)

**1. Bronce no se toca.** Todo es texto: ningún dato se pierde ni se "arregla" por un error de tipo. Los problemas
se miden en la capa de hallazgos, no se ocultan.

**2. Rechazar vs. marcar.** En plata hay dos tipos de regla (`docs/reglas_de_calidad.md`):
- **Rechazo** = el dato es imposible o inutilizable (llave nula o repetida, fecha/número ilegible, valor fuera de
  rango físico, `customer_id` que no existe en `customers`, estado fuera del dominio). La fila va a `*_rejected` con
  `reject_reason` (puede traer varios motivos separados por `;`).
- **Bandera (`flag_*`)** = el dato es *plausible pero sospechoso* (devolución sin motivo, estado `Cancelled` con
  `returned = true`, monto que no cuadra con cantidad × precio, fechas de pago posteriores al corte…). La fila **se
  conserva** y queda marcada. Así no se descarta, por ejemplo, el ~6 % de devoluciones sin motivo ni se pierden
  clientes por inconsistencias de un generador sintético. Si en el EDA decides que una bandera debe rechazar,
  muévela de `flags` a `rules` en `tools/generate_sql.py` y regenera.

**3. Cuadre de conteos.** Cada fila de bronce cae en exactamente una de las dos tablas de plata, así que
`bronce = válidas + rechazadas` (se comprueba en `05_checks/01_reconciliation.sql`). Una tabla *puede* tener 0
rechazadas: en datos sintéticos limpios es un resultado legítimo y debe contarse así.

**4. Integridad referencial.** `customers` es la raíz. Las otras 5 tablas rechazan los `customer_id` que no existen
en `silver.customers`; por eso se ejecuta primero.

**5. Oro = varias tablas, no una sola.** Un único "mega-join" mezcla granos distintos (cliente, pedido, ticket) y
sirve mal para BI. Por eso hay:
- `customer_360`: **1 fila por cliente** (join de las 6 tablas + RFM y tendencias desde `orders` + agregados de
  tickets + indicadores de ausencia). Es la base de EDA y modelo.
- `orders_monthly_category`: agregado de negocio (mes × categoría) para el tablero y para la comparación de capas.
- `churn_by_dimension`: tasa de churn y CLV por segmento (vista "monitoreo del churn").

**6. Fuga de información.** `churn_risk_score` y `customer_segment` pasan a oro, pero **no deben usarse como
predictoras** (auditoría en la sección 5.3 de `notebooks/01_eda_calidad.ipynb`). `first_name`, `country` (constantes) y
`last_name` (código único) se omiten en oro.

**7. Fecha de corte.** Las reglas de fechas usan `DATE '2026-07-31'` (publicación de la v2 del dataset). Se cambia en
`tools/generate_sql.py` (`CUT`).

## Supuestos y limitaciones

- Las columnas se tomaron de la propuesta del proyecto, del README del dataset y del diagrama entidad-relación; la
  página de Kaggle no expone la descripción de columnas de todas las tablas. **Valida el encabezado de cada CSV**
  y `data_dictionary.xlsx` antes de ejecutar.
- Los scripts asumen fechas ISO (`YYYY-MM-DD`) y booleanos `True/False`, `Yes/No` o `1/0`. Si
  `SELECT order_date FROM churn_bronze.orders LIMIT 20` muestra otro formato, ajusta `typed_expr()` en
  `tools/generate_sql.py`. Si una columna entera llega como `3.0`, cámbiala de `int` a `dbl`.
- El proyecto no tiene fecha de abandono: `churn` es una "fotografía estática", no una predicción futura.
- SQL probado por revisión estructural, no ejecutado contra Athena desde aquí: si una sentencia falla, copia el
  mensaje de error exacto y se corrige.

## Costos

~266 MB de datos: Athena (≈ 5 USD/TB escaneado) y S3 cuestan centavos. Aun así configura un *budget* (ver guía) y
limpia al terminar.

## EDA y calidad de datos

1. Sigue **`docs/02_conexion_aws.md`**: instala las dependencias, copia `.env.example` como `.env`, pon las llaves
   y ejecuta `python tools/verificar_conexion.py`. Las credenciales viven en `.env`, **nunca en el repo**.
2. Abre `notebooks/01_eda_calidad.ipynb`. La primera ejecución lee oro y plata desde Athena y los guarda en
   `data/*.parquet`; las siguientes usan esa caché.

El notebook mide la calidad sobre todos los datos (sin relacionar las variables con `churn`), fija la partición train/test
(`data/particion.parquet`) y hace el análisis exploratorio **solo sobre train**. Las decisiones quedan en
`docs/eda_decisiones.md` y las reglas de limpieza en `src/churn/features.py`. El modelado parte de lo mismo:

```python
from churn import data, features   # con src/ en sys.path
c360 = data.normalizar_tipos(data.cargar_customer_360(), features.COLUMNAS_FECHA)
limpio = features.crear_pipeline_limpieza().fit_transform(c360)
limpio = limpio.merge(data.cargar_particion(limpio), on=features.LLAVE)   # la misma partición del EDA
train = limpio[limpio["conjunto"] == "train"].drop(columns="conjunto")
test = limpio[limpio["conjunto"] == "test"].drop(columns="conjunto")      # se evalúa una sola vez, al final

variables_principal = features.VARIABLES_ESCENARIO_PRINCIPAL   # las 7 del EDA
variables_modelo = features.VARIABLES_MODELO_FINAL             # las 4 del modelo final, sin las de la etiqueta
variables_comparacion = features.variables_escenario_comparacion(train)
```

Las variables y los criterios para el modelado están en la sección 7 del notebook.

## Referencias

Jangra, K. (2026). *Customer Churn Prediction Dataset V2 (500K)* [Conjunto de datos]. Kaggle.
https://www.kaggle.com/datasets/kuldeepjangra/customer-behavior-and-churn-prediction-dataset
