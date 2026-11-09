# ---------------------------------------------------------------
# Imagen de Hadoop (standalone) + Python 3 + OpenSSH Server
# Base: Debian bookworm-slim
# ---------------------------------------------------------------
FROM debian:bookworm-slim

# Versión de Hadoop y URL de descarga (se pueden cambiar con --build-arg)
ARG HADOOP_VERSION=3.3.6
ARG HADOOP_URL=https://archive.apache.org/dist/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz

# Variables de entorno obligatorias.
# /usr/lib/jvm/default-java es un enlace que crea el paquete default-jre-headless;
# así funciona igual en amd64 y en arm64 (Mac M1/M2).
ENV JAVA_HOME=/usr/lib/jvm/default-java \
    HADOOP_HOME=/opt/hadoop \
    HADOOP_CONF_DIR=/opt/hadoop/etc/hadoop
ENV PATH=${HADOOP_HOME}/bin:${HADOOP_HOME}/sbin:${JAVA_HOME}/bin:${PATH}
# Java 17 restringe la reflexión; estas banderas evitan errores de Hadoop 3.3.x
ENV HADOOP_OPTS="--add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.base/java.util=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED --add-opens=java.base/sun.nio.ch=ALL-UNNAMED"

# 1) Paquetes: Java (OpenJDK 17), Python 3, SSH (servidor y cliente) y utilidades
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      default-jre-headless python3 openssh-server openssh-client \
      curl ca-certificates procps \
 && rm -rf /var/lib/apt/lists/*

# 2) Descargar e instalar Hadoop (sin la documentación para aligerar la imagen)
RUN curl -fSL "${HADOOP_URL}" -o /tmp/hadoop.tar.gz \
 && tar -xzf /tmp/hadoop.tar.gz -C /opt \
 && mv /opt/hadoop-${HADOOP_VERSION} ${HADOOP_HOME} \
 && rm -rf /tmp/hadoop.tar.gz ${HADOOP_HOME}/share/doc \
 # hadoop-env.sh necesita JAVA_HOME explícito (las sesiones SSH no heredan ENV)
 && echo "export JAVA_HOME=${JAVA_HOME}" >> ${HADOOP_CONF_DIR}/hadoop-env.sh

# 3) Variables disponibles también en sesiones SSH (login shells)
RUN printf 'export JAVA_HOME=%s\nexport HADOOP_HOME=%s\nexport HADOOP_CONF_DIR=%s\nexport HADOOP_OPTS="%s"\nexport PATH=%s/bin:%s/sbin:$PATH\n' \
      "${JAVA_HOME}" "${HADOOP_HOME}" "${HADOOP_CONF_DIR}" "${HADOOP_OPTS}" "${HADOOP_HOME}" "${HADOOP_HOME}" \
      > /etc/profile.d/hadoop.sh

# 4) Usuario sin contraseña: '*' = ninguna contraseña es válida (solo llaves)
RUN useradd -m -s /bin/bash hadoop \
 && usermod -p '*' hadoop

# 5) SSH server: solo autenticación por llave, sin root, sin contraseñas
RUN mkdir -p /run/sshd \
 && ssh-keygen -A \
 && sed -ri 's/^#?PasswordAuthentication .*/PasswordAuthentication no/' /etc/ssh/sshd_config \
 && sed -ri 's/^#?PermitRootLogin .*/PermitRootLogin no/' /etc/ssh/sshd_config \
 && sed -ri 's/^#?PubkeyAuthentication .*/PubkeyAuthentication yes/' /etc/ssh/sshd_config

# 6) Llave del usuario hadoop (ssh localhost sin contraseña, como en pseudo-distribuido)
USER hadoop
RUN mkdir -p ~/.ssh && chmod 700 ~/.ssh \
 && ssh-keygen -t ed25519 -N '' -f ~/.ssh/id_ed25519 -q \
 && cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys \
 && chmod 600 ~/.ssh/authorized_keys \
 && printf 'Host localhost 127.0.0.1 hadoop 0.0.0.0\n  StrictHostKeyChecking no\n  UserKnownHostsFile /dev/null\n  LogLevel ERROR\n' > ~/.ssh/config \
 && chmod 600 ~/.ssh/config
USER root

# 7) Verificación en tiempo de build: si Hadoop no funciona, el build falla
RUN hadoop version

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /opt/mapreduce
EXPOSE 22
ENTRYPOINT ["/entrypoint.sh"]
