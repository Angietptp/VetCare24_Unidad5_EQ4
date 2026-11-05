"""Disponibilidad: cuánta capacidad le queda a cada servicio (D-08).

Se consume al CONFIRMAR una cita y se libera al cancelarla. Realizar una cita no libera.
Nunca baja de cero ni sube por encima de la capacidad del catálogo.
"""

from __future__ import annotations

from collections.abc import Mapping

from vetcare24.domain._validacion import exigir_entero, exigir_texto
from vetcare24.domain.catalogo import ServicioVeterinario
from vetcare24.domain.errors import InvarianteViolada


class Disponibilidad:
    def __init__(self, capacidades: Mapping[str, int]) -> None:
        self._capacidad: dict[str, int] = {}
        for servicio_id, capacidad in capacidades.items():
            exigir_texto(servicio_id, "ID_VACIO", "El id del servicio")
            exigir_entero(capacidad, minimo=0, codigo="CAPACIDAD_INVALIDA", nombre="La capacidad")
            self._capacidad[servicio_id] = capacidad
        self._reservado: dict[str, int] = dict.fromkeys(self._capacidad, 0)

    @classmethod
    def desde_catalogo(cls, catalogo: Mapping[str, ServicioVeterinario]) -> Disponibilidad:
        return cls({servicio_id: s.capacidad for servicio_id, s in catalogo.items()})

    def disponible(self, servicio_id: str) -> int:
        """Unidades libres. Un servicio desconocido cuenta como 0 (falla cerrado)."""
        return self._capacidad.get(servicio_id, 0) - self._reservado.get(servicio_id, 0)

    def reservado(self, servicio_id: str) -> int:
        return self._reservado.get(servicio_id, 0)

    def como_mapa(self) -> dict[str, int]:
        return {servicio_id: self.disponible(servicio_id) for servicio_id in self._capacidad}

    def faltantes(
        self, demanda: Mapping[str, int], *, liberando: Mapping[str, int] | None = None
    ) -> tuple[str, ...]:
        """Servicios cuya demanda no cabe. `liberando` simula devolver unidades antes."""
        devueltas = liberando or {}
        return tuple(
            servicio_id
            for servicio_id, pedido in demanda.items()
            if pedido > self.disponible(servicio_id) + devueltas.get(servicio_id, 0)
        )

    def reservar(self, demanda: Mapping[str, int]) -> None:
        """Consume capacidad. Todo o nada: si algo no cabe, no se reserva nada."""
        faltan = self.faltantes(demanda)
        if faltan:
            raise InvarianteViolada(
                "CAPACIDAD_INSUFICIENTE", f"No hay capacidad para: {', '.join(faltan)}"
            )
        for servicio_id, cantidad in demanda.items():
            self._reservado[servicio_id] += cantidad

    def liberar(self, demanda: Mapping[str, int]) -> None:
        """Devuelve capacidad. Todo o nada; no se puede liberar más de lo reservado."""
        for servicio_id, cantidad in demanda.items():
            if cantidad > self.reservado(servicio_id):
                raise InvarianteViolada(
                    "LIBERACION_INVALIDA",
                    f"{servicio_id}: se intenta liberar {cantidad} y hay "
                    f"{self.reservado(servicio_id)} reservadas",
                )
        for servicio_id, cantidad in demanda.items():
            self._reservado[servicio_id] -= cantidad
