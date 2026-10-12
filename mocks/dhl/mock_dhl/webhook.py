"""Avisa cada cambio de estado al webhook del SIT, autenticado con OAuth 2.0 (credenciales de cliente)."""
import logging
import time

import httpx

log = logging.getLogger(__name__)


class NotificadorWebhook:
    def __init__(self, url_webhook: str, url_token: str, cliente_id: str, cliente_secreto: str,
                 cliente_http: httpx.Client | None = None):
        self._url_webhook = url_webhook
        self._url_token = url_token
        self._cliente_id = cliente_id
        self._secreto = cliente_secreto
        self._http = cliente_http or httpx.Client(timeout=10.0)
        self._token: str | None = None
        self._vence = 0.0

    def _obtener_token(self) -> str:
        if self._token and time.monotonic() < self._vence - 30:
            return self._token
        respuesta = self._http.post(self._url_token, data={"grant_type": "client_credentials"},
                                    auth=(self._cliente_id, self._secreto))
        respuesta.raise_for_status()
        datos = respuesta.json()
        self._token = datos["access_token"]
        self._vence = time.monotonic() + datos["expires_in"]
        return self._token

    def notificar(self, numero: str, evento: dict) -> None:
        cuerpo = {"shipmentTrackingNumber": numero, "event": evento}
        try:
            respuesta = self._http.post(self._url_webhook, json=cuerpo,
                                        headers={"Authorization": f"Bearer {self._obtener_token()}"})
            respuesta.raise_for_status()
            log.info("Webhook enviado: guía %s evento %s", numero, evento["typeCode"])
        except httpx.HTTPError as exc:
            log.error("No se pudo enviar el webhook de la guía %s: %s", numero, exc)
