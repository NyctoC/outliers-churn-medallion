-- ==============================================================================
-- VERIFICACIÓN: motivos de rechazo (una fila por motivo)
-- reject_reason puede traer varios motivos separados por ';' -> se separan con UNNEST.
-- Si una tabla no aparece, no tuvo filas rechazadas (es un resultado válido).
-- ==============================================================================

SELECT 'customers' AS tabla, u.motivo, count(*) AS filas
FROM churn_silver.customers_rejected
CROSS JOIN UNNEST(split(reject_reason, ';')) AS u(motivo)
GROUP BY u.motivo
UNION ALL
SELECT 'orders' AS tabla, u.motivo, count(*) AS filas
FROM churn_silver.orders_rejected
CROSS JOIN UNNEST(split(reject_reason, ';')) AS u(motivo)
GROUP BY u.motivo
UNION ALL
SELECT 'engagement' AS tabla, u.motivo, count(*) AS filas
FROM churn_silver.engagement_rejected
CROSS JOIN UNNEST(split(reject_reason, ';')) AS u(motivo)
GROUP BY u.motivo
UNION ALL
SELECT 'payments' AS tabla, u.motivo, count(*) AS filas
FROM churn_silver.payments_rejected
CROSS JOIN UNNEST(split(reject_reason, ';')) AS u(motivo)
GROUP BY u.motivo
UNION ALL
SELECT 'support_tickets' AS tabla, u.motivo, count(*) AS filas
FROM churn_silver.support_tickets_rejected
CROSS JOIN UNNEST(split(reject_reason, ';')) AS u(motivo)
GROUP BY u.motivo
UNION ALL
SELECT 'customer_summary' AS tabla, u.motivo, count(*) AS filas
FROM churn_silver.customer_summary_rejected
CROSS JOIN UNNEST(split(reject_reason, ';')) AS u(motivo)
GROUP BY u.motivo
ORDER BY tabla, filas DESC;
