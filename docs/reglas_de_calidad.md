# Catálogo de reglas de calidad

> Generado por `tools/generate_sql.py`. **Rechazo** = la fila va a `*_rejected` con su motivo. **Bandera** = la fila pasa a plata pero queda marcada en una columna `flag_*`.

> Completa la última columna con los números de `churn_silver.dq_findings`: así cada regla queda justificada con un hallazgo (criterio de evaluación de la parte A).

> Fecha de corte de datos usada en las reglas de fechas: `DATE '2026-07-31'`.


## customers

| Tipo | Código | Condición SQL | Evidencia (filas en bronce) |
|---|---|---|---|
| Rechazo | `customer_id:repetido` | `rn_customer_id > 1 AND t_customer_id IS NOT NULL` |  |
| Rechazo | `customer_id:nulo_o_invalido` | `t_customer_id IS NULL` |  |
| Rechazo | `age:formato_invalido` | `t_age IS NULL AND NULLIF(trim(age), '') IS NOT NULL` |  |
| Rechazo | `signup_date:formato_invalido` | `t_signup_date IS NULL AND NULLIF(trim(signup_date), '') IS NOT NULL` |  |
| Rechazo | `tenure_months:formato_invalido` | `t_tenure_months IS NULL AND NULLIF(trim(tenure_months), '') IS NOT NULL` |  |
| Rechazo | `age:fuera_de_18_100` | `t_age < 18 OR t_age > 100` |  |
| Rechazo | `signup_date:fuera_de_rango` | `t_signup_date < DATE '2015-01-01' OR t_signup_date > DATE '2026-07-31'` |  |
| Rechazo | `tenure_months:fuera_de_0_120` | `t_tenure_months < 0 OR t_tenure_months > 120` |  |
| Bandera | `flag_tenure_no_cuadra_con_signup_date` | `abs(t_tenure_months - date_diff('month', t_signup_date, DATE '2026-07-31')) > 6` |  |

## orders

| Tipo | Código | Condición SQL | Evidencia (filas en bronce) |
|---|---|---|---|
| Rechazo | `order_id:repetido` | `rn_order_id > 1 AND t_order_id IS NOT NULL` |  |
| Rechazo | `order_id:nulo_o_invalido` | `t_order_id IS NULL` |  |
| Rechazo | `customer_id:nulo_o_invalido` | `t_customer_id IS NULL` |  |
| Rechazo | `order_date:nulo_o_invalido` | `t_order_date IS NULL` |  |
| Rechazo | `quantity:formato_invalido` | `t_quantity IS NULL AND NULLIF(trim(quantity), '') IS NOT NULL` |  |
| Rechazo | `unit_price:formato_invalido` | `t_unit_price IS NULL AND NULLIF(trim(unit_price), '') IS NOT NULL` |  |
| Rechazo | `discount_percent:formato_invalido` | `t_discount_percent IS NULL AND NULLIF(trim(discount_percent), '') IS NOT NULL` |  |
| Rechazo | `order_amount:formato_invalido` | `t_order_amount IS NULL AND NULLIF(trim(order_amount), '') IS NOT NULL` |  |
| Rechazo | `coupon_used:formato_invalido` | `t_coupon_used IS NULL AND NULLIF(trim(coupon_used), '') IS NOT NULL` |  |
| Rechazo | `delivery_days:formato_invalido` | `t_delivery_days IS NULL AND NULLIF(trim(delivery_days), '') IS NOT NULL` |  |
| Rechazo | `returned:formato_invalido` | `t_returned IS NULL AND NULLIF(trim(returned), '') IS NOT NULL` |  |
| Rechazo | `seller_rating:formato_invalido` | `t_seller_rating IS NULL AND NULLIF(trim(seller_rating), '') IS NOT NULL` |  |
| Rechazo | `customer_rating:formato_invalido` | `t_customer_rating IS NULL AND NULLIF(trim(customer_rating), '') IS NOT NULL` |  |
| Rechazo | `customer_id:sin_cliente_en_customers` | `fk_missing AND t_customer_id IS NOT NULL` |  |
| Rechazo | `order_date:fuera_de_rango` | `t_order_date < DATE '2015-01-01' OR t_order_date > DATE '2026-07-31'` |  |
| Rechazo | `quantity:no_positiva` | `t_quantity <= 0` |  |
| Rechazo | `unit_price:no_positivo` | `t_unit_price <= 0` |  |
| Rechazo | `discount_percent:fuera_de_0_100` | `t_discount_percent < 0 OR t_discount_percent > 100` |  |
| Rechazo | `order_amount:no_positivo` | `t_order_amount <= 0` |  |
| Rechazo | `delivery_days:fuera_de_0_60` | `t_delivery_days < 0 OR t_delivery_days > 60` |  |
| Rechazo | `order_status:valor_no_permitido` | `t_order_status IS NULL OR lower(t_order_status) NOT IN ('delivered', 'cancelled', 'returned')` |  |
| Rechazo | `seller_rating:fuera_de_1_5` | `t_seller_rating < 1 OR t_seller_rating > 5` |  |
| Rechazo | `customer_rating:fuera_de_1_5` | `t_customer_rating < 1 OR t_customer_rating > 5` |  |
| Bandera | `flag_devuelto_sin_motivo` | `COALESCE(t_returned, false) AND t_return_reason IS NULL` |  |
| Bandera | `flag_motivo_sin_devolucion` | `NOT COALESCE(t_returned, false) AND t_return_reason IS NOT NULL` |  |
| Bandera | `flag_estado_vs_devuelto` | `(lower(t_order_status) = 'cancelled' AND COALESCE(t_returned, false)) OR (lower(t_order_status) = 'returned' AND NOT COALESCE(t_returned, false))` |  |
| Bandera | `flag_monto_no_cuadra` | `t_order_amount IS NOT NULL AND abs(t_order_amount - t_quantity * t_unit_price * (1 - t_discount_percent / 100.0)) > 0.05 * t_order_amount` |  |

## engagement

| Tipo | Código | Condición SQL | Evidencia (filas en bronce) |
|---|---|---|---|
| Rechazo | `customer_id:repetido` | `rn_customer_id > 1 AND t_customer_id IS NOT NULL` |  |
| Rechazo | `customer_id:nulo_o_invalido` | `t_customer_id IS NULL` |  |
| Rechazo | `app_usage_minutes:formato_invalido` | `t_app_usage_minutes IS NULL AND NULLIF(trim(app_usage_minutes), '') IS NOT NULL` |  |
| Rechazo | `website_sessions:formato_invalido` | `t_website_sessions IS NULL AND NULLIF(trim(website_sessions), '') IS NOT NULL` |  |
| Rechazo | `avg_session_duration:formato_invalido` | `t_avg_session_duration IS NULL AND NULLIF(trim(avg_session_duration), '') IS NOT NULL` |  |
| Rechazo | `search_frequency:formato_invalido` | `t_search_frequency IS NULL AND NULLIF(trim(search_frequency), '') IS NOT NULL` |  |
| Rechazo | `pages_viewed:formato_invalido` | `t_pages_viewed IS NULL AND NULLIF(trim(pages_viewed), '') IS NOT NULL` |  |
| Rechazo | `wishlist_items:formato_invalido` | `t_wishlist_items IS NULL AND NULLIF(trim(wishlist_items), '') IS NOT NULL` |  |
| Rechazo | `cart_abandon_rate:formato_invalido` | `t_cart_abandon_rate IS NULL AND NULLIF(trim(cart_abandon_rate), '') IS NOT NULL` |  |
| Rechazo | `notification_click_rate:formato_invalido` | `t_notification_click_rate IS NULL AND NULLIF(trim(notification_click_rate), '') IS NOT NULL` |  |
| Rechazo | `email_open_rate:formato_invalido` | `t_email_open_rate IS NULL AND NULLIF(trim(email_open_rate), '') IS NOT NULL` |  |
| Rechazo | `days_since_last_login:formato_invalido` | `t_days_since_last_login IS NULL AND NULLIF(trim(days_since_last_login), '') IS NOT NULL` |  |
| Rechazo | `customer_id:sin_cliente_en_customers` | `fk_missing AND t_customer_id IS NOT NULL` |  |
| Rechazo | `app_usage_minutes:negativo` | `t_app_usage_minutes < 0` |  |
| Rechazo | `website_sessions:negativo` | `t_website_sessions < 0` |  |
| Rechazo | `avg_session_duration:negativo` | `t_avg_session_duration < 0` |  |
| Rechazo | `search_frequency:negativo` | `t_search_frequency < 0` |  |
| Rechazo | `pages_viewed:negativo` | `t_pages_viewed < 0` |  |
| Rechazo | `wishlist_items:negativo` | `t_wishlist_items < 0` |  |
| Rechazo | `cart_abandon_rate:fuera_de_0_1` | `t_cart_abandon_rate < 0 OR t_cart_abandon_rate > 1` |  |
| Rechazo | `notification_click_rate:fuera_de_0_1` | `t_notification_click_rate < 0 OR t_notification_click_rate > 1` |  |
| Rechazo | `email_open_rate:fuera_de_0_1` | `t_email_open_rate < 0 OR t_email_open_rate > 1` |  |
| Rechazo | `days_since_last_login:fuera_de_0_730` | `t_days_since_last_login < 0 OR t_days_since_last_login > 730` |  |

## payments

| Tipo | Código | Condición SQL | Evidencia (filas en bronce) |
|---|---|---|---|
| Rechazo | `payment_id:repetido` | `rn_payment_id > 1 AND t_payment_id IS NOT NULL` |  |
| Rechazo | `customer_id:repetido` | `rn_customer_id > 1 AND t_customer_id IS NOT NULL` |  |
| Rechazo | `payment_id:nulo_o_invalido` | `t_payment_id IS NULL` |  |
| Rechazo | `customer_id:nulo_o_invalido` | `t_customer_id IS NULL` |  |
| Rechazo | `payment_failures:formato_invalido` | `t_payment_failures IS NULL AND NULLIF(trim(payment_failures), '') IS NOT NULL` |  |
| Rechazo | `refund_amount:formato_invalido` | `t_refund_amount IS NULL AND NULLIF(trim(refund_amount), '') IS NOT NULL` |  |
| Rechazo | `subscription_active:formato_invalido` | `t_subscription_active IS NULL AND NULLIF(trim(subscription_active), '') IS NOT NULL` |  |
| Rechazo | `subscription_fee:formato_invalido` | `t_subscription_fee IS NULL AND NULLIF(trim(subscription_fee), '') IS NOT NULL` |  |
| Rechazo | `average_monthly_spend:formato_invalido` | `t_average_monthly_spend IS NULL AND NULLIF(trim(average_monthly_spend), '') IS NOT NULL` |  |
| Rechazo | `last_payment_date:formato_invalido` | `t_last_payment_date IS NULL AND NULLIF(trim(last_payment_date), '') IS NOT NULL` |  |
| Rechazo | `customer_id:sin_cliente_en_customers` | `fk_missing AND t_customer_id IS NOT NULL` |  |
| Rechazo | `payment_failures:negativo` | `t_payment_failures < 0` |  |
| Rechazo | `refund_amount:negativo` | `t_refund_amount < 0` |  |
| Rechazo | `subscription_fee:negativo` | `t_subscription_fee < 0` |  |
| Rechazo | `average_monthly_spend:negativo` | `t_average_monthly_spend < 0` |  |
| Rechazo | `payment_status:valor_no_permitido` | `t_payment_status IS NULL OR lower(t_payment_status) NOT IN ('success', 'failed', 'pending', 'refunded')` |  |
| Bandera | `flag_fecha_pago_futura` | `t_last_payment_date > DATE '2026-07-31'` |  |
| Bandera | `flag_suscripcion_inactiva_con_tarifa` | `NOT COALESCE(t_subscription_active, false) AND t_subscription_fee > 0` |  |

## support_tickets

| Tipo | Código | Condición SQL | Evidencia (filas en bronce) |
|---|---|---|---|
| Rechazo | `ticket_id:repetido` | `rn_ticket_id > 1 AND t_ticket_id IS NOT NULL` |  |
| Rechazo | `ticket_id:nulo_o_invalido` | `t_ticket_id IS NULL` |  |
| Rechazo | `customer_id:nulo_o_invalido` | `t_customer_id IS NULL` |  |
| Rechazo | `tickets_last_year:formato_invalido` | `t_tickets_last_year IS NULL AND NULLIF(trim(tickets_last_year), '') IS NOT NULL` |  |
| Rechazo | `avg_resolution_hours:formato_invalido` | `t_avg_resolution_hours IS NULL AND NULLIF(trim(avg_resolution_hours), '') IS NOT NULL` |  |
| Rechazo | `satisfaction_score:formato_invalido` | `t_satisfaction_score IS NULL AND NULLIF(trim(satisfaction_score), '') IS NOT NULL` |  |
| Rechazo | `escalated:formato_invalido` | `t_escalated IS NULL AND NULLIF(trim(escalated), '') IS NOT NULL` |  |
| Rechazo | `customer_id:sin_cliente_en_customers` | `fk_missing AND t_customer_id IS NOT NULL` |  |
| Rechazo | `tickets_last_year:negativo` | `t_tickets_last_year < 0` |  |
| Rechazo | `avg_resolution_hours:negativo` | `t_avg_resolution_hours < 0` |  |
| Rechazo | `satisfaction_score:fuera_de_1_5` | `t_satisfaction_score < 1 OR t_satisfaction_score > 5` |  |
| Rechazo | `issue_status:valor_no_permitido` | `t_issue_status IS NULL OR lower(t_issue_status) NOT IN ('closed', 'resolved', 'escalated', 'open')` |  |
| Bandera | `flag_no_escalado_pero_estado_escalated` | `NOT COALESCE(t_escalated, false) AND lower(t_issue_status) = 'escalated'` |  |

## customer_summary

| Tipo | Código | Condición SQL | Evidencia (filas en bronce) |
|---|---|---|---|
| Rechazo | `customer_id:repetido` | `rn_customer_id > 1 AND t_customer_id IS NOT NULL` |  |
| Rechazo | `customer_id:nulo_o_invalido` | `t_customer_id IS NULL` |  |
| Rechazo | `churn:nulo_o_invalido` | `t_churn IS NULL` |  |
| Rechazo | `total_orders:formato_invalido` | `t_total_orders IS NULL AND NULLIF(trim(total_orders), '') IS NOT NULL` |  |
| Rechazo | `total_spent:formato_invalido` | `t_total_spent IS NULL AND NULLIF(trim(total_spent), '') IS NOT NULL` |  |
| Rechazo | `average_order_value:formato_invalido` | `t_average_order_value IS NULL AND NULLIF(trim(average_order_value), '') IS NOT NULL` |  |
| Rechazo | `total_returns:formato_invalido` | `t_total_returns IS NULL AND NULLIF(trim(total_returns), '') IS NOT NULL` |  |
| Rechazo | `return_rate:formato_invalido` | `t_return_rate IS NULL AND NULLIF(trim(return_rate), '') IS NOT NULL` |  |
| Rechazo | `loyalty_points:formato_invalido` | `t_loyalty_points IS NULL AND NULLIF(trim(loyalty_points), '') IS NOT NULL` |  |
| Rechazo | `last_purchase_days:formato_invalido` | `t_last_purchase_days IS NULL AND NULLIF(trim(last_purchase_days), '') IS NOT NULL` |  |
| Rechazo | `purchase_frequency:formato_invalido` | `t_purchase_frequency IS NULL AND NULLIF(trim(purchase_frequency), '') IS NOT NULL` |  |
| Rechazo | `lifetime_value:formato_invalido` | `t_lifetime_value IS NULL AND NULLIF(trim(lifetime_value), '') IS NOT NULL` |  |
| Rechazo | `churn_risk_score:formato_invalido` | `t_churn_risk_score IS NULL AND NULLIF(trim(churn_risk_score), '') IS NOT NULL` |  |
| Rechazo | `customer_id:sin_cliente_en_customers` | `fk_missing AND t_customer_id IS NOT NULL` |  |
| Rechazo | `total_orders:negativo` | `t_total_orders < 0` |  |
| Rechazo | `total_spent:negativo` | `t_total_spent < 0` |  |
| Rechazo | `average_order_value:negativo` | `t_average_order_value < 0` |  |
| Rechazo | `total_returns:negativo` | `t_total_returns < 0` |  |
| Rechazo | `loyalty_points:negativo` | `t_loyalty_points < 0` |  |
| Rechazo | `last_purchase_days:negativo` | `t_last_purchase_days < 0` |  |
| Rechazo | `purchase_frequency:negativo` | `t_purchase_frequency < 0` |  |
| Rechazo | `lifetime_value:negativo` | `t_lifetime_value < 0` |  |
| Rechazo | `return_rate:fuera_de_0_1` | `t_return_rate < 0 OR t_return_rate > 1` |  |
| Rechazo | `churn_risk_score:fuera_de_0_100` | `t_churn_risk_score < 0 OR t_churn_risk_score > 100` |  |
| Bandera | `flag_devoluciones_mayor_que_pedidos` | `t_total_returns > t_total_orders` |  |
| Bandera | `flag_clv_menor_que_gasto_total` | `t_lifetime_value < t_total_spent` |  |
