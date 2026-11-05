"""Patrón Specification: reglas de negocio como objetos que se pueden combinar.

Una Specification responde a una pregunta sobre un candidato: ¿se cumple la regla?
Se combinan con AND (&), OR (|) y NOT (~). Además de responder sí o no, explican POR QUÉ
no se cumple (`motivos_de_incumplimiento`), que es lo que la API devolverá como error.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Evaluacion:
    cumple: bool
    motivos: tuple[str, ...] = ()


class Specification[T](ABC):
    codigo: str = ""

    @abstractmethod
    def es_satisfecha_por(self, candidato: T) -> bool:
        """True si el candidato cumple la regla."""

    def motivos_de_incumplimiento(self, candidato: T) -> tuple[str, ...]:
        """Códigos que explican por qué NO se cumple (se asume que no se cumple)."""
        return (self.codigo or type(self).__name__,)

    def evaluar(self, candidato: T) -> Evaluacion:
        if self.es_satisfecha_por(candidato):
            return Evaluacion(True)
        return Evaluacion(False, self.motivos_de_incumplimiento(candidato))

    def descripcion(self) -> str:
        return type(self).__name__

    def _como_operando(self) -> str:
        return self.descripcion()

    def __and__(self, otra: Specification[T]) -> Specification[T]:
        return And(self, otra)

    def __or__(self, otra: Specification[T]) -> Specification[T]:
        return Or(self, otra)

    def __invert__(self) -> Specification[T]:
        return Not(self)

    def __str__(self) -> str:
        return self.descripcion()


class And[T](Specification[T]):
    """Se cumple si se cumplen TODAS."""

    def __init__(self, *specs: Specification[T]) -> None:
        planas: list[Specification[T]] = []
        for spec in specs:
            planas.extend(spec.specs if isinstance(spec, And) else [spec])
        if len(planas) < 2:
            raise ValueError("And necesita al menos dos especificaciones")
        self.specs = tuple(planas)

    def es_satisfecha_por(self, candidato: T) -> bool:
        return all(spec.es_satisfecha_por(candidato) for spec in self.specs)

    def motivos_de_incumplimiento(self, candidato: T) -> tuple[str, ...]:
        motivos: list[str] = []
        for spec in self.specs:
            if not spec.es_satisfecha_por(candidato):
                motivos.extend(spec.motivos_de_incumplimiento(candidato))
        return tuple(dict.fromkeys(motivos))

    def descripcion(self) -> str:
        return " AND ".join(spec._como_operando() for spec in self.specs)

    def _como_operando(self) -> str:
        return f"({self.descripcion()})"


class Or[T](Specification[T]):
    """Se cumple si se cumple AL MENOS UNA."""

    def __init__(self, *specs: Specification[T]) -> None:
        planas: list[Specification[T]] = []
        for spec in specs:
            planas.extend(spec.specs if isinstance(spec, Or) else [spec])
        if len(planas) < 2:
            raise ValueError("Or necesita al menos dos especificaciones")
        self.specs = tuple(planas)

    def es_satisfecha_por(self, candidato: T) -> bool:
        return any(spec.es_satisfecha_por(candidato) for spec in self.specs)

    def motivos_de_incumplimiento(self, candidato: T) -> tuple[str, ...]:
        # Si no se cumple el OR, no se cumplió ninguna: se informan todas.
        motivos: list[str] = []
        for spec in self.specs:
            motivos.extend(spec.motivos_de_incumplimiento(candidato))
        return tuple(dict.fromkeys(motivos))

    def descripcion(self) -> str:
        return " OR ".join(spec._como_operando() for spec in self.specs)

    def _como_operando(self) -> str:
        return f"({self.descripcion()})"


class Not[T](Specification[T]):
    """Se cumple si NO se cumple la otra. `codigo` nombra el motivo cuando falla."""

    def __init__(self, spec: Specification[T], codigo: str | None = None) -> None:
        self.spec = spec
        self.codigo = codigo or ""

    def es_satisfecha_por(self, candidato: T) -> bool:
        return not self.spec.es_satisfecha_por(candidato)

    def motivos_de_incumplimiento(self, candidato: T) -> tuple[str, ...]:
        return (self.codigo or f"NO_{self.spec.descripcion()}",)

    def descripcion(self) -> str:
        return f"NOT {self.spec._como_operando()}"
