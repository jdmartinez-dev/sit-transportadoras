
"""Pruebas de protección de datos sensibles."""

from lxml import etree
from sit.adaptadores.redaccion import redactar_json, redactar_xml


def test_redacta_datos_anidados() -> None:
    datos = {
        "receiver": {
            "name": "Ana Perez",
            "phone": "3001234567",
            "address": "Calle 123",
        },
        "reference": "PED-1001",
    }

    resultado = redactar_json(datos)

    assert isinstance(resultado, dict)

    destinatario = resultado["receiver"]
    assert isinstance(destinatario, dict)

    assert destinatario["name"] == "[REDACTADO]"
    assert destinatario["phone"] == "[REDACTADO]"
    assert destinatario["address"] == "[REDACTADO]"
    assert resultado["reference"] == "PED-1001"


def test_no_modifica_los_datos_originales() -> None:
    datos = {
        "receiver": {
            "name": "Ana Perez",
        }
    }

    redactar_json(datos)

    destinatario = datos["receiver"]

    assert destinatario["name"] == "Ana Perez"


def test_redacta_elementos_en_listas() -> None:
    datos = {
        "packages": [
            {"name": "Paquete privado"},
            {"reference": "PED-1002"},
        ]
    }

    resultado = redactar_json(datos)

    assert isinstance(resultado, dict)

    paquetes = resultado["packages"]
    assert isinstance(paquetes, list)

    assert paquetes[0] == {"name": "[REDACTADO]"}
    assert paquetes[1] == {"reference": "PED-1002"}

def test_redacta_datos_personales_xml() -> None:
    xml = etree.fromstring(b"""
    <Envio>
        <nombre>Ana Perez</nombre>
        <telefono>3001234567</telefono>
        <direccion>Calle 123</direccion>
        <referencia>PED-1001</referencia>
    </Envio>
    """)

    resultado = redactar_xml(xml)

    assert "Ana Perez" not in resultado
    assert "3001234567" not in resultado
    assert "Calle 123" not in resultado
    assert resultado.count("[REDACTADO]") == 3
    assert "PED-1001" in resultado


def test_no_modifica_xml_original() -> None:
    xml = etree.fromstring(b"""
    <Envio>
        <nombre>Ana Perez</nombre>
        <referencia>PED-1001</referencia>
    </Envio>
    """)

    redactar_xml(xml)

    assert xml.findtext("nombre") == "Ana Perez"


def test_redacta_xml_con_namespaces() -> None:
    xml = etree.fromstring(b"""
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                   xmlns:log="http://ejemplo.com/logistica">
        <soap:Body>
            <log:Envio>
                <log:nombre>Ana Perez</log:nombre>
                <log:telefono>3001234567</log:telefono>
                <log:referencia>PED-1001</log:referencia>
            </log:Envio>
        </soap:Body>
    </soap:Envelope>
    """)

    resultado = redactar_xml(xml)

    assert "Ana Perez" not in resultado
    assert "3001234567" not in resultado
    assert "PED-1001" in resultado
    assert resultado.count("[REDACTADO]") == 2


def test_redacta_atributos_xml() -> None:
    xml = etree.fromstring(b"""
    <Envio>
        <destinatario nombre="Ana Perez"
                      telefono="3001234567"
                      referencia="PED-1001"/>
    </Envio>
    """)

    resultado = redactar_xml(xml)

    assert "Ana Perez" not in resultado
    assert "3001234567" not in resultado
    assert "PED-1001" in resultado
