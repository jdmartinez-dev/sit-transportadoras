"""Cliente de la API canónica del SIT. Despachos no tiene lógica de mapeo: solo habla el modelo canónico."""
import time
from typing import Any

import httpx
from pydantic import BaseModel

from comun.canonico import (Cotizacion, ErrorCanonico, Guia, Recogida, SolicitudCotizacion, SolicitudEnvio,
                            SolicitudRecogida)
from comun.errores import ErrorPlataforma


class ProveedorToken:
    """Token de credenciales de cliente (OAuth 2.0), en caché hasta 30 s antes de vencer."""

    def __init__(self, url_token: str, cliente_id: str, secreto: str, http: httpx.Client):
        self._url_token = url_token
        self._cliente_id = cliente_id
        self._secreto = secreto
        self._http = http
        self._token: str | None = None
        self._vence = 0.0

    def token(self) -> str:
        if self._token and time.monotonic() < self._vence - 30:
            return self._token
        try:
            respuesta = self._http.post(self._url_token, data={"grant_type": "client_credentials",
                                                               "client_id": self._cliente_id,
                                                               "client_secret": self._secreto})
            respuesta.raise_for_status()
        except httpx.HTTPError as exc:
            raise ErrorPlataforma(502, "AUTH_NO_DISPONIBLE",
                                  "No se pudo obtener un token del servicio de autenticación") from exc
        datos = respuesta.json()
        self._token = datos["access_token"]
        self._vence = time.monotonic() + datos["expires_in"]
        return self._token


class ClienteSIT:
    def __init__(self, url_base: str, tokens: ProveedorToken, http: httpx.Client):
        self._url = url_base.rstrip("/")
        self._tokens = tokens
        self._http = http

    def cotizar(self, solicitud: SolicitudCotizacion) -> list[Cotizacion]:
        return [Cotizacion.model_validate(c) for c in self._post("/api/v1/cotizaciones", solicitud)]

    def crear_envio(self, solicitud: SolicitudEnvio) -> Guia:
        return Guia.model_validate(self._post("/api/v1/envios", solicitud))

    def programar_recogida(self, solicitud: SolicitudRecogida) -> Recogida:
        return Recogida.model_validate(self._post("/api/v1/recogidas", solicitud))

    def _post(self, ruta: str, cuerpo: BaseModel) -> Any:
        encabezados = {"Content-Type": "application/json", "Authorization": f"Bearer {self._tokens.token()}"}
        try:
            respuesta = self._http.post(self._url + ruta, content=cuerpo.model_dump_json(), headers=encabezados)
        except httpx.HTTPError as exc:
            raise ErrorPlataforma(502, "SIT_NO_DISPONIBLE",
                                  f"No se pudo contactar al SIT ({exc.__class__.__name__})") from exc
        if respuesta.status_code >= 400:
            try:
                error = ErrorCanonico.model_validate(respuesta.json())
            except ValueError:
                error = ErrorCanonico(codigo="SIT_ERROR", mensaje=f"El SIT respondió HTTP {respuesta.status_code}")
            raise ErrorPlataforma(respuesta.status_code, error.codigo, error.mensaje, error.transportadora)
        return respuesta.json()
