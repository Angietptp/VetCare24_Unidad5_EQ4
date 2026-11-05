"""Validaciones pequeñas y reutilizables para los constructores del dominio."""

from __future__ import annotations

from vetcare24.domain.errors import InvarianteViolada


def exigir_texto(valor: object, codigo: str, nombre: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise InvarianteViolada(codigo, f"{nombre} no puede estar vacío")
    return valor


def exigir_entero(valor: object, *, minimo: int, codigo: str, nombre: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise InvarianteViolada(codigo, f"{nombre} debe ser un entero")
    if valor < minimo:
        raise InvarianteViolada(codigo, f"{nombre} debe ser al menos {minimo}")
    return valor


def exigir_booleano(valor: object, codigo: str, nombre: str) -> bool:
    if not isinstance(valor, bool):
        raise InvarianteViolada(codigo, f"{nombre} debe ser verdadero o falso")
    return valor
