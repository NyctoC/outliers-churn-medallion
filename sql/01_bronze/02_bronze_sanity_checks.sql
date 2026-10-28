-- ==============================================================================
-- BRONCE: verificación (¿Athena leyó bien los CSV?)
-- Esperado: customers 500000 | orders 1000000 | engagement 500000 |
--           payments 500000 | support_tickets 150000 | customer_summary 500000
-- Si algún valor se ve 'corrido' (p. ej. una ciudad en la columna age), el orden
-- de columnas del DDL no coincide con el CSV: corrígelo y recrea la tabla.
-- ==============================================================================

SELECT 'customers' AS tabla, count(*) AS filas FROM churn_bronze.customers
UNION ALL SELECT 'orders', count(*) FROM churn_bronze.orders
UNION ALL SELECT 'engagement', count(*) FROM churn_bronze.engagement
UNION ALL SELECT 'payments', count(*) FROM churn_bronze.payments
UNION ALL SELECT 'support_tickets', count(*) FROM churn_bronze.support_tickets
UNION ALL SELECT 'customer_summary', count(*) FROM churn_bronze.customer_summary
ORDER BY tabla;

-- Mira 5 filas de cada tabla y compara contra el CSV:
SELECT * FROM churn_bronze.customers LIMIT 5;
SELECT * FROM churn_bronze.orders LIMIT 5;
SELECT * FROM churn_bronze.engagement LIMIT 5;
SELECT * FROM churn_bronze.payments LIMIT 5;
SELECT * FROM churn_bronze.support_tickets LIMIT 5;
SELECT * FROM churn_bronze.customer_summary LIMIT 5;
