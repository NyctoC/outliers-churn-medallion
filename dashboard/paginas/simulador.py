"""Ficha y simulador de un cliente: el modelo en vivo a través de la API, con su valor en riesgo.

Endpoints que usa:
- GET  /clientes/{id}    predicción guardada por lotes (para comparar con la respuesta en vivo)
- POST /explicar         probabilidad + contribución de cada término + motivo + campaña (cada vez que cambia un valor)
- POST /contrafactuales  el cambio mínimo que deja al cliente bajo el umbral
- GET  /modelo           ficha técnica del modelo que responde
Los datos del cliente (perfil, sus 4 variables y su CLV) se leen de customer_360 con Athena.
Pérdida esperada = probabilidad × CLV. En el what-if el CLV se estima proporcional al gasto (CLV ≈ 1,8 × gasto en los
datos), porque el dataset no documenta cómo se calculó y la API no lo devuelve.
"""
import json
import math

import streamlit as st

from componentes import api, datos, graficos as g, textos

UMBRAL = 0.5
CLV_POR_GASTO = 1.80  # pendiente de CLV sobre gasto total en customer_360 (regresión en Athena, R² = 0,89)

st.header("Ficha y simulador de un cliente")
st.caption("Por qué un cliente está en riesgo, cuánto valor se perdería, qué campaña le toca y qué cambio lo sacaría "
           "del riesgo, calculado en vivo por la API del modelo.")

# ---------------------------------------------------------------------------------------------------------------
# 1. Elegir el cliente
# ---------------------------------------------------------------------------------------------------------------
if "sim_cliente" not in st.session_state:
    st.session_state["sim_cliente"] = 1340006

origen = st.segmented_control("¿Qué cliente?", ["Cliente existente", "Cliente nuevo (valores libres)"],
                              default="Cliente existente", key="sim_origen") or "Cliente existente"

perfil = lote = None
if origen == "Cliente existente":
    st.caption("Casos de ejemplo (clientes de test, que el modelo no vio al entrenar):")
    botones = st.columns(len(textos.CASOS))
    for columna, (cid, descripcion) in zip(botones, textos.CASOS.items()):
        if columna.button(descripcion, key=f"caso_{cid}", width="stretch",
                          type="primary" if st.session_state["sim_cliente"] == cid else "secondary"):
            st.session_state["sim_cliente"] = cid
            st.rerun()
    st.number_input("…o escribe un customer_id (de 1.000.001 a 1.500.000)", 1_000_001, 1_500_000, step=1,
                    key="sim_cliente")
    cid = int(st.session_state["sim_cliente"])
    try:
        consulta = datos.cliente(cid)
        lote = api.buscar_cliente(cid)
    except datos.ErrorAthena as error:
        st.error(str(error))
        st.stop()
    except api.ErrorAPI as error:
        st.error(str(error), icon=":material/cloud_off:")
        st.stop()
    if consulta.df.empty:
        st.warning(f"No existe el cliente {cid} en customer_360.")
        st.stop()
    perfil = consulta.df.iloc[0]
    base = {"pedidos": int(perfil["summary_total_orders"]), "valor": float(perfil["average_order_value"]),
            "devoluciones": int(perfil["total_returns"]), "gasto": float(perfil["total_spent"])}
    st.markdown(
        f"**Cliente {cid}** · {perfil['membership_tier']} · {perfil['city']} · {perfil['preferred_device']} · "
        f"{int(perfil['age'])} años · {int(perfil['tenure_months'])} meses de antigüedad · "
        f"conjunto **{perfil['conjunto']}**")
else:
    cid = None
    base = {"pedidos": 10, "valor": 6000.0, "devoluciones": 3, "gasto": 60000.0}
clv = float(perfil["lifetime_value"]) if perfil is not None else None

# ---------------------------------------------------------------------------------------------------------------
# 2. What-if: los valores que se mandan a la API
# ---------------------------------------------------------------------------------------------------------------
sufijo = f"{origen}_{cid}"  # al cambiar de cliente, los controles vuelven a sus valores reales
claves = {k: f"sim_{k}_{sufijo}" for k in ["pedidos", "valor", "devoluciones"]}
for k, clave in claves.items():
    st.session_state.setdefault(clave, base[k])


def restaurar():
    for k, clave in claves.items():
        st.session_state[clave] = base[k]


def aplicar(variable, valor):
    nombre = {"summary_total_orders": "pedidos", "average_order_value": "valor", "total_returns": "devoluciones"}
    st.session_state[claves[nombre[variable]]] = int(valor) if nombre[variable] != "valor" else float(valor)


with st.container(border=True):
    st.markdown("**¿Y si cambiara…?** Mueve los valores: cada cambio es una llamada nueva a `POST /explicar`.")
    s1, s2, s3, s4 = st.columns([3, 3, 3, 2], vertical_alignment="bottom")
    # Rangos fijos: si los límites de un slider cambian, Streamlit lo reinicia y se pierde el valor elegido
    pedidos = s1.slider("Pedidos", 1, 120, key=claves["pedidos"])
    devoluciones_elegidas = s2.slider("Devoluciones", 0, 10, key=claves["devoluciones"])
    valor = s3.number_input("Valor promedio por pedido (₹)", 500.0, 12_000.0, step=250.0, key=claves["valor"])
    s4.button("Volver a los valores reales" if cid else "Restablecer", on_click=restaurar, width="stretch")
    devoluciones = min(devoluciones_elegidas, pedidos)
    sin_cambios = (pedidos, devoluciones, valor) == (base["pedidos"], base["devoluciones"], base["valor"])
    gasto = base["gasto"] if sin_cambios else pedidos * valor
    nota = (f" Las devoluciones se limitan a {pedidos}: no puede haber más devoluciones que pedidos (la API lo "
            f"rechaza)." if devoluciones < devoluciones_elegidas else "")
    st.caption(f"Gasto total = pedidos × valor promedio = ₹{g.formato_numero(gasto)} (se recalcula solo, como en "
               f"el modelado).{nota}")

try:
    exp = api.explicar(pedidos, gasto, valor, devoluciones, cid)
    cf = api.contrafactuales(pedidos, gasto, valor, devoluciones, cid)
except api.ErrorAPI as error:
    st.error(str(error), icon=":material/cloud_off:")
    st.stop()

prob = exp["probabilidad"]
contrib = {textos.TERMINOS.get(t, t): v for t, v in exp["contribuciones"].items()}
motivo = exp.get("motivo_principal")
campana = (exp.get("campana_sugerida") or "Sin campaña asignada").split(":")[0]

# ---------------------------------------------------------------------------------------------------------------
# 3. Resultado
# ---------------------------------------------------------------------------------------------------------------
if prob >= UMBRAL and motivo:
    titular = (f"Probabilidad de churn {g.formato_pct(prob, 0)}: en riesgo, sobre todo porque "
               f"{textos.MOTIVO_EN_FRASE.get(motivo, motivo)} → campaña de {campana.lower()}")
elif prob >= UMBRAL:
    titular = f"Probabilidad de churn {g.formato_pct(prob, 0)}: en riesgo"
else:
    titular = f"Probabilidad de churn {g.formato_pct(prob, 0)}: bajo el umbral de 0,5, no requiere campaña"
st.subheader(titular)

izq, der = st.columns([2, 3], gap="large")
with izq:
    g.mostrar(g.medidor(prob, UMBRAL, alto=150))
    # CLV: el real del cliente con sus valores reales. Si se cambian pedidos o valor promedio, se estima
    # manteniendo la relación CLV ÷ gasto del cliente (en los datos CLV ≈ 1,8 × gasto, R² = 0,89). Para un cliente
    # nuevo se usa esa relación promedio. Es una aproximación: el dataset no documenta cómo se calculó el CLV.
    if clv is not None:
        clv_usado = clv if sin_cambios else clv * gasto / base["gasto"]
    else:
        clv_usado = CLV_POR_GASTO * gasto
    v1, v2 = st.columns(2)
    if clv is not None and sin_cambios:
        v1.metric("CLV del cliente", f"₹{g.formato_numero(clv_usado)}",
                  help="Valor de vida del cliente (lifetime_value de customer_summary).")
    else:
        relacion = clv / base["gasto"] if clv is not None else CLV_POR_GASTO
        v1.metric("CLV estimado", f"₹{g.formato_numero(clv_usado)}",
                  None if clv is None else f"{'-' if clv_usado < clv else '+'}₹{g.formato_numero(abs(clv_usado - clv))}",
                  help=f"Gasto × {relacion:.2f}".replace(".", ",") + (
                      " (la relación CLV ÷ gasto de este cliente). Cambia con los pedidos y el valor promedio porque "
                      "cambian el gasto." if clv is not None else
                      " (la relación promedio CLV ÷ gasto de los 500.000 clientes; R² = 0,89)."))
    perdida = prob * clv_usado
    comparar = lote is not None and clv is not None and not sin_cambios
    diferencia = perdida - lote["probabilidad"] * clv if comparar else 0
    v2.metric("Pérdida esperada", f"₹{g.formato_numero(perdida)}",
              f"{'-' if diferencia < 0 else '+'}₹{g.formato_numero(abs(diferencia))}" if comparar else None,
              delta_color="inverse",
              help="Probabilidad × CLV: lo que se espera perder si no se hace nada. La flecha indica cuánto "
                   "cambia frente a los valores reales del cliente (baja la probabilidad, pero también puede "
                   "subir el CLV si aumenta el gasto).")
    # Solo cuando se cambian valores: cuánto se movió la probabilidad frente a la real (guardada en oro)
    if lote is not None and not sin_cambios:
        p_lote = lote["probabilidad"]
        st.metric("Con los valores reales era", g.formato_pct(p_lote),
                      f"{(prob - p_lote) * 100:+.1f} pp".replace(".", ","), delta_color="inverse",
                      help="Puntos porcentuales que cambió la probabilidad con los valores del simulador.")
    if perfil is not None and perfil["conjunto"] == "test":
        real = bool(perfil["churn"])
        predijo = lote is not None and lote["probabilidad"] >= UMBRAL
        if real == predijo:
            st.success(f"Resultado real: {'se fue' if real else 'se quedó'}. El modelo acertó.",
                       icon=":material/check_circle:")
        else:
            st.warning(f"Resultado real: {'se fue' if real else 'se quedó'}. El modelo se equivocó: "
                       + ("lo marcó en riesgo y no se fue (falsa alarma)." if predijo else
                          "no lo marcó y sí se fue. Sus pedidos y devoluciones parecían de un cliente fiel; "
                          "la señal pudo estar en variables que se retiraron por fuga, como la recencia de compra."),
                       icon=":material/error:")
    for aviso in exp.get("advertencias", []):
        st.warning(f"Advertencia de la API: {aviso}", icon=":material/warning:")
with der:
    st.markdown("**Por qué: cada término del modelo suma o resta riesgo** (naranja suma, azul resta)")
    g.mostrar(g.cascada(exp["intercepto"], contrib, prob, alto=330))
    st.caption("El EBM es aditivo: punto de partida + términos = log-odds, y log-odds > 0 equivale a probabilidad "
               "> 0,5. Describe cómo decide el modelo, no por qué se van los clientes.")
    with st.expander("¿Qué son los log-odds y el punto de partida?", icon=":material/help:"):
        st.markdown("""
**Odds** = probabilidad de irse ÷ probabilidad de quedarse. Con p = 0,8 las odds son 0,8 ÷ 0,2 = 4 ("4 a 1").
**Log-odds** = el logaritmo de las odds. Es la escala en la que el modelo **suma**: la probabilidad no se puede
sumar (está atrapada entre 0 y 1), los log-odds sí (van de −∞ a +∞).

| Log-odds | −2 | −1 | **0** | +1 | +2 |
|---|---|---|---|---|---|
| Probabilidad | 12 % | 27 % | **50 %** | 73 % | 88 % |

- **Punto de partida (intercepto):** lo que el modelo diría de un cliente "típico" antes de mirar sus datos.
  Vale −1,56, es decir ≈ 17 %, cerca de la tasa de churn del 20,7 %.
- **Cada barra:** cuánto mueve a este cliente su valor en esa variable, frente al cliente típico. Positivo
  (naranja) sube el riesgo; negativo (azul) lo baja. +1 log-odds multiplica las odds por ≈ 2,7.
- **Total:** punto de partida + barras. Se convierte en probabilidad con p = 1 ÷ (1 + e^(−total)).
  Si el total pasa de 0, la probabilidad pasa de 50 % y el cliente queda en riesgo.
""")

# ---------------------------------------------------------------------------------------------------------------
# 4. Contrafactuales
# ---------------------------------------------------------------------------------------------------------------
st.divider()
if cf["bajo_umbral"]:
    st.subheader("Ya está bajo el umbral: no hace falta un cambio")
    st.caption("POST /contrafactuales solo busca cambios cuando la probabilidad es ≥ 0,5.")
else:
    def bajo_umbral_pct(p):
        """Probabilidad bajo el umbral con un decimal, truncada: 0,4996 se muestra 49,9 % y no «50 %»."""
        return g.formato_pct(math.floor(p * 1000) / 1000, 1)

    meta = cf.get("meta")
    if meta:
        nombre = textos.VARIABLES_MODELO[meta["variable"]].split(" (")[0].lower()
        actual, propuesto = meta["valor_actual"], meta["valor_propuesto"]
        cambio = (f"{'+' if propuesto > actual else ''}{g.formato_numero(propuesto - actual)} "
                  if meta["variable"] != "average_order_value" else f"a ₹{g.formato_numero(propuesto)} ")
        st.subheader(f"El cambio más pequeño que lo saca del riesgo: {nombre} {cambio}"
                     f"(de {g.formato_numero(actual)} a {g.formato_numero(propuesto)}) → probabilidad "
                     f"{bajo_umbral_pct(meta['probabilidad_con_cambio'])}")
        st.button(f"Aplicar este cambio en el simulador", on_click=aplicar,
                  args=(meta["variable"], propuesto), icon=":material/play_arrow:")
    else:
        st.subheader("Ningún cambio de una sola variable lo saca del riesgo")
    def valor_legible(variable, valor):
        """Valor de una variable del modelo en formato es-CO (₹ sin decimales para el valor promedio)."""
        if valor is None:
            return None
        return f"₹{g.formato_numero(valor)}" if variable == "average_order_value" else g.formato_numero(valor)

    filas = []
    for fila in cf.get("una_variable") or []:
        logra = fila["valor_bajo_umbral"] is not None
        filas.append({
            "Variable": textos.VARIABLES_MODELO[fila["variable"]].split(" (")[0],
            "Valor actual": valor_legible(fila["variable"], fila["valor_actual"]),
            "Valor más cercano bajo 50 %": (valor_legible(fila["variable"], fila["valor_bajo_umbral"]) if logra
                                            else "Ninguno lo logra"),
            "Probabilidad con ese valor": bajo_umbral_pct(fila["probabilidad_con_cambio"]) if logra else "—",
            "Mínima alcanzable": g.formato_pct(fila["probabilidad_minima"], 0),
        })
    st.caption("Moviendo una variable a la vez, dentro del rango visto en el entrenamiento. «Ninguno lo logra»: "
               "aunque esa variable recorra todo su rango, la probabilidad nunca baja de 50 %; «Mínima alcanzable» "
               "dice hasta dónde llega.")
    st.dataframe(filas, hide_index=True, width="stretch")

    # Dos variables a la vez: la API busca la combinación más cercana entre las dos variables que más mueven la
    # probabilidad. Si esa combinación deja una de las dos igual, en realidad es un cambio de una sola variable.
    dos = cf.get("dos_variables") or {}
    combinacion = dos.get("combinacion_mas_cercana")
    if combinacion:
        cambian = [v for v in dos["variables"]
                   if combinacion[v]["valor_propuesto"] != combinacion[v]["valor_actual"]]
        partes = [f"{textos.VARIABLES_MODELO[v].split(' (')[0].lower()} de "
                  f"{valor_legible(v, combinacion[v]['valor_actual'])} a "
                  f"{valor_legible(v, combinacion[v]['valor_propuesto'])}" for v in cambian]
        nombres = " y ".join(textos.VARIABLES_MODELO[v].split(" (")[0].lower() for v in dos["variables"])
        if len(cambian) == 2:
            st.caption(f"Moviendo dos variables a la vez ({nombres}), la combinación más cercana es "
                       f"{' y '.join(partes)} → probabilidad {bajo_umbral_pct(combinacion['probabilidad'])}.")
        else:
            st.caption(f"Moviendo dos variables a la vez ({nombres}) no aparece nada más cercano: lo mínimo sigue "
                       f"siendo cambiar solo {partes[0] if partes else 'una variable'}.")
    elif dos.get("variables"):
        st.caption("Ni moviendo dos variables a la vez la probabilidad baja de 50 %.")
    st.caption("Los contrafactuales describen al modelo: indican la meta de la campaña, no garantizan que el cliente "
               "se quede.")

# ---------------------------------------------------------------------------------------------------------------
# 5. Transparencia: qué se mandó y qué respondió la API
# ---------------------------------------------------------------------------------------------------------------
st.divider()
c1, c2 = st.columns(2)
with c1.expander("Ver la petición y la respuesta de la API", icon=":material/api:"):
    cuerpo = {"customer_id": cid, "summary_total_orders": pedidos, "total_spent": round(gasto, 2),
              "average_order_value": valor, "total_returns": devoluciones}
    st.markdown("`POST /explicar` — cuerpo enviado:")
    st.code(json.dumps(cuerpo, indent=2), language="json")
    st.markdown("Respuesta:")
    st.json(exp, expanded=False)
    st.markdown("`POST /contrafactuales` — respuesta:")
    st.json(cf, expanded=False)
    if lote is not None:
        st.markdown(f"`GET /clientes/{cid}` — respuesta:")
        st.json(lote, expanded=False)
with c2.expander("Qué modelo está respondiendo (GET /modelo)", icon=":material/info:"):
    try:
        ficha = api.modelo()
        st.markdown(f"**{ficha['modelo']}** (Explainable Boosting Machine), escenario «{ficha['escenario']}».")
        st.markdown("Variables: " + ", ".join(textos.VARIABLES_MODELO[v] for v in ficha["variables"]))
        st.markdown("Retiradas por fuga: " + ", ".join(textos.VARIABLES_RETIRADAS.get(v, v)
                                                        for v in ficha["variables_retiradas_por_fuga"]))
        m = ficha["metricas"]
        st.markdown(f"ROC-AUC: validación cruzada {m['validacion_cruzada']['roc_auc']:.3f} · test "
                    f"{m['test']['roc_auc']:.3f}. PR-AUC test {m['test']['pr_auc']:.3f}.".replace(".", ","))
        st.json({"hiperparametros": ficha["hiperparametros"], "versiones": ficha["versiones"]}, expanded=False)
    except api.ErrorAPI as error:
        st.error(str(error))
