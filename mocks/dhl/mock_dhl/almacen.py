"""Envíos del DHL simulado, en memoria (se pierden al reiniciar el contenedor)."""
import itertools
import threading
import time
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
        # El consecutivo arranca en un valor que depende de la hora de arranque: si el contenedor se reinicia
        # sin borrar la base de la plataforma, los números nuevos no repiten los anteriores.
        self._consecutivo = itertools.count((int(time.time()) % 1_000_000) * 100 + 1)
        self._recogidas = itertools.count(1)
        self._candado = threading.Lock()

    def crear(self, referencia: str, origen: str, destino: str) -> EnvioDHL:
        with self._candado:
            numero = f"53{next(self._consecutivo) % 100_000_000:08d}"  # 10 dígitos
            envio = EnvioDHL(numero, referencia, origen, destino)
            self._envios[numero] = envio
            return envio

    def buscar(self, numero: str) -> EnvioDHL | None:
        return self._envios.get(numero)

    def nueva_recogida(self) -> str:
        with self._candado:
            return f"CBJ{next(self._recogidas):09d}"
