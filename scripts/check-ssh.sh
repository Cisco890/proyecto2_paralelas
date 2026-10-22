#!/usr/bin/env sh
set -eu

target="${1:-localhost}"
ssh_dir="${HOME:-/root}/.ssh"
key_path="${SSH_KEY_PATH:-$ssh_dir/id_rsa}"
ssh_user="${SSH_USER:-root}"
connect_timeout="${SSH_CONNECT_TIMEOUT:-8}"

if [ ! -f "$key_path" ]; then
    echo "ERROR: no existe la clave privada $key_path; ejecute init-ssh.sh primero." >&2
    exit 1
fi

ssh \
    -i "$key_path" \
    -o BatchMode=yes \
    -o IdentitiesOnly=yes \
    -o PasswordAuthentication=no \
    -o StrictHostKeyChecking=no \
    -o ConnectTimeout="$connect_timeout" \
    "$ssh_user@$target" hostname
