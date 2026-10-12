import httpx

from mock_dhl.webhook import NotificadorWebhook


def test_obtiene_el_token_una_vez_y_envia_el_webhook_con_bearer():
    pedidos = []

    def manejar(request: httpx.Request) -> httpx.Response:
        pedidos.append(request)
        if request.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "tok", "token_type": "Bearer", "expires_in": 900})
        return httpx.Response(204)

    notificador = NotificadorWebhook("http://sit:8000/api/v1/webhooks/dhl", "http://auth:8000/oauth/token",
                                     "mock-dhl", "secreto", httpx.Client(transport=httpx.MockTransport(manejar)))
    notificador.notificar("5300000001", {"typeCode": "PU"})
    notificador.notificar("5300000001", {"typeCode": "AF"})
    assert [p.url.path for p in pedidos] == ["/oauth/token", "/api/v1/webhooks/dhl", "/api/v1/webhooks/dhl"]
    assert pedidos[1].headers["authorization"] == "Bearer tok"


def test_si_el_sit_no_responde_no_rompe_el_simulador():
    def manejar(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin conexión")

    notificador = NotificadorWebhook("http://sit:8000/api/v1/webhooks/dhl", "http://auth:8000/oauth/token",
                                     "mock-dhl", "secreto", httpx.Client(transport=httpx.MockTransport(manejar)))
    notificador.notificar("5300000001", {"typeCode": "PU"})
