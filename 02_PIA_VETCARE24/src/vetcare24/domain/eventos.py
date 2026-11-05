"""Domain Events (D-14): hechos importantes que ya ocurrieron en una cita.

Un evento está en pasado (CitaAgendada, no AgendarCita), es inmutable y lleva lo mínimo que
necesitaría quien lo reciba. El dominio solo los crea; quién reacciona a ellos lo decide la
capa de aplicación (application/despachador.py).

Ya existen los de Cita, Vacunación (Etapa 9) y Emergencia (Etapa 10). Los de Hospitalización y
Nota clínica (D-14) llegan cuando existan esas entidades en el dominio.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date, datetime
from typing import Any, ClassVar

from vetcare24.domain.errors import InvarianteViolada
from vetcare24.domain.money import Money

# Servicios y unidades como pares (servicio_id, cantidad): inmutable y comparable.
Demanda = tuple[tuple[str, int], ...]


def _serializable(valor: Any) -> Any:
    if isinstance(valor, Money):
        return str(valor.monto)
    if isinstance(valor, (datetime, date)):  # datetime es un tipo de date: va junto
        return valor.isoformat()
    if isinstance(valor, (tuple, list)):
        return [_serializable(elemento) for elemento in valor]
    return valor


@dataclass(frozen=True)
class EventoDeDominio:
    ocurrido_en: datetime

    def __post_init__(self) -> None:
        if (
            not isinstance(self.ocurrido_en, datetime)
            or self.ocurrido_en.tzinfo is None
            or self.ocurrido_en.utcoffset() is None
        ):
            raise InvarianteViolada(
                "EVENTO_SIN_ZONA_HORARIA", "ocurrido_en debe ser una fecha y hora con zona horaria"
            )

    # Qué agregado emitió el evento y en qué campo viaja su identificador. Cada clase lo declara.
    AGREGADO: ClassVar[str] = ""
    CAMPO_ID: ClassVar[str] = ""

    @property
    def nombre(self) -> str:
        return type(self).__name__

    @property
    def agregado_tipo(self) -> str:
        return type(self).AGREGADO

    @property
    def agregado_id(self) -> str:
        return str(getattr(self, type(self).CAMPO_ID))

    def a_diccionario(self) -> dict[str, Any]:
        """Forma plana (texto, números y listas) para guardarlo o enviarlo como JSON."""
        datos = {campo.name: _serializable(getattr(self, campo.name)) for campo in fields(self)}
        return {"evento": self.nombre, **datos}


@dataclass(frozen=True)
class CitaAgendada(EventoDeDominio):
    """La cita se confirmó y reservó capacidad."""

    AGREGADO: ClassVar[str] = "Cita"
    CAMPO_ID: ClassVar[str] = "cita_id"

    cita_id: str
    propietario_id: str
    mascota_id: str
    servicios: Demanda
    total: Money


@dataclass(frozen=True)
class CitaRealizada(EventoDeDominio):
    AGREGADO: ClassVar[str] = "Cita"
    CAMPO_ID: ClassVar[str] = "cita_id"

    cita_id: str
    propietario_id: str
    mascota_id: str


@dataclass(frozen=True)
class CitaCancelada(EventoDeDominio):
    """`estado_anterior` indica si había capacidad reservada que se liberó (CONFIRMADA)."""

    AGREGADO: ClassVar[str] = "Cita"
    CAMPO_ID: ClassVar[str] = "cita_id"

    cita_id: str
    propietario_id: str
    mascota_id: str
    estado_anterior: str


@dataclass(frozen=True)
class CitaModificada(EventoDeDominio):
    AGREGADO: ClassVar[str] = "Cita"
    CAMPO_ID: ClassVar[str] = "cita_id"

    cita_id: str
    propietario_id: str
    mascota_id: str
    servicios_anteriores: Demanda
    servicios_nuevos: Demanda


@dataclass(frozen=True)
class VacunacionRegistrada(EventoDeDominio):
    """Se registró una aplicación de vacuna. No significa que se haya calculado o enviado un
    recordatorio ni que se haya persistido la próxima aplicación (informe, ADR-05)."""

    AGREGADO: ClassVar[str] = "Vacunacion"
    CAMPO_ID: ClassVar[str] = "vacunacion_id"

    vacunacion_id: str
    mascota_id: str
    vacuna: str
    fecha_aplicacion: date
    lote: str | None


@dataclass(frozen=True)
class EmergenciaIdentificada(EventoDeDominio):
    """Recepción identificó formalmente una emergencia y se activó el protocolo (US20, D-14).
    No significa que el veterinario ya haya sido notificado: eso ocurre después del commit."""

    AGREGADO: ClassVar[str] = "Emergencia"
    CAMPO_ID: ClassVar[str] = "emergencia_id"

    emergencia_id: str
    mascota_id: str | None  # P3: la mascota puede no estar registrada
    motivo: str
