-- ==============================================================================
-- COMPARACIÓN: la MISMA pregunta sobre bronce, plata y oro (tabla orders, 1.000.000 de filas)
-- Pregunta: ¿cuántos pedidos e ingresos tuvo cada categoría de producto en 2025?
--
-- Cómo medir (hazlo para cada consulta, 2 veces cada una, y anota la segunda):
--   1) En Athena, pestaña "Query stats" (o debajo del resultado): copia
--        - Data scanned  (bytes escaneados)
--        - Run time      (tiempo de ejecución)
--   2) Asegúrate de que "Reuse query results" esté DESACTIVADO, si no verás 0 bytes.
--   3) Anota los números en docs/comparacion_bronce_plata_oro.md
-- Ejecuta cada consulta por separado.
-- ==============================================================================

-- ---- A) BRONCE (CSV, todo texto: hay que convertir tipos al vuelo) ----------------
SELECT product_category,
       count(*)                                  AS orders_n,
       sum(TRY_CAST(order_amount AS double))     AS revenue
FROM churn_bronze.orders
WHERE substr(order_date, 1, 4) = '2025'
GROUP BY product_category
ORDER BY product_category;

-- ---- B) PLATA (Iceberg/Parquet, tipada, particionada por año de order_date) ----------
SELECT product_category,
       count(*)           AS orders_n,
       sum(order_amount)  AS revenue
FROM churn_silver.orders
WHERE order_date >= DATE '2025-01-01' AND order_date < DATE '2026-01-01'
GROUP BY product_category
ORDER BY product_category;

-- ---- C) ORO (agregado mes x categoría, pocos miles de filas) -----------------------
SELECT product_category,
       sum(orders_n)  AS orders_n,
       sum(revenue)   AS revenue
FROM churn_gold.orders_monthly_category
WHERE order_month >= DATE '2025-01-01' AND order_month < DATE '2026-01-01'
GROUP BY product_category
ORDER BY product_category;

-- NOTA: los resultados de A, B y C deben coincidir, salvo por las filas que plata rechazó.
--       Si hay rechazadas, la diferencia es justamente lo que limpió la capa plata.

-- ==============================================================================
-- Sanidad del oro
-- ==============================================================================

-- customer_360 debe tener una fila por cliente válido de plata:
SELECT (SELECT count(*) FROM churn_silver.customers)  AS clientes_plata,
       (SELECT count(*) FROM churn_gold.customer_360) AS filas_customer_360,
       (SELECT count(DISTINCT customer_id) FROM churn_gold.customer_360) AS clientes_distintos_360;

-- Distribución de la variable objetivo (esperado ~20,7 % de churn):
SELECT churn, count(*) AS clientes,
       round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS pct
FROM churn_gold.customer_360
GROUP BY churn;

-- ¿Cuántos clientes no tienen pedidos / tickets? (esperado ~13,5 % y ~74,1 %)
SELECT count_if(NOT has_orders)  AS sin_pedidos,
       count_if(NOT has_tickets) AS sin_tickets,
       count_if(summary_vs_orders_mismatch) AS resumen_no_coincide_con_orders
FROM churn_gold.customer_360;
