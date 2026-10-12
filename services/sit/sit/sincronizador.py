"""Consulta programada de estados para las transportadoras sin webhook (APScheduler, frecuencia del catálogo)."""
import logging
from datetime import timezone

from apscheduler.schedulers.background import BackgroundScheduler

from sit.catalogo import repositorio

log = logging.getLogger(__name__)


class Sincronizador:
    def __init__(self, servicio, Sesiones, programador: BackgroundScheduler | None = None):
        self._servicio = servicio
        self._Sesiones = Sesiones
        self._programador = programador or BackgroundScheduler(timezone=timezone.utc)

    def programar(self) -> None:
        with self._Sesiones() as sesion:
            transportadoras = repositorio.transportadoras(sesion, solo_activas=True)
        for t in transportadoras:
            if t.frecuencia_sincronizacion_seg:
                self._programador.add_job(self._servicio.sincronizar, "interval",
                                          seconds=t.frecuencia_sincronizacion_seg, args=[t.codigo],
                                          id=f"sincronizar-{t.codigo}", max_instances=1, coalesce=True)
                log.info("Consulta programada de %s cada %s s", t.codigo, t.frecuencia_sincronizacion_seg)

    def iniciar(self) -> None:
        self.programar()
        self._programador.start()

    def detener(self) -> None:
        self._programador.shutdown(wait=False)
