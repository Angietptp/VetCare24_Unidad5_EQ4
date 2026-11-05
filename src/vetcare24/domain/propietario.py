"""Propietario: persona responsable de una o más mascotas (NB-01, NB-02).

`preferente` es una extensión del paquete de pruebas (D-05); el BRD no la menciona.
"""

from __future__ import annotations

from dataclasses import dataclass

from vetcare24.domain._validacion import exigir_booleano, exigir_texto


@dataclass(frozen=True)
class Propietario:
    propietario_id: str
    nombre: str
    activo: bool = True
    preferente: bool = False

    def __post_init__(self) -> None:
        exigir_texto(self.propietario_id, "ID_VACIO", "El id del propietario")
        exigir_texto(self.nombre, "NOMBRE_VACIO", "El nombre del propietario")
        exigir_booleano(self.activo, "ACTIVO_INVALIDO", "activo")
        exigir_booleano(self.preferente, "PREFERENTE_INVALIDO", "preferente")
