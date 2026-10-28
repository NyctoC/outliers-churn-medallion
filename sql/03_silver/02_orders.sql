-- ==============================================================================
-- PLATA: orders
-- Requiere haber ejecutado ANTES 01_customers.sql (valida llaves foráneas contra silver.customers).
-- 1) Vista de validación: tipa las columnas y calcula reject_reason (vacío = fila válida).
-- 2) Tabla Iceberg con filas VÁLIDAS (tipos correctos + columnas flag_*).
-- 3) Tabla Iceberg con filas RECHAZADAS (valores crudos + motivo).
-- Regla de oro: bronce = válidas + rechazadas (se verifica en 05_checks/01_reconciliation.sql)
-- Si repites el script: DROP de las 3 tablas/vistas (sql/99_reset) y borra sus carpetas en S3.
-- ==============================================================================

-- 1) Vista de validación -----------------------------------------------------
CREATE OR REPLACE VIEW churn_silver.v_orders_validated AS
SELECT ranked.*,
    array_join(ARRAY[
      CASE WHEN (rn_order_id > 1 AND t_order_id IS NOT NULL) THEN 'order_id:repetido' END,
      CASE WHEN (t_order_id IS NULL) THEN 'order_id:nulo_o_invalido' END,
      CASE WHEN (t_customer_id IS NULL) THEN 'customer_id:nulo_o_invalido' END,
      CASE WHEN (t_order_date IS NULL) THEN 'order_date:nulo_o_invalido' END,
      CASE WHEN (t_quantity IS NULL AND NULLIF(trim(quantity), '') IS NOT NULL) THEN 'quantity:formato_invalido' END,
      CASE WHEN (t_unit_price IS NULL AND NULLIF(trim(unit_price), '') IS NOT NULL) THEN 'unit_price:formato_invalido' END,
      CASE WHEN (t_discount_percent IS NULL AND NULLIF(trim(discount_percent), '') IS NOT NULL) THEN 'discount_percent:formato_invalido' END,
      CASE WHEN (t_order_amount IS NULL AND NULLIF(trim(order_amount), '') IS NOT NULL) THEN 'order_amount:formato_invalido' END,
      CASE WHEN (t_coupon_used IS NULL AND NULLIF(trim(coupon_used), '') IS NOT NULL) THEN 'coupon_used:formato_invalido' END,
      CASE WHEN (t_delivery_days IS NULL AND NULLIF(trim(delivery_days), '') IS NOT NULL) THEN 'delivery_days:formato_invalido' END,
      CASE WHEN (t_returned IS NULL AND NULLIF(trim(returned), '') IS NOT NULL) THEN 'returned:formato_invalido' END,
      CASE WHEN (t_seller_rating IS NULL AND NULLIF(trim(seller_rating), '') IS NOT NULL) THEN 'seller_rating:formato_invalido' END,
      CASE WHEN (t_customer_rating IS NULL AND NULLIF(trim(customer_rating), '') IS NOT NULL) THEN 'customer_rating:formato_invalido' END,
      CASE WHEN (fk_missing AND t_customer_id IS NOT NULL) THEN 'customer_id:sin_cliente_en_customers' END,
      CASE WHEN (t_order_date < DATE '2015-01-01' OR t_order_date > DATE '2026-07-31') THEN 'order_date:fuera_de_rango' END,
      CASE WHEN (t_quantity <= 0) THEN 'quantity:no_positiva' END,
      CASE WHEN (t_unit_price <= 0) THEN 'unit_price:no_positivo' END,
      CASE WHEN (t_discount_percent < 0 OR t_discount_percent > 100) THEN 'discount_percent:fuera_de_0_100' END,
      CASE WHEN (t_order_amount <= 0) THEN 'order_amount:no_positivo' END,
      CASE WHEN (t_delivery_days < 0 OR t_delivery_days > 60) THEN 'delivery_days:fuera_de_0_60' END,
      CASE WHEN (t_order_status IS NULL OR lower(t_order_status) NOT IN ('delivered', 'cancelled', 'returned')) THEN 'order_status:valor_no_permitido' END,
      CASE WHEN (t_seller_rating < 1 OR t_seller_rating > 5) THEN 'seller_rating:fuera_de_1_5' END,
      CASE WHEN (t_customer_rating < 1 OR t_customer_rating > 5) THEN 'customer_rating:fuera_de_1_5' END
    ], ';') AS reject_reason
FROM (
    SELECT typed.*,
      row_number() OVER (PARTITION BY typed.t_order_id ORDER BY typed.t_order_id) AS rn_order_id,
      (fk.fk_id IS NULL) AS fk_missing
    FROM (
      SELECT b.*,
        TRY_CAST(NULLIF(trim(b.order_id), '') AS bigint) AS t_order_id,
        TRY_CAST(NULLIF(trim(b.customer_id), '') AS bigint) AS t_customer_id,
        TRY_CAST(substr(trim(b.order_date), 1, 10) AS date) AS t_order_date,
        NULLIF(trim(b.product_category), '') AS t_product_category,
        NULLIF(trim(b.product_name), '') AS t_product_name,
        TRY_CAST(NULLIF(trim(b.quantity), '') AS integer) AS t_quantity,
        TRY_CAST(NULLIF(trim(b.unit_price), '') AS double) AS t_unit_price,
        TRY_CAST(NULLIF(trim(b.discount_percent), '') AS double) AS t_discount_percent,
        TRY_CAST(NULLIF(trim(b.order_amount), '') AS double) AS t_order_amount,
        NULLIF(trim(b.payment_method), '') AS t_payment_method,
        CASE WHEN lower(trim(b.coupon_used)) IN ('true','1','1.0','yes','y','t','si','sí') THEN true WHEN lower(trim(b.coupon_used)) IN ('false','0','0.0','no','n','f') THEN false END AS t_coupon_used,
        TRY_CAST(NULLIF(trim(b.delivery_days), '') AS integer) AS t_delivery_days,
        NULLIF(trim(b.order_status), '') AS t_order_status,
        CASE WHEN lower(trim(b.returned)) IN ('true','1','1.0','yes','y','t','si','sí') THEN true WHEN lower(trim(b.returned)) IN ('false','0','0.0','no','n','f') THEN false END AS t_returned,
        NULLIF(trim(b.return_reason), '') AS t_return_reason,
        TRY_CAST(NULLIF(trim(b.seller_rating), '') AS double) AS t_seller_rating,
        TRY_CAST(NULLIF(trim(b.customer_rating), '') AS integer) AS t_customer_rating
      FROM churn_bronze.orders b
    ) typed
    LEFT JOIN (SELECT customer_id AS fk_id FROM churn_silver.customers) fk ON typed.t_customer_id = fk.fk_id
  ) ranked;

-- 2) Filas válidas -------------------------------------------------------------
CREATE TABLE churn_silver.orders
WITH (
  table_type = 'ICEBERG',
  is_external = false,
  format = 'PARQUET',
  location = 's3://YOUR_BUCKET/silver/orders/',
  partitioning = ARRAY['year(order_date)']
) AS
SELECT
  t_order_id AS order_id,
  t_customer_id AS customer_id,
  t_order_date AS order_date,
  t_product_category AS product_category,
  t_product_name AS product_name,
  t_quantity AS quantity,
  t_unit_price AS unit_price,
  t_discount_percent AS discount_percent,
  t_order_amount AS order_amount,
  t_payment_method AS payment_method,
  t_coupon_used AS coupon_used,
  t_delivery_days AS delivery_days,
  t_order_status AS order_status,
  t_returned AS returned,
  t_return_reason AS return_reason,
  t_seller_rating AS seller_rating,
  t_customer_rating AS customer_rating,
  CASE WHEN (COALESCE(t_returned, false) AND t_return_reason IS NULL) THEN true ELSE false END AS flag_devuelto_sin_motivo,
  CASE WHEN (NOT COALESCE(t_returned, false) AND t_return_reason IS NOT NULL) THEN true ELSE false END AS flag_motivo_sin_devolucion,
  CASE WHEN ((lower(t_order_status) = 'cancelled' AND COALESCE(t_returned, false)) OR (lower(t_order_status) = 'returned' AND NOT COALESCE(t_returned, false))) THEN true ELSE false END AS flag_estado_vs_devuelto,
  CASE WHEN (t_order_amount IS NOT NULL AND abs(t_order_amount - t_quantity * t_unit_price * (1 - t_discount_percent / 100.0)) > 0.05 * t_order_amount) THEN true ELSE false END AS flag_monto_no_cuadra,
  current_date AS silver_load_date
FROM churn_silver.v_orders_validated
WHERE reject_reason = '';

-- 3) Filas rechazadas ----------------------------------------------------------
CREATE TABLE churn_silver.orders_rejected
WITH (
  table_type = 'ICEBERG',
  is_external = false,
  format = 'PARQUET',
  location = 's3://YOUR_BUCKET/silver/orders_rejected/'
) AS
SELECT
  order_id,
  customer_id,
  order_date,
  product_category,
  product_name,
  quantity,
  unit_price,
  discount_percent,
  order_amount,
  payment_method,
  coupon_used,
  delivery_days,
  order_status,
  returned,
  return_reason,
  seller_rating,
  customer_rating,
  reject_reason,
  current_date AS rejected_date
FROM churn_silver.v_orders_validated
WHERE reject_reason <> '';
