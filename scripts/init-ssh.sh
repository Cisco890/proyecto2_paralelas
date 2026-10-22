#!/usr/bin/env sh
set -eu

ssh_dir="${HOME:-/root}/.ssh"
key_path="${SSH_KEY_PATH:-$ssh_dir/id_rsa}"
authorized_keys="$ssh_dir/authorized_keys"
key_type="${SSH_KEY_TYPE:-rsa}"

mkdir -p "$ssh_dir" /run/sshd
chmod 700 "$ssh_dir"
touch "$authorized_keys"
chmod 600 "$authorized_keys"

if [ ! -f "$key_path" ]; then
    ssh-keygen -q -t "$key_type" -N "" -f "$key_path"
fi

if [ ! -f "$key_path.pub" ]; then
    echo "ERROR: falta la clave publica $key_path.pub" >&2
    exit 1
fi

add_public_key() {
    key="$1"
    [ -n "$key" ] || return 0
    grep -Fqx "$key" "$authorized_keys" 2>/dev/null || printf '%s\n' "$key" >> "$authorized_keys"
}

# Permite validar ssh localhost sin contrasena. No sobrescribe claves existentes.
if [ "${AUTHORIZE_SELF:-1}" = "1" ]; then
    add_public_key "$(cat "$key_path.pub")"
fi

# Un worker recibe solo la clave publica del maestro, nunca su clave privada.
if [ -n "${SSH_PUBLIC_KEY:-}" ]; then
    add_public_key "$SSH_PUBLIC_KEY"
fi
if [ -n "${SSH_PUBLIC_KEY_FILE:-}" ] && [ -f "$SSH_PUBLIC_KEY_FILE" ]; then
    while IFS= read -r public_key || [ -n "$public_key" ]; do
        add_public_key "$public_key"
    done < "$SSH_PUBLIC_KEY_FILE"
fi

if ! pgrep -x sshd >/dev/null 2>&1; then
    /usr/sbin/sshd
fi

echo "SSH inicializado. Clave publica disponible en $key_path.pub"
