"""Genera la tabla churn_gold.churn_predicciones (una fila por cliente) con el modelo final de 02_modelado.

Puntúa a los 500.000 clientes de customer_360, agrega prioridad, motivo, campaña y las contribuciones del EBM, y
escribe la tabla en la capa oro (Iceberg) para el tablero. Guarda además una copia en Parquet para la API.

Uso (con el entorno activo, desde la raiz del repo):
    python tools/generar_predicciones.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import awswrangler as wr

from churn import data, features, modelos

BASE, TABLA = "churn_gold", "churn_predicciones"

# Athena no admite espacios ni "&" en los nombres de columna, así que se renombran las contribuciones del EBM
CONTRIBUCIONES = {
    "contribucion_summary_total_orders": "contribucion_pedidos",
    "contribucion_total_spent": "contribucion_gasto",
    "contribucion_average_order_value": "contribucion_valor_promedio",
    "contribucion_total_returns": "contribucion_devoluciones",
    "contribucion_summary_total_orders & total_returns": "contribucion_pedidos_devoluciones",
}


def construir_tabla():
    modelo, configuracion = modelos.cargar_modelo_final()
    clientes = modelos.cargar_clientes()
    tabla = modelos.explicar_clientes(modelo, clientes)
    tabla = tabla.merge(data.cargar_particion(clientes), on=features.LLAVE, how="left")
    tabla = tabla.merge(modelos.priorizar(tabla)[[features.LLAVE, "prioridad"]], on=features.LLAVE)

    sin_renombrar = set(CONTRIBUCIONES) - set(tabla.columns)
    if sin_renombrar:
        raise RuntimeError(f"El modelo no trae estos terminos: {sin_renombrar}. Columnas: {list(tabla.columns)}")
    tabla = tabla.rename(columns=CONTRIBUCIONES)
    tabla[["motivo_principal", "campana_sugerida"]] = tabla[["motivo_principal", "campana_sugerida"]].astype("string")
    tabla["modelo"] = configuracion["modelo"]
    tabla["umbral"] = modelos.UMBRAL
    tabla["fecha_prediccion"] = date.today()

    columnas = [features.LLAVE, "conjunto", "probabilidad", "churn_predicho", "prioridad", "motivo_principal",
                "campana_sugerida", *CONTRIBUCIONES.values(), "modelo", "umbral", "fecha_prediccion"]
    return tabla[columnas]


def verificar(tabla):
    assert len(tabla) == 500_000, f"se esperaban 500.000 filas y hay {len(tabla):,}"
    assert tabla[features.LLAVE].is_unique, "hay customer_id repetidos"
    print(f"filas: {len(tabla):,}; churn_predicho = 1: {int(tabla['churn_predicho'].sum()):,}")


def escribir_oro(tabla):
    bucket = data._bucket()
    wr.athena.to_iceberg(
        df=tabla, database=BASE, table=TABLA,
        table_location=f"s3://{bucket}/gold/{TABLA}/",
        temp_path=f"s3://{bucket}/athena-results/temp_iceberg/",
        s3_output=f"s3://{bucket}/athena-results/",
        mode="overwrite", keep_files=False, boto3_session=data._sesion(),
    )
    print(f"tabla {BASE}.{TABLA} escrita en s3://{bucket}/gold/{TABLA}/")


def guardar_copia_para_api(tabla):
    """Copia en Parquet para que la API responda /clientes/{customer_id} sin consultar Athena."""
    bucket = data._bucket()
    ruta = data.DIR_DATOS / "churn_predicciones.parquet"
    data.DIR_DATOS.mkdir(exist_ok=True)
    tabla.to_parquet(ruta, index=False)
    data._sesion().client("s3").upload_file(
        str(ruta), bucket, "gold/churn_predicciones_api/churn_predicciones.parquet")
    print(f"copia para la API en {ruta} y en s3://{bucket}/gold/churn_predicciones_api/")


if __name__ == "__main__":
    tabla = construir_tabla()
    verificar(tabla)
    escribir_oro(tabla)
    guardar_copia_para_api(tabla)
