"""Emergencia (CU-05, US20, NB-19, R-06): atención prioritaria SIN exigir una cita previa.

Recepción identifica la emergencia; al registrarla se activa el protocolo y se notifica al
veterinario (A-01, BPMN «¿Es una emergencia?» → «Protocolo de Emergencia»). Después, el
personal clínico inicia su atención (A-01, A-09).

    IDENTIFICADA --iniciar_atencion--> EN_ATENCION

La mascota es opcional (P3): una mascota que llega por primera vez puede no estar registrada;
en ese caso se guardan los datos disponibles del paciente como texto libre.
El cierre de la emergencia y sus criterios de activación quedan fuera de alcance (pendientes
del informe, CR-8).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from enum import StrEnum

from vetcare24.domain._validacion import exigir_texto
from vetcare24.domain.errors import InvarianteViolada, TransicionInvalida
from vetcare24.domain.eventos import EmergenciaIdentificada, EventoDeDominio
from vetcare24.domain.mascota import Mascota

ENTIDAD = "emergencia"


class EstadoEmergencia(StrEnum):
    IDENTIFICADA = "IDENTIFICADA"  # protocolo activado; espera al personal clínico
    EN_ATENCION = "EN_ATENCION"


class AccionEmergencia(StrEnum):
    INICIAR_ATENCION = "iniciar_atencion"


TRANSICIONES: Mapping[tuple[EstadoEmergencia, AccionEmergencia], EstadoEmergencia] = {
    (EstadoEmergencia.IDENTIFICADA, AccionEmergencia.INICIAR_ATENCION):
        EstadoEmergencia.EN_ATENCION,
}

# Sin cierre definido, toda emergencia registrada sigue activa (N-05).
ESTADOS_ACTIVOS = frozenset(EstadoEmergencia)


def _con_zona(valor: object, nombre: str) -> datetime:
    if not isinstance(valor, datetime) or valor.tzinfo is None or valor.utcoffset() is None:
        raise InvarianteViolada(
            "FECHA_HORA_SIN_ZONA", f"{nombre} debe ser una fecha y hora con zona horaria")
    return valor


def _limpiar(texto: str) -> str:
    return " ".join(texto.split())


class Emergencia:
    """Agregado raíz. El constructor reconstituye y valida la estructura; una emergencia nueva
    se registra con `CicloDeVidaDeEmergencia.identificar` (como F-01)."""

    def __init__(
        self,
        *,
        emergencia_id: str,
        motivo: str,
        identificada_en: datetime,
        mascota_id: str | None = None,
        datos_paciente: str | None = None,
        estado: EstadoEmergencia = EstadoEmergencia.IDENTIFICADA,
        atendida_en: datetime | None = None,
    ) -> None:
        exigir_texto(emergencia_id, "ID_VACIO", "El id de la emergencia")
        exigir_texto(motivo, "MOTIVO_VACIO", "El motivo de la emergencia")
        _con_zona(identificada_en, "identificada_en")
        if mascota_id is not None:
            exigir_texto(mascota_id, "MASCOTA_REQUERIDA", "La mascota")
        if datos_paciente is not None:
            exigir_texto(datos_paciente, "DATOS_PACIENTE_VACIOS", "Los datos del paciente")
        if not isinstance(estado, EstadoEmergencia):
            raise InvarianteViolada("ESTADO_INVALIDO", f"Estado desconocido: {estado!r}")
        if atendida_en is not None:
            _con_zona(atendida_en, "atendida_en")
            if atendida_en < identificada_en:
                raise InvarianteViolada(
                    "ATENCION_ANTES_DE_IDENTIFICAR",
                    "La emergencia no puede atenderse antes de ser identificada")
        if (estado is EstadoEmergencia.EN_ATENCION) != (atendida_en is not None):
            raise InvarianteViolada(
                "ESTADO_INCONSISTENTE",
                "Una emergencia EN_ATENCION debe tener fecha de atención, y solo ella")
        self._emergencia_id = emergencia_id
        self._motivo = _limpiar(motivo)
        self._identificada_en = identificada_en
        self._mascota_id = mascota_id
        self._datos_paciente = _limpiar(datos_paciente) if datos_paciente is not None else None
        self._estado = estado
        self._atendida_en = atendida_en
        self._eventos: list[EventoDeDominio] = []

    # --- lectura ---

    @property
    def emergencia_id(self) -> str:
        return self._emergencia_id

    @property
    def motivo(self) -> str:
        return self._motivo

    @property
    def identificada_en(self) -> datetime:
        return self._identificada_en

    @property
    def mascota_id(self) -> str | None:
        return self._mascota_id

    @property
    def datos_paciente(self) -> str | None:
        return self._datos_paciente

    @property
    def estado(self) -> EstadoEmergencia:
        return self._estado

    @property
    def atendida_en(self) -> datetime | None:
        return self._atendida_en

    @property
    def esta_activa(self) -> bool:
        return self._estado in ESTADOS_ACTIVOS

    def extraer_eventos(self) -> tuple[EventoDeDominio, ...]:
        pendientes = tuple(self._eventos)
        self._eventos.clear()
        return pendientes

    # --- solo para CicloDeVidaDeEmergencia (toda transición pasa por la máquina, H-06) ---

    def _atender(self, atendida_en: datetime) -> None:
        Emergencia(  # valida antes de cambiar: si algo falla, el objeto queda como estaba
            emergencia_id=self._emergencia_id, motivo=self.motivo,
            identificada_en=self._identificada_en, mascota_id=self._mascota_id,
            datos_paciente=self._datos_paciente, estado=EstadoEmergencia.EN_ATENCION,
            atendida_en=atendida_en)
        self._estado = EstadoEmergencia.EN_ATENCION
        self._atendida_en = atendida_en

    def _registrar_evento(self, evento: EventoDeDominio) -> None:
        self._eventos.append(evento)

    def __eq__(self, otro: object) -> bool:
        return isinstance(otro, Emergencia) and otro._emergencia_id == self._emergencia_id

    def __hash__(self) -> int:
        return hash(self._emergencia_id)

    def __repr__(self) -> str:
        return f"Emergencia({self._emergencia_id!r}, {self._mascota_id!r}, {self._estado.value})"


class CicloDeVidaDeEmergencia:
    """Servicio de dominio: identifica emergencias e inicia su atención respetando la máquina.

    Registrar una emergencia NO consulta citas (R-06, NB-19): no hay ninguna precondición de
    cita. El reloj se inyecta para probar con horas fijas (I-04).
    """

    def __init__(self, reloj: Callable[[], datetime]) -> None:
        self._reloj = reloj

    def identificar(
        self,
        *,
        emergencia_id: str,
        motivo: str,
        mascota: Mascota | None = None,
        datos_paciente: str | None = None,
    ) -> Emergencia:
        emergencia = Emergencia(
            emergencia_id=emergencia_id, motivo=motivo, identificada_en=self._reloj(),
            mascota_id=mascota.mascota_id if mascota is not None else None,
            datos_paciente=datos_paciente)
        emergencia._registrar_evento(EmergenciaIdentificada(
            ocurrido_en=emergencia.identificada_en,
            emergencia_id=emergencia.emergencia_id,
            mascota_id=emergencia.mascota_id,
            motivo=emergencia.motivo,
        ))
        return emergencia

    def iniciar_atencion(self, emergencia: Emergencia) -> None:
        if (emergencia.estado, AccionEmergencia.INICIAR_ATENCION) not in TRANSICIONES:
            raise TransicionInvalida(
                emergencia.estado.value, AccionEmergencia.INICIAR_ATENCION.value, ENTIDAD)
        emergencia._atender(self._reloj())
