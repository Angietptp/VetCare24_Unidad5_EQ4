"""Cita: raíz del agregado (D-01). Una solicitud de servicios veterinarios para una mascota.

Hay dos formas de obtener una Cita:
- `Cita.solicitar(...)`: crear una cita NUEVA. Aplica las reglas de negocio (D-09): al menos
  una línea, servicios existentes y habilitados, y que la mascota sea del propietario.
- `Cita(...)`: reconstituir una cita que ya existía (desde los CSV o la base de datos). Solo
  valida la estructura; no vuelve a aplicar reglas de negocio, porque los datos históricos
  pueden contener casos que hoy se rechazarían (tutor inactivo, sin detalle...).

Las transiciones de estado llegan en la Etapa 5; los eventos, en la Etapa 6.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from vetcare24.domain._validacion import exigir_booleano, exigir_entero, exigir_texto
from vetcare24.domain.catalogo import ServicioVeterinario
from vetcare24.domain.errors import InvarianteViolada
from vetcare24.domain.eventos import EventoDeDominio
from vetcare24.domain.mascota import Mascota
from vetcare24.domain.money import Money
from vetcare24.domain.propietario import Propietario


class EstadoCita(StrEnum):
    SOLICITADA = "SOLICITADA"
    CONFIRMADA = "CONFIRMADA"
    REALIZADA = "REALIZADA"
    CANCELADA = "CANCELADA"


@dataclass(frozen=True)
class ServicioSolicitado:
    """Una línea de la cita: qué servicio y cuántas unidades."""

    servicio_id: str
    cantidad: int

    def __post_init__(self) -> None:
        exigir_texto(self.servicio_id, "ID_VACIO", "El id del servicio solicitado")
        exigir_entero(self.cantidad, minimo=1, codigo="CANTIDAD_INVALIDA", nombre="La cantidad")


def demanda_de(lineas: Iterable[ServicioSolicitado]) -> dict[str, int]:
    """Unidades pedidas por servicio (si un servicio se repite en varias líneas, se suman)."""
    demanda: dict[str, int] = {}
    for linea in lineas:
        demanda[linea.servicio_id] = demanda.get(linea.servicio_id, 0) + linea.cantidad
    return demanda


def validar_lineas_solicitables(
    lineas: tuple[ServicioSolicitado, ...], catalogo: Mapping[str, ServicioVeterinario]
) -> None:
    """Reglas de negocio de las líneas de una cita nueva o modificada (D-09)."""
    if not lineas:
        raise InvarianteViolada("DETALLE_VACIO", "La cita necesita al menos un servicio")
    for linea in lineas:
        servicio = catalogo.get(linea.servicio_id)
        if servicio is None:
            raise InvarianteViolada(
                "SERVICIO_INEXISTENTE", f"{linea.servicio_id} no está en el catálogo"
            )
        if not servicio.habilitado:
            raise InvarianteViolada(
                "SERVICIO_DESHABILITADO", f"{linea.servicio_id} está deshabilitado"
            )


class Cita:
    def __init__(
        self,
        *,
        cita_id: str,
        propietario_id: str,
        mascota_id: str,
        lineas: Iterable[ServicioSolicitado],
        fecha_solicitud: date,
        estado: EstadoCita,
        autorizada: bool,
        promocion_activa: bool = False,
        referencia: str | None = None,
    ) -> None:
        exigir_texto(cita_id, "ID_VACIO", "El id de la cita")
        exigir_texto(propietario_id, "PROPIETARIO_REQUERIDO", "El propietario de la cita")
        exigir_texto(mascota_id, "MASCOTA_REQUERIDA", "La mascota de la cita")
        lineas = tuple(lineas)
        if not all(isinstance(linea, ServicioSolicitado) for linea in lineas):
            raise TypeError("Las líneas deben ser ServicioSolicitado")
        if not isinstance(fecha_solicitud, date):
            raise InvarianteViolada("FECHA_INVALIDA", "La fecha de solicitud debe ser una fecha")
        if not isinstance(estado, EstadoCita):
            raise InvarianteViolada("ESTADO_INVALIDO", f"Estado desconocido: {estado!r}")
        exigir_booleano(autorizada, "AUTORIZADA_INVALIDA", "autorizada")
        exigir_booleano(promocion_activa, "PROMOCION_INVALIDA", "promocion_activa")
        self._cita_id = cita_id
        self._propietario_id = propietario_id
        self._mascota_id = mascota_id
        self._lineas = lineas
        self._fecha_solicitud = fecha_solicitud
        self._estado = estado
        self._autorizada = autorizada
        self._promocion_activa = promocion_activa
        self._referencia = referencia
        self._eventos: list[EventoDeDominio] = []

    @classmethod
    def solicitar(
        cls,
        *,
        cita_id: str,
        propietario: Propietario,
        mascota: Mascota,
        lineas: Iterable[ServicioSolicitado],
        fecha_solicitud: date,
        catalogo: Mapping[str, ServicioVeterinario],
        autorizada: bool,
        promocion_activa: bool = False,
        referencia: str | None = None,
    ) -> Cita:
        """Crea una cita nueva en estado SOLICITADA aplicando las reglas de negocio."""
        if mascota.propietario_id != propietario.propietario_id:
            raise InvarianteViolada(
                "MASCOTA_AJENA",
                f"{mascota.mascota_id} no pertenece a {propietario.propietario_id} (R-10)",
            )
        lineas = tuple(lineas)
        validar_lineas_solicitables(lineas, catalogo)
        return cls(
            cita_id=cita_id,
            propietario_id=propietario.propietario_id,
            mascota_id=mascota.mascota_id,
            lineas=lineas,
            fecha_solicitud=fecha_solicitud,
            estado=EstadoCita.SOLICITADA,
            autorizada=autorizada,
            promocion_activa=promocion_activa,
            referencia=referencia,
        )

    @property
    def cita_id(self) -> str:
        return self._cita_id

    @property
    def propietario_id(self) -> str:
        return self._propietario_id

    @property
    def mascota_id(self) -> str:
        return self._mascota_id

    @property
    def lineas(self) -> tuple[ServicioSolicitado, ...]:
        return self._lineas

    @property
    def fecha_solicitud(self) -> date:
        return self._fecha_solicitud

    @property
    def estado(self) -> EstadoCita:
        return self._estado

    @property
    def autorizada(self) -> bool:
        return self._autorizada

    @property
    def promocion_activa(self) -> bool:
        return self._promocion_activa

    @property
    def referencia(self) -> str | None:
        return self._referencia

    def total(self, catalogo: Mapping[str, ServicioVeterinario]) -> Money:
        """Suma de precio x cantidad de cada línea, con el precio vigente del catálogo."""
        importes = []
        for linea in self._lineas:
            servicio = catalogo.get(linea.servicio_id)
            if servicio is None:
                raise InvarianteViolada(
                    "SERVICIO_INEXISTENTE", f"{linea.servicio_id} no está en el catálogo"
                )
            importes.append(servicio.precio.por(linea.cantidad))
        return Money.suma(importes)

    def demanda_por_servicio(self) -> dict[str, int]:
        """Unidades pedidas por servicio (si un servicio se repite en varias líneas, se suman)."""
        return demanda_de(self._lineas)

    # Solo los usa el servicio de ciclo de vida (domain/ciclo_de_vida.py): el estado y las
    # líneas no se cambian desde fuera, para que toda transición pase por la máquina de estados.
    def _establecer_estado(self, estado: EstadoCita) -> None:
        self._estado = estado

    def _reemplazar_lineas(self, lineas: tuple[ServicioSolicitado, ...]) -> None:
        self._lineas = lineas

    def _registrar_evento(self, evento: EventoDeDominio) -> None:
        self._eventos.append(evento)

    def extraer_eventos(self) -> tuple[EventoDeDominio, ...]:
        """Entrega los eventos pendientes (en orden) y los olvida: se publican una sola vez."""
        pendientes = tuple(self._eventos)
        self._eventos.clear()
        return pendientes

    def __eq__(self, otro: object) -> bool:
        return isinstance(otro, Cita) and otro._cita_id == self._cita_id

    def __hash__(self) -> int:
        return hash(self._cita_id)

    def __repr__(self) -> str:
        return f"Cita({self._cita_id!r}, {self._estado.value})"
