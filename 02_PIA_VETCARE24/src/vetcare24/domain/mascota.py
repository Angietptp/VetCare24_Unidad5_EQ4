"""Mascota: el paciente. Pertenece a un propietario y conserva peso y alergias (NB-03 a NB-05).

Es una entidad: se identifica por su id y puede cambiar (peso, alergias). Las alergias las
captura Recepción y las consulta el veterinario (A-04).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal, InvalidOperation

from vetcare24.domain._validacion import exigir_texto
from vetcare24.domain.errors import InvarianteViolada


def _peso(valor: Decimal | int | str | None) -> Decimal | None:
    if valor is None:
        return None
    if isinstance(valor, (bool, float)):
        raise InvarianteViolada("PESO_INVALIDO", "no se aceptan float ni bool; usa Decimal")
    try:
        numero = valor if isinstance(valor, Decimal) else Decimal(valor)
    except (InvalidOperation, TypeError, ValueError) as error:
        raise InvarianteViolada("PESO_INVALIDO", f"peso ilegible: {valor!r}") from error
    if not numero.is_finite() or numero <= 0:
        raise InvarianteViolada("PESO_INVALIDO", f"el peso debe ser mayor que cero: {valor!r}")
    return numero


class Mascota:
    def __init__(
        self,
        *,
        mascota_id: str,
        propietario_id: str,
        nombre: str,
        especie: str,
        raza: str | None = None,
        sexo: str | None = None,
        fecha_nacimiento: date | None = None,
        peso_kg: Decimal | int | str | None = None,
        alergias: Iterable[str] = (),
    ) -> None:
        exigir_texto(mascota_id, "ID_VACIO", "El id de la mascota")
        exigir_texto(propietario_id, "PROPIETARIO_REQUERIDO", "El propietario de la mascota")
        exigir_texto(nombre, "NOMBRE_VACIO", "El nombre de la mascota")
        exigir_texto(especie, "ESPECIE_VACIA", "La especie")
        self._mascota_id = mascota_id
        self._propietario_id = propietario_id
        self._nombre = nombre
        self._especie = especie
        self._raza = raza
        self._sexo = sexo
        self._fecha_nacimiento = fecha_nacimiento
        self._peso_kg = _peso(peso_kg)
        self._alergias: list[str] = []
        for alergia in alergias:
            self.registrar_alergia(alergia)

    @property
    def mascota_id(self) -> str:
        return self._mascota_id

    @property
    def propietario_id(self) -> str:
        return self._propietario_id

    @property
    def nombre(self) -> str:
        return self._nombre

    @property
    def especie(self) -> str:
        return self._especie

    @property
    def raza(self) -> str | None:
        return self._raza

    @property
    def sexo(self) -> str | None:
        return self._sexo

    @property
    def fecha_nacimiento(self) -> date | None:
        return self._fecha_nacimiento

    @property
    def peso_kg(self) -> Decimal | None:
        return self._peso_kg

    @property
    def alergias(self) -> tuple[str, ...]:
        return tuple(self._alergias)

    def registrar_peso(self, peso_kg: Decimal | int | str) -> None:
        """Peso actual (US08). Debe ser mayor que cero."""
        self._peso_kg = _peso(peso_kg)

    def registrar_alergia(self, alergia: str) -> None:
        """Agrega una alergia; si ya estaba (sin importar mayúsculas) no se duplica."""
        exigir_texto(alergia, "ALERGIA_VACIA", "La alergia")
        if alergia.strip().casefold() not in (a.casefold() for a in self._alergias):
            self._alergias.append(alergia.strip())

    def __eq__(self, otro: object) -> bool:
        return isinstance(otro, Mascota) and otro._mascota_id == self._mascota_id

    def __hash__(self) -> int:
        return hash(self._mascota_id)

    def __repr__(self) -> str:
        return f"Mascota({self._mascota_id!r}, {self._nombre!r})"
