"""ServicioVeterinario: un servicio del catálogo de la clínica (consulta, vacuna, estudio...)."""

from __future__ import annotations

from dataclasses import dataclass

from vetcare24.domain._validacion import exigir_booleano, exigir_entero, exigir_texto
from vetcare24.domain.money import Money


@dataclass(frozen=True)
class ServicioVeterinario:
    servicio_id: str
    descripcion: str
    precio: Money
    capacidad: int
    habilitado: bool = True

    def __post_init__(self) -> None:
        exigir_texto(self.servicio_id, "ID_VACIO", "El id del servicio")
        exigir_texto(self.descripcion, "DESCRIPCION_VACIA", "La descripción del servicio")
        if not isinstance(self.precio, Money):
            raise TypeError("El precio debe ser un Money")
        exigir_entero(self.capacidad, minimo=0, codigo="CAPACIDAD_INVALIDA", nombre="La capacidad")
        exigir_booleano(self.habilitado, "HABILITADO_INVALIDO", "habilitado")
