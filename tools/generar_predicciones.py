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

from churn import data, features, modelos

BASE, TABLA = "churn_gold", "churn_predicciones"

# Tipos de Athena para cada columna de la tabla (para el CREATE TABLE)
TIPOS_ATHENA = {
    "customer_id": "bigint", "conjunto": "string", "probabilidad": "double", "churn_predicho": "int",
    "prioridad": "int", "motivo_principal": "string", "campana_sugerida": "string",
    "contribucion_pedidos": "double", "contribucion_gasto": "double", "contribucion_valor_promedio": "double",
    "contribucion_devoluciones": "double", "contribucion_pedidos_devoluciones": "double",
    "modelo": "string", "umbral": "double", "fecha_prediccion": "date",
}

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
    """Sube la tabla a S3 en un único Parquet y crea la tabla externa en Athena.

    Se evita wr.athena.to_iceberg porque entra en conflicto con truststore (RecursionError al crear el
    cliente SSL). En cambio se usa el cliente S3 de boto3 (igual que descargar_modelado) y Athena para el DDL
    (igual que leer_athena), que sí conviven con truststore.
    """
    bucket = data._bucket()
    prefijo = f"gold/{TABLA}"
    ubicacion = f"s3://{bucket}/{prefijo}/"
    s3 = data._sesion().client("s3")

    # Borra lo que haya en la carpeta para que la tabla no mezcle una corrida anterior
    pagina = s3.list_objects_v2(Bucket=bucket, Prefix=f"{prefijo}/")
    objetos = [{"Key": o["Key"]} for o in pagina.get("Contents", [])]
    if objetos:
        s3.delete_objects(Bucket=bucket, Delete={"Objects": objetos})

    # Sube el Parquet (el DataFrame ya está en memoria, se escribe a un archivo local y se sube)
    ruta_local = data.DIR_DATOS / f"{TABLA}.parquet"
    data.DIR_DATOS.mkdir(exist_ok=True)
    tabla.to_parquet(ruta_local, index=False)
    s3.upload_file(str(ruta_local), bucket, f"{prefijo}/{TABLA}.parquet")

    # Crea la base (por si no existe) y la tabla externa, apuntando a la carpeta de Parquet
    columnas = ",\n  ".join(f"{col} {TIPOS_ATHENA[col]}" for col in tabla.columns)
    ejecutar_athena(f"CREATE DATABASE IF NOT EXISTS {BASE}")
    ejecutar_athena(f"DROP TABLE IF EXISTS {BASE}.{TABLA}")
    ejecutar_athena(
        f"CREATE EXTERNAL TABLE {BASE}.{TABLA} (\n  {columnas}\n)\n"
        f"STORED AS PARQUET\nLOCATION '{ubicacion}'\n"
        f"TBLPROPERTIES ('parquet.compression' = 'SNAPPY')")
    print(f"tabla {BASE}.{TABLA} creada sobre {ubicacion}")


def ejecutar_athena(sql):
    """Ejecuta una sentencia DDL en Athena (CREATE/DROP) y espera a que termine.

    Usa awswrangler igual que data.leer_athena, que convive con truststore. read_sql_query no sirve para DDL
    porque espera un resultado tabular.
    """
    import awswrangler as wr

    id_consulta = wr.athena.start_query_execution(
        sql=sql, database=BASE, s3_output=f"s3://{data._bucket()}/athena-results/",
        boto3_session=data._sesion())
    wr.athena.wait_query(query_execution_id=id_consulta, boto3_session=data._sesion())


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
