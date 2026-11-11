"""Carga de datos desde Athena con caché local en parquet, y partición train/test compartida.

Las credenciales de AWS se toman del archivo `.env` de la raíz del repo (ver docs/02_conexion_aws.md),
que está en el .gitignore: NUNCA se suben al repositorio. La caché queda en `data/`, también ignorada.
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
import truststore
from dotenv import load_dotenv
from sklearn.model_selection import train_test_split

# Valida los certificados con el almacén del sistema operativo. Sin esto, boto3 falla en los equipos cuyo
# antivirus inspecciona las conexiones seguras (por ejemplo, Norton), aunque las llaves estén bien.
truststore.inject_into_ssl()

RAIZ = Path(__file__).resolve().parents[2]
DIR_DATOS = RAIZ / "data"
DIR_MODELADO = DIR_DATOS / "modelado"
PREFIJO_MODELADO = "modelado"

load_dotenv(RAIZ / ".env")

BASE_ORO = "churn_gold"
BASE_PLATA = "churn_silver"
REGION = "us-east-1"

SEMILLA = 42
PROPORCION_PRUEBA = 0.3


def leer_athena(sql, base, nombre_cache, refrescar=False):
    """Ejecuta `sql` en Athena y guarda el resultado en `data/<nombre_cache>.parquet`.

    Si la caché ya existe (y `refrescar` es False), la lee sin volver a consultar Athena:
    así no se paga el escaneo en cada ejecución del notebook.
    """
    ruta = DIR_DATOS / f"{nombre_cache}.parquet"
    if ruta.exists() and not refrescar:
        return pd.read_parquet(ruta)

    import awswrangler as wr  # se importa aquí para poder usar la caché sin tener awswrangler

    # ctas_approach=False: sin tablas temporales, así basta el permiso de solo lectura sobre las bases
    df = wr.athena.read_sql_query(sql, database=base, ctas_approach=False,
                                  s3_output=os.environ.get("ATHENA_S3_OUTPUT"), boto3_session=_sesion())
    DIR_DATOS.mkdir(exist_ok=True)
    df.to_parquet(ruta, index=False)
    return df


def cargar_customer_360(refrescar=False):
    """Tabla de oro `customer_360`: una fila por cliente, base del EDA y del modelo."""
    return leer_athena("SELECT * FROM customer_360", BASE_ORO, "customer_360", refrescar)


def cargar_plata(tabla, refrescar=False):
    """Tabla de plata (por ejemplo `orders` o `orders_rejected`), para medir la calidad en su propio grano."""
    return leer_athena(f"SELECT * FROM {tabla}", BASE_PLATA, f"silver_{tabla}", refrescar)


def normalizar_tipos(df, columnas_fecha=(), llave="customer_id"):
    """Unifica los tipos que entrega Athena para trabajar con pandas y scikit-learn.

    - Fechas (llegan como objetos `date`) -> datetime64.
    - Booleanos -> `boolean` (admite nulos).
    - Numéricas (incluidos los enteros con nulos `Int64`) -> float64, salvo la llave.
    - Texto -> object, con los nulos como NaN (los `pd.NA` rompen algunos transformadores).
    """
    df = df.copy()
    for col in df.columns:
        serie = df[col]
        if col in columnas_fecha:
            df[col] = pd.to_datetime(serie)
        elif col == llave:
            continue
        elif pd.api.types.is_bool_dtype(serie):
            df[col] = serie.astype("boolean")
        elif pd.api.types.is_numeric_dtype(serie):
            df[col] = serie.astype("float64")
        else:
            df[col] = serie.astype(object).where(serie.notna(), np.nan)
    return df


def cargar_particion(df, objetivo="churn", llave="customer_id"):
    """Partición train/test estratificada por `objetivo`, la misma para todo el equipo.

    La primera vez la crea y la guarda en `data/particion.parquet` (llave + conjunto). Las siguientes
    la lee, así el EDA y el modelado usan exactamente los mismos clientes en cada conjunto.
    Se ordena por la llave antes de partir porque Athena no garantiza el orden de las filas: sin esto, cada
    integrante obtendría una partición distinta aun con la misma semilla.
    Los clientes sin objetivo (churn nulo) no entran en ningún conjunto.
    """
    ruta = DIR_DATOS / "particion.parquet"
    if ruta.exists():
        return pd.read_parquet(ruta)

    con_objetivo = df.loc[df[objetivo].notna(), [llave, objetivo]].sort_values(llave)
    train, test = train_test_split(
        con_objetivo, test_size=PROPORCION_PRUEBA, stratify=con_objetivo[objetivo], random_state=SEMILLA
    )
    particion = pd.concat([
        train[[llave]].assign(conjunto="train"),
        test[[llave]].assign(conjunto="test"),
    ], ignore_index=True)
    DIR_DATOS.mkdir(exist_ok=True)
    particion.to_parquet(ruta, index=False)
    return particion


def descargar_modelado(refrescar=False, subcarpeta=""):
    """Descarga de S3 a `data/modelado` los resultados con los que se decidió el modelo y el modelo final.

    Los archivos que ya existen no se tocan, salvo que `refrescar` sea True. Con `subcarpeta` (por ejemplo
    "modelo_final") solo se descarga esa carpeta.
    Devuelve cuántos archivos se descargaron y cuántos ya existían.
    """
    s3, bucket = _sesion().client("s3"), _bucket()
    descargados = existentes = 0
    prefijo = f"{PREFIJO_MODELADO}/{subcarpeta.strip('/') + '/' if subcarpeta else ''}"
    for pagina in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefijo):
        for objeto in pagina.get("Contents", []):
            if objeto["Key"].endswith("/"):
                continue
            ruta = DIR_MODELADO / objeto["Key"].removeprefix(f"{PREFIJO_MODELADO}/")
            if ruta.exists() and not refrescar:
                existentes += 1
                continue
            ruta.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, objeto["Key"], str(ruta))
            descargados += 1
    return descargados, existentes


def subir_modelado():
    """Sube a S3 todo `data/modelado`, incluido el modelo final, reemplazando lo que haya. Devuelve cuántos archivos subió."""
    s3, bucket = _sesion().client("s3"), _bucket()
    archivos = [ruta for ruta in DIR_MODELADO.rglob("*") if ruta.is_file()]
    for ruta in archivos:
        s3.upload_file(str(ruta), bucket, f"{PREFIJO_MODELADO}/{ruta.relative_to(DIR_MODELADO).as_posix()}")
    return len(archivos)


def _bucket():
    """Bucket del proyecto, tomado de ATHENA_S3_OUTPUT (s3://bucket/carpeta/) para no escribirlo en el repo."""
    salida = os.environ.get("ATHENA_S3_OUTPUT", "")
    if not salida.startswith("s3://"):
        raise ValueError("Falta ATHENA_S3_OUTPUT en .env, con la forma s3://bucket/carpeta/")
    return salida.removeprefix("s3://").split("/")[0]


def _sesion():
    import boto3

    return boto3.Session(region_name=os.environ.get("AWS_DEFAULT_REGION", REGION))
