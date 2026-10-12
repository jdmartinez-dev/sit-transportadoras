"""Mapeador DHL: modelo canónico <-> modelo de la MyDHL API simulada (JSON, unidades imperiales, códigos propios)."""
from datetime import datetime, time

from comun.canonico import (ZONA_COLOMBIA, Cotizacion, EstadoEnvio, EventoEstado, Franja, Guia, Paquete, Recogida,
                            SolicitudCotizacion, SolicitudEnvio, SolicitudRecogida, ahora)
from comun.errores import ErrorPlataforma
from sit.motor.equivalencias import TablasEquivalencia
from sit.motor.tipos import EstadoLeido, MensajeOperador

HORA_FRANJA = {Franja.MANANA: time(9, 0), Franja.TARDE: time(14, 0)}


class MapeadorDHL:
    codigo = "dhl"

    def _paquetes(self, paquetes: list[Paquete], tablas: TablasEquivalencia) -> list[dict]:
        return [{
            "weight": round(tablas.a_unidad_operador("peso", p.peso_kg), 2),
            "dimensions": {
                "length": round(tablas.a_unidad_operador("longitud", p.largo_cm), 1),
                "width": round(tablas.a_unidad_operador("longitud", p.ancho_cm), 1),
                "height": round(tablas.a_unidad_operador("longitud", p.alto_cm), 1),
            },
        } for p in paquetes]

    def cotizacion(self, solicitud: SolicitudCotizacion, tablas: TablasEquivalencia) -> MensajeOperador:
        return MensajeOperador("POST /rates", {
            "originCityCode": tablas.ciudad_a_operador(solicitud.origen),
            "destinationCityCode": tablas.ciudad_a_operador(solicitud.destino),
            "packages": self._paquetes(solicitud.paquetes, tablas),
        })

    def leer_cotizacion(self, respuesta: dict, tablas: TablasEquivalencia) -> Cotizacion:
        producto = respuesta["products"][0]
        peso = producto["weight"]
        facturable_lb = max(peso["volumetric"], peso["provided"])
        return Cotizacion(
            transportadora=self.codigo,
            valor_cop=round(producto["totalPrice"][0]["price"]),
            peso_facturable_kg=round(tablas.a_unidad_canonica("peso", facturable_lb), 2),
            dias_estimados=int(producto["totalTransitDays"]),
        )

    def envio(self, solicitud: SolicitudEnvio, tablas: TablasEquivalencia) -> MensajeOperador:
        destino = solicitud.destino
        return MensajeOperador("POST /shipments", {
            "originCityCode": tablas.ciudad_a_operador(solicitud.origen.divipola),
            "receiver": {"cityCode": tablas.ciudad_a_operador(destino.divipola), "name": destino.nombre,
                         "address": destino.direccion, "phone": destino.telefono},
            "packages": self._paquetes(solicitud.paquetes, tablas),
            "reference": solicitud.pedido_id,
        })

    def leer_guia(self, respuesta: dict, solicitud: SolicitudEnvio) -> Guia:
        return Guia(numero_guia=respuesta["shipmentTrackingNumber"], transportadora=self.codigo,
                    pedido_id=solicitud.pedido_id, estado=EstadoEnvio.CREADA, creada_en=ahora())

    def recogida(self, solicitud: SolicitudRecogida) -> MensajeOperador:
        momento = datetime.combine(solicitud.fecha, HORA_FRANJA[solicitud.franja], tzinfo=ZONA_COLOMBIA)
        return MensajeOperador("POST /pickups", {"shipmentTrackingNumber": solicitud.numero_guia,
                                                  "plannedPickupDateAndTime": momento.isoformat()})

    def leer_recogida(self, respuesta: dict, solicitud: SolicitudRecogida) -> Recogida:
        return Recogida(numero_guia=solicitud.numero_guia, transportadora=self.codigo,
                        confirmacion=respuesta["dispatchConfirmationNumbers"][0], fecha=solicitud.fecha,
                        franja=solicitud.franja)

    def consulta_estados(self, numero_guia: str) -> MensajeOperador:
        return MensajeOperador(f"GET /shipments/{numero_guia}/tracking")

    def leer_estados(self, respuesta: dict, tablas: TablasEquivalencia) -> list[EstadoLeido]:
        return [self._leer_evento(evento, tablas) for evento in respuesta["shipments"][0]["events"]]

    def leer_webhook(self, cuerpo: dict, tablas: TablasEquivalencia) -> tuple[str, EstadoLeido]:
        try:
            return cuerpo["shipmentTrackingNumber"], self._leer_evento(cuerpo["event"], tablas)
        except (KeyError, TypeError, ValueError) as exc:
            raise ErrorPlataforma(400, "WEBHOOK_INVALIDO", f"Cuerpo del webhook de {self.codigo} inválido",
                                  self.codigo) from exc

    def _leer_evento(self, evento: dict, tablas: TablasEquivalencia) -> EstadoLeido:
        # DHL separa fecha y hora locales; el modelo canónico usa un instante con zona horaria.
        momento = datetime.fromisoformat(f"{evento['date']}T{evento['time']}").replace(tzinfo=ZONA_COLOMBIA)
        traduccion = tablas.traducir_estado(evento["typeCode"])
        return EstadoLeido(EventoEstado(estado=traduccion.estado, ocurrido_en=momento), evento["typeCode"],
                           traduccion.sin_equivalencia)
