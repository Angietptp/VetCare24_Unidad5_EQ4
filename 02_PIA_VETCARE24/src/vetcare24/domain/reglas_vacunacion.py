"""Specifications del seguimiento de vacunación (D-06, ajustada en la Etapa 9).

La regla R-12 pide un esquema "definido y validado" antes de calcular la próxima aplicación
(ADR-05). Son dos condiciones, y se componen con AND; "seguimiento pendiente" es su NOT:

    seguimiento_calculable = EsquemaDefinido AND EsquemaValidado
    seguimiento_pendiente  = NOT seguimiento_calculable

Que la vacuna requiera refuerzo (R-13) es otra pregunta (`RequiereRefuerzo`): no condiciona
que el seguimiento se pueda calcular.
"""

from __future__ import annotations

from dataclasses import dataclass

from vetcare24.domain.errors import InvarianteViolada
from vetcare24.domain.specification import Not, Specification
from vetcare24.domain.vacunacion import EsquemaDeVacunacion, Vacunacion


@dataclass(frozen=True)
class VacunacionEnContexto:
    """La última aplicación de una vacuna y el esquema de esa vacuna (si existe)."""

    ultima: Vacunacion
    esquema: EsquemaDeVacunacion | None

    def __post_init__(self) -> None:
        if self.esquema is not None and self.esquema.clave != self.ultima.clave:
            raise InvarianteViolada(
                "ESQUEMA_INCORRECTO",
                f"El esquema de {self.esquema.vacuna} no corresponde a {self.ultima.vacuna}",
            )


Regla = Specification[VacunacionEnContexto]


class EsquemaDefinido(Regla):
    codigo = "ESQUEMA_NO_DEFINIDO"

    def es_satisfecha_por(self, c: VacunacionEnContexto) -> bool:
        return c.esquema is not None


class EsquemaValidado(Regla):
    codigo = "ESQUEMA_NO_VALIDADO"

    def es_satisfecha_por(self, c: VacunacionEnContexto) -> bool:
        return c.esquema is not None and c.esquema.validado

    def motivos_de_incumplimiento(self, c: VacunacionEnContexto) -> tuple[str, ...]:
        # Sin esquema ya se informa ESQUEMA_NO_DEFINIDO; no se repite como "no validado".
        return () if c.esquema is None else (self.codigo,)


class RequiereRefuerzo(Regla):
    codigo = "NO_REQUIERE_REFUERZO"

    def es_satisfecha_por(self, c: VacunacionEnContexto) -> bool:
        return c.esquema is not None and c.esquema.requiere_refuerzo


def seguimiento_calculable() -> Regla:
    """R-12: esquema definido AND esquema validado."""
    return EsquemaDefinido() & EsquemaValidado()


def seguimiento_pendiente() -> Regla:
    """ADR-05: NOT seguimiento_calculable (no es un error: el registro ya se guardó)."""
    return Not(seguimiento_calculable(), "SEGUIMIENTO_PENDIENTE_DE_ESQUEMA_VALIDADO")
