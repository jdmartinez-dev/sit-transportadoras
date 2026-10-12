"""Envíos del DHL simulado, en memoria (se pierden al reiniciar el contenedor)."""
import itertools
import threading
from dataclasses import dataclass, field


@dataclass
class EnvioDHL:
    numero: str
    referencia: str
    origen: str
    destino: str
    eventos: list[dict] = field(default_factory=list)


class Almacen:
    def __init__(self):
        self._envios: dict[str, EnvioDHL] = {}
        self._consecutivo = itertools.count(1)
        self._recogidas = itertools.count(1)
        self._candado = threading.Lock()

    def crear(self, referencia: str, origen: str, destino: str) -> EnvioDHL:
        with self._candado:
            numero = f"53{next(self._consecutivo):08d}"  # 10 dígitos
            envio = EnvioDHL(numero, referencia, origen, destino)
            self._envios[numero] = envio
            return envio

    def buscar(self, numero: str) -> EnvioDHL | None:
        return self._envios.get(numero)

    def nueva_recogida(self) -> str:
        with self._candado:
            return f"CBJ{next(self._recogidas):09d}"
