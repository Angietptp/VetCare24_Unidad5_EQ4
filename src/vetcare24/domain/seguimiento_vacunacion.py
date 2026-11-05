"""Servicio de seguimiento de vacunación (domain service, ADR-05).

Para cada tipo de vacuna del historial toma la ÚLTIMA aplicación y, si el esquema está
definido y validado, calcula la próxima:

    proxima_aplicacion = fecha de la última aplicación + frecuencia_dias del esquema

El BRD (Q10) dice que la frecuencia depende del tipo de vacuna y que se usa el esquema para
determinar la siguiente aplicación, pero no da una fórmula; esta es la más simple compatible
con eso y es una PROPUESTA por validar con el stakeholder. El resultado no se guarda: se calcula
cada vez a partir del historial (informe, CU-03).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from vetcare24.domain.reglas_vacunacion import VacunacionEnContexto, seguimiento_calculable
from vetcare24.domain.vacunacion import EsquemaDeVacunacion, Vacunacion


class EstadoDeSeguimiento(StrEnum):
    CALCULADO = "calculado"
    PENDIENTE_DE_ESQUEMA = "pendiente_de_esquema"


@dataclass(frozen=True)
class SeguimientoDeVacuna:
    vacuna: str
    ultima_aplicacion: date
    estado: EstadoDeSeguimiento
    proxima_aplicacion: date | None
    es_refuerzo: bool | None
    motivos: tuple[str, ...]


class ServicioDeSeguimientoDeVacunacion:
    def __init__(self) -> None:
        self._calculable = seguimiento_calculable()

    def seguimiento(
        self, historial: Iterable[Vacunacion], esquemas: Mapping[str, EsquemaDeVacunacion]
    ) -> list[SeguimientoDeVacuna]:
        """Un seguimiento por tipo de vacuna, ordenado por nombre. `esquemas` va por clave
        normalizada (`EsquemaDeVacunacion.clave`)."""
        ultimas: dict[str, Vacunacion] = {}
        for vacunacion in historial:
            actual = ultimas.get(vacunacion.clave)
            if actual is None or _orden(vacunacion) > _orden(actual):
                ultimas[vacunacion.clave] = vacunacion
        resultado = []
        for clave in sorted(ultimas):
            ultima = ultimas[clave]
            esquema = esquemas.get(clave)
            evaluacion = self._calculable.evaluar(VacunacionEnContexto(ultima, esquema))
            if evaluacion.cumple and esquema is not None:
                proxima = ultima.fecha_aplicacion + timedelta(days=esquema.frecuencia_dias)
                resultado.append(SeguimientoDeVacuna(
                    ultima.vacuna, ultima.fecha_aplicacion, EstadoDeSeguimiento.CALCULADO,
                    proxima, esquema.requiere_refuerzo, ()))
            else:
                resultado.append(SeguimientoDeVacuna(
                    ultima.vacuna, ultima.fecha_aplicacion,
                    EstadoDeSeguimiento.PENDIENTE_DE_ESQUEMA, None, None, evaluacion.motivos))
        return resultado

    @staticmethod
    def vence_pronto(seguimiento: SeguimientoDeVacuna, hoy: date, dentro_de_dias: int) -> bool:
        """Está vencida o vence dentro de la ventana (para recordatorios, NB-17)."""
        if seguimiento.proxima_aplicacion is None:
            return False
        return seguimiento.proxima_aplicacion <= hoy + timedelta(days=dentro_de_dias)


def _orden(vacunacion: Vacunacion) -> tuple[date, str]:
    return (vacunacion.fecha_aplicacion, vacunacion.vacunacion_id)
