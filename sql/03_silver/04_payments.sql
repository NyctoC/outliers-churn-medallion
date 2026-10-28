-- ==============================================================================
-- PLATA: payments
-- Requiere haber ejecutado ANTES 01_customers.sql (valida llaves foráneas contra silver.customers).
-- 1) Vista de validación: tipa las columnas y calcula reject_reason (vacío = fila válida).
-- 2) Tabla Iceberg con filas VÁLIDAS (tipos correctos + columnas flag_*).
-- 3) Tabla Iceberg con filas RECHAZADAS (valores crudos + motivo).
-- Regla de oro: bronce = válidas + rechazadas (se verifica en 05_checks/01_reconciliation.sql)
-- Si repites el script: DROP de las 3 tablas/vistas (sql/99_reset) y borra sus carpetas en S3.
-- ==============================================================================

-- 1) Vista de validación -----------------------------------------------------
CREATE OR REPLACE VIEW churn_silver.v_payments_validated AS
SELECT ranked.*,
    array_join(ARRAY[
      CASE WHEN (rn_payment_id > 1 AND t_payment_id IS NOT NULL) THEN 'payment_id:repetido' END,
      CASE WHEN (rn_customer_id > 1 AND t_customer_id IS NOT NULL) THEN 'customer_id:repetido' END,
      CASE WHEN (t_payment_id IS NULL) THEN 'payment_id:nulo_o_invalido' END,
      CASE WHEN (t_customer_id IS NULL) THEN 'customer_id:nulo_o_invalido' END,
      CASE WHEN (t_payment_failures IS NULL AND NULLIF(trim(payment_failures), '') IS NOT NULL) THEN 'payment_failures:formato_invalido' END,
      CASE WHEN (t_refund_amount IS NULL AND NULLIF(trim(refund_amount), '') IS NOT NULL) THEN 'refund_amount:formato_invalido' END,
      CASE WHEN (t_subscription_active IS NULL AND NULLIF(trim(subscription_active), '') IS NOT NULL) THEN 'subscription_active:formato_invalido' END,
      CASE WHEN (t_subscription_fee IS NULL AND NULLIF(trim(subscription_fee), '') IS NOT NULL) THEN 'subscription_fee:formato_invalido' END,
      CASE WHEN (t_average_monthly_spend IS NULL AND NULLIF(trim(average_monthly_spend), '') IS NOT NULL) THEN 'average_monthly_spend:formato_invalido' END,
      CASE WHEN (t_last_payment_date IS NULL AND NULLIF(trim(last_payment_date), '') IS NOT NULL) THEN 'last_payment_date:formato_invalido' END,
      CASE WHEN (fk_missing AND t_customer_id IS NOT NULL) THEN 'customer_id:sin_cliente_en_customers' END,
      CASE WHEN (t_payment_failures < 0) THEN 'payment_failures:negativo' END,
      CASE WHEN (t_refund_amount < 0) THEN 'refund_amount:negativo' END,
      CASE WHEN (t_subscription_fee < 0) THEN 'subscription_fee:negativo' END,
      CASE WHEN (t_average_monthly_spend < 0) THEN 'average_monthly_spend:negativo' END,
      CASE WHEN (t_payment_status IS NULL OR lower(t_payment_status) NOT IN ('success', 'failed', 'pending', 'refunded')) THEN 'payment_status:valor_no_permitido' END
    ], ';') AS reject_reason
FROM (
    SELECT typed.*,
      row_number() OVER (PARTITION BY typed.t_payment_id ORDER BY typed.t_payment_id) AS rn_payment_id,
      row_number() OVER (PARTITION BY typed.t_customer_id ORDER BY typed.t_customer_id) AS rn_customer_id,
      (fk.fk_id IS NULL) AS fk_missing
    FROM (
      SELECT b.*,
        TRY_CAST(NULLIF(trim(b.payment_id), '') AS bigint) AS t_payment_id,
        TRY_CAST(NULLIF(trim(b.customer_id), '') AS bigint) AS t_customer_id,
        NULLIF(trim(b.payment_method), '') AS t_payment_method,
        NULLIF(trim(b.payment_status), '') AS t_payment_status,
        TRY_CAST(NULLIF(trim(b.payment_failures), '') AS integer) AS t_payment_failures,
        TRY_CAST(NULLIF(trim(b.refund_amount), '') AS double) AS t_refund_amount,
        CASE WHEN lower(trim(b.subscription_active)) IN ('true','1','1.0','yes','y','t','si','sí') THEN true WHEN lower(trim(b.subscription_active)) IN ('false','0','0.0','no','n','f') THEN false END AS t_subscription_active,
        TRY_CAST(NULLIF(trim(b.subscription_fee), '') AS double) AS t_subscription_fee,
        TRY_CAST(NULLIF(trim(b.average_monthly_spend), '') AS double) AS t_average_monthly_spend,
        TRY_CAST(substr(trim(b.last_payment_date), 1, 10) AS date) AS t_last_payment_date
      FROM churn_bronze.payments b
    ) typed
    LEFT JOIN (SELECT customer_id AS fk_id FROM churn_silver.customers) fk ON typed.t_customer_id = fk.fk_id
  ) ranked;

-- 2) Filas válidas -------------------------------------------------------------
CREATE TABLE churn_silver.payments
WITH (
  table_type = 'ICEBERG',
  is_external = false,
  format = 'PARQUET',
  location = 's3://YOUR_BUCKET/silver/payments/'
) AS
SELECT
  t_payment_id AS payment_id,
  t_customer_id AS customer_id,
  t_payment_method AS payment_method,
  t_payment_status AS payment_status,
  t_payment_failures AS payment_failures,
  t_refund_amount AS refund_amount,
  t_subscription_active AS subscription_active,
  t_subscription_fee AS subscription_fee,
  t_average_monthly_spend AS average_monthly_spend,
  t_last_payment_date AS last_payment_date,
  CASE WHEN (t_last_payment_date > DATE '2026-07-31') THEN true ELSE false END AS flag_fecha_pago_futura,
  CASE WHEN (NOT COALESCE(t_subscription_active, false) AND t_subscription_fee > 0) THEN true ELSE false END AS flag_suscripcion_inactiva_con_tarifa,
  current_date AS silver_load_date
FROM churn_silver.v_payments_validated
WHERE reject_reason = '';

-- 3) Filas rechazadas ----------------------------------------------------------
CREATE TABLE churn_silver.payments_rejected
WITH (
  table_type = 'ICEBERG',
  is_external = false,
  format = 'PARQUET',
  location = 's3://YOUR_BUCKET/silver/payments_rejected/'
) AS
SELECT
  payment_id,
  customer_id,
  payment_method,
  payment_status,
  payment_failures,
  refund_amount,
  subscription_active,
  subscription_fee,
  average_monthly_spend,
  last_payment_date,
  reject_reason,
  current_date AS rejected_date
FROM churn_silver.v_payments_validated
WHERE reject_reason <> '';
