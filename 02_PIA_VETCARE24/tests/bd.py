"""Ayudas para probar con base de datos.

Cada prueba corre contra SQLite (siempre) y contra PostgreSQL (si DATABASE_URL apunta a uno,
como en Docker Compose y en el CI). Sin PostgreSQL, esa variante se omite.
"""

from __future__ import annotations

import itertools
import os
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from vetcare24.application.despachador import Despachador, RegistroDeEventos
from vetcare24.application.puertos import NotificadorDeVeterinario
from vetcare24.application.servicios import ServicioDeCitas, ServicioDeRegistro
from vetcare24.application.servicios_emergencias import ServicioDeEmergencias
from vetcare24.application.servicios_vacunacion import ServicioDeVacunacion
from vetcare24.domain.catalogo import ServicioVeterinario
from vetcare24.domain.emergencia import Emergencia
from vetcare24.domain.eventos import EventoDeDominio
from vetcare24.domain.mascota import Mascota
from vetcare24.domain.money import Money
from vetcare24.domain.propietario import Propietario
from vetcare24.domain.vacunacion import EsquemaDeVacunacion
from vetcare24.infrastructure.base_de_datos import conectar
from vetcare24.infrastructure.esquema import crear_esquema, eliminar_esquema
from vetcare24.infrastructure.repositorios_sql import UnidadDeTrabajoSql

BACKENDS = ["sqlite", "postgres"]
HORA = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)


def _errores_de_bd() -> tuple[type[Exception], ...]:
    """Errores que lanzan los controladores cuando la base rechaza una operación."""
    errores: tuple[type[Exception], ...] = (sqlite3.Error,)
    try:
        import psycopg
    except ImportError:  # sin PostgreSQL instalado (pruebas locales rápidas)
        return errores
    return (*errores, psycopg.Error)


ERRORES_DE_BD = _errores_de_bd()


def preparar(backend: str, tmp_path: Path) -> str:
    """Devuelve la URL de una base vacía con el esquema recién creado."""
    if backend == "sqlite":
        url = f"sqlite:///{tmp_path / 'vetcare.db'}"
    else:
        url = os.environ.get("DATABASE_URL", "")
        if not url.startswith(("postgresql://", "postgresql+psycopg://")):
            pytest.skip("PostgreSQL no está configurado (DATABASE_URL)")
    conexion = conectar(url)
    eliminar_esquema(conexion)
    crear_esquema(conexion)
    conexion.cerrar()
    return url


def sembrar_basico(url: str, capacidad: int = 5) -> None:
    """Dos servicios habilitados, uno deshabilitado, un propietario y una mascota."""
    with UnidadDeTrabajoSql(url) as uow:
        uow.servicios.agregar(ServicioVeterinario("S1", "Consulta", Money.mxn("300"), capacidad))
        uow.servicios.agregar(ServicioVeterinario("S2", "Vacuna", Money.mxn("100"), capacidad))
        uow.servicios.agregar(
            ServicioVeterinario("S3", "Cerrado", Money.mxn("10"), capacidad, habilitado=False))
        uow.propietarios.agregar(Propietario("P1", "Ana"))
        uow.mascotas.agregar(
            Mascota(mascota_id="M1", propietario_id="P1", nombre="Rex", especie="Perro"))
        uow.commit()


def sembrar_esquemas(url: str) -> None:
    """Tres esquemas: anual validado, refuerzo cada 30 días validado, y uno sin validar."""
    with UnidadDeTrabajoSql(url) as uow:
        uow.esquemas.agregar(EsquemaDeVacunacion(
            vacuna="VAC-ANUAL", frecuencia_dias=365, requiere_refuerzo=False, validado=True))
        uow.esquemas.agregar(EsquemaDeVacunacion(
            vacuna="VAC-REFUERZO", frecuencia_dias=30, requiere_refuerzo=True, validado=True))
        uow.esquemas.agregar(EsquemaDeVacunacion(
            vacuna="VAC-SIN-VALIDAR", frecuencia_dias=90, requiere_refuerzo=True, validado=False))
        uow.commit()


@dataclass
class Entorno:
    url: str
    citas: ServicioDeCitas
    registro: ServicioDeRegistro
    despachador: Despachador
    eventos: RegistroDeEventos
    fabrica: Callable[[], UnidadDeTrabajoSql]
    vacunacion: ServicioDeVacunacion
    emergencias: ServicioDeEmergencias
    reloj: RelojDePrueba
    notificador: NotificadorDePrueba


class RelojDePrueba:
    """Reloj fijo que se puede adelantar (para probar fechas y horas)."""

    def __init__(self, inicio: datetime = HORA) -> None:
        self.ahora = inicio

    def __call__(self) -> datetime:
        return self.ahora

    def avanzar(self, **delta: float) -> None:
        self.ahora += timedelta(**delta)


class NotificadorDePrueba(NotificadorDeVeterinario):
    """Registra cada aviso y, si `falla`, simula que el canal no está disponible. Guarda si la
    emergencia ya estaba confirmada en la base al momento de notificar (informe, CU-05)."""

    def __init__(self, url: str) -> None:
        self._url = url
        self.falla = False
        self.avisos: list[tuple[str, bool]] = []  # (emergencia_id, ¿ya estaba guardada?)

    def notificar(self, emergencia: Emergencia) -> None:
        with UnidadDeTrabajoSql(self._url) as uow:  # otra conexión: solo ve lo confirmado
            guardada = uow.emergencias.obtener(emergencia.emergencia_id) is not None
        self.avisos.append((emergencia.emergencia_id, guardada))
        if self.falla:
            raise ConnectionError("canal de avisos no disponible")


def armar(url: str) -> Entorno:
    despachador, eventos = Despachador(), RegistroDeEventos()
    despachador.suscribir(EventoDeDominio, eventos)
    contador = itertools.count(1)

    def generar(prefijo: str) -> str:
        return f"{prefijo}-{next(contador):03d}"

    def fabrica() -> UnidadDeTrabajoSql:
        return UnidadDeTrabajoSql(url)

    reloj, notificador = RelojDePrueba(), NotificadorDePrueba(url)
    return Entorno(
        url, ServicioDeCitas(fabrica, despachador, generar_id=generar),
        ServicioDeRegistro(fabrica, generar), despachador, eventos, fabrica,
        ServicioDeVacunacion(fabrica, despachador, reloj=lambda: HORA, generar_id=generar),
        ServicioDeEmergencias(fabrica, despachador, notificador, reloj=reloj,
                              generar_id=generar),
        reloj, notificador)
