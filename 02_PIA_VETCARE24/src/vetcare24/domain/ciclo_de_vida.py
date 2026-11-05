"""Máquina de estados de la Cita (D-07, D-08, D-12, A-06).

    SOLICITADA --confirmar--> CONFIRMADA --realizar--> REALIZADA
    SOLICITADA --cancelar---> CANCELADA   CONFIRMADA --cancelar--> CANCELADA
    SOLICITADA / CONFIRMADA --modificar--> (el mismo estado)

La tabla TRANSICIONES es la única fuente de verdad de qué acción es válida en cada estado.
Orden de evaluación (D-12): primero que la transición sea válida; después, las condiciones
(solo confirmar las tiene: elegibilidad, servicios habilitados y capacidad).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from enum import StrEnum

from vetcare24.domain.catalogo import ServicioVeterinario
from vetcare24.domain.cita import (
    Cita,
    EstadoCita,
    ServicioSolicitado,
    demanda_de,
    validar_lineas_solicitables,
)
from vetcare24.domain.disponibilidad import Disponibilidad
from vetcare24.domain.errors import PrecondicionNoCumplida, TransicionInvalida
from vetcare24.domain.eventos import CitaAgendada, CitaCancelada, CitaModificada, CitaRealizada
from vetcare24.domain.propietario import Propietario
from vetcare24.domain.reglas_cita import CitaEnContexto, puede_confirmarse


class Accion(StrEnum):
    CONFIRMAR = "confirmar"
    REALIZAR = "realizar"
    CANCELAR = "cancelar"
    MODIFICAR = "modificar"


TRANSICIONES: Mapping[tuple[EstadoCita, Accion], EstadoCita] = {
    (EstadoCita.SOLICITADA, Accion.CONFIRMAR): EstadoCita.CONFIRMADA,
    (EstadoCita.CONFIRMADA, Accion.REALIZAR): EstadoCita.REALIZADA,
    (EstadoCita.SOLICITADA, Accion.CANCELAR): EstadoCita.CANCELADA,
    (EstadoCita.CONFIRMADA, Accion.CANCELAR): EstadoCita.CANCELADA,
    (EstadoCita.SOLICITADA, Accion.MODIFICAR): EstadoCita.SOLICITADA,
    (EstadoCita.CONFIRMADA, Accion.MODIFICAR): EstadoCita.CONFIRMADA,
}


def ahora_utc() -> datetime:
    return datetime.now(UTC)


class CicloDeVidaDeCita:
    """Servicio de dominio: aplica las acciones sobre una cita respetando la máquina.

    Cada transición exitosa deja su evento en la cita (`cita.extraer_eventos()`). Si la acción
    falla, no se registra ningún evento. El reloj se inyecta para poder probar con horas fijas.
    """

    def __init__(self, reloj: Callable[[], datetime] = ahora_utc) -> None:
        self._puede_confirmarse = puede_confirmarse()
        self._reloj = reloj

    @staticmethod
    def _destino(cita: Cita, accion: Accion) -> EstadoCita:
        destino = TRANSICIONES.get((cita.estado, accion))
        if destino is None:
            raise TransicionInvalida(cita.estado.value, accion.value)
        return destino

    def confirmar(
        self,
        cita: Cita,
        propietario: Propietario,
        catalogo: Mapping[str, ServicioVeterinario],
        disponibilidad: Disponibilidad,
    ) -> None:
        destino = self._destino(cita, Accion.CONFIRMAR)
        contexto = CitaEnContexto(cita, propietario, catalogo, disponibilidad.como_mapa())
        evaluacion = self._puede_confirmarse.evaluar(contexto)
        if not evaluacion.cumple:
            raise PrecondicionNoCumplida(Accion.CONFIRMAR.value, evaluacion.motivos)
        disponibilidad.reservar(cita.demanda_por_servicio())
        cita._establecer_estado(destino)
        cita._registrar_evento(CitaAgendada(
            ocurrido_en=self._reloj(),
            cita_id=cita.cita_id,
            propietario_id=cita.propietario_id,
            mascota_id=cita.mascota_id,
            servicios=tuple(cita.demanda_por_servicio().items()),
            total=cita.total(catalogo),
        ))

    def realizar(self, cita: Cita) -> None:
        cita._establecer_estado(self._destino(cita, Accion.REALIZAR))
        cita._registrar_evento(CitaRealizada(
            ocurrido_en=self._reloj(),
            cita_id=cita.cita_id,
            propietario_id=cita.propietario_id,
            mascota_id=cita.mascota_id,
        ))

    def cancelar(self, cita: Cita, disponibilidad: Disponibilidad) -> None:
        destino = self._destino(cita, Accion.CANCELAR)
        estado_anterior = cita.estado
        if estado_anterior is EstadoCita.CONFIRMADA:
            disponibilidad.liberar(cita.demanda_por_servicio())
        cita._establecer_estado(destino)
        cita._registrar_evento(CitaCancelada(
            ocurrido_en=self._reloj(),
            cita_id=cita.cita_id,
            propietario_id=cita.propietario_id,
            mascota_id=cita.mascota_id,
            estado_anterior=estado_anterior.value,
        ))

    def modificar(
        self,
        cita: Cita,
        nuevas_lineas: Iterable[ServicioSolicitado],
        catalogo: Mapping[str, ServicioVeterinario],
        disponibilidad: Disponibilidad,
    ) -> None:
        self._destino(cita, Accion.MODIFICAR)
        lineas = tuple(nuevas_lineas)
        validar_lineas_solicitables(lineas, catalogo)
        anterior = cita.demanda_por_servicio()
        nueva = demanda_de(lineas)
        if cita.estado is EstadoCita.CONFIRMADA:
            faltan = disponibilidad.faltantes(nueva, liberando=anterior)
            if faltan:
                raise PrecondicionNoCumplida(
                    Accion.MODIFICAR.value,
                    tuple(f"CAPACIDAD_INSUFICIENTE:{servicio_id}" for servicio_id in faltan),
                )
            disponibilidad.liberar(anterior)
            disponibilidad.reservar(nueva)
        cita._reemplazar_lineas(lineas)
        cita._registrar_evento(CitaModificada(
            ocurrido_en=self._reloj(),
            cita_id=cita.cita_id,
            propietario_id=cita.propietario_id,
            mascota_id=cita.mascota_id,
            servicios_anteriores=tuple(anterior.items()),
            servicios_nuevos=tuple(nueva.items()),
        ))
