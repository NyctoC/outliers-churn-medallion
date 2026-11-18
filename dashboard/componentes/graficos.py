"""Estilo común de los gráficos (Plotly) y gráficos que se repiten entre vistas.

Paleta (validada para daltonismo en claro y oscuro con el validador de la guía de visualización):
- AZUL: la serie principal (el modelo, el dato que se discute). Una serie = un color.
- NARANJA: segunda serie cuando hay que contrastar dos, o lo que suma riesgo en una explicación.
- GRIS: contexto (azar, promedio, umbral) — nunca compite con el dato principal.
Los textos van en la tinta del tema, no en el color de la serie. El título declarativo va en Streamlit, no en Plotly.
"""
import numpy as np
import plotly.graph_objects as go
import streamlit as st

AZUL = "#2a78d6"
NARANJA = "#eb6834"
GRIS = "#898781"
GRIS_CLARO = "#c3c2b7"
FUENTE = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def estilo(fig, alto=380, eje_y_pct=False, eje_x_pct=False, leyenda=False):
    """Márgenes compactos, rejilla tenue y leyenda arriba a la izquierda."""
    fig.update_layout(
        height=alto, margin=dict(l=8, r=8, t=30 if leyenda else 8, b=8), font=dict(family=FUENTE, size=13),
        showlegend=leyenda, hoverlabel=dict(font=dict(family=FUENTE)), bargap=0.3,
        separators=",.",  # formato es-CO en ejes y hover: decimales con coma, miles con punto
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridwidth=1, zeroline=False)
    if eje_y_pct:
        fig.update_yaxes(tickformat=".0%")
    if eje_x_pct:
        fig.update_xaxes(tickformat=".0%")
    return fig


def mostrar(fig, **kwargs):
    """st.plotly_chart con el tema de Streamlit (se adapta a claro/oscuro) y sin la barra de herramientas."""
    return st.plotly_chart(fig, theme="streamlit", width="stretch",
                           config={"displayModeBar": False, "locale": "es"}, **kwargs)


def nota(html):
    """Nota corta bajo un KPI: fondo azul tenue (semitransparente, sirve en tema claro y oscuro).
    Reemplaza el "delta" de st.metric cuando no hay una comparación (su flecha sugiere que algo subió)."""
    st.markdown(f'<div style="background:rgba(42,120,214,0.10);border-radius:8px;padding:6px 10px;'
                f'font-size:0.85rem;line-height:1.35;min-height:3.6em">{html}</div>', unsafe_allow_html=True)


def curva_ganancia(curva, marca=None, alto=380):
    """Curva de ganancia del modelo frente al azar. `marca` (0 a 1) resalta un punto con su lectura."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Contactar al azar",
                             line=dict(color=GRIS, width=1.5), hoverinfo="skip"))
    x = np.r_[0, curva["pct_contactado"]]
    y = np.r_[0, curva["pct_capturado"]]
    fig.add_trace(go.Scatter(
        x=x, y=y, mode="lines", name="Priorizar con el modelo", line=dict(color=AZUL, width=2.5),
        hovertemplate="Contactando al %{x:.0%} de mayor riesgo<br>se captura el %{y:.1%} del churn<extra></extra>"))
    if marca is not None:
        valor = float(np.interp(marca, x, y))
        fig.add_trace(go.Scatter(x=[marca], y=[valor], mode="markers", showlegend=False, hoverinfo="skip",
                                 marker=dict(size=10, color=AZUL, line=dict(width=2, color="white"))))
        fig.add_annotation(x=marca, y=valor, text=f"<b>{marca:.0%} → {valor:.0%}</b>".replace(".", ","),
                           showarrow=False, xanchor="left", yanchor="top", xshift=10, yshift=-2)
    fig.update_xaxes(title="% de clientes contactados (de mayor a menor riesgo)", range=[0, 1])
    fig.update_yaxes(title="% del churn capturado", range=[0, 1.02])
    return estilo(fig, alto=alto, eje_y_pct=True, eje_x_pct=True, leyenda=True)


def barras(categorias, valores, alto=360, horizontal=False, formato=".1%", referencia=None,
           texto_referencia=None, resaltar=None, hover=None, titulo_valor="Tasa de churn"):
    """Barras de una sola serie (un color). `resaltar`: categorías en azul y el resto en gris claro (énfasis).
    `referencia`: línea gris (promedio, umbral) con su texto."""
    categorias = [str(c) for c in categorias]
    colores = [AZUL if resaltar is None or c in resaltar else GRIS_CLARO for c in categorias]
    textos = [_fmt(v, formato) for v in valores]
    plantilla = hover or (f"%{{{'y' if horizontal else 'x'}}}<br>{titulo_valor}: "
                          f"%{{{'x' if horizontal else 'y'}:{formato}}}<extra></extra>")
    comun = dict(marker_color=colores, text=textos, textposition="outside", cliponaxis=False,
                 hovertemplate=plantilla, marker_line_width=0)
    barra = (go.Bar(y=categorias, x=valores, orientation="h", **comun) if horizontal
             else go.Bar(x=categorias, y=valores, **comun))
    fig = go.Figure(barra)
    maximo = max(list(valores) + ([referencia] if referencia is not None else [])) * 1.2
    eje_valor = dict(tickformat=".0%" if formato.endswith("%") else None, title=titulo_valor, range=[0, maximo])
    if horizontal:
        fig.update_xaxes(**eje_valor)
        fig.update_yaxes(autorange="reversed", type="category")
    else:
        fig.update_yaxes(**eje_valor)
        fig.update_xaxes(type="category")
    if referencia is not None:
        linea = dict(color=GRIS, width=1.5)
        if horizontal:
            fig.add_vline(x=referencia, line=linea, annotation_text=texto_referencia, annotation_position="top")
        else:
            fig.add_hline(y=referencia, line=linea, annotation_text=texto_referencia,
                          annotation_position="top left")
    return estilo(fig, alto=alto)


def cascada(intercepto, contribuciones, probabilidad, alto=360):
    """Explicación aditiva del EBM: intercepto + cada término = log-odds → probabilidad.
    Naranja = suma riesgo, azul = resta riesgo, gris = intercepto y total."""
    nombres = ["Punto de partida"] + list(contribuciones) + ["Total (log-odds)"]
    valores = [intercepto] + list(contribuciones.values()) + [0]
    medidas = ["absolute"] + ["relative"] * len(contribuciones) + ["total"]
    fig = go.Figure(go.Waterfall(
        x=nombres, y=valores, measure=medidas,
        text=[f"{v:+.2f}".replace(".", ",") for v in valores[:-1]] + [f"{intercepto + sum(contribuciones.values()):.2f}"
                                                                         .replace(".", ",")],
        textposition="outside", cliponaxis=False,
        increasing=dict(marker=dict(color=NARANJA)), decreasing=dict(marker=dict(color=AZUL)),
        totals=dict(marker=dict(color=GRIS)), connector=dict(line=dict(color=GRIS_CLARO, width=1)),
        hovertemplate="%{x}: %{y:+.2f} log-odds<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=GRIS, width=1), annotation_text="log-odds 0 = probabilidad 0,5 (umbral)",
                  annotation_position="bottom right")
    fig.update_yaxes(title="Log-odds de churn")
    return estilo(fig, alto=alto)


def medidor(probabilidad, umbral=0.5, alto=170):
    """Probabilidad de churn como barra horizontal 0–100 % con el umbral marcado y el valor escrito en la barra."""
    color = NARANJA if probabilidad >= umbral else AZUL
    fig = go.Figure(go.Bar(
        x=[probabilidad], y=[""], orientation="h", marker_color=color, width=0.6,
        text=[formato_pct(probabilidad, 0)], textposition="outside", cliponaxis=False,
        textfont=dict(size=16), hovertemplate="Probabilidad: %{x:.1%}<extra></extra>"))
    fig.add_vline(x=umbral, line=dict(color=GRIS, width=2))
    # Texto del umbral dentro del área del gráfico (arriba de la línea), para que no se corte
    fig.add_annotation(x=umbral, y=1, yref="paper", yanchor="bottom", showarrow=False,
                       text=f"umbral {formato_pct(umbral, 0)}", font=dict(size=12, color=GRIS))
    fig.update_xaxes(range=[0, 1], tickvals=[0, 0.25, 0.5, 0.75, 1],
                     ticktext=["0 %", "25 %", "50 %", "75 %", "100 %"], showgrid=True)
    fig.update_yaxes(showticklabels=False)
    fig = estilo(fig, alto=alto)
    fig.update_layout(margin=dict(l=8, r=40, t=28, b=8))
    return fig


def _fmt(valor, formato):
    if formato.endswith("%"):
        decimales = int(formato[1]) if formato[1].isdigit() else 0
        return formato_pct(valor, decimales)
    return formato_numero(valor)


def formato_numero(valor, decimales=0):
    """Número con separador de miles en punto y decimales con coma (formato es-CO)."""
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def formato_pct(valor, decimales=1):
    return f"{valor * 100:.{decimales}f} %".replace(".", ",")
