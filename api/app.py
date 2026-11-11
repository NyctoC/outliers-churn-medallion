"""API de churn de The Outliers: usa churn.modelos, el mismo código de 02_modelado y 03_xai.

El modelo (EBM con 4 variables) se carga una sola vez al iniciar. Si existe una tabla de predicciones en
`data/churn_predicciones.parquet`, también se carga para responder la búsqueda por customer_id.

Para correrla en local, desde la raíz del repo y con el entorno activo:
    uvicorn api.app:app --reload
"""
import math
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

from churn import data, modelos

MAX_LOTE = 1000
# Rangos observados en el entrenamiento: fuera de ellos el EBM repite el valor del extremo (sin extrapolar)
RANGOS = {
    "summary_total_orders": (1, 120),
    "total_returns": (0, 10),
    "average_order_value": (500.12, 11999.99),
    "total_spent": (502.27, 1439544),
}
# Tabla con una fila por cliente, para buscar por customer_id sin consultar Athena en cada petición (opcional)
RUTA_PREDICCIONES = Path(os.environ.get("RUTA_PREDICCIONES", data.DIR_DATOS / "churn_predicciones.parquet"))

ESTADO = {"modelo": None, "configuracion": None, "predicciones": None}


@asynccontextmanager
async def ciclo_de_vida(app):
    # El modelo se carga una sola vez, al iniciar la API, no en cada petición
    ESTADO["modelo"], ESTADO["configuracion"] = modelos.cargar_modelo_final()
    if RUTA_PREDICCIONES.exists():
        ESTADO["predicciones"] = pd.read_parquet(RUTA_PREDICCIONES).set_index("customer_id")
    yield


app = FastAPI(
    title="API de churn - The Outliers",
    version="1.0",
    lifespan=ciclo_de_vida,
    description="Probabilidad de abandono, explicación y contrafactuales (modelo EBM, 4 variables de customer_summary).",
)


class Cliente(BaseModel):
    customer_id: int | None = None
    summary_total_orders: float = Field(gt=0, examples=[60])
    total_spent: float = Field(ge=0, examples=[377662])
    average_order_value: float = Field(gt=0, examples=[6243])
    total_returns: float = Field(ge=0, examples=[5])

    @model_validator(mode="after")
    def coherente(self):
        if self.total_returns > self.summary_total_orders:
            raise ValueError("total_returns no puede ser mayor que summary_total_orders")
        return self

    def advertencias(self):
        """Avisos no bloqueantes: valores fuera del rango de entrenamiento o gasto que no cuadra con pedidos x valor."""
        avisos = []
        for variable, (minimo, maximo) in RANGOS.items():
            valor = getattr(self, variable)
            if not minimo <= valor <= maximo:
                avisos.append(f"{variable}={valor} esta fuera del rango de entrenamiento ({minimo} a {maximo})")
        esperado = self.summary_total_orders * self.average_order_value
        if not math.isclose(self.total_spent, esperado, rel_tol=0.01):
            avisos.append(f"total_spent={self.total_spent} no coincide con summary_total_orders x "
                          f"average_order_value ({esperado:.2f})")
        return avisos


def fila(cliente):
    """DataFrame de una fila con las 4 variables del modelo, en el orden con el que se entrenó."""
    return pd.DataFrame([{v: getattr(cliente, v) for v in modelos.VARIABLES}])


def a_json(valor):
    """Convierte DataFrames, tipos de numpy y NaN/NA a algo que JSON admita (NaN e infinitos pasan a null)."""
    if isinstance(valor, pd.DataFrame):
        return a_json(valor.reset_index().to_dict("records"))
    if isinstance(valor, dict):
        return {str(k): a_json(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [a_json(v) for v in valor]
    if isinstance(valor, np.generic):
        valor = valor.item()
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(valor, float) and not math.isfinite(valor):
        return None
    return valor


@app.get("/salud")
def salud():
    cfg = ESTADO["configuracion"]
    return {"estado": "ok", "modelo": cfg["modelo"], "variables": cfg["variables"],
            "umbral": modelos.UMBRAL, "metricas": cfg["metricas"],
            "busqueda_por_customer_id": ESTADO["predicciones"] is not None}


@app.get("/modelo")
def modelo():
    cfg = ESTADO["configuracion"]
    return {k: cfg[k] for k in ["modelo", "escenario", "variables", "variables_retiradas_por_fuga",
                                "hiperparametros", "metricas", "versiones"]}


@app.post("/predecir")
def predecir(clientes: list[Cliente]):
    if not 1 <= len(clientes) <= MAX_LOTE:
        raise HTTPException(422, f"Envia entre 1 y {MAX_LOTE} clientes")
    X = pd.concat([fila(c) for c in clientes], ignore_index=True)
    registros = a_json(modelos.predecir(ESTADO["modelo"], X).to_dict("records"))
    for registro, cliente in zip(registros, clientes):
        registro["customer_id"] = cliente.customer_id
        registro["advertencias"] = cliente.advertencias()
    return registros


@app.post("/explicar")
def explicar(cliente: Cliente):
    explicacion = modelos.explicar_cliente(ESTADO["modelo"], fila(cliente))
    return a_json({"customer_id": cliente.customer_id, **explicacion, "advertencias": cliente.advertencias()})


@app.post("/contrafactuales")
def contrafactuales(cliente: Cliente):
    resultado = modelos.contrafactuales(ESTADO["modelo"], fila(cliente))
    return a_json({"customer_id": cliente.customer_id, **resultado, "advertencias": cliente.advertencias()})


@app.get("/clientes/{customer_id}")
def buscar_cliente(customer_id: int):
    """Predicción ya calculada de un cliente existente (lee la tabla cargada, no consulta Athena)."""
    if ESTADO["predicciones"] is None:
        raise HTTPException(503, "Esta API no tiene cargada la tabla de predicciones")
    if customer_id not in ESTADO["predicciones"].index:
        raise HTTPException(404, f"No existe el cliente {customer_id}")
    return a_json({"customer_id": customer_id, **ESTADO["predicciones"].loc[customer_id].to_dict()})
