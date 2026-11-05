"""Acceso a la base de datos: una conexión pequeña que funciona con PostgreSQL y con SQLite.

PostgreSQL es la base real (Docker Compose). SQLite se usa en pruebas rápidas. Todo el SQL del
proyecto se escribe una sola vez con `?` como marcador y aquí se adapta a cada motor.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Dialecto:
    nombre: str  # "postgresql" o "sqlite"

    @property
    def es_postgres(self) -> bool:
        return self.nombre == "postgresql"

    @property
    def llave_serie(self) -> str:
        """Columna numérica que se autoincrementa."""
        if self.es_postgres:
            return "BIGSERIAL PRIMARY KEY"
        return "INTEGER PRIMARY KEY AUTOINCREMENT"

    def adaptar(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.es_postgres else sql


class Conexion:
    def __init__(self, cruda: Any, dialecto: Dialecto) -> None:
        self._cruda = cruda
        self.dialecto = dialecto

    def ejecutar(self, sql: str, parametros: Sequence[Any] = ()) -> None:
        self.consultar(sql, parametros)

    def consultar(self, sql: str, parametros: Sequence[Any] = ()) -> list[tuple[Any, ...]]:
        sentencia = self.dialecto.adaptar(sql)
        if self.dialecto.es_postgres:
            with self._cruda.cursor() as cursor:
                cursor.execute(sentencia, tuple(parametros))
                return [tuple(fila) for fila in cursor.fetchall()] if cursor.description else []
        cursor = self._cruda.execute(sentencia, tuple(parametros))
        return [tuple(fila) for fila in cursor.fetchall()]

    def commit(self) -> None:
        self._cruda.commit()

    def rollback(self) -> None:
        self._cruda.rollback()

    def cerrar(self) -> None:
        self._cruda.close()


def conectar(url: str) -> Conexion:
    """Abre una conexión. `url`: postgresql://usuario:clave@host:puerto/base o sqlite:///ruta."""
    if url.startswith("sqlite:///"):
        cruda = sqlite3.connect(url.removeprefix("sqlite:///"))
        cruda.execute("PRAGMA foreign_keys = ON")
        return Conexion(cruda, Dialecto("sqlite"))
    if url.startswith(("postgresql://", "postgresql+psycopg://")):
        import psycopg  # solo hace falta cuando se usa PostgreSQL

        dsn = url.replace("postgresql+psycopg://", "postgresql://", 1)
        return Conexion(psycopg.connect(dsn), Dialecto("postgresql"))
    raise ValueError(f"URL de base de datos no soportada: {url.split('://')[0]}://")
