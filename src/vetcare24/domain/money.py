"""Money: objeto de valor para importes en pesos mexicanos (D-02).

Reglas: usa Decimal (nunca float), no admite negativos y siempre tiene 2 decimales
(redondeo ROUND_HALF_UP). Es inmutable: sumar o multiplicar crea un Money nuevo.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import ClassVar

from vetcare24.domain._validacion import exigir_entero
from vetcare24.domain.errors import InvarianteViolada

CENTAVO = Decimal("0.01")


@dataclass(frozen=True, order=True)
class Money:
    monto: Decimal
    MONEDA: ClassVar[str] = "MXN"

    def __post_init__(self) -> None:
        object.__setattr__(self, "monto", self._normalizar(self.monto))

    @staticmethod
    def _normalizar(valor: Decimal | int | str) -> Decimal:
        if isinstance(valor, (bool, float)):
            raise InvarianteViolada(
                "MONTO_INVALIDO", "no se aceptan float ni bool; usa Decimal, int o str"
            )
        try:
            numero = valor if isinstance(valor, Decimal) else Decimal(valor)
            if not numero.is_finite():
                raise InvarianteViolada("MONTO_INVALIDO", f"importe no finito: {valor!r}")
            if numero < 0:
                raise InvarianteViolada(
                    "MONTO_INVALIDO", f"el importe no puede ser negativo: {valor!r}"
                )
            return numero.quantize(CENTAVO, rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError) as error:
            raise InvarianteViolada("MONTO_INVALIDO", f"importe ilegible: {valor!r}") from error

    @classmethod
    def mxn(cls, valor: Decimal | int | str) -> Money:
        return cls(valor)

    @classmethod
    def cero(cls) -> Money:
        return cls(Decimal("0"))

    @classmethod
    def suma(cls, montos: Iterable[Money]) -> Money:
        total = cls.cero()
        for monto in montos:
            total = total + monto
        return total

    def __add__(self, otro: object) -> Money:
        if not isinstance(otro, Money):
            return NotImplemented
        return Money(self.monto + otro.monto)

    def por(self, cantidad: int) -> Money:
        """Importe de `cantidad` unidades de este precio."""
        exigir_entero(cantidad, minimo=0, codigo="CANTIDAD_INVALIDA", nombre="La cantidad")
        return Money(self.monto * cantidad)

    def __str__(self) -> str:
        return f"{self.monto:.2f} {self.MONEDA}"
