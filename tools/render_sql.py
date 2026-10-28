#!/usr/bin/env python3
"""
Copia sql/ a sql_rendered/ reemplazando YOUR_BUCKET por el nombre real de tu bucket.
sql_rendered/ está en .gitignore: así el repo conserva el placeholder y cada integrante
puede ejecutar los scripts con su propio bucket.

Uso:
    python tools/render_sql.py --bucket outliers-churn-medallion-abc123
"""
import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

parser = argparse.ArgumentParser()
parser.add_argument("--bucket", required=True, help="nombre del bucket S3 (sin s3://)")
args = parser.parse_args()

if "/" in args.bucket or args.bucket.startswith("s3:"):
    raise SystemExit("Pasa solo el nombre del bucket, p. ej. outliers-churn-medallion-abc123")

out = ROOT / "sql_rendered"
if out.exists():
    shutil.rmtree(out)
for f in sorted((ROOT / "sql").rglob("*.sql")):
    dest = out / f.relative_to(ROOT / "sql")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(f.read_text(encoding="utf-8").replace("YOUR_BUCKET", args.bucket), encoding="utf-8")
    print("  ", dest.relative_to(ROOT))
print(f"\nListo: ejecuta los scripts de sql_rendered/ en Athena (bucket: {args.bucket}).")
