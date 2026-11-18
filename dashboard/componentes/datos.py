"""Consultas a Athena (capa oro) para la exploración del valor en riesgo y la ficha de cliente.

Cada vista lanza consultas SQL agregadas: Athena hace el trabajo sobre los 500.000 clientes y al tablero solo
llegan unas pocas filas. Cada resultado guarda su SQL, el tiempo y los MB escaneados, que se muestran bajo los
gráficos. Los resultados quedan en caché 6 horas: repetir una consulta (mismos filtros) no vuelve a Athena.

Definiciones:
- CLV = `lifetime_value` de customer_summary (valor de vida del cliente, en ₹).
- Pérdida esperada = probabilidad de churn × CLV: lo que se espera perder si no se hace nada.
- Los deciles de riesgo y de valor se calculan sobre los 500.000 clientes ANTES de filtrar, para que una celda
  signifique lo mismo con o sin filtros. Decil 1 = mayor riesgo / mayor valor.
- Lo que compara contra lo que realmente pasó (churners encontrados) usa solo `test`: el modelo no vio esos clientes.
"""
import os
import time
from dataclasses import dataclass

import pandas as pd
import streamlit as st

from componentes import config

config.preparar_entorno()

ORO = "churn_gold"

# Filtros disponibles: columna de la tabla base → opciones (fijas, para no consultar Athena solo para listarlas)
OPCIONES_FILTRO = {
    "membership_tier": ["Basic", "Silver", "Gold", "Platinum"],
    "city": ["Ahmedabad", "Bengaluru", "Chennai", "Delhi", "Faridabad", "Hyderabad", "Kolkata", "Mumbai"],
    "preferred_device": ["Android", "iPhone", "Web"],
    "referral_source": ["Organic", "Friend", "Ads", "Social Media"],
    "campana": ["Reactivación", "Atención posventa", "Sin campaña asignada"],
}

BASE = """
WITH base AS (
  SELECT p.customer_id, p.conjunto, p.probabilidad, p.churn_predicho, p.motivo_principal,
         coalesce(split_part(p.campana_sugerida, ':', 1), 'Sin campaña asignada') AS campana,
         c.lifetime_value AS clv,
         p.probabilidad * c.lifetime_value AS perdida,
         CAST(c.churn AS integer) AS churn,
         c.membership_tier, c.city, c.preferred_device, c.referral_source,
         CAST(c.summary_total_orders AS integer) AS pedidos, CAST(c.total_returns AS integer) AS devoluciones,
         ntile(10) OVER (ORDER BY p.probabilidad DESC) AS decil_riesgo,
         ntile(10) OVER (ORDER BY c.lifetime_value DESC) AS decil_valor
  FROM churn_predicciones p
  JOIN customer_360 c ON c.customer_id = p.customer_id
)"""


@dataclass
class Consulta:
    df: pd.DataFrame
    sql: str
    segundos: float
    mb_escaneados: float


class ErrorAthena(Exception):
    """Falla al consultar Athena, con un mensaje listo para mostrar."""


@st.cache_data(ttl=6 * 3600, show_spinner="Consultando Athena…", max_entries=300)
def consultar(sql, base=ORO):
    """Ejecuta `sql` en Athena y devuelve una Consulta (resultado + SQL + tiempo + MB escaneados)."""
    import awswrangler as wr  # después de config.preparar_entorno() (truststore)
    import boto3

    sesion = boto3.Session(region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    inicio = time.time()
    try:
        df = wr.athena.read_sql_query(sql, database=base, ctas_approach=False,
                                      s3_output=os.environ.get("ATHENA_S3_OUTPUT"), boto3_session=sesion)
    except Exception as error:  # noqa: BLE001 - se muestra al usuario tal cual
        raise ErrorAthena(f"Athena no pudo ejecutar la consulta: {error}") from None
    metadatos = getattr(df, "query_metadata", None) or {}
    escaneado = metadatos.get("Statistics", {}).get("DataScannedInBytes", 0) / 1e6
    return Consulta(df=df, sql=sql.strip(), segundos=time.time() - inicio, mb_escaneados=escaneado)


def mostrar_sql(*consultas):
    """Expander con el SQL de las consultas que alimentan una sección, con su tiempo y MB escaneados."""
    total_mb = sum(c.mb_escaneados for c in consultas)
    with st.expander(f"Consulta a Athena · {total_mb:.1f} MB escaneados".replace(".", ","),
                     icon=":material/database:"):
        for c in consultas:
            st.caption(f"{c.segundos:.1f} s · {c.mb_escaneados:.2f} MB escaneados · {len(c.df)} filas devueltas"
                       .replace(".", ","))
            st.code(c.sql, language="sql")


def _where(filtros, extra=()):
    """WHERE a partir de {columna: [valores]} (solo columnas y valores de OPCIONES_FILTRO) y condiciones extra."""
    condiciones = list(extra)
    for columna, valores in sorted(filtros.items()):
        validos = [v for v in valores if v in OPCIONES_FILTRO.get(columna, [])]
        if validos:
            condiciones.append(f"{columna} IN (" + ", ".join(f"'{v}'" for v in validos) + ")")
    return ("WHERE " + "\n  AND ".join(condiciones)) if condiciones else ""


def _filtros(filtros):
    """Los filtros como tupla ordenada (hashable) para la caché."""
    return tuple(sorted((k, tuple(v)) for k, v in filtros.items() if v))


# ---------------------------------------------------------------------------------------------------------------
# Consultas de la vista "Valor en riesgo"
# ---------------------------------------------------------------------------------------------------------------

def resumen(filtros):
    return consultar(f"""{BASE}
SELECT count(*)                                         AS clientes,
       sum(clv)                                         AS clv_total,
       sum(perdida)                                     AS perdida_esperada,
       sum(probabilidad)                                AS churners_esperados,
       sum(churn_predicho)                              AS marcados,
       sum(CASE WHEN churn_predicho = 1 THEN clv END)   AS clv_marcados
FROM base
{_where(dict(filtros))}""")


def matriz(filtros):
    """Pérdida esperada por celda decil de riesgo × decil de valor."""
    return consultar(f"""{BASE}
SELECT decil_riesgo, decil_valor, count(*) AS clientes, sum(perdida) AS perdida,
       avg(probabilidad) AS probabilidad_media, avg(clv) AS clv_medio
FROM base
{_where(dict(filtros))}
GROUP BY decil_riesgo, decil_valor""")


DIMENSIONES = {
    "membership_tier": "Membresía",
    "city": "Ciudad",
    "preferred_device": "Dispositivo",
    "referral_source": "Canal de llegada",
    "campana": "Campaña sugerida",
}


def por_dimension(filtros, dimension):
    if dimension not in DIMENSIONES:
        raise ValueError(dimension)
    return consultar(f"""{BASE}
SELECT {dimension} AS valor, count(*) AS clientes, sum(perdida) AS perdida,
       avg(probabilidad) AS probabilidad_media, avg(clv) AS clv_medio
FROM base
{_where(dict(filtros))}
GROUP BY {dimension}
ORDER BY perdida DESC""")


def dilema(filtros):
    """En test: % de churners reales y % del CLV de esos churners que se encuentran al contactar el x % de clientes,
    ordenando por probabilidad o por pérdida esperada (100 puntos por estrategia)."""
    return consultar(f"""{BASE},
test AS (SELECT * FROM base {_where(dict(filtros), ["conjunto = 'test'"])}),
ordenado AS (
  SELECT 'probabilidad' AS estrategia, churn, clv,
         row_number() OVER (ORDER BY probabilidad DESC) AS posicion FROM test
  UNION ALL
  SELECT 'perdida' AS estrategia, churn, clv,
         row_number() OVER (ORDER BY perdida DESC) AS posicion FROM test
),
acumulado AS (
  SELECT estrategia, posicion,
         count(*) OVER (PARTITION BY estrategia) AS total,
         sum(churn) OVER (PARTITION BY estrategia ORDER BY posicion ROWS UNBOUNDED PRECEDING) AS churners,
         sum(churn * clv) OVER (PARTITION BY estrategia ORDER BY posicion ROWS UNBOUNDED PRECEDING) AS valor,
         sum(churn) OVER (PARTITION BY estrategia) AS total_churners,
         sum(churn * clv) OVER (PARTITION BY estrategia) AS total_valor
  FROM ordenado
)
SELECT estrategia,
       CAST(posicion AS double) / total                AS pct_contactado,
       CAST(churners AS double) / total_churners       AS pct_churners,
       valor / total_valor                             AS pct_valor
FROM acumulado
WHERE posicion % greatest(total / 100, 1) = 0 OR posicion = total
ORDER BY estrategia, pct_contactado""")


def clientes_celda(filtros, decil_riesgo, decil_valor, orden, limite=200):
    extra = []
    if decil_riesgo:
        extra.append(f"decil_riesgo = {int(decil_riesgo)}")
    if decil_valor:
        extra.append(f"decil_valor = {int(decil_valor)}")
    columna_orden = "perdida" if orden == "perdida" else "probabilidad"
    return consultar(f"""{BASE}
SELECT customer_id, round(probabilidad, 3) AS probabilidad, round(clv) AS clv, round(perdida) AS perdida,
       motivo_principal, campana, membership_tier, city, pedidos, devoluciones, conjunto
FROM base
{_where(dict(filtros), extra)}
ORDER BY {columna_orden} DESC
LIMIT {int(limite)}""")


# ---------------------------------------------------------------------------------------------------------------
# Ficha de cliente
# ---------------------------------------------------------------------------------------------------------------

def cliente(customer_id):
    """Perfil, variables del modelo, CLV, etiqueta real y conjunto de un cliente."""
    return consultar(f"""
SELECT c.customer_id, c.age, c.gender, c.city, c.membership_tier, c.preferred_device, c.referral_source,
       c.tenure_months, c.summary_total_orders, c.total_spent, c.average_order_value, c.total_returns,
       c.lifetime_value, c.churn, p.conjunto
FROM customer_360 c
JOIN churn_predicciones p ON p.customer_id = c.customer_id
WHERE c.customer_id = {int(customer_id)}""")
