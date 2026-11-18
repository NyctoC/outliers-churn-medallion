"""Configuración del tablero: variables de entorno, secretos de Streamlit Cloud y certificados.

En local se leen de `.env` (raíz del repo, ignorado por git). En Streamlit Cloud se leen de los Secrets de la app
(Settings → Secrets) con el mismo formato:

    AWS_ACCESS_KEY_ID = "..."          # usuario de SOLO LECTURA (outliers-equipo)
    AWS_SECRET_ACCESS_KEY = "..."
    AWS_DEFAULT_REGION = "us-east-1"
    ATHENA_S3_OUTPUT = "s3://<bucket>/athena-results/"
    API_URL = "http://<elastic-ip>:8000"

Este módulo debe importarse antes que boto3 o awswrangler (ver `preparar_entorno`).
"""
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]
DIR_CACHE = RAIZ / "data"
VARIABLES = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION", "ATHENA_S3_OUTPUT", "API_URL"]

_listo = False


def preparar_entorno():
    """Carga `.env` y los Secrets de Streamlit en `os.environ`, y activa truststore. Se ejecuta una sola vez.

    truststore valida los certificados con el almacén del sistema operativo: sin esto, boto3 falla en los equipos
    cuyo antivirus inspecciona las conexiones seguras. Debe activarse ANTES de importar awswrangler; en el otro
    orden, crear un cliente de AWS da RecursionError (ver tools/generar_predicciones.py).
    """
    global _listo
    if _listo:
        return
    load_dotenv(RAIZ / ".env")
    try:
        for clave in VARIABLES:
            if clave in st.secrets and not os.environ.get(clave):
                os.environ[clave] = str(st.secrets[clave])
    except FileNotFoundError:
        pass  # en local no hay secrets.toml: basta con .env
    except Exception:  # noqa: BLE001 - versiones de Streamlit que lanzan otra excepción sin secrets
        pass
    try:
        import truststore

        truststore.inject_into_ssl()
    except ImportError:
        pass
    _listo = True


def faltantes():
    """Variables de configuración que no están definidas."""
    return [v for v in VARIABLES if not os.environ.get(v)]


def api_url():
    return os.environ.get("API_URL", "").rstrip("/")
