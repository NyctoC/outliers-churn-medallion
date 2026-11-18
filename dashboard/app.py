"""Tablero de churn · The Outliers (Proyecto Integrador 1, EAFIT).

Ejecutar desde la raíz del repo, con el entorno activo:
    streamlit run dashboard/app.py

Complementa la presentación: en lugar de repetir el modelo, permite explorar dónde está el valor en riesgo y bajar
hasta un cliente para entender su riesgo y simular cambios con la API del modelo.
- "Valor en riesgo": consultas SQL a Athena sobre la capa oro (churn_predicciones + customer_360).
- "Ficha y simulador" y "Efecto de las variables": la API FastAPI del modelo desplegada en EC2.
La configuración va en .env (local) o en los Secrets de Streamlit Cloud: ver componentes/config.py.
"""
import streamlit as st

st.set_page_config(page_title="Modelo de predicción de churn · Dashboard interactivo", page_icon="📉", layout="wide")

from componentes import api, config, textos  # noqa: E402  (después de set_page_config)

config.preparar_entorno()

faltan = config.faltantes()
if faltan:
    st.error(f"Falta configuración: {', '.join(faltan)}. En local va en el archivo .env de la raíz del repo; "
             f"en Streamlit Cloud, en Settings → Secrets.")
    st.stop()

navegacion = st.navigation([
    st.Page("paginas/valor.py", title="Valor en riesgo", icon=":material/payments:", default=True),
    st.Page("paginas/simulador.py", title="Ficha y simulador", icon=":material/person_search:"),
    st.Page("paginas/efectos.py", title="Efecto de las variables", icon=":material/tune:"),
])

with st.sidebar:
    st.caption("**The Outliers** · Proyecto Integrador 1 · EAFIT")
    st.caption(textos.IDEA_CENTRAL)
    try:
        estado = api.salud()
        st.success(f"API del modelo en línea · {estado['modelo']} · ROC-AUC test "
                   f"{estado['metricas']['test']['roc_auc']:.3f}".replace(".", ","), icon=":material/cloud_done:")
    except api.ErrorAPI as error:
        st.error(f"API del modelo sin conexión. {error}", icon=":material/cloud_off:")
    st.caption("**Valor en riesgo** consulta la capa oro con Amazon Athena. **Ficha** y **Efecto** llaman en vivo "
               "a la API del modelo en Amazon EC2.")

# Título del tablero, común a todas las vistas (cada vista tiene debajo su propio subtítulo)
st.caption("PROYECTO INTEGRADOR 1 · THE OUTLIERS · EAFIT")
st.title("Modelo de predicción de churn — Dashboard interactivo")
st.divider()

navegacion.run()
