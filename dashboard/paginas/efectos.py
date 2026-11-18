"""Efecto de las variables: cómo cambia la probabilidad cuando se mueve cada variable, con POST /predecir.

Se parte de un cliente base y se mandan a la API lotes de variantes (una variable a la vez, y una rejilla de
pedidos × devoluciones). El gasto total se recalcula como pedidos × valor promedio, como en el modelado.
"""
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from componentes import api, datos, graficos as g, textos

UMBRAL = 0.5

st.header("Efecto de las variables")
st.caption("Cómo responde el modelo cuando cambia una sola cosa del cliente, calculado en vivo con "
            "`POST /predecir`.")

def usar_cliente_de_la_ficha():
    """Toma como base las variables del cliente abierto en la ficha (customer_360 con Athena)."""
    fila_cliente = datos.cliente(st.session_state["sim_cliente"]).df
    if not fila_cliente.empty:
        c = fila_cliente.iloc[0]
        st.session_state["ef_pedidos"] = int(c["summary_total_orders"])
        st.session_state["ef_devoluciones"] = int(c["total_returns"])
        st.session_state["ef_valor"] = int(round(float(c["average_order_value"]) / 250) * 250)
        st.session_state["ef_origen"] = f"cliente {int(c['customer_id'])}"


with st.container(border=True):
    cab, boton = st.columns([3, 1], vertical_alignment="center")
    cab.markdown("**Cliente base** (los demás valores quedan fijos mientras se mueve uno)"
                 + (f" · tomado del {st.session_state['ef_origen']}" if st.session_state.get("ef_origen") else ""))
    if "sim_cliente" in st.session_state:
        boton.button(f"Usar el cliente {st.session_state['sim_cliente']} de la ficha", width="stretch",
                     on_click=usar_cliente_de_la_ficha, icon=":material/person:")
    c1, c2, c3 = st.columns(3)
    for clave, inicial in {"ef_pedidos": 20, "ef_devoluciones": 3, "ef_valor": 6_000}.items():
        st.session_state.setdefault(clave, inicial)
    al_mover = dict(on_change=st.session_state.pop, args=("ef_origen", None))  # ya no es el cliente de la ficha
    pedidos = c1.slider("Pedidos", 1, 120, key="ef_pedidos", **al_mover)
    # Rango fijo (si cambia, Streamlit reinicia el slider); se limita a los pedidos al usarlo
    devoluciones = min(c2.slider("Devoluciones", 0, 10, key="ef_devoluciones", **al_mover), pedidos)
    valor = c3.slider("Valor promedio por pedido (₹)", 500, 12_000, step=250, key="ef_valor", **al_mover)


def predecir(filas):
    """Llama a /predecir en bloques de 1.000 y devuelve las probabilidades en el mismo orden."""
    probabilidades = []
    for inicio in range(0, len(filas), 1000):
        bloque = tuple(filas[inicio:inicio + 1000])
        probabilidades += [r["probabilidad"] for r in api.predecir(bloque)]
    return np.array(probabilidades)


def fila(p, v, d):
    return (float(p), float(p * v), float(v), float(d))


try:
    base = predecir([fila(pedidos, valor, devoluciones)])[0]
    rejilla_p = np.arange(1, 121)
    prob_p = predecir([fila(p, valor, min(devoluciones, p)) for p in rejilla_p])
    rejilla_d = np.arange(0, min(10, pedidos) + 1)
    prob_d = predecir([fila(pedidos, valor, d) for d in rejilla_d])
    rejilla_v = np.linspace(500, 12_000, 47)
    prob_v = predecir([fila(pedidos, v, devoluciones) for v in rejilla_v])
except api.ErrorAPI as error:
    st.error(str(error), icon=":material/cloud_off:")
    st.stop()

def primer_bajo_umbral(x, y):
    """Primer valor de x con probabilidad bajo el umbral (None si nunca baja)."""
    debajo = np.flatnonzero(np.asarray(y) < UMBRAL)
    return int(x[debajo[0]]) if len(debajo) else None


st.subheader(f"Para este cliente (probabilidad {g.formato_pct(base, 0)}), los pedidos mueven el riesgo de "
             f"{g.formato_pct(prob_p[0], 0)} a {g.formato_pct(prob_p[-1], 0)} y las devoluciones entre "
             f"{g.formato_pct(prob_d.min(), 0)} y {g.formato_pct(prob_d.max(), 0)}; el valor promedio casi no lo "
             f"cambia ({g.formato_pct(np.ptp(prob_v), 0)})" if np.ptp(prob_v) < 0.1 else
             f"Para este cliente (probabilidad {g.formato_pct(base, 0)}), los pedidos mueven el riesgo de "
             f"{g.formato_pct(prob_p[0], 0)} a {g.formato_pct(prob_p[-1], 0)} y las devoluciones entre "
             f"{g.formato_pct(prob_d.min(), 0)} y {g.formato_pct(prob_d.max(), 0)}")
st.caption(f"{len(rejilla_p) + len(rejilla_d) + len(rejilla_v) + 1} predicciones de la API para estas curvas. Cada "
           "curva mueve una variable y deja las demás fijas; el gasto se recalcula como pedidos × valor promedio. "
           "El punto marca el cliente base; la línea gris, el umbral de 50 %.")


def curva(x, y, actual, titulo_x, formato_x=None, cruce=None):
    fig = go.Figure(go.Scatter(x=x, y=y, mode="lines", line=dict(color=g.AZUL, width=2.5, shape="hv"),
                               hovertemplate=f"{titulo_x}: %{{x:,.0f}}<br>Probabilidad: %{{y:.1%}}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[actual], y=[np.interp(actual, x, y)], mode="markers", hoverinfo="skip",
                             marker=dict(size=10, color=g.AZUL, line=dict(width=2, color="white"))))
    fig.add_hline(y=UMBRAL, line=dict(color=g.GRIS, width=1.5))
    if cruce is not None:
        fig.add_annotation(x=cruce, y=UMBRAL, text=f"bajo 50 % desde {cruce}", showarrow=True, arrowhead=0,
                           ax=30, ay=-30, font=dict(size=12))
    fig.update_xaxes(title=titulo_x, tickformat=formato_x)
    fig.update_yaxes(title="Probabilidad de churn", range=[0, 1])
    return g.estilo(fig, alto=280, eje_y_pct=True)


a, b, c = st.columns(3, gap="medium")
with a:
    cruce_p = primer_bajo_umbral(rejilla_p, prob_p)
    st.markdown(f"**Pedidos: de {g.formato_pct(prob_p[0], 0)} con 1 pedido a {g.formato_pct(prob_p[-1], 0)} con 120**")
    g.mostrar(curva(rejilla_p, prob_p, pedidos, "Pedidos", cruce=cruce_p if prob_p[0] >= UMBRAL else None))
with b:
    sube = prob_d[-1] > prob_d[0]
    st.markdown(f"**Devoluciones: {'cada devolución sube el riesgo' if sube else 'su efecto depende de los pedidos'}**")
    g.mostrar(curva(rejilla_d, prob_d, devoluciones, "Devoluciones"))
with c:
    st.markdown(f"**Valor promedio: efecto {'pequeño' if np.ptp(prob_v) < 0.1 else 'notable'} "
                f"({g.formato_pct(np.ptp(prob_v), 0)} de rango)**")
    g.mostrar(curva(rejilla_v, prob_v, valor, "Valor promedio por pedido (₹)", ",.0f"))

st.divider()

# ---------------------------------------------------------------------------------------------------------------
# Interacción pedidos × devoluciones: todas las combinaciones válidas (1 a 120 pedidos, 0 a 10 devoluciones)
# ---------------------------------------------------------------------------------------------------------------
pasos_p = np.arange(1, 121)
pasos_d = np.arange(0, 11)
combinaciones = [(p, d) for d in pasos_d for p in pasos_p if d <= p]
try:
    prob_pd = predecir([fila(p, valor, d) for p, d in combinaciones])
except api.ErrorAPI as error:
    st.error(str(error), icon=":material/cloud_off:")
    st.stop()
matriz = np.full((len(pasos_d), len(pasos_p)), np.nan)
for (p, d), pr in zip(combinaciones, prob_pd):
    matriz[d, p - 1] = pr

# Frontera: para cada número de devoluciones, el mínimo de pedidos con el que la probabilidad baja de 50 %
frontera = {int(d): primer_bajo_umbral(pasos_p[~np.isnan(matriz[d])] , matriz[d][~np.isnan(matriz[d])])
            for d in pasos_d}
sin_dev, con_dev = frontera[0], frontera[10]
if sin_dev is not None and con_dev is not None:
    st.subheader(f"Pedidos y devoluciones se combinan: sin devoluciones "
                 f"{'basta 1 pedido' if sin_dev == 1 else f'bastan {sin_dev} pedidos'} para quedar bajo 50 %; "
                 f"con 10 devoluciones hacen falta {con_dev}")
else:
    st.subheader("Pedidos y devoluciones se combinan: el efecto de las devoluciones depende de los pedidos")
st.caption(f"Probabilidad de cada combinación con el valor promedio fijo en ₹{g.formato_numero(valor)}: "
           f"{g.formato_numero(len(combinaciones))} predicciones de la API. Más oscuro = más probabilidad de churn. La "
           "línea naranja es la frontera del 50 %: a su derecha el cliente queda bajo el umbral. Las celdas vacías tienen más "
           "devoluciones que pedidos, algo que la API rechaza.")
# Un solo tono (azul), de claro a oscuro: más oscuro = más probabilidad de churn
escala = [[0, "#cde2fb"], [0.25, "#86b6ef"], [0.5, "#3987e5"], [0.75, "#1c5cab"], [1, "#0d366b"]]
fig = go.Figure(go.Heatmap(
    x=pasos_p, y=pasos_d, z=matriz, zmin=0, zmax=1, colorscale=escala,
    colorbar=dict(title="Prob.", tickformat=".0%", tickvals=[0, 0.25, 0.5, 0.75, 1]),
    hovertemplate="Pedidos: %{x}<br>Devoluciones: %{y}<br>Probabilidad: %{z:.1%}<extra></extra>"))
# Escalera por los bordes de las celdas: en cada fila d, una línea vertical en el borde izquierdo de la celda frontera
xs, ys, textos_frontera = [], [], []
for d, p in sorted(frontera.items()):
    if p is None:
        continue
    xs += [p - 0.5, p - 0.5]
    ys += [d - 0.5, d + 0.5]
    textos_frontera += [f"Con {d} devoluciones: bajo 50 % desde {p} pedidos"] * 2
fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=g.NARANJA, width=3), name="Frontera de 50 %",
                         text=textos_frontera, hovertemplate="%{text}<extra></extra>"))
fig.add_trace(go.Scatter(x=[pedidos], y=[devoluciones], mode="markers", name="Cliente base", hoverinfo="skip",
                         marker=dict(size=14, symbol="x", color="white", line=dict(width=1.5, color="#0b0b0b"))))
fig.update_xaxes(title="Pedidos", range=[0.5, 120.5])
fig.update_yaxes(title="Devoluciones", dtick=1, range=[-0.5, 10.5])
g.mostrar(g.estilo(fig, alto=400, leyenda=True))
st.caption("El modelo tiene un término de interacción pedidos × devoluciones: el efecto de las devoluciones depende "
           "de cuántos pedidos tiene el cliente. Todo esto describe cómo decide el modelo, no relaciones causales.")
