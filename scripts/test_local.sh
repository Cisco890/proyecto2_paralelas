#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

key=20000
limit=50000
phrase="la busqueda distribuida termina cuando aparece la frase clave"

mpicc -std=c11 -O2 bruteforce_mpi.c -lcrypto -o bruteforce_mpi
output="$(mktemp)"
trap 'rm -f "$output"' EXIT

mpirun --oversubscribe -np 2 ./bruteforce_mpi \
  --plaintext texto_plano.txt \
  --search "$phrase" \
  --key "$key" \
  --limit "$limit" | tee "$output"

grep -F "Clave encontrada: $key" "$output" >/dev/null
grep -F "Validacion: OK" "$output" >/dev/null
echo "Prueba local aprobada. El valor de Ts aparece en 'Tiempo total (s)'."
