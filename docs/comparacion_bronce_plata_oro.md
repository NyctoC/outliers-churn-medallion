# Comparación bronce vs plata vs oro

Consulta: *ingresos y pedidos por categoría de producto en 2025* sobre `orders` (1.000.000 de filas).
SQL en `sql/05_checks/04_comparison_queries.sql`. Mide cada consulta **dos veces** con
*Reuse query results* desactivado y anota la segunda ejecución.

| Capa | Tabla | Formato | Datos escaneados (bytes) | Tiempo (s) | Filas leídas aprox. |
|---|---|---|---|---|---|
| Bronce | `churn_bronze.orders` | CSV (texto) |  |  | 1.000.000 |
| Plata | `churn_silver.orders` | Iceberg / Parquet, partición por año |  |  |  |
| Oro | `churn_gold.orders_monthly_category` | Iceberg / Parquet, agregado |  |  |  |

## Interpretación (completa con tus números)

Ideas para argumentar (verifícalas con lo que midas):

- **Bronce**: CSV es un formato *por filas*; Athena debe leer el archivo completo aunque la consulta use 3 de
  17 columnas, y además convierte textos a números al vuelo. No hay compresión ni estadísticas.
- **Plata**: Parquet es *columnar* y comprimido: solo se leen las columnas usadas (`product_category`,
  `order_amount`, `order_date`) y la partición por año evita leer los demás años.
- **Oro**: la agregación ya está hecha; se leen unos pocos miles de filas en vez de un millón.
- Lo que "pagas" (bytes escaneados) y lo que "esperas" (tiempo) mejoran a medida que subes de capa, a cambio de
  perder detalle (oro) o de pagar el costo único de construir la capa (plata y oro).
