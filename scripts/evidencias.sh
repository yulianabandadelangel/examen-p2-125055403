#!/bin/bash
# Corre todas las demostraciones y guarda los logs en ./evidencias/
# Uso (desde la raíz del repo, con el ambiente levantado):  bash scripts/evidencias.sh
set -uo pipefail
cd "$(dirname "$0")/.."
source .env
E=evidencias
mkdir -p "$E"
PORT="${API_PORT:-8000}"

paso() { echo -e "\n===== $1 =====" | tee -a "$E/00_todo.log"; }

paso "1. hadoop version"
docker compose exec -T hadoop hadoop version 2>&1 | tee "$E/01_hadoop_version.log"

paso "2. ssh localhost sin contraseña (dentro de hadoop)"
docker compose exec -T -u hadoop hadoop ssh localhost 'echo "Conectado a $(hostname) como $(whoami)"' 2>&1 | tee "$E/02_ssh_localhost.log"

paso "3. ssh desde api hacia hadoop por nombre de servicio"
docker compose exec -T api ssh hadoop@hadoop 'echo "Conectado a $(hostname) como $(whoami)"; hadoop version | head -1' 2>&1 | tee "$E/03_ssh_api_a_hadoop.log"

paso "4. Job de Hadoop Streaming"
docker compose exec -T -u hadoop hadoop bash /opt/mapreduce/run_job.sh 2>&1 | tee "$E/04_job_hadoop.log"

paso "5. Script secuencial + verificación"
docker compose exec -T -u hadoop hadoop bash -c "time python3 /opt/mapreduce/secuencial.py /data/input/ventas_${MATRICULA}.csv --salida /data/output/secuencial.tsv --comparar /data/output/resultado/part-00000" 2>&1 | tee "$E/05_secuencial.log"

paso "6. Carga a PostgreSQL"
docker compose exec -T api python /opt/scripts/cargar_resultados.py --reemplazar 2>&1 | tee "$E/06_carga.log"

paso "7. API"
{
  echo "GET /resultados";            curl -s "localhost:$PORT/resultados"; echo
  echo "GET /resultados/T001";       curl -s "localhost:$PORT/resultados/T001"; echo
  echo "POST /resultados (T999)";    curl -s -X POST "localhost:$PORT/resultados" -H 'Content-Type: application/json' \
                                       -d '{"tienda":"T999","ticket_promedio":100.5,"num_ventas":10,"ingreso_total":1005}'; echo
  echo "PUT /resultados/T999";       curl -s -X PUT "localhost:$PORT/resultados/T999" -H 'Content-Type: application/json' \
                                       -d '{"ticket_promedio":200}'; echo
  echo "DELETE /resultados/T999";    curl -s -X DELETE "localhost:$PORT/resultados/T999"; echo
} 2>&1 | tee "$E/07_api.log"

echo -e "\nLogs guardados en $E/"
