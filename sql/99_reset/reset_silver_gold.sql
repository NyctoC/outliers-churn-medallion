-- ==============================================================================
-- RESET: borra plata, oro y hallazgos para poder repetir todo
-- OJO: no toca bronce (los CSV siguen en S3).
-- Si al recrear una tabla Athena dice que la ubicación no está vacía, borra la
-- carpeta correspondiente en S3 (silver/<tabla>/, gold/<tabla>/, audit/dq_findings/).
-- ==============================================================================

-- Oro
DROP TABLE IF EXISTS churn_gold.customer_360;
DROP TABLE IF EXISTS churn_gold.orders_monthly_category;
DROP TABLE IF EXISTS churn_gold.churn_by_dimension;

-- Plata (en orden inverso a la creación)
DROP VIEW IF EXISTS churn_silver.v_customer_summary_validated;
DROP TABLE IF EXISTS churn_silver.customer_summary_rejected;
DROP TABLE IF EXISTS churn_silver.customer_summary;
DROP VIEW IF EXISTS churn_silver.v_support_tickets_validated;
DROP TABLE IF EXISTS churn_silver.support_tickets_rejected;
DROP TABLE IF EXISTS churn_silver.support_tickets;
DROP VIEW IF EXISTS churn_silver.v_payments_validated;
DROP TABLE IF EXISTS churn_silver.payments_rejected;
DROP TABLE IF EXISTS churn_silver.payments;
DROP VIEW IF EXISTS churn_silver.v_engagement_validated;
DROP TABLE IF EXISTS churn_silver.engagement_rejected;
DROP TABLE IF EXISTS churn_silver.engagement;
DROP VIEW IF EXISTS churn_silver.v_orders_validated;
DROP TABLE IF EXISTS churn_silver.orders_rejected;
DROP TABLE IF EXISTS churn_silver.orders;
DROP VIEW IF EXISTS churn_silver.v_customers_validated;
DROP TABLE IF EXISTS churn_silver.customers_rejected;
DROP TABLE IF EXISTS churn_silver.customers;

-- Hallazgos
DROP TABLE IF EXISTS churn_silver.dq_findings;
