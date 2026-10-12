"""Reglas propias del DHL simulado: unidades imperiales y códigos de ciudad propios."""
import math

DIVISOR_VOLUMETRICO = 139  # pulgadas cúbicas por libra
COBERTURA = {"BOG", "MDE", "CLO", "BAQ", "CTG", "BGA"}
DESCRIPCIONES = {
    "SD": "Shipment information received",
    "PU": "Shipment picked up",
    "AF": "Arrived at DHL facility",
    "DF": "Departed from DHL facility",
    "WC": "With delivery courier",
    "OK": "Delivered",
    "OH": "Shipment on hold",
    "RT": "Returned to shipper",
}


def peso_volumetrico_lb(largo_in: float, ancho_in: float, alto_in: float) -> float:
    return round(largo_in * ancho_in * alto_in / DIVISOR_VOLUMETRICO, 2)


def peso_facturable_lb(peso_lb: float, largo_in: float, ancho_in: float, alto_in: float) -> float:
    """El mayor entre el real y el volumétrico, redondeado hacia arriba a 0,5 lb."""
    mayor = max(peso_lb, peso_volumetrico_lb(largo_in, ancho_in, alto_in))
    return math.ceil(mayor * 2) / 2


def precio_cop(lb_facturables: float, origen: str, destino: str) -> float:
    precio = 18000 + 3500 * lb_facturables
    if origen != destino:
        precio *= 1.4
    return round(precio, 2)


def dias_transito(origen: str, destino: str) -> int:
    return 1 if origen == destino else 2
