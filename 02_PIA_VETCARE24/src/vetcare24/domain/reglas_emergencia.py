"""Specification de la atención sin cita (D-06, R-06, NB-19; cierra G-06).

Una mascota puede recibir atención si tiene una cita confirmada O si llegó como emergencia:

    atencion_permitida = TieneCitaConfirmada OR TieneEmergenciaActiva

Es una consulta (no cambia nada): la API la expone como evaluación, igual que L-01.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from vetcare24.domain._validacion import exigir_texto
from vetcare24.domain.cita import Cita, EstadoCita
from vetcare24.domain.emergencia import Emergencia
from vetcare24.domain.specification import Specification


@dataclass(frozen=True)
class MascotaParaAtencion:
    """Una mascota con sus citas y sus emergencias (solo las suyas)."""

    mascota_id: str
    citas: tuple[Cita, ...]
    emergencias: tuple[Emergencia, ...]

    @classmethod
    def de(cls, mascota_id: str, citas: Iterable[Cita],
           emergencias: Iterable[Emergencia]) -> MascotaParaAtencion:
        """Arma el contexto quedándose solo con lo que es de esa mascota."""
        exigir_texto(mascota_id, "MASCOTA_REQUERIDA", "La mascota")
        return cls(
            mascota_id,
            tuple(c for c in citas if c.mascota_id == mascota_id),
            tuple(e for e in emergencias if e.mascota_id == mascota_id),
        )


Regla = Specification[MascotaParaAtencion]


class TieneCitaConfirmada(Regla):
    """Una cita programada para la mascota. SOLICITADA aún no está programada (CitaAgendada se
    emite al confirmar, I-01); REALIZADA y CANCELADA ya no dan pie a una atención nueva."""

    codigo = "SIN_CITA_CONFIRMADA"

    def es_satisfecha_por(self, c: MascotaParaAtencion) -> bool:
        return any(cita.estado is EstadoCita.CONFIRMADA for cita in c.citas)


class TieneEmergenciaActiva(Regla):
    codigo = "SIN_EMERGENCIA_ACTIVA"

    def es_satisfecha_por(self, c: MascotaParaAtencion) -> bool:
        return any(emergencia.esta_activa for emergencia in c.emergencias)


def atencion_permitida() -> Regla:
    """R-06: TieneCitaConfirmada OR TieneEmergenciaActiva."""
    return TieneCitaConfirmada() | TieneEmergenciaActiva()
