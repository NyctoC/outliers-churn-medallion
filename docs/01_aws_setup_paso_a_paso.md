# Setup de AWS paso a paso (desde cero)

> Todo se hace **a mano en la consola web de AWS**. El Trabajo 1 prohíbe infraestructura como código
> (CloudFormation, Terraform, Serverless Framework): el video debe mostrar la consola de CloudFormation
> **sin ningún stack**. Si tu cuenta tiene stacks de laboratorios anteriores, bórralos antes de grabar.

## Mapa mental: qué es cada pieza

| Servicio | Para qué lo usamos | Analogía |
|---|---|---|
| **S3** | Guardar archivos (CSV, Parquet) en un "bucket" | Un Google Drive para datos |
| **Athena** | Ejecutar SQL directamente sobre archivos en S3 | Un motor SQL sin servidor que ni prendes ni apagas |
| **Glue Data Catalog** | Guarda los nombres de bases/tablas/columnas (Athena lo usa solo) | El índice de una biblioteca |
| **Iceberg** | Formato de tabla (sobre Parquet) que Athena sabe crear y actualizar | Una tabla "de verdad" con historial |

Athena **cobra por datos escaneados** (≈ 5 USD por TB). Con ~266 MB todo el proyecto cuesta centavos.

---

## Paso 1 · Asegurar la cuenta (10 min, una sola vez)

1. Entra como usuario **root** (el correo con el que creaste la cuenta).
2. Arriba a la derecha, clic en tu nombre → **Security credentials** → **Multi-factor authentication (MFA)** →
   activa MFA con una app (Google Authenticator / Authy).
3. **Billing and Cost Management → Budgets → Create budget** → plantilla "Zero spend budget" (o un monto de 5 USD)
   con tu correo. Te avisa si algo empieza a cobrar.
4. (Recomendado) **IAM → Users → Create user** (p. ej. `camilo-admin`), permisos `AdministratorAccess`,
   activa MFA y úsalo en el día a día en vez del root. Nunca crees *access keys* para el root.

> Si tu cuenta es de **AWS Academy / Learner Lab**: usa la región `us-east-1`; los pasos son los mismos,
> pero no podrás crear usuarios IAM.

## Paso 2 · Elegir la región (¡no te la saltes!)

Arriba a la derecha, selector de región → **US East (N. Virginia) `us-east-1`**.
Todo (bucket, Athena, catálogo) debe estar en la **misma región**. Si "no ves" tus tablas, casi siempre es la región.

## Paso 3 · Crear el bucket de S3

1. Consola → busca **S3** → **Create bucket**.
2. **Bucket name**: único en todo el mundo, solo minúsculas, números y guiones.
   Ej.: `outliers-churn-medallion-<tus-iniciales>-<4 dígitos>`.
3. Región `us-east-1`. Deja **Block all public access = ON**. Versioning desactivado. Cifrado por defecto (SSE-S3). **Create bucket**.
4. Entra al bucket → **Create folder** y crea estas carpetas en la raíz:

```
bronze/
silver/
gold/
audit/
athena-results/
```

5. Dentro de `bronze/` crea **una carpeta por tabla** (Athena apunta a carpetas, no a archivos):

```
bronze/customers/
bronze/orders/
bronze/engagement/
bronze/payments/
bronze/support_tickets/
bronze/customer_summary/
```

> **No** crees subcarpetas dentro de `silver/` ni `gold/`: Athena las crea sola al ejecutar los scripts
> (una tabla Iceberg exige que su carpeta destino esté vacía).

## Paso 4 · Descargar y subir los CSV (capa bronce)

1. En Kaggle (necesitas sesión iniciada) abre el dataset y pulsa **Download** → te baja un `.zip` (~266 MB).
2. Descomprime. Deberías ver 6 CSV: `customers`, `orders`, `engagement`, `payments`, `support_tickets`,
   `customer_summary` (+ `README.md`, `data_dictionary.xlsx` y el diagrama: **no los subas**).
3. Abre el **encabezado** (primera línea) de cada CSV en un editor de texto y compara el orden de columnas con
   `sql/01_bronze/01_create_bronze_tables.sql`. Si difiere, ajusta el DDL.
4. En S3, entra a cada carpeta de `bronze/` → **Upload** → **Add files** → sube **solo** el CSV que corresponde.
   `orders.csv` es el más grande; deja la pestaña abierta hasta que termine.

> Regla de oro: **un solo tipo de archivo por carpeta de bronce**. Si subes el README o el xlsx ahí, Athena
> intentará leerlo como si fuera datos y verás filas basura.

## Paso 5 · Configurar Athena

1. Consola → **Amazon Athena** → **Launch query editor** (Query editor).
2. **Settings → Manage** (arriba a la derecha) → **Query result location**:
   `s3://<tu-bucket>/athena-results/` → **Save**. (Sin esto, ninguna consulta corre.)
3. Workgroup **primary** está bien; usa el motor **Athena engine v3** (requerido para Iceberg; es el predeterminado).
4. (Opcional, buena práctica) **Workgroups → Create workgroup** `outliers` con un límite de
   *data scanned per query* (p. ej. 10 GB) para evitar sustos.
5. En el editor: **Data source** = `AwsDataCatalog`. Las bases aparecerán al ejecutar el primer script.

> **Ejecuta una sentencia a la vez**: resáltala con el mouse y presiona **Run**. Si pegas varias juntas y la
> consola se queja, es por eso.

## Paso 6 · Preparar los scripts con tu bucket

Los `.sql` usan el placeholder `YOUR_BUCKET`. Desde la raíz del repo:

```bash
python tools/render_sql.py --bucket <tu-bucket>
```

Eso crea `sql_rendered/` (ignorado por git) con tu bucket ya puesto. Ejecuta **esos** archivos.

## Paso 7 · Ejecutar en orden

Ver la tabla "Orden de ejecución" del `README.md`. Después de cada capa, corre su verificación.

## Paso 8 · Antes de grabar el video

- CloudFormation (`us-east-1`) → **Stacks**: lista vacía.
- Tablas legibles: aumenta el zoom del navegador (Ctrl +) y usa el panel de resultados a pantalla completa.
- No muestres credenciales ni la página de *Security credentials*.

## Paso 9 · Limpieza (después de entregar)

- Athena: ejecuta `sql/99_reset/reset_silver_gold.sql` y luego `DROP DATABASE churn_bronze/silver/gold CASCADE`.
- S3: vacía el bucket (**Empty**) y elimínalo (**Delete**).
- Esto conserva los créditos del plan gratuito para la Parte B (IoT Core, SQS, Lambda, DynamoDB).

---

## Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| "No output location provided" | Falta el *Query result location* | Paso 5.2 |
| No veo mis bases/tablas | Región distinta | Paso 2 |
| Columnas "corridas" o datos raros en bronce | Orden de columnas ≠ encabezado del CSV, o subiste archivos extra a la carpeta | Paso 4.3 y regla de oro |
| `Iceberg ... not supported` | Workgroup en motor v2 | Paso 5.3 |
| `table location is not empty` / `already exists` al repetir un CTAS | Quedaron archivos o la tabla de un intento previo | `sql/99_reset` y borra la carpeta en S3 |
| `TABLE_NOT_FOUND churn_silver.customers` | Ejecutaste `02_orders.sql` antes de `01_customers.sql` | Respeta el orden |
| `Access Denied` en S3 | Tu usuario IAM no tiene permisos sobre el bucket | Usa un usuario con `AdministratorAccess` o ajusta la política |
