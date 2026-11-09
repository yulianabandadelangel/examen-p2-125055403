#!/usr/bin/env python3
"""
Versión secuencial (sin Hadoop) de: ticket promedio por tienda.
Lee el CSV línea por línea en un solo proceso y produce el mismo formato
que el reducer:  tienda \t ticket_promedio \t num_ventas \t ingreso_total

Uso:
  python3 secuencial.py /data/input/ventas_<matricula>.csv
  python3 secuencial.py /data/input/ventas_<matricula>.csv --salida /data/output/secuencial.tsv \
          --comparar /data/output/resultado/part-00000
"""
import argparse
import sys
import time
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

CENTAVO = Decimal("0.01")


def calcular(ruta_csv):
    totales = defaultdict(int)   # tienda -> ingreso en centavos
    conteos = defaultdict(int)   # tienda -> número de registros
    malformadas = 0

    with open(ruta_csv, encoding="utf-8") as f:
        next(f, None)  # saltar encabezado
        for linea in f:
            campos = linea.strip().split(",")
            if len(campos) != 8:
                malformadas += 1
                continue
            try:
                tienda = campos[2].strip()
                cantidad = int(campos[5])
                precio_centavos = round(float(campos[6]) * 100)
                if not tienda or cantidad <= 0 or precio_centavos < 0:
                    raise ValueError
            except ValueError:
                malformadas += 1
                continue
            totales[tienda] += cantidad * precio_centavos
            conteos[tienda] += 1

    filas = []
    for tienda in sorted(totales):
        n = conteos[tienda]
        prom = (Decimal(totales[tienda]) / n / 100).quantize(CENTAVO, ROUND_HALF_UP)
        total = (Decimal(totales[tienda]) / 100).quantize(CENTAVO)
        filas.append(f"{tienda}\t{prom}\t{n}\t{total}")
    return filas, malformadas


def comparar(filas, ruta_hadoop):
    with open(ruta_hadoop, encoding="utf-8") as f:
        hadoop = [l.rstrip("\n") for l in f if l.strip()]
    if hadoop == filas:
        print(f"[OK] Los {len(filas)} registros coinciden exactamente con {ruta_hadoop}")
        return True
    print("[ERROR] Los resultados NO coinciden:")
    for a, b in zip(filas, hadoop):
        if a != b:
            print(f"  secuencial: {a}\n  hadoop:     {b}")
    if len(filas) != len(hadoop):
        print(f"  filas secuencial={len(filas)} hadoop={len(hadoop)}")
    return False


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv")
    p.add_argument("--salida", help="archivo TSV donde guardar el resultado")
    p.add_argument("--comparar", help="ruta a part-00000 de Hadoop para verificar")
    a = p.parse_args()

    inicio = time.perf_counter()
    filas, malformadas = calcular(a.csv)
    seg = time.perf_counter() - inicio

    if a.salida:
        with open(a.salida, "w", encoding="utf-8") as f:
            f.write("\n".join(filas) + "\n")
    else:
        print("\n".join(filas))

    print(f"[secuencial] {len(filas)} tiendas, {malformadas} líneas mal formadas, "
          f"{seg:.2f} s de cómputo", file=sys.stderr)

    if a.comparar and not comparar(filas, a.comparar):
        sys.exit(1)


if __name__ == "__main__":
    main()
