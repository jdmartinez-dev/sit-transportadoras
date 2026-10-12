
"""Utilidades para proteger datos sensibles en las bitácoras."""

from typing import TypeAlias
from lxml import etree

ValorJSON: TypeAlias = (
    str | int | float | bool | None
    | list["ValorJSON"]
    | dict[str, "ValorJSON"]
)

CAMPOS_SENSIBLES: frozenset[str] = frozenset({
    "name",
    "nombre",
    "phone",
    "telefono",
    "address",
    "direccion",
    "email",
    "password",
    "contrasena",
    "token",
    "authorization",
})

def redactar_json(datos: ValorJSON) -> ValorJSON:
    """Devuelve una copia del JSON con los campos sensibles ocultos."""
    if isinstance(datos, dict):
        return {
            clave: (
                "[REDACTADO]"
                if clave.lower() in CAMPOS_SENSIBLES
                else redactar_json(valor)
            )
            for clave, valor in datos.items()
        }

    if isinstance(datos, list):
        return [redactar_json(elemento) for elemento in datos]

    return datos

def redactar_xml(envelope: etree._Element) -> str:
    """Genera una copia saneada del XML sin modificar el original."""
    copia = etree.fromstring(etree.tostring(envelope))

    for elemento in copia.iter():
        if not isinstance(elemento.tag, str):
            continue

        nombre = etree.QName(elemento).localname.lower()

        # Proteger el contenido de elementos sensibles.
        if nombre in CAMPOS_SENSIBLES:
            elemento.text = "[REDACTADO]"

            for hijo in list(elemento):
                elemento.remove(hijo)

        # Proteger atributos sensibles.
        for atributo in list(elemento.attrib.keys()):
            nombre_atributo = etree.QName(atributo).localname.lower()

            if nombre_atributo in CAMPOS_SENSIBLES:
                elemento.attrib[atributo] = "[REDACTADO]"

    return etree.tostring(
        copia,
        pretty_print=True,
        encoding="unicode",
    )