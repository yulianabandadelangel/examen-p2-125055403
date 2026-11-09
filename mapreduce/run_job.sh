#!/bin/bash
# Ejecuta el job de Hadoop Streaming (modo standalone).
# Uso (desde el host):
#   docker compose exec -u hadoop hadoop bash /opt/mapreduce/run_job.sh
# Opcional: MAPS=4 para correr 4 mappers en paralelo en el LocalJobRunner
#   docker compose exec -u hadoop -e MAPS=4 hadoop bash /opt/mapreduce/run_job.sh
set -euo pipefail

: "${MATRICULA:?Falta la variable MATRICULA (revisa tu .env)}"
INPUT="/data/input/ventas_${MATRICULA}.csv"
OUTPUT="/data/output/resultado"
MAPS="${MAPS:-1}"

[ -f "$INPUT" ] || { echo "No existe $INPUT (¿generaste el CSV en ./data?)"; exit 1; }

# Hadoop falla si la carpeta de salida ya existe
rm -rf "$OUTPUT"
cd /opt/mapreduce

# Las opciones genéricas (-D, -files) van ANTES de las de streaming
time hadoop jar "$HADOOP_HOME"/share/hadoop/tools/lib/hadoop-streaming-*.jar \
  -D mapreduce.job.name="ticket-promedio-${MATRICULA}" \
  -D mapreduce.job.reduces=1 \
  -D mapreduce.local.map.tasks.maximum="${MAPS}" \
  -files mapper.py,reducer.py \
  -input "$INPUT" \
  -output "$OUTPUT" \
  -mapper "python3 mapper.py" \
  -reducer "python3 reducer.py"

echo "---- Resultado ($OUTPUT/part-00000) ----"
cat "$OUTPUT/part-00000"
