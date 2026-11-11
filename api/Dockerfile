# Imagen de la API de churn. Python 3.12 para que coincida con las versiones del entrenamiento del modelo.
FROM python:3.12-slim

WORKDIR /app

COPY api/requirements.txt api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt

# El paquete churn y el código de la API. El modelo NO va en la imagen: se monta al ejecutar el contenedor
# en /app/data/modelado/modelo_final (ver docs/03_api_despliegue.md).
COPY src/ src/
COPY api/ api/

ENV PYTHONPATH=/app/src
EXPOSE 8000

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
