"""Funciones del análisis exploratorio y de calidad de datos.

Las de distribución, atípicos, correlación, VIF, completitud, duplicidad, conformidad y llaves vienen de
los retos del curso de Aprendizaje Automático (tasación de diamantes y accidentalidad en El Poblado).
Las de relación con el objetivo están adaptadas a un objetivo binario (churn).
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import MaxNLocator
from scipy.stats import chi2_contingency
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.linear_model import LinearRegression
from sklearn.metrics import roc_auc_score

from churn.data import RAIZ

DIR_FIGURAS = RAIZ / "reports" / "figures"


def _mostrar(fig, nombre_figura):
    """Muestra la figura y, si se indica `nombre_figura`, la guarda en reports/figures/<nombre>.png
    para usarla en el documento final y en la presentación."""
    if nombre_figura is not None:
        DIR_FIGURAS.mkdir(parents=True, exist_ok=True)
        fig.savefig(DIR_FIGURAS / f"{nombre_figura}.png", dpi=150, bbox_inches="tight")
    plt.show()
    plt.close(fig)


def _titulo_general(fig, titulo):
    """Título general de la figura con un espacio fijo en pulgadas, para que no se monte sobre la primera
    fila de gráficos sin importar la altura de la figura."""
    alto = fig.get_figheight()
    fig.suptitle(titulo, fontsize=14, y=1 - 0.2 / alto)
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.5 / alto))


# ------------------------------------------------------------------------------------------------
# Entendimiento: llaves entre tablas
# ------------------------------------------------------------------------------------------------

def resumen_llave(df, llave, tabla):
    """Indica si las columnas de `llave` identifican de forma única cada fila de `df`."""
    unicas = len(df.drop_duplicates(llave))
    return {
        "tabla": tabla,
        "llave": ", ".join(llave),
        "filas": len(df),
        "combinaciones_unicas": unicas,
        "duplicadas": len(df) - unicas,
        "nulos_en_llave": int(df[llave].isna().any(axis=1).sum()),
        "es_llave": unicas == len(df) and df[llave].notna().all().all(),
    }


def comparar_llaves(izq, der, llave, nombre_izq, nombre_der):
    """Cruza las combinaciones únicas de `llave` de dos tablas e indica en cuál está cada una."""
    cruce = izq[llave].drop_duplicates().merge(
        der[llave].drop_duplicates(), on=llave, how="outer", indicator=True
    )
    cruce["ubicacion"] = cruce["_merge"].map(
        {"left_only": f"solo en {nombre_izq}", "both": "en ambas", "right_only": f"solo en {nombre_der}"}
    )
    return cruce.drop(columns="_merge")


# ------------------------------------------------------------------------------------------------
# Análisis univariado
# ------------------------------------------------------------------------------------------------

def graficar_distribucion(df, columnas=None, bins=50, n_cols=4, nombre_figura=None):
    """Histograma de cada variable numérica del DataFrame, con su coeficiente de asimetría (skewness).

    Interpretación de la asimetría:
    - Cerca de 0 (entre -0.5 y 0.5): distribución aproximadamente simétrica.
    - Entre 0.5 y 1 (o entre -1 y -0.5): asimetría moderada.
    - Mayor a 1 (o menor a -1): asimetría alta.
    - Positiva: cola larga hacia la derecha (pocos valores muy altos). Negativa: cola hacia la izquierda.
    """
    if columnas is None:
        columnas = df.select_dtypes(include="number").columns
    n_filas = int(np.ceil(len(columnas) / n_cols))

    fig, axes = plt.subplots(n_filas, n_cols, figsize=(4.5 * n_cols, 3.5 * n_filas), squeeze=False)
    axes = axes.ravel()

    for ax, col in zip(axes, columnas):
        ax.hist(df[col].dropna(), bins=bins, color="steelblue", alpha=0.8)
        ax.set_title(f"{col} (asimetría = {df[col].skew():.2f})")
        ax.set_ylabel("Frecuencia")

    for ax in axes[len(columnas):]:
        ax.set_visible(False)

    _titulo_general(fig, "Distribución de las variables numéricas")
    _mostrar(fig, nombre_figura)


def graficar_atipicos(df, columnas=None, n_cols=4, nombre_figura=None):
    """Boxplot de cada variable numérica y resumen de atípicos."""
    if columnas is None:
        columnas = df.select_dtypes(include="number").columns
    n_filas = int(np.ceil(len(columnas) / n_cols))

    fig, axes = plt.subplots(n_filas, n_cols, figsize=(4.5 * n_cols, 3 * n_filas), squeeze=False)
    axes = axes.ravel()
    resumen = []

    for ax, col in zip(axes, columnas):
        datos = df[col].dropna()
        q1, q3 = np.percentile(datos, [25, 75])
        iqr = q3 - q1
        lim_inf, lim_sup = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        n_atipicos = ((datos < lim_inf) | (datos > lim_sup)).sum()
        resumen.append({
            "variable": col,
            "limite_inferior": lim_inf,
            "limite_superior": lim_sup,
            "n_atipicos": n_atipicos,
            "pct_atipicos": 100 * n_atipicos / len(datos),
        })

        ax.boxplot(
            datos,
            orientation="horizontal",
            flierprops={"marker": "o", "markersize": 3, "markerfacecolor": "red", "alpha": 0.4},
        )
        ax.set_title(col)
        ax.set_yticks([])
        ax.set_xlabel(f"{n_atipicos} atípicos ({n_atipicos / len(datos):.1%})")

    for ax in axes[len(columnas):]:
        ax.set_visible(False)

    _titulo_general(fig, "Boxplots de las variables numéricas")
    _mostrar(fig, nombre_figura)

    return pd.DataFrame(resumen).set_index("variable").round(2)


def conteo_categoricas(df, columnas=None, n_cols=3, nombre_figura=None):
    """Gráfico de barras con el conteo de cada categoría y tabla con conteo y porcentaje."""
    if columnas is None:
        columnas = df.select_dtypes(exclude="number").columns
    n_filas = int(np.ceil(len(columnas) / n_cols))

    fig, axes = plt.subplots(n_filas, n_cols, figsize=(5 * n_cols, 3.5 * n_filas), squeeze=False)
    axes = axes.ravel()
    tablas = []

    for ax, col in zip(axes, columnas):
        conteo = df[col].value_counts()
        ax.bar(conteo.index.astype(str), conteo.values, color="steelblue", alpha=0.8)
        ax.set_title(col)
        ax.set_ylabel("Frecuencia")
        ax.tick_params(axis="x", rotation=45)

        tablas.append(pd.DataFrame({
            "variable": col,
            "categoria": conteo.index,
            "conteo": conteo.values,
            "porcentaje": (100 * conteo.values / conteo.sum()).round(2),
        }))

    for ax in axes[len(columnas):]:
        ax.set_visible(False)

    _titulo_general(fig, "Conteo de las variables categóricas")
    _mostrar(fig, nombre_figura)

    return pd.concat(tablas).set_index(["variable", "categoria"])


def evaluar_uniformidad(df, columnas=None, bins=20):
    """Qué tan cerca de una distribución uniforme está cada variable numérica.

    Divide el rango de cada variable en `bins` intervalos iguales y compara las frecuencias observadas
    con las de una uniforme. El coeficiente de variación de las frecuencias (cv_frecuencias) es cercano
    a 0 cuando todos los intervalos tienen casi los mismos registros, es decir, cuando la variable es
    casi uniforme. Con 500 mil filas la prueba chi-cuadrado rechaza casi siempre, por eso se reporta
    también el tamaño de efecto (V de Cramér de bondad de ajuste). Si una variable tiene menos de `bins`
    valores distintos, se compara entre esos valores: más intervalos quedarían vacíos y la harían ver
    menos uniforme de lo que es.
    """
    if columnas is None:
        columnas = df.select_dtypes(include="number").columns
    filas = []
    for col in columnas:
        datos = df[col].dropna()
        valores_unicos = datos.nunique()
        if valores_unicos < bins:
            frecuencias = datos.value_counts().to_numpy()
        else:
            frecuencias, _ = np.histogram(datos, bins=bins)
        n_grupos = len(frecuencias)
        esperado = np.full(n_grupos, len(datos) / n_grupos)
        chi2 = ((frecuencias - esperado) ** 2 / esperado).sum()
        filas.append({
            "variable": col,
            "valores_unicos": valores_unicos,
            "cv_frecuencias": frecuencias.std() / frecuencias.mean(),
            "v_cramer_vs_uniforme": np.sqrt(chi2 / (len(datos) * (n_grupos - 1))),
        })
    return pd.DataFrame(filas).set_index("variable").sort_values("cv_frecuencias").round(3)


# ------------------------------------------------------------------------------------------------
# Relación con el objetivo (binario)
# ------------------------------------------------------------------------------------------------

def tasa_objetivo_por_categoria(df, objetivo, columnas=None, n_cols=3, max_categorias=20,
                                nombre_figura=None):
    """Tasa del objetivo (proporción de 1) por categoría, con su intervalo de confianza del 95 %.

    La línea punteada es la tasa global: una categoría cuyo intervalo no la cruza se diferencia de
    verdad del promedio. Las variables con más de `max_categorias` categorías muestran solo las más
    frecuentes. Devuelve la tabla con registros, tasa e intervalo por categoría.
    """
    if columnas is None:
        columnas = df.drop(columns=objetivo).select_dtypes(exclude="number").columns
    n_filas = int(np.ceil(len(columnas) / n_cols))
    y = df[objetivo].astype(float)
    tasa_global = y.mean()

    fig, axes = plt.subplots(n_filas, n_cols, figsize=(5 * n_cols, 3.8 * n_filas), squeeze=False)
    axes = axes.ravel()
    tablas = []

    for ax, col in zip(axes, columnas):
        tabla = y.groupby(df[col].astype("object").fillna("(nulo)")).agg(registros="size", tasa="mean")
        tabla = tabla.sort_values("registros", ascending=False).head(max_categorias).sort_values("tasa")
        tabla["ic95"] = 1.96 * np.sqrt(tabla["tasa"] * (1 - tabla["tasa"]) / tabla["registros"])

        ax.barh(tabla.index.astype(str), 100 * tabla["tasa"], xerr=100 * tabla["ic95"],
                color="steelblue", alpha=0.8, ecolor="gray")
        ax.axvline(100 * tasa_global, color="darkorange", linestyle="--")
        ax.set_title(col)
        ax.set_xlabel(f"% {objetivo}")
        ax.tick_params(axis="y", labelsize=8)

        tablas.append(tabla.assign(variable=col).rename_axis("categoria").reset_index())

    for ax in axes[len(columnas):]:
        ax.set_visible(False)

    _titulo_general(fig, f"Tasa de {objetivo} por categoría (IC 95 %; en naranja la tasa global {tasa_global:.1%})")
    _mostrar(fig, nombre_figura)

    resultado = pd.concat(tablas).set_index(["variable", "categoria"])
    resultado[["tasa", "ic95"]] = (100 * resultado[["tasa", "ic95"]]).round(2)
    return resultado


def tasa_objetivo_por_rango(df, objetivo, columnas=None, n_rangos=10, n_cols=4, nombre_figura=None):
    """Tasa del objetivo en cada decil (o `n_rangos` cuantiles) de las variables numéricas.

    Una línea plana alrededor de la tasa global indica que la variable no separa las clases; una
    pendiente o una forma de U indica relación (no necesariamente lineal).
    """
    if columnas is None:
        columnas = df.drop(columns=objetivo).select_dtypes(include="number").columns
    n_filas = int(np.ceil(len(columnas) / n_cols))
    y = df[objetivo].astype(float)

    fig, axes = plt.subplots(n_filas, n_cols, figsize=(4.5 * n_cols, 3.3 * n_filas), squeeze=False,
                             sharey=True)
    axes = axes.ravel()

    for ax, col in zip(axes, columnas):
        rango = pd.qcut(df[col], n_rangos, duplicates="drop")
        tasa = y.groupby(rango, observed=True).mean()
        ax.plot(range(len(tasa)), 100 * tasa.values, marker="o", color="steelblue")
        ax.axhline(100 * y.mean(), color="darkorange", linestyle="--")
        ax.set_title(col, fontsize=10)
        ax.set_xlabel("Rango (de menor a mayor)")
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_ylabel(f"% {objetivo}")

    for ax in axes[len(columnas):]:
        ax.set_visible(False)

    _titulo_general(fig, f"Tasa de {objetivo} por rango de cada variable numérica (en naranja la tasa global)")
    _mostrar(fig, nombre_figura)


def resumen_relacion_objetivo(df, objetivo, columnas=None):
    """Fuerza de la relación de cada variable con el objetivo binario.

    - auc_univariado: ROC-AUC de usar solo esa variable para ordenar a los clientes. Para las
      categóricas se usa la tasa del objetivo de cada categoría como puntaje. 0.5 = sin señal;
      se reporta max(AUC, 1 - AUC) para que no importe el sentido de la relación. Un valor cercano
      a 1 en una sola variable es una alerta de fuga de información.
    - efecto: d de Cohen (numéricas: diferencia de medias entre clases en desviaciones estándar) o
      V de Cramér (categóricas). Con muchas filas, una diferencia muy pequeña puede salir "significativa",
      por eso importa el tamaño del efecto y no el p-valor. Referencia: d de 0.2 pequeño, 0.5 mediano, 0.8 grande;
      V de 0.1 pequeño, 0.3 mediano, 0.5 grande.

    Calcúlese solo sobre train: la tasa por categoría usa el objetivo.
    """
    if columnas is None:
        columnas = df.columns.drop(objetivo)
    y = df[objetivo].astype(int)
    filas = []
    for col in columnas:
        serie = df[col]
        numerica = pd.api.types.is_numeric_dtype(serie) and not pd.api.types.is_bool_dtype(serie)
        if numerica:
            validos = serie.notna()
            puntaje, y_validos = serie[validos], y[validos]
            g1, g0 = puntaje[y_validos == 1], puntaje[y_validos == 0]
            desviacion = np.sqrt((g1.var() + g0.var()) / 2)
            efecto, metrica = (g1.mean() - g0.mean()) / desviacion if desviacion > 0 else 0.0, "d_cohen"
        else:
            categorias = serie.astype("object").fillna("(nulo)")
            puntaje, y_validos = categorias.map(y.groupby(categorias).mean()), y
            tabla = pd.crosstab(categorias, y)
            chi2 = chi2_contingency(tabla)[0] if tabla.shape[0] > 1 else 0.0
            efecto, metrica = np.sqrt(chi2 / (len(y) * (min(tabla.shape) - 1))), "v_cramer"
        auc = roc_auc_score(y_validos, puntaje) if y_validos.nunique() == 2 else np.nan
        filas.append({
            "variable": col,
            "tipo": "numérica" if numerica else "categórica",
            "pct_nulos": 100 * serie.isna().mean(),
            "auc_univariado": max(auc, 1 - auc),
            "metrica_efecto": metrica,
            "efecto": efecto,
        })
    return pd.DataFrame(filas).set_index("variable").sort_values("auc_univariado", ascending=False).round(4)


# ------------------------------------------------------------------------------------------------
# Análisis multivariado
# ------------------------------------------------------------------------------------------------

def graficar_matriz_correlacion(df, metodo="pearson", columnas=None, nombre_figura=None):
    """Mapa de calor de la matriz de correlación entre las variables numéricas.
    """
    if columnas is None:
        columnas = df.select_dtypes(include="number").columns
    corr = df[columnas].corr(method=metodo)

    # Se oculta la diagonal y todo lo que está por encima (es la misma información reflejada)
    triangular = corr.where(np.tril(np.ones(corr.shape, dtype=bool), k=-1))
    # La primera fila y la última columna quedan vacías, así que no se muestran
    triangular = triangular.iloc[1:, :-1]
    filas, cols = triangular.index, triangular.columns

    fig, ax = plt.subplots(figsize=(0.9 * len(cols) + 2, 0.8 * len(filas) + 1))
    im = ax.imshow(triangular, cmap="coolwarm", vmin=-1, vmax=1)
    fig.colorbar(im, ax=ax, shrink=0.8)

    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=45, ha="right")
    ax.set_yticks(range(len(filas)))
    ax.set_yticklabels(filas)
    for i in range(len(filas)):
        for j in range(len(cols)):
            valor = triangular.iloc[i, j]
            if pd.notna(valor):
                ax.text(j, i, f"{valor:.2f}", ha="center", va="center", fontsize=8,
                        color="white" if abs(valor) > 0.6 else "black")
    for borde in ax.spines.values():
        borde.set_visible(False)

    ax.set_title(f"Matriz de correlación ({metodo})", fontsize=14)
    fig.tight_layout()
    _mostrar(fig, nombre_figura)

    return corr


def calcular_vif(df, columnas=None, nombre_figura=None):
    """Factor de inflación de la varianza (VIF) de cada variable numérica.

    El VIF de una variable es 1 / (1 - R^2), donde R^2 sale de una regresión lineal de esa variable
    contra todas las demás. Indica cuánto se puede explicar una variable con las otras:
    VIF < 5 es aceptable, entre 5 y 10 es multicolinealidad moderada y > 10 es alta.
    Grafica los VIF de cada variable. Las filas con nulos se excluyen del cálculo.
    """
    if columnas is None:
        columnas = df.select_dtypes(include="number").columns
    X = df[columnas].dropna().astype(float)

    vif = {}
    for col in columnas:
        otras = X.drop(columns=col)
        r2 = LinearRegression().fit(otras, X[col]).score(otras, X[col])
        vif[col] = np.inf if r2 == 1 else 1 / (1 - r2)
    vif = pd.Series(vif, name="VIF").sort_values()

    fig, ax = plt.subplots(figsize=(7, 0.45 * len(vif) + 1.5))
    colores = ["firebrick" if v > 10 else "orange" if v > 5 else "steelblue" for v in vif]
    ax.barh(vif.index, vif.values, color=colores)
    ax.axvline(5, color="orange", linestyle="--", label="VIF = 5")
    ax.axvline(10, color="firebrick", linestyle="--", label="VIF = 10")
    for i, v in enumerate(vif.values):
        ax.text(v, i, f" {v:.1f}", va="center", fontsize=8)
    ax.set_xlabel("VIF")
    ax.set_title("Multicolinealidad (VIF)", fontsize=14)
    ax.legend()
    fig.tight_layout()
    _mostrar(fig, nombre_figura)

    return vif.round(2)


def correlacion_parcial(df, objetivo, variables, controles_extra=()):
    """Correlación parcial de cada variable de `variables` con `objetivo`.

    La correlación parcial mide la relación entre dos variables después de quitar el efecto de otras
    (los controles). Se calcula así: se hace una regresión lineal de la variable y del objetivo contra
    los controles, y se correlacionan los residuos, es decir, la parte de cada una que los controles
    no explican.

    Para cada variable se calculan dos versiones:
    - controlando por las demás variables de `variables`;
    - controlando además por `controles_extra`.

    Devuelve una tabla con la correlación simple (Pearson) y las dos correlaciones parciales.
    """
    df = df[list(variables) + list(controles_extra) + [objetivo]].dropna().astype(float)

    def parcial(variable, controles):
        C = df[controles]
        residuo_variable = df[variable] - LinearRegression().fit(C, df[variable]).predict(C)
        residuo_objetivo = df[objetivo] - LinearRegression().fit(C, df[objetivo]).predict(C)
        return np.corrcoef(residuo_variable, residuo_objetivo)[0, 1]

    filas = []
    for variable in variables:
        otras = [v for v in variables if v != variable]
        filas.append({
            "variable": variable,
            "correlacion_simple": df[variable].corr(df[objetivo]),
            "parcial (controlando las otras)": parcial(variable, otras),
            "parcial (controlando las otras + extra)": parcial(variable, otras + list(controles_extra)),
        })
    return pd.DataFrame(filas).set_index("variable").round(3)


# ------------------------------------------------------------------------------------------------
# Calidad de datos
# ------------------------------------------------------------------------------------------------

def evaluar_completitud(df, columnas_positivas=(), textos_nulos=("", "nan", "na", "n/a", "null", "none", "?", "-")):
    """Cuenta los valores faltantes, incluyendo los nulos disfrazados.

    Se consideran nulos disfrazados:
    - En columnas de texto: cadenas vacías o valores como "NA", "null", "?" (sin importar mayúsculas ni espacios).
    - En `columnas_positivas`: valores menores o iguales a 0, que no tienen sentido físico.

    Devuelve el resumen por columna.
    """
    nulos = df.isna()

    disfrazados = pd.DataFrame(False, index=df.index, columns=df.columns)
    for col in df.select_dtypes(include=["object", "string"]).columns:
        disfrazados[col] = df[col].notna() & df[col].astype(str).str.strip().str.lower().isin(textos_nulos)
    for col in [c for c in columnas_positivas if c in df.columns]:
        disfrazados[col] = df[col] <= 0

    faltantes = nulos | disfrazados
    por_columna = pd.DataFrame({
        "nulos": nulos.sum(),
        "nulos_disfrazados": disfrazados.sum(),
        "total_faltantes": faltantes.sum(),
        "pct_faltantes": (100 * faltantes.mean()).round(3),
    })

    return por_columna


def evaluar_duplicidad(df, llave, caracteristicas, objetivo=None):
    """Resume los duplicados de un DataFrame en tres niveles.

    - Filas idénticas: todas las columnas iguales.
    - Duplicados por llave: la columna `llave` (identificador) se repite.
    - Duplicados por características: las columnas `caracteristicas` son iguales aunque cambie la llave.
      Si se indica `objetivo`, cuenta cuántos de esos grupos tienen valores distintos del objetivo.

    Devuelve la tabla resumen y los grupos duplicados por características (con los valores del objetivo).
    """
    dup_caracteristicas = df.duplicated(caracteristicas, keep=False)
    resumen = pd.DataFrame({
        "registros_sobrantes": [
            df.duplicated().sum(),
            df[llave].duplicated().sum(),
            df.duplicated(caracteristicas).sum(),
        ],
        "registros_involucrados": [
            df.duplicated(keep=False).sum(),
            df[llave].duplicated(keep=False).sum(),
            dup_caracteristicas.sum(),
        ],
    }, index=["Filas idénticas", f"Duplicados por llave ({llave})", "Duplicados por características"])
    resumen["pct_involucrados"] = (100 * resumen["registros_involucrados"] / len(df)).round(3)

    grupos = df[dup_caracteristicas].groupby(caracteristicas, dropna=False).size().to_frame("registros")
    if objetivo is not None:
        valores = df[dup_caracteristicas].groupby(caracteristicas, dropna=False)[objetivo].nunique()
        grupos["valores_distintos_objetivo"] = valores
        grupos = grupos.sort_values("valores_distintos_objetivo", ascending=False)

    return resumen, grupos.reset_index()


def evaluar_conformidad(df, reglas):
    """Verifica que cada columna cumpla el formato y el dominio esperados.

    `reglas` es un dict columna -> dict con cualquiera de estas claves:
    - "tipo": "entero", "decimal", "texto", "booleano" o "fecha".
    - "valores": lista de valores permitidos (para columnas categóricas).
    - "min" / "max": límites del rango permitido (inclusivos).
    - "decimales": número máximo de decimales.

    Devuelve una tabla con el número de registros que incumplen cada regla (los nulos no cuentan
    como incumplimiento: se miden en completitud).
    """
    tipos = {
        "entero": pd.api.types.is_integer_dtype,
        "decimal": pd.api.types.is_float_dtype,
        "texto": lambda s: pd.api.types.is_string_dtype(s) or pd.api.types.is_object_dtype(s),
        "booleano": pd.api.types.is_bool_dtype,
        "fecha": pd.api.types.is_datetime64_any_dtype,
    }
    filas = []
    for col, regla in reglas.items():
        serie = df[col]
        presentes = serie.notna()
        fila = {"columna": col, "tipo_esperado": regla.get("tipo"), "tipo_real": str(serie.dtype)}
        fila["cumple_tipo"] = tipos[regla["tipo"]](serie) if "tipo" in regla else None

        fuera_dominio = pd.Series(False, index=df.index)
        if "valores" in regla:
            fuera_dominio |= presentes & ~serie.isin(regla["valores"])
        if "min" in regla:
            fuera_dominio |= presentes & (serie < regla["min"])
        if "max" in regla:
            fuera_dominio |= presentes & (serie > regla["max"])
        fila["fuera_de_dominio"] = fuera_dominio.sum()

        if "decimales" in regla:
            escala = 10 ** regla["decimales"]
            fila["exceso_decimales"] = ((serie * escala - (serie * escala).round()).abs() > 1e-6).sum()
        else:
            fila["exceso_decimales"] = None

        filas.append(fila)

    return pd.DataFrame(filas).set_index("columna")


# ------------------------------------------------------------------------------------------------
# Referencias (líneas base que cualquier modelo debe superar)
# ------------------------------------------------------------------------------------------------

class TasaPorGrupo(ClassifierMixin, BaseEstimator):
    """Referencia: predice para cada cliente la tasa del objetivo de su grupo en el entrenamiento.

    Equivale a la `TasaHistorica` del reto de accidentalidad. Los grupos que no aparecen en el
    entrenamiento reciben la tasa global. Se usa dentro de la validación cruzada, así que en cada
    partición las tasas se calculan solo con su entrenamiento.
    """

    def __init__(self, columnas):
        self.columnas = columnas

    def fit(self, X, y):
        y = pd.Series(np.asarray(y, dtype=float), index=X.index)
        claves = self._claves(X)
        self.tasa_global_ = y.mean()
        self.tasas_ = y.groupby(claves).mean()
        self.classes_ = np.array([0, 1])
        return self

    def predict_proba(self, X):
        p = self._claves(X).map(self.tasas_).fillna(self.tasa_global_).to_numpy(dtype=float)
        return np.column_stack([1 - p, p])

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)

    def _claves(self, X):
        claves = X[self.columnas[0]].astype(str)
        for col in self.columnas[1:]:
            claves = claves + "|" + X[col].astype(str)
        return claves
