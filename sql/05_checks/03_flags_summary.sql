-- ==============================================================================
-- VERIFICACIÓN: banderas (inconsistencias que NO se rechazaron) en plata
-- Si una bandera afecta a muchísimas filas, probablemente las tablas sintéticas se
-- generaron de forma independiente. Decide en el EDA si la promueves a regla de rechazo.
-- ==============================================================================

SELECT 'customers' AS tabla, u.bandera, u.filas, m.total AS total_filas
FROM (SELECT count(*) AS total, count_if(flag_tenure_no_cuadra_con_signup_date) AS f1
      FROM churn_silver.customers) m
CROSS JOIN UNNEST(ARRAY['flag_tenure_no_cuadra_con_signup_date'], ARRAY[m.f1]) AS u(bandera, filas)
UNION ALL
SELECT 'orders' AS tabla, u.bandera, u.filas, m.total AS total_filas
FROM (SELECT count(*) AS total, count_if(flag_devuelto_sin_motivo) AS f1, count_if(flag_motivo_sin_devolucion) AS f2, count_if(flag_estado_vs_devuelto) AS f3, count_if(flag_monto_no_cuadra) AS f4
      FROM churn_silver.orders) m
CROSS JOIN UNNEST(ARRAY['flag_devuelto_sin_motivo', 'flag_motivo_sin_devolucion', 'flag_estado_vs_devuelto', 'flag_monto_no_cuadra'], ARRAY[m.f1, m.f2, m.f3, m.f4]) AS u(bandera, filas)
UNION ALL
SELECT 'payments' AS tabla, u.bandera, u.filas, m.total AS total_filas
FROM (SELECT count(*) AS total, count_if(flag_fecha_pago_futura) AS f1, count_if(flag_suscripcion_inactiva_con_tarifa) AS f2
      FROM churn_silver.payments) m
CROSS JOIN UNNEST(ARRAY['flag_fecha_pago_futura', 'flag_suscripcion_inactiva_con_tarifa'], ARRAY[m.f1, m.f2]) AS u(bandera, filas)
UNION ALL
SELECT 'support_tickets' AS tabla, u.bandera, u.filas, m.total AS total_filas
FROM (SELECT count(*) AS total, count_if(flag_no_escalado_pero_estado_escalated) AS f1
      FROM churn_silver.support_tickets) m
CROSS JOIN UNNEST(ARRAY['flag_no_escalado_pero_estado_escalated'], ARRAY[m.f1]) AS u(bandera, filas)
UNION ALL
SELECT 'customer_summary' AS tabla, u.bandera, u.filas, m.total AS total_filas
FROM (SELECT count(*) AS total, count_if(flag_devoluciones_mayor_que_pedidos) AS f1, count_if(flag_clv_menor_que_gasto_total) AS f2
      FROM churn_silver.customer_summary) m
CROSS JOIN UNNEST(ARRAY['flag_devoluciones_mayor_que_pedidos', 'flag_clv_menor_que_gasto_total'], ARRAY[m.f1, m.f2]) AS u(bandera, filas)
ORDER BY tabla, filas DESC;
