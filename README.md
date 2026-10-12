# Prototipo de la Entrega 3 — Plataforma de despachos (Arquitectura de Software, Grupo 7)

Prototipo del **Servicio de Integración con Transportadoras (SIT)**, que aplica el patrón **Data Model
Transformation** para que la plataforma vea a todas las transportadoras en un mismo modelo canónico. Implementa los
componentes marcados con **E3** en la Figura 1 del documento (Entregas 1 y 2). La especificación completa está en
[`docs/specs/2026-10-11-prototipo-entrega-3-design.md`](docs/specs/2026-10-11-prototipo-entrega-3-design.md).

## Componentes

| Contenedor | Qué es | Puerto |
|---|---|---|
| `auth` | Servicio de autenticación OAuth 2.0 que emite JWT (RS256) | 8000 |
| `sit` | SIT: API canónica, sincronizador, catálogo, motor de transformación, adaptadores REST y SOAP | 8010 |
| `despachos` | Orquestador del proceso de envío | 8020 |
| `rastreo` | Historial de estados canónicos | 8030 |
| `mock-dhl` | DHL Express **simulada** (REST/JSON, FastAPI) | 8082 |
| `mock-coordinadora` | Coordinadora **simulada** (SOAP/XML, SoapUI con WSDL propio) | 8088 |
| `postgres`, `redis` | Una base por servicio · bus de eventos (Redis Streams) | internos |

Documentación OpenAPI de cada servicio: `http://localhost:<puerto>/docs`.

## Requisitos

- Docker con Docker Compose v2.
- `bash` y `openssl` (en Windows: Git Bash o WSL).
- Solo para las pruebas: Python 3.12 (o [uv](https://docs.astral.sh/uv/)).

## Puesta en marcha

```bash
scripts/generar-secretos.sh        # crea secrets/ (llaves JWT, contraseñas) e imprime la clave de los usuarios de demo
docker compose up --build -d       # la primera vez descarga SoapUI y construye las imágenes
docker compose ps                  # espere a que los 8 contenedores estén "healthy"
```

Usuarios de demo (contraseña en `secrets/usuarios_demo_password`): `cliente1` (cliente), `agente1` (agente de
servicio), `operador1` (operador logístico) y `admin1` (administrador de integraciones).

Para empezar de cero (por ejemplo, antes de grabar el video): `docker compose down -v && docker compose up -d`.
Si regenera los secretos (`scripts/generar-secretos.sh --forzar`), use siempre `docker compose down -v`.

## Demo

1. Importe en Postman `postman/Entrega3.postman_collection.json` y `postman/Local.postman_environment.json`.
2. En el entorno, ponga en `password` el contenido de `secrets/usuarios_demo_password`.
3. Ejecute `scripts/publicar-pedido.sh PED-1002 coordinadora` (simula el servicio de pedidos publicando
   `pedido.confirmado`).
4. Ejecute las peticiones en orden: tokens → pedido A (DHL) → pedido B (Coordinadora, por evento) → comparación →
   pedido C (la más barata) → cambios de estado → rastreo → `NOVEDAD` → consulta en vivo → catálogo → `403`.

Para ver el XML que el SIT intercambia con Coordinadora y el JSON con DHL: `docker compose logs -f sit`.
Para ver los estados sin equivalencia registrados:
`docker compose exec postgres psql -U plataforma -d sit -c "SELECT * FROM estado_sin_equivalencia"`.

Por terminal, el mismo guion se ejecuta con `npx --yes newman@6.2.1 run postman/Entrega3.postman_collection.json -e
postman/Local.postman_environment.json --env-var "password=$(cat secrets/usuarios_demo_password)"`.

## Pruebas

```bash
uv venv -p 3.12 .venv && uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/pytest                                       # pruebas unitarias (sin Docker)
docker run -d --rm --name redis-pruebas -p 6379:6379 redis:7-alpine
REDIS_URL_PRUEBAS=redis://localhost:6379/0 .venv/bin/pytest -m redis   # recuperación de mensajes pendientes
docker compose up -d && E2E=1 .venv/bin/pytest tests/e2e -v            # guion completo de punta a punta
```

## Cómo se implementó, paso a paso

Sigue el orden del *Plan de implementación técnica* del documento y los pasos de *Aplicación* de la Tabla 3:

1. **Modelo canónico** (`shared/comun/canonico.py`): envío, paquete, cotización, guía y el catálogo de estados
   `CREADA … DEVUELTA`, validados con Pydantic. Es el modelo destino (patrón Canonical Schema).
2. **Tablas de equivalencia** (`services/sit/sit/catalogo/semilla.sql`): estados, ciudades (→ DIVIPOLA) y unidades
   (→ kg y cm) de cada transportadora, en PostgreSQL.
3. **Motor de transformación** (`services/sit/sit/motor/`): un mapeador por transportadora sabe *dónde* va cada dato
   (estructura) y las tablas dicen *cómo* se traduce cada valor (datos). Un estado sin equivalencia se publica como
   `NOVEDAD` y se registra.
4. **Adaptadores por protocolo** (`services/sit/sit/adaptadores/`): REST con httpx y SOAP con zeep (el XML se registra
   con lxml). Reintentan ante fallas y nunca reenvían el error crudo del operador.
5. **API canónica** (`services/sit/sit/api.py`): las rutas de la Tabla 2, con contrato OpenAPI y JWT.
6. **Sincronizador de estados** (`services/sit/sit/servicio.py`, `sincronizador.py`): webhook para DHL y consulta
   programada (APScheduler, cada 10 s según el catálogo) para Coordinadora; publica `envio.estado.actualizado` solo
   cuando cambia el estado canónico.
7. **Orquestador** (`services/despachos/despachos/orquestador.py`): cotiza, elige, crea la guía, programa la recogida
   y publica `guia.creada`; si un paso falla, un nuevo intento retoma desde ahí sin duplicar.
8. **Rastreo** (`services/rastreo/`): guarda el historial canónico sin duplicados.
9. **Seguridad** (`services/auth/`, `shared/comun/seguridad.py`): OAuth 2.0, JWT RS256 y control por roles; los
   secretos van en Docker secrets.

## Cómo agregar una transportadora (Figura 3, parte B)

1. **Adaptador**: reutilice `rest` o `soap` si el protocolo ya existe; si no, implemente uno nuevo en
   `services/sit/sit/adaptadores/` y regístrelo en `crear_adaptador`.
2. **Mapeador y tablas**: escriba su mapeador en `services/sit/sit/motor/mapeadores/`, agréguelo a `MAPEADORES` y
   cargue sus filas de estados, ciudades y unidades.
3. **Catálogo**: registre la transportadora (protocolo, versión de API, adaptador, endpoint, frecuencia, versión de
   tablas) en la tabla `transportadora`, inicialmente con `activa = false`.
4. **Validación y activación**: pruebe el contrato contra un simulador y luego active la transportadora. Despachos y
   Rastreo no se modifican.

## Alcance

Fuera del prototipo, como dice la Entrega 2: API Gateway (Traefik), registro con Consul, adaptador SFTP, servicio de
pedidos y servicios de contexto. Dentro de la red de Compose el tráfico va por HTTP porque el documento ubica la
terminación TLS en el gateway.

## Solución de problemas

- **Un puerto ya está en uso**: detenga el proceso que lo ocupa o cambie el puerto publicado en `docker-compose.yml`.
- **`password authentication failed` en los logs**: los secretos cambiaron con la base ya creada; ejecute
  `docker compose down -v`.
- **`mock-coordinadora` tarda en estar `healthy`**: SoapUI necesita unos segundos para cargar el proyecto.
