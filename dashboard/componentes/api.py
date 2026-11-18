"""Cliente de la API del modelo (FastAPI en EC2). El tablero no carga el modelo: todo pasa por aquí.

No hay respaldo a propósito: si la API falla, se lanza ErrorAPI con un mensaje que dice qué revisar, y la vista
lo muestra tal cual. Así se sabe que el problema está en la API y no en el tablero.
"""
import requests
import streamlit as st

from componentes import config

config.preparar_entorno()

TIMEOUT = 20  # segundos; /contrafactuales tarda ~0,3 s, el margen cubre una instancia recién encendida


class ErrorAPI(Exception):
    """Falla al llamar a la API, con un mensaje listo para mostrar."""


def _llamar(metodo, ruta, cuerpo=None):
    url = config.api_url()
    if not url:
        raise ErrorAPI("Falta API_URL en la configuración (.env en local o Secrets en Streamlit Cloud).")
    try:
        respuesta = requests.request(metodo, f"{url}{ruta}", json=cuerpo, timeout=TIMEOUT)
    except requests.exceptions.ConnectTimeout:
        raise ErrorAPI(f"La API en {url} no respondió a tiempo. Revisa que la instancia EC2 esté encendida "
                       f"(Running) y que el Security Group permita el puerto 8000.") from None
    except requests.exceptions.ConnectionError:
        raise ErrorAPI(f"No se pudo conectar con la API en {url}. Revisa que la instancia EC2 esté encendida, "
                       f"que la IP sea la correcta y que el contenedor churn-api esté corriendo.") from None
    except requests.exceptions.Timeout:
        raise ErrorAPI(f"La API en {url} tardó más de {TIMEOUT} s en responder {ruta}.") from None
    if respuesta.status_code == 422:
        raise ErrorAPI(f"La API rechazó los datos enviados a {ruta}: {_detalle(respuesta)}")
    if not respuesta.ok:
        raise ErrorAPI(f"La API respondió {respuesta.status_code} en {ruta}: {_detalle(respuesta)}")
    return respuesta.json()


def _detalle(respuesta):
    try:
        detalle = respuesta.json().get("detail", respuesta.text)
    except ValueError:
        return respuesta.text[:300]
    if isinstance(detalle, list):  # errores de validación de FastAPI
        return "; ".join(str(d.get("msg", d)) for d in detalle)
    return str(detalle)


def _cliente(pedidos, gasto, valor_promedio, devoluciones, customer_id=None):
    return {"customer_id": customer_id, "summary_total_orders": float(pedidos), "total_spent": float(gasto),
            "average_order_value": float(valor_promedio), "total_returns": float(devoluciones)}


@st.cache_data(ttl=30, show_spinner=False)
def salud():
    """Estado de la API (GET /salud). Se refresca cada 30 s."""
    return _llamar("GET", "/salud")


@st.cache_data(ttl=3600, show_spinner=False)
def modelo():
    """Ficha técnica del modelo que responde (GET /modelo): variables, retiradas por fuga, hiperparámetros, métricas."""
    return _llamar("GET", "/modelo")


@st.cache_data(ttl=3600, max_entries=500, show_spinner=False)
def buscar_cliente(customer_id):
    """Predicción ya calculada por lotes de un cliente existente (GET /clientes/{id}). None si no existe."""
    try:
        return _llamar("GET", f"/clientes/{int(customer_id)}")
    except ErrorAPI as error:
        if "404" in str(error):
            return None
        raise


@st.cache_data(max_entries=2000, show_spinner=False)
def explicar(pedidos, gasto, valor_promedio, devoluciones, customer_id=None):
    """Probabilidad, contribución de cada término, motivo y campaña (POST /explicar)."""
    return _llamar("POST", "/explicar", _cliente(pedidos, gasto, valor_promedio, devoluciones, customer_id))


@st.cache_data(max_entries=500, show_spinner=False)
def contrafactuales(pedidos, gasto, valor_promedio, devoluciones, customer_id=None):
    """Cambio mínimo para quedar bajo el umbral, con una y con dos variables (POST /contrafactuales)."""
    return _llamar("POST", "/contrafactuales", _cliente(pedidos, gasto, valor_promedio, devoluciones, customer_id))


@st.cache_data(max_entries=200, show_spinner=False)
def predecir(filas):
    """Probabilidad de varios clientes (POST /predecir, máx. 1.000).

    `filas`: tupla de (pedidos, gasto, valor, devoluciones) o (pedidos, gasto, valor, devoluciones, customer_id).
    """
    return _llamar("POST", "/predecir", [_cliente(*f) for f in filas])
