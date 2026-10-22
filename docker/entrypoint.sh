#!/bin/sh
set -e

mkdir -p /run/sshd /root/.ssh
chmod 700 /root/.ssh

# Se generan al arrancar, nunca se comparte una identidad SSH desde la imagen.
ssh-keygen -A
/usr/sbin/sshd -t

# Respeta un servidor ya iniciado en este contenedor.
if [ -s /run/sshd.pid ] && kill -0 "$(cat /run/sshd.pid)" 2>/dev/null; then
    echo "SSH ya esta activo en el contenedor." >&2
else
    if ! /usr/sbin/sshd -e; then
        echo "ERROR: no se pudo iniciar sshd; revisa la configuracion y el puerto 22." >&2
        exit 1
    fi
    # El proceso daemon puede tardar brevemente en escribir su PID tras el fork.
    attempts=0
    until [ -s /run/sshd.pid ] && kill -0 "$(cat /run/sshd.pid)" 2>/dev/null; do
        attempts=$((attempts + 1))
        if [ "$attempts" -ge 20 ]; then
            echo "ERROR: sshd no quedo activo; revisa si el puerto 22 esta ocupado." >&2
            exit 1
        fi
        sleep 0.1
    done
fi

if [ "$#" -eq 0 ]; then
    set -- /bin/bash
fi
exec "$@"
