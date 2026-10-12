from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Identidad(Base):
    """Usuario de un canal o cliente de servicio, con su secreto guardado como hash bcrypt."""

    __tablename__ = "identidad"

    nombre: Mapped[str] = mapped_column(String(80), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(20))  # "usuario" o "cliente"
    hash_secreto: Mapped[str] = mapped_column(String(100))
    roles: Mapped[str] = mapped_column(String(200))  # separados por comas

    def lista_roles(self) -> list[str]:
        return [rol for rol in self.roles.split(",") if rol]
