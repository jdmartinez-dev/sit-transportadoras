"""Motor de transformación: por transportadora, su mapeador (estructura), sus tablas (datos) y su adaptador
(protocolo). El catálogo indica qué adaptador y qué tablas usar."""
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from comun.errores import ErrorPlataforma
from sit.catalogo import repositorio
from sit.catalogo.modelos import TransportadoraBD
from sit.motor.equivalencias import TablasEquivalencia
from sit.motor.mapeadores import MAPEADORES


@dataclass
class Integracion:
    transportadora: str
    mapeador: Any
    tablas: TablasEquivalencia
    adaptador: Any


class Motor:
    def __init__(self, Sesiones, crear_adaptador: Callable[[TransportadoraBD], Any], mapeadores=MAPEADORES):
        self._Sesiones = Sesiones
        self._crear_adaptador = crear_adaptador
        self._mapeadores = mapeadores
        self._adaptadores: dict[str, Any] = {}
        self._candado = threading.Lock()

    def integracion(self, codigo: str) -> Integracion:
        with self._Sesiones() as sesion:
            transportadora = repositorio.transportadora(sesion, codigo)
            if transportadora is None or not transportadora.activa or codigo not in self._mapeadores:
                raise ErrorPlataforma(422, "TRANSPORTADORA_DESCONOCIDA",
                                      f"Transportadora desconocida o inactiva: {codigo}", codigo)
            # Las tablas se leen en cada llamada: completar una tabla no exige reiniciar el SIT.
            tablas = repositorio.tablas_de(sesion, codigo)
        with self._candado:
            if codigo not in self._adaptadores:
                self._adaptadores[codigo] = self._crear_adaptador(transportadora)
            adaptador = self._adaptadores[codigo]
        return Integracion(codigo, self._mapeadores[codigo], tablas, adaptador)

    def activas(self) -> list[str]:
        with self._Sesiones() as sesion:
            return [t.codigo for t in repositorio.transportadoras(sesion, solo_activas=True)
                    if t.codigo in self._mapeadores]
