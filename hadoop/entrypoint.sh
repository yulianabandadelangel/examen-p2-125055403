#!/bin/bash
# Arranque del contenedor hadoop:
#  - genera (una sola vez) la llave que usará el contenedor api para entrar por SSH
#  - autoriza esa llave para el usuario hadoop
#  - deja sshd corriendo en primer plano (mantiene vivo el contenedor)
set -e

SHARED=/ssh-shared                       # volumen nombrado compartido con api
AUTH=/home/hadoop/.ssh/authorized_keys

if [ -d "$SHARED" ]; then
  if [ ! -f "$SHARED/id_ed25519" ]; then
    ssh-keygen -t ed25519 -N '' -C "api->hadoop" -f "$SHARED/id_ed25519" -q
    echo "[entrypoint] Llave para el contenedor api generada en $SHARED"
  fi
  chmod 600 "$SHARED/id_ed25519"
  PUB="$(cat "$SHARED/id_ed25519.pub")"
  grep -qxF "$PUB" "$AUTH" || echo "$PUB" >> "$AUTH"
  chown hadoop:hadoop "$AUTH" && chmod 600 "$AUTH"
fi

# Carpeta de salida de MapReduce escribible por el usuario hadoop
mkdir -p /data/output && chown hadoop:hadoop /data/output

echo "[entrypoint] Iniciando sshd..."
exec /usr/sbin/sshd -D -e
