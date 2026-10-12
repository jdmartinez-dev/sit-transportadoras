"""Guion de la demo (sección 15 de la especificación) contra el Docker Compose en ejecución.

Ejecutar: docker compose up -d && E2E=1 .venv/bin/pytest tests/e2e -v
"""
import os
import subprocess
import time
import uuid
from pathlib import Path

import httpx
import pytest

pytestmark = [pytest.mark.e2e,
              pytest.mark.skipif(os.environ.get("E2E") != "1", reason="requiere docker compose up y E2E=1")]

RAIZ = Path(__file__).resolve().parents[2]
AUTH, SIT, DESPACHOS, RASTREO = ("http://localhost:8000", "http://localhost:8010", "http://localhost:8020",
                                 "http://localhost:8030")
DHL, COORDINADORA = "http://localhost:8082", "http://localhost:8088/ws/guias"
SUFIJO = uuid.uuid4().hex[:6]  # pedidos únicos en cada ejecución


def _token(usuario: str) -> str:
    clave = (RAIZ / "secrets" / "usuarios_demo_password").read_text().strip()
    r = httpx.post(f"{AUTH}/oauth/token", data={"grant_type": "password", "username": usuario, "password": clave})
    r.raise_for_status()
    return r.json()["access_token"]


def _con(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def tokens() -> dict:
    return {usuario: _token(usuario) for usuario in ("agente1", "operador1", "admin1", "cliente1")}


def _pedido(pedido_id: str, transportadora: str | None = None) -> dict:
    return {"pedido_id": pedido_id, "transportadora": transportadora,
            "destino": {"divipola": "05001", "direccion": "Carrera 43A # 1-50", "nombre": "Cliente de prueba",
                        "telefono": "3001234567"},
            "paquetes": [{"peso_kg": 2.0, "largo_cm": 30, "ancho_cm": 20, "alto_cm": 10}]}


def _esperar(condicion, segundos: int = 30):
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        resultado = condicion()
        if resultado:
            return resultado
        time.sleep(1)
    pytest.fail("La condición no se cumplió a tiempo")


def _estado_en_rastreo(guia: str, token: str, esperado: str) -> dict:
    def condicion():
        r = httpx.get(f"{RASTREO}/api/v1/rastreo/{guia}", headers=_con(token))
        return r.json() if r.status_code == 200 and r.json()["estado_actual"] == esperado else None
    return _esperar(condicion)


def _despacho_completo(pedido_id: str, token: str) -> dict:
    def condicion():
        r = httpx.get(f"{DESPACHOS}/api/v1/despachos/{pedido_id}", headers=_con(token))
        return r.json() if r.status_code == 200 and r.json()["estado"] == "RECOGIDA_PROGRAMADA" else None
    return _esperar(condicion)


def test_guion_de_la_demo(tokens):
    agente = _con(tokens["agente1"])

    # 2. Pedido A forzando DHL (POST /api/v1/despachos)
    r = httpx.post(f"{DESPACHOS}/api/v1/despachos", json=_pedido(f"PED-A-{SUFIJO}", "dhl"), headers=agente, timeout=60)
    assert r.status_code == 201, r.text
    a = r.json()
    assert (a["estado"], a["transportadora"], len(a["numero_guia"])) == ("RECOGIDA_PROGRAMADA", "dhl", 10)

    # 3. Pedido B forzando Coordinadora, publicado como evento pedido.confirmado
    subprocess.run([str(RAIZ / "scripts" / "publicar-pedido.sh"), f"PED-B-{SUFIJO}", "coordinadora"], check=True,
                   cwd=RAIZ)
    b = _despacho_completo(f"PED-B-{SUFIJO}", tokens["agente1"])
    assert (b["transportadora"], len(b["numero_guia"])) == ("coordinadora", 12)

    # 4. Mismo formato canónico para las dos guías
    assert set(a) == set(b)

    # 5. Pedido C sin forzar: cotizaciones comparables y la más barata
    r = httpx.post(f"{DESPACHOS}/api/v1/despachos", json=_pedido(f"PED-C-{SUFIJO}"), headers=agente, timeout=60)
    c = r.json()
    assert {x["transportadora"] for x in c["cotizaciones"]} == {"dhl", "coordinadora"}
    assert c["transportadora"] == min(c["cotizaciones"], key=lambda x: x["valor_cop"])["transportadora"]

    # 6. DHL: cambio de estado → webhook → SIT → evento → Rastreo
    httpx.post(f"{DHL}/demo/envios/{a['numero_guia']}/estado", json={"typeCode": "PU"}).raise_for_status()
    _estado_en_rastreo(a["numero_guia"], tokens["cliente1"], "RECOGIDA")

    # 7. Coordinadora: cambio de estado por SOAP → consulta programada (≤ 10 s) → Rastreo
    sobre = ('<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
             'xmlns:g="http://coordinadora.simulada/guias"><soapenv:Body><g:CambiarEstadoGuia>'
             f'<g:codigoRemision>{b["numero_guia"]}</g:codigoRemision><g:codigoEstado>6</g:codigoEstado>'
             '</g:CambiarEstadoGuia></soapenv:Body></soapenv:Envelope>')
    httpx.post(COORDINADORA, content=sobre, headers={
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": '"http://coordinadora.simulada/guias/CambiarEstadoGuia"'}).raise_for_status()
    rastreo_b = _estado_en_rastreo(b["numero_guia"], tokens["agente1"], "EN_REPARTO")
    assert [e["estado"] for e in rastreo_b["historial"]] == ["CREADA", "EN_REPARTO"]

    # 8. Código sin equivalencia → NOVEDAD y registro para completar la tabla
    httpx.post(f"{DHL}/demo/envios/{a['numero_guia']}/estado", json={"typeCode": "XX"}).raise_for_status()
    _estado_en_rastreo(a["numero_guia"], tokens["agente1"], "NOVEDAD")
    consulta = ("SELECT codigo_operador FROM estado_sin_equivalencia "
                f"WHERE numero_guia = '{a['numero_guia']}'")
    salida = subprocess.run(["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "plataforma", "-d", "sit",
                             "-tAc", consulta], capture_output=True, text=True, cwd=RAIZ, check=True)
    assert salida.stdout.strip() == "XX"

    # 9. Consulta en vivo al operador (operador logístico)
    r = httpx.get(f"{SIT}/api/v1/envios/{b['numero_guia']}/estados", headers=_con(tokens["operador1"]))
    assert r.status_code == 200
    assert r.json()[-1]["estado"] == "EN_REPARTO"

    # 10. Catálogo (administrador de integraciones)
    r = httpx.get(f"{SIT}/api/v1/transportadoras", headers=_con(tokens["admin1"]))
    assert {t["codigo"] for t in r.json()} == {"dhl", "coordinadora"}

    # 11. Seguridad: un cliente no puede despachar
    r = httpx.post(f"{DESPACHOS}/api/v1/despachos", json=_pedido(f"PED-D-{SUFIJO}"),
                   headers=_con(tokens["cliente1"]))
    assert r.status_code == 403
