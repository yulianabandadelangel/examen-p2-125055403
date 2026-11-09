# Examen Segundo Parcial: Manejo Masivo de Datos (Big Data)

* **Matrícula:** 125055403
* **Pregunta asignada (último dígito 3):** *Ticket promedio (ingreso promedio por registro) por tienda.*

  * `ingreso = cantidad × precio\_unitario`
  * `ticket\_promedio(tienda) = Σ ingreso / número de registros de la tienda`

## Arquitectura

```
                 red: datamart-net (bridge)
 ┌────────────────────┐   ssh hadoop@hadoop   ┌───────────────────┐   psycopg2    ┌──────────────┐
 │ hadoop             │ ◄──────────────────── │ api (Flask)       │ ────────────► │ db (Postgres)│
 │ Debian + Java 17   │                       │ :5000 → host:8000 │               │ vol: pgdata  │
 │ Hadoop 3.3.6 + sshd│                       │ cargar\_resultados │               └──────────────┘
 └────────────────────┘                       └───────────────────┘
   /data/input  (ro) ← ./data           /data/output ← ./output (part-00000)
```

|Servicio|Imagen|Detalles|
|-|-|-|
|`hadoop`|`hadoop/Dockerfile` (debian:bookworm-slim)|OpenJDK 17, Python 3, Hadoop standalone y OpenSSH Server. El dataset se monta en `/data/input` en **solo lectura**.|
|`db`|postgres:16|Credenciales en `.env`. Usa el volumen nombrado `pgdata`.|
|`api`|`api/Dockerfile` (python:3.12-slim)|Flask + gunicorn. Se conecta a `db` por nombre de servicio y tiene `depends\_on: db` (healthy).|

## Estructura

```
├── docker-compose.yml
├── .env.example           # copiar a .env
├── hadoop/Dockerfile, entrypoint.sh
├── mapreduce/mapper.py, reducer.py, secuencial.py, run\_job.sh
├── api/Dockerfile, requirements.txt, app.py
├── scripts/generar\_dataset.py, cargar\_resultados.py, evidencias.sh
├── data/                  # aquí va el CSV (ignorado por git)
├── output/                # salida de Hadoop (ignorada por git)
└── evidencias/
```

## Cómo reproducir

```bash
# 0) Generar el dataset dentro de ./data (≈400 MB, tarda unos minutos)
cd data \&\& python3 ../scripts/generar\_dataset.py 125055403 \&\& cd ..

# 1) Variables de entorno (cambia la contraseña en .env)
cp .env.example .env

# 2) Levantar todo con un solo comando
docker compose up --build -d
docker compose ps
```

> El primer build descarga Hadoop (\~700 MB) y puede tardar varios minutos.

### Parte A. Verificar Hadoop

```bash
docker compose exec hadoop hadoop version
docker compose exec hadoop bash -c 'echo $JAVA\_HOME $HADOOP\_HOME'
```

### Parte B. SSH sin contraseña

```bash
# ssh localhost dentro del contenedor hadoop
docker compose exec -u hadoop hadoop ssh localhost hostname

# Desde api hacia hadoop, por nombre de servicio
docker compose exec api ssh hadoop@hadoop 'hostname; whoami; hadoop version | head -1'
```

Funcionamiento:

* **ssh localhost:** al construir la imagen, el usuario `hadoop` genera su par de llaves con `ssh-keygen -N ''` y copia la llave pública a `authorized\_keys`, igual que en el modo pseudo-distribuido.
* **api → hadoop:** al arrancar, `hadoop/entrypoint.sh` genera una segunda llave en el volumen nombrado `ssh-shared` y la autoriza. El contenedor `api` monta ese volumen en solo lectura y la usa.
* `sshd` tiene `PasswordAuthentication no` y `PermitRootLogin no`. El usuario no tiene contraseña (`usermod -p '\*'`), así que **no hay contraseñas en el Dockerfile ni en el repositorio**, y las llaves privadas tampoco se suben.

### Parte C1. Job de Hadoop Streaming

```bash
docker compose exec -u hadoop hadoop bash /opt/mapreduce/run\_job.sh
cat output/resultado/part-00000
```

El script ejecuta:

```bash
hadoop jar $HADOOP\_HOME/share/hadoop/tools/lib/hadoop-streaming-\*.jar \\
  -D mapreduce.job.reduces=1 -files mapper.py,reducer.py \\
  -input /data/input/ventas\_125055403.csv -output /data/output/resultado \\
  -mapper "python3 mapper.py" -reducer "python3 reducer.py"
```

* **mapper.py** ignora el encabezado (`id,...`). Una línea mal formada (con campos de más o de menos, o con números inválidos) se cuenta en el contador `DataMart:LineasMalformadas` y se salta, sin detener el job. Por cada registro emite `tienda \\t ingreso\_en\_centavos \\t 1`.
* **reducer.py** suma ingresos y conteos de cada tienda y emite `tienda \\t ticket\_promedio \\t num\_ventas \\t ingreso\_total`.
* El ingreso se calcula en **centavos enteros** para que la suma sea exacta y los resultados coincidan al centavo con el script secuencial.

### Parte C2. Comparativa

```bash
docker compose exec -u hadoop hadoop bash -c \\
  "time python3 /opt/mapreduce/secuencial.py /data/input/ventas\_\\$MATRICULA.csv \\
   --salida /data/output/secuencial.tsv --comparar /data/output/resultado/part-00000"
```

`--comparar` compara línea por línea con `part-00000` y muestra `\[OK]` si los resultados coinciden.

| Método | Tiempo `real` | ¿Coincide? |

|---|---|---|

| Hadoop Streaming (standalone, 1 mapper a la vez) | 1m41.901s | — |

| Python secuencial (línea a línea) | 0m48.371s | \[OK] |



**¿Por qué uno fue más rápido?** *(ajusta el párrafo a tus tiempos)*: En este escenario, el script secuencial fue más rápido que Hadoop. En modo standalone, Hadoop corre en una sola máquina con el `LocalJobRunner` ...El script secuencial solo lee el archivo una vez y acumula en un diccionario de 21 tiendas que cabe completo en memoria. A eso se le suma un costo fijo que el script secuencial no tiene: arrancar la JVM, planear el job, abrir un proceso de Python por cada split, pasar cada línea por tuberías stdin/stdout, serializar 5 millones de pares clave-valor, y ordenarlos y escribirlos a disco (*spill*) durante el *shuffle* para un solo reducer. El script secuencial solo lee el archivo una vez y acumula en un diccionario de \~20 tiendas que cabe completo en memoria. MapReduce compensa cuando los datos no caben en una máquina o cuando hay varios nodos que procesan bloques de HDFS en paralelo.

### Parte D. Integración con la base de datos y la API

```bash
# Cargar part-00000 en PostgreSQL (UPSERT; --reemplazar vacía la tabla antes)
docker compose exec api python /opt/scripts/cargar\_resultados.py

curl localhost:8000/resultados                    # todos
curl "localhost:8000/resultados?orden=ticket"     # ordenados por ticket descendente
curl localhost:8000/resultados/T001               # filtro por tienda

# Escritura (CRUD)
curl -X POST localhost:8000/resultados -H 'Content-Type: application/json' \\
     -d '{"tienda":"T999","ticket\_promedio":100.5,"num\_ventas":10,"ingreso\_total":1005}'
curl -X PUT localhost:8000/resultados/T999 -H 'Content-Type: application/json' -d '{"ticket\_promedio":200}'
curl -X DELETE localhost:8000/resultados/T999
```

Tabla `resultados\_ticket(tienda PK, ticket\_promedio, num\_ventas, ingreso\_total, actualizado)`.

**Persistencia:**

```bash
docker compose down          # elimina contenedores y la red, pero NO los volúmenes
docker compose up -d
curl localhost:8000/resultados   # los datos siguen ahí
```

### Evidencias automáticas

```bash
bash scripts/evidencias.sh   # guarda logs de cada paso en ./evidencias/
```

Agrega también capturas de pantalla de: `hadoop version`, ssh sin contraseña (en los dos casos), salida del job y respuesta de la API.

\---

## Parte E. Teoría

**1. Modos de Hadoop.** En el modo *standalone* (local), todo corre en un solo proceso JVM sobre el sistema de archivos local. No hay demonios ni HDFS, y se usa para desarrollo y depuración. En el modo *pseudo-distribuido*, cada demonio (NameNode, DataNode, ResourceManager, NodeManager) corre como un proceso separado en **una sola máquina**, y se comunican por SSH a `localhost`. En el modo *totalmente distribuido*, los demonios se reparten en varios nodos de un clúster, con replicación de bloques. **HDFS se usa en los modos pseudo-distribuido y totalmente distribuido**, no en standalone.

**2. Volumen vs `COPY` para el dataset.** (a) **Tamaño:** copiar 400 MB dentro de la imagen la hace pesada y lenta de construir, subir y descargar. (b) **Independencia de datos y código:** cada alumno o ejecución usa un CSV distinto sin reconstruir la imagen; si el CSV cambia, basta con reemplazar el archivo. (c) **Caché de build:** con `COPY`, cualquier cambio invalida las capas. (d) **Seguridad y repositorio:** el dato no queda dentro de la imagen ni en el contexto de build. Además, montarlo `:ro` garantiza que el job no lo modifique.

**3. `down` vs `down -v`.** `docker compose down` detiene y elimina los contenedores y la red, pero **conserva los volúmenes nombrados** (`pgdata`): al volver a levantar el ambiente, los datos siguen ahí. `docker compose down -v` además **borra los volúmenes nombrados** declarados en el compose, así que la base de datos se pierde y PostgreSQL arranca vacío. Hay que volver a correr `cargar\_resultados.py`. Los *bind mounts* (`./data`, `./output`) no se borran en ningún caso.

**4. ¿Por qué MapReduce no siempre gana?** Con 400 MB en una sola máquina, el costo fijo de MapReduce domina: arranque de la JVM, planeación, procesos de streaming, serialización, *sort/shuffle* y escritura a disco. El archivo cabe en el caché de memoria y un solo proceso lo recorre en segundos. Conviene cuando los datos **no caben en una máquina** (de cientos de GB a TB), cuando hay **varios nodos** que procesan en paralelo bloques locales de HDFS (localidad de datos) y se necesita **tolerancia a fallos**, o cuando el cómputo por registro es pesado y se puede paralelizar.

**5. `CMD` vs `ENTRYPOINT`, `COPY` vs `ADD`.** `ENTRYPOINT` define el ejecutable principal del contenedor, y los argumentos de `docker run` se le **agregan**. Solo se reemplaza con `--entrypoint`. `CMD` define el comando o los argumentos por defecto, y se **reemplaza** con lo que escribas después de la imagen en `docker run`. Si se usan juntos, `CMD` funciona como parámetros de `ENTRYPOINT`. `COPY` solo copia archivos del contexto de build. `ADD` hace lo mismo y además descomprime automáticamente archivos `.tar` locales y puede descargar URLs. Se recomienda `COPY` por ser más predecible.

\---

## Guía para la defensa oral

|Cambio solicitado|Cómo hacerlo|
|-|-|
|**Cambiar el puerto de la API**|Edita `API\_PORT=9000` en `.env` y luego `docker compose up -d api` (o `up -d --build`). Prueba con `curl localhost:9000/resultados`. El puerto interno (5000) no cambia; solo cambia el mapeo `host:contenedor`.|
|**Cambiar la agregación**|`mapreduce/` está montado como volumen, así que basta con editar el archivo y volver a correr `run\_job.sh`, **sin reconstruir la imagen**. Ejemplos: <br>• *Filtro por mes:* en el mapper, `if campos\[1]\[5:7] != "03": continue` (la fecha es `YYYY-MM-DD ...`). <br>• *Ingreso total en lugar del promedio:* en el reducer, emite `total/100`. <br>• *Promedio de unidades:* en el mapper, emite `cantidad` en lugar del ingreso.|
|**Borrar el volumen de la BD y recargar**|`docker compose down -v \&\& docker compose up -d`, luego `docker compose exec api python /opt/scripts/cargar\_resultados.py` y `curl localhost:8000/resultados`. Nota: `-v` también borra `ssh-shared`, pero se regenera solo al arrancar.|
|**Diagnóstico**|`docker compose ps`, `docker compose logs api` / `db` / `hadoop`, `docker compose exec hadoop bash`. Si el job falla con *Output directory already exists*, borra `output/resultado` (`run\_job.sh` ya lo hace). Si la API responde *connection refused*, revisa que `db` esté *healthy*.|

Nota técnica: no se puede usar el reducer como *combiner* porque emite un promedio, y el promedio de promedios es incorrecto. Un combiner válido tendría que emitir `(suma, conteo)`, con el mismo formato que el mapper.

