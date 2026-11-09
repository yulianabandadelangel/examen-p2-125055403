#!/usr/bin/env python3
"""
Mapper - Ticket promedio por tienda (matrícula terminación 3).

Entrada (stdin): líneas del CSV
    id,fecha_hora,tienda,categoria,producto,cantidad,precio_unitario,metodo_pago
Salida (stdout): tienda \t ingreso_en_centavos \t 1

El ingreso se maneja en CENTAVOS (enteros) para que la suma sea exacta y
el resultado de Hadoop coincida al centavo con el script secuencial.
"""
import sys

NUM_CAMPOS = 8


def contador(nombre):
    """Incrementa un contador de Hadoop Streaming (aparece en el log del job)."""
    sys.stderr.write(f"reporter:counter:DataMart,{nombre},1\n")


for linea in sys.stdin:
    linea = linea.strip()
    if not linea:
        continue

    campos = linea.split(",")

    # 1) Encabezado: se ignora
    if campos[0] == "id":
        contador("Encabezado")
        continue

    # 2) Líneas mal formadas: se cuentan y se saltan (no truncan el job)
    if len(campos) != NUM_CAMPOS:
        contador("LineasMalformadas")
        continue
    try:
        tienda = campos[2].strip()
        cantidad = int(campos[5])
        precio_centavos = round(float(campos[6]) * 100)
        if not tienda or cantidad <= 0 or precio_centavos < 0:
            raise ValueError("valores fuera de rango")
    except ValueError:
        contador("LineasMalformadas")
        continue

    # 3) Emitir clave (tienda) y valores (ingreso del registro, 1 registro)
    sys.stdout.write(f"{tienda}\t{cantidad * precio_centavos}\t1\n")
