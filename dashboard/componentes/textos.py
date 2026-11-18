"""Etiquetas en español y el argumento del tablero, en un solo lugar."""

# El argumento central del proyecto (lo único que el tablero comparte con la presentación)
IDEA_CENTRAL = ("El churn no depende de quién es el cliente sino de cómo compra: con pedidos, gasto y devoluciones, "
                "el modelo encuentra 3,5 veces más clientes que se van que el azar y le dice a cada uno qué "
                "campaña necesita.")

# --- Variables y términos del modelo ------------------------------------------------------------------------------
VARIABLES_MODELO = {
    "summary_total_orders": "Pedidos",
    "total_spent": "Gasto total (₹)",
    "average_order_value": "Valor promedio por pedido (₹)",
    "total_returns": "Devoluciones",
}
TERMINOS = {
    "summary_total_orders": "Pedidos",
    "total_spent": "Gasto total",
    "average_order_value": "Valor promedio",
    "total_returns": "Devoluciones",
    "summary_total_orders & total_returns": "Pedidos × devoluciones",
}
MOTIVO_EN_FRASE = {
    "summary_total_orders": "tiene pocos pedidos",
    "total_spent": "su gasto total es bajo",
    "average_order_value": "su valor promedio por pedido",
    "total_returns": "sus devoluciones",
    "summary_total_orders & total_returns": "la combinación de pocos pedidos y devoluciones",
}
VARIABLES_RETIRADAS = {
    "last_purchase_days": "Días desde la última compra",
    "return_rate": "Tasa de devolución",
    "purchase_frequency": "Frecuencia de compra",
}

# --- Filtros -------------------------------------------------------------------------------------------------------
NOMBRES_FILTRO = {
    "membership_tier": "Membresía",
    "city": "Ciudad",
    "preferred_device": "Dispositivo",
    "referral_source": "Canal de llegada",
    "campana": "Campaña sugerida",
}

# --- Casos de ejemplo de la ficha (clientes de test) --------------------------------------------------------------
CASOS = {
    1340006: "Riesgo alto por pocos pedidos (el del PPT)",
    1070128: "Alto valor en riesgo",
    1000863: "Riesgo por devoluciones",
    1113773: "Riesgo bajo, cliente fiel",
    1002569: "Falsa alarma",
    1000074: "Se escapó",
}
