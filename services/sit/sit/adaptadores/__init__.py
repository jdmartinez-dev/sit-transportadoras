"""Un adaptador por protocolo (patrón Protocol Bridging): reutilizable por cualquier operador que use ese protocolo."""
from sit.adaptadores.rest import AdaptadorREST
from sit.adaptadores.soap import AdaptadorSOAP
from sit.catalogo.modelos import TransportadoraBD
from sit.config import Config


def crear_adaptador(transportadora: TransportadoraBD, config: Config):
    """El campo `adaptador` del catálogo decide el protocolo (Figura 3B, paso 1)."""
    if transportadora.adaptador == "rest":
        return AdaptadorREST(transportadora.codigo, transportadora.endpoint, config.credenciales(transportadora.codigo),
                             config.reintentos, config.timeout_seg)
    if transportadora.adaptador == "soap":
        return AdaptadorSOAP(transportadora.codigo, transportadora.endpoint, config.reintentos, config.timeout_seg)
    raise ValueError(f"Adaptador no disponible en el prototipo: {transportadora.adaptador}")
