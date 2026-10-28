-- ==============================================================================
-- SETUP: una base de datos (catálogo Glue) por capa de la arquitectura Medallion
-- Ejecuta cada sentencia por separado (resáltala y presiona Run).
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS churn_bronze;   -- datos crudos (CSV en S3, todo texto)
CREATE DATABASE IF NOT EXISTS churn_silver;   -- datos validados + rechazados (Iceberg)
CREATE DATABASE IF NOT EXISTS churn_gold;     -- tablas listas para EDA / BI / ML (Iceberg)

-- Verifica que existen:
SHOW DATABASES;
