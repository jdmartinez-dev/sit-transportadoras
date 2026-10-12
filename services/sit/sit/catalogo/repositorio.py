"""Acceso al catálogo y a las tablas de equivalencia."""
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from comun.canonico import EstadoEnvio
from sit.catalogo.modelos import EquivalenciaCiudad, EquivalenciaEstado, EquivalenciaUnidad, TransportadoraBD
from sit.motor.equivalencias import TablasEquivalencia

SEMILLA = Path(__file__).with_name("semilla.sql")


def _sentencias(sql: str) -> list[str]:
    """Divide el archivo en sentencias (SQLite no ejecuta varias a la vez). La semilla no usa ';' en sus datos."""
    sin_comentarios = "\n".join(linea for linea in sql.splitlines() if not linea.strip().startswith("--"))
    return [s.strip() for s in sin_comentarios.split(";") if s.strip()]


def cargar_semilla_si_vacio(sesion: Session) -> bool:
    if sesion.scalar(select(func.count()).select_from(TransportadoraBD)):
        return False
    conexion = sesion.connection()
    for sentencia in _sentencias(SEMILLA.read_text(encoding="utf-8")):
        conexion.exec_driver_sql(sentencia)
    sesion.commit()
    return True


def transportadoras(sesion: Session, solo_activas: bool = False) -> list[TransportadoraBD]:
    consulta = select(TransportadoraBD).order_by(TransportadoraBD.codigo)
    if solo_activas:
        consulta = consulta.where(TransportadoraBD.activa.is_(True))
    return list(sesion.scalars(consulta))


def transportadora(sesion: Session, codigo: str) -> TransportadoraBD | None:
    return sesion.get(TransportadoraBD, codigo)


def tablas_de(sesion: Session, codigo: str) -> TablasEquivalencia:
    estados = sesion.scalars(select(EquivalenciaEstado).where(EquivalenciaEstado.transportadora == codigo))
    ciudades = sesion.scalars(select(EquivalenciaCiudad).where(EquivalenciaCiudad.transportadora == codigo))
    unidades = sesion.scalars(select(EquivalenciaUnidad).where(EquivalenciaUnidad.transportadora == codigo))
    return TablasEquivalencia(
        transportadora=codigo,
        estados={e.codigo_operador: EstadoEnvio(e.estado_canonico) for e in estados},
        ciudades={c.divipola: c.codigo_operador for c in ciudades},
        unidades={u.magnitud: (u.unidad_operador, float(u.factor_a_canonico)) for u in unidades},
    )
