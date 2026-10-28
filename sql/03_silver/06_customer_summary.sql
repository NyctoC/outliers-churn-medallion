-- ==============================================================================
-- PLATA: customer_summary
-- Requiere haber ejecutado ANTES 01_customers.sql (valida llaves foráneas contra silver.customers).
-- 1) Vista de validación: tipa las columnas y calcula reject_reason (vacío = fila válida).
-- 2) Tabla Iceberg con filas VÁLIDAS (tipos correctos + columnas flag_*).
-- 3) Tabla Iceberg con filas RECHAZADAS (valores crudos + motivo).
-- Regla de oro: bronce = válidas + rechazadas (se verifica en 05_checks/01_reconciliation.sql)
-- Si repites el script: DROP de las 3 tablas/vistas (sql/99_reset) y borra sus carpetas en S3.
-- ==============================================================================

-- 1) Vista de validación -----------------------------------------------------
CREATE OR REPLACE VIEW churn_silver.v_customer_summary_validated AS
SELECT ranked.*,
    array_join(ARRAY[
      CASE WHEN (rn_customer_id > 1 AND t_customer_id IS NOT NULL) THEN 'customer_id:repetido' END,
      CASE WHEN (t_customer_id IS NULL) THEN 'customer_id:nulo_o_invalido' END,
      CASE WHEN (t_churn IS NULL) THEN 'churn:nulo_o_invalido' END,
      CASE WHEN (t_total_orders IS NULL AND NULLIF(trim(total_orders), '') IS NOT NULL) THEN 'total_orders:formato_invalido' END,
      CASE WHEN (t_total_spent IS NULL AND NULLIF(trim(total_spent), '') IS NOT NULL) THEN 'total_spent:formato_invalido' END,
      CASE WHEN (t_average_order_value IS NULL AND NULLIF(trim(average_order_value), '') IS NOT NULL) THEN 'average_order_value:formato_invalido' END,
      CASE WHEN (t_total_returns IS NULL AND NULLIF(trim(total_returns), '') IS NOT NULL) THEN 'total_returns:formato_invalido' END,
      CASE WHEN (t_return_rate IS NULL AND NULLIF(trim(return_rate), '') IS NOT NULL) THEN 'return_rate:formato_invalido' END,
      CASE WHEN (t_loyalty_points IS NULL AND NULLIF(trim(loyalty_points), '') IS NOT NULL) THEN 'loyalty_points:formato_invalido' END,
      CASE WHEN (t_last_purchase_days IS NULL AND NULLIF(trim(last_purchase_days), '') IS NOT NULL) THEN 'last_purchase_days:formato_invalido' END,
      CASE WHEN (t_purchase_frequency IS NULL AND NULLIF(trim(purchase_frequency), '') IS NOT NULL) THEN 'purchase_frequency:formato_invalido' END,
      CASE WHEN (t_lifetime_value IS NULL AND NULLIF(trim(lifetime_value), '') IS NOT NULL) THEN 'lifetime_value:formato_invalido' END,
      CASE WHEN (t_churn_risk_score IS NULL AND NULLIF(trim(churn_risk_score), '') IS NOT NULL) THEN 'churn_risk_score:formato_invalido' END,
      CASE WHEN (fk_missing AND t_customer_id IS NOT NULL) THEN 'customer_id:sin_cliente_en_customers' END,
      CASE WHEN (t_total_orders < 0) THEN 'total_orders:negativo' END,
      CASE WHEN (t_total_spent < 0) THEN 'total_spent:negativo' END,
      CASE WHEN (t_average_order_value < 0) THEN 'average_order_value:negativo' END,
      CASE WHEN (t_total_returns < 0) THEN 'total_returns:negativo' END,
      CASE WHEN (t_loyalty_points < 0) THEN 'loyalty_points:negativo' END,
      CASE WHEN (t_last_purchase_days < 0) THEN 'last_purchase_days:negativo' END,
      CASE WHEN (t_purchase_frequency < 0) THEN 'purchase_frequency:negativo' END,
      CASE WHEN (t_lifetime_value < 0) THEN 'lifetime_value:negativo' END,
      CASE WHEN (t_return_rate < 0 OR t_return_rate > 1) THEN 'return_rate:fuera_de_0_1' END,
      CASE WHEN (t_churn_risk_score < 0 OR t_churn_risk_score > 100) THEN 'churn_risk_score:fuera_de_0_100' END
    ], ';') AS reject_reason
FROM (
    SELECT typed.*,
      row_number() OVER (PARTITION BY typed.t_customer_id ORDER BY typed.t_customer_id) AS rn_customer_id,
      (fk.fk_id IS NULL) AS fk_missing
    FROM (
      SELECT b.*,
        TRY_CAST(NULLIF(trim(b.customer_id), '') AS bigint) AS t_customer_id,
        TRY_CAST(NULLIF(trim(b.total_orders), '') AS integer) AS t_total_orders,
        TRY_CAST(NULLIF(trim(b.total_spent), '') AS double) AS t_total_spent,
        TRY_CAST(NULLIF(trim(b.average_order_value), '') AS double) AS t_average_order_value,
        TRY_CAST(NULLIF(trim(b.total_returns), '') AS integer) AS t_total_returns,
        TRY_CAST(NULLIF(trim(b.return_rate), '') AS double) AS t_return_rate,
        TRY_CAST(NULLIF(trim(b.loyalty_points), '') AS integer) AS t_loyalty_points,
        TRY_CAST(NULLIF(trim(b.last_purchase_days), '') AS integer) AS t_last_purchase_days,
        TRY_CAST(NULLIF(trim(b.purchase_frequency), '') AS double) AS t_purchase_frequency,
        TRY_CAST(NULLIF(trim(b.lifetime_value), '') AS double) AS t_lifetime_value,
        NULLIF(trim(b.customer_segment), '') AS t_customer_segment,
        TRY_CAST(NULLIF(trim(b.churn_risk_score), '') AS double) AS t_churn_risk_score,
        CASE WHEN lower(trim(b.churn)) IN ('true','1','1.0','yes','y','t','si','sí') THEN true WHEN lower(trim(b.churn)) IN ('false','0','0.0','no','n','f') THEN false END AS t_churn
      FROM churn_bronze.customer_summary b
    ) typed
    LEFT JOIN (SELECT customer_id AS fk_id FROM churn_silver.customers) fk ON typed.t_customer_id = fk.fk_id
  ) ranked;

-- 2) Filas válidas -------------------------------------------------------------
CREATE TABLE churn_silver.customer_summary
WITH (
  table_type = 'ICEBERG',
  is_external = false,
  format = 'PARQUET',
  location = 's3://YOUR_BUCKET/silver/customer_summary/'
) AS
SELECT
  t_customer_id AS customer_id,
  t_total_orders AS total_orders,
  t_total_spent AS total_spent,
  t_average_order_value AS average_order_value,
  t_total_returns AS total_returns,
  t_return_rate AS return_rate,
  t_loyalty_points AS loyalty_points,
  t_last_purchase_days AS last_purchase_days,
  t_purchase_frequency AS purchase_frequency,
  t_lifetime_value AS lifetime_value,
  t_customer_segment AS customer_segment,
  t_churn_risk_score AS churn_risk_score,
  t_churn AS churn,
  CASE WHEN (t_total_returns > t_total_orders) THEN true ELSE false END AS flag_devoluciones_mayor_que_pedidos,
  CASE WHEN (t_lifetime_value < t_total_spent) THEN true ELSE false END AS flag_clv_menor_que_gasto_total,
  current_date AS silver_load_date
FROM churn_silver.v_customer_summary_validated
WHERE reject_reason = '';

-- 3) Filas rechazadas ----------------------------------------------------------
CREATE TABLE churn_silver.customer_summary_rejected
WITH (
  table_type = 'ICEBERG',
  is_external = false,
  format = 'PARQUET',
  location = 's3://YOUR_BUCKET/silver/customer_summary_rejected/'
) AS
SELECT
  customer_id,
  total_orders,
  total_spent,
  average_order_value,
  total_returns,
  return_rate,
  loyalty_points,
  last_purchase_days,
  purchase_frequency,
  lifetime_value,
  customer_segment,
  churn_risk_score,
  churn,
  reject_reason,
  current_date AS rejected_date
FROM churn_silver.v_customer_summary_validated
WHERE reject_reason <> '';
