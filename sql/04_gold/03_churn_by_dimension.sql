-- ==============================================================================
-- ORO 3/3: churn_by_dimension
-- Pregunta de negocio que responde:
--   ¿En qué segmentos (membresía, dispositivo, canal, ingreso, ciudad, etc.) es mayor la tasa
--   de churn y cuánto CLV hay en juego? Es la vista "monitoreo del churn" del tablero.
-- Grano: 1 fila por (dimensión, valor). Formato "largo" para graficar fácil en Power BI/Tableau.
-- Requiere: gold.customer_360. Solo clientes con etiqueta churn conocida.
-- ==============================================================================

CREATE TABLE churn_gold.churn_by_dimension
WITH (
  table_type = 'ICEBERG',
  is_external = false,
  format = 'PARQUET',
  location = 's3://YOUR_BUCKET/gold/churn_by_dimension/'
) AS
WITH base AS (
  SELECT * FROM churn_gold.customer_360 WHERE churn IS NOT NULL
),
unpivoted AS (
  SELECT 'membership_tier'  AS dimension, CAST(membership_tier  AS varchar) AS dimension_value, churn, lifetime_value FROM base
  UNION ALL SELECT 'preferred_device',  CAST(preferred_device  AS varchar), churn, lifetime_value FROM base
  UNION ALL SELECT 'referral_source',   CAST(referral_source   AS varchar), churn, lifetime_value FROM base
  UNION ALL SELECT 'income_group',      CAST(income_group      AS varchar), churn, lifetime_value FROM base
  UNION ALL SELECT 'gender',            CAST(gender            AS varchar), churn, lifetime_value FROM base
  UNION ALL SELECT 'city',              CAST(city              AS varchar), churn, lifetime_value FROM base
  UNION ALL SELECT 'state',             CAST(state             AS varchar), churn, lifetime_value FROM base
  UNION ALL SELECT 'education',         CAST(education         AS varchar), churn, lifetime_value FROM base
  UNION ALL SELECT 'occupation',        CAST(occupation        AS varchar), churn, lifetime_value FROM base
  UNION ALL SELECT 'marital_status',    CAST(marital_status    AS varchar), churn, lifetime_value FROM base
  UNION ALL SELECT 'customer_segment',  CAST(customer_segment  AS varchar), churn, lifetime_value FROM base
  UNION ALL SELECT 'last_payment_status', CAST(last_payment_status AS varchar), churn, lifetime_value FROM base
  UNION ALL SELECT 'has_orders',        CAST(has_orders        AS varchar), churn, lifetime_value FROM base
  UNION ALL SELECT 'has_tickets',       CAST(has_tickets       AS varchar), churn, lifetime_value FROM base
  UNION ALL SELECT 'age_band',
    CASE WHEN age < 25 THEN '18-24' WHEN age < 35 THEN '25-34' WHEN age < 45 THEN '35-44'
         WHEN age < 55 THEN '45-54' WHEN age < 65 THEN '55-64' ELSE '65+' END,
    churn, lifetime_value FROM base
)
SELECT
  dimension,
  dimension_value,
  count(*)                                          AS customers_n,
  count_if(churn)                                   AS churned_n,
  CAST(count_if(churn) AS double) / count(*)        AS churn_rate,
  avg(lifetime_value)                               AS avg_clv,
  sum(lifetime_value)                               AS total_clv,
  sum(CASE WHEN churn THEN lifetime_value END)      AS clv_at_risk
FROM unpivoted
GROUP BY dimension, dimension_value;
