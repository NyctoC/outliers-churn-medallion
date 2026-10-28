-- ==============================================================================
-- ORO 2/3: orders_monthly_category
-- Pregunta de negocio que responde:
--   ¿Cómo evolucionan por mes y por categoría los ingresos, el ticket promedio, las devoluciones
--   y las cancelaciones? ¿Qué categorías concentran más devoluciones (posible causa de churn)?
-- Grano: 1 fila por (mes, categoría de producto). Alimenta el tablero de monitoreo y se usa como
-- "oro" en la comparación bronce vs plata vs oro.
-- ==============================================================================

CREATE TABLE churn_gold.orders_monthly_category
WITH (
  table_type = 'ICEBERG',
  is_external = false,
  format = 'PARQUET',
  location = 's3://YOUR_BUCKET/gold/orders_monthly_category/'
) AS
SELECT
  CAST(date_trunc('month', order_date) AS date)                    AS order_month,
  product_category,
  count(*)                                                         AS orders_n,
  sum(quantity)                                                    AS units,
  sum(order_amount)                                                AS revenue,
  avg(order_amount)                                                AS avg_order_value,
  avg(discount_percent)                                            AS avg_discount_percent,
  count_if(returned)                                               AS returned_n,
  CAST(count_if(returned) AS double) / count(*)                    AS return_rate,
  count_if(lower(order_status) = 'cancelled')                      AS cancelled_n,
  CAST(count_if(lower(order_status) = 'cancelled') AS double) / count(*) AS cancel_rate,
  avg(delivery_days)                                               AS avg_delivery_days,
  avg(customer_rating)                                             AS avg_customer_rating
FROM churn_silver.orders
GROUP BY 1, 2;
