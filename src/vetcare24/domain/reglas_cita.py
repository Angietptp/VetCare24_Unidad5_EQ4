"""Specifications sobre la Cita (Etapa 4).

Todas evalúan un `CitaEnContexto`: la cita junto con lo que hace falta para juzgarla
(su propietario, el catálogo y la capacidad disponible). Los códigos de motivo coinciden con
los del oráculo.

Origen de cada regla:
- BRD: ActorActivo, DetalleNoVacio, Autorizada, ServiciosHabilitados, CapacidadSuficiente,
  estados que permiten cancelar o modificar (NB-08, R-09, R-14, D-07, A-06).
- Extensión del paquete (D-05): PropietarioPreferente, TotalMinimo, PromocionActiva.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field

from vetcare24.domain.catalogo import ServicioVeterinario
from vetcare24.domain.cita import Cita, EstadoCita
from vetcare24.domain.errors import InvarianteViolada
from vetcare24.domain.money import Money
from vetcare24.domain.propietario import Propietario
from vetcare24.domain.specification import Not, Specification

UMBRAL_BENEFICIO = Money.mxn("1500")


def disponibilidad_inicial(catalogo: Mapping[str, ServicioVeterinario]) -> dict[str, int]:
    """Capacidad completa de cada servicio, antes de confirmar ninguna cita."""
    return {servicio_id: s.capacidad for servicio_id, s in catalogo.items()}


@dataclass(frozen=True)
class CitaEnContexto:
    cita: Cita
    propietario: Propietario
    catalogo: Mapping[str, ServicioVeterinario]
    disponible: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.cita.propietario_id != self.propietario.propietario_id:
            raise InvarianteViolada(
                "PROPIETARIO_INCORRECTO",
                f"{self.cita.cita_id} es de {self.cita.propietario_id}, "
                f"no de {self.propietario.propietario_id}",
            )


Regla = Specification[CitaEnContexto]


# --- Specifications atómicas ---------------------------------------------------------------

class ActorActivo(Regla):
    codigo = "ACTOR_INACTIVO"

    def es_satisfecha_por(self, c: CitaEnContexto) -> bool:
        return c.propietario.activo


class DetalleNoVacio(Regla):
    codigo = "DETALLE_VACIO"

    def es_satisfecha_por(self, c: CitaEnContexto) -> bool:
        return len(c.cita.lineas) > 0


class Autorizada(Regla):
    codigo = "NO_AUTORIZADA"

    def es_satisfecha_por(self, c: CitaEnContexto) -> bool:
        return c.cita.autorizada


class PropietarioPreferente(Regla):
    codigo = "NO_PREFERENTE"

    def es_satisfecha_por(self, c: CitaEnContexto) -> bool:
        return c.propietario.preferente


class PromocionActiva(Regla):
    codigo = "SIN_PROMOCION"

    def es_satisfecha_por(self, c: CitaEnContexto) -> bool:
        return c.cita.promocion_activa


class TotalMinimo(Regla):
    codigo = "TOTAL_INSUFICIENTE"

    def __init__(self, umbral: Money) -> None:
        self.umbral = umbral

    def es_satisfecha_por(self, c: CitaEnContexto) -> bool:
        return c.cita.total(c.catalogo) >= self.umbral

    def descripcion(self) -> str:
        return f"TotalMinimo({self.umbral})"


class ServiciosHabilitados(Regla):
    """Todos los servicios de la cita existen en el catálogo y están habilitados."""

    def _problemas(self, c: CitaEnContexto) -> Iterator[str]:
        for linea in c.cita.lineas:
            servicio = c.catalogo.get(linea.servicio_id)
            if servicio is None:
                yield f"SERVICIO_INEXISTENTE:{linea.servicio_id}"
            elif not servicio.habilitado:
                yield f"SERVICIO_DESHABILITADO:{linea.servicio_id}"

    def es_satisfecha_por(self, c: CitaEnContexto) -> bool:
        return next(self._problemas(c), None) is None

    def motivos_de_incumplimiento(self, c: CitaEnContexto) -> tuple[str, ...]:
        return tuple(dict.fromkeys(self._problemas(c)))


class CapacidadSuficiente(Regla):
    """La demanda de cada servicio cabe en la capacidad disponible."""

    def _faltantes(self, c: CitaEnContexto) -> Iterator[str]:
        for servicio_id, pedido in c.cita.demanda_por_servicio().items():
            if pedido > c.disponible.get(servicio_id, 0):
                yield f"CAPACIDAD_INSUFICIENTE:{servicio_id}"

    def es_satisfecha_por(self, c: CitaEnContexto) -> bool:
        return next(self._faltantes(c), None) is None

    def motivos_de_incumplimiento(self, c: CitaEnContexto) -> tuple[str, ...]:
        return tuple(dict.fromkeys(self._faltantes(c)))


class EnEstado(Regla):
    def __init__(self, estado: EstadoCita) -> None:
        self.estado = estado
        self.codigo = f"NO_ESTA_{estado.value}"

    def es_satisfecha_por(self, c: CitaEnContexto) -> bool:
        return c.cita.estado is self.estado

    def descripcion(self) -> str:
        return f"EnEstado({self.estado.value})"


# --- Reglas compuestas (las que usan los casos de uso) -------------------------------------

def puede_procesarse() -> Regla:
    """D-03: ActorActivo AND DetalleNoVacio AND Autorizada."""
    return ActorActivo() & DetalleNoVacio() & Autorizada()


def puede_confirmarse() -> Regla:
    """D-12: elegibilidad AND servicios habilitados AND capacidad suficiente."""
    return puede_procesarse() & ServiciosHabilitados() & CapacidadSuficiente()


def beneficio_de_referencia(umbral: Money = UMBRAL_BENEFICIO) -> Regla:
    """D-05: PropietarioPreferente AND TotalMinimo AND NOT PromocionActiva."""
    sin_promocion = Not(PromocionActiva(), "PROMOCION_ACTIVA")
    return PropietarioPreferente() & TotalMinimo(umbral) & sin_promocion


def esta_finalizada() -> Regla:
    """D-07: REALIZADA OR CANCELADA (estados terminales)."""
    return EnEstado(EstadoCita.REALIZADA) | EnEstado(EstadoCita.CANCELADA)


def puede_cancelarse() -> Regla:
    """D-07 / NB-08: se cancela mientras la cita no esté finalizada."""
    return Not(esta_finalizada(), "CITA_FINALIZADA")


def puede_modificarse() -> Regla:
    """A-06 / NB-08: se modifica mientras la cita no esté finalizada."""
    return Not(esta_finalizada(), "CITA_FINALIZADA")
