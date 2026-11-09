#!/usr/bin/env python3
"""
Reducer - Ticket promedio por tienda.

Entrada (stdin, ordenada por clave): tienda \t ingreso_centavos \t conteo
Salida: tienda \t ticket_promedio \t num_ventas \t ingreso_total

ticket_promedio = ingreso_total / num_ventas   (redondeado a 2 decimales)
"""
import sys
from decimal import Decimal, ROUND_HALF_UP

CENTAVO = Decimal("0.01")


def emitir(tienda, total_centavos, num_ventas):
    promedio = (Decimal(total_centavos) / num_ventas / 100).quantize(CENTAVO, ROUND_HALF_UP)
    ingreso_total = (Decimal(total_centavos) / 100).quantize(CENTAVO)
    print(f"{tienda}\t{promedio}\t{num_ventas}\t{ingreso_total}")


tienda_actual = None
total = 0     # suma de ingresos en centavos
conteo = 0    # número de registros

for linea in sys.stdin:
    try:
        tienda, ingreso, n = linea.rstrip("\n").split("\t")
        ingreso, n = int(ingreso), int(n)
    except ValueError:
        sys.stderr.write("reporter:counter:DataMart,EntradaReducerInvalida,1\n")
        continue

    # Hadoop entrega las claves ordenadas: al cambiar de clave, se emite la anterior
    if tienda != tienda_actual:
        if tienda_actual is not None:
            emitir(tienda_actual, total, conteo)
        tienda_actual, total, conteo = tienda, 0, 0

    total += ingreso
    conteo += n

if tienda_actual is not None:
    emitir(tienda_actual, total, conteo)
