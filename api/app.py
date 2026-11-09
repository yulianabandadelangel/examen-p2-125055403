"""
API DataMart - Ticket promedio por tienda.

Endpoints:
  GET    /health
  GET    /resultados                 -> todos los registros (?orden=ticket para ordenar por ticket desc)
  GET    /resultados/<tienda>        -> filtro por tienda (ej. T007)
  POST   /resultados                 -> crear registro
  PUT    /resultados/<tienda>        -> actualizar registro
  DELETE /resultados/<tienda>        -> eliminar registro
"""
import os
import time

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, request

app = Flask(__name__)

DB = dict(
    host=os.getenv("DB_HOST", "db"),            # nombre del servicio en el compose
    port=int(os.getenv("DB_PORT", "5432")),
    dbname=os.getenv("POSTGRES_DB"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
)

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
CAMPOS = ("ticket_promedio", "num_ventas", "ingreso_total")


def conectar():
    return psycopg2.connect(**DB)


def init_db(reintentos=15):
    """Crea la tabla; reintenta mientras PostgreSQL termina de arrancar."""
    for i in range(reintentos):
        try:
            with conectar() as c, c.cursor() as cur:
                cur.execute(DDL)
            return
        except psycopg2.OperationalError:
            print(f"[api] Esperando a la base de datos ({i + 1}/{reintentos})...", flush=True)
            time.sleep(2)
    raise RuntimeError("No se pudo conectar a la base de datos")


def a_json(fila):
    return {
        "tienda": fila["tienda"],
        "ticket_promedio": float(fila["ticket_promedio"]),
        "num_ventas": fila["num_ventas"],
        "ingreso_total": float(fila["ingreso_total"]),
        "actualizado": fila["actualizado"].isoformat(),
    }


def consulta(sql, params=(), una=False):
    with conectar() as c, c.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        if cur.description is None:
            return None
        return cur.fetchone() if una else cur.fetchall()


def validar(datos, parcial=False):
    """Devuelve (valores, error). En PUT (parcial) no todos los campos son obligatorios."""
    valores = {}
    for campo in CAMPOS:
        if campo not in datos:
            if parcial:
                continue
            return None, f"Falta el campo '{campo}'"
        try:
            v = int(datos[campo]) if campo == "num_ventas" else float(datos[campo])
        except (TypeError, ValueError):
            return None, f"'{campo}' debe ser numérico"
        if v < 0:
            return None, f"'{campo}' no puede ser negativo"
        valores[campo] = v
    if parcial and not valores:
        return None, f"Envía al menos uno de: {', '.join(CAMPOS)}"
    return valores, None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/resultados")
def listar():
    orden = "ticket_promedio DESC" if request.args.get("orden") == "ticket" else "tienda"
    filas = consulta(f"SELECT * FROM {TABLA} ORDER BY {orden}")
    return jsonify([a_json(f) for f in filas])


@app.get("/resultados/<tienda>")
def obtener(tienda):
    fila = consulta(f"SELECT * FROM {TABLA} WHERE tienda = %s", (tienda.upper(),), una=True)
    if not fila:
        return {"error": f"No hay resultados para la tienda {tienda.upper()}"}, 404
    return a_json(fila)


@app.post("/resultados")
def crear():
    datos = request.get_json(silent=True) or {}
    tienda = str(datos.get("tienda", "")).strip().upper()
    if not tienda:
        return {"error": "Falta el campo 'tienda'"}, 400
    valores, error = validar(datos)
    if error:
        return {"error": error}, 400
    try:
        fila = consulta(
            f"INSERT INTO {TABLA} (tienda, ticket_promedio, num_ventas, ingreso_total) "
            f"VALUES (%s, %s, %s, %s) RETURNING *",
            (tienda, valores["ticket_promedio"], valores["num_ventas"], valores["ingreso_total"]),
            una=True,
        )
    except psycopg2.errors.UniqueViolation:
        return {"error": f"La tienda {tienda} ya existe; usa PUT para actualizarla"}, 409
    return a_json(fila), 201


@app.put("/resultados/<tienda>")
def actualizar(tienda):
    valores, error = validar(request.get_json(silent=True) or {}, parcial=True)
    if error:
        return {"error": error}, 400
    sets = ", ".join(f"{c} = %s" for c in valores) + ", actualizado = NOW()"
    fila = consulta(
        f"UPDATE {TABLA} SET {sets} WHERE tienda = %s RETURNING *",
        (*valores.values(), tienda.upper()),
        una=True,
    )
    if not fila:
        return {"error": f"No existe la tienda {tienda.upper()}"}, 404
    return a_json(fila)


@app.delete("/resultados/<tienda>")
def eliminar(tienda):
    fila = consulta(f"DELETE FROM {TABLA} WHERE tienda = %s RETURNING *", (tienda.upper(),), una=True)
    if not fila:
        return {"error": f"No existe la tienda {tienda.upper()}"}, 404
    return {"eliminado": a_json(fila)}


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
