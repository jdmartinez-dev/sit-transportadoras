"""Mapeador Coordinadora: modelo canónico <-> WSDL propio de la Coordinadora simulada (gramos, DIVIPOLA de 8 dígitos)."""
import math
from datetime import datetime

from comun.canonico import (ZONA_COLOMBIA, Cotizacion, EstadoEnvio, EventoEstado, Franja, Guia, Paquete, Recogida,
                            SolicitudCotizacion, SolicitudEnvio, SolicitudRecogida, ahora)
from sit.motor.equivalencias import TablasEquivalencia
from sit.motor.tipos import EstadoLeido, MensajeOperador

FRANJA = {Franja.MANANA: "AM", Franja.TARDE: "PM"}


class MapeadorCoordinadora:
    codigo = "coordinadora"

    def _piezas(self, paquetes: list[Paquete], tablas: TablasEquivalencia) -> list[dict]:
        return [{
            "pesoGr": round(tablas.a_unidad_operador("peso", p.peso_kg)),
            "largoCm": math.ceil(tablas.a_unidad_operador("longitud", p.largo_cm)),
            "anchoCm": math.ceil(tablas.a_unidad_operador("longitud", p.ancho_cm)),
            "altoCm": math.ceil(tablas.a_unidad_operador("longitud", p.alto_cm)),
        } for p in paquetes]

    def cotizacion(self, solicitud: SolicitudCotizacion, tablas: TablasEquivalencia) -> MensajeOperador:
        return MensajeOperador("CotizarFlete", {
            "ciudadOrigen": tablas.ciudad_a_operador(solicitud.origen),
            "ciudadDestino": tablas.ciudad_a_operador(solicitud.destino),
            "piezas": self._piezas(solicitud.paquetes, tablas),
        })

    def leer_cotizacion(self, respuesta: dict, tablas: TablasEquivalencia) -> Cotizacion:
        return Cotizacion(
            transportadora=self.codigo,
            valor_cop=int(respuesta["valorFlete"]),
            peso_facturable_kg=round(tablas.a_unidad_canonica("peso", respuesta["pesoLiquidadoGr"]), 2),
            dias_estimados=int(respuesta["diasEntrega"]),
        )

    def envio(self, solicitud: SolicitudEnvio, tablas: TablasEquivalencia) -> MensajeOperador:
        destino = solicitud.destino
        return MensajeOperador("GenerarGuia", {
            "referencia": solicitud.pedido_id,
            "ciudadOrigen": tablas.ciudad_a_operador(solicitud.origen.divipola),
            "destinatario": {"nombre": destino.nombre, "direccion": destino.direccion, "telefono": destino.telefono,
                             "ciudad": tablas.ciudad_a_operador(destino.divipola)},
            "piezas": self._piezas(solicitud.paquetes, tablas),
        })

    def leer_guia(self, respuesta: str, solicitud: SolicitudEnvio) -> Guia:
        # GenerarGuiaRespuesta tiene un solo elemento (codigoRemision): zeep lo entrega como texto.
        return Guia(numero_guia=str(respuesta), transportadora=self.codigo, pedido_id=solicitud.pedido_id,
                    estado=EstadoEnvio.CREADA, creada_en=ahora())

    def recogida(self, solicitud: SolicitudRecogida) -> MensajeOperador:
        return MensajeOperador("ProgramarRecogida", {"codigoRemision": solicitud.numero_guia,
                                                      "fechaRecogida": solicitud.fecha.isoformat(),
                                                      "franja": FRANJA[solicitud.franja]})

    def leer_recogida(self, respuesta: str, solicitud: SolicitudRecogida) -> Recogida:
        return Recogida(numero_guia=solicitud.numero_guia, transportadora=self.codigo, confirmacion=str(respuesta),
                        fecha=solicitud.fecha, franja=solicitud.franja)

    def consulta_estados(self, numero_guia: str) -> MensajeOperador:
        return MensajeOperador("ConsultarEstadoGuia", {"codigoRemision": numero_guia})

    def leer_estados(self, respuesta: dict, tablas: TablasEquivalencia) -> list[EstadoLeido]:
        return [self._leer_estado(estado, tablas) for estado in respuesta["estados"]]

    def _leer_estado(self, estado: dict, tablas: TablasEquivalencia) -> EstadoLeido:
        codigo = str(estado["codigo"])
        momento = datetime.fromisoformat(estado["fecha"]).replace(tzinfo=ZONA_COLOMBIA)
        traduccion = tablas.traducir_estado(codigo)
        return EstadoLeido(EventoEstado(estado=traduccion.estado, ocurrido_en=momento), codigo,
                           traduccion.sin_equivalencia)
