-- ==============================================================================
-- ORO 1/3: customer_360  (una fila por cliente)
-- Es la tabla base del EDA y del modelo de churn: une las 6 tablas de plata.
--
-- Decisiones:
--   * Base = silver.customers; todo lo demás entra con LEFT JOIN. Los clientes sin pedidos
--     (~13 %) o sin tickets (~74 %) NO se pierden: quedan con has_orders / has_tickets = false.
--   * Se omiten first_name (constante), last_name (código único) y country (constante).
--   * churn_risk_score y customer_segment se dejan, pero SON CANDIDATAS A FUGA DE INFORMACIÓN:
--     audítalas en el EDA antes de usarlas como predictoras.
--   * Las variables de pedidos se recalculan desde silver.orders (no desde customer_summary)
--     porque las dos fuentes no coinciden: ver columna summary_vs_orders_mismatch.
--   * Fecha de referencia de recencia = fecha del último pedido del dataset.
-- Requiere: las 6 tablas de plata creadas.
-- ==============================================================================

CREATE TABLE churn_gold.customer_360
WITH (
  table_type = 'ICEBERG',
  is_external = false,
  format = 'PARQUET',
  location = 's3://YOUR_BUCKET/gold/customer_360/'
) AS
WITH ref AS (
  SELECT max(order_date) AS ref_date FROM churn_silver.orders
),
ord AS (
  SELECT
    o.customer_id,
    count(*)                                                          AS orders_n,
    sum(o.order_amount)                                               AS orders_amount_sum,
    avg(o.order_amount)                                               AS orders_amount_avg,
    min(o.order_date)                                                 AS first_order_date,
    max(o.order_date)                                                 AS last_order_date,
    count_if(o.order_date >= date_add('month', -3,  r.ref_date))      AS orders_last_3m,
    count_if(o.order_date >= date_add('month', -6,  r.ref_date))      AS orders_last_6m,
    count_if(o.order_date >= date_add('month', -12, r.ref_date))      AS orders_last_12m,
    count_if(lower(o.order_status) = 'cancelled')                     AS orders_cancelled_n,
    count_if(lower(o.order_status) = 'returned')                      AS orders_status_returned_n,
    count_if(o.returned)                                              AS orders_returned_flag_n,
    avg(o.discount_percent)                                           AS orders_discount_avg,
    CAST(count_if(o.coupon_used) AS double) / count(*)                AS orders_coupon_share,
    avg(o.delivery_days)                                              AS orders_delivery_days_avg,
    avg(o.customer_rating)                                            AS orders_customer_rating_avg
  FROM churn_silver.orders o
  CROSS JOIN ref r
  GROUP BY o.customer_id, r.ref_date
),
tix AS (
  SELECT
    t.customer_id,
    count(*)                         AS tickets_n,
    max(t.tickets_last_year)         AS tickets_last_year_max,
    avg(t.avg_resolution_hours)      AS tickets_resolution_hours_avg,
    avg(t.satisfaction_score)        AS tickets_satisfaction_avg,
    min(t.satisfaction_score)        AS tickets_satisfaction_min,
    count_if(t.escalated)            AS tickets_escalated_n
  FROM churn_silver.support_tickets t
  GROUP BY t.customer_id
)
SELECT
  -- Perfil (customers)
  c.customer_id,
  c.age, c.gender, c.city, c.state,
  c.signup_date, c.tenure_months,
  c.membership_tier, c.occupation, c.income_group, c.marital_status, c.education,
  c.preferred_device, c.referral_source,

  -- Interacción digital (engagement)
  e.app_usage_minutes, e.website_sessions, e.avg_session_duration, e.search_frequency,
  e.pages_viewed, e.wishlist_items, e.cart_abandon_rate, e.notification_click_rate,
  e.email_open_rate, e.days_since_last_login,

  -- Pagos (payments)
  p.payment_method              AS usual_payment_method,
  p.payment_status              AS last_payment_status,
  p.payment_failures, p.refund_amount, p.subscription_active, p.subscription_fee,
  p.average_monthly_spend, p.last_payment_date,
  p.flag_fecha_pago_futura      AS payment_date_in_future,

  -- Resumen del autor (customer_summary). OJO: churn_risk_score y customer_segment = posible fuga
  s.total_orders                AS summary_total_orders,
  s.total_spent, s.average_order_value, s.total_returns, s.return_rate,
  s.loyalty_points, s.last_purchase_days, s.purchase_frequency, s.lifetime_value,
  s.customer_segment, s.churn_risk_score,

  -- Pedidos recalculados desde orders (RFM + tendencias)
  COALESCE(ord.orders_n, 0)                  AS orders_n,
  ord.orders_amount_sum, ord.orders_amount_avg,
  ord.first_order_date, ord.last_order_date,
  date_diff('day', ord.last_order_date, r.ref_date) AS days_since_last_order,
  COALESCE(ord.orders_last_3m, 0)            AS orders_last_3m,
  COALESCE(ord.orders_last_6m, 0)            AS orders_last_6m,
  COALESCE(ord.orders_last_12m, 0)           AS orders_last_12m,
  COALESCE(ord.orders_cancelled_n, 0)        AS orders_cancelled_n,
  COALESCE(ord.orders_status_returned_n, 0)  AS orders_status_returned_n,
  COALESCE(ord.orders_returned_flag_n, 0)    AS orders_returned_flag_n,
  ord.orders_discount_avg, ord.orders_coupon_share,
  ord.orders_delivery_days_avg, ord.orders_customer_rating_avg,

  -- Soporte (support_tickets)
  COALESCE(tix.tickets_n, 0)                 AS tickets_n,
  tix.tickets_last_year_max, tix.tickets_resolution_hours_avg,
  tix.tickets_satisfaction_avg, tix.tickets_satisfaction_min,
  COALESCE(tix.tickets_escalated_n, 0)       AS tickets_escalated_n,

  -- Indicadores de ausencia y de consistencia entre tablas
  (ord.customer_id IS NOT NULL)              AS has_orders,
  (tix.customer_id IS NOT NULL)              AS has_tickets,
  (s.total_orders IS NOT NULL
     AND s.total_orders <> COALESCE(ord.orders_n, 0)) AS summary_vs_orders_mismatch,

  -- Variable objetivo (NULL si el cliente fue rechazado en customer_summary: excluir del modelo)
  s.churn
FROM churn_silver.customers c
LEFT JOIN churn_silver.engagement       e   ON e.customer_id   = c.customer_id
LEFT JOIN churn_silver.payments         p   ON p.customer_id   = c.customer_id
LEFT JOIN churn_silver.customer_summary s   ON s.customer_id   = c.customer_id
LEFT JOIN ord                               ON ord.customer_id = c.customer_id
LEFT JOIN tix                               ON tix.customer_id = c.customer_id
CROSS JOIN ref r;
