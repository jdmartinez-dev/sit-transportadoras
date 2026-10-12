"""Adaptador SOAP (zeep + lxml): puente de protocolo hacia las transportadoras que exponen SOAP/XML.

SOAP queda confinado aquí: ningún otro componente de la plataforma conoce WSDL ni XML.
"""
import logging
import time
from typing import Any

import requests
from lxml import etree
from zeep import Client, Plugin
from zeep.exceptions import Error as ErrorZeep, Fault, TransportError
from zeep.helpers import serialize_object
from zeep.transports import Transport

from comun.errores import ErrorPlataforma
from sit.motor.tipos import MensajeOperador
from sit.adaptadores.redaccion import redactar_xml

log = logging.getLogger(__name__)
ESPERAS = (0.5, 1.0)



class BitacoraXML(Plugin):
    """Registra XML SOAP ocultando información sensible."""

    def __init__(self, transportadora: str):
        self._transportadora = transportadora

    def egress(self, envelope, http_headers, operation, binding_options):
        log.info(
            "[%s] XML enviado (%s):\n%s",
            self._transportadora,
            operation.name,
            redactar_xml(envelope),
        )

        return envelope, http_headers

    def ingress(self, envelope, http_headers, operation):
        log.info(
            "[%s] XML recibido (%s):\n%s",
            self._transportadora,
            operation.name,
            redactar_xml(envelope),
        )

        return envelope, http_headers



class AdaptadorSOAP:
    def __init__(self, transportadora: str, endpoint: str, reintentos: int = 3, timeout_seg: float = 10.0,
                 transporte: Transport | None = None, wsdl: str | None = None, dormir=time.sleep):
        self._transportadora = transportadora
        self._endpoint = endpoint
        self._wsdl = wsdl or f"{endpoint}?WSDL"
        self._reintentos = reintentos
        self._transporte = transporte or Transport(timeout=timeout_seg, operation_timeout=timeout_seg)
        self._dormir = dormir
        self._servicio = None

    def _obtener_servicio(self):
        """Carga el WSDL en el primer uso; si falla, no se guarda nada y se intenta de nuevo la próxima vez."""
        if self._servicio is None:
            cliente = Client(self._wsdl, transport=self._transporte, plugins=[BitacoraXML(self._transportadora)])
            binding = next(iter(cliente.wsdl.bindings))  # el WSDL del operador define un solo binding SOAP
            self._servicio = cliente.create_service(binding, self._endpoint)  # dirección del catálogo
        return self._servicio

    def enviar(self, mensaje: MensajeOperador) -> Any:
        for intento in range(1, self._reintentos + 1):
            try:
                operacion = getattr(self._obtener_servicio(), mensaje.operacion)
                return serialize_object(operacion(**mensaje.cuerpo), dict)
            except Fault as exc:
                log.warning("[%s] SOAP Fault en %s: %s", self._transportadora, mensaje.operacion, exc.message)
                raise ErrorPlataforma(502, "TRANSPORTADORA_RECHAZO",
                                      f"La transportadora {self._transportadora} rechazó la solicitud "
                                      f"({mensaje.operacion})", self._transportadora) from exc
            except (requests.RequestException, TransportError) as exc:
                motivo = exc.__class__.__name__
            except ErrorZeep as exc:  # XML o WSDL que no corresponde al contrato: no se arregla reintentando
                log.warning("[%s] respuesta SOAP inesperada en %s: %s", self._transportadora, mensaje.operacion, exc)
                raise ErrorPlataforma(502, "TRANSPORTADORA_RECHAZO",
                                      f"Respuesta inesperada de la transportadora {self._transportadora} "
                                      f"({mensaje.operacion})", self._transportadora) from exc
            if intento < self._reintentos:
                log.warning("[%s] intento %s fallido (%s); se reintenta", self._transportadora, intento, motivo)
                self._dormir(ESPERAS[min(intento - 1, len(ESPERAS) - 1)])
        raise ErrorPlataforma(502, "TRANSPORTADORA_SIN_RESPUESTA",
                              f"La transportadora {self._transportadora} no respondió tras {self._reintentos} intentos",
                              self._transportadora)
