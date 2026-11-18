"""Valor en riesgo: dónde está el CLV que se puede perder, y a quién llamar. Exploración agregada → cliente.

Flujo: filtros → KPIs → matriz riesgo × valor (clic en una celda) y desglose por dimensión (clic en una barra
filtra) → el dilema de priorizar por probabilidad o por pérdida esperada → lista de clientes → ficha del cliente.
Todo con consultas SQL a Athena sobre la capa oro.
"""
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from componentes import datos, graficos as g, textos

SECUENCIAL = [[0, "#cde2fb"], [0.25, "#86b6ef"], [0.5, "#3987e5"], [0.75, "#1c5cab"], [1, "#0d366b"]]


def rupias(valor):
    """₹ abreviado: mil millones (mil M), millones (M) o completo."""
    if abs(valor) >= 1e9:
        return f"₹{valor / 1e9:.1f} mil M".replace(".", ",")
    if abs(valor) >= 1e6:
        return f"₹{valor / 1e6:.1f} M".replace(".", ",")
    return f"₹{g.formato_numero(valor)}"


# La selección de un gráfico persiste entre recargas: para "soltarla" después de usarla, se cambia la key del
# gráfico con un contador (una key nueva = un gráfico sin selección).
for contador in ["k_matriz", "k_barras", "k_tabla"]:
    st.session_state.setdefault(contador, 0)


def soltar(contador):
    st.session_state[contador] += 1


# --- Un clic en una barra agrega un filtro: se aplica aquí, antes de dibujar los controles -----------------------
pendiente = st.session_state.pop("filtro_pendiente", None)
if pendiente:
    columna, valor = pendiente
    actuales = st.session_state.get(f"f_{columna}", [])
    if valor not in actuales:
        st.session_state[f"f_{columna}"] = actuales + [valor]

st.header("¿Dónde está el valor en riesgo?")
st.caption("Pérdida esperada = probabilidad de churn × CLV (valor de vida del cliente): lo que se espera perder si "
           "no se hace nada. Filtra, haz clic en la matriz o en las barras y baja hasta un cliente.")

# ---------------------------------------------------------------------------------------------------------------
# Filtros (una fila)
# ---------------------------------------------------------------------------------------------------------------
columnas = st.columns(len(datos.OPCIONES_FILTRO) + 1, vertical_alignment="bottom")
for columna, (campo, opciones) in zip(columnas, datos.OPCIONES_FILTRO.items()):
    columna.multiselect(textos.NOMBRES_FILTRO[campo], opciones, key=f"f_{campo}", placeholder="Todos")


def limpiar():
    for campo in datos.OPCIONES_FILTRO:
        st.session_state[f"f_{campo}"] = []
    st.session_state.pop("celda", None)
    soltar("k_matriz")


columnas[-1].button("Limpiar", on_click=limpiar, width="stretch", icon=":material/filter_alt_off:")
filtros = {c: st.session_state.get(f"f_{c}", []) for c in datos.OPCIONES_FILTRO}
filtros = {c: v for c, v in filtros.items() if v}

try:
    res = datos.resumen(filtros)
    mat = datos.matriz(filtros)
except datos.ErrorAthena as error:
    st.error(str(error))
    st.stop()

r = res.df.iloc[0]
if not r["clientes"]:
    st.warning("Ningún cliente cumple los filtros.")
    st.stop()

# Cada cifra lleva debajo una nota corta que dice cómo leerla (sin flechas de "delta": no hay comparación)
nota = g.nota
clv_marcados = r["clv_marcados"] or 0
perdida = r["perdida_esperada"]
k = st.columns(4, gap="medium")
with k[0]:
    st.metric("Clientes", g.formato_numero(r["clientes"]))
    nota("Con los filtros actuales." if filtros else "Toda la base, sin filtros.")
with k[1]:
    st.metric("Pérdida esperada", rupias(perdida),
              help="Para cada cliente: probabilidad de churn × su CLV. Luego se suma.")
    nota(f"<b>{g.formato_pct(perdida / r['clv_total'])}</b> del CLV total ({rupias(r['clv_total'])}).")
with k[2]:
    st.metric("CLV de los marcados en riesgo", rupias(clv_marcados),
              help="Suma del CLV completo de los clientes con probabilidad ≥ 50 %.")
    texto = f"<b>{g.formato_numero(r['marcados'])}</b> clientes con p ≥ 50 %."
    if perdida and clv_marcados < perdida:
        texto += f" Al menos el <b>{g.formato_pct(1 - clv_marcados / perdida, 0)}</b> de la pérdida está en los no marcados."
    nota(texto)
with k[3]:
    st.metric("Churners esperados", g.formato_numero(r["churners_esperados"]),
              help="Cuántos clientes se espera que se vayan: suma de las probabilidades de churn.")
    nota(f"<b>{g.formato_pct(r['churners_esperados'] / r['clientes'])}</b> de los clientes.")

marcados_txt = g.formato_numero(r["marcados"])
esperados_txt = g.formato_numero(r["churners_esperados"])
with st.expander(f"¿Por qué el modelo marca a {marcados_txt} clientes si se espera que se vayan {esperados_txt}?",
                 icon=":material/help:"):
    st.markdown(f"""
Las dos cifras responden preguntas distintas:

- **Marcados en riesgo ({marcados_txt}):** cuántos clientes tienen probabilidad de churn **de 50 % o más**. Es un
  conteo con corte: cada cliente sobre el umbral cuenta 1 y el resto cuenta 0. Es la lista que el modelo señala.
- **Churners esperados ({esperados_txt}):** cuántos clientes **se espera que se vayan en total**. Es la suma de las
  probabilidades de todos: un cliente con 30 % aporta 0,3 y uno con 80 % aporta 0,8.

**Ejemplo:** 10 clientes con 30 % de probabilidad cada uno. **Ninguno** queda marcado, porque ninguno llega al 50 %,
pero en promedio **3 de ellos se van** (10 × 0,3).

Eso pasa a gran escala: hay cientos de miles de clientes con 15 %, 25 % o 40 % de probabilidad. Ninguno supera el
umbral, pero sumados son la mayoría de los que se van. Además, no todos los marcados se van: 60 % no es certeza.

**Qué implica:** quedarse solo con la lista de marcados deja fuera a buena parte de quienes se van y del dinero en
riesgo. Por eso esta vista ordena por **pérdida esperada** (probabilidad × CLV) y no solo por el umbral: la matriz,
el dilema y la lista de clientes permiten priorizar más allá de los marcados.
""")

# ---------------------------------------------------------------------------------------------------------------
# Matriz riesgo × valor
# ---------------------------------------------------------------------------------------------------------------
m = mat.df.copy()
total_perdida = m["perdida"].sum()
por_riesgo = m.groupby("decil_riesgo")["perdida"].sum()
top_riesgo = por_riesgo.get(1, 0) / total_perdida if total_perdida else 0
celda_max = m.loc[m["perdida"].idxmax()]
celda = st.session_state.get("celda")

izq, der = st.columns([3, 2], gap="large")
with izq:
    st.subheader(f"El 10 % de mayor riesgo solo carga el {g.formato_pct(top_riesgo, 0)} de la pérdida esperada: "
                 f"quien más se va, menos vale")
    st.caption("Cada cuadro es un grupo de clientes por decil de riesgo (filas) y de CLV (columnas); el color es su "
               "pérdida esperada. Haz clic en un cuadro para ver sus clientes abajo.")
    x = 11 - m["decil_valor"]  # a la derecha, más valor
    y = m["decil_riesgo"]
    tamano = np.where((m["decil_riesgo"] == (celda or (0, 0))[0]) & (m["decil_valor"] == (celda or (0, 0))[1]), 2.5, 0)
    fig = go.Figure(go.Scatter(
        x=x, y=y, mode="markers",
        marker=dict(symbol="square", size=30, color=m["perdida"] / 1e9, colorscale=SECUENCIAL,
                    line=dict(width=tamano, color="#eb6834"),
                    colorbar=dict(title="mil M ₹", thickness=12)),
        customdata=np.c_[m["decil_riesgo"], m["decil_valor"], m["clientes"], m["probabilidad_media"],
                         m["clv_medio"], m["perdida"] / 1e9],
        hovertemplate=("Riesgo D%{customdata[0]} · Valor D%{customdata[1]}<br>Clientes: %{customdata[2]:,}"
                       "<br>Probabilidad media: %{customdata[3]:.1%}<br>CLV medio: ₹%{customdata[4]:,.0f}"
                       "<br>Pérdida esperada: ₹%{customdata[5]:.2f} mil M<extra></extra>")))
    fig.update_xaxes(title="CLV → (decil, D1 = 10 % de mayor valor)", tickvals=list(range(1, 11)),
                     ticktext=[f"D{11 - i}" for i in range(1, 11)], range=[0.4, 10.6])
    fig.update_yaxes(title="← Riesgo de churn (decil, D1 = mayor)", tickvals=list(range(1, 11)),
                     ticktext=[f"D{i}" for i in range(1, 11)], autorange="reversed")
    evento = g.mostrar(g.estilo(fig, alto=430), on_select="rerun", selection_mode="points",
                       key=f"matriz_{st.session_state['k_matriz']}")
    puntos = evento.selection.points if evento and evento.selection else []
    if puntos:
        st.session_state["celda"] = (int(puntos[0]["y"]), int(11 - puntos[0]["x"]))
        soltar("k_matriz")
        st.rerun()

with der:
    dimension = st.selectbox("Desglosar la pérdida esperada por", list(datos.DIMENSIONES),
                             format_func=datos.DIMENSIONES.get, key="dimension")
    dim = datos.por_dimension(filtros, dimension)
    d = dim.df
    lider = d.iloc[0]
    if len(d) == 1:
        st.markdown(f"**Con los filtros actuales solo queda {lider['valor']}: elige otra dimensión para desglosar**")
    else:
        st.markdown(f"**{lider['valor']} concentra {rupias(lider['perdida'])} "
                    f"({g.formato_pct(lider['perdida'] / d['perdida'].sum(), 0)}) de la pérdida esperada**")
    fig = go.Figure(go.Bar(
        y=d["valor"].astype(str), x=d["perdida"] / 1e9, orientation="h", marker_color=g.AZUL,
        text=[rupias(v) for v in d["perdida"]], textposition="outside", cliponaxis=False,
        customdata=np.c_[d["clientes"], d["probabilidad_media"], d["clv_medio"]],
        hovertemplate=("%{y}<br>Pérdida esperada: ₹%{x:.2f} mil M<br>Clientes: %{customdata[0]:,}"
                       "<br>Probabilidad media: %{customdata[1]:.1%}<br>CLV medio: ₹%{customdata[2]:,.0f}"
                       "<extra></extra>")))
    fig.update_xaxes(title="Pérdida esperada (mil M ₹)", range=[0, d["perdida"].max() / 1e9 * 1.3])
    fig.update_yaxes(autorange="reversed", type="category")
    evento_barras = g.mostrar(g.estilo(fig, alto=370), on_select="rerun", selection_mode="points",
                              key=f"barras_{dimension}_{st.session_state['k_barras']}")
    st.caption("Clic en una barra para filtrar por ese valor.")
    puntos = evento_barras.selection.points if evento_barras and evento_barras.selection else []
    if puntos:
        st.session_state["filtro_pendiente"] = (dimension, str(puntos[0]["y"]))
        soltar("k_barras")
        st.rerun()

datos.mostrar_sql(res, mat, dim)
st.caption("Ojo: el CLV casi es el gasto total (correlación 0,94), y el gasto bajo es una de las variables que sube "
           "el riesgo en el modelo. Que alto riesgo coincida con bajo valor es en parte consecuencia de eso.")

st.divider()

# ---------------------------------------------------------------------------------------------------------------
# El dilema: ¿priorizar por probabilidad o por pérdida esperada?
# ---------------------------------------------------------------------------------------------------------------
dil = datos.dilema(filtros)
dd = dil.df
pct = st.slider("Si la empresa puede contactar al…", 1, 50, 10, format="%d %% de los clientes", key="pct") / 100


def lectura(estrategia, columna):
    serie = dd[dd["estrategia"] == estrategia]
    return float(np.interp(pct, np.r_[0, serie["pct_contactado"]], np.r_[0, serie[columna]]))


prob_ch, prob_va = lectura("probabilidad", "pct_churners"), lectura("probabilidad", "pct_valor")
perd_ch, perd_va = lectura("perdida", "pct_churners"), lectura("perdida", "pct_valor")
st.subheader(f"El dilema: contactando al {g.formato_pct(pct, 0)}, priorizar por probabilidad encuentra el "
             f"{g.formato_pct(prob_ch, 0)} de los que se van; priorizar por pérdida esperada protege el "
             f"{g.formato_pct(perd_va, 0)} de su valor")
st.caption("Clientes de test (el modelo no los vio al entrenar), comparados con lo que realmente pasó. Valor = CLV "
           "de los clientes que sí se fueron. Ninguna estrategia gana en las dos: es una decisión de negocio.")

c1, c2 = st.columns(2, gap="large")
for contenedor, columna, titulo, eje in [
    (c1, "pct_churners", "Churners encontrados", "% de los clientes que se fueron"),
    (c2, "pct_valor", "Valor de esos churners", "% del CLV que se fue"),
]:
    with contenedor:
        a, b = (prob_ch, perd_ch) if columna == "pct_churners" else (prob_va, perd_va)
        st.markdown(f"**{titulo}: {g.formato_pct(a, 0)} por probabilidad vs. {g.formato_pct(b, 0)} por pérdida "
                    f"esperada**")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Al azar", line=dict(color=g.GRIS, width=1),
                                 hoverinfo="skip"))
        for estrategia, nombre, color in [("probabilidad", "Priorizar por probabilidad", g.AZUL),
                                          ("perdida", "Priorizar por pérdida esperada", g.NARANJA)]:
            serie = dd[dd["estrategia"] == estrategia]
            fig.add_trace(go.Scatter(x=np.r_[0, serie["pct_contactado"]], y=np.r_[0, serie[columna]], mode="lines",
                                     name=nombre, line=dict(color=color, width=2.5),
                                     hovertemplate=f"{nombre}<br>Contactando al %{{x:.0%}}: %{{y:.1%}}<extra></extra>"))
        fig.add_vline(x=pct, line=dict(color=g.GRIS, width=1))
        fig.update_xaxes(title="% de clientes contactados", range=[0, 1])
        fig.update_yaxes(title=eje, range=[0, 1.02])
        g.mostrar(g.estilo(fig, alto=320, eje_x_pct=True, eje_y_pct=True, leyenda=True))
datos.mostrar_sql(dil)

st.divider()

# ---------------------------------------------------------------------------------------------------------------
# Lista de clientes → ficha
# ---------------------------------------------------------------------------------------------------------------
cab, orden_col, quitar = st.columns([4, 2, 1], vertical_alignment="bottom")
with cab:
    if celda:
        st.subheader(f"Clientes de la celda riesgo D{celda[0]} × valor D{celda[1]}")
    else:
        st.subheader("Clientes con mayor pérdida esperada")
orden = orden_col.segmented_control("Ordenar por", ["perdida", "probabilidad"], default="perdida", key="orden",
                                    format_func={"perdida": "Pérdida esperada", "probabilidad": "Probabilidad"}.get)
if celda and quitar.button("Quitar celda", width="stretch"):
    st.session_state.pop("celda", None)
    soltar("k_matriz")
    st.rerun()

lista = datos.clientes_celda(filtros, celda[0] if celda else None, celda[1] if celda else None, orden or "perdida")
tabla = lista.df.assign(motivo_principal=lista.df["motivo_principal"].map(textos.TERMINOS))
st.caption("Los primeros 200 con los filtros actuales. **Selecciona una fila** para abrir la ficha del cliente y "
           "simular cambios con la API.")
evento_tabla = st.dataframe(
    tabla, hide_index=True, width="stretch", height=340, on_select="rerun", selection_mode="single-row",
    key=f"tabla_{st.session_state['k_tabla']}",
    column_config={
        "customer_id": st.column_config.NumberColumn("Cliente", format="plain"),
        "probabilidad": st.column_config.ProgressColumn("Probabilidad", min_value=0, max_value=1, format="percent"),
        "clv": st.column_config.NumberColumn("CLV (₹)", format="localized"),
        "perdida": st.column_config.NumberColumn("Pérdida esperada (₹)", format="localized"),
        "motivo_principal": "Motivo", "campana": "Campaña", "membership_tier": "Membresía", "city": "Ciudad",
        "pedidos": "Pedidos", "devoluciones": "Devoluciones", "conjunto": "Conjunto",
    })
st.download_button("Descargar esta lista (CSV)", tabla.to_csv(index=False).encode("utf-8"),
                   file_name="clientes_valor_en_riesgo.csv", mime="text/csv", icon=":material/download:")
datos.mostrar_sql(lista)

filas = evento_tabla.selection.rows if evento_tabla and evento_tabla.selection else []
if filas:
    st.session_state["sim_cliente"] = int(tabla.iloc[filas[0]]["customer_id"])
    soltar("k_tabla")
    st.switch_page("paginas/simulador.py")
