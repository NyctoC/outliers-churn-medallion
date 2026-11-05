# Conexión a AWS desde Python

Para ejecutar los notebooks, Python necesita credenciales para leer las tablas de Athena. El equipo comparte unas
mismas llaves y cada integrante las guarda en un archivo `.env` local, que git ignora. No hace falta instalar el
AWS CLI ni ejecutar `aws configure`.

- **Si vas a conectarte:** sigue la parte 1.
- **Si administras la cuenta y quieres cambiar a llaves de solo lectura:** sigue la parte 2 (una sola vez).

## Parte 1 · Conectarte (cada integrante, 5 minutos)

Necesitas Git, Python 3.11 o superior, y estos dos datos del administrador: las llaves compartidas y el nombre del
bucket.

**1. Clona el repo fuera de OneDrive, Dropbox o Google Drive.** Si no, el `.env` con las llaves y las cachés de
datos se sincronizarían a la nube. Por ejemplo, en `C:\Ambientes`:

```powershell
git clone https://github.com/NyctoC/outliers-churn-medallion.git
cd outliers-churn-medallion
```

**2. Crea el ambiente e instala las dependencias.** Ejecútalo en la terminal de VS Code (**Terminal → New Terminal**):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Si PowerShell bloquea la activación, ejecuta primero
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y vuelve a intentarlo. En macOS o Linux, activa con
`source .venv/bin/activate`.

**3. Crea tu archivo `.env` a partir de la plantilla:**

```powershell
Copy-Item .env.example .env
```

En macOS o Linux: `cp .env.example .env`.

**4. Abre `.env` y reemplaza los valores**, sin comillas ni espacios alrededor del `=`:

```ini
AWS_ACCESS_KEY_ID=<access key compartida>
AWS_SECRET_ACCESS_KEY=<secret key compartida>
AWS_DEFAULT_REGION=us-east-1
ATHENA_S3_OUTPUT=s3://<nombre-del-bucket>/athena-results/
```

Edita `.env`, **no** `.env.example`: la plantilla sí se sube al repo.

**5. Verifica la conexión:**

```powershell
python tools/verificar_conexion.py
```

Debe terminar con `Conexión lista` y mostrar 500.000 filas en `customer_360`. Si algo falla, el script indica qué
revisar. Si las llaves son del usuario root, muestra un aviso (ver "Cuidados con la llave compartida"), pero
continúa. Después ya puedes abrir los notebooks con el kernel de `.venv`.

### Errores frecuentes

| Mensaje | Causa probable | Solución |
|---|---|---|
| `CERTIFICATE_VERIFY_FAILED` en `pip install` | El antivirus (por ejemplo, Norton) inspecciona las conexiones | `pip install --use-feature=truststore -r requirements.txt`. No uses `--trusted-host`: desactiva la verificación |
| `Falta la librería ...` | El ambiente no está activo | Actívalo y repite `pip install -r requirements.txt` |
| `AWS rechazó las credenciales` | Llave incompleta, con espacios o desactivada | Vuelve a copiarla; si persiste, pregunta si se cambió la llave |
| `AccessDenied` en Athena | La política no cubre el bucket o la base | Avisa al administrador |
| No encuentra la tabla o la base | Región distinta de `us-east-1` | Corrige `AWS_DEFAULT_REGION` |
| `Unable to verify output location` | Bucket mal escrito en `ATHENA_S3_OUTPUT` | Corrígelo y conserva `/athena-results/` |

## Parte 2 · Crear un usuario de solo lectura (administrador, una sola vez)

Es la opción más segura y reemplaza las llaves del usuario root. Se hace en la consola web de AWS. El resto del
equipo solo tendría que cambiar las dos llaves en su `.env`.

**1. Crea el usuario.** En **IAM → Users → Create user**, llámalo `outliers-equipo`. **No** actives el acceso a la
consola.

**2. Asígnale la política.** En **Permissions → Add permissions → Create inline policy → JSON**, pega esto y reemplaza
`NOMBRE-DEL-BUCKET` en los tres lugares donde aparece:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EjecutarConsultas",
      "Effect": "Allow",
      "Action": [
        "athena:StartQueryExecution",
        "athena:StopQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:GetWorkGroup",
        "athena:GetDataCatalog"
      ],
      "Resource": "*"
    },
    {
      "Sid": "LeerCatalogo",
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase",
        "glue:GetDatabases",
        "glue:GetTable",
        "glue:GetTables",
        "glue:GetPartition",
        "glue:GetPartitions"
      ],
      "Resource": "*"
    },
    {
      "Sid": "LeerBucket",
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": "arn:aws:s3:::NOMBRE-DEL-BUCKET"
    },
    {
      "Sid": "LeerDatos",
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::NOMBRE-DEL-BUCKET/*"
    },
    {
      "Sid": "EscribirResultadosDeAthena",
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"],
      "Resource": "arn:aws:s3:::NOMBRE-DEL-BUCKET/athena-results/*"
    }
  ]
}
```

Con esta política se pueden consultar las tablas, pero no modificarlas ni borrarlas. Athena solo necesita escribir en
`athena-results/`, donde guarda los resultados de cada consulta.

**3. Crea la llave.** En el usuario, ve a **Security credentials → Create access key → Application running outside
AWS**. La secret key solo se muestra esa vez.

**4. Comparte las llaves con el equipo** por un mensaje privado, no en el canal de Teams, en el repo ni en un
documento compartido. Borra el mensaje cuando todos las hayan copiado.

**5. Prueba la conexión** con la parte 1 antes de avisarle al equipo.

Si alguien necesita más permisos, por ejemplo para desplegar la API, agrega solo los que hagan falta. No uses
`AdministratorAccess` en este usuario: todo el equipo tiene sus llaves.

## Cuidados con la llave compartida

- **Nunca** pongas las llaves en notebooks, código, capturas de pantalla o la presentación. Tampoco imprimas
  `os.environ` en un notebook, porque las salidas también se suben al repo.
- **Las llaves del usuario root tienen control total de la cuenta y AWS desaconseja usarlas:** con ellas se puede
  borrar el data lake, generar cobros en la tarjeta o cerrar la cuenta, y no se les pueden limitar los permisos. Si
  el equipo las usa, compártanlas solo por mensaje privado, mantengan activa una alerta de presupuesto en **Billing**
  y **elimínenlas al terminar el proyecto** en **Security credentials**.
- Antes de cada commit, revisa con `git status` que `.env` no aparezca.

### Si una llave se expone

Actúa de inmediato, aunque ya hayas borrado el archivo o el commit, porque el historial de git y los bots que
rastrean GitHub pueden conservarla:

1. Desactiva la llave y crea una nueva:
   - **Si son llaves del usuario root:** entra con el usuario root a **Security credentials** (menú con el nombre de la
     cuenta, arriba a la derecha) y hazlo en **Access keys**.
   - **Si usan el usuario de solo lectura:** ve a **IAM → Users → `outliers-equipo` → Security credentials**.
2. Comparte la nueva con el equipo por mensaje privado. **Todos** deben actualizar su `.env`.
3. Revisa en **Billing** que no haya cobros inesperados y borra la llave vieja.
