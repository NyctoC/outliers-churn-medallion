-- ==============================================================================
-- BRONCE: tablas externas sobre los CSV crudos (todo como texto)
-- Athena NO copia los datos: solo 'mira' los CSV que subiste a S3.
-- Cada tabla apunta a una CARPETA (no a un archivo): s3://BUCKET/bronze/<tabla>/
-- El orden de las columnas debe ser el mismo que el encabezado del CSV.
-- Antes de ejecutar: reemplaza YOUR_BUCKET por el nombre real de tu bucket.
-- ==============================================================================

CREATE EXTERNAL TABLE IF NOT EXISTS churn_bronze.customers (
  customer_id string,
  first_name string,
  last_name string,
  age string,
  gender string,
  city string,
  state string,
  country string,
  signup_date string,
  tenure_months string,
  membership_tier string,
  occupation string,
  income_group string,
  marital_status string,
  education string,
  preferred_device string,
  referral_source string
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar' = ',', 'quoteChar' = '"')
STORED AS TEXTFILE
LOCATION 's3://YOUR_BUCKET/bronze/customers/'
TBLPROPERTIES ('skip.header.line.count' = '1');

CREATE EXTERNAL TABLE IF NOT EXISTS churn_bronze.orders (
  order_id string,
  customer_id string,
  order_date string,
  product_category string,
  product_name string,
  quantity string,
  unit_price string,
  discount_percent string,
  order_amount string,
  payment_method string,
  coupon_used string,
  delivery_days string,
  order_status string,
  returned string,
  return_reason string,
  seller_rating string,
  customer_rating string
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar' = ',', 'quoteChar' = '"')
STORED AS TEXTFILE
LOCATION 's3://YOUR_BUCKET/bronze/orders/'
TBLPROPERTIES ('skip.header.line.count' = '1');

CREATE EXTERNAL TABLE IF NOT EXISTS churn_bronze.engagement (
  customer_id string,
  app_usage_minutes string,
  website_sessions string,
  avg_session_duration string,
  search_frequency string,
  pages_viewed string,
  wishlist_items string,
  cart_abandon_rate string,
  notification_click_rate string,
  email_open_rate string,
  days_since_last_login string
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar' = ',', 'quoteChar' = '"')
STORED AS TEXTFILE
LOCATION 's3://YOUR_BUCKET/bronze/engagement/'
TBLPROPERTIES ('skip.header.line.count' = '1');

CREATE EXTERNAL TABLE IF NOT EXISTS churn_bronze.payments (
  payment_id string,
  customer_id string,
  payment_method string,
  payment_status string,
  payment_failures string,
  refund_amount string,
  subscription_active string,
  subscription_fee string,
  average_monthly_spend string,
  last_payment_date string
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar' = ',', 'quoteChar' = '"')
STORED AS TEXTFILE
LOCATION 's3://YOUR_BUCKET/bronze/payments/'
TBLPROPERTIES ('skip.header.line.count' = '1');

CREATE EXTERNAL TABLE IF NOT EXISTS churn_bronze.support_tickets (
  ticket_id string,
  customer_id string,
  tickets_last_year string,
  complaint_category string,
  avg_resolution_hours string,
  satisfaction_score string,
  escalated string,
  issue_status string
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar' = ',', 'quoteChar' = '"')
STORED AS TEXTFILE
LOCATION 's3://YOUR_BUCKET/bronze/support_tickets/'
TBLPROPERTIES ('skip.header.line.count' = '1');

CREATE EXTERNAL TABLE IF NOT EXISTS churn_bronze.customer_summary (
  customer_id string,
  total_orders string,
  total_spent string,
  average_order_value string,
  total_returns string,
  return_rate string,
  loyalty_points string,
  last_purchase_days string,
  purchase_frequency string,
  lifetime_value string,
  customer_segment string,
  churn_risk_score string,
  churn string
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar' = ',', 'quoteChar' = '"')
STORED AS TEXTFILE
LOCATION 's3://YOUR_BUCKET/bronze/customer_summary/'
TBLPROPERTIES ('skip.header.line.count' = '1');

