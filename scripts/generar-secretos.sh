#!/usr/bin/env bash
# Genera los Docker secrets del prototipo en ./secrets (la carpeta está en .gitignore: nunca se sube).
set -euo pipefail
cd "$(dirname "$0")/.."
DIR=secrets
if [[ -d "$DIR" && "${1:-}" != "--forzar" ]]; then
  echo "Ya existe $DIR/. Use --forzar para regenerarlos (y luego: docker compose down -v)." >&2
  exit 1
fi
mkdir -p "$DIR"
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$DIR/jwt_privada" 2>/dev/null
openssl pkey -in "$DIR/jwt_privada" -pubout -out "$DIR/jwt_publica"
for nombre in postgres_password dhl_api_password cliente_despachos_secret cliente_mock_dhl_secret usuarios_demo_password; do
  openssl rand -hex 16 > "$DIR/$nombre"
done
chmod 600 "$DIR"/*
echo "Secretos generados en $DIR/."
echo "Contraseña de los usuarios de demo (cliente1, agente1, operador1, admin1): $(cat "$DIR/usuarios_demo_password")"
