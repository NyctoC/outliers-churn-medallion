"""Modelo final de churn (EBM): carga desde AWS, predicción, priorización, explicaciones y contrafactuales.

Reúne lo decidido en 02_modelado.ipynb y 03_xai.ipynb (bitácora en docs/modelado_decisiones.md) para que la API y
el tablero usen exactamente lo mismo que los notebooks:

- Los clientes se leen de `churn_gold.customer_360` con Athena y pasan por el pipeline de limpieza del EDA.
- El modelo y su configuración se descargan de S3 (`modelado/modelo_final/`) a `data/modelado/modelo_final/`.
- El modelo usa las 4 variables de `features.VARIABLES_MODELO_FINAL`.

Uso:
    from churn import modelos
    modelo, configuracion = modelos.cargar_modelo_final()
    clientes = modelos.cargar_clientes()
    predicciones = modelos.predecir(modelo, clientes)
    explicacion = modelos.explicar_cliente(modelo, clientes.iloc[[0]])
    contrafactuales = modelos.contrafactuales(modelo, clientes.iloc[[0]])
"""
import json

import joblib
import numpy as np
import pandas as pd
from interpret.glassbox import ExplainableBoostingClassifier
from sklearn.pipeline import make_pipeline

from . import data, features

SUBCARPETA_MODELO = "modelo_final"
DIR_MODELO = data.DIR_MODELADO / SUBCARPETA_MODELO
RUTA_MODELO = DIR_MODELO / "modelo.joblib"
RUTA_CONFIGURACION = DIR_MODELO / "configuracion.json"

VARIABLES = features.VARIABLES_MODELO_FINAL
UMBRAL = 0.5   # el que aplica el EBM por defecto (sección 4 de 03_xai)

# Variables que se mueven en los contrafactuales. total_spent se recalcula como pedidos x valor promedio (sección 5.1)
VARIABLES_MOVIBLES = ["summary_total_orders", "average_order_value", "total_returns"]
PASOS_CONTINUOS = 120   # puntos de la rejilla de average_order_value, como en 03_xai

# Campaña sugerida según el término que más riesgo le suma al cliente (sección 8 de 03_xai)
REACTIVACION = "Reactivación: incentivo para la siguiente compra (descuento, envío gratis o recordatorio de recompra)"
POSVENTA = "Atención posventa: contacto de servicio, revisión de las devoluciones y opción de cambio"
CAMPANAS = {
    "summary_total_orders": REACTIVACION,
    "total_spent": REACTIVACION,
    "total_returns": POSVENTA,
    "summary_total_orders & total_returns": POSVENTA,
    "average_order_value": None,   # casi nunca es el motivo principal, no tiene campaña propia
}


# ---------------------------------------------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------------------------------------------

def crear_modelo_final(hiperparametros):
    """Pipeline sin entrenar con la misma estructura del modelo guardado: el EBM no transforma las variables."""
    ebm = ExplainableBoostingClassifier(n_jobs=-1, random_state=data.SEMILLA, **hiperparametros)
    return make_pipeline("passthrough", ebm)


def entrenar_modelo_final(train, hiperparametros):
    """Entrena el modelo final con todo `train`, como en la sección 8 de 02_modelado. Nunca con `test`."""
    return crear_modelo_final(hiperparametros).fit(preparar_variables(train), train[features.OBJETIVO].astype(int))


def cargar_modelo_final(refrescar=False):
    """Descarga de S3 el modelo final y su configuración (si no están en local o si `refrescar`) y los carga.

    Comprueba que las variables guardadas coincidan con `features.VARIABLES_MODELO_FINAL`.
    Devuelve el pipeline y el diccionario de configuración.
    """
    if refrescar or not (RUTA_MODELO.exists() and RUTA_CONFIGURACION.exists()):
        data.descargar_modelado(refrescar=refrescar, subcarpeta=SUBCARPETA_MODELO)
    modelo = joblib.load(RUTA_MODELO)
    configuracion = json.loads(RUTA_CONFIGURACION.read_text(encoding="utf-8"))
    if configuracion["variables"] != VARIABLES:
        raise ValueError(f"El modelo guardado usa {configuracion['variables']}, pero "
                         f"features.VARIABLES_MODELO_FINAL es {VARIABLES}")
    return modelo, configuracion


def _ebm(modelo):
    """El EBM dentro del pipeline (o el propio EBM si se pasa directamente)."""
    return modelo[-1] if hasattr(modelo, "steps") else modelo


# ---------------------------------------------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------------------------------------------

def cargar_clientes(refrescar=False, customer_ids=None):
    """Clientes de `customer_360` (Athena, con la caché de `data/`) con el pipeline de limpieza del EDA aplicado.

    Con `refrescar` se vuelve a consultar Athena. Con `customer_ids` se devuelven solo esos clientes.
    """
    c360 = data.normalizar_tipos(data.cargar_customer_360(refrescar=refrescar), features.COLUMNAS_FECHA)
    limpio = features.crear_pipeline_limpieza().fit_transform(c360)
    if customer_ids is not None:
        limpio = limpio[limpio[features.LLAVE].isin(list(customer_ids))]
    return limpio.reset_index(drop=True)


def preparar_variables(clientes):
    """Las 4 variables del modelo como float, en el orden con el que se entrenó. Falla si falta alguna o hay nulos."""
    if isinstance(clientes, pd.Series):
        clientes = clientes.to_frame().T
    faltantes = [v for v in VARIABLES if v not in clientes.columns]
    if faltantes:
        raise KeyError(f"Faltan las variables del modelo: {faltantes}")
    X = clientes[VARIABLES].astype(float)
    if X.isna().any().any():
        raise ValueError(f"Hay nulos en las variables del modelo: {X.columns[X.isna().any()].tolist()}")
    return X


# ---------------------------------------------------------------------------------------------------------------
# Predicción y priorización
# ---------------------------------------------------------------------------------------------------------------

def predecir(modelo, clientes, umbral=UMBRAL):
    """Probabilidad de churn y clasificación con `umbral` de cada cliente.

    Si `clientes` trae `customer_id`, se incluye en el resultado.
    """
    probabilidad = modelo.predict_proba(preparar_variables(clientes))[:, 1]
    resultado = pd.DataFrame({"probabilidad": probabilidad, "churn_predicho": (probabilidad >= umbral).astype(int)},
                             index=clientes.index)
    if features.LLAVE in clientes.columns:
        resultado.insert(0, features.LLAVE, clientes[features.LLAVE].to_numpy())
    return resultado.reset_index(drop=True)


def priorizar(predicciones, porcentaje=None):
    """Ordena los clientes de mayor a menor probabilidad de churn (decisión 22 de docs/modelado_decisiones.md).

    Agrega `prioridad` (1 = mayor riesgo). Con `porcentaje` devuelve solo ese porcentaje de clientes de mayor riesgo.
    """
    ordenadas = predicciones.sort_values("probabilidad", ascending=False, kind="stable").reset_index(drop=True)
    ordenadas.insert(0, "prioridad", np.arange(1, len(ordenadas) + 1))
    if porcentaje is not None:
        ordenadas = ordenadas.head(int(np.ceil(len(ordenadas) * porcentaje / 100)))
    return ordenadas


# ---------------------------------------------------------------------------------------------------------------
# Explicaciones del EBM
# ---------------------------------------------------------------------------------------------------------------

def contribuciones(modelo, clientes):
    """Contribución (log-odds) de cada término del EBM para cada cliente, una columna por término."""
    ebm = _ebm(modelo)
    return pd.DataFrame(ebm.eval_terms(preparar_variables(clientes)), columns=ebm.term_names_, index=clientes.index)


def explicar_clientes(modelo, clientes, umbral=UMBRAL):
    """Explicación resumida de varios clientes: probabilidad, clasificación, motivo principal y campaña sugerida.

    El motivo principal es el término que más le suma riesgo al cliente. Si ninguno suma, queda vacío.
    Las columnas `contribucion_<término>` traen el aporte de cada término al log-odds.
    """
    aportes = contribuciones(modelo, clientes)
    intercepto = float(np.ravel(_ebm(modelo).intercept_)[0])
    log_odds = intercepto + aportes.sum(axis=1)
    probabilidad = 1 / (1 + np.exp(-log_odds))
    motivo = aportes.idxmax(axis=1).where(aportes.max(axis=1) > 0)

    resultado = pd.DataFrame({"probabilidad": probabilidad, "churn_predicho": (probabilidad >= umbral).astype(int),
                              "motivo_principal": motivo, "campana_sugerida": motivo.map(CAMPANAS)})
    resultado = resultado.join(aportes.add_prefix("contribucion_"))
    if features.LLAVE in clientes.columns:
        resultado.insert(0, features.LLAVE, clientes[features.LLAVE].to_numpy())
    return resultado.reset_index(drop=True)


def explicar_cliente(modelo, cliente, umbral=UMBRAL):
    """Por qué el modelo clasifica así a un cliente (sección 4 de 03_xai).

    `cliente` es un DataFrame de una fila o una Series. Devuelve un diccionario con el intercepto, la contribución
    de cada término ordenada por magnitud, el log-odds, la probabilidad, la clasificación, el motivo principal y la
    campaña sugerida. Comprueba que la suma de los términos reproduzca la probabilidad del modelo.
    """
    cliente = _una_fila(cliente)
    aportes = contribuciones(modelo, cliente).iloc[0]
    intercepto = float(np.ravel(_ebm(modelo).intercept_)[0])
    log_odds = intercepto + aportes.sum()
    probabilidad = float(1 / (1 + np.exp(-log_odds)))
    probabilidad_modelo = float(modelo.predict_proba(preparar_variables(cliente))[0, 1])
    if not np.isclose(probabilidad, probabilidad_modelo, atol=1e-9):
        raise RuntimeError(f"La suma de los términos ({probabilidad}) no reproduce la probabilidad del modelo "
                           f"({probabilidad_modelo})")

    motivo = aportes.idxmax() if aportes.max() > 0 else None
    return {
        "valores": preparar_variables(cliente).iloc[0].to_dict(),
        "intercepto": intercepto,
        "contribuciones": aportes.sort_values(key=np.abs, ascending=False).to_dict(),
        "log_odds": float(log_odds),
        "probabilidad": probabilidad_modelo,
        "umbral": umbral,
        "churn_predicho": int(probabilidad_modelo >= umbral),
        "empujan_a_churn": [t for t, v in aportes.sort_values(ascending=False).items() if v > 0],
        "empujan_a_no_churn": [t for t, v in aportes.sort_values().items() if v < 0],
        "motivo_principal": motivo,
        "campana_sugerida": CAMPANAS.get(motivo),
    }


def _una_fila(cliente):
    if isinstance(cliente, pd.Series):
        cliente = cliente.to_frame().T
    if len(cliente) != 1:
        raise ValueError(f"Se esperaba un solo cliente y llegaron {len(cliente)}")
    return cliente.reset_index(drop=True)


# ---------------------------------------------------------------------------------------------------------------
# Contrafactuales (sección 5 de 03_xai)
# ---------------------------------------------------------------------------------------------------------------

def rejillas_contrafactuales(modelo, pasos_continuos=PASOS_CONTINUOS):
    """Valores que puede tomar cada variable movible, dentro del rango observado en el entrenamiento.

    Los rangos salen del propio EBM (`feature_bounds_`), así no hace falta cargar `train`. Pedidos y devoluciones se
    mueven de uno en uno y `average_order_value` en `pasos_continuos` puntos.
    """
    ebm = _ebm(modelo)
    limites = dict(zip(ebm.feature_names_in_, ebm.feature_bounds_))
    rejillas = {}
    for variable in VARIABLES_MOVIBLES:
        minimo, maximo = limites[variable]
        if variable == "average_order_value":
            rejillas[variable] = np.linspace(minimo, maximo, pasos_continuos)
        else:
            rejillas[variable] = np.arange(minimo, maximo + 1)
    return rejillas


def generar_variantes(cliente, **valores):
    """Una fila por cada combinación de `valores`, con el resto de variables del cliente fijas.

    `total_spent` se recalcula para seguir siendo pedidos x valor promedio, y se descartan las combinaciones con más
    devoluciones que pedidos. Devuelve la rejilla de valores y las filas listas para el modelo.
    """
    cliente = preparar_variables(_una_fila(cliente))
    rejilla = pd.MultiIndex.from_product(list(valores.values()), names=list(valores)).to_frame(index=False)
    filas = cliente.loc[cliente.index.repeat(len(rejilla))].reset_index(drop=True)
    for variable in valores:
        filas[variable] = rejilla[variable].astype(float).to_numpy()
    filas["total_spent"] = (cliente["total_spent"].iloc[0]
                            * filas["summary_total_orders"] / cliente["summary_total_orders"].iloc[0]
                            * filas["average_order_value"] / cliente["average_order_value"].iloc[0])
    validas = filas["total_returns"] <= filas["summary_total_orders"]
    return rejilla[validas].reset_index(drop=True), filas.loc[validas, VARIABLES].reset_index(drop=True)


def contrafactual_una_variable(modelo, cliente, umbral=UMBRAL, rejillas=None):
    """Mueve una variable a la vez y busca el valor más cercano al actual con el que la probabilidad baja de `umbral`.

    Devuelve una fila por variable con el valor actual, el valor más cercano bajo el umbral (vacío si ninguno lo
    logra), el cambio necesario, la probabilidad con ese valor, la mínima alcanzable y el rango de probabilidad.
    """
    cliente = _una_fila(cliente)
    rejillas = rejillas or rejillas_contrafactuales(modelo)
    filas_resumen = []
    for variable in VARIABLES_MOVIBLES:
        rejilla, filas = generar_variantes(cliente, **{variable: rejillas[variable]})
        probabilidad = modelo.predict_proba(filas)[:, 1]
        actual = float(cliente[variable].iloc[0])
        debajo = np.flatnonzero(probabilidad < umbral)
        if len(debajo):
            mejor = debajo[np.abs(rejilla[variable].to_numpy()[debajo] - actual).argmin()]
            valor, probabilidad_valor = float(rejilla[variable].iloc[mejor]), float(probabilidad[mejor])
        else:
            valor = probabilidad_valor = np.nan
        filas_resumen.append({"variable": variable, "valor_actual": actual, "valor_bajo_umbral": valor,
                              "cambio_necesario": valor - actual, "probabilidad_con_cambio": probabilidad_valor,
                              "probabilidad_minima": float(probabilidad.min()),
                              "rango_probabilidad": float(np.ptp(probabilidad))})
    return pd.DataFrame(filas_resumen).set_index("variable")


def contrafactual_dos_variables(modelo, cliente, variables=None, umbral=UMBRAL, rejillas=None):
    """Mueve dos variables a la vez y busca la combinación bajo `umbral` más cercana al cliente.

    Por defecto usa las dos variables con mayor rango de probabilidad en `contrafactual_una_variable`. La distancia
    suma el cambio de cada variable como fracción de su rango. Devuelve un diccionario con la combinación, o None
    si ninguna baja del umbral, y la rejilla completa con la probabilidad de cada combinación.
    """
    cliente = _una_fila(cliente)
    rejillas = rejillas or rejillas_contrafactuales(modelo)
    if variables is None:
        una = contrafactual_una_variable(modelo, cliente, umbral, rejillas)
        variables = una["rango_probabilidad"].sort_values(ascending=False).index[:2].tolist()
    variable_x, variable_y = variables

    rejilla, filas = generar_variantes(cliente, **{variable_x: rejillas[variable_x], variable_y: rejillas[variable_y]})
    rejilla["probabilidad"] = modelo.predict_proba(filas)[:, 1]
    distancia = sum((rejilla[v] - float(cliente[v].iloc[0])).abs() / np.ptp(rejillas[v]) for v in variables)
    debajo = rejilla["probabilidad"] < umbral

    combinacion = None
    if debajo.any():
        mejor = rejilla.loc[distancia[debajo].idxmin()]
        combinacion = {"probabilidad": float(mejor["probabilidad"]),
                       **{v: {"valor_actual": float(cliente[v].iloc[0]), "valor_propuesto": float(mejor[v])}
                          for v in variables}}
    return {"variables": variables, "combinacion_mas_cercana": combinacion, "rejilla": rejilla}


def contrafactuales(modelo, cliente, umbral=UMBRAL):
    """Qué tendría que cambiar el cliente para quedar por debajo de `umbral`, con una y con dos variables.

    Si el cliente ya está por debajo, lo indica y no busca cambios. La meta de la campaña es el cambio más pequeño
    (sección 8 de 03_xai). Los contrafactuales describen al modelo y no garantizan que el cliente se quede.
    """
    cliente = _una_fila(cliente)
    probabilidad = float(modelo.predict_proba(preparar_variables(cliente))[0, 1])
    if probabilidad < umbral:
        return {"probabilidad_actual": probabilidad, "bajo_umbral": True, "una_variable": None,
                "dos_variables": None, "meta": None}

    rejillas = rejillas_contrafactuales(modelo)
    una = contrafactual_una_variable(modelo, cliente, umbral, rejillas)
    dos = contrafactual_dos_variables(modelo, cliente, umbral=umbral, rejillas=rejillas)

    # Meta: el cambio de una sola variable que menos se aleja del valor actual, medido como fracción de su rango
    posibles = una.dropna(subset=["valor_bajo_umbral"])
    meta = None
    if len(posibles):
        relativo = posibles["cambio_necesario"].abs() / pd.Series({v: np.ptp(rejillas[v]) for v in posibles.index})
        variable = relativo.idxmin()
        meta = {"variable": variable, "valor_actual": float(posibles.loc[variable, "valor_actual"]),
                "valor_propuesto": float(posibles.loc[variable, "valor_bajo_umbral"]),
                "probabilidad_con_cambio": float(posibles.loc[variable, "probabilidad_con_cambio"])}
    return {"probabilidad_actual": probabilidad, "bajo_umbral": False, "una_variable": una,
            "dos_variables": {k: v for k, v in dos.items() if k != "rejilla"}, "meta": meta}
