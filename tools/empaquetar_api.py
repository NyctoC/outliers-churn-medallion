"""Empaqueta el código de la API (api/, src/churn/ y .dockerignore) en un zip y, opcionalmente, lo sube a S3.

El repo es privado, así que la instancia EC2 no puede clonarlo sin credenciales de GitHub. En su lugar descarga este
zip de S3 con su rol IAM. El zip no lleva el modelo, el .env ni datos.

Uso (desde la raíz del repo, con el entorno activo):
    python tools/empaquetar_api.py            # solo crea data/churn-api.zip
    python tools/empaquetar_api.py --subir    # además lo sube a s3://<bucket>/despliegue/churn-api.zip
"""
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

ARCHIVOS = [".dockerignore", *sorted(p.relative_to(RAIZ).as_posix() for p in (RAIZ / "api").glob("*")
                                     if p.is_file()),
            *sorted(p.relative_to(RAIZ).as_posix() for p in (RAIZ / "src" / "churn").glob("*.py"))]
CLAVE_S3 = "despliegue/churn-api.zip"


def crear_zip():
    destino = RAIZ / "data" / "churn-api.zip"
    destino.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for archivo in ARCHIVOS:
            z.write(RAIZ / archivo, archivo)   # rutas con "/", que es lo que espera Linux
    return destino


if __name__ == "__main__":
    zip_local = crear_zip()
    with zipfile.ZipFile(zip_local) as z:
        print(f"{zip_local} ({zip_local.stat().st_size / 1024:.0f} KB) con {len(z.namelist())} archivos:")
        for nombre in z.namelist():
            print("  ", nombre)
    if "--subir" in sys.argv:
        from churn import data   # activa truststore; boto3 se importa después

        bucket = data._bucket()
        data._sesion().client("s3").upload_file(str(zip_local), bucket, CLAVE_S3)
        print(f"subido a s3://{bucket}/{CLAVE_S3}")
