"""Pipeline de limpieza decidido en el EDA (sección 3 del notebook 01_eda_calidad).

Aquí solo van las reglas DETERMINISTAS: se aplican igual a cualquier cliente (train, test o un cliente
nuevo que llegue a la API) y no aprenden nada de los datos. Las transformaciones que sí aprenden
(imputación, escalado, codificación) van en el pipeline del modelado y se ajustan solo con train.

Uso:
    from churn.features import crear_pipeline_limpieza
    limpio = crear_pipeline_limpieza().fit_transform(customer_360)

Cada regla se documenta en la tabla "Pipeline de limpieza" del notebook y en docs/eda_decisiones.md.
"""
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline

FECHA_CORTE = pd.Timestamp("2026-07-31")  # misma fecha de corte de las reglas de plata (CUT)

OBJETIVO = "churn"
LLAVE = "customer_id"

# Diccionario de customer_360 por grupo temático (de sql/04_gold/01_customer_360.sql)
GRUPOS_VARIABLES = {
    "Perfil": [
        "age", "gender", "city", "state", "signup_date", "tenure_months", "membership_tier",
        "occupation", "income_group", "marital_status", "education", "preferred_device", "referral_source",
    ],
    "Interacción digital": [
        "app_usage_minutes", "website_sessions", "avg_session_duration", "search_frequency",
        "pages_viewed", "wishlist_items", "cart_abandon_rate", "notification_click_rate",
        "email_open_rate", "days_since_last_login",
    ],
    "Pagos": [
        "usual_payment_method", "last_payment_status", "payment_failures", "refund_amount",
        "subscription_active", "subscription_fee", "average_monthly_spend", "last_payment_date",
        "payment_date_in_future",
    ],
    "Resumen de cliente": [
        "summary_total_orders", "total_spent", "average_order_value", "total_returns", "return_rate",
        "loyalty_points", "last_purchase_days", "purchase_frequency", "lifetime_value",
        "customer_segment", "churn_risk_score",
    ],
    "Pedidos (recalculados)": [
        "orders_n", "orders_amount_sum", "orders_amount_avg", "first_order_date", "last_order_date",
        "days_since_last_order", "orders_last_3m", "orders_last_6m", "orders_last_12m",
        "orders_cancelled_n", "orders_status_returned_n", "orders_returned_flag_n",
        "orders_discount_avg", "orders_coupon_share", "orders_delivery_days_avg",
        "orders_customer_rating_avg",
    ],
    "Soporte": [
        "tickets_n", "tickets_last_year_max", "tickets_resolution_hours_avg",
        "tickets_satisfaction_avg", "tickets_satisfaction_min", "tickets_escalated_n",
    ],
    "Indicadores": ["has_orders", "has_tickets", "summary_vs_orders_mismatch"],
}

COLUMNAS_FECHA = ["signup_date", "last_payment_date", "first_order_date", "last_order_date"]

# Origen y descripción de cada columna de customer_360. Las de tablas del dataset vienen de data_dictionary.xlsx
# del autor; las "Calculada" no están en ese diccionario y se definen en sql/03_silver y sql/04_gold.
DESCRIPCIONES = {
    "customer_id": ("customers", "Identificador único del cliente"),
    "age": ("customers", "Edad"),
    "gender": ("customers", "Género"),
    "city": ("customers", "Ciudad"),
    "state": ("customers", "Estado"),
    "signup_date": ("customers", "Fecha de registro"),
    "tenure_months": ("customers", "Antigüedad del cliente"),
    "membership_tier": ("customers", "Nivel de membresía"),
    "occupation": ("customers", "Profesión"),
    "income_group": ("customers", "Categoría de ingresos"),
    "marital_status": ("customers", "Estado civil"),
    "education": ("customers", "Nivel educativo más alto"),
    "preferred_device": ("customers", "Plataforma preferida"),
    "referral_source": ("customers", "Fuente de adquisición"),
    "app_usage_minutes": ("engagement", "Tiempo de uso de la aplicación"),
    "website_sessions": ("engagement", "Número de sesiones"),
    "avg_session_duration": ("engagement", "Duración promedio de la sesión"),
    "search_frequency": ("engagement", "Búsquedas"),
    "pages_viewed": ("engagement", "Páginas vistas"),
    "wishlist_items": ("engagement", "Artículos en la lista de deseos"),
    "cart_abandon_rate": ("engagement", "Proporción de abandono del carrito"),
    "notification_click_rate": ("engagement", "Tasa de clics en notificaciones"),
    "email_open_rate": ("engagement", "Proporción de apertura de correos"),
    "days_since_last_login": ("engagement", "Días desde el último ingreso"),
    "usual_payment_method": ("payments", "Método de pago (payment_method)"),
    "last_payment_status": ("payments", "Estado de la transacción (payment_status)"),
    "payment_failures": ("payments", "Pagos fallidos"),
    "refund_amount": ("payments", "Valor reembolsado"),
    "subscription_active": ("payments", "Estado de la suscripción"),
    "subscription_fee": ("payments", "Tarifa de la suscripción"),
    "average_monthly_spend": ("payments", "Gasto mensual promedio"),
    "last_payment_date": ("payments", "Fecha del último pago"),
    "payment_date_in_future": ("Calculada: payments", "last_payment_date es posterior al 2026-07-31"),
    "summary_total_orders": ("customer_summary", "Total de pedidos (total_orders)"),
    "total_spent": ("customer_summary", "Gasto total"),
    "average_order_value": ("customer_summary", "Valor promedio del pedido"),
    "total_returns": ("customer_summary", "Número de devoluciones"),
    "return_rate": ("customer_summary", "Porcentaje de devoluciones"),
    "loyalty_points": ("customer_summary", "Puntos de lealtad"),
    "last_purchase_days": ("customer_summary", "Días desde la última compra"),
    "purchase_frequency": ("customer_summary", "Frecuencia de compra"),
    "lifetime_value": ("customer_summary", "Valor de vida del cliente (CLV)"),
    "customer_segment": ("customer_summary", "Segmento del cliente"),
    "churn_risk_score": ("customer_summary", "Riesgo de abandono estimado (0 a 100)"),
    "orders_n": ("Calculada: orders", "Número de pedidos (0 si no tiene)"),
    "orders_amount_sum": ("Calculada: orders", "Suma de order_amount"),
    "orders_amount_avg": ("Calculada: orders", "Promedio de order_amount"),
    "first_order_date": ("Calculada: orders", "Fecha del primer pedido"),
    "last_order_date": ("Calculada: orders", "Fecha del último pedido"),
    "days_since_last_order": ("Calculada: orders", "Días entre el último pedido y el pedido más reciente del dataset"),
    "orders_last_3m": ("Calculada: orders", "Pedidos en los 3 meses previos al pedido más reciente del dataset"),
    "orders_last_6m": ("Calculada: orders", "Pedidos en los 6 meses previos al pedido más reciente del dataset"),
    "orders_last_12m": ("Calculada: orders", "Pedidos en los 12 meses previos al pedido más reciente del dataset"),
    "orders_cancelled_n": ("Calculada: orders", "Pedidos con order_status = Cancelled"),
    "orders_status_returned_n": ("Calculada: orders", "Pedidos con order_status = Returned"),
    "orders_returned_flag_n": ("Calculada: orders", "Pedidos con returned = verdadero"),
    "orders_discount_avg": ("Calculada: orders", "Promedio de discount_percent"),
    "orders_coupon_share": ("Calculada: orders", "Proporción de pedidos con cupón"),
    "orders_delivery_days_avg": ("Calculada: orders", "Promedio de delivery_days"),
    "orders_customer_rating_avg": ("Calculada: orders", "Promedio de customer_rating"),
    "tickets_n": ("Calculada: support_tickets", "Número de tickets (0 si no tiene)"),
    "tickets_last_year_max": ("Calculada: support_tickets", "Máximo de tickets_last_year"),
    "tickets_resolution_hours_avg": ("Calculada: support_tickets", "Promedio de avg_resolution_hours"),
    "tickets_satisfaction_avg": ("Calculada: support_tickets", "Promedio de satisfaction_score"),
    "tickets_satisfaction_min": ("Calculada: support_tickets", "Mínimo de satisfaction_score"),
    "tickets_escalated_n": ("Calculada: support_tickets", "Tickets con escalated = verdadero"),
    "has_orders": ("Calculada: orders", "El cliente tiene al menos un pedido"),
    "has_tickets": ("Calculada: support_tickets", "El cliente tiene al menos un ticket"),
    "summary_vs_orders_mismatch": ("Calculada: customer_summary y orders", "total_orders es distinto de orders_n"),
    "churn": ("customer_summary", "Etiqueta de abandono (Yes/No en el dataset)"),
}

# El modelado no debe usarlas como predictoras (auditoría de la sección 5.3): churn_risk_score es fuga directa y
# customer_segment resume otras columnas de customer_summary
COLUMNAS_FUGA = ["churn_risk_score", "customer_segment"]

# Variables redundantes que el modelado no debe usar como predictoras (sección 5.4). Siguen en customer_360:
# lifetime_value se usa para priorizar clientes por valor
COLUMNAS_REDUNDANTES = ["loyalty_points", "lifetime_value", "orders_status_returned_n"]

# Variables del escenario principal fijadas en el EDA (secciones 5.3 y 5.4). El modelo final usa VARIABLES_MODELO_FINAL.
# El escenario de comparación usa las demás
# variables de customer_360 que no pertenecen a customer_summary, sin COLUMNAS_FUGA ni COLUMNAS_REDUNDANTES
VARIABLES_ESCENARIO_PRINCIPAL = [
    "summary_total_orders", "total_spent", "average_order_value", "total_returns", "return_rate",
    "last_purchase_days", "purchase_frequency",
]

# Variables del escenario principal con las que parece construida la etiqueta (sección 5.6 de 02_modelado). Con ellas
# el ROC-AUC llega a 1, así que el modelado las retira por fuga (sección 5.7 de 02_modelado). El orden se conserva
# porque la sección 5.6 prueba también sus primeros subconjuntos
COLUMNAS_FUGA_ETIQUETA = ["last_purchase_days", "return_rate", "purchase_frequency"]

# Variables del modelo final: el escenario principal sin COLUMNAS_FUGA_ETIQUETA. Son las que recibe la API
VARIABLES_MODELO_FINAL = [v for v in VARIABLES_ESCENARIO_PRINCIPAL if v not in COLUMNAS_FUGA_ETIQUETA]

# Columnas que la calidad de datos decidió no usar, cada una con su regla (sección 3.7 del notebook)
COLUMNAS_DESCARTADAS = [
    "last_payment_date",       # Regla 2: 41,66 % posterior a la fecha de corte; no se puede corregir
    "payment_date_in_future",  # Regla 2: marca un problema de calidad de esa fecha, no un comportamiento del cliente
    "summary_vs_orders_mismatch",  # Regla 3: marca una inconsistencia entre fuentes, no un comportamiento del cliente
]


def variables_escenario_comparacion(df):
    """Variables del escenario de comparación: las columnas de `df` que no son llave, objetivo ni fechas, sin las
    descartadas por calidad, las de customer_summary ni las redundantes."""
    excluidas = {LLAVE, OBJETIVO, *COLUMNAS_FECHA, *COLUMNAS_DESCARTADAS, *COLUMNAS_FUGA, *COLUMNAS_REDUNDANTES,
                 *GRUPOS_VARIABLES["Resumen de cliente"]}
    return [c for c in df.columns if c not in excluidas]


class DerivarAntiguedad(TransformerMixin, BaseEstimator):
    """Regla 1 (Consistencia): antigüedad en meses calculada desde `signup_date` hasta la fecha de corte.

    Se agrega junto a `tenure_months`, que no cuadra con `signup_date` en la mayoría de los clientes. Ninguna
    de las 2 medidas se trata como la verdadera (decisión de la sección 3.4).
    """

    def __init__(self, fecha_corte=FECHA_CORTE):
        self.fecha_corte = fecha_corte

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X = X.copy()
        signup = pd.to_datetime(X["signup_date"])
        X["antiguedad_meses"] = (self.fecha_corte - signup).dt.days / 30.44
        return X


class DescartarColumnas(TransformerMixin, BaseEstimator):
    """Quita las columnas que la calidad de datos o la auditoría de fuga decidieron no usar."""

    def __init__(self, columnas=()):
        self.columnas = columnas

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return X.drop(columns=[c for c in self.columnas if c in X.columns])


def crear_pipeline_limpieza():
    """Pipeline con las reglas deterministas de limpieza, en el orden de la tabla del notebook."""
    return Pipeline([
        ("derivar_antiguedad", DerivarAntiguedad()),
        ("descartar_columnas", DescartarColumnas(COLUMNAS_DESCARTADAS)),
    ])
