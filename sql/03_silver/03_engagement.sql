-- ==============================================================================
-- PLATA: engagement
-- Requiere haber ejecutado ANTES 01_customers.sql (valida llaves foráneas contra silver.customers).
-- 1) Vista de validación: tipa las columnas y calcula reject_reason (vacío = fila válida).
-- 2) Tabla Iceberg con filas VÁLIDAS (tipos correctos + columnas flag_*).
-- 3) Tabla Iceberg con filas RECHAZADAS (valores crudos + motivo).
-- Regla de oro: bronce = válidas + rechazadas (se verifica en 05_checks/01_reconciliation.sql)
-- Si repites el script: DROP de las 3 tablas/vistas (sql/99_reset) y borra sus carpetas en S3.
-- ==============================================================================

-- 1) Vista de validación -----------------------------------------------------
CREATE OR REPLACE VIEW churn_silver.v_engagement_validated AS
SELECT ranked.*,
    array_join(ARRAY[
      CASE WHEN (rn_customer_id > 1 AND t_customer_id IS NOT NULL) THEN 'customer_id:repetido' END,
      CASE WHEN (t_customer_id IS NULL) THEN 'customer_id:nulo_o_invalido' END,
      CASE WHEN (t_app_usage_minutes IS NULL AND NULLIF(trim(app_usage_minutes), '') IS NOT NULL) THEN 'app_usage_minutes:formato_invalido' END,
      CASE WHEN (t_website_sessions IS NULL AND NULLIF(trim(website_sessions), '') IS NOT NULL) THEN 'website_sessions:formato_invalido' END,
      CASE WHEN (t_avg_session_duration IS NULL AND NULLIF(trim(avg_session_duration), '') IS NOT NULL) THEN 'avg_session_duration:formato_invalido' END,
      CASE WHEN (t_search_frequency IS NULL AND NULLIF(trim(search_frequency), '') IS NOT NULL) THEN 'search_frequency:formato_invalido' END,
      CASE WHEN (t_pages_viewed IS NULL AND NULLIF(trim(pages_viewed), '') IS NOT NULL) THEN 'pages_viewed:formato_invalido' END,
      CASE WHEN (t_wishlist_items IS NULL AND NULLIF(trim(wishlist_items), '') IS NOT NULL) THEN 'wishlist_items:formato_invalido' END,
      CASE WHEN (t_cart_abandon_rate IS NULL AND NULLIF(trim(cart_abandon_rate), '') IS NOT NULL) THEN 'cart_abandon_rate:formato_invalido' END,
      CASE WHEN (t_notification_click_rate IS NULL AND NULLIF(trim(notification_click_rate), '') IS NOT NULL) THEN 'notification_click_rate:formato_invalido' END,
      CASE WHEN (t_email_open_rate IS NULL AND NULLIF(trim(email_open_rate), '') IS NOT NULL) THEN 'email_open_rate:formato_invalido' END,
      CASE WHEN (t_days_since_last_login IS NULL AND NULLIF(trim(days_since_last_login), '') IS NOT NULL) THEN 'days_since_last_login:formato_invalido' END,
      CASE WHEN (fk_missing AND t_customer_id IS NOT NULL) THEN 'customer_id:sin_cliente_en_customers' END,
      CASE WHEN (t_app_usage_minutes < 0) THEN 'app_usage_minutes:negativo' END,
      CASE WHEN (t_website_sessions < 0) THEN 'website_sessions:negativo' END,
      CASE WHEN (t_avg_session_duration < 0) THEN 'avg_session_duration:negativo' END,
      CASE WHEN (t_search_frequency < 0) THEN 'search_frequency:negativo' END,
      CASE WHEN (t_pages_viewed < 0) THEN 'pages_viewed:negativo' END,
      CASE WHEN (t_wishlist_items < 0) THEN 'wishlist_items:negativo' END,
      CASE WHEN (t_cart_abandon_rate < 0 OR t_cart_abandon_rate > 1) THEN 'cart_abandon_rate:fuera_de_0_1' END,
      CASE WHEN (t_notification_click_rate < 0 OR t_notification_click_rate > 1) THEN 'notification_click_rate:fuera_de_0_1' END,
      CASE WHEN (t_email_open_rate < 0 OR t_email_open_rate > 1) THEN 'email_open_rate:fuera_de_0_1' END,
      CASE WHEN (t_days_since_last_login < 0 OR t_days_since_last_login > 730) THEN 'days_since_last_login:fuera_de_0_730' END
    ], ';') AS reject_reason
FROM (
    SELECT typed.*,
      row_number() OVER (PARTITION BY typed.t_customer_id ORDER BY typed.t_customer_id) AS rn_customer_id,
      (fk.fk_id IS NULL) AS fk_missing
    FROM (
      SELECT b.*,
        TRY_CAST(NULLIF(trim(b.customer_id), '') AS bigint) AS t_customer_id,
        TRY_CAST(NULLIF(trim(b.app_usage_minutes), '') AS integer) AS t_app_usage_minutes,
        TRY_CAST(NULLIF(trim(b.website_sessions), '') AS integer) AS t_website_sessions,
        TRY_CAST(NULLIF(trim(b.avg_session_duration), '') AS double) AS t_avg_session_duration,
        TRY_CAST(NULLIF(trim(b.search_frequency), '') AS integer) AS t_search_frequency,
        TRY_CAST(NULLIF(trim(b.pages_viewed), '') AS integer) AS t_pages_viewed,
        TRY_CAST(NULLIF(trim(b.wishlist_items), '') AS integer) AS t_wishlist_items,
        TRY_CAST(NULLIF(trim(b.cart_abandon_rate), '') AS double) AS t_cart_abandon_rate,
        TRY_CAST(NULLIF(trim(b.notification_click_rate), '') AS double) AS t_notification_click_rate,
        TRY_CAST(NULLIF(trim(b.email_open_rate), '') AS double) AS t_email_open_rate,
        TRY_CAST(NULLIF(trim(b.days_since_last_login), '') AS integer) AS t_days_since_last_login
      FROM churn_bronze.engagement b
    ) typed
    LEFT JOIN (SELECT customer_id AS fk_id FROM churn_silver.customers) fk ON typed.t_customer_id = fk.fk_id
  ) ranked;

-- 2) Filas válidas -------------------------------------------------------------
CREATE TABLE churn_silver.engagement
WITH (
  table_type = 'ICEBERG',
  is_external = false,
  format = 'PARQUET',
  location = 's3://YOUR_BUCKET/silver/engagement/'
) AS
SELECT
  t_customer_id AS customer_id,
  t_app_usage_minutes AS app_usage_minutes,
  t_website_sessions AS website_sessions,
  t_avg_session_duration AS avg_session_duration,
  t_search_frequency AS search_frequency,
  t_pages_viewed AS pages_viewed,
  t_wishlist_items AS wishlist_items,
  t_cart_abandon_rate AS cart_abandon_rate,
  t_notification_click_rate AS notification_click_rate,
  t_email_open_rate AS email_open_rate,
  t_days_since_last_login AS days_since_last_login,
  current_date AS silver_load_date
FROM churn_silver.v_engagement_validated
WHERE reject_reason = '';

-- 3) Filas rechazadas ----------------------------------------------------------
CREATE TABLE churn_silver.engagement_rejected
WITH (
  table_type = 'ICEBERG',
  is_external = false,
  format = 'PARQUET',
  location = 's3://YOUR_BUCKET/silver/engagement_rejected/'
) AS
SELECT
  customer_id,
  app_usage_minutes,
  website_sessions,
  avg_session_duration,
  search_frequency,
  pages_viewed,
  wishlist_items,
  cart_abandon_rate,
  notification_click_rate,
  email_open_rate,
  days_since_last_login,
  reject_reason,
  current_date AS rejected_date
FROM churn_silver.v_engagement_validated
WHERE reject_reason <> '';
