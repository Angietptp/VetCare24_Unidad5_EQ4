"""Errores del dominio. Cada violación lleva un código estable (para la API y las pruebas)."""

from __future__ import annotations


class ErrorDeDominio(Exception):
    """Base de todos los errores de reglas de negocio."""


class InvarianteViolada(ErrorDeDominio):
    """Un objeto del dominio no puede existir (o cambiar) de esa forma."""

    def __init__(self, codigo: str, mensaje: str) -> None:
        super().__init__(f"{codigo}: {mensaje}")
        self.codigo = codigo
        self.mensaje = mensaje


class TransicionInvalida(ErrorDeDominio):
    """La acción no está permitida desde el estado actual (la API responde 409)."""

    def __init__(self, estado: str, accion: str, entidad: str = "cita") -> None:
        self.estado = estado
        self.accion = accion
        self.entidad = entidad  # qué agregado rechazó la acción (cita, hospitalización)
        self.motivo = f"{accion} desde {estado}"
        super().__init__(f"Transición inválida: {self.motivo}")


class PrecondicionNoCumplida(ErrorDeDominio):
    """La transición es válida, pero no se cumplen las condiciones para ejecutarla."""

    def __init__(self, accion: str, motivos: tuple[str, ...], entidad: str = "cita") -> None:
        self.accion = accion
        self.motivos = motivos
        self.entidad = entidad
        super().__init__(f"No se puede {accion}: {', '.join(motivos)}")
