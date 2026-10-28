-- ==============================================================================
-- PLATA: customers
-- Esta tabla es la raíz: las demás validan su customer_id contra ella.
-- 1) Vista de validación: tipa las columnas y calcula reject_reason (vacío = fila válida).
-- 2) Tabla Iceberg con filas VÁLIDAS (tipos correctos + columnas flag_*).
-- 3) Tabla Iceberg con filas RECHAZADAS (valores crudos + motivo).
-- Regla de oro: bronce = válidas + rechazadas (se verifica en 05_checks/01_reconciliation.sql)
-- Si repites el script: DROP de las 3 tablas/vistas (sql/99_reset) y borra sus carpetas en S3.
-- ==============================================================================

-- 1) Vista de validación -----------------------------------------------------
CREATE OR REPLACE VIEW churn_silver.v_customers_validated AS
SELECT ranked.*,
    array_join(ARRAY[
      CASE WHEN (rn_customer_id > 1 AND t_customer_id IS NOT NULL) THEN 'customer_id:repetido' END,
      CASE WHEN (t_customer_id IS NULL) THEN 'customer_id:nulo_o_invalido' END,
      CASE WHEN (t_age IS NULL AND NULLIF(trim(age), '') IS NOT NULL) THEN 'age:formato_invalido' END,
      CASE WHEN (t_signup_date IS NULL AND NULLIF(trim(signup_date), '') IS NOT NULL) THEN 'signup_date:formato_invalido' END,
      CASE WHEN (t_tenure_months IS NULL AND NULLIF(trim(tenure_months), '') IS NOT NULL) THEN 'tenure_months:formato_invalido' END,
      CASE WHEN (t_age < 18 OR t_age > 100) THEN 'age:fuera_de_18_100' END,
      CASE WHEN (t_signup_date < DATE '2015-01-01' OR t_signup_date > DATE '2026-07-31') THEN 'signup_date:fuera_de_rango' END,
      CASE WHEN (t_tenure_months < 0 OR t_tenure_months > 120) THEN 'tenure_months:fuera_de_0_120' END
    ], ';') AS reject_reason
FROM (
    SELECT typed.*,
      row_number() OVER (PARTITION BY typed.t_customer_id ORDER BY typed.t_customer_id) AS rn_customer_id
    FROM (
      SELECT b.*,
        TRY_CAST(NULLIF(trim(b.customer_id), '') AS bigint) AS t_customer_id,
        NULLIF(trim(b.first_name), '') AS t_first_name,
        NULLIF(trim(b.last_name), '') AS t_last_name,
        TRY_CAST(NULLIF(trim(b.age), '') AS integer) AS t_age,
        NULLIF(trim(b.gender), '') AS t_gender,
        NULLIF(trim(b.city), '') AS t_city,
        NULLIF(trim(b.state), '') AS t_state,
        NULLIF(trim(b.country), '') AS t_country,
        TRY_CAST(substr(trim(b.signup_date), 1, 10) AS date) AS t_signup_date,
        TRY_CAST(NULLIF(trim(b.tenure_months), '') AS integer) AS t_tenure_months,
        NULLIF(trim(b.membership_tier), '') AS t_membership_tier,
        NULLIF(trim(b.occupation), '') AS t_occupation,
        NULLIF(trim(b.income_group), '') AS t_income_group,
        NULLIF(trim(b.marital_status), '') AS t_marital_status,
        NULLIF(trim(b.education), '') AS t_education,
        NULLIF(trim(b.preferred_device), '') AS t_preferred_device,
        NULLIF(trim(b.referral_source), '') AS t_referral_source
      FROM churn_bronze.customers b
    ) typed
  ) ranked;

-- 2) Filas válidas -------------------------------------------------------------
CREATE TABLE churn_silver.customers
WITH (
  table_type = 'ICEBERG',
  is_external = false,
  format = 'PARQUET',
  location = 's3://YOUR_BUCKET/silver/customers/'
) AS
SELECT
  t_customer_id AS customer_id,
  t_first_name AS first_name,
  t_last_name AS last_name,
  t_age AS age,
  t_gender AS gender,
  t_city AS city,
  t_state AS state,
  t_country AS country,
  t_signup_date AS signup_date,
  t_tenure_months AS tenure_months,
  t_membership_tier AS membership_tier,
  t_occupation AS occupation,
  t_income_group AS income_group,
  t_marital_status AS marital_status,
  t_education AS education,
  t_preferred_device AS preferred_device,
  t_referral_source AS referral_source,
  CASE WHEN (abs(t_tenure_months - date_diff('month', t_signup_date, DATE '2026-07-31')) > 6) THEN true ELSE false END AS flag_tenure_no_cuadra_con_signup_date,
  current_date AS silver_load_date
FROM churn_silver.v_customers_validated
WHERE reject_reason = '';

-- 3) Filas rechazadas ----------------------------------------------------------
CREATE TABLE churn_silver.customers_rejected
WITH (
  table_type = 'ICEBERG',
  is_external = false,
  format = 'PARQUET',
  location = 's3://YOUR_BUCKET/silver/customers_rejected/'
) AS
SELECT
  customer_id,
  first_name,
  last_name,
  age,
  gender,
  city,
  state,
  country,
  signup_date,
  tenure_months,
  membership_tier,
  occupation,
  income_group,
  marital_status,
  education,
  preferred_device,
  referral_source,
  reject_reason,
  current_date AS rejected_date
FROM churn_silver.v_customers_validated
WHERE reject_reason <> '';
