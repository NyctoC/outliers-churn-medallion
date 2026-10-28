-- ==============================================================================
-- VERIFICACIÓN: los conteos cuadran (bronce = válidas + rechazadas)
-- ==============================================================================

SELECT tabla, bronce, plata_validas, plata_rechazadas,
       bronce - plata_validas - plata_rechazadas AS diferencia,
       CASE WHEN bronce = plata_validas + plata_rechazadas THEN 'OK' ELSE 'REVISAR' END AS cuadra
FROM (
  SELECT 'customers' AS tabla,
    (SELECT count(*) FROM churn_bronze.customers) AS bronce,
    (SELECT count(*) FROM churn_silver.customers) AS plata_validas,
    (SELECT count(*) FROM churn_silver.customers_rejected) AS plata_rechazadas
  UNION ALL
  SELECT 'orders' AS tabla,
    (SELECT count(*) FROM churn_bronze.orders) AS bronce,
    (SELECT count(*) FROM churn_silver.orders) AS plata_validas,
    (SELECT count(*) FROM churn_silver.orders_rejected) AS plata_rechazadas
  UNION ALL
  SELECT 'engagement' AS tabla,
    (SELECT count(*) FROM churn_bronze.engagement) AS bronce,
    (SELECT count(*) FROM churn_silver.engagement) AS plata_validas,
    (SELECT count(*) FROM churn_silver.engagement_rejected) AS plata_rechazadas
  UNION ALL
  SELECT 'payments' AS tabla,
    (SELECT count(*) FROM churn_bronze.payments) AS bronce,
    (SELECT count(*) FROM churn_silver.payments) AS plata_validas,
    (SELECT count(*) FROM churn_silver.payments_rejected) AS plata_rechazadas
  UNION ALL
  SELECT 'support_tickets' AS tabla,
    (SELECT count(*) FROM churn_bronze.support_tickets) AS bronce,
    (SELECT count(*) FROM churn_silver.support_tickets) AS plata_validas,
    (SELECT count(*) FROM churn_silver.support_tickets_rejected) AS plata_rechazadas
  UNION ALL
  SELECT 'customer_summary' AS tabla,
    (SELECT count(*) FROM churn_bronze.customer_summary) AS bronce,
    (SELECT count(*) FROM churn_silver.customer_summary) AS plata_validas,
    (SELECT count(*) FROM churn_silver.customer_summary_rejected) AS plata_rechazadas
) x
ORDER BY tabla;
