"""Errores de la capa de aplicación. La API los traduce a códigos HTTP (Etapa 8)."""

from __future__ import annotations


class ErrorDeAplicacion(Exception):
    """Base de los errores de la capa de aplicación."""


class NoEncontrado(ErrorDeAplicacion):
    """No existe lo que se pidió (404)."""

    def __init__(self, tipo: str, identificador: str) -> None:
        self.tipo = tipo
        self.identificador = identificador
        super().__init__(f"No existe {tipo} {identificador!r}")


class YaExiste(ErrorDeAplicacion):
    """Ya hay un registro con ese identificador (409)."""

    def __init__(self, tipo: str, identificador: str) -> None:
        self.tipo = tipo
        self.identificador = identificador
        super().__init__(f"Ya existe {tipo} {identificador!r}")


class AccesoDenegado(ErrorDeAplicacion):
    """El rol no tiene permiso para esa operación (403)."""

    def __init__(self, rol: str, permiso: str) -> None:
        self.rol = rol
        self.permiso = permiso
        super().__init__(f"El rol {rol!r} no tiene el permiso {permiso!r}")
