-- ==============================================================================
-- PLATA: support_tickets
-- Requiere haber ejecutado ANTES 01_customers.sql (valida llaves foráneas contra silver.customers).
-- 1) Vista de validación: tipa las columnas y calcula reject_reason (vacío = fila válida).
-- 2) Tabla Iceberg con filas VÁLIDAS (tipos correctos + columnas flag_*).
-- 3) Tabla Iceberg con filas RECHAZADAS (valores crudos + motivo).
-- Regla de oro: bronce = válidas + rechazadas (se verifica en 05_checks/01_reconciliation.sql)
-- Si repites el script: DROP de las 3 tablas/vistas (sql/99_reset) y borra sus carpetas en S3.
-- ==============================================================================

-- 1) Vista de validación -----------------------------------------------------
CREATE OR REPLACE VIEW churn_silver.v_support_tickets_validated AS
SELECT ranked.*,
    array_join(ARRAY[
      CASE WHEN (rn_ticket_id > 1 AND t_ticket_id IS NOT NULL) THEN 'ticket_id:repetido' END,
      CASE WHEN (t_ticket_id IS NULL) THEN 'ticket_id:nulo_o_invalido' END,
      CASE WHEN (t_customer_id IS NULL) THEN 'customer_id:nulo_o_invalido' END,
      CASE WHEN (t_tickets_last_year IS NULL AND NULLIF(trim(tickets_last_year), '') IS NOT NULL) THEN 'tickets_last_year:formato_invalido' END,
      CASE WHEN (t_avg_resolution_hours IS NULL AND NULLIF(trim(avg_resolution_hours), '') IS NOT NULL) THEN 'avg_resolution_hours:formato_invalido' END,
      CASE WHEN (t_satisfaction_score IS NULL AND NULLIF(trim(satisfaction_score), '') IS NOT NULL) THEN 'satisfaction_score:formato_invalido' END,
      CASE WHEN (t_escalated IS NULL AND NULLIF(trim(escalated), '') IS NOT NULL) THEN 'escalated:formato_invalido' END,
      CASE WHEN (fk_missing AND t_customer_id IS NOT NULL) THEN 'customer_id:sin_cliente_en_customers' END,
      CASE WHEN (t_tickets_last_year < 0) THEN 'tickets_last_year:negativo' END,
      CASE WHEN (t_avg_resolution_hours < 0) THEN 'avg_resolution_hours:negativo' END,
      CASE WHEN (t_satisfaction_score < 1 OR t_satisfaction_score > 5) THEN 'satisfaction_score:fuera_de_1_5' END,
      CASE WHEN (t_issue_status IS NULL OR lower(t_issue_status) NOT IN ('closed', 'resolved', 'escalated', 'open')) THEN 'issue_status:valor_no_permitido' END
    ], ';') AS reject_reason
FROM (
    SELECT typed.*,
      row_number() OVER (PARTITION BY typed.t_ticket_id ORDER BY typed.t_ticket_id) AS rn_ticket_id,
      (fk.fk_id IS NULL) AS fk_missing
    FROM (
      SELECT b.*,
        TRY_CAST(NULLIF(trim(b.ticket_id), '') AS bigint) AS t_ticket_id,
        TRY_CAST(NULLIF(trim(b.customer_id), '') AS bigint) AS t_customer_id,
        TRY_CAST(NULLIF(trim(b.tickets_last_year), '') AS integer) AS t_tickets_last_year,
        NULLIF(trim(b.complaint_category), '') AS t_complaint_category,
        TRY_CAST(NULLIF(trim(b.avg_resolution_hours), '') AS double) AS t_avg_resolution_hours,
        TRY_CAST(NULLIF(trim(b.satisfaction_score), '') AS double) AS t_satisfaction_score,
        CASE WHEN lower(trim(b.escalated)) IN ('true','1','1.0','yes','y','t','si','sí') THEN true WHEN lower(trim(b.escalated)) IN ('false','0','0.0','no','n','f') THEN false END AS t_escalated,
        NULLIF(trim(b.issue_status), '') AS t_issue_status
      FROM churn_bronze.support_tickets b
    ) typed
    LEFT JOIN (SELECT customer_id AS fk_id FROM churn_silver.customers) fk ON typed.t_customer_id = fk.fk_id
  ) ranked;

-- 2) Filas válidas -------------------------------------------------------------
CREATE TABLE churn_silver.support_tickets
WITH (
  table_type = 'ICEBERG',
  is_external = false,
  format = 'PARQUET',
  location = 's3://YOUR_BUCKET/silver/support_tickets/'
) AS
SELECT
  t_ticket_id AS ticket_id,
  t_customer_id AS customer_id,
  t_tickets_last_year AS tickets_last_year,
  t_complaint_category AS complaint_category,
  t_avg_resolution_hours AS avg_resolution_hours,
  t_satisfaction_score AS satisfaction_score,
  t_escalated AS escalated,
  t_issue_status AS issue_status,
  CASE WHEN (NOT COALESCE(t_escalated, false) AND lower(t_issue_status) = 'escalated') THEN true ELSE false END AS flag_no_escalado_pero_estado_escalated,
  current_date AS silver_load_date
FROM churn_silver.v_support_tickets_validated
WHERE reject_reason = '';

-- 3) Filas rechazadas ----------------------------------------------------------
CREATE TABLE churn_silver.support_tickets_rejected
WITH (
  table_type = 'ICEBERG',
  is_external = false,
  format = 'PARQUET',
  location = 's3://YOUR_BUCKET/silver/support_tickets_rejected/'
) AS
SELECT
  ticket_id,
  customer_id,
  tickets_last_year,
  complaint_category,
  avg_resolution_hours,
  satisfaction_score,
  escalated,
  issue_status,
  reject_reason,
  current_date AS rejected_date
FROM churn_silver.v_support_tickets_validated
WHERE reject_reason <> '';
