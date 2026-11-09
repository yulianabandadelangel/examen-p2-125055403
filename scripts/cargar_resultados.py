#!/usr/bin/env python3
"""
Carga la salida del job (part-00000) en PostgreSQL.

Formato de cada línea:  tienda \t ticket_promedio \t num_ventas \t ingreso_total

Uso (desde el host):
  docker compose exec api python /opt/scripts/cargar_resultados.py
  docker compose exec api python /opt/scripts/cargar_resultados.py --archivo /data/output/resultado/part-00000 --reemplazar
"""
import argparse
import os
import sys
import time

import psycopg2
from psycopg2.extras import execute_values

TABLA = "resultados_ticket"
DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLA} (
    tienda           VARCHAR(10) PRIMARY KEY,
    ticket_promedio  NUMERIC(12,2) NOT NULL,
    num_ventas       INTEGER       NOT NULL,
    ingreso_total    NUMERIC(16,2) NOT NULL,
    actualizado      TIMESTAMP     NOT NULL DEFAULT NOW()
);
"""
# UPSERT: si la tienda ya existe se actualiza (el script se puede correr varias veces)
UPSERT = f"""
INSERT INTO {TABLA} (tienda, ticket_promedio, num_ventas, ingreso_total) VALUES %s
ON CONFLICT (tienda) DO UPDATE SET
    ticket_promedio = EXCLUDED.ticket_promedio,
    num_ventas      = EXCLUDED.num_ventas,
    ingreso_total   = EXCLUDED.ingreso_total,
    actualizado     = NOW();
"""


def leer(ruta):
    registros, invalidas = [], 0
    with open(ruta, encoding="utf-8") as f:
        for num, linea in enumerate(f, 1):
            partes = linea.rstrip("\n").split("\t")
            try:
                tienda, prom, n, total = partes
                registros.append((tienda, float(prom), int(n), float(total)))
            except ValueError:
                invalidas += 1
                print(f"  línea {num} ignorada: {linea!r}", file=sys.stderr)
    return registros, invalidas


def conectar(reintentos=10):
    for i in range(reintentos):
        try:
            return psycopg2.connect(
                host=os.getenv("DB_HOST", "db"),
                port=int(os.getenv("DB_PORT", "5432")),
                dbname=os.environ["POSTGRES_DB"],
                user=os.environ["POSTGRES_USER"],
                password=os.environ["POSTGRES_PASSWORD"],
            )
        except psycopg2.OperationalError:
            print(f"Esperando a la base de datos ({i + 1}/{reintentos})...")
            time.sleep(2)
    sys.exit("No se pudo conectar a la base de datos")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--archivo", default="/data/output/resultado/part-00000")
    p.add_argument("--reemplazar", action="store_true", help="vacía la tabla antes de cargar")
    a = p.parse_args()

    if not os.path.exists(a.archivo):
        sys.exit(f"No existe {a.archivo}. ¿Ya corriste el job de Hadoop?")

    registros, invalidas = leer(a.archivo)
    if not registros:
        sys.exit("El archivo no tiene registros válidos")

    with conectar() as conn, conn.cursor() as cur:
        cur.execute(DDL)
        if a.reemplazar:
            cur.execute(f"TRUNCATE {TABLA}")
        execute_values(cur, UPSERT, registros)
        cur.execute(f"SELECT COUNT(*) FROM {TABLA}")
        total = cur.fetchone()[0]

    print(f"Cargados {len(registros)} registros ({invalidas} inválidos). "
          f"La tabla {TABLA} tiene ahora {total} filas.")


if __name__ == "__main__":
    main()
