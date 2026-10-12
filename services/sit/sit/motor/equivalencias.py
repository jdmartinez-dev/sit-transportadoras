"""Aplicación de las tablas de equivalencia (datos). No toca la base: se prueba sin Docker."""
from dataclasses import dataclass

from comun.canonico import EstadoEnvio
from comun.errores import ErrorPlataforma


@dataclass(frozen=True)
class Traduccion:
    estado: EstadoEnvio
    sin_equivalencia: bool = False


@dataclass
class TablasEquivalencia:
    transportadora: str
    estados: dict[str, EstadoEnvio]  # código del operador -> estado canónico
    ciudades: dict[str, str]  # DIVIPOLA (5 dígitos) -> código del operador
    unidades: dict[str, tuple[str, float]]  # magnitud -> (unidad del operador, factor a la unidad canónica)

    def traducir_estado(self, codigo_operador: str) -> Traduccion:
        estado = self.estados.get(codigo_operador)
        if estado is None:
            # Documento: "si un estado no tiene equivalencia, se publica como NOVEDAD y se registra".
            return Traduccion(EstadoEnvio.NOVEDAD, sin_equivalencia=True)
        return Traduccion(estado)

    def ciudad_a_operador(self, divipola: str) -> str:
        try:
            return self.ciudades[divipola]
        except KeyError:
            raise ErrorPlataforma(422, "DESTINO_NO_CUBIERTO",
                                  f"La transportadora {self.transportadora} no cubre la ciudad {divipola}",
                                  self.transportadora) from None

    def a_unidad_operador(self, magnitud: str, valor_canonico: float) -> float:
        _, factor = self.unidades[magnitud]
        return valor_canonico / factor

    def a_unidad_canonica(self, magnitud: str, valor_operador: float) -> float:
        _, factor = self.unidades[magnitud]
        return valor_operador * factor
