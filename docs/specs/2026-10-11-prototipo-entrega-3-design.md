# Especificación del prototipo — Entrega 3

**Proyecto:** Arquitectura de Software, Grupo 7 — Politécnico Grancolombiano
**Fecha:** 11 de octubre de 2026
**Fuente:** documento "Entrega 1 y Entrega 2" (secciones *Modelo arquitectónico*, *Selección del patrón*, *Diseño de los servicios*, *Comunicación entre servicios y orquestación*, *Proveedor y registro de servicios*, *Seguridad* y *Plan de implementación técnica*), y rúbrica de la Entrega 3.

## 1. Criterio rector

El prototipo **implementa lo que ya dicen las Entregas 1 y 2, sin cambiarlo**, porque la nota final depende de la coherencia entre el documento y lo construido. Toda decisión de esta especificación cumple una de dos condiciones:

1. sale textualmente del documento (la sección 17 traza cada una), o
2. completa un detalle que el documento deja abierto, sin contradecirlo (la sección 18 las lista de forma explícita).

Si durante la implementación algo obliga a apartarse del documento, se detiene el trabajo y se decide con el equipo antes de seguir.

## 2. Alcance

### 2.1 Dentro del prototipo

Son los componentes marcados con **E3** en la Figura 1 y en el "Alcance del prototipo (Entrega 3)":

- **SIT** (Servicio de Integración con Transportadoras): API canónica, sincronizador de estados, catálogo, motor de transformación y adaptadores REST y SOAP.
- **Despachos** mínimo, que actúa como orquestador.
- **Rastreo** mínimo.
- **Servicio de autenticación.**
- **Redis** (bus de eventos con Redis Streams) y **PostgreSQL**.
- **Dos transportadoras simuladas** con modelos de datos distintos entre sí:
  - DHL Express: REST/JSON, simulada en FastAPI.
  - Coordinadora: SOAP/XML, simulada en SoapUI a partir de un WSDL propio.

### 2.2 Fuera del prototipo

Quedan como diseño, igual que en el documento:

- **API Gateway (Traefik).** En consecuencia, dentro de la red de Docker Compose el tráfico va por HTTP, porque el documento ubica la terminación TLS en el gateway.
- **Registro de servicios (Consul)**, que es la Figura 3, parte A. Los contenedores se ubican por nombre dentro de la red de Docker Compose, como dice el documento.
- **Adaptador SFTP** y operadores regionales.
- **Servicio de pedidos.** Se simula la confirmación del pedido con `POST /api/v1/despachos` desde Postman, o publicando el evento con `scripts/publicar-pedido.sh`.
- **Servicios de contexto:** inventario, cotización de fletes, notificaciones y conciliación.
- **Varias instancias del SIT.** Se implementan los reintentos, que son la otra mitigación de la Tabla 3.
- **WS-Security.** El documento lo aplica "cuando el operador lo exige", y el simulador de Coordinadora no lo exige.

## 3. Decisiones de la Fase 0

| # | Decisión | Base en el documento |
|---|---|---|
| D1 | Simulador de Coordinadora en **SoapUI** con WSDL propio, ejecutado con `mockservicerunner.sh` dentro de un contenedor. | Tabla 4: "mock SOAP en SoapUI a partir de un WSDL propio"; "todos los componentes corren con Docker Compose". |
| D2 | Un estado sin equivalencia **se publica como `NOVEDAD` y se registra** en la tabla `estado_sin_equivalencia`. | *Comunicación entre servicios*: "si un estado no tiene equivalencia, se publica como NOVEDAD y se registra para que el equipo de integración complete la tabla". |
| D3 | Despachos elige la **cotización más barata**. Un pedido puede **forzar** la transportadora. | Tabla 2: "cotiza a través del SIT, elige la transportadora" (no fija una regla). |
| D4 | Código en un **repositorio git local** en `repository/`. Se pasa a GitHub cuando la base funcione. | No aplica (el documento no lo menciona). |

## 4. Arquitectura del prototipo

```
 Postman ── HTTP + JWT ──► auth · despachos · rastreo · sit (consultas de la demo)
 scripts/publicar-pedido.sh ── XADD pedido.confirmado ──► Redis Streams

 ┌───────────┐ REST/JSON + JWT  ┌─────────────────────────────────────┐
 │ despachos │ ───────────────► │ SIT                                 │
 └─────▲─────┘                  │  API canónica /api/v1               │
       │ pedido.confirmado      │  sincronizador · catálogo           │
 ┌─────┴────────────────────┐   │  motor de transformación            │
 │ Redis Streams            │◄──│  adaptador REST · adaptador SOAP    │
 │ envio.estado.actualizado │   └───────┬────────────────┬────────────┘
 └─────┬────────────────────┘ HTTP+JSON │       HTTP+XML │ (SOAP)
       ▼                                ▼                ▼
 ┌───────────┐                  ┌──────────────┐  ┌───────────────────┐
 │ rastreo   │                  │ mock-dhl     │  │ mock-coordinadora │
 └───────────┘                  │ (FastAPI)    │  │ (SoapUI)          │
                                └──────┬───────┘  └───────────────────┘
                                       └── webhook (JSON + JWT) ──► SIT

 auth emite los JWT de usuarios y servicios · PostgreSQL: una base por servicio
```

| Contenedor | Tecnología | Puerto interno | Puerto publicado |
|---|---|---|---|
| `auth` | Python 3.12 + FastAPI | 8000 | 8000 |
| `sit` | Python 3.12 + FastAPI | 8000 | 8010 |
| `despachos` | Python 3.12 + FastAPI | 8000 | 8020 |
| `rastreo` | Python 3.12 + FastAPI | 8000 | 8030 |
| `mock-dhl` | Python 3.12 + FastAPI | 8000 | 8082 |
| `mock-coordinadora` | Java + SoapUI (`mockservicerunner.sh`) | 8088 | 8088 |
| `postgres` | PostgreSQL 16 | 5432 | — |
| `redis` | Redis 7 | 6379 | — |

**Estilo de código.** Los servicios son síncronos: endpoints `def` de FastAPI, SQLAlchemy síncrono, `httpx.Client`, `zeep.Client`, consumidores de Redis en un hilo de fondo y APScheduler `BackgroundScheduler`. El objetivo es que el código se pueda explicar paso a paso sin introducir programación asíncrona.

**Paquete compartido `comun`** (`shared/`). Lo instalan todos los servicios propios, pero no los simuladores, que representan a terceros. Contiene:

- `comun/canonico.py`: el modelo canónico, que es el patrón *Canonical Schema* como modelo destino.
- `comun/eventos.py`: el sobre de los eventos, los nombres de los streams y la clase `Bus` para publicar y consumir.
- `comun/seguridad.py`: validación del JWT con la llave pública y la dependencia `requiere_roles(...)`.
- `comun/errores.py`: el error canónico y su manejador para FastAPI.

## 5. Modelo canónico (`comun/canonico.py`)

Son modelos Pydantic v2. Los nombres van en español con `snake_case`, y las fechas en ISO 8601 con zona horaria.

```python
class EstadoEnvio(str, Enum):        # nota de la Tabla 2
    CREADA, RECOGIDA, EN_TRANSITO, EN_REPARTO, ENTREGADA, NOVEDAD, DEVUELTA

class Direccion:          divipola: str (5 dígitos, municipio DANE), direccion: str,
                          nombre: str, telefono: str        # solo lo necesario (Ley 1581)
class Paquete:            peso_kg: float > 0, largo_cm: float > 0, ancho_cm: float > 0, alto_cm: float > 0

class SolicitudCotizacion: origen: str (divipola), destino: str (divipola),
                           paquetes: list[Paquete] (mín. 1), transportadora: str | None
class Cotizacion:          transportadora: str, valor_cop: int, peso_facturable_kg: float, dias_estimados: int

class SolicitudEnvio:      pedido_id: str, transportadora: str, origen: Direccion, destino: Direccion,
                           paquetes: list[Paquete] (mín. 1)
class Guia:                numero_guia: str, transportadora: str, pedido_id: str,
                           estado: EstadoEnvio, creada_en: datetime

class Franja(str, Enum):   MANANA, TARDE
class SolicitudRecogida:   numero_guia: str, fecha: date, franja: Franja
class Recogida:            numero_guia: str, transportadora: str, confirmacion: str, fecha: date, franja: Franja

class EventoEstado:        estado: EstadoEnvio, ocurrido_en: datetime

class Transportadora:      codigo, nombre, protocolo, version_api, adaptador,
                           frecuencia_sincronizacion_seg: int | None, version_equivalencias, activa: bool

class ErrorCanonico:       codigo: str, mensaje: str, transportadora: str | None
```

Datos de los eventos (sección 6):

```python
class PedidoConfirmado:       pedido_id: str, destino: Direccion, paquetes: list[Paquete],
                              transportadora: str | None
class GuiaCreada:             pedido_id: str, numero_guia: str, transportadora: str
class EnvioEstadoActualizado: numero_guia: str, transportadora: str, estado: EstadoEnvio, ocurrido_en: datetime
```

`EnvioEstadoActualizado` **nunca incluye el código del operador**, porque según el documento Despachos y Rastreo nunca reciben el formato del operador.

## 6. Eventos (Redis Streams)

- **Streams:** hay uno por tipo de evento, y el nombre del stream es el nombre del evento: `pedido.confirmado`, `guia.creada` y `envio.estado.actualizado`.
- **Formato de cada entrada:** un solo campo, `evento`, con el JSON del sobre:
  ```json
  {"id_evento": "<uuid4>", "tipo": "envio.estado.actualizado", "version": 1,
   "ocurrido_en": "2026-10-12T09:30:00-05:00", "datos": { ... }}
  ```
- **Grupos de consumidores:**

  | Stream | Grupo | Lo consume |
  |---|---|---|
  | `pedido.confirmado` | `despachos` | Despachos |
  | `envio.estado.actualizado` | `rastreo` | Rastreo |
  | `guia.creada` | — | Nadie en el prototipo. Lo consumen los servicios de contexto, que están fuera del alcance. |

- **`Bus.consumir(tipo, grupo, consumidor, manejar)`:**
  1. Crea el grupo si no existe (`XGROUP CREATE ... MKSTREAM`, desde `0`).
  2. Al arrancar, procesa primero sus mensajes pendientes (id `0`). Después lee los nuevos (`>`) con `BLOCK` de 5 s.
  3. Confirma con `XACK` solo si `manejar` termina sin excepción. Si lanza una, el mensaje queda pendiente y se reprocesa al reiniciar el consumidor.
- **Entrega al menos una vez:** un mensaje puede llegar dos veces. Rastreo descarta duplicados por `id_evento`, y Despachos es idempotente por `pedido_id`.

## 7. Transportadoras simuladas

Cada simulador tiene su propio modelo, distinto del canónico y del otro simulador. Esa diferencia es lo que demuestra el patrón.

| Aspecto | DHL (mock REST) | Coordinadora (mock SOAP) | Canónico |
|---|---|---|---|
| Protocolo | REST/JSON, autenticación básica | SOAP 1.1 document/literal | REST/JSON + JWT |
| Peso | libras (`lb`) | gramos (entero) | kg |
| Medidas | pulgadas (`in`) | cm (entero) | cm |
| Peso facturable | máx(real, L·W·H in³ / 139), redondeado hacia arriba a 0,5 lb | máx(real, L·W·H cm³ × 0,4 g) | lo calcula cada operador; el SIT lo pasa a kg |
| Ciudad | código propietario (`BOG`, `MDE`…) | DIVIPOLA de 8 dígitos (centro poblado: `11001000`) | DIVIPOLA de 5 dígitos (municipio: `11001`) |
| Estados | siglas (`SD`, `PU`…) | numéricos (`1`…`9`) | `EstadoEnvio` |
| Número de guía | 10 dígitos | 12 dígitos | texto |
| Fechas | `date` + `time` separados, hora local | `fecha` local sin zona | ISO 8601 con zona |
| Avisos de estado | webhook al SIT | ninguno (el SIT consulta) | evento |

Como los números de guía tienen longitudes distintas, son únicos entre transportadoras. Los precios de los dos simuladores son ilustrativos y deterministas:

- **DHL:** `18.000 + 3.500 × lb_facturables`, multiplicado por 1,4 si origen ≠ destino. Entrega en 1 día en la misma ciudad y en 2 días en otra.
- **Coordinadora:** `9.000 + 6.000 × ⌈kg_liquidados⌉`, multiplicado por 1,3 si origen ≠ destino. Entrega en 1 día en la misma ciudad y en 3 días en otra.

Con un paquete típico (2 kg, Bogotá → Medellín), Coordinadora resulta más barata y DHL más rápida.

### 7.1 Simulador DHL (`mocks/dhl`, FastAPI)

Está inspirado en la MyDHL API. Guarda el estado en memoria. Las rutas `/mydhlapi/*` exigen autenticación básica, con un usuario de configuración y la contraseña del secreto `dhl_api_password`.

| Método y ruta | Entrada (resumen) | Salida (resumen) |
|---|---|---|
| `POST /mydhlapi/rates` | `originCityCode`, `destinationCityCode`, `packages[{weight, dimensions{length,width,height}}]` en unidades imperiales | `products[{productCode, totalPrice[{price, priceCurrency:"COP"}], weight{volumetric, provided, unitOfMeasurement:"imperial"}, totalTransitDays}]` |
| `POST /mydhlapi/shipments` | `originCityCode`, `receiver{cityCode, name, address, phone}`, `packages[...]`, `reference` (pedido) | `shipmentTrackingNumber` (10 dígitos) |
| `POST /mydhlapi/pickups` | `shipmentTrackingNumber`, `plannedPickupDateAndTime` (`2026-10-12T09:00:00-05:00`) | `dispatchConfirmationNumbers[]` |
| `GET /mydhlapi/shipments/{n}/tracking` | — | `shipments[{shipmentTrackingNumber, events[{date, time, typeCode, description}]}]` |
| `POST /demo/envios/{n}/estado` | `{"typeCode": "PU"}` | Agrega el evento y envía el webhook. Es el panel de demo, sin autenticación. |
| `GET /salud` | — | `{"estado": "ok"}` |

- Si una ciudad no está en su lista de cobertura (`BOG`, `MDE`, `CLO`, `BAQ`, `CTG`, `BGA`), responde `400`.
- **Webhook.** Cuando se crea una guía (evento `SD`) y en cada cambio de estado, el simulador hace `POST {SIT}/api/v1/webhooks/dhl` en segundo plano, después de responder. El cuerpo es `{"shipmentTrackingNumber", "event": {"typeCode", "date", "time", "description"}}`. El token lo obtiene del servicio de autenticación con credenciales de cliente (`mock-dhl`).

### 7.2 Simulador Coordinadora (`mocks/coordinadora`, SoapUI)

- **Contrato:** `coordinadora.wsdl`, propio, SOAP 1.1 document/literal, espacio de nombres `http://coordinadora.simulada/guias`.
- **Proyecto:** `coordinadora-soapui-project.xml`, con el MockService `CoordinadoraMock` en el puerto 8088 y la ruta `/ws/guias`. El WSDL se sirve en `/ws/guias?WSDL`.
- **Estado de las guías:** se guarda en un archivo JSON dentro del contenedor, que leen y escriben los scripts Groovy del MockService con acceso sincronizado. Se pierde al reiniciar el contenedor, lo cual es aceptable para un simulador.

| Operación | Entrada | Salida |
|---|---|---|
| `CotizarFlete` | `ciudadOrigen`, `ciudadDestino` (DIVIPOLA de 8 dígitos), `piezas[{pesoGr, largoCm, anchoCm, altoCm}]` | `valorFlete` (COP), `pesoLiquidadoGr`, `diasEntrega` |
| `GenerarGuia` | `referencia` (pedido), `ciudadOrigen`, `destinatario{nombre, direccion, telefono, ciudad}`, `piezas[...]` | `codigoRemision` (12 dígitos). La guía queda en estado `1`. |
| `ProgramarRecogida` | `codigoRemision`, `fechaRecogida` (`AAAA-MM-DD`), `franja` (`AM`/`PM`) | `numeroRecogida` |
| `ConsultarEstadoGuia` | `codigoRemision` | `estados[{codigo, descripcion, fecha}]` (historial, el último al final) |
| `CambiarEstadoGuia` *(demo)* | `codigoRemision`, `codigoEstado` | `resultado` = `OK` |

Si una remisión no existe, la respuesta es un SOAP Fault.

### 7.3 Datos iniciales de las tablas de equivalencia

**Estados**

| DHL | Significado | Canónico | Coordinadora | Significado | Canónico |
|---|---|---|---|---|---|
| `SD` | Información de envío recibida | CREADA | `1` | Guía generada | CREADA |
| `PU` | Recogido | RECOGIDA | `2` | Recogida | RECOGIDA |
| `AF` | Llegó a instalación | EN_TRANSITO | `3` | En terminal de origen | EN_TRANSITO |
| `DF` | Salió de instalación | EN_TRANSITO | `4` | En transporte | EN_TRANSITO |
| `WC` | Con el mensajero | EN_REPARTO | `5` | En terminal de destino | EN_TRANSITO |
| `OK` | Entregado | ENTREGADA | `6` | En reparto | EN_REPARTO |
| `OH` | En espera | NOVEDAD | `7` | Entregada | ENTREGADA |
| `RT` | Devuelto al remitente | DEVUELTA | `8` | Novedad | NOVEDAD |
| | | | `9` | Devuelta al remitente | DEVUELTA |

Cualquier otro código, por ejemplo `XX` en la demo, no tiene equivalencia. Se publica como `NOVEDAD` y se registra (D2).

**Ciudades** (canónico = DIVIPOLA de 5 dígitos)

| Ciudad | Canónico | DHL | Coordinadora |
|---|---|---|---|
| Bogotá | `11001` | `BOG` | `11001000` |
| Medellín | `05001` | `MDE` | `05001000` |
| Cali | `76001` | `CLO` | `76001000` |
| Barranquilla | `08001` | `BAQ` | `08001000` |
| Cartagena | `13001` | `CTG` | `13001000` |
| Bucaramanga | `68001` | `BGA` | `68001000` |
| Pereira | `66001` | — (sin cobertura) | `66001000` |

**Unidades** (factor para pasar de la unidad del operador a la canónica)

| Transportadora | Magnitud | Unidad del operador | Factor |
|---|---|---|---|
| dhl | peso | lb | 0,45359237 |
| dhl | longitud | in | 2,54 |
| coordinadora | peso | g | 0,001 |
| coordinadora | longitud | cm | 1 |

**Catálogo**

| codigo | nombre | protocolo | version_api | adaptador | endpoint | frecuencia_sincronizacion_seg | version_equivalencias | activa |
|---|---|---|---|---|---|---|---|---|
| `dhl` | DHL Express (simulada) | REST | MyDHL API 2 (simulada) | `rest` | `http://mock-dhl:8000/mydhlapi` | — (webhook) | `2026.10-1` | sí |
| `coordinadora` | Coordinadora (simulada) | SOAP | Guías 1.0 (simulada) | `soap` | `http://mock-coordinadora:8088/ws/guias` | 10 | `2026.10-1` | sí |

## 8. SIT (`services/sit`)

### 8.1 Estructura

```
sit/
  main.py            app FastAPI; al arrancar: crea tablas, carga la semilla si el catálogo está vacío,
                     inicia el sincronizador
  config.py          configuración (pydantic-settings; secretos desde /run/secrets)
  api/               routers de la API canónica /api/v1
  catalogo/          modelos SQLAlchemy, consultas y semilla (semilla.sql)
  motor/             equivalencias.py (aplica tablas), motor.py, mapeadores/{dhl,coordinadora}.py
  adaptadores/       base.py (interfaz), rest.py (httpx), soap.py (zeep + lxml)
  sincronizador/     webhooks y consulta programada (APScheduler)
  servicio.py        casos de uso: cotizar, crear guía, recogida, consultar estados, procesar estado
```

### 8.2 Catálogo y tablas (PostgreSQL, base `sit`, SQLAlchemy 2)

| Tabla | Clave | Columnas |
|---|---|---|
| `transportadora` | `codigo` | `nombre`, `protocolo`, `version_api`, `adaptador`, `endpoint`, `frecuencia_sincronizacion_seg` (nula = webhook), `version_equivalencias`, `activa` |
| `equivalencia_estado` | (`transportadora`, `codigo_operador`) | `estado_canonico` |
| `equivalencia_ciudad` | (`transportadora`, `divipola`); `codigo_operador` único por transportadora | `codigo_operador` |
| `equivalencia_unidad` | (`transportadora`, `magnitud`) | `unidad_operador`, `factor_a_canonico` |
| `guia` | `numero` | `transportadora`, `pedido_id` (puede ser nulo un instante, ver 8.6), `ultimo_estado` (nulo hasta el primer estado), `eventos_leidos` (cuántos eventos del historial del operador ya procesó la consulta programada), `creada_en`, `actualizada_en` |
| `estado_sin_equivalencia` | `id`; única (`transportadora`, `codigo_operador`, `numero_guia`) | `registrado_en` |

Las dos últimas tablas son internas del SIT (sección 18). La semilla (`catalogo/semilla.sql`) carga los datos de la sección 7.3. Se ejecuta al arrancar, solo si `transportadora` está vacía.

### 8.3 Motor de transformación (patrón Data Model Transformation)

El motor separa dos cosas:

- **Tablas (datos):** `TablasEquivalencia`, que se cargan desde la base, con:
  - `estados: dict[codigo_operador, EstadoEnvio]`;
  - `ciudades: dict[divipola, codigo_operador]` y su inversa;
  - `unidades: dict[magnitud, (unidad, factor)]`.

  Las funciones de `equivalencias.py` son puras y no tocan la base, así que se prueban sin Docker:
  - `traducir_estado(codigo) -> Traduccion(estado, sin_equivalencia: bool)`. Si el código no existe, devuelve `NOVEDAD` con `sin_equivalencia=True`.
  - `ciudad_a_operador(divipola)`. Si la ciudad no existe, lanza `DESTINO_NO_CUBIERTO`.
  - `a_unidad_operador(magnitud, valor_canonico)` y `a_unidad_canonica(magnitud, valor_operador)`.
- **Mapeadores (estructura):** uno por operador, en `mapeadores/dhl.py` y `mapeadores/coordinadora.py`. Saben en qué campo del JSON o del XML va cada dato y usan las tablas para traducir valores. Cada mapeador produce un `MensajeOperador(operacion, cuerpo)` y lee la respuesta del operador:
  - `cotizacion(solicitud, tablas) -> MensajeOperador` y `leer_cotizacion(respuesta, tablas) -> Cotizacion`
  - `envio(solicitud, tablas) -> MensajeOperador` y `leer_guia(respuesta, solicitud) -> Guia`
  - `recogida(solicitud: SolicitudRecogida) -> MensajeOperador` y `leer_recogida(respuesta, solicitud) -> Recogida`
  - `consulta_estados(numero_guia) -> MensajeOperador` y `leer_estados(respuesta, tablas) -> list[(EventoEstado, codigo_operador, sin_equivalencia)]`
  - DHL además tiene `leer_webhook(cuerpo, tablas) -> (numero_guia, EventoEstado, codigo_operador, sin_equivalencia)`.

  Ejemplos de las transformaciones que hacen:
  - kg → lb y cm → in (DHL); kg → g y cm → cm enteros (Coordinadora).
  - DIVIPOLA → código propietario o DIVIPOLA de 8 dígitos.
  - `MANANA`/`TARDE` → `09:00`/`14:00` con zona horaria (DHL) o `AM`/`PM` (Coordinadora).
  - `date` + `time` locales → `datetime` con zona `-05:00`.
  - Peso facturable del operador → kg con 2 decimales.
- **`Motor`:** dado el código de una transportadora, entrega su mapeador, sus tablas y su adaptador, según el campo `adaptador` del catálogo. Así se cumple lo que dice el documento: "el catálogo indica qué adaptador y qué tablas de equivalencia usar".

### 8.4 Adaptadores (patrones Protocol Bridging y Data Format Transformation)

La interfaz común es `Adaptador.enviar(mensaje: MensajeOperador) -> dict`. Hay una implementación por protocolo, reutilizable por cualquier operador que use ese mismo protocolo (Figura 3B, paso 1):

- **`rest`** (`httpx.Client`): envía `operacion` como método y ruta, por ejemplo `POST /shipments`, contra el `endpoint` del catálogo. Usa autenticación básica con usuario de configuración y contraseña de secreto. Registra en el log el JSON enviado y recibido.
- **`soap`** (`zeep.Client`): carga el WSDL desde `endpoint?WSDL` la primera vez que se usa, invoca `operacion` y convierte la respuesta en `dict` (`zeep.helpers.serialize_object`). Un plugin de zeep registra en el log el XML enviado y recibido, formateado con `lxml`. Esos logs son la evidencia de "XML del operador frente a JSON canónico" para la sección del ejemplo funcional.
- **Reintentos** (Tabla 3): hasta 3 intentos, con esperas de 0,5 s y 1 s, ante errores de conexión, tiempos de espera o respuestas 5xx. Los SOAP Fault y las respuestas 4xx no se reintentan.

### 8.5 API canónica (`/api/v1`, Tabla 2)

| Método y ruta | Roles | Entrada | Respuesta |
|---|---|---|---|
| `POST /api/v1/cotizaciones` | operador_logistico, admin_integraciones | `SolicitudCotizacion` | `200 list[Cotizacion]`. Sin `transportadora`, cotiza con todas las activas: una que falle o no cubra el destino se omite y queda en el log, y si ninguna cotiza responde `502 SIN_COTIZACIONES`. Con `transportadora`, cotiza solo con esa y sus errores se devuelven tal cual (por ejemplo, `422 DESTINO_NO_CUBIERTO`). |
| `POST /api/v1/envios` | operador_logistico, admin_integraciones | `SolicitudEnvio` | `201 Guia` (estado `CREADA`) |
| `POST /api/v1/recogidas` | operador_logistico, admin_integraciones | `SolicitudRecogida` | `201 Recogida`. La transportadora sale de la tabla `guia`. |
| `GET /api/v1/envios/{numero_guia}/estados` | operador_logistico, admin_integraciones | — | `200 list[EventoEstado]`, consultando en vivo al operador. |
| `POST /api/v1/webhooks/{transportadora}` | operador_logistico | cuerpo en el formato del operador | `204`. Procesa el estado (8.6). |
| `GET /api/v1/transportadoras` | operador_logistico, admin_integraciones | — | `200 list[Transportadora]` |
| `GET /salud` | — (sin token) | — | `200 {"estado": "ok"}` |

FastAPI genera el contrato OpenAPI en `/openapi.json` y la documentación en `/docs`.

**Errores canónicos** (`ErrorCanonico`, para que nunca se reenvíe el error crudo del operador):

| Código | HTTP | Cuándo |
|---|---|---|
| `TRANSPORTADORA_DESCONOCIDA` | 422 | No está en el catálogo, está inactiva o no recibe webhooks. |
| `DESTINO_NO_CUBIERTO` | 422 | La ciudad no está en sus tablas. |
| `GUIA_NO_ENCONTRADA` | 404 | El SIT no conoce la guía. |
| `TRANSPORTADORA_SIN_RESPUESTA` | 502 | Se agotaron los reintentos. |
| `TRANSPORTADORA_RECHAZO` | 502 | El operador respondió 4xx o un SOAP Fault. |
| `SIN_COTIZACIONES` | 502 | Ninguna transportadora cotizó. |

### 8.6 Sincronizador de estados

- **Webhook (DHL):** `POST /api/v1/webhooks/dhl` → `mapeador.leer_webhook` → `procesar_estado(...)`.
- **Consulta programada (Coordinadora):** al arrancar, por cada transportadora activa con `frecuencia_sincronizacion_seg` (10 s en la semilla), se programa un trabajo de APScheduler. El trabajo consulta `ConsultarEstadoGuia` para cada guía de esa transportadora cuyo `ultimo_estado` no sea `ENTREGADA` ni `DEVUELTA`, procesa en orden los eventos del historial que aún no había leído (`eventos_leidos`) y llama a `procesar_estado(...)` con cada uno. Así no se pierde ningún estado aunque cambie varias veces entre dos consultas.
- **`procesar_estado(transportadora, numero_guia, evento, codigo_operador, sin_equivalencia)`:**
  1. Si `sin_equivalencia`, registra la fila en `estado_sin_equivalencia` (idempotente) y escribe un aviso en el log.
  2. Si el estado canónico es distinto de `guia.ultimo_estado`, actualiza la guía y publica `envio.estado.actualizado`. Si es igual, no publica nada; por ejemplo, `AF` → `DF` siguen siendo `EN_TRANSITO`.
- **El primer estado viene del operador:**
  - DHL envía el webhook `SD` al crear la guía (→ `CREADA`).
  - En Coordinadora, la primera consulta encuentra `1` (→ `CREADA`).
- **Carrera webhook/creación:** el webhook de creación de DHL puede llegar antes de que el SIT guarde la guía. Por eso el registro de la guía funciona como *upsert* en los dos caminos: crea la fila si no existe y completa `pedido_id` si estaba vacío. Si dos inserciones chocan (`IntegrityError`), se reintenta una vez como actualización.
- **Traducción en `GET .../estados`:** traduce también los estados sin equivalencia y los registra con la misma lógica idempotente, pero no publica eventos.

## 9. Despachos (`services/despachos`, orquestador)

**Identificador.** Hay un despacho por pedido, así que **el id del despacho es el `pedido_id`**.

**Modelo `despacho`** (base `despachos`):
- `pedido_id` (clave);
- `estado`: `PENDIENTE` | `GUIA_CREADA` | `RECOGIDA_PROGRAMADA` | `FALLIDO`;
- `transportadora_solicitada`, `transportadora`, `cotizaciones` (JSON), `numero_guia`, `confirmacion_recogida`, `evento_publicado` (bool);
- `solicitud` (JSON con destino y paquetes, para poder reintentar), `error`, `creado_en`, `actualizado_en`.

**Activación:**
- consumidor del stream `pedido.confirmado` (grupo `despachos`), o
- `POST /api/v1/despachos` con cuerpo `PedidoConfirmado` ("reintento o despacho manual").

**`procesar_pedido(pedido)`** retoma desde el primer paso que no tenga resultado guardado:

1. Si no hay transportadora: `POST {SIT}/api/v1/cotizaciones` desde el origen configurado (bodega en Bogotá, `11001`). Si el pedido fuerza una transportadora, la solicitud lleva ese `transportadora` y el SIT cotiza solo con ella. Luego `elegir(cotizaciones, transportadora_forzada)`: la forzada o, si no hay, la de menor `valor_cop`; en caso de empate, la de menos `dias_estimados` y luego la de menor `codigo`.
2. Si no hay guía: `POST {SIT}/api/v1/envios`. Estado → `GUIA_CREADA`.
3. Si no hay recogida: `POST {SIT}/api/v1/recogidas` para el día siguiente, en la franja `MANANA`.
4. Si el evento no se ha publicado: publica `guia.creada`. Estado → `RECOGIDA_PROGRAMADA`.

Si cualquier paso falla, el estado pasa a `FALLIDO` y se guarda el error canónico en `error`. Un nuevo `POST` del mismo pedido reanuda desde el primer paso sin resultado guardado. Si el despacho ya está en `RECOGIDA_PROGRAMADA`, se devuelve tal cual, sin repetir nada.

**Llamadas al SIT:** usan un token de credenciales de cliente (`despachos`, rol `operador_logistico`). El token se guarda en caché hasta 30 s antes de expirar. **Despachos no tiene ninguna lógica de mapeo.**

**API:**

| Método y ruta | Roles | Respuesta |
|---|---|---|
| `POST /api/v1/despachos` | agente_servicio, operador_logistico | `201 Despacho` si se creó y completó; `200 Despacho` si ya existía o se reanudó; `502 Despacho` (estado `FALLIDO`) si falló. |
| `GET /api/v1/despachos/{pedido_id}` | agente_servicio, operador_logistico | `200 Despacho`, o `404` |
| `GET /salud` | — | `200` |

`Despacho` (respuesta) tiene: `pedido_id`, `estado`, `transportadora`, `numero_guia`, `confirmacion_recogida`, `cotizaciones: list[Cotizacion]`, `error`, `creado_en`, `actualizado_en`.

**Consumidor:** procesa el pedido y confirma el mensaje. Los fallos de negocio quedan como `FALLIDO` y se confirman igual, porque se reintentan con `POST`. Solo un error de infraestructura, por ejemplo la base caída, deja el mensaje pendiente.

## 10. Rastreo (`services/rastreo`)

- **Modelo `estado_registrado`** (base `rastreo`): `id`, `id_evento` (único), `numero_guia` (con índice), `transportadora`, `estado`, `ocurrido_en`, `recibido_en`.
- **Consumidor** del stream `envio.estado.actualizado` (grupo `rastreo`): inserta el estado. Si el `id_evento` ya existe, lo ignora (`IntegrityError`) y confirma el mensaje.
- **API:**

  | Método y ruta | Roles | Respuesta |
  |---|---|---|
  | `GET /api/v1/rastreo/{guia}` | cliente, agente_servicio, operador_logistico | `200 {numero_guia, transportadora, estado_actual, historial: list[EventoEstado]}`, ordenado por `ocurrido_en`; o `404 GUIA_NO_ENCONTRADA` |
  | `GET /salud` | — | `200` |

## 11. Autenticación y seguridad (`services/auth`)

- **`POST /oauth/token`** (RFC 6749, `application/x-www-form-urlencoded`):
  - `grant_type=password` con `username` y `password`. Son los usuarios de los canales y corresponde a "al iniciar sesión".
  - `grant_type=client_credentials` con `client_id` y `client_secret`, en el cuerpo o con autenticación básica. Lo usan los servicios.
  - Respuesta: `{"access_token", "token_type": "Bearer", "expires_in": 900}`.
  - Errores según el RFC: `400 invalid_grant`, `401 invalid_client` y `400 unsupported_grant_type`.
- **Token:** JWT RS256 con `iss = "auth-plataforma"`, `sub`, `roles`, `iat` y `exp` (15 minutos). La llave privada solo la tiene `auth`. Los demás servicios validan la firma con la llave pública, según el documento.
- **Roles del documento:** `cliente`, `agente_servicio`, `operador_logistico` y `admin_integraciones`. Los clientes de servicio reciben uno de esos roles; no se crea un rol nuevo.

| Identidad | Tipo | Roles |
|---|---|---|
| `cliente1` | usuario | cliente |
| `agente1` | usuario | agente_servicio |
| `operador1` | usuario | operador_logistico |
| `admin1` | usuario | admin_integraciones |
| `despachos` | cliente de servicio | operador_logistico |
| `mock-dhl` | cliente de servicio (webhook) | operador_logistico |

- **Datos de identidad:** las contraseñas de los usuarios de demo y los secretos de los clientes salen de Docker secrets. Al arrancar, `auth` los guarda con hash `bcrypt` en su base. Este paso es idempotente.
- **`comun.seguridad.requiere_roles(*roles)`:** es una dependencia de FastAPI que valida firma, `iss` y `exp`, y responde `401` si el token falta o no es válido, o `403` si falta el rol.
- **Datos personales:** los destinatarios se limitan a nombre, dirección, teléfono y ciudad (Ley 1581).

## 12. Configuración y secretos

**Configuración:** `pydantic-settings`, con variables de entorno para la configuración y `secrets_dir=/run/secrets` para los secretos.

**Secretos:** están en `secrets/`, que no se sube a git. Los genera `scripts/generar-secretos.sh` con `openssl`.

| Secreto | Lo usan |
|---|---|
| `jwt_privada` (PEM) | auth |
| `jwt_publica` (PEM) | sit, despachos, rastreo |
| `postgres_password` | postgres, auth, sit, despachos, rastreo |
| `dhl_api_password` | sit, mock-dhl |
| `cliente_despachos_secret` | auth, despachos |
| `cliente_mock_dhl_secret` | auth, mock-dhl |
| `usuarios_demo_password` (una contraseña común para los cuatro usuarios de demo) | auth (y Postman o la prueba de punta a punta para iniciar sesión) |

Las credenciales de las transportadoras nunca están en el código ni en el repositorio, como dice la sección *Seguridad*.

## 13. Despliegue (Docker Compose)

- **Arranque:** `docker compose up --build` levanta los 8 contenedores de la sección 4.
- **Imágenes propias:** `python:3.12-slim`, con contexto de construcción en la raíz para poder instalar `shared/`, y `uvicorn <paquete>.main:app`.
- **Chequeos de salud:**
  - los servicios Python consultan `GET /salud` con `python -c` (sin curl);
  - `postgres` usa `pg_isready`;
  - `redis` usa `redis-cli ping`;
  - `mock-coordinadora` consulta el WSDL.
- **Orden de arranque** (`depends_on` con `service_healthy`):
  - `auth` → postgres;
  - `sit` → postgres, redis;
  - `despachos` → postgres, redis, auth, sit;
  - `rastreo` → postgres, redis;
  - `mock-dhl` → auth.

  El SIT no depende de los simuladores para arrancar, porque crea los clientes de zeep y httpx al primer uso.
- **Base de datos:** un solo `postgres` con un script de inicio (`infra/postgres/01-bases.sql`) que crea las bases `sit`, `despachos`, `rastreo` y `auth`. Ningún servicio lee la base de otro (bajo acoplamiento, Tabla 3).
- **Esquema:** las tablas se crean con SQLAlchemy (`create_all`) al arrancar cada servicio. Por tamaño del prototipo, no hay migraciones.

## 14. Pruebas y CI

- **Unitarias (pytest)**, sin Docker, con SQLite en memoria, dobles del SIT y del bus, y llaves JWT generadas en la prueba:
  - **comun:** validación del modelo canónico, del sobre de eventos y de los tokens. Casos: válido, vencido, firma ajena y rol faltante.
  - **sit:**
    - cada mapeador en las dos direcciones;
    - conversión de unidades;
    - estados de varios a uno;
    - código desconocido → `NOVEDAD` + registro;
    - ciudad sin cobertura;
    - `procesar_estado`, que publica solo los cambios;
    - *upsert* de la guía;
    - la API con adaptadores falsos.
  - **despachos:** `elegir` (más barata, forzada, empate), `procesar_pedido` de punta a punta con dobles, reanudación de un `FALLIDO` e idempotencia.
  - **rastreo:** consumo, descarte de duplicados y respuesta de `GET`.
  - **auth:** los dos flujos, credenciales inválidas, tipo de flujo no soportado y contenido del token.
  - **mock-dhl:** cálculo de peso volumétrico y precio, y cambio de estado con webhook (cliente HTTP falso).
- **De punta a punta** (`tests/e2e`, marca `e2e`): requiere el Compose en ejecución y repite el guion de la sección 15 contra `localhost`. Espera los efectos asíncronos con sondeo, hasta 30 s.
- **Configuración común:** un solo `pytest` en la raíz, con `--import-mode=importlib` y nombres de paquete únicos por servicio (`sit`, `despachos`, `rastreo`, `auth`, `mock_dhl`).
- **GitHub Actions** (Tabla 4): `.github/workflows/pruebas.yml` instala Python 3.12 y `requirements-dev.txt` y ejecuta `pytest -m "not e2e"`. La prueba de punta a punta no corre en CI, porque construir el simulador de SoapUI en cada ejecución la hace pesada.
- **Dependencias:** las versiones se fijan en los `requirements.txt` de cada servicio para que el equipo obtenga el mismo resultado.

## 15. Demo (colección de Postman)

Se usan `postman/Entrega3.postman_collection.json` y `postman/Local.postman_environment.json`. El entorno no incluye contraseñas: se llenan una vez desde `secrets/`. Este guion es la base del ejemplo funcional y del video:

1. **Tokens.** Iniciar sesión como `agente1`, `operador1`, `admin1` y `cliente1`.
2. **Pedido A, forzando DHL.** `POST /api/v1/despachos` (`PED-1001`, Medellín, `transportadora: "dhl"`). Devuelve `201` con una guía de 10 dígitos.
3. **Pedido B, forzando Coordinadora, por evento.** `scripts/publicar-pedido.sh PED-1002 coordinadora` ejecuta `XADD` en `pedido.confirmado`. Luego, `GET /api/v1/despachos/PED-1002` muestra una guía de 12 dígitos.
4. **Mismo formato.** Las guías A y B se comparan lado a lado: la misma estructura canónica.
5. **Pedido C, sin forzar.** La respuesta muestra las dos cotizaciones en COP y kg, ya comparables, y la elección de la más barata.
6. **Cambio de estado en DHL.** `POST :8082/demo/envios/{guiaA}/estado {"typeCode":"PU"}`, y después `GET /api/v1/rastreo/{guiaA}` muestra `RECOGIDA`.
7. **Cambio de estado en Coordinadora.** Petición SOAP `CambiarEstadoGuia` (`codigoEstado` 6) a `:8088/ws/guias`. A los 10 s o menos, `GET /api/v1/rastreo/{guiaB}` muestra `EN_REPARTO`.
8. **Estado sin equivalencia.** Código `XX` en DHL: Rastreo muestra `NOVEDAD`, y el log del SIT y la tabla `estado_sin_equivalencia` muestran el registro.
9. **Consulta en vivo.** `GET /api/v1/envios/{guiaB}/estados` como `operador1`: el historial de Coordinadora ya traducido.
10. **Catálogo.** `GET /api/v1/transportadoras` como `admin1`.
11. **Seguridad.** `POST /api/v1/despachos` como `cliente1` → `403`.

## 16. Estructura del repositorio

```
repository/
  README.md                    paso a paso: requisitos, secretos, arranque, demo, pruebas,
                               cómo agregar una transportadora (Figura 3B)
  docker-compose.yml
  pytest.ini
  requirements-dev.txt
  .gitignore                   secrets/, .venv/, __pycache__/, etc.
  .github/workflows/pruebas.yml
  docs/specs/                  esta especificación
  docs/plans/                  plan de implementación
  infra/postgres/01-bases.sql
  scripts/generar-secretos.sh
  scripts/publicar-pedido.sh
  shared/                      pyproject.toml, comun/, tests/
  services/auth/               Dockerfile, requirements.txt, auth/, tests/
  services/sit/                Dockerfile, requirements.txt, sit/, tests/
  services/despachos/          Dockerfile, requirements.txt, despachos/, tests/
  services/rastreo/            Dockerfile, requirements.txt, rastreo/, tests/
  mocks/dhl/                   Dockerfile, requirements.txt, mock_dhl/, tests/
  mocks/coordinadora/          Dockerfile, coordinadora.wsdl, coordinadora-soapui-project.xml
  postman/                     colección y entorno
  tests/e2e/                   prueba de punta a punta
```

## 17. Trazabilidad: documento → prototipo

| Lo que dice el documento | Dónde se cumple |
|---|---|
| Se conserva SOA; los servicios se construyen con REST; SOAP queda confinado al adaptador de las transportadoras que lo exigen (*Modelo arquitectónico*). | Secciones 4 y 8.4. Solo `adaptadores/soap.py` conoce SOAP. |
| El modelo canónico se publica como contrato OpenAPI (*Modelo arquitectónico*; Tabla 4). | 8.5: `/openapi.json` en cada servicio. |
| Servicios en Python con FastAPI, desplegados en un solo equipo con Docker Compose. | Secciones 4 y 13. |
| SIT: API canónica hacia adentro; REST, SOAP o SFTP hacia afuera; único componente que conoce el modelo de cada operador (Figura 1). | Sección 8. SFTP queda fuera (2.2). |
| Data Model Transformation como patrón principal; Canonical Schema como modelo destino; Legacy Wrapper solo en SFTP (*Selección del patrón*, Tabla 1). | 8.3 (motor) y 5 (`comun.canonico`). |
| Tabla 2: endpoints del SIT, de Despachos y de Rastreo. | 8.5, 9 y 10 (las mismas rutas y métodos). |
| Despachos: se activa con `pedido.confirmado`; cotiza, elige, crea la guía, programa la recogida y publica `guia.creada`; sin lógica de mapeo. | Sección 9. |
| Rastreo: consume `envio.estado.actualizado` y guarda solo estados canónicos. | Sección 10. |
| Estados canónicos CREADA … DEVUELTA (nota de la Tabla 2). | `EstadoEnvio` (sección 5). |
| Tabla 3, Aplicación 1–4: esquema canónico; tablas de estados, ciudades (DIVIPOLA) y unidades; mapeadores y un adaptador por protocolo; migrar los servicios internos. | 5, 7.3, 8.3, 8.4 y 9–10. |
| Tabla 3, Impacto: se mitiga con reintentos. | 8.4. |
| Tabla 3, Relaciones: Data Format Transformation (JSON/XML) y Protocol Bridging (REST/SOAP). | 8.3–8.4. |
| Eventos JSON canónicos en Redis Streams con grupos de consumidores. | Sección 6. |
| Webhooks REST en `POST /api/v1/webhooks/{transportadora}`; consulta programada SOAP con la frecuencia del catálogo. | 8.6. |
| Estado sin equivalencia → `NOVEDAD` y registro. | 8.3, 8.6 y D2. |
| Despachos es el orquestador; propagación de estados por eventos, como coreografía. | Secciones 9 y 6. |
| Catálogo en PostgreSQL con protocolo, versión de API, adaptador activo, frecuencia y versión de tablas (`GET /api/v1/transportadoras`). | 8.2 y 7.3. |
| Incorporar una transportadora en 4 pasos (Figura 3B). | Catálogo con `activa`, adaptadores reutilizables y README. |
| Contenedores ubicados por nombre en la red de Compose; Consul queda como diseño. | Secciones 13 y 2.2. |
| OAuth 2.0 con servicio propio en FastAPI; JWT firmados; canales al iniciar sesión y servicios con credenciales de cliente; validación con llave pública; los cuatro roles. | Sección 11. |
| Credenciales de las transportadoras como Docker secrets, nunca en el código. | Sección 12. |
| Datos de destinatarios limitados a lo necesario (Ley 1581). | `Direccion` (sección 5). |
| Tabla 4: Python 3.12, FastAPI, Pydantic, lxml, PostgreSQL + SQLAlchemy, httpx, zeep, APScheduler, Redis Streams (redis-py), PyJWT, Docker secrets, mock REST en FastAPI, mock SOAP en SoapUI, pytest, Postman, Docker Compose, GitHub Actions. | Secciones 4, 8, 12, 13 y 14. paramiko, Traefik y Consul quedan fuera por el alcance de la E3. |
| Demo: un pedido por transportadora; ambas guías en el mismo formato canónico; cambiar el estado en cada simulador y verlo en `GET /api/v1/rastreo/{guia}`. | Sección 15, pasos 2–7. |
| Orden de implementación: modelo canónico y tablas → SIT con adaptadores y sincronizador → (SFTP) → migración de servicios internos (*Plan de implementación técnica*). | Orden de construcción de la sección 20. |

## 18. Detalles que completan el documento sin contradecirlo

El documento no los menciona, pero el prototipo los necesita:

- Las tablas internas del SIT `guia` y `estado_sin_equivalencia`, y el *upsert* de la guía (8.2, 8.6).
- Los modelos concretos de cada simulador: unidades, códigos, formato de las guías y precios (sección 7).
- La regla de elección de transportadora y la opción de forzarla (D3).
- El id del despacho igual al `pedido_id`, y la reanudación por pasos (sección 9).
- Los endpoints de demo de los simuladores (`/demo/...` y `CambiarEstadoGuia`) y `GET /salud` en cada servicio.
- Los nombres técnicos de los roles en `snake_case` y los usuarios de demo (sección 11).
- `scripts/publicar-pedido.sh`, para "publicar ese evento" desde la terminal durante la demo.

## 19. Riesgos y verificación temprana

| Riesgo | Mitigación |
|---|---|
| `mockservicerunner.sh` de SoapUI en un contenedor: la versión de Java compatible y el manejo de estado con Groovy. | Es la **primera tarea** del plan: una prueba corta con SoapUI 5.7.2 (descarga verificada) y una JRE. Si Java 17 falla, se usa Java 11 u 8. |
| zeep con el WSDL servido por SoapUI, que puede reescribir la dirección del servicio. | El adaptador crea el servicio con la dirección del catálogo (`client.create_service`), sin depender de la del WSDL. |
| Carrera entre el webhook de creación de DHL y el registro de la guía. | *Upsert* idempotente (8.6) y prueba unitaria específica. |
| Diferencias entre SQLite (pruebas) y PostgreSQL (Compose). | Solo SQLAlchemy portable, sin `ON CONFLICT` específico de PostgreSQL. Los duplicados se manejan con `IntegrityError`. La prueba de punta a punta corre sobre PostgreSQL. |

## 20. Orden de construcción

Sigue el orden de la sección *Plan de implementación técnica* del documento:

0. Verificación temprana del simulador SoapUI (sección 19).
1. Esqueleto del repositorio, `comun` (modelo canónico, eventos, errores y seguridad) y `auth`.
2. Simuladores DHL y Coordinadora.
3. SIT: catálogo y tablas de equivalencia, motor y mapeadores, adaptadores REST y SOAP, API canónica y sincronizador.
4. Despachos y Rastreo, que es la "migración de los servicios internos a la API canónica".
5. Docker Compose completo, prueba de punta a punta, colección de Postman, README y GitHub Actions.
