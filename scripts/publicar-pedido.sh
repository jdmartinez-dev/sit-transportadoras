#!/usr/bin/env bash
# Publica un evento pedido.confirmado en Redis Streams. Simula el servicio de pedidos, que está fuera del alcance.
# Uso: scripts/publicar-pedido.sh <pedido_id> [transportadora] [divipola_destino]
#   scripts/publicar-pedido.sh PED-1002 coordinadora
set -euo pipefail
cd "$(dirname "$0")/.."
PEDIDO="${1:?Uso: $0 <pedido_id> [transportadora] [divipola_destino]}"
TRANSPORTADORA="${2:-}"
DESTINO="${3:-05001}"
ID_EVENTO=$( (cat /proc/sys/kernel/random/uuid 2>/dev/null || uuidgen || python3 -c 'import uuid; print(uuid.uuid4())') | tr 'A-Z' 'a-z')
AHORA=$(date -u +%Y-%m-%dT%H:%M:%SZ)
if [[ -n "$TRANSPORTADORA" ]]; then CAMPO="\"$TRANSPORTADORA\""; else CAMPO="null"; fi
EVENTO="{\"id_evento\": \"$ID_EVENTO\", \"tipo\": \"pedido.confirmado\", \"version\": 1, \"ocurrido_en\": \"$AHORA\", \"datos\": {\"pedido_id\": \"$PEDIDO\", \"transportadora\": $CAMPO, \"destino\": {\"divipola\": \"$DESTINO\", \"direccion\": \"Carrera 43A # 1-50\", \"nombre\": \"Cliente de prueba\", \"telefono\": \"3001234567\"}, \"paquetes\": [{\"peso_kg\": 2.0, \"largo_cm\": 30, \"ancho_cm\": 20, \"alto_cm\": 10}]}}"
docker compose exec -T redis redis-cli XADD pedido.confirmado '*' evento "$EVENTO" > /dev/null
echo "Evento pedido.confirmado publicado para $PEDIDO"
