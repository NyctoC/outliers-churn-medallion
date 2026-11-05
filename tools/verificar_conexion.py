"""Verifica la conexión a AWS del proyecto. Uso: python tools/verificar_conexion.py

Comprueba el archivo .env, que git lo ignore, las credenciales y una consulta a Athena (cuesta una fracción de
centavo). Nunca imprime las llaves. Guía completa: docs/02_conexion_aws.md
"""
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RUTA_ENV = RAIZ / ".env"
GUIA = "docs/02_conexion_aws.md"
VARIABLES = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION", "ATHENA_S3_OUTPUT"]
FILAS_ESPERADAS = 500_000

sys.path.insert(0, str(RAIZ / "src"))


def ok(mensaje):
    print(f"[OK]    {mensaje}")


def fallo(mensaje, solucion):
    print(f"[ERROR] {mensaje}\n        Qué hacer: {solucion}\n        Guía: {GUIA}")
    sys.exit(1)


def verificar_env():
    """El .env existe, tiene todas las variables y ya no tiene los valores de ejemplo."""
    from dotenv import dotenv_values

    if not RUTA_ENV.exists():
        fallo("No existe el archivo .env en la raíz del repo.", "Copia .env.example como .env y llena sus valores.")

    valores = dotenv_values(RUTA_ENV)
    faltantes = [v for v in VARIABLES if not valores.get(v)]
    if faltantes:
        fallo(f"Faltan valores en .env: {', '.join(faltantes)}.", "Compáralo con .env.example.")

    sin_llenar = [v for v in VARIABLES if "pon_aqui" in valores[v] or "nombre-del-bucket" in valores[v]]
    if sin_llenar:
        fallo(f"Siguen con el valor de ejemplo: {', '.join(sin_llenar)}.", "Reemplázalos por los valores reales.")

    salida = valores["ATHENA_S3_OUTPUT"]
    if not (salida.startswith("s3://") and salida.endswith("/")):
        fallo("ATHENA_S3_OUTPUT no tiene el formato esperado.", "Debe ser s3://<bucket>/athena-results/ (con / final).")
    ok(".env existe y tiene todas las variables.")
    return valores


def verificar_git():
    """El .env está ignorado por git y no quedó versionado."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True).returncode

    try:
        versionado = git("ls-files", "--error-unmatch", ".env") == 0
        ignorado = git("check-ignore", "-q", ".env") == 0
    except FileNotFoundError:
        print("[AVISO] No se encontró git: no se pudo comprobar que .env esté ignorado.")
        return
    if versionado:
        fallo("¡El archivo .env está versionado en git!",
              "Avisa al equipo, desactiva la llave en IAM y crea otra: borrar el archivo no la protege.")
    if not ignorado:
        fallo("Git no está ignorando el archivo .env.", "Restaura la línea .env en .gitignore antes de hacer commit.")
    ok("Git ignora el archivo .env.")


def verificar_credenciales():
    """AWS reconoce las llaves. Si son las del usuario root, lo advierte."""
    from churn.data import _sesion  # primero: activa la validación de certificados del sistema

    from botocore.exceptions import BotoCoreError, ClientError

    try:
        identidad = _sesion().client("sts").get_caller_identity()
    except ClientError as error:
        fallo(f"AWS rechazó las credenciales ({error.response['Error']['Code']}).",
              "Revisa que las dos llaves estén completas, sin espacios ni comillas, y que la llave siga activa.")
    except BotoCoreError as error:
        fallo(f"No se pudo contactar a AWS ({type(error).__name__}).", "Revisa tu conexión a internet y la región.")

    if identidad["Arn"].endswith(":root"):
        print("[AVISO] Son llaves del usuario root: tienen control total de la cuenta. "
              f"Protégelas y desactívalas al terminar el proyecto (ver {GUIA}).")
    ok(f"Credenciales válidas: {identidad['Arn']}")


def verificar_athena(valores):
    """Athena responde y customer_360 tiene las filas esperadas."""
    import awswrangler as wr

    from churn.data import BASE_ORO, _sesion

    try:
        resultado = wr.athena.read_sql_query(
            "SELECT count(*) AS filas FROM customer_360", database=BASE_ORO, ctas_approach=False,
            s3_output=valores["ATHENA_S3_OUTPUT"], boto3_session=_sesion(),
        )
    except Exception as error:
        detalle = str(error).replace(valores["AWS_SECRET_ACCESS_KEY"], "***")[:500]
        fallo(f"La consulta a Athena falló ({type(error).__name__}): {detalle}",
              "Si dice AccessDenied, revisa la política del usuario IAM; si no encuentra la tabla o el bucket, "
              "revisa ATHENA_S3_OUTPUT y la región.")

    filas = int(resultado["filas"].iloc[0])
    if filas != FILAS_ESPERADAS:
        fallo(f"customer_360 tiene {filas:,} filas y se esperaban {FILAS_ESPERADAS:,}.",
              "La conexión funciona, pero revisa con quien administra el data lake si la tabla está completa.")
    ok(f"Athena responde: customer_360 tiene {filas:,} filas.")


def main():
    try:
        valores = verificar_env()
        verificar_git()
        verificar_credenciales()
        verificar_athena(valores)
    except ModuleNotFoundError as error:
        fallo(f"Falta la librería {error.name}.", "Activa el ambiente y ejecuta: pip install -r requirements.txt")
    print("\nConexión lista. Ya puedes ejecutar los notebooks.")


if __name__ == "__main__":
    main()
