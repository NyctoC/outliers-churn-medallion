#!/usr/bin/env python3
"""
Genera los scripts SQL de bronce, hallazgos, plata y verificaciones a partir de UNA sola
especificación (columnas + reglas de calidad). Así las listas de columnas son idénticas en todas
las capas y las reglas se cambian en un solo lugar.

Uso (desde la raíz del repo):
    python tools/generate_sql.py

Los scripts de oro (sql/04_gold) y las consultas de comparación se escriben a mano y NO se tocan.
No necesita instalar nada: solo Python 3.8+.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL = ROOT / "sql"
DOCS = ROOT / "docs"

# ----------------------------------------------------------------------------------------------
# Parámetros del proyecto
# ----------------------------------------------------------------------------------------------
BUCKET = "YOUR_BUCKET"                 # <- se reemplaza a mano en los .sql (Ctrl+Shift+H en VS Code)
CUT = "DATE '2026-07-31'"              # fecha de corte de los datos: publicación de la v2 en Kaggle
DB_B, DB_S, DB_G = "churn_bronze", "churn_silver", "churn_gold"
FK_TABLE_SILVER = f"{DB_S}.customers"

# ----------------------------------------------------------------------------------------------
# Helpers para escribir reglas
# ----------------------------------------------------------------------------------------------
def neg(c):
    return (f"{c}:negativo", f"t_{c} < 0")

def rng(c, lo, hi):
    return (f"{c}:fuera_de_{lo}_{hi}", f"t_{c} < {lo} OR t_{c} > {hi}")

def dom(c, values):
    lst = ", ".join(f"'{v}'" for v in values)
    return (f"{c}:valor_no_permitido", f"t_{c} IS NULL OR lower(t_{c}) NOT IN ({lst})")

# ----------------------------------------------------------------------------------------------
# Especificación de las 6 tablas (orden = orden de columnas en el CSV de Kaggle)
# kinds: id | int | dbl | str | date | bool
# rules  = RECHAZAN la fila (van a *_rejected con su motivo)
# flags  = NO rechazan; se guardan como columna booleana flag_* en plata
# ----------------------------------------------------------------------------------------------
TABLES = [
    dict(
        name="customers", pk="customer_id", fk=False,
        required=["customer_id"], unique=["customer_id"],
        cols=[("customer_id", "id"), ("first_name", "str"), ("last_name", "str"), ("age", "int"),
              ("gender", "str"), ("city", "str"), ("state", "str"), ("country", "str"),
              ("signup_date", "date"), ("tenure_months", "int"), ("membership_tier", "str"),
              ("occupation", "str"), ("income_group", "str"), ("marital_status", "str"),
              ("education", "str"), ("preferred_device", "str"), ("referral_source", "str")],
        rules=[rng("age", 18, 100),
               ("signup_date:fuera_de_rango", f"t_signup_date < DATE '2015-01-01' OR t_signup_date > {CUT}"),
               rng("tenure_months", 0, 120)],
        flags=[("tenure_no_cuadra_con_signup_date",
                f"abs(t_tenure_months - date_diff('month', t_signup_date, {CUT})) > 6")],
        partition=None,
    ),
    dict(
        name="orders", pk="order_id", fk=True,
        required=["order_id", "customer_id", "order_date"], unique=["order_id"],
        cols=[("order_id", "id"), ("customer_id", "id"), ("order_date", "date"),
              ("product_category", "str"), ("product_name", "str"), ("quantity", "int"),
              ("unit_price", "dbl"), ("discount_percent", "dbl"), ("order_amount", "dbl"),
              ("payment_method", "str"), ("coupon_used", "bool"), ("delivery_days", "int"),
              ("order_status", "str"), ("returned", "bool"), ("return_reason", "str"),
              ("seller_rating", "dbl"), ("customer_rating", "int")],
        rules=[("order_date:fuera_de_rango", f"t_order_date < DATE '2015-01-01' OR t_order_date > {CUT}"),
               ("quantity:no_positiva", "t_quantity <= 0"),
               ("unit_price:no_positivo", "t_unit_price <= 0"),
               rng("discount_percent", 0, 100),
               ("order_amount:no_positivo", "t_order_amount <= 0"),
               rng("delivery_days", 0, 60),
               dom("order_status", ["delivered", "cancelled", "returned"]),
               rng("seller_rating", 1, 5),
               rng("customer_rating", 1, 5)],
        flags=[("devuelto_sin_motivo", "COALESCE(t_returned, false) AND t_return_reason IS NULL"),
               ("motivo_sin_devolucion", "NOT COALESCE(t_returned, false) AND t_return_reason IS NOT NULL"),
               ("estado_vs_devuelto",
                "(lower(t_order_status) = 'cancelled' AND COALESCE(t_returned, false)) "
                "OR (lower(t_order_status) = 'returned' AND NOT COALESCE(t_returned, false))"),
               ("monto_no_cuadra",
                "t_order_amount IS NOT NULL AND abs(t_order_amount - t_quantity * t_unit_price "
                "* (1 - t_discount_percent / 100.0)) > 0.05 * t_order_amount")],
        partition="year(order_date)",
    ),
    dict(
        name="engagement", pk="customer_id", fk=True,
        required=["customer_id"], unique=["customer_id"],
        cols=[("customer_id", "id"), ("app_usage_minutes", "int"), ("website_sessions", "int"),
              ("avg_session_duration", "dbl"), ("search_frequency", "int"), ("pages_viewed", "int"),
              ("wishlist_items", "int"), ("cart_abandon_rate", "dbl"),
              ("notification_click_rate", "dbl"), ("email_open_rate", "dbl"),
              ("days_since_last_login", "int")],
        rules=[neg("app_usage_minutes"), neg("website_sessions"), neg("avg_session_duration"),
               neg("search_frequency"), neg("pages_viewed"), neg("wishlist_items"),
               rng("cart_abandon_rate", 0, 1), rng("notification_click_rate", 0, 1),
               rng("email_open_rate", 0, 1), rng("days_since_last_login", 0, 730)],
        flags=[],
        partition=None,
    ),
    dict(
        name="payments", pk="payment_id", fk=True,
        required=["payment_id", "customer_id"], unique=["payment_id", "customer_id"],
        cols=[("payment_id", "id"), ("customer_id", "id"), ("payment_method", "str"),
              ("payment_status", "str"), ("payment_failures", "int"), ("refund_amount", "dbl"),
              ("subscription_active", "bool"), ("subscription_fee", "dbl"),
              ("average_monthly_spend", "dbl"), ("last_payment_date", "date")],
        rules=[neg("payment_failures"), neg("refund_amount"), neg("subscription_fee"),
               neg("average_monthly_spend"),
               dom("payment_status", ["success", "failed", "pending", "refunded"])],
        flags=[("fecha_pago_futura", f"t_last_payment_date > {CUT}"),
               ("suscripcion_inactiva_con_tarifa",
                "NOT COALESCE(t_subscription_active, false) AND t_subscription_fee > 0")],
        partition=None,
    ),
    dict(
        name="support_tickets", pk="ticket_id", fk=True,
        required=["ticket_id", "customer_id"], unique=["ticket_id"],
        cols=[("ticket_id", "id"), ("customer_id", "id"), ("tickets_last_year", "int"),
              ("complaint_category", "str"), ("avg_resolution_hours", "dbl"),
              ("satisfaction_score", "dbl"), ("escalated", "bool"), ("issue_status", "str")],
        rules=[neg("tickets_last_year"), neg("avg_resolution_hours"),
               rng("satisfaction_score", 1, 5),
               dom("issue_status", ["closed", "resolved", "escalated", "open"])],
        flags=[("no_escalado_pero_estado_escalated",
                "NOT COALESCE(t_escalated, false) AND lower(t_issue_status) = 'escalated'")],
        partition=None,
    ),
    dict(
        name="customer_summary", pk="customer_id", fk=True,
        required=["customer_id", "churn"], unique=["customer_id"],
        cols=[("customer_id", "id"), ("total_orders", "int"), ("total_spent", "dbl"),
              ("average_order_value", "dbl"), ("total_returns", "int"), ("return_rate", "dbl"),
              ("loyalty_points", "int"), ("last_purchase_days", "int"),
              ("purchase_frequency", "dbl"), ("lifetime_value", "dbl"),
              ("customer_segment", "str"), ("churn_risk_score", "dbl"), ("churn", "bool")],
        rules=[neg("total_orders"), neg("total_spent"), neg("average_order_value"),
               neg("total_returns"), neg("loyalty_points"), neg("last_purchase_days"),
               neg("purchase_frequency"), neg("lifetime_value"),
               rng("return_rate", 0, 1), rng("churn_risk_score", 0, 100)],
        flags=[("devoluciones_mayor_que_pedidos", "t_total_returns > t_total_orders"),
               ("clv_menor_que_gasto_total", "t_lifetime_value < t_total_spent")],
        partition=None,
    ),
]

# ----------------------------------------------------------------------------------------------
# Piezas de SQL
# ----------------------------------------------------------------------------------------------
def typed_expr(c, kind):
    raw = f"trim(b.{c})"
    if kind in ("id", "int", "dbl"):
        sql_t = {"id": "bigint", "int": "integer", "dbl": "double"}[kind]
        return f"TRY_CAST(NULLIF({raw}, '') AS {sql_t})"
    if kind == "str":
        return f"NULLIF({raw}, '')"
    if kind == "date":
        return f"TRY_CAST(substr({raw}, 1, 10) AS date)"
    if kind == "bool":
        return (f"CASE WHEN lower({raw}) IN ('true','1','1.0','yes','y','t','si','sí') THEN true "
                f"WHEN lower({raw}) IN ('false','0','0.0','no','n','f') THEN false END")
    raise ValueError(kind)


def ranked_sql(t, fk_source):
    """Subconsulta que añade columnas t_* (tipadas), rn_* (duplicados) y fk_missing."""
    typed_cols = ",\n        ".join(f"{typed_expr(c, k)} AS t_{c}" for c, k in t["cols"])
    windows = "".join(
        f",\n      row_number() OVER (PARTITION BY typed.t_{u} ORDER BY typed.t_{u}) AS rn_{u}"
        for u in t["unique"])
    fk_cols, fk_join = "", ""
    if t["fk"]:
        fk_cols = ",\n      (fk.fk_id IS NULL) AS fk_missing"
        if fk_source == "bronze":
            fk_sub = (f"(SELECT DISTINCT TRY_CAST(NULLIF(trim(customer_id), '') AS bigint) AS fk_id\n"
                      f"       FROM {DB_B}.customers)")
        else:
            fk_sub = f"(SELECT customer_id AS fk_id FROM {FK_TABLE_SILVER})"
        fk_join = f"\n    LEFT JOIN {fk_sub} fk ON typed.t_customer_id = fk.fk_id"
    return (f"(\n    SELECT typed.*{windows}{fk_cols}\n    FROM (\n      SELECT b.*,\n        {typed_cols}\n"
            f"      FROM {DB_B}.{t['name']} b\n    ) typed{fk_join}\n  )")


def hard_checks(t):
    """[(codigo, condicion)] que RECHAZAN la fila."""
    out = []
    for u in t["unique"]:
        out.append((f"{u}:repetido", f"rn_{u} > 1 AND t_{u} IS NOT NULL"))
    for c in t["required"]:
        out.append((f"{c}:nulo_o_invalido", f"t_{c} IS NULL"))
    for c, k in t["cols"]:
        if k != "str" and c not in t["required"]:
            out.append((f"{c}:formato_invalido", f"t_{c} IS NULL AND NULLIF(trim({c}), '') IS NOT NULL"))
    if t["fk"]:
        out.append(("customer_id:sin_cliente_en_customers", "fk_missing AND t_customer_id IS NOT NULL"))
    out.extend(t["rules"])
    return out


def reject_expr(t):
    items = ",\n      ".join(f"CASE WHEN ({cond}) THEN '{code}' END" for code, cond in hard_checks(t))
    return f"array_join(ARRAY[\n      {items}\n    ], ';')"


def tbl_opts(location, partition=None):
    p = f",\n  partitioning = ARRAY['{partition}']" if partition else ""
    return (f"WITH (\n  table_type = 'ICEBERG',\n  is_external = false,\n  format = 'PARQUET',\n"
            f"  location = 's3://{BUCKET}/{location}/'{p}\n)")


def header(title, lines):
    body = "".join(f"-- {l}\n" for l in lines)
    return f"-- ==============================================================================\n-- {title}\n{body}-- ==============================================================================\n\n"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print("  escrito", path.relative_to(ROOT))


# ----------------------------------------------------------------------------------------------
# Generadores por capa
# ----------------------------------------------------------------------------------------------
def gen_bronze():
    out = header("BRONCE: tablas externas sobre los CSV crudos (todo como texto)",
                 ["Athena NO copia los datos: solo 'mira' los CSV que subiste a S3.",
                  "Cada tabla apunta a una CARPETA (no a un archivo): s3://BUCKET/bronze/<tabla>/",
                  "El orden de las columnas debe ser el mismo que el encabezado del CSV.",
                  "Antes de ejecutar: reemplaza YOUR_BUCKET por el nombre real de tu bucket."])
    for t in TABLES:
        cols = ",\n".join(f"  {c} string" for c, _ in t["cols"])
        out += (f"CREATE EXTERNAL TABLE IF NOT EXISTS {DB_B}.{t['name']} (\n{cols}\n)\n"
                f"ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'\n"
                f"WITH SERDEPROPERTIES ('separatorChar' = ',', 'quoteChar' = '\"')\n"
                f"STORED AS TEXTFILE\n"
                f"LOCATION 's3://{BUCKET}/bronze/{t['name']}/'\n"
                f"TBLPROPERTIES ('skip.header.line.count' = '1');\n\n")
    write(SQL / "01_bronze" / "01_create_bronze_tables.sql", out)

    out = header("BRONCE: verificación (¿Athena leyó bien los CSV?)",
                 ["Esperado: customers 500000 | orders 1000000 | engagement 500000 |",
                  "          payments 500000 | support_tickets 150000 | customer_summary 500000",
                  "Si algún valor se ve 'corrido' (p. ej. una ciudad en la columna age), el orden",
                  "de columnas del DDL no coincide con el CSV: corrígelo y recrea la tabla."])
    out += "SELECT 'customers' AS tabla, count(*) AS filas FROM {b}.customers\n".format(b=DB_B)
    for t in TABLES[1:]:
        out += f"UNION ALL SELECT '{t['name']}', count(*) FROM {DB_B}.{t['name']}\n"
    out += "ORDER BY tabla;\n\n-- Mira 5 filas de cada tabla y compara contra el CSV:\n"
    for t in TABLES:
        out += f"SELECT * FROM {DB_B}.{t['name']} LIMIT 5;\n"
    write(SQL / "01_bronze" / "02_bronze_sanity_checks.sql", out)


def gen_findings():
    out = header("HALLAZGOS: defectos de calidad medidos con SQL sobre BRONCE",
                 ["Crea la tabla Iceberg churn_silver.dq_findings (una fila por tabla x hallazgo).",
                  "tipo = 'rechazo' : regla que rechazaría la fila en plata",
                  "tipo = 'bandera' : inconsistencia que se marca pero NO rechaza",
                  "tipo = 'vacio'   : valores vacíos por columna",
                  "Ejecuta TODO el CREATE TABLE de una vez (es una sola sentencia).",
                  "Si la repites: DROP TABLE churn_silver.dq_findings; y borra s3://BUCKET/audit/dq_findings/"])
    branches = []
    for t in TABLES:
        checks = [(c, "rechazo", cond) for c, cond in hard_checks(t)]
        checks += [(f"flag_{n}", "bandera", cond) for n, cond in t["flags"]]
        checks += [(f"{c}:vacio", "vacio", f"NULLIF(trim({c}), '') IS NULL") for c, _ in t["cols"]]
        counts = ",\n      ".join(f"count_if({cond}) AS c{i}" for i, (_, _, cond) in enumerate(checks, 1))
        names = ",\n      ".join(f"'{c}'" for c, _, _ in checks)
        types = ",\n      ".join(f"'{k}'" for _, k, _ in checks)
        vals = ",\n      ".join(f"m.c{i}" for i in range(1, len(checks) + 1))
        branches.append(
            f"-- {t['name']}\n"
            f"SELECT CAST('{t['name']}' AS varchar) AS tabla, u.hallazgo, u.tipo, u.filas,\n"
            f"       m.total AS total_filas,\n"
            f"       round(CAST(100.0 * u.filas / m.total AS double), 3) AS pct\n"
            f"FROM (\n"
            f"  SELECT count(*) AS total,\n      {counts}\n"
            f"  FROM {ranked_sql(t, 'bronze')} ranked\n"
            f") m\n"
            f"CROSS JOIN UNNEST(\n  ARRAY[\n      {names}\n  ],\n  ARRAY[\n      {types}\n  ],\n"
            f"  ARRAY[\n      {vals}\n  ]\n) AS u(hallazgo, tipo, filas)")
    out += (f"CREATE TABLE {DB_S}.dq_findings\n{tbl_opts('audit/dq_findings')} AS\n"
            + "\nUNION ALL\n".join(branches) + ";\n\n")
    out += ("-- ---- Tabla de hallazgos para el video (solo defectos con filas afectadas) ----\n"
            f"SELECT tabla, hallazgo, tipo, filas, total_filas, pct\nFROM {DB_S}.dq_findings\n"
            "WHERE filas > 0 AND tipo <> 'vacio'\nORDER BY tabla, tipo, filas DESC;\n\n"
            "-- ---- Valores vacíos por columna ----\n"
            f"SELECT tabla, hallazgo AS columna, filas, pct\nFROM {DB_S}.dq_findings\n"
            "WHERE filas > 0 AND tipo = 'vacio'\nORDER BY tabla, filas DESC;\n")
    write(SQL / "02_hallazgos" / "01_dq_findings.sql", out)


def gen_silver():
    for n, t in enumerate(TABLES, 1):
        name = t["name"]
        raw_cols = ",\n  ".join(c for c, _ in t["cols"])
        silver_cols = ",\n  ".join(f"t_{c} AS {c}" for c, _ in t["cols"])
        flag_cols = "".join(f",\n  CASE WHEN ({cond}) THEN true ELSE false END AS flag_{fn}"
                            for fn, cond in t["flags"])
        dep = ("Requiere haber ejecutado ANTES 01_customers.sql (valida llaves foráneas contra silver.customers)."
               if t["fk"] else "Esta tabla es la raíz: las demás validan su customer_id contra ella.")
        out = header(f"PLATA: {name}",
                     [dep,
                      "1) Vista de validación: tipa las columnas y calcula reject_reason (vacío = fila válida).",
                      "2) Tabla Iceberg con filas VÁLIDAS (tipos correctos + columnas flag_*).",
                      "3) Tabla Iceberg con filas RECHAZADAS (valores crudos + motivo).",
                      "Regla de oro: bronce = válidas + rechazadas (se verifica en 05_checks/01_reconciliation.sql)",
                      "Si repites el script: DROP de las 3 tablas/vistas (sql/99_reset) y borra sus carpetas en S3."])
        out += (f"-- 1) Vista de validación -----------------------------------------------------\n"
                f"CREATE OR REPLACE VIEW {DB_S}.v_{name}_validated AS\n"
                f"SELECT ranked.*,\n    {reject_expr(t)} AS reject_reason\n"
                f"FROM {ranked_sql(t, 'silver')} ranked;\n\n")
        out += (f"-- 2) Filas válidas -------------------------------------------------------------\n"
                f"CREATE TABLE {DB_S}.{name}\n{tbl_opts('silver/' + name, t['partition'])} AS\n"
                f"SELECT\n  {silver_cols}{flag_cols},\n  current_date AS silver_load_date\n"
                f"FROM {DB_S}.v_{name}_validated\nWHERE reject_reason = '';\n\n")
        out += (f"-- 3) Filas rechazadas ----------------------------------------------------------\n"
                f"CREATE TABLE {DB_S}.{name}_rejected\n{tbl_opts('silver/' + name + '_rejected')} AS\n"
                f"SELECT\n  {raw_cols},\n  reject_reason,\n  current_date AS rejected_date\n"
                f"FROM {DB_S}.v_{name}_validated\nWHERE reject_reason <> '';\n")
        write(SQL / "03_silver" / f"{n:02d}_{name}.sql", out)


def gen_checks():
    out = header("VERIFICACIÓN: los conteos cuadran (bronce = válidas + rechazadas)", [])
    parts = []
    for t in TABLES:
        nm = t["name"]
        parts.append(f"  SELECT '{nm}' AS tabla,\n"
                     f"    (SELECT count(*) FROM {DB_B}.{nm}) AS bronce,\n"
                     f"    (SELECT count(*) FROM {DB_S}.{nm}) AS plata_validas,\n"
                     f"    (SELECT count(*) FROM {DB_S}.{nm}_rejected) AS plata_rechazadas")
    out += ("SELECT tabla, bronce, plata_validas, plata_rechazadas,\n"
            "       bronce - plata_validas - plata_rechazadas AS diferencia,\n"
            "       CASE WHEN bronce = plata_validas + plata_rechazadas THEN 'OK' ELSE 'REVISAR' END AS cuadra\n"
            "FROM (\n" + "\n  UNION ALL\n".join(parts) + "\n) x\nORDER BY tabla;\n")
    write(SQL / "05_checks" / "01_reconciliation.sql", out)

    out = header("VERIFICACIÓN: motivos de rechazo (una fila por motivo)",
                 ["reject_reason puede traer varios motivos separados por ';' -> se separan con UNNEST.",
                  "Si una tabla no aparece, no tuvo filas rechazadas (es un resultado válido)."])
    parts = [f"SELECT '{t['name']}' AS tabla, u.motivo, count(*) AS filas\n"
             f"FROM {DB_S}.{t['name']}_rejected\n"
             f"CROSS JOIN UNNEST(split(reject_reason, ';')) AS u(motivo)\nGROUP BY u.motivo"
             for t in TABLES]
    out += "\nUNION ALL\n".join(parts) + "\nORDER BY tabla, filas DESC;\n"
    write(SQL / "05_checks" / "02_reject_reasons.sql", out)

    out = header("VERIFICACIÓN: banderas (inconsistencias que NO se rechazaron) en plata",
                 ["Si una bandera afecta a muchísimas filas, probablemente las tablas sintéticas se",
                  "generaron de forma independiente. Decide en el EDA si la promueves a regla de rechazo."])
    parts = []
    for t in TABLES:
        if not t["flags"]:
            continue
        names = ", ".join(f"'flag_{n}'" for n, _ in t["flags"])
        vals = ", ".join(f"count_if(flag_{n})" for n, _ in t["flags"])
        parts.append(f"SELECT '{t['name']}' AS tabla, u.bandera, u.filas, m.total AS total_filas\n"
                     f"FROM (SELECT count(*) AS total, {', '.join(f'count_if(flag_{n}) AS f{i}' for i, (n, _) in enumerate(t['flags'], 1))}\n"
                     f"      FROM {DB_S}.{t['name']}) m\n"
                     f"CROSS JOIN UNNEST(ARRAY[{names}], ARRAY[{', '.join(f'm.f{i}' for i in range(1, len(t['flags']) + 1))}]) AS u(bandera, filas)")
    out += "\nUNION ALL\n".join(parts) + "\nORDER BY tabla, filas DESC;\n"
    write(SQL / "05_checks" / "03_flags_summary.sql", out)


def gen_reset():
    out = header("RESET: borra plata, oro y hallazgos para poder repetir todo",
                 ["OJO: no toca bronce (los CSV siguen en S3).",
                  "Si al recrear una tabla Athena dice que la ubicación no está vacía, borra la",
                  "carpeta correspondiente en S3 (silver/<tabla>/, gold/<tabla>/, audit/dq_findings/)."])
    out += f"-- Oro\n"
    for g in ["customer_360", "orders_monthly_category", "churn_by_dimension"]:
        out += f"DROP TABLE IF EXISTS {DB_G}.{g};\n"
    out += "\n-- Plata (en orden inverso a la creación)\n"
    for t in reversed(TABLES):
        out += (f"DROP VIEW IF EXISTS {DB_S}.v_{t['name']}_validated;\n"
                f"DROP TABLE IF EXISTS {DB_S}.{t['name']}_rejected;\n"
                f"DROP TABLE IF EXISTS {DB_S}.{t['name']};\n")
    out += f"\n-- Hallazgos\nDROP TABLE IF EXISTS {DB_S}.dq_findings;\n"
    write(SQL / "99_reset" / "reset_silver_gold.sql", out)


def gen_rules_doc():
    out = ["# Catálogo de reglas de calidad\n",
           "> Generado por `tools/generate_sql.py`. **Rechazo** = la fila va a `*_rejected` con su motivo. "
           "**Bandera** = la fila pasa a plata pero queda marcada en una columna `flag_*`.\n",
           "> Completa la última columna con los números de `churn_silver.dq_findings`: así cada regla queda "
           "justificada con un hallazgo (criterio de evaluación de la parte A).\n",
           f"> Fecha de corte de datos usada en las reglas de fechas: `{CUT}`.\n"]
    for t in TABLES:
        out.append(f"\n## {t['name']}\n")
        out.append("| Tipo | Código | Condición SQL | Evidencia (filas en bronce) |")
        out.append("|---|---|---|---|")
        for code, cond in hard_checks(t):
            out.append(f"| Rechazo | `{code}` | `{cond}` |  |")
        for n, cond in t["flags"]:
            out.append(f"| Bandera | `flag_{n}` | `{cond}` |  |")
    write(DOCS / "reglas_de_calidad.md", "\n".join(out) + "\n")


if __name__ == "__main__":
    print("Generando SQL...")
    gen_bronze()
    gen_findings()
    gen_silver()
    gen_checks()
    gen_reset()
    gen_rules_doc()
    print("Listo.")
