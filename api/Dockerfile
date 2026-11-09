FROM python:3.12-slim

# Cliente SSH para conectarse al contenedor hadoop por nombre de servicio
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssh-client \
 && rm -rf /var/lib/apt/lists/*

# "ssh hadoop" usa la llave del volumen compartido (la genera el contenedor hadoop al arrancar)
RUN printf 'Host hadoop\n  User hadoop\n  IdentityFile /ssh-shared/id_ed25519\n  StrictHostKeyChecking no\n  UserKnownHostsFile /dev/null\n  LogLevel ERROR\n' \
      > /etc/ssh/ssh_config.d/hadoop.conf

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

EXPOSE 5000
# --preload: la tabla se crea una sola vez antes de levantar los workers
CMD ["gunicorn", "--preload", "-w", "2", "-b", "0.0.0.0:5000", "app:app"]
