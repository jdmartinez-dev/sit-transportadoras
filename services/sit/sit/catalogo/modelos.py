from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from comun.bd import FechaHora


class Base(DeclarativeBase):
    pass


class TransportadoraBD(Base):
    """Catálogo (sección Proveedor y registro): protocolo, versión de API, adaptador activo y frecuencia."""

    __tablename__ = "transportadora"

    codigo: Mapped[str] = mapped_column(String(30), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    protocolo: Mapped[str] = mapped_column(String(10))
    version_api: Mapped[str] = mapped_column(String(60))
    adaptador: Mapped[str] = mapped_column(String(20))
    endpoint: Mapped[str] = mapped_column(String(200))
    frecuencia_sincronizacion_seg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version_equivalencias: Mapped[str] = mapped_column(String(20))
    activa: Mapped[bool] = mapped_column(Boolean, default=True)


class EquivalenciaEstado(Base):
    __tablename__ = "equivalencia_estado"

    transportadora: Mapped[str] = mapped_column(ForeignKey("transportadora.codigo"), primary_key=True)
    codigo_operador: Mapped[str] = mapped_column(String(20), primary_key=True)
    estado_canonico: Mapped[str] = mapped_column(String(20))


class EquivalenciaCiudad(Base):
    __tablename__ = "equivalencia_ciudad"
    __table_args__ = (UniqueConstraint("transportadora", "codigo_operador"),)

    transportadora: Mapped[str] = mapped_column(ForeignKey("transportadora.codigo"), primary_key=True)
    divipola: Mapped[str] = mapped_column(String(5), primary_key=True)
    codigo_operador: Mapped[str] = mapped_column(String(20))


class EquivalenciaUnidad(Base):
    __tablename__ = "equivalencia_unidad"

    transportadora: Mapped[str] = mapped_column(ForeignKey("transportadora.codigo"), primary_key=True)
    magnitud: Mapped[str] = mapped_column(String(20), primary_key=True)
    unidad_operador: Mapped[str] = mapped_column(String(10))
    factor_a_canonico: Mapped[float] = mapped_column(Float)


class GuiaBD(Base):
    """Interna del SIT (spec §18): qué guías consultar y cuál fue el último estado publicado."""

    __tablename__ = "guia"

    numero: Mapped[str] = mapped_column(String(30), primary_key=True)
    transportadora: Mapped[str] = mapped_column(ForeignKey("transportadora.codigo"))
    pedido_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ultimo_estado: Mapped[str | None] = mapped_column(String(20), nullable=True)
    eventos_leidos: Mapped[int] = mapped_column(Integer, default=0)  # del historial del operador (consulta programada)
    creada_en: Mapped[datetime] = mapped_column(FechaHora)
    actualizada_en: Mapped[datetime] = mapped_column(FechaHora)


class EstadoSinEquivalencia(Base):
    """Interna del SIT: estados registrados "para que el equipo de integración complete la tabla"."""

    __tablename__ = "estado_sin_equivalencia"
    __table_args__ = (UniqueConstraint("transportadora", "codigo_operador", "numero_guia"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transportadora: Mapped[str] = mapped_column(String(30))
    codigo_operador: Mapped[str] = mapped_column(String(20))
    numero_guia: Mapped[str] = mapped_column(String(30))
    registrado_en: Mapped[datetime] = mapped_column(FechaHora)
