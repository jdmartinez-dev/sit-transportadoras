"""Adaptador REST (httpx): puente de protocolo hacia las transportadoras que exponen JSON sobre HTTP."""
import json
import logging
import time
from typing import Any

import httpx

from comun.errores import ErrorPlataforma
from sit.motor.tipos import MensajeOperador

log = logging.getLogger(__name__)
ESPERAS = (0.5, 1.0)


class AdaptadorREST:
    def __init__(self, transportadora: str, endpoint: str, credenciales: tuple[str, str] | None = None,
                 reintentos: int = 3, timeout_seg: float = 10.0, cliente_http: httpx.Client | None = None,
                 dormir=time.sleep):
        self._transportadora = transportadora
        self._endpoint = endpoint.rstrip("/")
        self._credenciales = credenciales
        self._reintentos = reintentos
        self._http = cliente_http or httpx.Client(timeout=timeout_seg)
        self._dormir = dormir

    def enviar(self, mensaje: MensajeOperador) -> Any:
        metodo, ruta = mensaje.operacion.split(" ", 1)
        cuerpo = None if metodo == "GET" else mensaje.cuerpo
        log.info("[%s] %s %s — JSON enviado: %s", self._transportadora, metodo, ruta,
                 json.dumps(cuerpo, ensure_ascii=False))
        for intento in range(1, self._reintentos + 1):
            try:
                respuesta = self._http.request(metodo, self._endpoint + ruta, json=cuerpo, auth=self._credenciales)
            except httpx.TransportError as exc:
                motivo = f"sin conexión ({exc.__class__.__name__})"
            else:
                if respuesta.status_code < 400:
                    try:
                        datos = respuesta.json()
                    except ValueError as exc:
                        log.warning("[%s] respuesta %s que no es JSON: %s", self._transportadora,
                                    respuesta.status_code, respuesta.text[:200])
                        raise ErrorPlataforma(502, "TRANSPORTADORA_RECHAZO",
                                              f"Respuesta inesperada de la transportadora {self._transportadora}",
                                              self._transportadora) from exc
                    log.info("[%s] JSON recibido: %s", self._transportadora, json.dumps(datos, ensure_ascii=False))
                    return datos
                if respuesta.status_code < 500:
                    log.warning("[%s] rechazo HTTP %s: %s", self._transportadora, respuesta.status_code,
                                respuesta.text)
                    raise ErrorPlataforma(502, "TRANSPORTADORA_RECHAZO",
                                          f"La transportadora {self._transportadora} rechazó la solicitud "
                                          f"(HTTP {respuesta.status_code})", self._transportadora)
                motivo = f"HTTP {respuesta.status_code}"
            if intento < self._reintentos:
                log.warning("[%s] intento %s fallido (%s); se reintenta", self._transportadora, intento, motivo)
                self._dormir(ESPERAS[min(intento - 1, len(ESPERAS) - 1)])
        raise ErrorPlataforma(502, "TRANSPORTADORA_SIN_RESPUESTA",
                              f"La transportadora {self._transportadora} no respondió tras {self._reintentos} intentos",
                              self._transportadora)
